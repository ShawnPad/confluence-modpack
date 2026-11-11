"""tools/route_generated.py (v1.0 plan Task 15; spec §6.1 generated sources)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from route_generated import (EXPORTED, GENERATED_TYPES, condition_holds, coverage_problems, flower_group,  # noqa: E402
                             load_bee_definitions, loaded_mod_ids, ma_rules, pb_jar, pb_rules)
from route_sources import Rule  # noqa: E402

BIOMES = {"#c:is_overworld": "minecraft:overworld", "minecraft:deep_ocean": "minecraft:overworld"}
CROP = {"id": "mysticalagriculture:iron", "enabled": True, "seeds": "mysticalagriculture:iron_seeds",
        "essence": "mysticalagriculture:iron_essence", "crux": None, "material": {"id": "c:ingots/iron", "tag": True},
        "biomes": [], "tier_essence": "mysticalagriculture:tertium_essence",
        "crafting_seed": "mysticalagriculture:prosperity_seed_base"}
MACHINES = {t: (frozenset({"productivebees:advanced_beehive"}),) if t.endswith("advanced_beehive") else () for t in GENERATED_TYPES}


def read_ingredient(v):
    return frozenset([v["item"]]) if isinstance(v, dict) and "item" in v else None


def read_products(b):
    return frozenset()


def row(rid, t, body):
    return {"id": rid, "type": t, "json": json.dumps({"type": t, **body})}


ROWS = [
    row("s", "productivebees:bee_spawning", {"ingredient": {"item": "productivebees:coarse_dirt_nest"},
                                             "results": ["productivebees:leafcutter_bee"], "biomes": "#c:is_overworld"}),
    row("b", "productivebees:bee_breeding", {"parent1": "productivebees:a", "parent2": "productivebees:b",
                                             "offspring": "productivebees:c"}),
    row("c", "productivebees:bee_conversion", {"source": "productivebees:c", "result": "productivebees:d",
                                               "item": {"item": "minecraft:crimson_fungus"}}),
    row("f", "productivebees:bee_fishing", {"bee": "productivebees:sponge", "biomes": ["minecraft:deep_ocean"]}),
    row("i", "productivebees:item_conversion", {"bees": ["productivebees:rancher_bee"],
                                                "ingredients": [{"item": "ad_astra:cheese_block"}],
                                                "result": {"components": {"minecraft:entity_data": {"type": "productivebees:cheese"}},
                                                           "id": "productivebees:spawn_egg_configurable_bee"}}),
    row("h", "productivebees:advanced_beehive", {"ingredient": "productivebees:lead", "results": [
        {"item": {"type": "productivebees:component", "components": {"productivebees:bee_type": "productivebees:lead"},
                  "items": "productivebees:configurable_honeycomb"}}]}),
]
DEFS = {"productivebees:lead": {"flowerTag": "productivebees:flowers/lead"}}
BLOCKS = {"productivebees:flowers/lead": ["minecraft:lead_block_stand_in"]}
ITEMS = {}


def pb(rows, defs=DEFS, blocks=BLOCKS, items=ITEMS, machines=MACHINES):
    return pb_rules(rows, defs, blocks, {}, items, BIOMES, machines, read_ingredient, read_products)


def rules_by_unit():
    rules, problems = pb(ROWS)
    assert problems == []
    return {r.unit: r for r in rules}


def test_ma_rule_is_seeds_crux_and_biome():
    rules, problems = ma_rules([CROP, {**CROP, "id": "x:off", "enabled": False}], BIOMES)
    assert problems == [] and rules == [Rule("ma:mysticalagriculture:iron", ("mysticalagriculture:iron_essence",),
                                             (frozenset({"mysticalagriculture:iron_seeds"}),))]
    rules, _ = ma_rules([{**CROP, "crux": "mysticalagriculture:iron_crux", "biomes": ["#c:is_overworld"]}], BIOMES)
    assert rules[0].groups[1:] == (frozenset({"mysticalagriculture:iron_crux"}), frozenset({"dim:minecraft:overworld"}))
    rules, problems = ma_rules([{**CROP, "biomes": ["x:nowhere"]}], BIOMES)
    assert rules[0].groups[-1] == frozenset() and problems == [
        "UNMAPPED BIOME x:nowhere (ma:mysticalagriculture:iron): add it to route_sources.yaml biome_dimensions"]


def test_each_pb_type():
    r = rules_by_unit()
    assert (r["s"].outputs, r["s"].groups) == (("bee:productivebees:leafcutter_bee",), (
        frozenset({"productivebees:coarse_dirt_nest"}), frozenset({"dim:minecraft:overworld"})))
    assert (r["b"].outputs, r["b"].groups) == (("bee:productivebees:c",), (
        frozenset({"bee:productivebees:a"}), frozenset({"bee:productivebees:b"})))
    assert (r["c"].outputs, r["c"].groups) == (("bee:productivebees:d",), (
        frozenset({"bee:productivebees:c"}), frozenset({"minecraft:crimson_fungus"})))
    assert (r["f"].outputs, r["f"].groups) == (("bee:productivebees:sponge",), (frozenset({"dim:minecraft:overworld"}),))
    assert (r["i"].outputs, r["i"].groups) == (("bee:productivebees:cheese", "egg:productivebees:cheese"), (
        frozenset({"bee:productivebees:rancher_bee"}), frozenset({"ad_astra:cheese_block"})))
    assert (r["h"].outputs, r["h"].groups) == (("comb:productivebees:lead",), (
        frozenset({"bee:productivebees:lead"}), frozenset({"minecraft:lead_block_stand_in"}),
        frozenset({"productivebees:advanced_beehive"})))


def test_pb_fails_closed():
    no_machine = {t: g for t, g in MACHINES.items() if not t.endswith("bee_breeding")}
    _, problems = pb(ROWS, machines=no_machine)
    assert problems == ["UNMODELLED (a) productivebees:bee_breeding: no machines: entry in tools/route_sources.yaml "
                        "(1 recipes, first b)"]
    odd = [row("x", "productivebees:bee_breeding", {"parent1": "productivebees:a"})]
    _, problems = pb(odd)
    assert len(problems) == 1 and problems[0].startswith("UNMODELLED (c) productivebees:bee_breeding: x has a shape")
    unread = [row("y", "productivebees:bee_conversion", {"source": "productivebees:c", "result": "productivebees:d",
                                                         "item": {"type": "neoforge:intersection"}})]
    _, problems = pb(unread)
    assert problems == ['UNMODELLED (c) y: ingredient {"type": "neoforge:intersection"} not read']


def test_flower_group():
    p = []
    assert flower_group("b", None, {}, {}, {}, p) == ()
    assert flower_group("b", {"flowerBlock": "minecraft:dandelion"}, {}, {}, {}, p) == (frozenset({"minecraft:dandelion"}),)
    assert flower_group("b", {"flowerItem": "minecraft:sugar"}, {}, {}, {}, p) == (frozenset({"minecraft:sugar"}),)
    assert flower_group("b", {"flowerFluid": "minecraft:lava"}, {}, {}, {}, p) == (frozenset({"fluid:minecraft:lava"}),)
    assert flower_group("b", {"flowerFluid": "#c:oil"}, {}, {"c:oil": ["x:oil"]}, {}, p) == (frozenset({"fluid:x:oil"}),)
    assert flower_group("b", {"flowerType": "entity_types", "flowerTag": "!x:y"}, {}, {}, {}, p) == ()
    assert p == []
    assert flower_group("b", {"flowerTag": "x:missing"}, {}, {}, {}, p) == (frozenset(),)
    assert flower_group("b", {"flowerType": "blocks"}, {}, {}, {}, p) == (frozenset(),)
    assert p == ["BEE FLOWER b: tag x:missing has no members as a block tag or an item tag",
                 "BEE FLOWER b: no flowerTag, flowerBlock, flowerItem or flowerFluid, and flowerType 'blocks'"]


def test_flower_tag_is_block_and_item_tag():
    """Review I2/I3: ConfigurableBee.isFlowerItem resolves flowerTag as an item tag too (a Feeder holds it). Block and item
    members are one group; item-only also needs a Feeder; an empty group is always a problem."""
    p = []
    both = flower_group("b", {"flowerTag": "x:f"}, {"x:f": ["x:blk"]}, {}, {"x:f": ["x:itm"]}, p)
    assert both == (frozenset({"x:blk", "x:itm"}),)
    only_items = flower_group("b", {"flowerTag": "#x:f"}, {"x:f": []}, {}, {"x:f": ["x:itm"]}, p)
    assert only_items == (frozenset({"x:itm"}), frozenset({"productivebees:feeder"}))
    assert flower_group("b", {"flowerTag": "x:f"}, {}, {}, {"x:f": ["x:itm"]}, p) == only_items
    assert p == []
    assert flower_group("b", {"flowerTag": "x:f"}, {"x:f": []}, {}, {"x:f": []}, p) == (frozenset(),)
    assert flower_group("b", {"flowerFluid": "#c:none"}, {}, {}, {}, p) == (frozenset(),)
    assert p == ["BEE FLOWER b: tag x:f has no members as a block tag or an item tag",
                 "BEE FLOWER b: flower group is empty ({'flowerFluid': '#c:none'})"]


def test_beehive_configurable_comb_takes_the_hive_bee():
    """Review I1: AdvancedBeehiveRecipe.getRecipeOutputs calls BeeCreator.setType(hive bee, stack) on every
    configurable_honeycomb output when the hive bee is configurable (here: has a definition)."""
    defs = {"productivebees:lead": {"flowerBlock": "x:f"}, "productivebees:amethyst": {"flowerBlock": "x:f"}}
    comb = "productivebees:configurable_honeycomb"
    rows = [row("leaden", "productivebees:advanced_beehive", {"ingredient": "productivebees:lead", "results": [
                {"item": {"type": "productivebees:component", "items": comb,
                          "components": {"productivebees:bee_type": "productivebees:leaden"}}}]}),
            row("am", "productivebees:advanced_beehive", {"ingredient": "productivebees:amethyst", "results": [
                {"item": {"item": comb}}, {"item": {"tag": "c:pollens"}, "chance": 0.05}]}),
            row("vanilla", "productivebees:advanced_beehive", {"ingredient": "minecraft:bee", "results": [
                {"item": {"item": comb}}]})]
    rules, problems = pb(rows, defs=defs)
    assert problems == []
    r = {x.unit: x for x in rules}
    assert r["leaden"].outputs == ("comb:productivebees:lead",)
    assert r["am"].outputs == ("comb:productivebees:amethyst",)
    assert r["vanilla"].outputs == ()


def test_bee_recipe_keys_are_allow_listed():
    """Review I4: a key a bee recipe type's codec does not have (or one this module does not read) is UNMODELLED."""
    odd = [row("k", "productivebees:bee_breeding", {"parent1": "productivebees:a", "parent2": "productivebees:b",
                                                    "offspring": "productivebees:c", "catalyst": {"item": "x:y"}})]
    rules, problems = pb(odd)
    assert rules == [] and problems == ["UNMODELLED (c) k: productivebees:bee_breeding key(s) ['catalyst'] not read"]
    ok = [row("k2", "productivebees:bee_breeding", {"parent1": "productivebees:a", "parent2": "productivebees:b",
                                                    "offspring": "productivebees:c", "parentDeathChance": 0.1,
                                                    "neoforge:conditions": []})]
    assert len(pb(ok)[0]) == 1 and pb(ok)[1] == []


def test_spawn_item_is_a_group():
    rows = [row("sp", "productivebees:bee_spawning", {"ingredient": {"item": "productivebees:obsidian_nest"},
                                                      "results": ["productivebees:draconic"],
                                                      "spawn_item": {"item": "minecraft:dragon_breath"},
                                                      "biomes": "#c:is_overworld"})]
    rules, problems = pb(rows)
    assert problems == [] and rules[0].groups == (
        frozenset({"productivebees:obsidian_nest"}), frozenset({"dim:minecraft:overworld"}),
        frozenset({"minecraft:dragon_breath"}))


def test_empty_biome_list_is_anywhere():
    """Review M2: an empty biomes list is a HolderSet of size 0, which the jar reads as 'any biome'."""
    rows = [row("f0", "productivebees:bee_fishing", {"bee": "productivebees:sponge", "biomes": []}),
            row("s0", "productivebees:bee_spawning", {"ingredient": {"item": "productivebees:coarse_dirt_nest"},
                                                      "results": ["productivebees:leafcutter_bee"], "biomes": []})]
    rules, problems = pb(rows)
    r = {x.unit: x for x in rules}
    assert problems == [] and r["f0"].groups == () and r["s0"].groups == (frozenset({"productivebees:coarse_dirt_nest"}),)


def test_coverage():
    rules = list(rules_by_unit().values())
    members = {"c:seeds": ["mysticalagriculture:iron_seeds", "mysticalagriculture:gold_seeds", "minecraft:wheat_seeds"]}
    centrifuge = [row("z", "productivebees:centrifuge", {"ingredient": {
        "type": "productivebees:component", "components": {"productivebees:bee_type": "productivebees:tin"},
        "items": "productivebees:configurable_honeycomb"}, "outputs": []})]
    assert coverage_problems([CROP], rules, centrifuge, members) == [
        "NO GENERATED SOURCE mysticalagriculture:gold_seeds: no crop in ma_crops.json has these seeds",
        "NO GENERATED SOURCE comb:productivebees:tin: a centrifuge (z) takes it and no beehive rule makes it"]


def test_conditions():
    mods, items, fluids = {"mekanism"}, {"c:ingots/lead": ["x:lead"], "c:none": []}, {"c:chocolate": []}
    yes = [{"type": "neoforge:mod_loaded", "modid": "mekanism"},
           {"type": "neoforge:not", "value": {"type": "neoforge:mod_loaded", "modid": "chemlib"}},
           {"type": "neoforge:or", "values": [{"type": "neoforge:mod_loaded", "modid": "gtceu"},
                                              {"type": "neoforge:tag_empty", "tag": "c:none"}]},
           {"type": "neoforge:not", "value": {"type": "neoforge:tag_empty", "tag": "c:ingots/lead"}},
           {"type": "productivelib:fluid_tag_empty", "tag": "c:chocolate"}]
    assert [condition_holds(c, mods, items, fluids) for c in yes] == [True] * 5
    with pytest.raises(ValueError):
        condition_holds({"type": "neoforge:item_exists", "item": "x:y"}, mods, items, fluids)


def test_real_jar_definitions():
    jar = pb_jar()
    members = [EXPORTED / "item_tag_members.json", EXPORTED / "fluid_tag_members.json"]
    if jar is None or not all(p.is_file() for p in members):
        pytest.skip("no productivebees jar or no tag member exports (boot with tools/server_boot.sh first)")
    items = json.loads(members[0].read_text())["minecraft:item"]
    fluids = json.loads(members[1].read_text())["minecraft:fluid"]
    mods = loaded_mod_ids()
    assert {"productivebees", "productivelib", "mekanism"} <= mods and "productivemetalworks" not in mods
    defs, problems = load_bee_definitions(jar, mods, items, fluids)
    assert problems == []
    assert len(defs) == 104   # live definitions at plan time (0.3 mods; 431 file stems, 440 files)
    keys = {k for d in defs.values() for k in d if k.startswith("flower")}
    assert keys <= {"flowerTag", "flowerBlock", "flowerItem", "flowerFluid", "flowerType"}, keys


def test_real_dump_bees_and_seeds():
    """Real data (Task 15 report): a bee in a dump row of a bee-gated type with no live definition must be one of Productive
    Bees' built-in entity classes (lang key entity.productivebees.<name>, or minecraft:bee), so flower_group's `defn is None`
    branch never hides a configurable bee whose conditions this module misread; every configurable bee id there is
    productivebees:<file stem>. Every MA/Agradditions seeds item has a crop in ma_crops.json."""
    jar = pb_jar()
    paths = [EXPORTED / n for n in ("recipes.json", "item_tag_members.json", "fluid_tag_members.json", "ma_crops.json")]
    if jar is None or not all(p.is_file() for p in paths):
        pytest.skip("no productivebees jar or no exports (boot with tools/server_boot.sh first)")
    rows = json.loads(paths[0].read_text())
    items = json.loads(paths[1].read_text())["minecraft:item"]
    fluids = json.loads(paths[2].read_text())["minecraft:fluid"]
    defs, _ = load_bee_definitions(jar, loaded_mod_ids(), items, fluids)
    import zipfile
    with zipfile.ZipFile(jar) as z:
        lang = json.loads(z.read("assets/productivebees/lang/en_us.json"))
    builtin = {"minecraft:bee"} | {"productivebees:" + k.split(".", 2)[2] for k in lang
                                   if k.startswith("entity.productivebees.") and k.count(".") == 2}
    bees = set()
    for r in rows:
        if r["type"] not in GENERATED_TYPES:
            continue
        b = json.loads(r["json"])
        t = r["type"]
        if t == "productivebees:bee_spawning":
            bees.update(b["results"])
        elif t == "productivebees:bee_breeding":
            bees.update([b["parent1"], b["parent2"], b["offspring"]])
        elif t == "productivebees:bee_conversion":
            bees.update([b["source"], b["result"]])
        elif t == "productivebees:bee_fishing":
            bees.add(b["bee"])
        elif t == "productivebees:item_conversion":
            bees.update(b["bees"])
            bees.add(b["result"]["components"]["minecraft:entity_data"]["type"])
        else:
            bees.add(b["ingredient"])
    assert sorted(bees - set(defs) - builtin) == []
    blocks = json.loads((EXPORTED / "block_tag_members.json").read_text())["minecraft:block"]
    hive = [r for r in rows if r["type"] == "productivebees:advanced_beehive"]
    rules, problems = pb_rules(hive, defs, blocks, fluids, items, {}, {"productivebees:advanced_beehive": ()},
                               lambda v: frozenset(), lambda b: frozenset())
    assert problems == []   # every hive bee's flower group reads and is non-empty (review I2/I3: plastic, mithril)
    comb_problems = [p for p in coverage_problems(json.loads(paths[3].read_text())["crops"], rules, rows, items)
                     if p.startswith("NO GENERATED SOURCE comb:")]
    # Review I1 fixes lead and amethyst. niter: honeycomb_saltpeter.json is live but no niter bee is (dusts/niter.json needs
    # a non-empty c:storage_blocks/niter), so its comb has no source in this pack.
    assert [p.split()[3].rstrip(":") for p in comb_problems] == ["comb:productivebees:niter"], comb_problems
    assert len(bees & set(defs)) > 90   # 95 configurable bees at Task 15
    crops = json.loads(paths[3].read_text())["crops"]
    assert [p for p in coverage_problems(crops, [], [], items) if "_seeds" in p] == []
