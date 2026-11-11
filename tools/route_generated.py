"""Generated route sources (v1.0 spec §6.1 "sources: (generated)", A18; plan Task 15). Never hand-listed:
  - Mystical Agriculture crops, from the dev export kubejs/exported/ma_crops.json (kubejs/server_scripts/routeexport.js,
    Mystical Agriculture's own crop registry): seeds (+ crux, + a required biome's dimension) -> essence;
  - Productive Bees, from the dump's rows of GENERATED_TYPES plus each bee's flower from its definition in the pinned jar
    (data/productivebees/productivebees/**.json whose load conditions hold; bee id productivebees:<file stem>).
The centrifuge stays a normal recipe: check_route.Reader reads its productivebees:component ingredient as comb:<bee>.
Every shape this module cannot read is a problem string (UNMODELLED, UNMAPPED BIOME, BEE FLOWER, NO GENERATED SOURCE), never a
silent skip; check_route.py fails on any of them.
"""
import io
import json
import re
import zipfile
from pathlib import Path

from route_sources import Rule

ROOT = Path(__file__).resolve().parents[1]
EXPORTED = ROOT / ".run" / "server" / "kubejs" / "exported"
MA_CROPS = EXPORTED / "ma_crops.json"
MODS = ROOT / ".run" / "server" / "mods"
PB_DEFS = "data/productivebees/productivebees/"
SPAWNING, BREEDING, CONVERSION = "productivebees:bee_spawning", "productivebees:bee_breeding", "productivebees:bee_conversion"
FISHING, ITEM_CONVERSION, BEEHIVE = ("productivebees:bee_fishing", "productivebees:item_conversion",
                                     "productivebees:advanced_beehive")
GENERATED_TYPES = frozenset({SPAWNING, BREEDING, CONVERSION, FISHING, ITEM_CONVERSION, BEEHIVE})
CONFIGURABLE_COMB = "productivebees:configurable_honeycomb"
FEEDER = "productivebees:feeder"
# Each type's keys: its codec's field names (javap -c on cy/jdkdigital/productivebees/common/recipe/<Type>Recipe and
# $Serializer in productivebees-1.21.1-13.13.5.jar) plus type and neoforge:conditions. Any other key is UNMODELLED (Task 15
# review I4). Read: the inputs below; not inputs: chance, parentDeathChance, pollinates (a mode, the ingredient still holds).
BASE_KEYS = {"type", "neoforge:conditions"}
ALLOWED_KEYS = {
    SPAWNING: BASE_KEYS | {"ingredient", "results", "biomes", "spawn_item"},
    BREEDING: BASE_KEYS | {"parent1", "parent2", "offspring", "parentDeathChance"},
    CONVERSION: BASE_KEYS | {"source", "result", "item", "chance"},
    FISHING: BASE_KEYS | {"bee", "biomes", "chance"},
    ITEM_CONVERSION: BASE_KEYS | {"bees", "ingredients", "result", "chance", "pollinates"},
    BEEHIVE: BASE_KEYS | {"ingredient", "results"},
}
SEEDS = re.compile(r"mysticalagri(culture|additions):[a-z0-9_]+_seeds")


def pb_jar():
    """The one productivebees jar in .run/server/mods, or None."""
    jars = sorted(MODS.glob("productivebees-*.jar"))
    assert len(jars) <= 1, jars
    return jars[0] if jars else None


MOD_ID = re.compile(r'^\s*modId\s*=\s*"([^"]+)"', re.M)


def loaded_mod_ids(mods_dir: Path = MODS) -> set:
    """Every modId in META-INF/neoforge.mods.toml of each jar in mods_dir and of its jar-in-jar jars, plus minecraft and
    neoforge."""
    ids = {"minecraft", "neoforge"}

    def read(z):
        for name in z.namelist():
            if name == "META-INF/neoforge.mods.toml":
                ids.update(MOD_ID.findall(z.read(name).decode("utf-8", "replace")))
            elif name.startswith("META-INF/jarjar/") and name.endswith(".jar"):
                with zipfile.ZipFile(io.BytesIO(z.read(name))) as inner:
                    read(inner)
    for jar in sorted(mods_dir.glob("*.jar")):
        with zipfile.ZipFile(jar) as z:
            read(z)
    return ids


def condition_holds(c, mods, item_members, fluid_members) -> bool:
    """A bee definition's load condition, by the five types the jar uses (plan Task 15: mod_loaded, not, or, tag_empty,
    productivelib:fluid_tag_empty; and is read too). Any other type raises ValueError."""
    t = c.get("type")
    if t == "neoforge:mod_loaded":
        return c["modid"] in mods
    if t == "neoforge:not":
        return not condition_holds(c["value"], mods, item_members, fluid_members)
    if t == "neoforge:and":
        return all(condition_holds(x, mods, item_members, fluid_members) for x in c["values"])
    if t == "neoforge:or":
        return any(condition_holds(x, mods, item_members, fluid_members) for x in c["values"])
    if t == "neoforge:tag_empty":
        return not item_members.get(c["tag"].lstrip("#"))
    if t == "productivelib:fluid_tag_empty":
        return not fluid_members.get(c["tag"].lstrip("#"))
    raise ValueError(f"condition type {t} not read")


def load_bee_definitions(jar: Path, mods, item_members, fluid_members):
    """({bee id: definition}, problems): every data/productivebees/productivebees/**.json in the jar whose `conditions` all
    hold, keyed productivebees:<file stem>. Several files share a stem (chemlib/lithium.json and mekanism/lithium.json), and
    their conditions pick one (plan Task 15: at most one live file per stem at plan time). Two live files for one bee, or a
    condition type not read, is a problem."""
    defs, problems = {}, []
    with zipfile.ZipFile(jar) as z:
        for name in sorted(z.namelist()):
            if not (name.startswith(PB_DEFS) and name.endswith(".json")):
                continue
            d = json.loads(z.read(name))
            try:
                live = all(condition_holds(c, mods, item_members, fluid_members) for c in d.get("conditions", []))
            except (ValueError, KeyError) as e:
                problems.append(f"BEE DEFINITION {name}: {e}")
                continue
            if not live:
                continue
            bee = "productivebees:" + Path(name).stem
            if bee in defs:
                problems.append(f"BEE DEFINITION {name}: a second live definition for {bee}")
                continue
            defs[bee] = d
    return defs, problems


def load_crops(path: Path = MA_CROPS) -> list:
    return json.loads(path.read_text())["crops"]


def biome_groups(biomes, biome_map, where, problems) -> list:
    """A recipe's biome requirement as rule groups: none for an empty list (a HolderSet of size 0, which Productive Bees
    reads as any biome; Task 15 review M2), else one group of dim: tokens."""
    if not isinstance(biomes, str) and len(biomes) == 0:
        return []
    return [biome_tokens(biomes, biome_map, where, problems)]


def biome_tokens(biomes, biome_map, where, problems) -> frozenset:
    """The dim: tokens of a biome id, a biome tag, or a list of them; an unmapped one is a problem (and adds nothing)."""
    out = set()
    for b in [biomes] if isinstance(biomes, str) else list(biomes):
        if b in biome_map:
            out.add("dim:" + biome_map[b])
        else:
            problems.append(f"UNMAPPED BIOME {b} ({where}): add it to route_sources.yaml biome_dimensions")
    return frozenset(out)


def ma_rules(crops, biome_map):
    """(rules, problems): one rule per enabled crop."""
    rules, problems = [], []
    for c in crops:
        if not c["enabled"]:
            continue
        unit = "ma:" + c["id"]
        groups = [frozenset([c["seeds"]])]
        if c["crux"]:
            groups.append(frozenset([c["crux"]]))
        if c["biomes"]:
            groups.append(biome_tokens(c["biomes"], biome_map, unit, problems))
        rules.append(Rule(unit, (c["essence"],), tuple(groups)))
    return rules, problems


def flower_group(bee, defn, block_members, fluid_members, item_members, problems) -> tuple:
    """The rule groups the bee's flower needs: () when it needs no item, else one any-of group, plus a Feeder group when the
    flower is only an item. flowerTag is read as a block tag and as an item tag (ConfigurableBee.isFlowerItem resolves it
    with ModTags.getItemTag, for the Feeder; Task 15 review I2), and the members are one group. An empty group is always a
    BEE FLOWER problem (review I3)."""
    if defn is None:
        return ()   # a bee with no definition file is one of Productive Bees' own classes: no flower data to read
    if defn.get("flowerType") == "entity_types":
        return ()   # the bee "pollinates" entities (its flowerTag is then an entity tag); no item to hold
    if "flowerTag" in defn:
        tag = defn["flowerTag"].lstrip("#")
        blocks, items = frozenset(block_members.get(tag, ())), frozenset(item_members.get(tag, ()))
        if not blocks and not items:
            problems.append(f"BEE FLOWER {bee}: tag {tag} has no members as a block tag or an item tag")
            return (frozenset(),)
        return (blocks | items,) if blocks else (items, frozenset([FEEDER]))
    if isinstance(defn.get("flowerBlock"), str):
        group = frozenset([defn["flowerBlock"]])
    elif isinstance(defn.get("flowerItem"), str):
        group = frozenset([defn["flowerItem"]])
    elif isinstance(defn.get("flowerFluid"), str):
        f = defn["flowerFluid"]
        group = (frozenset("fluid:" + x for x in fluid_members.get(f[1:], ())) if f.startswith("#")
                 else frozenset(["fluid:" + f]))
    else:
        problems.append(f"BEE FLOWER {bee}: no flowerTag, flowerBlock, flowerItem or flowerFluid, and flowerType "
                        f"{defn.get('flowerType')!r}")
        return (frozenset(),)
    if not group:
        flower = {k: v for k, v in defn.items() if k.startswith("flower")}
        problems.append(f"BEE FLOWER {bee}: flower group is empty ({flower})")
    return (group,)


def _ingredient(read_ingredient, v, rid, problems):
    got = read_ingredient(v)
    if got is None:
        problems.append(f"UNMODELLED (c) {rid}: ingredient {json.dumps(v, sort_keys=True)} not read")
    return got


def _shape(t, b, rid, ctx, problems):
    """(outputs, groups) for one generated row, or (None, None) after recording a problem."""
    defs, block_members, fluid_members, item_members, biome_map, read_ingredient, read_products = ctx
    bee = "bee:".__add__
    extra = sorted(set(b) - ALLOWED_KEYS[t])
    if extra:
        problems.append(f"UNMODELLED (c) {rid}: {t} key(s) {extra} not read")
        return None, None
    if t == SPAWNING:
        nest = _ingredient(read_ingredient, b["ingredient"], rid, problems)
        if nest is None:
            return None, None
        groups = [nest] + biome_groups(b["biomes"], biome_map, rid, problems)
        if "spawn_item" in b:   # required (strict: nothing shows a nest spawn passes without it; review I4)
            item = _ingredient(read_ingredient, b["spawn_item"], rid, problems)
            if item is None:
                return None, None
            groups.append(item)
        return {bee(x) for x in b["results"]}, groups
    if t == BREEDING:
        return {bee(b["offspring"])}, [frozenset([bee(b["parent1"])]), frozenset([bee(b["parent2"])])]
    if t == CONVERSION:
        item = _ingredient(read_ingredient, b["item"], rid, problems)
        if item is None:
            return None, None
        return {bee(b["result"])}, [frozenset([bee(b["source"])]), item]
    if t == FISHING:
        return {bee(b["bee"])}, biome_groups(b["biomes"], biome_map, rid, problems)
    if t == ITEM_CONVERSION:
        kind = b["result"]["components"]["minecraft:entity_data"]["type"]
        groups = [frozenset(bee(x) for x in b["bees"])]
        for v in b["ingredients"]:
            g = _ingredient(read_ingredient, v, rid, problems)
            if g is None:
                return None, None
            groups.append(g)
        return {"egg:" + kind, bee(kind)}, groups
    who = b["ingredient"]   # BEEHIVE: the bee in the hive
    # AdvancedBeehiveRecipe.getRecipeOutputs: when the hive bee is configurable (it has a definition), BeeCreator.setType(
    # hive bee, stack) retypes every configurable_honeycomb output, whatever component the recipe wrote (review I1: lead's
    # recipe writes leaden, amethyst's writes none). A built-in bee keeps the component the recipe wrote.
    outs = set(read_products(b)) - {CONFIGURABLE_COMB}
    for r in b["results"]:
        item = r.get("item")
        if not isinstance(item, dict):
            continue
        component = item.get("type") == "productivebees:component"
        if who in defs and (item.get("item") == CONFIGURABLE_COMB or component and item.get("items") == CONFIGURABLE_COMB):
            outs.add("comb:" + who)
        elif component:
            outs.add("comb:" + item["components"]["productivebees:bee_type"])
    groups = [frozenset([bee(who)])]
    groups.extend(flower_group(who, defs.get(who), block_members, fluid_members, item_members, problems))
    return outs, groups


def pb_rules(rows, defs, block_members, fluid_members, item_members, biome_map, machine_groups, read_ingredient,
             read_products):
    """(rules, problems) for every dump row of GENERATED_TYPES. machine_groups: type -> the groups of its machines: entry.
    item_members: the item tag export (flowerTag is also an item tag; review I2)."""
    rules, problems, no_machine = [], [], {}
    ctx = (defs, block_members, fluid_members, item_members, biome_map, read_ingredient, read_products)
    for row in rows:
        t = row.get("type")
        if t not in GENERATED_TYPES or not row.get("json"):
            continue
        rid = row["id"]
        if t not in machine_groups:
            no_machine.setdefault(t, []).append(rid)
            continue
        try:
            outs, groups = _shape(t, json.loads(row["json"]), rid, ctx, problems)
        except (KeyError, TypeError, AttributeError) as e:
            problems.append(f"UNMODELLED (c) {t}: {rid} has a shape route_generated.py does not read ({e!r})")
            continue
        if outs is not None:
            rules.append(Rule(rid, tuple(sorted(outs)), tuple(groups) + tuple(machine_groups[t])))
    for t, rids in sorted(no_machine.items()):   # one line per type, not per row
        problems.append(f"UNMODELLED (a) {t}: no machines: entry in tools/route_sources.yaml ({len(rids)} recipes, first {rids[0]})")
    return rules, problems


def coverage_problems(crops, rules, rows, item_members):
    """Every MA/Agradditions seeds item in the item tag export has a crop; every comb a centrifuge takes has a beehive rule."""
    problems = []
    seeds = {i for ms in item_members.values() for i in ms if SEEDS.fullmatch(i)}
    for s in sorted(seeds - {c["seeds"] for c in crops}):
        problems.append(f"NO GENERATED SOURCE {s}: no crop in ma_crops.json has these seeds")
    made = {o for r in rules for o in r.outputs}
    for row in rows:
        if row.get("type") != "productivebees:centrifuge" or not row.get("json"):
            continue
        ing = json.loads(row["json"]).get("ingredient")
        if isinstance(ing, dict) and ing.get("type") == "productivebees:component":
            comb = "comb:" + ing["components"]["productivebees:bee_type"]
            if comb not in made:
                problems.append(f"NO GENERATED SOURCE {comb}: a centrifuge ({row['id']}) takes it and no beehive rule makes it")
    return problems
