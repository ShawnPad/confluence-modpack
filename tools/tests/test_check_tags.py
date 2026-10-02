import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_tags import (
    IDS_JS,
    NON_ITEM_TAGS,
    check_deny_tags,
    check_members,
    ids_ref,
    read_tier_ore_members,
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


@pytest.mark.parametrize("src,want", [
    # a regex holding '//': not a comment
    (r"const r = /https?:\/\//g // gone", r"const r = /https?:\/\//g "),
    # a regex holding '/*' in a class: not a block comment, so the next line survives
    ("const r = /[/*]/ // gone\nconst t = '#c:kept'", "const r = /[/*]/ \nconst t = '#c:kept'"),
    # a regex holding a quote: not a string, so the comment after it is still a comment
    ("s.replace(/'/g, '') // '#c:fake'", "s.replace(/'/g, '') "),
    # bypass.js's regex, as it is written there
    ("event.remove({ id: /^deeperdarker:.*gloomslate_.*_ore$/ }) // x", "event.remove({ id: /^deeperdarker:.*gloomslate_.*_ore$/ }) "),
    # after a name, a number or ')' a '/' divides, and a comment after it still goes
    ("a = b / c // gone", "a = b / c "),
    ("a = f(x) / 2 /* gone */ + 1", "a = f(x) / 2   + 1"),   # a block comment becomes one space
    # Task 8b review: after '++' or '--' a '/' divides; after a single '+' or '-' (the end of an odd run) it starts a regex
    ("y = i++ / 2 // gone", "y = i++ / 2 "),
    ("y = i-- / 2 /* gone */ + 1", "y = i-- / 2   + 1"),
    ("y = a+++/x\\//.source // gone", "y = a+++/x\\//.source "),
    ("y = a + /'/.source // gone", "y = a + /'/.source "),
    # Task 8b round 3 (J-c): a block comment between two '+' keeps them apart, as in JS, so the '/' after them starts a regex
    ("y = a+/**/+/'/.source // '#c:fake'", "y = a+ +/'/.source "),
])
def test_strip_comments_reads_regex_literals(src, want):
    assert strip_js_comments(src) == want


def test_increment_before_a_slash_hides_no_tag():
    """Task 8b review: with `i++ /` read as the start of a regex, the regex would run to the '/' inside 'a/b', and the
    quotes after it would pair up wrongly, so '#c:real' would sit outside any string."""
    assert tags_from_script("x = i++ / 2 + 'a/b'; t = '#c:real'\n") == {"c:real"}
    assert tags_from_script("x = i-- / 2 + 'a/b'; t = '#c:real'\n") == {"c:real"}


def test_regex_start_rule_matches_jslex():
    """check_tags.py (tools/, run as a script) and tools/tests/jslex.py (the lints' tokenizer) each hold the rule for where
    a '/' starts a regex; keep them equal. jslex also has the token '=>', which check_tags sees as its last character '>'.
    Then, for each '/' jslex reads (as a regex or as division), check_tags' _regex_may_start on the text before it, with
    comments stripped as strip_js_comments strips them, must decide the same."""
    import check_tags
    import jslex
    assert check_tags.REGEX_AFTER_CHARS | check_tags.REGEX_AFTER_WORDS | {"=>"} == jslex.REGEX_AFTER
    snippets = ["y = i++ / 2 + 'a/b'", "y = a+++/x/.source", "y = --n / 2", "y = n-- / 2 / 3", "y = a + /x/.source",
                "y = a - -/x/.source.length", "return /x/", "f(x) / 2", "a = b / c", "x = [/a/, /b/]", "y = typeof /x/",
                "xs.some(s => /x/.test(s))", "s = 'q' / 2", "o = { k: /x/ }",
                # round 3 J-c: a block comment between two '+'; J-b: the documented limit both share
                "y = a+/**/+/x/.source", "y = a+/* c */+b / 2", "x = {} / 2 / 3", "y = function () {} / 2 / 3"]
    seen = 0
    for src in snippets:
        for t in jslex.tokens(src):
            if t.text.startswith("/") and t.kind in ("regex", "punct"):
                before = list(check_tags.strip_js_comments(src[:t.start]))
                assert check_tags._regex_may_start(before) == (t.kind == "regex"), (src, t)
                seen += 1
    assert seen == 20   # every snippet's slashes outside strings and comments


def test_documented_limit_slash_after_a_brace():
    """Round 3 J-b (the limit in strip_js_comments' docstring, shared with jslex): a '/' after '}' starts a regex, so after
    an object literal or a function expression the division is misread, and the comment after it is read as code. The pack
    writes neither form."""
    assert tags_from_script("x = {} / 2 // '#c:fake'\n") == {"c:fake"}
    assert tags_from_script("y = function () {} / 2 // '#c:fake'\n") == {"c:fake"}


def test_documented_limit_templates_are_plain_quotes():
    """Round 4 R11 (the last limit in strip_js_comments' docstring): a comment inside a ${ ... } is kept, so its tag counts;
    a nested template's backtick ends the outer template early, so a quote after it pairs wrongly. The pack writes neither."""
    assert tags_from_script("s = `${ x /* '#c:in_comment' */ }`\n") == {"c:in_comment"}
    # JS: the template ends at the last backtick before //, and the comment goes. Here the backticks pair up wrongly, the
    # quote in '`' opens a string, and the comment is kept with its tag.
    assert tags_from_script("s = `a ${ `b` + '`' } c` // '#c:fake'\n") == {"c:fake"}


def test_block_comment_between_plus_signs_hides_no_tag():
    """Round 3 J-c: with the comment dropped outright, `a+/**/+` became `a++` and the regex /'/ after it was read as division,
    so its quote opened a string and the comment's tag was read as code."""
    assert tags_from_script("x = a+/**/+/'/.source // '#c:fake'\nt = '#c:real'\n") == {"c:real"}


def test_regex_quote_hides_no_tag():
    """With the regex read as a string opener, the quote in /'/ would run to the next quote and the comment's tag would be
    read as code."""
    assert tags_from_script("s.replace(/'/g, '') // '#c:fake'\nconst x = '#c:real'\n") == {"c:real"}


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


# ---- v0.3 Task 8c: the members of the D112 block tags (kubejs/exported/tag_members.json, written by tagcheck.js) ----

IMMUNE = ["minecraft:wither_immune", "cataclysm:ignis_immune", "cataclysm:maledictus_immune", "cataclysm:scylla_immune",
          "cataclysm:netherite_monstrosity_immune"]
TIER_ORES = ["allthemodium:allthemodium_ore", "allthemodium:allthemodium_slate_ore", "allthemodium:vibranium_ore",
             "allthemodium:other_vibranium_ore", "allthemodium:unobtainium_ore"]
DENY_ORES = ["allthemodium:vibranium_ore", "allthemodium:other_vibranium_ore", "allthemodium:unobtainium_ore"]
# allthemodium-3.0.1_mc_1.21.1.jar!data/c/tags/block/needs_*_tool.json, the first two entries of each non-empty one.
NEEDS_MEMBERS = {
    "c:needs_allthemodium_tool": ["allthemodium:other_vibranium_ore", "allthemodium:vibranium_ore"],
    "c:needs_vibranium_tool": ["allthemodium:raw_unobtainium_block", "allthemodium:unobtainium_ore"],
    "c:needs_unobtainium_tool": ["allthemodium:ancient_smooth_stone"],
    "c:needs_allthemodiumalloy_tool": [],
}


def members_export(**overrides):
    """A synthetic tag_members.json: the needs tags above, each deny tag holding their union, each immune tag holding the five
    ores and one vanilla block. An override (tag with '__' for ':') replaces that tag's members; None drops the tag."""
    union = sorted({b for ms in NEEDS_MEMBERS.values() for b in ms})
    block = dict(NEEDS_MEMBERS)
    block.update({t: list(union) for t in DENY_NINE})
    block.update({t: sorted(TIER_ORES + ["minecraft:bedrock"]) for t in IMMUNE})
    for tag, members in overrides.items():
        tag = tag.replace("__", ":")
        if members is None:
            block.pop(tag)
        else:
            block[tag] = members
    return {"minecraft:block": block}


def test_members_pass():
    assert check_members(members_export(), DENY_NINE, ATM_NEEDS, IMMUNE, TIER_ORES, DENY_ORES) == []


def test_tier_ore_missing_from_an_immune_tag_fails():
    no_slate = sorted(o for o in TIER_ORES if o != "allthemodium:allthemodium_slate_ore")
    bad = check_members(members_export(cataclysm__scylla_immune=no_slate), DENY_NINE, ATM_NEEDS, IMMUNE, TIER_ORES, DENY_ORES)
    assert bad == ["NOT IMMUNE allthemodium:allthemodium_slate_ore is missing from #cataclysm:scylla_immune"]
    bad = check_members(members_export(minecraft__wither_immune=["minecraft:bedrock"]), DENY_NINE, ATM_NEEDS, IMMUNE,
                        TIER_ORES, DENY_ORES)
    assert bad == [f"NOT IMMUNE {o} is missing from #minecraft:wither_immune" for o in TIER_ORES]


def test_deny_tag_holding_a_block_outside_the_needs_tags_fails():
    union = sorted({b for ms in NEEDS_MEMBERS.values() for b in ms})
    bad = check_members(members_export(mekanism__incorrect_for_meka_tool=union + ["minecraft:obsidian"]),
                        DENY_NINE, ATM_NEEDS, IMMUNE, TIER_ORES, DENY_ORES)
    assert bad == ["DENY TAG #mekanism:incorrect_for_meka_tool holds blocks outside the 4 needs tags: ['minecraft:obsidian']"]


def test_deny_ore_missing_from_a_deny_tag_fails():
    """Vibranium ore and Unobtainium ore must be in every deny tag. A deny tag that lost one fails here even though it holds
    nothing outside the needs tags."""
    union = sorted({b for ms in NEEDS_MEMBERS.values() for b in ms} - {"allthemodium:unobtainium_ore"})
    bad = check_members(members_export(cataclysm__needs_black_steel_tool=union), DENY_NINE, ATM_NEEDS, IMMUNE, TIER_ORES,
                        DENY_ORES)
    assert bad == ["NOT DENIED allthemodium:unobtainium_ore is missing from #cataclysm:needs_black_steel_tool"]


def test_member_tag_missing_from_the_members_export_fails():
    bad = check_members(members_export(c__needs_vibranium_tool=None, cataclysm__ignis_immune=None), DENY_NINE, ATM_NEEDS,
                        IMMUNE, TIER_ORES, DENY_ORES)
    assert bad == ["NO MEMBERS #c:needs_vibranium_tool in tag_members.json", "NO MEMBERS #cataclysm:ignis_immune in tag_members.json"]
    assert check_members({}, DENY_NINE, ATM_NEEDS, IMMUNE, TIER_ORES, DENY_ORES) == [
        "NO SUCH REGISTRY minecraft:block in tag_members.json"]


def test_tier_ores_and_immune_tags_are_read_from_ids_js():
    assert read_tier_ore_members(IDS_JS.read_text()) == (IMMUNE, TIER_ORES, DENY_ORES)


def test_ids_ref_fails_closed():
    src = "IDS = { allthemodium: { ore: 'allthemodium:allthemodium_ore', x: 'a:b' } }\nIDS.allthemodium.vibraniumOre = 'a:v'\n"
    assert ids_ref(src, "IDS.allthemodium.ore") == "allthemodium:allthemodium_ore"
    assert ids_ref(src, "IDS.allthemodium.vibraniumOre") == "a:v"
    for ref in ("IDS.allthemodium.nope", "IDS.other.ore", "allthemodium.ore"):
        with pytest.raises(ValueError):
            ids_ref(src, ref)
    with pytest.raises(ValueError):   # assigned twice
        ids_ref(src + "IDS.allthemodium.vibraniumOre = 'a:w'\n", "IDS.allthemodium.vibraniumOre")


def test_main_fails_without_the_members_file(tmp_path, monkeypatch, capsys):
    """The counts export alone no longer passes: a boot whose tagcheck.js did not write tag_members.json fails, and the first
    line's bad count says so."""
    import check_tags
    export = tmp_path / "tags.json"
    # counts equal to the synthetic members' lengths (round 2, R4): each deny tag holds the 5-block union = 2 + 2 + 1 + 0
    block = {t: len(ms) for t, ms in members_export()["minecraft:block"].items()}
    export.write_text(json.dumps({"minecraft:item": {"c:drives": 1}, "minecraft:block": block}))
    (tmp_path / "item_tag_members.json").write_text(json.dumps({"minecraft:item": {"c:drives": ["ae2:drive"]}}))
    monkeypatch.setattr(check_tags, "EXPORT", export)
    monkeypatch.setattr(check_tags, "MEMBERS", tmp_path / "tag_members.json")
    monkeypatch.setattr(check_tags, "ITEM_MEMBERS", tmp_path / "item_tag_members.json")
    monkeypatch.setattr(check_tags, "collect_references", lambda root: {})
    assert check_tags.main() == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "tags: 0 referenced, 0 verified non-empty, 1 bad"
    assert out[-3].startswith("tag members (D112): ") and out[-3].endswith("; 1 bad")
    assert out[-2] == f"  MISSING EXPORT {tmp_path / 'tag_members.json'} (tagcheck.js writes it at ServerEvents.loaded)"
    assert out[-1] == "item tag members: 1 tags exported, 1 bound in tags.json; 0 bad"
    (tmp_path / "tag_members.json").write_text(json.dumps(members_export()))
    assert check_tags.main() == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "tags: 0 referenced, 0 verified non-empty, 0 bad"
    assert out[-2] == ("tag members (D112): 18 tags; 5 tier ores in 5 immune tags, 3 ores in 9 deny tags, 9 deny tags "
                       "within the 4 needs tags; 0 bad")
    assert out[-1] == "item tag members: 1 tags exported, 1 bound in tags.json; 0 bad"


# ---- v0.3 Task 8c round 2: both members exports are this boot's (R4), well formed (minor 10), and written where they are read ----

import check_tags  # noqa: E402
import check_recipes  # noqa: E402


def test_a_members_count_that_differs_from_tags_json_is_stale():
    """Each exported tag's member list must be as long as tags.json's count for it: the two files come from one walk, so a
    difference means a members file left over from another boot."""
    export = {"minecraft:block": {"a:one": 2, "a:two": 1}}
    assert check_tags.check_freshness({"minecraft:block": {"a:one": ["x:a", "x:b"], "a:two": ["x:c"]}}, export,
                                      "minecraft:block", "tag_members.json") == []
    assert check_tags.check_freshness({"minecraft:block": {"a:one": ["x:a"], "a:gone": []}}, export, "minecraft:block",
                                      "tag_members.json") == [
        "STALE #a:one in tag_members.json: 1 members, tags.json counts 2",
        "STALE #a:gone in tag_members.json: not bound in tags.json"]


def test_the_item_export_must_hold_every_bound_item_tag():
    export = {"minecraft:item": {"a:one": 1, "a:two": 0, "a:three": 4}}
    bad = check_tags.check_freshness({"minecraft:item": {"a:one": ["x:a"]}}, export, "minecraft:item",
                                     "item_tag_members.json", complete=True)
    assert bad == ["NOT EXPORTED 2 of 3 minecraft:item tags bound in tags.json are missing from item_tag_members.json: "
                   "#a:three, #a:two"]


def test_a_stale_export_is_reported_in_at_most_eleven_lines():
    export = {"minecraft:item": {f"a:t{i:02}": 1 for i in range(30)}}
    bad = check_tags.check_freshness({"minecraft:item": {f"a:t{i:02}": [] for i in range(30)}}, export, "minecraft:item",
                                     "item_tag_members.json", complete=True)
    assert len(bad) == 11 and bad[-1] == "STALE ... and 20 more tags in item_tag_members.json"


@pytest.mark.parametrize("members, line", [
    ({"minecraft:block": {"a:one": "x:a"}}, "BAD MEMBERS #a:one in tag_members.json: not a list of strings"),
    ({"minecraft:block": {"a:one": ["x:a", 3]}}, "BAD MEMBERS #a:one in tag_members.json: not a list of strings"),
    ({"minecraft:block": {"a:one": None}}, "BAD MEMBERS #a:one in tag_members.json: not a list of strings"),
    ({"minecraft:block": ["a:one"]}, "BAD MEMBERS minecraft:block in tag_members.json: not a {tag: [id, ...]} map"),
    ({}, "NO SUCH REGISTRY minecraft:block in tag_members.json"),
])
def test_a_member_value_that_is_not_a_list_of_strings_fails(members, line):
    assert check_tags.check_freshness(members, {"minecraft:block": {"a:one": 1}}, "minecraft:block", "tag_members.json") == [line]
    if members.get("minecraft:block") is not None and isinstance(members["minecraft:block"], dict):
        assert check_members(members, [], [], [], [], []) == [line]


def test_main_fails_on_a_stale_or_missing_item_export(tmp_path, monkeypatch, capsys):
    export = tmp_path / "tags.json"
    block = {t: len(ms) for t, ms in members_export()["minecraft:block"].items()}
    export.write_text(json.dumps({"minecraft:item": {"c:drives": 2}, "minecraft:block": block}))
    (tmp_path / "tag_members.json").write_text(json.dumps(members_export()))
    monkeypatch.setattr(check_tags, "EXPORT", export)
    monkeypatch.setattr(check_tags, "MEMBERS", tmp_path / "tag_members.json")
    monkeypatch.setattr(check_tags, "ITEM_MEMBERS", tmp_path / "item_tag_members.json")
    monkeypatch.setattr(check_tags, "collect_references", lambda root: {})
    assert check_tags.main() == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "tags: 0 referenced, 0 verified non-empty, 1 bad"
    assert out[-2:] == ["item tag members: 0 tags exported, 1 bound in tags.json; 1 bad",
                        f"  MISSING EXPORT {tmp_path / 'item_tag_members.json'} (tagcheck.js writes it at ServerEvents.loaded)"]
    (tmp_path / "item_tag_members.json").write_text(json.dumps({"minecraft:item": {"c:drives": ["ae2:drive"]}}))
    assert check_tags.main() == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "tags: 0 referenced, 0 verified non-empty, 1 bad"
    assert out[-1] == "  STALE #c:drives in item_tag_members.json: 1 members, tags.json counts 2"
    # the block members file is held to the same rule
    stale = members_export()
    stale["minecraft:block"]["minecraft:wither_immune"] = stale["minecraft:block"]["minecraft:wither_immune"][1:]
    (tmp_path / "tag_members.json").write_text(json.dumps(stale))
    (tmp_path / "item_tag_members.json").write_text(json.dumps({"minecraft:item": {"c:drives": ["ae2:drive", "x:y"]}}))
    assert check_tags.main() == 1
    out = capsys.readouterr().out.splitlines()
    assert "  STALE #minecraft:wither_immune in tag_members.json: 5 members, tags.json counts 6" in out


def test_tagcheck_writes_exactly_the_files_the_checkers_read():
    """The JsonIO.write path literals in tagcheck.js and dump.js (relative to the server directory, .run/server) are the
    files check_tags.py and check_recipes.py read, and the two checkers read the item export from one place."""
    import re
    server = check_tags.ROOT / ".run" / "server"
    scripts = check_tags.ROOT / "kubejs" / "server_scripts"
    written = {name: re.findall(r"JsonIO\.write\(\s*'([^']*)'", (scripts / name).read_text()) for name in ("tagcheck.js", "dump.js")}
    assert sorted(server / p for p in written["tagcheck.js"]) == sorted(
        [check_tags.EXPORT, check_tags.MEMBERS, check_tags.ITEM_MEMBERS])
    assert [server / p for p in written["dump.js"]] == [check_recipes.DUMP]
    assert check_recipes.ITEM_MEMBERS == check_tags.ITEM_MEMBERS
    assert len(re.findall(r"JsonIO\.write\(", (scripts / "tagcheck.js").read_text())) == 3
