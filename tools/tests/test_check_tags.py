import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_tags import (
    NON_ITEM_TAGS,
    collect_references,
    run_checks,
    strip_js_comments,
    tags_from_json,
    tags_from_script,
)

EXPORT = {
    "minecraft:item": {
        "c:ingots/osmium": 3,
        "aether:gems/zanite": 1,
        "confluence:ars_essences": 4,
        "c:gems/zanite": 0,
    },
    "minecraft:worldgen/biome": {"twilightforest:in_twilight_forest": 25},
}


def test_script_literals_found_in_nested_objects():
    src = "const IDS = { a: { b: '#c:ingots/osmium' }, c: [\"#aether:gems/zanite\"] }"
    assert tags_from_script(src) == {"c:ingots/osmium", "aether:gems/zanite"}


def test_grid_key_hash_and_bare_hash_are_not_tags():
    src = "recipe(['I#G'], { '#': 'minecraft:furnace' })  // raw JSON drops the leading '#'."
    assert tags_from_script(src) == set()


def test_comments_are_stripped():
    src = "// the c: form '#c:gems/zanite' is an empty tag\nconst x = '#aether:gems/zanite'\n"
    assert tags_from_script(src) == {"aether:gems/zanite"}


def test_block_comment_stripped_but_strings_kept():
    src = "/* '#c:wrong/tag' */ const x = '#c:ingots/osmium' // trailing\n"
    assert tags_from_script(src) == {"c:ingots/osmium"}


def test_strip_comments_leaves_a_slash_inside_a_string():
    assert strip_js_comments("const u = 'http://x//y' // gone") == "const u = 'http://x//y' "


def test_json_tag_values_at_any_depth():
    doc = {
        "key": {"A": {"tag": "c:plastics"}},
        "ingredients": [{"tag": "#confluence:ars_essences"}, {"item": "minecraft:stone"}],
    }
    assert tags_from_json(doc) == {"c:plastics", "confluence:ars_essences"}


def test_all_good():
    refs = {"c:ingots/osmium": ["a.js"], "twilightforest:in_twilight_forest": ["worldgen.js"]}
    res = run_checks(refs, EXPORT)
    assert res.failures == []
    assert res.checked == {"c:ingots/osmium": 3, "twilightforest:in_twilight_forest": 25}


def test_absent_tag_fails_and_is_named():
    res = run_checks({"c:gems/nonexistent": ["lib/ids.js"]}, EXPORT)
    assert res.absent == [("c:gems/nonexistent", "minecraft:item", ["lib/ids.js"])]
    assert res.checked == {}


def test_bound_but_empty_tag_fails():
    """The zanite defect: c:gems/zanite exists in the export with 0 elements."""
    res = run_checks({"c:gems/zanite": ["lib/ids.js"]}, EXPORT)
    assert res.empty == [("c:gems/zanite", "minecraft:item", ["lib/ids.js"])]
    assert res.absent == []


def test_non_item_tag_is_not_looked_up_in_the_item_registry():
    export = {"minecraft:item": {}, "minecraft:worldgen/biome": {"twilightforest:in_twilight_forest": 25}}
    assert run_checks({"twilightforest:in_twilight_forest": ["worldgen.js"]}, export).failures == []


def test_missing_registry_reported():
    res = run_checks({"c:ingots/osmium": ["a.js"]}, {"minecraft:block": {}})
    assert res.no_registry == [("c:ingots/osmium", "minecraft:item", ["a.js"])]


def test_collect_references_walks_scripts_and_data(tmp_path):
    (tmp_path / "kubejs/server_scripts/lib").mkdir(parents=True)
    (tmp_path / "kubejs/startup_scripts").mkdir(parents=True)
    (tmp_path / "kubejs/client_scripts").mkdir(parents=True)
    (tmp_path / "kubejs/data/mod/recipe").mkdir(parents=True)
    (tmp_path / "kubejs/server_scripts/lib/ids.js").write_text(
        "const IDS = { m: { o: '#c:ingots/osmium' } }\n// '#c:gems/zanite' is empty\n"
    )
    (tmp_path / "kubejs/startup_scripts/items.js").write_text("event.create('coin')\n")
    (tmp_path / "kubejs/client_scripts/jei.js").write_text("event.add('#c:plastics')\n")
    (tmp_path / "kubejs/data/mod/recipe/x.json").write_text(
        json.dumps({"ingredients": [{"tag": "c:circuits/basic"}]})
    )
    refs = collect_references(tmp_path)
    assert set(refs) == {"c:ingots/osmium", "c:plastics", "c:circuits/basic"}
    assert refs["c:circuits/basic"] == ["kubejs/data/mod/recipe/x.json"]
    assert refs["c:ingots/osmium"] == ["kubejs/server_scripts/lib/ids.js"]


def test_v03_block_tags_are_checked_in_the_block_registry():
    """v0.3 (spec §7 D112, §8): allthemodium:ancient_stone is also a 1-entry item tag, so looked up in minecraft:item it
    would pass even when the block tag lib/ids.js means is empty. Checked in minecraft:block, an empty one fails. The
    pin: all eleven v0.3 block tags (ATM tool tiers, boss immunity, ore-target stones) map to minecraft:block."""
    v03 = [
        "c:needs_allthemodium_tool", "c:needs_vibranium_tool", "c:needs_unobtainium_tool",
        "minecraft:wither_immune", "cataclysm:ignis_immune", "cataclysm:maledictus_immune",
        "cataclysm:scylla_immune", "cataclysm:netherite_monstrosity_immune",
        "allthemodium:ancient_stone", "ad_astra:mercury_stone_replaceables", "ad_astra:glacio_stone_replaceables",
    ]
    assert {t: NON_ITEM_TAGS.get(t) for t in v03} == {t: "minecraft:block" for t in v03}
    export = {"minecraft:item": {"allthemodium:ancient_stone": 1}, "minecraft:block": {"allthemodium:ancient_stone": 0}}
    res = run_checks({"allthemodium:ancient_stone": ["kubejs/server_scripts/lib/ids.js"]}, export)
    assert res.empty == [("allthemodium:ancient_stone", "minecraft:block", ["kubejs/server_scripts/lib/ids.js"])]
    assert res.checked == {}


def test_bare_tag_ids_are_not_references():
    """Bound-but-empty tags stay bare in lib/ids.js (IDS.tierOres.incorrectForTags, alloyToolTagEmpty), so the
    checker never looks them up; only a leading '#' inside one literal makes a reference. Task 8 nests the empty
    alloy tag as '#' + IDS.tierOres.alloyToolTagEmpty (spec §7 D112a), which must stay invisible too."""
    src = ("IDS.tierOres = { t: ['undergarden:incorrect_for_forgotten_tool'], a: 'c:needs_allthemodiumalloy_tool' }\n"
           "event.add(IDS.tierOres.t[0], '#' + IDS.tierOres.a)\n")
    assert tags_from_script(src) == set()


def test_empty_twin_in_another_registry_fails(monkeypatch):
    """A block tag missing from NON_ITEM_TAGS is looked up as an item tag. If an item tag of the same id is non-empty
    it passes by accident, while the block tag the script means is bound with 0 entries: report that 'empty twin'.
    An explicit NON_ITEM_TAGS entry is the cited way to accept a tag, so a mapped tag is never an empty twin."""
    export = {"minecraft:item": {"mod:stone": 1, "c:ingots/osmium": 3}, "minecraft:block": {"mod:stone": 0, "c:ingots/osmium": 2}}
    res = run_checks({"mod:stone": ["lib/ids.js"], "c:ingots/osmium": ["a.js"]}, export)
    assert res.empty_twin == [("mod:stone", "minecraft:block", ["lib/ids.js"])]
    assert res.checked == {"c:ingots/osmium": 3}
    assert res.failures == [("mod:stone", "minecraft:block", ["lib/ids.js"])]
    monkeypatch.setitem(NON_ITEM_TAGS, "mod:mapped", "minecraft:block")
    mapped = run_checks({"mod:mapped": ["lib/ids.js"]}, {"minecraft:item": {"mod:mapped": 0}, "minecraft:block": {"mod:mapped": 2}})
    assert mapped.empty_twin == [] and mapped.checked == {"mod:mapped": 2}
