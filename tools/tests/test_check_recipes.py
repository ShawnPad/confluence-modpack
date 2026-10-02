import json

import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_recipes import run_checks

DUMP = [
    {"id": "confluence:tier1/flint_and_steel", "type": "minecraft:crafting_shaped", "output": "minecraft:flint_and_steel"},
    {"id": "minecraft:stone", "type": "minecraft:smelting", "output": "minecraft:stone"},
    {"id": "modx:stone_dup", "type": "minecraft:smelting", "output": "minecraft:stone"},
]

def test_all_good():
    r = run_checks(DUMP, gates=["confluence:tier1/flint_and_steel"], removed=["minecraft:flint_and_steel"])
    assert r.missing == [] and r.still_present == []

def test_missing_and_present():
    r = run_checks(DUMP, gates=["confluence:tier1/nope"], removed=["minecraft:stone"])
    assert r.missing == ["confluence:tier1/nope"]
    assert r.still_present == ["minecraft:stone"]

def test_duplicates_listed():
    r = run_checks(DUMP, gates=[], removed=[])
    assert ("minecraft:smelting", "minecraft:stone") in r.duplicates

def test_rows_without_a_json_body_fail_and_are_named(tmp_path, monkeypatch, capsys):
    """v0.3: dump.js gives every row its recipe JSON (the column later tasks read). A missing or empty `json` means the
    dump broke silently -- a Rhino `const` inside `try` once emptied all 18880 rows while this check stayed green -- so
    exit 1, naming the count and up to 10 ids. A clean export prints nothing new."""
    import check_recipes
    manifest = tmp_path / "gates.yaml"
    manifest.write_text("gates:\n  - confluence:tier1/flint_and_steel\nremoved:\n  - minecraft:flint_and_steel\n"
                        "sole_producers:\n  minecraft:flint_and_steel: [confluence:tier1/flint_and_steel]\n")
    dump = tmp_path / "recipes.json"
    monkeypatch.setattr(check_recipes, "DUMP", dump)
    monkeypatch.setattr(check_recipes, "MANIFEST", manifest)
    monkeypatch.setattr(check_recipes, "ITEM_MEMBERS", tmp_path / "no_item_tag_members.json")
    rows = [dict(r, json=json.dumps({"type": r["type"], "result": r["output"]})) for r in DUMP]
    dump.write_text(json.dumps(rows))
    assert check_recipes.main() == 0
    clean = capsys.readouterr().out.splitlines()
    assert clean[0] == "gates: 1 expected, 0 missing, 0 removed-still-present"
    assert not any("json" in line.lower() for line in clean)
    rows[0]["json"] = ""
    del rows[2]["json"]
    rows += [{"id": f"modx:r{i:02}", "type": "minecraft:smelting", "output": "", "json": ""} for i in range(11)]
    dump.write_text(json.dumps(rows))
    assert check_recipes.main() == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "gates: 1 expected, 0 missing, 0 removed-still-present"
    bad = [line for line in out if "NO JSON" in line]
    assert len(bad) == 1 and "13 rows" in bad[0]
    assert "confluence:tier1/flint_and_steel" in bad[0] and "modx:stone_dup" in bad[0]
    assert sum(bad[0].count(f"modx:r{i:02}") for i in range(11)) == 8   # 10 named: the 2 above + the first 8 of 11


# ---- v0.3 Task 8c: `sole_producers:` (the dump-body producer check) and the manifest's section rule ----

from check_recipes import check_sole_producers, load_manifest, load_sole_producers, products  # noqa: E402


def row(rid, body, rtype=None):
    """A dump row as dump.js writes it: the `output` column is often empty, so only `json` names the product."""
    return {"id": rid, "type": rtype or body.get("type", "minecraft:crafting_shaped"), "output": "", "json": json.dumps(body)}


SHAPED_KEY = {"pattern": ["A"], "key": {"A": {"item": "minecraft:stone"}}}
GOOD = [
    row("confluence:tier5/ultimate_control_circuit", {"type": "kubejs:shaped", **SHAPED_KEY,
        "result": {"id": "mekanism:ultimate_control_circuit", "count": 4}, "_kubejs_changed_marker": {"line": 6}}),
    row("allthemodium:processing/unobtainium/crystal/from_slurry", {"type": "mekanism:crystallizing",
        "input": {"amount": 200, "chemical": "allthemodium:clean_unobtainium"}, "output": {"count": 1, "id": "allthemodium:unobtainium_crystal"}}),
    row("confluence:bypass/unobtainium_crystal_from_ore", {"type": "mekanism:combining", "main_input": {"count": 1, "tag": "c:ores/unobtainium"},
        "extra_input": {"count": 1, "item": "ad_astra:etrium_ingot"}, "output": {"count": 5, "id": "allthemodium:unobtainium_crystal"}}),
    # A consumer, not a producer: the slurry is this washing recipe's chemical input.
    row("allthemodium:processing/unobtainium/slurry/clean", {"type": "mekanism:washing", "fluid_input": {"amount": 5, "tag": "minecraft:water"},
        "chemical_input": {"amount": 1, "chemical": "allthemodium:dirty_unobtainium"}, "output": {"amount": 1, "id": "allthemodium:clean_unobtainium"}}),
    row("modx:unrelated", {"type": "modx:odd", "result": {"weird": ["shape"]}}),
]
SOLE = {
    "mekanism:ultimate_control_circuit": ("item", ["confluence:tier5/ultimate_control_circuit"]),
    "allthemodium:unobtainium_crystal": ("item", ["allthemodium:processing/unobtainium/crystal/from_slurry",
                                                  "confluence:bypass/unobtainium_crystal_from_ore"]),
    "allthemodium:dirty_unobtainium": ("chemical", []),
}


def test_sole_producers_pass():
    assert check_sole_producers(GOOD, SOLE) == []


def test_sole_producers_extra_producer_fails():
    extra = row("modx:cheap_circuit", {"type": "mekanism:enriching", "input": {"count": 1, "tag": "c:dusts/redstone"},
                                       "output": {"count": 1, "id": "mekanism:ultimate_control_circuit"}})
    assert check_sole_producers(GOOD + [extra], SOLE) == [
        "WRONG PRODUCERS mekanism:ultimate_control_circuit: expected ['confluence:tier5/ultimate_control_circuit'], "
        "got ['confluence:tier5/ultimate_control_circuit', 'modx:cheap_circuit']"]


def test_sole_producers_missing_producer_fails():
    """With the row gone from the dump, the listed producer is also UNREFERENCED (round 2, minor 9)."""
    assert check_sole_producers([r for r in GOOD if r["id"] != "confluence:bypass/unobtainium_crystal_from_ore"], SOLE) == [
        "UNREFERENCED confluence:bypass/unobtainium_crystal_from_ore (a producer of allthemodium:unobtainium_crystal): no such "
        "recipe id in the dump",
        "WRONG PRODUCERS allthemodium:unobtainium_crystal: expected ['allthemodium:processing/unobtainium/crystal/from_slurry', "
        "'confluence:bypass/unobtainium_crystal_from_ore'], got ['allthemodium:processing/unobtainium/crystal/from_slurry']"]


def test_sole_producers_empty_list_violated_by_a_chemical_producer():
    """A `kind: chemical` entry reads the chemical fields: {amount, id} under output, chemical_output and the like."""
    dissolve = row("allthemodium:processing/unobtainium/slurry/dirty/from_ore", {"type": "mekanism:dissolution",
        "chemical_input": {"amount": 1, "tag": "mekanism:sulfuric_acid"}, "item_input": {"count": 1, "tag": "c:ores/unobtainium"},
        "output": {"amount": 1000, "id": "allthemodium:dirty_unobtainium"}})
    assert check_sole_producers(GOOD + [dissolve], SOLE) == [
        "WRONG PRODUCERS allthemodium:dirty_unobtainium: expected [], "
        "got ['allthemodium:processing/unobtainium/slurry/dirty/from_ore']"]
    rotary = row("modx:rotary", {"type": "mekanism:rotary", "chemical_output": {"amount": 1, "id": "allthemodium:dirty_unobtainium"}})
    assert check_sole_producers(GOOD + [rotary], SOLE) == [
        "WRONG PRODUCERS allthemodium:dirty_unobtainium: expected [], got ['modx:rotary']"]


def test_sole_producers_item_and_chemical_kinds_do_not_mix():
    """A chemical-shaped stack ({amount, id}) never counts as an item producer, nor an item stack as a chemical producer: a
    listed id that a body names in the other kind is a shape the rule does not know, so it fails."""
    as_item = row("modx:dirty_item", {"type": "modx:m", "output": {"count": 1, "id": "allthemodium:dirty_unobtainium"}})
    bad = check_sole_producers(GOOD + [as_item], SOLE)
    assert bad == ["UNKNOWN SHAPE allthemodium:dirty_unobtainium (chemical) in modx:dirty_item, key output: "
                   '{"count": 1, "id": "allthemodium:dirty_unobtainium"}']


@pytest.mark.parametrize("value", [
    {"weird": "mekanism:ultimate_control_circuit"},
    [{"stacks": [{"id": "mekanism:ultimate_control_circuit"}]}],
    {"block": {"id": "mekanism:ultimate_control_circuit"}},
])
def test_sole_producers_unknown_shape_for_a_listed_output_fails(value):
    odd = row("modx:odd_maker", {"type": "modx:machine", "result": value})
    bad = check_sole_producers(GOOD + [odd], SOLE)
    assert len(bad) == 1 and bad[0].startswith(
        "UNKNOWN SHAPE mekanism:ultimate_control_circuit (item) in modx:odd_maker, key result: "), bad


def test_products_reads_every_known_shape():
    """The shapes surveyed in the 0.3 dump (18880 rows): a string (with a count prefix), {id}, {count, id}, {item} as a string
    or a nested stack, {stack}, list elements of results/outputs, Mekanism's main/secondary/item outputs, a custom ingredient's
    `items`, and the chemical/fluid stacks {amount, id}, {fluid} and {amount, fluid}."""
    body = {
        "type": "modx:all", "result": "2x modx:a", "output": {"count": 1, "id": "modx:b"},
        "results": [{"item": {"count": 1, "id": "modx:c"}}, {"chance": 0.5, "item": {"item": "modx:d"}}, "modx:e",
                    {"amount": 2, "item": {"id": "modx:f"}}, {"item": {"type": "neoforge:components", "items": "modx:g"}},
                    {"chance": 0.1, "item": {"tag": "c:dusts/x"}}],
        "outputs": [{"chance": 1, "maxRange": 2, "stack": {"count": 1, "id": "modx:h"}}, {"item": "modx:i"}],
        "main_output": {"count": 1, "id": "modx:j"}, "secondary_output": {"count": 1, "id": "modx:k"},
        "item_output": {"count": 1, "id": "modx:l"}, "output_item": {"id": "modx:m"}, "byproduct": {"id": "modx:n"},
        "chemical_output": {"amount": 1, "id": "modx:chem_a"}, "fluid_output": {"amount": 1, "id": "modx:fluid_a"},
        "outputFluid": {"amount": 1, "fluid": "modx:fluid_b"}, "resultCount": 2,
        "_kubejs_changed_marker": {"source": "x", "line": 1},
    }
    items, chemicals, unknown = products(body)
    assert items == {"modx:" + c for c in "abcdefghijklmn"}
    assert chemicals == {"modx:chem_a", "modx:fluid_a", "modx:fluid_b"}
    assert unknown == []


MANIFEST_TEXT = """\
gates:
  - confluence:tier1/a
removed:
  # a comment
  - minecraft:b
sole_producers:
  # v0.3 heading: nodes (file); D1
  mekanism:ultimate_control_circuit: [confluence:tier5/ultimate_control_circuit]
  allthemodium:unobtainium_crystal: [allthemodium:processing/unobtainium/crystal/from_slurry,
    confluence:bypass/unobtainium_crystal_from_ore]
  allthemodium:dirty_unobtainium: {kind: chemical, producers: []}
  kubejs:other_key: []
"""


def test_any_other_top_level_key_ends_a_section(tmp_path):
    """load_manifest keeps its signature, (gates, removed) as two lists of ids (plan Tasks 10 and 13 call
    `gates, _ = load_manifest(MANIFEST)`), and a top-level key after `removed:`, with or without `- ` lines under it, never
    leaks into it."""
    m = tmp_path / "gates.yaml"
    m.write_text(MANIFEST_TEXT + "later_section:\n  - not:a_removal\n")
    assert load_manifest(m) == (["confluence:tier1/a"], ["minecraft:b"])


def test_load_sole_producers(tmp_path):
    m = tmp_path / "gates.yaml"
    m.write_text(MANIFEST_TEXT)
    assert load_sole_producers(m) == {
        "mekanism:ultimate_control_circuit": ("item", ["confluence:tier5/ultimate_control_circuit"]),
        "allthemodium:unobtainium_crystal": ("item", ["allthemodium:processing/unobtainium/crystal/from_slurry",
                                                      "confluence:bypass/unobtainium_crystal_from_ore"]),
        "allthemodium:dirty_unobtainium": ("chemical", []),
        "kubejs:other_key": ("item", []),
    }


@pytest.mark.parametrize("bad", [
    "  modx:a: confluence:x\n",                                   # not a flow list
    "  modx:a: [confluence:x\n",                                  # never closed
    "  modx:a: {kind: liquid, producers: []}\n",                  # unknown kind
    "  modx:a: [a]\n  modx:a: [b]\n",                             # duplicate output
    "  modx:a: [not an id]\n",                                    # not a resource location
    "  - modx:a\n",                                               # a list item where an entry belongs
    "  modx:a: [confluence:x, confluence:x]\n",                   # duplicate producer
])
def test_load_sole_producers_rejects_malformed_entries(tmp_path, bad):
    m = tmp_path / "gates.yaml"
    m.write_text("gates:\n  - a:b\nsole_producers:\n" + bad)
    with pytest.raises(ValueError):
        load_sole_producers(m)


def test_main_prints_the_sole_producers_line_and_folds_failures_into_the_exit_code(tmp_path, monkeypatch, capsys):
    import check_recipes
    manifest = tmp_path / "gates.yaml"
    manifest.write_text("gates:\n  - confluence:tier5/ultimate_control_circuit\nremoved:\n  - minecraft:b\nsole_producers:\n"
                        "  mekanism:ultimate_control_circuit: [confluence:tier5/ultimate_control_circuit]\n"
                        "  allthemodium:dirty_unobtainium: {kind: chemical, producers: []}\n")
    dump = tmp_path / "recipes.json"
    monkeypatch.setattr(check_recipes, "DUMP", dump)
    monkeypatch.setattr(check_recipes, "MANIFEST", manifest)
    monkeypatch.setattr(check_recipes, "ITEM_MEMBERS", tmp_path / "no_item_tag_members.json")
    dump.write_text(json.dumps(GOOD))
    assert check_recipes.main() == 0
    out = capsys.readouterr().out.splitlines()
    assert out[:2] == ["gates: 1 expected, 0 missing, 0 removed-still-present", "sole producers: 2 outputs, 0 bad"]
    extra = row("modx:cheap_circuit", {"type": "modx:m", "output": "mekanism:ultimate_control_circuit"})
    dump.write_text(json.dumps(GOOD + [extra]))
    assert check_recipes.main() == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "gates: 1 expected, 0 missing, 0 removed-still-present"
    assert out[1] == "sole producers: 2 outputs, 1 bad"
    assert out[2] == ("  WRONG PRODUCERS mekanism:ultimate_control_circuit: expected ['confluence:tier5/ultimate_control_circuit'], "
                      "got ['confluence:tier5/ultimate_control_circuit', 'modx:cheap_circuit']")


# ---- v0.3 Task 8c round 2: the manifest fails closed (R1, minor 6), every product key is read or refused (R2), tag products
# are expanded (R3), and an entry the dump never names is reported (minor 9) ----

import check_recipes  # noqa: E402

GATES_YAML = Path(__file__).resolve().parents[1] / "gates.yaml"


def manifest(tmp_path, text):
    m = tmp_path / "gates.yaml"
    m.write_text(text)
    return m


@pytest.mark.parametrize("text, msg", [
    # a column-0 entry used to end the section: every later entry was dropped and the run exited 0 (R1)
    ("gates:\n  - a:b\nsole_producers:\n  x:one: [r:a]\nae2:drive: [r:b]\n  x:three: [r:c]\n", "ae2:drive"),
    # a misspelled heading used to read 0 outputs and exit 0
    ("gates:\n  - a:b\nsole_producer:\n  x:one: [r:a]\n", "sole_producer"),
    ("gates:\n  - a:b\nremoved:\n  - c:d\n", "no sole_producers: section"),
    ("gates:\n  - a:b\nsole_producers:\n  # only a comment\n", "sole_producers: is empty"),
    ("sole_producers:\n  x:one: [r:a]\nsole_producers:\n  x:two: [r:b]\n", "twice"),
    # a stray line in gates: or removed: (a column-0 id is not a top-level key any more)
    ("gates:\n  - a:b\nae2:drive: [r:b]\nsole_producers:\n  x:one: [r:a]\n", "ae2:drive"),
    ("gates:\n  - not an id\nsole_producers:\n  x:one: [r:a]\n", "not an id"),
])
def test_load_sole_producers_fails_closed_on_the_manifest_shape(tmp_path, text, msg):
    with pytest.raises(ValueError, match=msg):
        load_sole_producers(manifest(tmp_path, text))


def test_a_resource_location_at_column_0_is_not_a_top_level_key():
    assert check_recipes.TOP_KEY.match("sole_producers:")
    assert check_recipes.TOP_KEY.match("gates:  # comment")
    assert not check_recipes.TOP_KEY.match("ae2:inscriber: [confluence:tier5/inscriber]")


# The brief's "At least" list (task-08c.md, Part 1): every output it names, with the producer sets it fixes.
AT_LEAST = {
    "mekanism:ultimate_control_circuit": ["confluence:tier5/ultimate_control_circuit"],
    "mekanism:digital_miner": None, "kubejs:other_key": None, "industrialforegoing:machine_frame_supreme": None,
    "allthemodium:unobtainium_allthemodium_alloy_ingot": None, "allthemodium:vibranium_allthemodium_alloy_ingot": None,
    "allthemodium:unobtainium_vibranium_alloy_ingot": None,
    "ad_astra:nasa_workbench": None, "ad_astra:space_suit": None, "ad_astra:oxygen_loader": None, "ad_astra:fuel_refinery": None,
    "ad_astra:steel_engine": None, "ad_astra:etrium_ingot": None, "ad_astra:etrium_plate": None, "kubejs:astral_focus": None,
    **{f"ad_astra:tier_{n}_rocket": [f"ad_astra:nasa_workbench/tier_{n}_rocket_from_nasa_workbench"] for n in (1, 2, 3, 4)},
    "ad_astra:launch_pad": ["ad_astra:launch_pad"], "ad_astra:desh_engine": ["ad_astra:desh_engine"],
    "ad_astra:ostrum_engine": ["ad_astra:ostrum_engine"], "ad_astra:calorite_engine": ["ad_astra:calorite_engine"],
    **{f"ae2:{x}": None for x in ("inscriber", "charger", "controller", "drive", "import_bus", "export_bus", "terminal",
                                  "wireless_receiver", "crafting_unit")},
    "ae2:pattern_provider": ["ae2:network/blocks/pattern_providers_interface_alt", "confluence:tier6/pattern_provider"],
    "ae2:cable_pattern_provider": ["ae2:network/blocks/pattern_providers_interface_part"],
    **{f"allthemodium:{m}_crystal": [f"allthemodium:processing/{m}/crystal/from_slurry"] + [
        f"confluence:bypass/{m}_crystal_from_{x}" for x in ("ore", "raw_ore", "raw_block")]
       for m in ("allthemodium", "vibranium", "unobtainium")},
    **{f"allthemodium:dirty_{m}": [] for m in ("allthemodium", "vibranium", "unobtainium")},
    **{f"allthemodium:{m}_ingot": None for m in ("allthemodium", "vibranium", "unobtainium")},
}


def test_the_real_manifest_reads_49_entries_including_the_brief_list():
    sole = load_sole_producers(GATES_YAML)
    assert len(sole) == 49
    assert sorted(set(AT_LEAST) - set(sole)) == []
    assert {o: sorted(sole[o][1]) for o, want in AT_LEAST.items() if want is not None and sorted(sole[o][1]) != sorted(want)} == {}
    assert sorted(o for o, (kind, _) in sole.items() if kind == "chemical") == [
        f"allthemodium:dirty_{m}" for m in ("allthemodium", "unobtainium", "vibranium")]
    smelting = [p for o in sole if o.endswith("_ingot") and not o.endswith("alloy_ingot") and o.startswith("allthemodium:")
                for p in sole[o][1] if "smelting" in p]
    assert sorted(smelting) == [f"allthemodium:{m}_ingot_from_dust_smelting" for m in ("allthemodium", "unobtainium", "vibranium")]


def test_main_reports_a_bad_manifest_after_the_gates_line(tmp_path, monkeypatch, capsys):
    """Minor 6: a manifest ValueError no longer crashes main(); the gates line still comes first."""
    m = manifest(tmp_path, "gates:\n  - confluence:tier5/ultimate_control_circuit\nsole_producer:\n  x:one: [r:a]\n")
    dump = tmp_path / "recipes.json"
    dump.write_text(json.dumps(GOOD))
    monkeypatch.setattr(check_recipes, "DUMP", dump)
    monkeypatch.setattr(check_recipes, "MANIFEST", m)
    monkeypatch.setattr(check_recipes, "ITEM_MEMBERS", tmp_path / "none.json")
    assert check_recipes.main() == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "gates: 1 expected, 0 missing, 0 removed-still-present"
    assert out[1].startswith("sole producers: BAD MANIFEST ") and "sole_producer" in out[1]


DRIVE = {"ae2:drive": ("item", ["confluence:tier5/drive"])}
DRIVE_ROW = row("confluence:tier5/drive", {"type": "kubejs:shaped", **SHAPED_KEY, "result": {"id": "ae2:drive", "count": 1}})
EXTRA = "WRONG PRODUCERS ae2:drive: expected ['confluence:tier5/drive'], got ['confluence:tier5/drive', 'evil:row']"


def evil(body, members=None, sole=DRIVE):
    return check_sole_producers([DRIVE_ROW, row("evil:row", body)], sole, members)


# R2: products under keys PRODUCT_KEY misses (each read from its recipe class; check_recipes.TYPE_PRODUCT_KEYS cites them)
@pytest.mark.parametrize("body", [
    {"type": "ae2:storage_cell_disassembly", "cell": "x:y", "cell_disassembly_items": [{"count": 1, "id": "ae2:drive"}]},
    {"type": "ae2:crafting_unit_transform", "upgrade_item": "x:y", "upgraded_block": "ae2:drive"},
    {"type": "functionalstorage:custom_compacting", "higher_input": {"count": 1, "id": "ae2:drive"},
     "lower_input": {"count": 9, "id": "x:y"}},
    {"type": "functionalstorage:custom_compacting", "higher_input": {"count": 1, "id": "x:y"},
     "lower_input": {"count": 9, "id": "ae2:drive"}},
    # twilightforest:uncrafting is inverted: `input` is uncrafted into the pattern's `key` items
    {"type": "twilightforest:uncrafting", "cost": 1, "input": {"item": "x:y"}, "key": {"A": {"item": "ae2:drive"}}, "pattern": ["A"]},
], ids=["cell_disassembly_items", "upgraded_block", "higher_input", "lower_input", "uncrafting key"])
def test_a_type_specific_product_key_makes_a_producer(body):
    assert evil(body) == [EXTRA]


def test_block_conversion_to_is_a_product_key():
    """productivebees:block_conversion's `to` is a block state ({Name}), a shape the rule does not read: naming a listed
    output there fails."""
    bad = evil({"type": "productivebees:block_conversion", "from": {"Name": "x:y"}, "to": {"Name": "ae2:drive"}})
    assert bad == ['UNKNOWN SHAPE ae2:drive (item) in evil:row, key to: {"Name": "ae2:drive"}']


@pytest.mark.parametrize("key, value", [
    ("recipe", {"type": "minecraft:crafting_shaped", "result": {"id": "ae2:drive"}}),   # a wrapper around a recipe
    ("drops", [{"count": 1, "id": "ae2:drive"}]),
    ("yield", "ae2:drive"),
])
def test_a_listed_output_under_any_other_key_is_an_unknown_shape(key, value):
    bad = evil({"type": "modx:wrapper", key: value})
    assert bad == [f"UNKNOWN SHAPE ae2:drive (item) in evil:row, key {key}: {json.dumps(value, sort_keys=True)}"]


@pytest.mark.parametrize("body", [
    {"type": "minecraft:crafting_shaped", "pattern": ["A"], "key": {"A": {"item": "ae2:drive"}}, "result": {"id": "x:y"}},
    {"type": "mekanism:combining", "main_input": {"item": "ae2:drive"}, "extra_input": {"item": "ae2:drive"}, "output": {"id": "x:y"}},
    {"type": "ars_nouveau:enchanting_apparatus", "reagent": [{"item": "ae2:drive"}], "pedestalItems": [{"item": "ae2:drive"}],
     "result": {"id": "x:y"}},
    {"type": "industrialforegoing:dissolution_chamber", "neoforge:conditions": [{"type": "neoforge:item_exists", "item": "ae2:drive"}],
     "result": {"id": "x:y"}},
    {"type": "ae2:drive", "result": {"id": "x:y"}},   # `type` is never a product, whatever it names
])
def test_a_listed_output_as_an_ingredient_is_fine(body):
    assert evil(body) == []


# R3: tag products, expanded through the item-tag members export (tagcheck.js, kubejs/exported/item_tag_members.json)
MEMBERS = {"c:drives": ["ae2:drive", "x:other"], "c:empty": [], "c:others": ["x:other"]}


@pytest.mark.parametrize("body", [
    {"type": "cucumber:shaped_tag", **SHAPED_KEY, "result": {"tag": "c:drives", "count": 1}},
    {"type": "modx:m", "result": "#c:drives"},
    {"type": "productivebees:centrifuge", "outputs": [{"item": {"tag": "c:drives"}, "chance": 1}]},
], ids=["{tag}", "'#tag'", "nested {item: {tag}}"])
def test_a_tag_product_holding_a_listed_output_makes_a_producer(body):
    assert evil(body, MEMBERS) == [EXTRA]


@pytest.mark.parametrize("tag", ["c:others", "c:empty", "c:unbound"])
def test_a_tag_product_without_a_listed_output_makes_none(tag):
    """An unbound tag holds nothing: tools/check_tags.py requires the members export to hold every bound item tag."""
    assert evil({"type": "modx:m", "result": {"tag": tag}}, MEMBERS) == []


def test_a_tag_product_with_no_members_export_fails():
    bad = evil({"type": "modx:m", "result": {"tag": "c:others"}}, None)
    assert bad == ["NO TAG MEMBERS evil:row makes #c:others, and there is no item-tag members export to expand it "
                   "(tagcheck.js writes kubejs/exported/item_tag_members.json)"]


def test_a_chemical_tag_product_fails_while_a_chemical_entry_is_listed():
    sole = dict(DRIVE, **{"allthemodium:dirty_unobtainium": ("chemical", [])})
    rows = [DRIVE_ROW, row("x:wash", {"type": "mekanism:washing", "chemical_input": {"amount": 1, "chemical": "allthemodium:dirty_unobtainium"}}),
            row("evil:row", {"type": "modx:m", "output": {"amount": 100, "tag": "c:slurries"}})]
    assert check_sole_producers(rows, sole, MEMBERS) == [
        "UNEXPANDED TAG evil:row makes chemical tag #c:slurries; no export lists chemical or fluid tag members"]
    assert check_sole_producers(rows, DRIVE, MEMBERS) == []


# Minor 9: an entry the dump never names (a typo in a `[]` key passes forever otherwise)
def test_an_unreferenced_entry_or_producer_is_reported():
    sole = dict(DRIVE, **{"ae2:drvie": ("item", []), "ae2:charger": ("item", ["confluence:tier5/charger"])})
    bad = check_sole_producers([DRIVE_ROW, row("x:uses", {"type": "minecraft:crafting_shapeless", "ingredients": [{"item": "ae2:charger"}]})], sole, {})
    assert bad == ["UNREFERENCED ae2:drvie: no recipe in the dump names it",
                   "UNREFERENCED confluence:tier5/charger (a producer of ae2:charger): no such recipe id in the dump",
                   "WRONG PRODUCERS ae2:charger: expected ['confluence:tier5/charger'], got []"]


def test_a_listed_output_spelled_in_another_case_is_an_unknown_shape():
    """A ResourceLocation is lowercase, so 'AE2:drive' is no item; a body naming one is a broken shape, not a non-producer."""
    assert evil({"type": "modx:m", "result": {"count": 1, "id": "AE2:Drive"}}) == [
        'UNKNOWN SHAPE ae2:drive (item) in evil:row, key result: {"count": 1, "id": "AE2:Drive"}']


# ---- Task 8c round 3: chipped's products under `ingredients` (B1), inverted types (C1), tag mentions (C2), stale members (H1) ----

# B1: chipped:workbench is the only recipe type chipped-neoforge-1.21.1-4.0.2.jar registers (ModRecipeSerializers registers
# "workbench"), and ChippedRecipe.getResults gives every item of the ingredient group the input matches: `ingredients` holds
# its products.
@pytest.mark.parametrize("ingredients", [[{"item": "x:y"}, {"item": "ae2:drive"}], [{"tag": "c:others"}, {"tag": "c:drives"}]],
                         ids=["B1a id", "B1b tag"])
def test_a_chipped_workbench_group_holding_a_listed_output_makes_it(ingredients):
    assert evil({"type": "chipped:workbench", "ingredients": ingredients}, MEMBERS) == [EXTRA]


# C1: a listed output named under an ingredient key (not `type`) is consumed only by a reviewed type
@pytest.mark.parametrize("body, key", [
    ({"type": "newmod:uncraft", "input": {"item": "x:y"}, "ingredients": [{"item": "ae2:drive"}]}, "ingredients"),
    ({"type": "newmod:reverse", "ingredient": {"item": "ae2:drive"}, "source": {"item": "x:y"}}, "ingredient"),
], ids=["ingredients", "ingredient"])
def test_a_listed_output_under_an_ingredient_key_of_an_unreviewed_type_is_an_unknown_shape(body, key):
    text = json.dumps(body[key], sort_keys=True)
    assert evil(body) == [f"UNKNOWN SHAPE ae2:drive (item) in evil:row, key {key} (an ingredient key of a type not in "
                          f"CONSUMING_TYPES): {text}"]


def test_the_reviewed_consuming_types():
    assert check_recipes.CONSUMING_TYPES == {
        "minecraft:crafting_shaped", "minecraft:crafting_shapeless", "kubejs:shaped", "minecraft:smithing_transform",
        "mekanism:combining", "mekanism:washing", "mekanism:mek_data", "industrialforegoing:dissolution_chamber",
        "ars_nouveau:enchanting_apparatus", "ad_astra:compressing", "ad_astra:nasa_workbench", "ae2:inscriber"}


# C2: a tag holding a listed output, mentioned in a product or unknown key where made_by did not read it as a product
TAG_SHAPE = "UNKNOWN SHAPE #c:drives (holds ae2:drive) in evil:row, key {key}: {text}"


@pytest.mark.parametrize("key, value", [
    ("drops", [{"tag": "c:drives"}]),                                                  # X1
    ("recipe", {"result": {"tag": "c:drives"}}),                                       # X2
    ("result", {"count": 2, "ingredient": {"tag": "c:drives"}}),                       # X3
    ("result", {"tag": {"id": "c:drives"}}),                                           # a tag object the rule does not read
], ids=["X1 drops", "X2 recipe wrapper", "X3 sized ingredient", "tag object"])
def test_a_listed_tag_in_a_shape_the_rule_does_not_read_is_an_unknown_shape(key, value):
    assert evil({"type": "modx:m", key: value}, MEMBERS) == [
        TAG_SHAPE.format(key=key, text=json.dumps(value, sort_keys=True))]


@pytest.mark.parametrize("s", ["2x #c:drives", " #c:drives", "#c:drives junk", "3 x #c:drives[x]"])
def test_a_tag_string_is_read_as_generously_as_an_id(s):   # X4: a count prefix, then '#', then the tag id
    assert evil({"type": "modx:m", "result": s}, MEMBERS) == [EXTRA]
    assert check_recipes.made_by({"result": s}).tags == [("c:drives", "item")]


def test_a_listed_tag_consumed_by_an_ingredient_key_is_fine():
    assert evil({"type": "modx:m", "ingredients": [{"tag": "c:drives"}], "input": "#c:drives", "result": "x:y"}, MEMBERS) == []
    assert evil({"type": "modx:m", "drops": [{"tag": "c:others"}]}, MEMBERS) == []   # a tag that holds no listed output


def test_main_refuses_a_members_export_older_than_the_dump(tmp_path, monkeypatch, capsys):
    """H1: tools/check_tags.py checks the members export against tags.json; this checks it is not older than the dump it
    expands (tagcheck.js writes it at ServerEvents.loaded, after dump.js wrote the dump in the recipes event)."""
    import os
    m = manifest(tmp_path, "gates:\n  - confluence:tier5/ultimate_control_circuit\n"
                           "sole_producers:\n  mekanism:ultimate_control_circuit: [confluence:tier5/ultimate_control_circuit]\n")
    dump, members = tmp_path / "recipes.json", tmp_path / "item_tag_members.json"
    dump.write_text(json.dumps(GOOD))
    members.write_text(json.dumps({"minecraft:item": {}}))
    monkeypatch.setattr(check_recipes, "DUMP", dump)
    monkeypatch.setattr(check_recipes, "MANIFEST", m)
    monkeypatch.setattr(check_recipes, "ITEM_MEMBERS", members)
    os.utime(dump, (2000, 2000))
    os.utime(members, (1000, 1000))
    assert check_recipes.main() == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "gates: 1 expected, 0 missing, 0 removed-still-present"
    assert out[1] == f"sole producers: STALE TAG MEMBERS {members} is older than {dump} (boot again)"
    os.utime(members, (2000, 2000))
    assert check_recipes.main() == 0
    assert capsys.readouterr().out.splitlines()[1] == "sole producers: 1 outputs, 0 bad"


def test_a_bare_listed_tag_counts_only_in_a_product_value_the_rule_does_not_read():
    """The bare form (no '#', no "tag":) is looked for only in the unread values, so an item id that is also a listed tag's id
    (ae2:pattern_provider is both in the 0.3 dump) is not taken for that tag where the rule reads it as an item."""
    members = {**MEMBERS, "ae2:drive": ["ae2:drive"]}
    result = [{"count": 1, "id": "ae2:drive"}, {"weird": "c:drives"}]
    body = {"type": "kubejs:shaped", **SHAPED_KEY, "result": result}
    text = json.dumps(result, sort_keys=True)
    assert check_sole_producers([row("confluence:tier5/drive", body)], DRIVE, members) == [
        f"UNKNOWN SHAPE #c:drives (holds ae2:drive) in confluence:tier5/drive, key result: {text}"]
