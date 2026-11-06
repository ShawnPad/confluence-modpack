"""Assert the gate manifest (tools/gates.yaml) against the KubeJS recipe dump, and that every dump row carries its recipe
body (the `json` column dump.js writes since v0.3; a missing or empty one means the dump itself broke).

`sole_producers:` (v0.3 Task 8c) pins, for each gated output, exactly the recipe ids that may make it, read from the dump's
`json` bodies. It replaces the one-off producer checks of plan Tasks 4-8 (Task 4 Step 7, Task 5 Step 7, Task 6 Step 6,
Task 7 Step 7, Task 8 Step 6), which nobody re-ran. The `output` column cannot be used: dump.js fills it from
r.get('result') || r.get('output'), so it is empty for many machine types (Ad Astra, IF, Mekanism chemical rows).

The producer rule. A row produces X when its body yields X under a product key. Each top-level key of a body has a role
(key_role), KubeJS bookkeeping keys (_kubejs_*) aside:
  - a product key: any key whose name contains "result", "output" or "product" (result, output, results, outputs,
    main_output, secondary_output, item_output, output_item, chemical_output, fluid_output, outputFluid, byproduct, ...),
    and the keys TYPE_PRODUCT_KEYS names for one recipe type (cell_disassembly_items, upgraded_block, a block conversion's
    `to`, both compacting inputs, twilightforest:uncrafting's pattern `key`, whose items the uncrafting table gives out, and
    chipped:workbench's `ingredients`, every item of whose matched group is an output);
  - an ingredient key (INGREDIENT_KEYS: type, ingredient(s), key, pattern, input(s), base, addition, template, reagent,
    pedestalItems, catalyst, the Mekanism *_input keys, the load conditions): what the recipe consumes or needs;
  - any other key: unknown.
A product value yields:
  - a string: an item id, read generously (json_item_id: an optional count prefix such as '2x ', then the first run of
    resource-location characters, so a components suffix is dropped); a '#' after the optional count makes it a tag;
  - a list: each element;
  - a dict with `item` (a string, or a nested stack: {item: {count, id}}, {item: {item}}, {amount, item: {id}}): that item;
  - a dict with `stack` (IF laser drill, Ars crush: {chance, maxRange, stack: {count, id}}): that stack;
  - a dict with `id` and `amount` but no `count`: a chemical or fluid ({amount, id}, Mekanism chemicals and fluids alike);
  - any other dict with `id` ({id}, {count, id}, {components, count, id}): that item;
  - a dict with `fluid` ({fluid}, {amount, fluid}): a fluid, read as a chemical;
  - a dict with `tag`: a tag ({amount, tag} without a count is a chemical or fluid tag);
  - a dict with `items` (a custom ingredient written as a product, e.g. productivebees:component): each of its items;
  - a number, boolean or null: nothing.
Anything else is an unknown shape. Task 8c surveyed the 0.3 dump (18880 rows): 103 product values, one in each of 103 rows,
have other shapes (Mystical Agriculture soul extraction {souls, type}; Aether block conversions {block, properties} and
{block}; IF fluid extractor {Name, Properties} and {Name}; AE2 entropy {block}, {fluid}, {drops}), and productivebees:
block_conversion's `to` is a {Name} block state too. They are ignored because none names a listed output.

Tag products (Task 8c round 2, R3). An item tag product makes every listed item output among the tag's members, read from
kubejs/exported/item_tag_members.json (tagcheck.js writes the members of every bound item tag; tools/check_tags.py checks that
it is this boot's; main() also refuses an export older than the dump, STALE TAG MEMBERS). An unbound tag holds nothing. A tag
product with no members export fails (NO TAG MEMBERS), and so does a chemical or fluid tag product while a chemical entry is
listed (UNEXPANDED TAG: no export holds those members).

Failures, one line each, all counted in the "sole producers: N outputs, M bad" line:
  - UNREFERENCED: a listed output no recipe body names (a typo in a `[]` entry would otherwise pass forever), or a listed
    producer that is no recipe id in the dump;
  - NO TAG MEMBERS, UNEXPANDED TAG: above;
  - UNKNOWN SHAPE: a listed output named in a product value that the rule does not read as that output's kind (an unknown
    shape, or an item stack for a `kind: chemical` entry), or named anywhere under an unknown key (a wrapper's
    {recipe: {result}}, a `drops` or `yield` list), or under an ingredient key (not `type`) of a type outside
    CONSUMING_TYPES, the reviewed types that consume their ingredient keys (round 3, C1: an inverted type keeps its products
    there). The same holds for a listed tag, an item tag whose exported members include a listed item output (round 3, C2):
    written '#t' or "tag": "t" (or bare, inside a product value of a shape the rule does not read) under a product key that
    made_by did not read it from, or under an unknown key, it fails; an ingredient key may consume it. It is a failure,
    never a skip. Surveyed over the 0.3 dump: no listed output is named outside the product keys and the ingredient keys of
    CONSUMING_TYPES, and no listed tag outside an ingredient key or a product made_by reads;
  - WRONG PRODUCERS: the producers differ from the entry.

The manifest entry. `<output id>: [<recipe id>, ...]` lists exactly the producers (`[]`: nothing may make it). An entry is an
item unless written `<id>: {kind: chemical, producers: [...]}`, which matches the chemical/fluid stacks above. A flow list may
continue onto the next lines until its bracket closes. A row with no `json` cannot be read; check_recipes already fails it
(NO JSON), so the producer check simply skips it. The manifest is read strictly (load_sole_producers): a top-level key other
than gates:, removed: and sole_producers:, a resource location at column 0, a missing or empty sole_producers: section and
any line it cannot read fail as "sole producers: BAD MANIFEST <reason>", after the gates line.
"""
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DUMP = ROOT / ".run" / "server" / "kubejs" / "exported" / "recipes.json"
# The members of every bound minecraft:item tag, {"minecraft:item": {tag: [item id, ...]}}: kubejs/server_scripts/tagcheck.js
# writes it at ServerEvents.loaded, and tools/check_tags.py checks it is this boot's (each tag's member count equals tags.json's).
ITEM_MEMBERS = ROOT / ".run" / "server" / "kubejs" / "exported" / "item_tag_members.json"
ITEM_REGISTRY = "minecraft:item"
MANIFEST = ROOT / "tools" / "gates.yaml"


@dataclass
class Result:
    missing: list = field(default_factory=list)
    still_present: list = field(default_factory=list)
    duplicates: list = field(default_factory=list)
    no_json: list = field(default_factory=list)   # ids of rows with no `json` key or an empty one (v0.3 dump.js)
    sole_bad: list = field(default_factory=list)  # the sole_producers: failure lines (check_sole_producers)


# A top-level manifest key: a name at column 0 followed by ':' and then whitespace or the end of the line. Each one starts a
# section; only gates: and removed: hold ids. The lookahead keeps a resource location at column 0 ("ae2:inscriber: [...]",
# a mis-indented sole_producers: entry) from reading as a top-level key `ae2` (Task 8c round 2, R1).
TOP_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?=\s|$)(.*)$")
SECTIONS = ("gates", "removed", "sole_producers")


def load_manifest(path: Path) -> tuple[list[str], list[str]]:
    """(gates, removed): the `- ` rows of those two sections, as two lists of ids. Any other top-level key ends the current
    section, so the `- ` rows of a later section never leak into `removed:`. load_sole_producers checks the file's shape."""
    gates, removed, section = [], [], None
    for line in path.read_text().splitlines():
        s = line.strip()
        if s.startswith("#") or not s:
            continue
        top = TOP_KEY.match(line)
        if top:
            section = {"gates": gates, "removed": removed}.get(top.group(1))
            continue
        if s.startswith("- ") and section is not None:
            section.append(s[2:].strip().strip('"'))
    return gates, removed


RESOURCE = re.compile(r"[a-z0-9_.-]+:[a-z0-9_./-]+")
SOLE_ENTRY = re.compile(r"^  (\S+):\s*(.*)$")
SOLE_KIND = re.compile(r"^\{\s*kind:\s*(item|chemical)\s*,\s*producers:\s*(\[.*\])\s*\}$")
LIST_ROW = re.compile(r"^\s+- (.*)$")


def _flow_list(text: str, where: str) -> list[str]:
    """`[a, b]` -> ['a', 'b']: each element a resource location, optionally quoted, none repeated."""
    if not (text.startswith("[") and text.endswith("]")) or "[" in text[1:-1] or "]" in text[1:-1]:
        raise ValueError(f"{where}: expected a flow list [...], got {text!r}")
    items = [x.strip().strip('"\'') for x in text[1:-1].split(",")] if text[1:-1].strip() else []
    bad = [x for x in items if not RESOURCE.fullmatch(x)]
    if bad:
        raise ValueError(f"{where}: not a resource location: {bad}")
    if len(set(items)) != len(items):
        raise ValueError(f"{where}: a producer is listed twice: {items}")
    return items


def load_sole_producers(path: Path) -> dict[str, tuple[str, list[str]]]:
    """The `sole_producers:` section: {output id: (kind, [recipe id, ...])}, kind 'item' or 'chemical'. Raises ValueError on
    anything it does not read, so a typo fails the check instead of checking nothing: a top-level key other than gates:,
    removed: and sole_producers: (a misspelled heading), a section twice, no sole_producers: section or an empty one, a line
    in gates: or removed: that is not `  - <resource location>`, and any malformed entry (Task 8c round 2, R1)."""
    out, section, pending, seen = {}, None, None, set()
    for n, line in enumerate(path.read_text().splitlines(), 1):
        s = line.strip()
        if s.startswith("#") or not s:
            continue
        top = TOP_KEY.match(line)
        if top and pending is None:
            section = top.group(1)
            if section not in SECTIONS:
                raise ValueError(f"{path.name}:{n}: unknown top-level key {section!r} (expected one of {', '.join(SECTIONS)})")
            if section in seen:
                raise ValueError(f"{path.name}:{n}: {section}: appears twice")
            seen.add(section)
            if top.group(2).split("#", 1)[0].strip():
                raise ValueError(f"{path.name}:{n}: {section}: takes no inline value")
            continue
        if section is None:
            raise ValueError(f"{path.name}:{n}: {line!r} comes before any top-level key")
        if section != "sole_producers":
            m = LIST_ROW.match(line)
            if not m or not RESOURCE.fullmatch(m.group(1).strip().strip('"')):
                raise ValueError(f"{path.name}:{n}: expected '  - <resource location>' under {section}:, got {line!r}")
            continue
        if pending is not None:   # a flow value continued from an earlier line
            key, start, text = pending
            text += " " + s
        else:
            m = SOLE_ENTRY.match(line)
            if not m or not RESOURCE.fullmatch(m.group(1)):
                raise ValueError(f"{path.name}:{n}: expected '  <output id>: [<recipe id>, ...]', got {line!r}")
            key, start, text = m.group(1), n, m.group(2).strip()
        if text.count("[") + text.count("{") > text.count("]") + text.count("}"):
            pending = (key, start, text)
            continue
        pending = None
        where = f"{path.name}:{start} ({key})"
        kind = SOLE_KIND.match(text)
        kind, producers = (kind.group(1), _flow_list(kind.group(2), where)) if kind else ("item", _flow_list(text, where))
        if key in out:
            raise ValueError(f"{where}: listed twice")
        out[key] = (kind, producers)
    if pending is not None:
        raise ValueError(f"{path.name}:{pending[1]} ({pending[0]}): the flow value never closes")
    if "sole_producers" not in seen:
        raise ValueError(f"{path.name}: no sole_producers: section")
    if not out:
        raise ValueError(f"{path.name}: sole_producers: is empty")
    return out


# Which top-level keys of a recipe body hold its products (module docstring, "The producer rule").
PRODUCT_KEY = re.compile(r"result|output|product", re.I)
BOOKKEEPING = re.compile(r"^_kubejs")   # _kubejs_changed_marker (KubeRecipe.serializeChanges; see dump.js)
# Product keys PRODUCT_KEY misses, by recipe type (Task 8c round 2, R2), each read from the mod's recipe class (javap -p/-c):
#   ae2:storage_cell_disassembly: appliedenergistics2-19.2.17.jar appeng/recipes/game/StorageCellDisassemblyRecipe,
#     getDisassemblyResult(Level, Item) -> List<ItemStack>, the cell_disassembly_items list;
#   ae2:crafting_unit_transform: appeng/recipes/game/CraftingUnitTransformRecipe.getUpgradedBlock, the block a crafting unit
#     becomes (upgraded_block);
#   productivebees:block_conversion: productivebees-1.21.1-13.13.5.jar cy/jdkdigital/productivebees/common/recipe/
#     BlockConversionRecipe, bees turn the `from` block state into the `to` one;
#   functionalstorage:custom_compacting: functionalstorage-1.21.1-1.5.8.jar com/buuz135/functionalstorage/util/CompactingUtil
#     reads CustomCompactingRecipe's lower_input and higher_input in both orders (javap -c offsets 520-534 and 666-680), so a
#     compacting drawer turns either into the other: both are products;
#   twilightforest:uncrafting (inverted): twilightforest-1.21.1-4.8.3345-universal.jar twilightforest/item/recipe/
#     UncraftingRecipe extends ShapedRecipe with an `input` Ingredient: the uncrafting table takes the input and gives the
#     pattern's `key` items, so its `key` holds the products;
#   chipped:workbench (inverted; round 3, B1): chipped-neoforge-1.21.1-4.0.2.jar earth/terrarium/chipped/common/recipes/
#     ChippedRecipe (a record of one List<Ingredient> `ingredients`). getResults(ItemStack) is ingredients.stream()
#     .filter(i -> i.test(stack)).map(Ingredient::getItems).flatMap(...) (javap -c, offsets 13-53): every item of the group
#     the input belongs to is an output. It is the jar's only recipe type (ModRecipeSerializers registers "workbench").
TYPE_PRODUCT_KEYS = {
    "ae2:storage_cell_disassembly": {"cell_disassembly_items"},
    "ae2:crafting_unit_transform": {"upgraded_block"},
    "productivebees:block_conversion": {"to"},
    "functionalstorage:custom_compacting": {"higher_input", "lower_input"},
    "twilightforest:uncrafting": {"key"},
    "chipped:workbench": {"ingredients"},
}
# Keys that hold what a recipe consumes or needs (or its type and load conditions): a listed output named here is no
# producer. Every other key that is not a product key is unknown, and a listed output named under one fails as UNKNOWN SHAPE
# (a wrapper's {recipe: {result}}, a `drops` or `yield` list). Surveyed over the 0.3 dump (18880 rows, Task 8c round 2): no
# listed output is named outside the product keys and these.
INGREDIENT_KEYS = frozenset({
    "type", "ingredient", "ingredients", "key", "pattern", "input", "inputs", "base", "addition", "template", "reagent",
    "pedestalItems", "catalyst", "item_input", "chemical_input", "fluid_input", "main_input", "extra_input", "left_input",
    "right_input", "neoforge:conditions", "neoforge:load_conditions", "fabric:load_conditions",
})
# The types whose ingredient keys may name a listed output (round 3, C1). They consume what those keys hold and name their
# products under product keys (every row of each in the 0.3 dump makes something the rule reads). Reviewed by the Task 8c
# coordinator; the 0.3 dump names a listed output under an ingredient key (other than `type`) only in rows of these types
# (ae2:inscriber names one only as its `type`). A listed output named under an ingredient key of any other type fails as
# UNKNOWN SHAPE: an inverted type (chipped:workbench, twilightforest:uncrafting) keeps its products there.
CONSUMING_TYPES = frozenset({
    "minecraft:crafting_shaped", "minecraft:crafting_shapeless", "kubejs:shaped", "minecraft:smithing_transform",
    "mekanism:combining", "mekanism:washing", "mekanism:mek_data", "industrialforegoing:dissolution_chamber",
    "ars_nouveau:enchanting_apparatus", "ad_astra:compressing", "ad_astra:nasa_workbench", "ae2:inscriber",
})
# A product string, read generously: an optional count ('2x ', '2 x ', '3x', '1.5x'), then the first run of resource-location
# characters, so a components suffix ('[...]', '{...}') or trailing text is dropped. Reading more makers is the safe direction:
# a maker read wrongly here could only add a producer (WRONG PRODUCERS), never hide one. A string with no id there (an
# uppercase id, a stand-in such as '<inert>') is kept whole, so a listed output named in it fails as UNKNOWN SHAPE. The tests'
# kjs.products reads custom recipes with this rule too (Task 8c round 2, minor 7: one producer rule).
JSON_ITEM_STRING = re.compile(r"\s*(?:[+-]?[0-9.]+\s*x\s*)?([a-z0-9_:/.-]*)")
# A tag string, read the same way (round 3, X4): an optional count, then '#', then the first run of resource-location
# characters ('2x #c:ingots' is the tag c:ingots).
JSON_TAG_STRING = re.compile(r"\s*(?:[+-]?[0-9.]+\s*x\s*)?#([a-z0-9_:/.-]+)")


def json_item_id(s: str) -> str:
    """The item id a product string names (JSON_ITEM_STRING): 'ae2:drive' for '2x ae2:drive' and for
    'ae2:drive[minecraft:rarity="epic"]', 'minecraft:stick' for 'stick'. A string with no id there is returned unchanged."""
    raw = JSON_ITEM_STRING.match(s).group(1)
    if not raw or raw.startswith("-"):
        return s
    return raw if ":" in raw else "minecraft:" + raw


def key_role(rtype, key: str):
    """'product', 'ingredient', 'other', or None for a KubeJS bookkeeping key."""
    if BOOKKEEPING.match(key):
        return None
    if key in TYPE_PRODUCT_KEYS.get(rtype, ()) or PRODUCT_KEY.search(key):
        return "product"
    return "ingredient" if key in INGREDIENT_KEYS else "other"


def product_values(body: dict) -> list:
    """[(key, value)] for each product a recipe body holds, in order: the value of each product key, or, for a pattern `key`
    map (twilightforest:uncrafting), each of its values."""
    rtype = body.get("type")
    out = []
    for k, v in body.items():
        if key_role(rtype, k) != "product" or v is None:
            continue
        if k == "key" and isinstance(v, dict):
            out.extend((k, x) for x in v.values())
        else:
            out.append((k, v))
    return out


@dataclass
class Made:
    """What a recipe body makes: item and chemical ids (each in first-seen order, once), tag products as (tag, 'item' or
    'chemical'), and the product values of a shape the rule does not read, as (key, value) pairs."""
    items: list = field(default_factory=list)
    chemicals: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    unknown: list = field(default_factory=list)


def _add(seq, x):
    if x not in seq:
        seq.append(x)


def _read_product(v, made: Made, unknown: list):
    if v is None or isinstance(v, (bool, int, float)):
        return
    if isinstance(v, str):
        tag = JSON_TAG_STRING.match(v)
        if tag:
            _add(made.tags, (tag.group(1), "item"))
        else:
            _add(made.items, json_item_id(v))
        return
    if isinstance(v, list):
        for x in v:
            _read_product(x, made, unknown)
        return
    if isinstance(v, dict):
        if "item" in v:
            _read_product(v["item"], made, unknown)
        elif "stack" in v:
            _read_product(v["stack"], made, unknown)
        elif isinstance(v.get("id"), str):
            _add(made.chemicals if "amount" in v and "count" not in v else made.items, v["id"])
        elif isinstance(v.get("fluid"), str):
            _add(made.chemicals, v["fluid"])
        elif isinstance(v.get("tag"), str):
            # {amount, tag} without a count is a fluid or chemical tag, as {amount, id} is a fluid or chemical stack
            _add(made.tags, (v["tag"].lstrip("#"), "chemical" if "amount" in v and "count" not in v else "item"))
        elif isinstance(v.get("items"), (str, list)):
            for x in ([v["items"]] if isinstance(v["items"], str) else v["items"]):
                _read_product(x, made, unknown)
        else:
            unknown.append(v)
        return
    unknown.append(v)


def made_by(body: dict) -> Made:
    """Made for a recipe body, by the producer rule in this module's docstring."""
    made = Made()
    for k, v in product_values(body):
        u = []
        _read_product(v, made, u)
        made.unknown.extend((k, x) for x in u)
    return made


def products(body: dict):
    """(items, chemicals, unknown) a recipe body makes: two sets of ids, and the product values of a shape the rule does not
    read, as (key, value) pairs. Tag products are in made_by(body).tags."""
    made = made_by(body)
    return set(made.items), set(made.chemicals), made.unknown


def _names(item: str) -> re.Pattern:
    """`item` as a whole resource location inside JSON text (not a prefix of a longer id)."""
    return re.compile(r"(?<![a-z0-9_.:/-])" + re.escape(item) + r"(?![a-z0-9_./-])")


def _mentions(ids) -> re.Pattern:
    """One pattern for every id in `ids`, each as a whole resource location (as _names), in any case: findall gives the ids
    named, lowercased by _named. A ResourceLocation is lowercase, so 'AE2:Drive' reads as no item and fails as UNKNOWN SHAPE
    instead of passing as a non-producer."""
    alts = "|".join(re.escape(i) for i in sorted(ids, key=len, reverse=True))
    return re.compile(r"(?<![a-z0-9_.:/-])(" + alts + r")(?![a-z0-9_./-])", re.I)


def _named(pattern: re.Pattern, text: str) -> set:
    return {x.lower() for x in pattern.findall(text)}


def _tag_mentions(tags):
    """(the listed tags as '#t' or "tag": "t" inside JSON text, the same as a bare id): two patterns, each matching the tag id
    as its group, or None for no tags."""
    if not tags:
        return None, None
    alts = "|".join(re.escape(t) for t in sorted(tags, key=len, reverse=True))
    return (re.compile(r'(?:#|"tag":\s*"#?)(' + alts + r")(?![a-z0-9_./-])", re.I),
            re.compile(r"(?<![a-z0-9_.:/-])#?(" + alts + r")(?![a-z0-9_./-])", re.I))


def check_sole_producers(dump: list[dict], sole: dict, members: dict | None = None) -> list[str]:
    """One line per failure (module docstring): UNREFERENCED, NO TAG MEMBERS, UNEXPANDED TAG, UNKNOWN SHAPE, then WRONG
    PRODUCERS. `members` is the minecraft:item part of the item-tag members export ({tag: [item id, ...]}), or None when there
    is none, which fails every tag product. Rows without a `json` body are skipped (run_checks fails them as NO JSON)."""
    if not sole:
        return []
    makers = {o: set() for o in sole}
    item_outputs = {o for o, (kind, _) in sole.items() if kind == "item"}
    chemical_outputs = set(sole) - item_outputs
    mention = _mentions(sole)
    # round 3, C2: the item tags whose members include a listed item output
    listed_tags = {t: sorted(set(ms) & item_outputs) for t, ms in (members or {}).items() if set(ms) & item_outputs}
    tag_mention, bare_tag = _tag_mentions(listed_tags)
    named, ids, shape_bad, tag_bad = set(), set(), [], []
    for r in dump:
        ids.add(r["id"])
        raw = r.get("json")
        if not raw:
            continue
        body = json.loads(raw)
        if not isinstance(body, dict):
            continue
        made = made_by(body)
        got = {"item": set(made.items) & item_outputs, "chemical": set(made.chemicals) & chemical_outputs}
        for tag, kind in made.tags:
            if kind == "chemical":
                if chemical_outputs:
                    tag_bad.append(f"UNEXPANDED TAG {r['id']} makes chemical tag #{tag}; no export lists chemical or fluid "
                                   f"tag members")
            elif members is None:
                tag_bad.append(f"NO TAG MEMBERS {r['id']} makes #{tag}, and there is no item-tag members export to expand "
                               f"it (tagcheck.js writes kubejs/exported/item_tag_members.json)")
            else:
                got["item"] |= set(members.get(tag, ())) & item_outputs
        for o in got["item"] | got["chemical"]:
            makers[o].add(r["id"])
        here = _named(mention, raw)
        named |= here
        # the unread product values, per key: the only place a listed tag is looked for bare (an id may also be a tag's id)
        unread = {k: json.dumps([u for kk, u in made.unknown if kk == k]) for k, _ in made.unknown}
        tags_here = (_named(tag_mention, raw) | _named(bare_tag, " ".join(unread.values()))) if tag_mention else set()
        if not here and not tags_here:
            continue
        rtype = body.get("type")
        read_tags = {t for t, kind in made.tags if kind == "item"}
        for k, v in body.items():
            role = key_role(rtype, k)
            if role is None or (role == "ingredient" and (k == "type" or rtype in CONSUMING_TYPES)):
                continue
            text = json.dumps(v, sort_keys=True)
            for o in sorted(_named(mention, text)):
                kind = sole[o][0]
                if role == "ingredient":
                    shape_bad.append(f"UNKNOWN SHAPE {o} ({kind}) in {r['id']}, key {k} (an ingredient key of a type not in "
                                     f"CONSUMING_TYPES): {text}")
                elif role == "other" or o not in got[kind]:
                    shape_bad.append(f"UNKNOWN SHAPE {o} ({kind}) in {r['id']}, key {k}: {text}")
            if role == "ingredient" or not tags_here:
                continue   # an ingredient key may consume a listed tag
            tags = _named(tag_mention, text) | (_named(bare_tag, unread[k]) if k in unread else set())
            for t in sorted(tags):
                if role == "other" or t not in read_tags:
                    shape_bad.append(f"UNKNOWN SHAPE #{t} (holds {', '.join(listed_tags[t])}) in {r['id']}, key {k}: {text}")
    bad = []
    for o, (kind, want) in sole.items():
        if o not in named and o not in ids:
            bad.append(f"UNREFERENCED {o}: no recipe in the dump names it")
        bad += [f"UNREFERENCED {p} (a producer of {o}): no such recipe id in the dump" for p in want if p not in ids]
    bad += tag_bad + shape_bad
    for o, (kind, want) in sole.items():
        if sorted(makers[o]) != sorted(want):
            bad.append(f"WRONG PRODUCERS {o}: expected {sorted(want)}, got {sorted(makers[o])}")
    return bad


def load_item_members(path: Path):
    """The minecraft:item part of the item-tag members export, or None when the file does not exist. Raises ValueError on a
    file of another shape."""
    if not path.exists():
        return None
    doc = json.loads(path.read_text())
    items = doc.get(ITEM_REGISTRY) if isinstance(doc, dict) else None
    if not isinstance(items, dict) or not all(isinstance(v, list) and all(isinstance(x, str) for x in v) for v in items.values()):
        raise ValueError(f"{path.name} is not {{{ITEM_REGISTRY!r}: {{tag: [item id, ...]}}}}")
    return items


def run_checks(dump: list[dict], gates: list[str], removed: list[str], sole: dict | None = None,
               members: dict | None = None) -> Result:
    ids = {r["id"] for r in dump}
    res = Result()
    res.missing = [g for g in gates if g not in ids]
    res.still_present = [r for r in removed if r in ids]
    counts = Counter((r["type"], r["output"]) for r in dump if r["output"] and not r["type"].startswith("minecraft:crafting"))
    res.duplicates = sorted(k for k, n in counts.items() if n > 1)
    res.no_json = [r["id"] for r in dump if not r.get("json")]
    res.sole_bad = check_sole_producers(dump, sole or {}, members)
    return res


def main() -> int:
    dump = json.loads(DUMP.read_text())
    gates, removed = load_manifest(MANIFEST)
    problem = None
    try:
        sole = load_sole_producers(MANIFEST)
    except ValueError as e:
        sole, problem = {}, f"BAD MANIFEST {e}"
    try:
        members = load_item_members(ITEM_MEMBERS)
    except ValueError as e:
        members, problem = None, problem or f"BAD TAG MEMBERS {e}"
    # round 3, H1: the members export must be this boot's too (tagcheck.js writes it at ServerEvents.loaded, after dump.js
    # wrote the dump); tools/check_tags.py checks it against tags.json
    if members is not None and ITEM_MEMBERS.stat().st_mtime < DUMP.stat().st_mtime:
        problem = problem or f"STALE TAG MEMBERS {ITEM_MEMBERS} is older than {DUMP} (boot again)"
    r = run_checks(dump, gates, removed, {} if problem else sole, members)
    print(f"gates: {len(gates)} expected, {len(r.missing)} missing, {len(r.still_present)} removed-still-present")
    for m in r.missing:
        print("  MISSING", m)
    for p in r.still_present:
        print("  STILL PRESENT", p)
    if r.no_json:
        print(f"  NO JSON {len(r.no_json)} rows have no recipe body (dump.js `json` column): {', '.join(r.no_json[:10])}")
    if problem:
        print(f"sole producers: {problem}")
    else:
        print(f"sole producers: {len(sole)} outputs, {len(r.sole_bad)} bad")
    for line in r.sole_bad:
        print("  " + line)
    print(f"non-crafting duplicate outputs: {len(r.duplicates)} (informational; crafting-grid conflicts are Polymorph's job)")
    for d in r.duplicates[:50]:
        print("  dup", d)
    return 1 if (r.missing or r.still_present or r.no_json or r.sole_bad or problem) else 0


if __name__ == "__main__":
    sys.exit(main())
