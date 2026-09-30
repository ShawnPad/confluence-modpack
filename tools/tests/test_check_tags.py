import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_tags import (
    IDS_JS,
    NON_ITEM_TAGS,
    check_deny_tags,
    collect_references,
    ids_value,
    read_tier_ore_tags,
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


# D112(a) (v0.3 plan Task 8): the nine deny tags and ATM's four needs tags, as lib/ids.js names them.
DENY_NINE = [
    "cataclysm:needs_monstrosity_tool", "cataclysm:needs_black_steel_tool", "undergarden:incorrect_for_forgotten_tool",
    "deeperdarker:incorrect_for_resonarium_tool", "deeperdarker:incorrect_for_warden_tool", "mekanism:incorrect_for_disassembler",
    "mekanism:incorrect_for_meka_tool", "mysticalagriculture:incorrect_for_supremium_tool",
    "mysticalagriculture:incorrect_for_awakened_supremium_tool",
]
ATM_NEEDS = ["c:needs_allthemodium_tool", "c:needs_vibranium_tool", "c:needs_unobtainium_tool", "c:needs_allthemodiumalloy_tool"]


def deny_export(deny=27, **overrides):
    """A synthetic tags.json: the four needs tags at their 0.3.0 counts (4, 3, 20, 0) and every deny tag at `deny`. An
    override of None drops that tag from the export."""
    block = {"c:needs_allthemodium_tool": 4, "c:needs_vibranium_tool": 3, "c:needs_unobtainium_tool": 20,
             "c:needs_allthemodiumalloy_tool": 0, "minecraft:wither_immune": 107}
    block.update({t: deny for t in DENY_NINE})
    for tag, count in overrides.items():
        tag = tag.replace("__", ":")
        if count is None:
            block.pop(tag)
        else:
            block[tag] = count
    return {"minecraft:item": {}, "minecraft:block": block}


def test_deny_tags_holding_the_needs_sum_pass():
    assert check_deny_tags(deny_export(), DENY_NINE, ATM_NEEDS) == (27, [])


def test_deny_tag_at_zero_fails():
    """The 0.2.1 state (each deny tag ships empty), for one tag, and for all nine."""
    expected, bad = check_deny_tags(deny_export(**{"mekanism__incorrect_for_meka_tool": 0}), DENY_NINE, ATM_NEEDS)
    assert (expected, bad) == (27, ["DENY TAG #mekanism:incorrect_for_meka_tool holds 0 blocks, expected 27"])
    assert len(check_deny_tags(deny_export(deny=0), DENY_NINE, ATM_NEEDS)[1]) == 9


def test_deny_or_needs_tag_missing_from_the_export_fails():
    """A deny tag that is not bound at all fails. So does a missing needs tag: if ATM stopped shipping the empty
    needs_allthemodiumalloy_tool, vanilla would build none of the nine (they reference it), and the sum is unknown."""
    expected, bad = check_deny_tags(deny_export(**{"cataclysm__needs_black_steel_tool": None}), DENY_NINE, ATM_NEEDS)
    assert (expected, bad) == (27, ["ABSENT #cataclysm:needs_black_steel_tool (a D112a deny tag) not bound in minecraft:block"])
    gone = deny_export(**{"c__needs_allthemodiumalloy_tool": None}, **{t.replace(":", "__"): None for t in DENY_NINE})
    expected, bad = check_deny_tags(gone, DENY_NINE, ATM_NEEDS)
    assert expected is None and len(bad) == 10
    assert bad[0] == "ABSENT #c:needs_allthemodiumalloy_tool (an ATM needs tag) not bound in minecraft:block"
    no_block = check_deny_tags({"minecraft:item": {}}, DENY_NINE, ATM_NEEDS)
    assert no_block == (None, ["NO SUCH REGISTRY minecraft:block in the export"])


def test_needs_tags_summing_to_zero_fail():
    """Deny tags equal to an empty sum would deny nothing, so a pass there would be vacuous."""
    empty = {t.replace(":", "__"): 0 for t in ATM_NEEDS}
    expected, bad = check_deny_tags(deny_export(deny=0, **empty), DENY_NINE, ATM_NEEDS)
    assert expected == 0 and bad == ["the ATM needs tags hold 0 blocks between them, so the deny tags would deny nothing"]


def test_deny_and_needs_tags_are_read_from_ids_js():
    assert read_tier_ore_tags(IDS_JS.read_text()) == (DENY_NINE, ATM_NEEDS)


def test_ids_value_fails_closed():
    """A missing, repeated or computed key raises, so the boot check can never pass by checking nothing."""
    assert ids_value("a: ['x:y', \"x:z\"], b: 'q:r'", "a") == ["x:y", "x:z"]
    assert ids_value("a: ['x:y'], b: 'q:r'", "b") == "q:r"
    for src in ("b: ['x:y']", "a: ['x:y'], a: ['x:z']", "a: [IDS.x.y, 'x:z']", "a: []", "a: IDS.x.y"):
        with pytest.raises(ValueError):
            ids_value(src, "a")
