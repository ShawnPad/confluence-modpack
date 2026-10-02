from pathlib import Path
import re
import shutil
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_quests
from check_quests import (ENTRY, LEGENDARY_ALLOWED, QUESTS, canonical_problems, chapter_reward_hits, excluded_in_table,
                          forbidden_in_table, quests_in_lang, tree_nodes)
from scaffold_chapter import parseable_id, quest_id

TREE = """
### Tier 1 — Nether
- [D1.1] Nether key — vanilla
  - gate: [T0.2] Mekanism osmium ingot (recipe); [M0.1] Ars source gem (recipe)
- [X1.1] Netherite — vanilla
  - gate: [D1.1] the Nether (dimension)
### Tier 2 — Twilight Forest
- [D2.1] Twilight key
  - gate: [X1.1] netherite ingot (recipe)
"""

def test_tree_nodes_and_gates():
    nodes = tree_nodes(TREE, tiers={1})
    assert set(nodes) == {"D1.1", "X1.1"}
    assert nodes["D1.1"] == ["T0.2", "M0.1"]

def test_lang_nodes():
    lang = '{\n\tquest.' + quest_id("D1.1") + '.title: "Nether Key"\n\tquest.' + quest_id("D1.1") + '.quest_desc: ["text"]\n}'
    assert quests_in_lang(lang, ["D1.1", "D2.1"]) == {"D1.1": quest_id("D1.1")}

def test_forbidden():
    table = 'item: { count: 1, id: "kubejs:twilight_key" }\nitem: { count: 1, id: "minecraft:bread" }'
    assert forbidden_in_table(table) == ["kubejs:twilight_key"]

def test_gate_refs_ignore_citations():
    # combined-tree.md L175: a cross-pack citation "(recipe, ozone [T4.2] pattern)" is not a hard gate
    tree = "### Tier 1 — Nether\n- [T1.1] x\n  - gate: [M0.1] Ars source gem (recipe) `[design]`; [T0.2] osmium ingot (recipe, ozone [T4.2] pattern)\n"
    assert tree_nodes(tree, tiers={1})["T1.1"] == ["M0.1", "T0.2"]


def test_lang_nodes_multiline_list():
    # research/phase6-tooling-worldgen-quests.md §4.7 L509-512: FTB Quests re-saves a multi-entry quest_desc one entry
    # per line; the title key is unaffected either way, so the mapping survives an editor round-trip.
    lang = '{\n\tquest.' + quest_id("D1.1") + '.quest_desc: [\n\t\t"a"\n\t\t"b"\n\t]\n\tquest.' + quest_id("D1.1") + '.title: "Nether Key"\n}'
    assert quests_in_lang(lang, ["D1.1"]) == {"D1.1": quest_id("D1.1")}


# ---- v0.3 reward tables (spec §9.2, §10; D126). Every item id below was read from a jar at plan time: the lang key in
# the comment is in that jar's assets/<ns>/lang/en_us.json (vanilla: server-1.21.1-20240808.144430-extra.jar), and the
# kubejs: ids are event.create() calls in kubejs/startup_scripts/items.js.
V03_FORBIDDEN = [
    "ad_astra:nasa_workbench",             # adastra-1.21.1-1.16.25-neoforge.jar block.ad_astra.nasa_workbench
    "ars_nouveau:wilden_tribute",          # ars_nouveau-1.21.1-5.13.1.jar item.ars_nouveau.wilden_tribute
    "irons_spellbooks:divine_soulshard",   # irons_spellbooks-1.21.1-3.16.3.jar item.irons_spellbooks.divine_soulshard
    "mekanism:ultimate_control_circuit",   # Mekanism-1.21.1-10.7.19.85.jar item.mekanism.ultimate_control_circuit
    "kubejs:mercury_shard", "kubejs:glacio_shard", "kubejs:mercury_ore", "kubejs:glacio_ore",
    # eternalstarlight-0.9.0+1.21.1+neoforge.jar item.eternal_starlight.{unrealium,golem_steel}_{ingot,nugget} and
    # block.eternal_starlight.{unrealium,golem_steel}_block
    "eternal_starlight:unrealium_ingot", "eternal_starlight:unrealium_nugget", "eternal_starlight:unrealium_block",
    "eternal_starlight:golem_steel_ingot", "eternal_starlight:golem_steel_nugget", "eternal_starlight:golem_steel_block",
    "minecraft:dragon_egg",                # block.minecraft.dragon_egg
    "the_bumblezone:essence_of_the_bees",  # the_bumblezone-7.15.3+1.21.1-neoforge.jar item.the_bumblezone.essence_of_the_bees
]
# Caught before v0.3 too; listed so the one-alternative-per-line rewrite of FORBIDDEN is shown to keep them. Lang keys:
# item.allthemodium.{vibranium_ingot,piglich_heart}, item.ad_astra.desh_ingot, item.cataclysm.ignitium_ingot
# (L_Ender's Cataclysm 1.21.1-3.33.jar), item.twilightforest.knightmetal_ingot, item.undergarden.forgotten_ingot.
V02_FORBIDDEN = [
    "kubejs:other_key", "allthemodium:vibranium_ingot", "allthemodium:piglich_heart", "ad_astra:desh_ingot",
    "cataclysm:ignitium_ingot", "twilightforest:knightmetal_ingot", "undergarden:forgotten_ingot",
]
# Registered items next to a forbidden one that must stay allowed: item.mekanism.{elite,advanced,basic}_control_circuit,
# item.ars_nouveau.wilden_horn, item.irons_spellbooks.arcane_essence, item.minecraft.dragon_breath,
# block.minecraft.dragon_head, item.eternal_starlight.deepsilver_ingot, item.ad_astra.steel_ingot,
# item.the_bumblezone.royal_jelly_bottle, and kubejs:coin (items.js).
NEAR_MISSES = [
    "mekanism:elite_control_circuit", "mekanism:advanced_control_circuit", "mekanism:basic_control_circuit",
    "ars_nouveau:wilden_horn", "irons_spellbooks:arcane_essence", "minecraft:dragon_breath", "minecraft:dragon_head",
    "eternal_starlight:deepsilver_ingot", "ad_astra:steel_ingot", "the_bumblezone:royal_jelly_bottle", "kubejs:coin",
    # R2 (D133): the two lower Industrial Foregoing frames (block.industrialforegoing.machine_frame_{pity,simple},
    # industrialforegoing-1.21-3.6.39.jar) and Ad Astra steel (item.ad_astra.{steel_plate,steel_rod},
    # block.ad_astra.steel_block, adastra-1.21.1-1.16.25-neoforge.jar): the widened ad_astra alternative must not reach
    # steel. Steel plates and blocks are in spec §10's excluded set, which EXCLUDED checks; they are not FORBIDDEN.
    "industrialforegoing:machine_frame_pity", "industrialforegoing:machine_frame_simple",
    "ad_astra:steel_plate", "ad_astra:steel_rod", "ad_astra:steel_block",
]
# Spec §10 (D126): table id, entry-id prefix (D63/D68 pattern: entries are 0C0F1B000000<table><entry>), order_index,
# then (count, item id, weight) in file order.
BAGS = {
    "epic_bag": ("0C0F1B0000000004", "0C0F1B00000004", 3, [
        (4, "minecraft:netherite_ingot", 15), (16, "minecraft:diamond", 15), (8, "mekanism:ingot_refined_obsidian", 15),
        (8, "powah:crystal_spirited", 10), (4, "ars_nouveau:source_gem_block", 10), (32, "irons_spellbooks:arcane_essence", 10),
        (16, "minecraft:experience_bottle", 10), (8, "mekanism:alloy_reinforced", 5), (48, "kubejs:coin", 10)]),
    "legendary_bag": ("0C0F1B0000000005", "0C0F1B00000005", 4, [
        (8, "minecraft:netherite_ingot", 15), (4, "minecraft:diamond_block", 15), (16, "mekanism:ingot_refined_obsidian", 15),
        (32, "industrialforegoing:plastic", 10), (8, "mekanism:elite_control_circuit", 10),
        (8, "ars_nouveau:source_gem_block", 10), (32, "minecraft:experience_bottle", 10), (16, "powah:crystal_spirited", 5),
        (64, "kubejs:coin", 10)]),
}


def _row(item_id):
    return f'\t\t{{ id: "0C0F1B0000000999" item: {{ count: 1, id: "{item_id}" }} weight: 10.0f }}'


def test_forbidden_catches_v03_ids_and_keeps_v02_ones():
    missed = [i for i in V03_FORBIDDEN + V02_FORBIDDEN if forbidden_in_table(_row(i)) != [i]]
    assert missed == []


def test_forbidden_spares_near_misses():
    assert [i for i in NEAR_MISSES if forbidden_in_table(_row(i))] == []


def test_forbidden_spares_every_epic_and_legendary_entry():
    entries = sorted({item for _, _, _, rows in BAGS.values() for _, item, _ in rows})
    assert [i for i in entries if forbidden_in_table(_row(i))] == []


def test_committed_reward_tables():
    tables = {p.stem: p.read_text() for p in sorted((QUESTS / "reward_tables").glob("*.snbt"))}
    assert sorted(tables) == ["common_bag", "epic_bag", "legendary_bag", "rare_bag", "uncommon_bag"]
    # every table, the three shipped ones included, passes the extended FORBIDDEN
    assert {name: forbidden_in_table(text) for name, text in tables.items()} == {name: [] for name in tables}
    colors = {name: re.search(r"^\t\tcolor: ([0-9]+)$", text, re.M).group(1) for name, text in tables.items()}
    assert len(set(colors.values())) == 5, colors
    ids = [re.search(r'^\tid: "([0-9A-F]{16})"$', text, re.M).group(1) for text in tables.values()]
    ids += [m.group(1) for text in tables.values() for m in ENTRY.finditer(text)]
    assert len(ids) == len(set(ids)) and all(parseable_id(i) for i in ids)
    for name, (table_id, prefix, order, rows) in BAGS.items():
        text = tables[name]
        for line in (f'\tid: "{table_id}"', f'\t\tstring_id: "{name}"', "\t\tglow: 1b",
                     "\t\tdrops: { boss: 0 monster: 0 passive: 0 }", "\tloot_size: 3", f"\torder_index: {order}",
                     "\tuse_title: true"):
            assert re.search("^" + re.escape(line) + "$", text, re.M), (name, line)
        want = [(f"{prefix}{n:02d}", str(c), item, str(w)) for n, (c, item, w) in enumerate(rows, 1)]
        assert ENTRY.findall(text) == want


# ---- R1 (v0.3 Task 10 round 2, D133): a reward table must be in the one canonical shape. FTB Quests reads a table with
# ftb-library's SNBT parser, which accepts many shapes a text check cannot read: single quotes, an unknown escape (dropped),
# bare words, an id with a leading colon or no namespace (both parse as minecraft:), typed rewards (a type: "command" row
# becomes a CommandReward), item components, and lines starting with // or # (dropped before parsing). The reviewers ran each
# shape through the real parser (scratchpad t10-verify/forbidden/java/P.java, doctor.py). All 41 shipped rows are one
# shape, so check_quests.canonical_problems requires it and main() fails on anything else.
ROW = '\t\t{ id: "0C0F1B0000000401" item: { count: 4, id: "minecraft:netherite_ingot" } weight: 15.0f }'
BAD_ROWS = {
    "single-quoted id": "\t\t{ id: \"0C0F1B0000000401\" item: { count: 1, id: 'minecraft:dragon_egg' } weight: 15.0f }",
    "single-quoted string item": "\t\t{ id: \"0C0F1B0000000401\" item: 'minecraft:dragon_egg' weight: 15.0f }",
    "string item": '\t\t{ id: "0C0F1B0000000401" item: "minecraft:dragon_egg" weight: 15.0f }',
    "legacy Count compound": '\t\t{ id: "0C0F1B0000000401" item: { Count: 1b, id: "minecraft:dragon_egg" } weight: 15.0f }',
    "legacy compound, single-quoted id": "\t\t{ id: \"0C0F1B0000000401\" item: { Count: 1b, id: 'minecraft:dragon_egg', tag: { } } weight: 15.0f }",
    "unknown escape, dropped by FTB": '\t\t{ id: "0C0F1B0000000401" item: { count: 1, id: "minecraft:dragon_eg\\g" } weight: 15.0f }',
    "bare-word item": '\t\t{ id: "0C0F1B0000000401" item: dragon_egg weight: 15.0f }',
    "bare-word id": '\t\t{ id: "0C0F1B0000000401" item: { count: 1, id: dragon_egg } weight: 15.0f }',
    "leading-colon id": '\t\t{ id: "0C0F1B0000000401" item: { count: 1, id: ":dragon_egg" } weight: 15.0f }',
    "no namespace": '\t\t{ id: "0C0F1B0000000401" item: { count: 1, id: "dragon_egg" } weight: 15.0f }',
    "command reward": '\t\t{ command: "/give @p minecraft:dragon_egg 1" id: "0C0F1B0000000401" type: "command" weight: 15.0f }',
    "typed item reward": '\t\t{ id: "0C0F1B0000000401" item: { count: 1, id: "minecraft:diamond" } type: "item" weight: 15.0f }',
    "components (a bundle holding an egg)": '\t\t{ id: "0C0F1B0000000401" item: { components: { "minecraft:bundle_contents": '
                                            '[{ count: 1, id: "minecraft:dragon_egg" }] }, count: 1, id: "minecraft:bundle" } '
                                            'weight: 15.0f }',
    "reward-level count": '\t\t{ count: 4, id: "0C0F1B0000000401" item: "minecraft:dragon_egg" weight: 15.0f }',
    "equals separators": '\t\t{ id = "0C0F1B0000000401" item = { count = 1, id = "minecraft:dragon_egg" } weight = 15.0f }',
    "two rows on one line": ROW + " " + ROW.strip(),
    # round 3, M1: FTB Quests pays a zero-weight row on every opening (check_quests.ENTRY), and Python's \d reads
    # fullwidth digits
    "zero weight": '\t\t{ id: "0C0F1B0000000401" item: { count: 4, id: "minecraft:netherite_ingot" } weight: 0.0f }',
    "fullwidth count": '\t\t{ id: "0C0F1B0000000401" item: { count: \uff14, id: "minecraft:netherite_ingot" } weight: 15.0f }',
    "fullwidth weight": '\t\t{ id: "0C0F1B0000000401" item: { count: 4, id: "minecraft:netherite_ingot" } weight: \uff11\uff15.0f }',
}
BAD_LINES = {   # (anchor line, replacement lines): the anchor is replaced by the lines
    "// comment line": (ROW, ['\t\t// { id: "0C0F1B0000000499" item: { count: 1, id: "minecraft:dragon_egg" } weight: 1.0f }', ROW]),
    "# comment line": (ROW, ["# a note", ROW]),
    "empty_weight": ("\tloot_size: 3", ["\tempty_weight: 50.0f", "\tloot_size: 3"]),
    "loot_table_id": ("\tloot_size: 3", ['\tloot_size: 3', '\tloot_table_id: "minecraft:chests/end_city_treasure"']),
    "a key smuggled onto a crate line": ("\t\tglow: 1b", ["\t\tglow: 1b } empty_weight: 50.0f loot_crate2: {"]),
    "a key smuggled onto a top-level line": ("\tloot_size: 3", ["\tloot_size: 3 empty_weight: 50.0f"]),
    "a top-level key twice": ("\tuse_title: true", ["\tuse_title: true", "\tloot_size: 9"]),
    "rewards inline": (ROW, []),   # with the next edit below, the block collapses onto one line
    "loot_size 0": ("\tloot_size: 3", ["\tloot_size: 0"]),               # round 3, M1: an empty bag
    "fullwidth loot_size": ("\tloot_size: 3", ["\tloot_size: \uff13"]),
    "fullwidth color": ("\t\tcolor: 16755200", ["\t\tcolor: \uff11\uff16755200"]),
    "fullwidth drops": ("\t\tdrops: { boss: 0 monster: 0 passive: 0 }", ["\t\tdrops: { boss: \uff10 monster: 0 passive: 0 }"]),
    "fullwidth order_index": ("\torder_index: 3", ["\torder_index: \uff13"]),
}


def _epic():
    return (QUESTS / "reward_tables" / "epic_bag.snbt").read_text()


def _doctor_row(row):
    text = _epic()
    assert ROW in text
    return text.replace(ROW, row)


def _doctor_lines(anchor, lines):
    text = _epic()
    out = []
    for line in text.split("\n"):
        out.extend(lines if line == anchor else [line])
    return "\n".join(out)


@pytest.mark.parametrize("shape", sorted(BAD_ROWS))
def test_a_non_canonical_row_fails(shape):
    assert canonical_problems(_doctor_row(BAD_ROWS[shape])) != []


@pytest.mark.parametrize("shape", sorted(BAD_LINES))
def test_a_non_canonical_line_fails(shape):
    if shape == "rewards inline":
        text = _epic()
        start, end = text.index("\trewards: ["), text.index("\t]\n") + 3
        text = text[:start] + "\trewards: [ " + " ".join(l.strip() for l in text[start:end].split("\n")[1:-2]) + " ]\n" + text[end:]
    else:
        text = _doctor_lines(*BAD_LINES[shape])
    assert canonical_problems(text) != []


def test_the_real_tables_are_canonical():
    tables = {p.name: canonical_problems(p.read_text()) for p in sorted((QUESTS / "reward_tables").glob("*.snbt"))}
    assert len(tables) == 5 and tables == {name: [] for name in tables}
    assert sum(len(ENTRY.findall(p.read_text())) for p in (QUESTS / "reward_tables").glob("*.snbt")) == 41


def test_comment_quote_and_escape_lines_name_their_reason():
    # the template alone also rejects these; the line scan names why, so a failure says what FTB Quests would do
    reasons = {shape: [why for _, why in canonical_problems(_doctor_lines(*BAD_LINES[shape]))] for shape in
               ("// comment line", "# comment line")}
    assert all(any(w.startswith("comment line") for w in ws) for ws in reasons.values()), reasons
    assert any(w == "single quote" for _, w in canonical_problems(_doctor_row(BAD_ROWS["single-quoted id"])))
    assert any(w == "backslash escape" for _, w in canonical_problems(_doctor_row(BAD_ROWS["unknown escape, dropped by FTB"])))


# Round 3, M2: FTB Quests re-saves a table with drops on several lines and each row across several lines, as the copies
# under .run/server/config/ftbquests/quests/reward_tables show; the template names the way back.
FTB_RESAVED_DROPS = ("\t\tdrops: { boss: 0 monster: 0 passive: 0 }",
                     ["\t\tdrops: {", "\t\t\tboss: 0", "\t\t\tmonster: 0", "\t\t\tpassive: 0", "\t\t}"])
HINT = ("FTB's own re-saved form (multi-line drops, reward-level count) is not accepted; write one row per line as the "
        "shipped tables do")


def test_an_ftb_resaved_table_fails_with_the_way_back():
    problems = canonical_problems(_doctor_lines(*FTB_RESAVED_DROPS))
    assert problems and all(why.endswith(HINT) for _, why in problems if why.startswith("expected the ")), problems
    assert any(why.startswith("expected the ") for _, why in problems)


def _tree(tmp_path, tables):
    """A copy of the questbook's chapters with `tables` ({filename: text}) as its reward_tables/; for main()."""
    root = tmp_path / "quests"
    shutil.copytree(QUESTS / "chapters", root / "chapters")
    shutil.copy(QUESTS / "data.snbt", root / "data.snbt")
    (root / "reward_tables").mkdir()
    for name, text in tables.items():
        (root / "reward_tables" / name).write_text(text)
    return root


def _real_tables():
    return {p.name: p.read_text() for p in (QUESTS / "reward_tables").glob("*.snbt")}


# The end of main()'s summary line on the shipped tables (round 3, M4: the node counts are Task 11's to change, so the
# tests here pin only the reward-table part, the exit code and the failure lines).
CLEAN = "; reward tables: 5, forbidden items: 0"


def _main(monkeypatch, capsys, root):
    monkeypatch.setattr(check_quests, "QUESTS", root)
    rc = check_quests.main(["--tiers", "0,1,2,3,4"])
    return rc, capsys.readouterr().out.splitlines()


def test_main_prints_each_non_canonical_line_and_fails(tmp_path, monkeypatch, capsys):
    bad = _doctor_row(BAD_ROWS["command reward"])
    line = bad.split("\n").index(BAD_ROWS["command reward"]) + 1
    rc, out = _main(monkeypatch, capsys, _tree(tmp_path, {"zz_bag.snbt": bad}))
    assert rc == 1
    assert out[0].endswith("; reward tables: 1, forbidden items: 0")
    assert any(o.strip().startswith(f"NON-CANONICAL zz_bag.snbt:{line}: ") for o in out), out


def test_main_output_is_one_line_when_clean(tmp_path, monkeypatch, capsys):
    rc, out = _main(monkeypatch, capsys, _tree(tmp_path, _real_tables()))
    assert rc == 0 and len(out) == 1 and out[0].endswith(CLEAN), out



# ---- R2 (D133): FORBIDDEN covers one-step forms. Each wildcard alternative gets a registered id that is not an ingot, and
# each precursor gets the dump recipe (.run/server/kubejs/exported/recipes.json) that turns it into a forbidden id in one
# step with one distinct ingredient. Lang keys are in the jar's assets/<ns>/lang/en_us.json; the mysticalagriculture
# seeds and essences have no lang key of their own and are members of #mysticalagriculture:seeds and
# #mysticalagriculture:essences in item_tag_members.json.
WIDENED = [
    "allthemodium:raw_unobtainium",              # item.allthemodium.raw_unobtainium (allthemodium-3.0.1_mc_1.21.1.jar)
    "ad_astra:etrium_plate",                     # item.ad_astra.etrium_plate (adastra-1.21.1-1.16.25-neoforge.jar)
    "ad_astra:raw_desh",                         # ad_astra:smelting/desh_ingot_from_smelting_raw_desh
    "ad_astra:moon_desh_ore",                    # ad_astra:smelting/desh_ingot_from_smelting_moon_desh_ore
    "ad_astra:raw_calorite_block",               # ad_astra:raw_calorite (shapeless, 9 raw_calorite)
    "allthemodium:piglich_heart_block",          # allthemodium:piglich_heart (shapeless, 9 piglich_heart)
    "cataclysm:curved_azure_seastone_scylla_1",  # block.cataclysm.curved_azure_seastone_scylla_1: a digit in the id
    "twilightforest:knightmetal_block",          # block.twilightforest.knightmetal_block (twilightforest-1.21.1-4.8.3345)
    "undergarden:forgotten_nugget",              # item.undergarden.forgotten_nugget (The_Undergarden-1.21.1-0.9.6.jar)
    "ad_astra:ice_shard",                        # item.ad_astra.ice_shard (a tier-6 Etrium input, spec §6)
    "ad_astra:moon_ice_shard_ore",               # ad_astra:smelting/ice_shard_from_smelting_moon_ice_shard_ore
    "allthemodium:soul_lava_bucket",             # item.allthemodium.soul_lava_bucket
    "industrialforegoing:machine_frame_advanced",  # block.industrialforegoing.machine_frame_advanced
    "industrialforegoing:machine_frame_supreme",   # block.industrialforegoing.machine_frame_supreme
    "twilightforest:armor_shard",                # x9: twilightforest:material/armor_shard_cluster
    "twilightforest:armor_shard_cluster",        # twilightforest:material/smelted_knightmetal_ingot
    "mysticalagriculture:knightmetal_seeds",     # mysticalagriculture:seed/reprocessor/knightmetal -> knightmetal_essence
    "mysticalagriculture:knightmetal_essence",   # mysticalagriculture:essence/twilightforest/knightmetal_ingot
    "eternal_starlight:unrealium_sword",         # item.eternal_starlight.unrealium_sword (eternalstarlight-0.9.0+1.21.1+neoforge)
    "eternal_starlight:oxidized_golem_steel_ingot",   # golem_steel_ingot_smelting_from_oxidized_golem_steel_ingot
    "eternal_starlight:oxidized_golem_steel_nugget",  # golem_steel_nugget_smelting_from_oxidized_golem_steel_nugget
    "eternal_starlight:waxed_golem_steel_block",      # block.eternal_starlight.waxed_golem_steel_block
    "mysticalagriculture:dragon_egg_seeds",      # mysticalagriculture:seed/reprocessor/dragon_egg -> dragon_egg_essence
    "mysticalagriculture:dragon_egg_essence",    # x9: mysticalagradditions:essence/dragon_egg_chunk
    "mysticalagradditions:dragon_egg_chunk",     # x3: mysticalagradditions:dragon_egg -> minecraft:dragon_egg
]
# The key alternative names five ids and V02_FORBIDDEN pins other_key only; these are the other v0.3 key items
# (kubejs/startup_scripts/items.js event.create).
KUBEJS_KEYS = ["kubejs:end_focus", "kubejs:astral_focus", "kubejs:confluence_catalyst"]


def test_forbidden_catches_one_step_forms_and_every_key():
    assert [i for i in WIDENED + KUBEJS_KEYS if forbidden_in_table(_row(i)) != [i]] == []


# Not registered: each wildcard alternative's wildcard is ENTRY's whole id-path grammar ([a-z0-9_./-]), not [a-z_], so an id
# with a digit, dot, slash or hyphen is caught too (cataclysm:curved_azure_seastone_scylla_1 above is the one registered case).
GRAMMAR = ["allthemodium:unobtainium_2", "ad_astra:desh/plate", "allthemodium:piglich_heart.2", "cataclysm:x-2",
           "twilightforest:knightmetal_2", "undergarden:forgotten_2", "eternal_starlight:golem_steel_2", "ad_astra:ice_shard_2",
           "allthemodium:soul_lava_2", "twilightforest:armor_shard_2", "ad_astra:2_etrium"]


def test_forbidden_wildcards_read_the_whole_id_grammar():
    assert [i for i in GRAMMAR if forbidden_in_table(_row(i)) != [i]] == []


def test_both_lists_match_only_a_whole_quoted_id():
    # registered ids that start with an excluded one (item.ae2.logic_processor_press, appliedenergistics2-19.2.17.jar;
    # item.industrialforegoing.pink_slime_ingot, industrialforegoing-1.21-3.6.39.jar), and unregistered extensions on
    # either side of a forbidden one
    assert [i for i in ("ae2:logic_processor_press", "industrialforegoing:pink_slime_ingot") if excluded_in_table(_row(i))] == []
    for longer in ("minecraft:dragon_egg_x", "xminecraft:dragon_egg"):   # dragon_egg is in both lists
        assert forbidden_in_table(_row(longer)) == [] and excluded_in_table(_row(longer)) == [], longer



# ---- R3 (D133): spec §10's excluded set, phrase by phrase. Each item id has a lang key in its jar's
# assets/<ns>/lang/en_us.json (check_quests.EXCLUDED_IDS names them) or is a kubejs/startup_scripts/items.js event.create();
# a tag in brackets is the spec's own ingredient, whose members in .run/server/kubejs/exported/item_tag_members.json are
# exactly the ids listed. The two fluids are named by the T5.2 and X5.2 bodies in .run/server/kubejs/exported/recipes.json
# (industrialforegoing:dissolution_chamber/supreme_machine_frame, confluence:tier5/unobtainium_vibranium_alloy_ingot).
# The two family phrases (fluix, QIO) name every member of their narrowed alternatives (round 3, I6).
SPEC_EXCLUDED = {
    "the End Focus": ["kubejs:end_focus"],
    "Vibranium": ["allthemodium:vibranium_ingot"],                                          # [#c:ingots/vibranium]
    "the advanced and Supreme frames": ["industrialforegoing:machine_frame_advanced",       # [#industrialforegoing:
                                        "industrialforegoing:machine_frame_supreme"],       #  machine_frame/advanced]
    "Essence of the Bees": ["the_bumblezone:essence_of_the_bees"],
    "the dragon egg": ["minecraft:dragon_egg"],
    "elite and ultimate circuits": ["mekanism:elite_control_circuit",                       # [#c:circuits/elite]
                                    "mekanism:ultimate_control_circuit"],                   # [#c:circuits/ultimate]
    "atomic alloy": ["mekanism:alloy_atomic"],                                              # [#mekanism:alloys/atomic]
    "Unobtainium": ["allthemodium:unobtainium_ingot", "allthemodium:unobtainium_block"],    # [#c:ingots/, storage_blocks/]
    "the Wilden Tribute": ["ars_nouveau:wilden_tribute"],
    "plastic": ["industrialforegoing:plastic"],                                             # [#c:plastics]
    "nitro crystals and nitro crystal blocks": ["powah:crystal_nitro", "powah:nitro_crystal_block"],
    "ether gas": ["industrialforegoing:ether_gas", "industrialforegoing:ether_gas_bucket"],  # the T5.2 fluid and its bucket
    "Allthemodium": ["allthemodium:allthemodium_ingot"],                                    # [#c:ingots/allthemodium]
    "the Piglich heart": ["allthemodium:piglich_heart"],
    "the four elemental essences": ["ars_nouveau:air_essence", "ars_nouveau:earth_essence",  # [#confluence:ars_essences]
                                    "ars_nouveau:water_essence", "ars_nouveau:fire_essence"],
    "pink slime": ["industrialforegoing:pink_slime"],
    "soul lava": ["allthemodium:soul_lava", "allthemodium:soul_lava_bucket"],                # the X5.2 fluid and its bucket
    "the three ATM alloys": ["allthemodium:unobtainium_allthemodium_alloy_ingot", "allthemodium:vibranium_allthemodium_alloy_ingot",
                             "allthemodium:unobtainium_vibranium_alloy_ingot"],
    "HDPE sheet": ["mekanism:hdpe_sheet"],
    "knightmetal": ["twilightforest:knightmetal_ingot"],                                    # [#c:ingots/knightmetal]
    "fluix": ["ae2:fluix_crystal", "ae2:fluix_glass_cable", "ae2:fluix_block"],          # S5.2, S5.3/S6.2; 4 crystals
    "the forgotten ingot": ["undergarden:forgotten_ingot"],
    "AE2 processors and cores": ["ae2:engineering_processor", "ae2:logic_processor", "ae2:calculation_processor",
                                 "ae2:annihilation_core", "ae2:formation_core"],
    "sky stone": ["ae2:smooth_sky_stone_block", "ae2:sky_stone_block"],
    "the inventory connector": ["toms_storage:inventory_connector"],
    "QIO parts and the QIO dashboard": ["mekanism:qio_drive_array", "mekanism:qio_importer", "mekanism:qio_exporter",
                                        "mekanism:qio_dashboard"],                          # [S3.1]; spec §5, S5.3
    "steel plates and blocks": ["ad_astra:steel_plate",                                     # [#ad_astra:steel_plates]
                                "ad_astra:steel_block", "mekanism:block_steel"],            # [#ad_astra:steel_blocks]
    "the elytra": ["minecraft:elytra"],
    "the electric pump": ["mekanism:electric_pump"],
    "the engine frame": ["ad_astra:engine_frame"],
    "the fan": ["ad_astra:fan"],
    "desh": ["ad_astra:desh_ingot"],                                                        # [#c:ingots/desh]
    "ostrum": ["ad_astra:ostrum_ingot"],                                                    # [#c:ingots/ostrum]
    "calorite": ["ad_astra:calorite_ingot"],                                                # [#c:ingots/calorite]
    "the ice shard": ["ad_astra:ice_shard"],
    "Etrium": ["ad_astra:etrium_ingot"],
    "the divine soulshard": ["irons_spellbooks:divine_soulshard"],
    "the Mercury and Glacio shards": ["kubejs:mercury_shard", "kubejs:glacio_shard"],
    "fluix pearls": ["ae2:fluix_pearl"],
    "quartz fiber": ["ae2:quartz_fiber"],
    "Unrealium": ["eternal_starlight:unrealium_ingot"],                                     # [#c:ingots/unrealium]
}
# Registered items next to an excluded one that stay allowed: the lower circuits and alloys, steel ingots, the printed
# (uncooked) processors, certus quartz, the shipped bags' powah crystal, and the four Epic-only entries.
EXCLUDED_NEAR_MISSES = [
    "mekanism:basic_control_circuit", "mekanism:advanced_control_circuit", "mekanism:alloy_infused",
    "mekanism:alloy_reinforced", "mekanism:ingot_steel", "ad_astra:steel_ingot", "ad_astra:steel_rod",
    "ae2:printed_logic_processor", "ae2:printed_engineering_processor", "ae2:certus_quartz_crystal",
    "industrialforegoing:machine_frame_pity", "industrialforegoing:machine_frame_simple", "powah:crystal_spirited",
    "ars_nouveau:source_gem_block", "irons_spellbooks:arcane_essence", "mekanism:ingot_refined_obsidian",
]


# Round 3, I6: the 16 coloured AE2 glass cables (the other members of #ae2:glass_cable in item_tag_members.json) wash back
# into the fluix one: ae2:network/cables/glass_fluix_clean takes a #ae2:glass_cable member and a #ae2:can_remove_color
# member (water bucket or snowball), two ingredients, so the precursor closure does not reach them.
COLOURED_GLASS_CABLES = [f"ae2:{c}_glass_cable" for c in (
    "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray", "light_gray", "cyan", "purple", "blue",
    "brown", "green", "red", "black")]
# The registered rest of the two families, which no gate recipe takes (appliedenergistics2-19.2.17.jar and
# Mekanism-1.21.1-10.7.19.85.jar lang keys item.ae2.fluix_*, block.ae2.fluix_*, item.mekanism.qio_*, block.mekanism.qio_*):
# EXCLUDED leaves them to tools/bag_banned.json, which bars any of them that is a tier-5/6 input or a precursor.
FAMILY_REST = ["ae2:fluix_dust", "ae2:fluix_slab", "ae2:fluix_stairs", "ae2:fluix_wall", "ae2:fluix_axe", "ae2:fluix_hoe",
               "ae2:fluix_pickaxe", "ae2:fluix_shovel", "ae2:fluix_sword", "ae2:fluix_covered_cable",
               "ae2:fluix_covered_dense_cable", "ae2:fluix_smart_cable", "ae2:fluix_smart_dense_cable",
               "ae2:fluix_upgrade_smithing_template", "mekanism:qio_drive_base", "mekanism:qio_drive_hyper_dense",
               "mekanism:qio_drive_supermassive", "mekanism:qio_drive_time_dilating", "mekanism:qio_redstone_adapter"]


def test_excluded_holds_the_coloured_glass_cables():
    assert [i for i in COLOURED_GLASS_CABLES if excluded_in_table(_row(i)) != [i]] == []


def test_excluded_spares_the_family_rest():
    assert [i for i in FAMILY_REST if excluded_in_table(_row(i))] == []


def test_excluded_resolves_every_phrase_of_spec_10():
    ids = [i for group in SPEC_EXCLUDED.values() for i in group]
    assert len(SPEC_EXCLUDED) == 41   # the phrases of spec §10's excluded-set paragraph, in order
    assert [i for i in ids if excluded_in_table(_row(i)) != [i]] == []


def test_excluded_spares_near_misses():
    assert [i for i in EXCLUDED_NEAR_MISSES if excluded_in_table(_row(i))] == []


def test_legendary_allowed_is_the_two_tier5_inputs_it_holds():
    # spec §10 "A tier-5 input may appear in the tier-6 bag" (D89/D94, restated in D126); test_bag_collisions.py checks
    # that these are exactly Legendary's tier-5 inputs in the recipe dump
    assert LEGENDARY_ALLOWED == {"industrialforegoing:plastic", "mekanism:elite_control_circuit"}
    legendary = (QUESTS / "reward_tables" / "legendary_bag.snbt").read_text()
    assert sorted(excluded_in_table(legendary)) == sorted(LEGENDARY_ALLOWED)
    epic = (QUESTS / "reward_tables" / "epic_bag.snbt").read_text()
    assert excluded_in_table(epic) == []


COLOURS = ("white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray", "light_gray", "cyan", "purple",
           "blue", "brown", "green", "red", "black")


def test_base_materials_are_spec_10s_list_plus_wool_and_glass_panes():
    # round 4, B1: spec §10 ¶1 "Base vanilla materials (iron, copper, pistons, buckets, furnaces, crafting tables) are not
    # gate inputs, as in D89", read as the six items: iron and copper are the ingots, with no block, nugget or raw form
    assert check_quests.SPEC_BASE_MATERIALS == {"minecraft:iron_ingot", "minecraft:copper_ingot", "minecraft:piston",
                                                "minecraft:bucket", "minecraft:furnace", "minecraft:crafting_table"}
    # round 5: plus the glass pane and the 16 vanilla wools (orchestrator interpretation, D133); test_bag_collisions.py
    # pins the wools against #minecraft:wool's minecraft: members in the dump
    assert check_quests.VANILLA_WOOL == {f"minecraft:{c}_wool" for c in COLOURS}
    assert check_quests.BASE_MATERIALS == (check_quests.SPEC_BASE_MATERIALS | {"minecraft:glass_pane"}
                                           | check_quests.VANILLA_WOOL)
    assert len(check_quests.BASE_MATERIALS) == 23
    assert not any(check_quests.BANNED.fullmatch(i) for i in check_quests.BASE_MATERIALS)


def _swap(text, old_item, new_item):
    assert text.count(f'id: "{old_item}"') == 1
    return text.replace(f'id: "{old_item}"', f'id: "{new_item}"')


def test_main_prints_each_excluded_hit_and_spares_legendarys_allowance(tmp_path, monkeypatch, capsys):
    tables = _real_tables()
    tables["legendary_bag.snbt"] = _swap(tables["legendary_bag.snbt"], "minecraft:diamond_block", "mekanism:alloy_atomic")
    tables["epic_bag.snbt"] = _swap(tables["epic_bag.snbt"], "minecraft:diamond", "industrialforegoing:plastic")
    rc, out = _main(monkeypatch, capsys, _tree(tmp_path, tables))
    assert rc == 1
    assert out[0].endswith(CLEAN)
    assert sorted(o.strip() for o in out[1:]) == ["EXCLUDED epic_bag: industrialforegoing:plastic",
                                                  "EXCLUDED legendary_bag: mekanism:alloy_atomic"]



# ---- R5 (D133): every object id FTB Quests reads from the questbook is defined once. A definition is `id: "<16 hex>"` at any
# depth (chapter groups, chapters, quests, tasks, rewards, reward tables and their entries); a reference (dependencies,
# table_id) is written another way. Ids are scaffold_chapter.quest_id / D63/D68 patterns, so a clash would be a copy error.
HEX_ID = re.compile(r'(?<![A-Za-z0-9_])id: "([0-9A-F]{16})"')


def _hex_definitions(root):
    return [(p.relative_to(root).as_posix(), m.group(1)) for p in sorted(root.rglob("*.snbt"))
            for m in HEX_ID.finditer(p.read_text())]


def _duplicates(defs):
    seen, dup = {}, []
    for where, i in defs:
        if i in seen:
            dup.append((i, seen[i], where))
        seen.setdefault(i, where)
    return dup


def test_every_hex_id_definition_is_unique():
    defs = _hex_definitions(QUESTS)
    assert len(defs) >= 283 and _duplicates(defs) == []   # 283 when Task 10 measured: groups 3, chapters 234, tables 46


def test_a_duplicated_hex_id_is_found(tmp_path):
    shutil.copytree(QUESTS, tmp_path / "quests")
    epic = tmp_path / "quests" / "reward_tables" / "epic_bag.snbt"
    epic.write_text(epic.read_text().replace('id: "0C0F1B0000000401"', 'id: "0C0F1B0000000301"'))   # a Rare entry's id
    assert _duplicates(_hex_definitions(tmp_path / "quests")) == [
        ("0C0F1B0000000301", "reward_tables/epic_bag.snbt", "reward_tables/rare_bag.snbt")]


# ---- R6 (D133): a chapter's quest rewards may not pay out a FORBIDDEN or EXCLUDED id either. Measured before the check
# went in: 73 rewards arrays across the 11 chapters, 70 item rewards (all kubejs:coin) and loot-table rewards, 0 hits.
# Only `rewards:` arrays are read; a task may name any item.
QUEST = ('\t\t{\n\t\t\tid: "0C0F1B00000099A1"\n\t\t\trewards: [{ id: "0C0F1B00000099A2" item: { count: 15, id: "kubejs:coin" } '
         'type: "item" }, {REWARD}]\n\t\t\ttasks: [{ id: "0C0F1B00000099A3" item: { count: 1, id: "minecraft:dragon_egg" } '
         'type: "item" }]\n\t\t}\n')


def test_chapter_reward_hits_reads_rewards_not_tasks():
    coin = '{ id: "0C0F1B00000099A4" item: { count: 1, id: "kubejs:coin" } type: "item" }'
    assert chapter_reward_hits(QUEST.replace("{REWARD}", coin)) == []
    egg = coin.replace("kubejs:coin", "minecraft:dragon_egg")
    assert chapter_reward_hits(QUEST.replace("{REWARD}", egg)) == ["minecraft:dragon_egg"]
    plastic = coin.replace("kubejs:coin", "industrialforegoing:plastic")   # excluded, and a chapter is no Legendary bag
    assert chapter_reward_hits(QUEST.replace("{REWARD}", plastic)) == ["industrialforegoing:plastic"]
    multi = QUEST.replace("rewards: [{", "rewards: [\n\t\t\t\t{").replace("{REWARD}]", "\n\t\t\t\t" + egg + "\n\t\t\t]")
    assert chapter_reward_hits(multi) == ["minecraft:dragon_egg"]   # FTB Quests may write the array one entry per line
    # round 3 (repro c8): a rewards array inside another one (a table_data table's) is part of the outer array, so its ids
    # are read once
    nested = coin.replace('item: { count: 1, id: "kubejs:coin" } type: "item"',
                          'table_data: { rewards: [{ item: { count: 1, id: "minecraft:dragon_egg" } }] } type: "random"')
    assert chapter_reward_hits(QUEST.replace("{REWARD}", nested)) == ["minecraft:dragon_egg"]


def test_no_chapter_rewards_a_forbidden_or_excluded_id():
    chapters = sorted((QUESTS / "chapters").glob("*.snbt"))
    assert {p.name: chapter_reward_hits(p.read_text()) for p in chapters} == {p.name: [] for p in chapters}


def test_main_prints_each_chapter_reward_hit(tmp_path, monkeypatch, capsys):
    root = _tree(tmp_path, _real_tables())
    chapter = sorted((root / "chapters").glob("*.snbt"))[0]
    text = chapter.read_text()
    assert text.count('id: "kubejs:coin" } type: "item"') >= 1
    chapter.write_text(text.replace('id: "kubejs:coin" } type: "item"', 'id: "ad_astra:raw_desh" } type: "item"', 1))
    rc, out = _main(monkeypatch, capsys, root)
    assert rc == 1
    assert out[0].endswith(CLEAN) and out[1:] == [f"  CHAPTER REWARD {chapter.name}: ad_astra:raw_desh"]


# ---- round 3, I3: tools/bag_banned.json holds the recipe dump's verdicts, so a clone with no dump still fails them ----
def test_main_fails_a_gated_output_with_no_dump(tmp_path, monkeypatch, capsys):
    tables = _real_tables()
    tables["rare_bag.snbt"] = _swap(tables["rare_bag.snbt"], "mekanism:ingot_steel", "ae2:controller")
    rc, out = _main(monkeypatch, capsys, _tree(tmp_path, tables))
    assert rc == 1 and out[1:] == ["  COLLISION rare_bag: ae2:controller (gated output)"]


def test_main_fails_with_no_snapshot(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check_quests, "SNAPSHOT", tmp_path / "bag_banned.json")
    rc, out = _main(monkeypatch, capsys, _tree(tmp_path, _real_tables()))
    assert rc == 1 and out[1:] == [f"  NO SNAPSHOT {tmp_path / 'bag_banned.json'}: regenerate with "
                                   f"`{check_quests.SNAPSHOT_COMMAND}` (from pack/, after a boot)"]


def test_the_snapshot_holds_what_only_the_dump_guarded():
    snap = check_quests.load_snapshot(check_quests.SNAPSHOT)
    # S5.3's monitor and the X5.3 Digital Miner's default inputs, which spec §10's list omits (round 3, M5)
    for i in ("ae2:semi_dark_monitor", "mekanism:logistical_sorter", "mekanism:robit", "mekanism:steel_casing",
              "mekanism:teleportation_core"):
        assert "in5" in check_quests.snapshot_codes(i, snap), i
    assert "gated" in check_quests.snapshot_codes("ae2:controller", snap)
    assert check_quests.snapshot_codes("kubejs:coin", snap) == []



# ---- round 3, I1/I2: chapter files and data.snbt. Measured before the check went in, over the 11 chapters: 73 `rewards:`
# arrays, each on one line `\t\t\trewards: [...]` in one of three shapes (one coin item reward: 66; a coin item reward then a
# loot reward: 4; one loot reward: 3); reward types item (70) and loot (7), and no other; every table_id is a reward table's
# id (868942939919745025-27); no chapter holds a `'`, a `\`, a // or # line, or table_data. data.snbt has no
# emergency_items. FTB Quests reads the chapters with ftb-library's SNBT parser, so each shape below pays out a dragon egg or
# a gated item; the reviewers ran each one through it (scratchpad t10-verify2/full/chapters.py, snbt/P2.java).
INTRO = "intro.snbt"
OLD_REWARD = '\t\t\trewards: [{ id: "246094B7FA79D4B5" item: { count: 3, id: "kubejs:coin" } type: "item" }]'
T3 = "\t\t\t"
EGG = 'item: { count: 1, id: "minecraft:dragon_egg" }'
CHAPTER_SHAPES = {   # name: (the rewards line(s) in place of OLD_REWARD, the reason main() prints for its first problem)
    "c1 single-quoted id": (T3 + "rewards: [{ id: \"246094B7FA79D4B5\" item: { count: 1, id: 'minecraft:dragon_egg' } "
                            "type: \"item\" }]", "single quote"),
    "c2 no namespace": (T3 + 'rewards: [{ id: "246094B7FA79D4B5" item: { count: 1, id: "dragon_egg" } type: "item" }]',
                        "not a canonical rewards line"),
    "c3 unknown escape": (T3 + 'rewards: [{ id: "246094B7FA79D4B5" item: { count: 1, id: "minecraft:dragon_egg\\z" } '
                          'type: "item" }]', "backslash escape"),
    "c4 command reward": (T3 + 'rewards: [{ command: "/give @p minecraft:dragon_egg 1" id: "246094B7FA79D4B5" '
                          'type: "command" }]', "not a canonical rewards line"),
    "c5 quoted rewards key": (T3 + '"rewards": [{ id: "246094B7FA79D4B5" ' + EGG + ' type: "item" }]',
                              "not a canonical rewards line"),
    "c6 rewards:[": (T3 + 'rewards:[{ id: "246094B7FA79D4B5" ' + EGG + ' type: "item" }]', "not a canonical rewards line"),
    "c7 comment line in a multi-line array": (T3 + "rewards: [\n" + T3 + "\t// ]\n" + T3 + '\t{ id: "246094B7FA79D4B5" ' + EGG
                                              + ' type: "item" }\n' + T3 + "]", "not a canonical rewards line"),
    "c8 table_data, table_id 0": (T3 + 'rewards: [{ id: "246094B7FA79D4B5" table_data: { rewards: [{ item: { count: 1, '
                                  'id: "ae2:controller" } }] } type: "random" }]', "not a canonical rewards line"),
    "c9 table_data, dangling table_id": (T3 + 'rewards: [{ id: "246094B7FA79D4B5" table_data: { rewards: [{ item: { '
                                         'count: 1, id: "ad_astra:rocket_nose_cone" } }] } table_id: 1234L type: "loot" }]',
                                         "not a canonical rewards line"),
    "custom reward": (T3 + 'rewards: [{ id: "246094B7FA79D4B5" type: "custom" }]', "not a canonical rewards line"),
    "loot reward naming no table": (T3 + 'rewards: [{ id: "246094B7FA79D4B5" table_id: 1234L type: "loot" }]',
                                    "table_id 1234 is not a reward table's id"),
}
# Every reason each shape must produce somewhere (I1: table_data and a table_id that names no table; I2: the type).
CHAPTER_REASONS = {"c4 command reward": 'reward type "command"', "custom reward": 'reward type "custom"',
                   "c7 comment line in a multi-line array": "comment line", "c8 table_data, table_id 0": "table_data",
                   "c9 table_data, dangling table_id": "table_id 1234 is not a reward table's id"}


def _chapter_tree(tmp_path, new):
    root = _tree(tmp_path, _real_tables())
    intro = root / "chapters" / INTRO
    text = intro.read_text()
    assert text.count(OLD_REWARD) == 1
    intro.write_text(text.replace(OLD_REWARD, new))
    return root, text.split("\n").index(OLD_REWARD) + 1


@pytest.mark.parametrize("shape", sorted(CHAPTER_SHAPES))
def test_a_chapter_reward_shape_fails(tmp_path, monkeypatch, capsys, shape):
    new, reason = CHAPTER_SHAPES[shape]
    root, line = _chapter_tree(tmp_path, new)
    rc, out = _main(monkeypatch, capsys, root)
    assert rc == 1 and out[1].startswith(f"  NON-CANONICAL {INTRO}:{line}: {reason}"), out
    if shape in CHAPTER_REASONS:
        assert any(CHAPTER_REASONS[shape] in o for o in out[1:]), out


@pytest.mark.parametrize("item,line", [("minecraft:dragon_egg", f"  CHAPTER REWARD {INTRO}: minecraft:dragon_egg"),
                                       ("ae2:controller", f"  CHAPTER REWARD {INTRO}: ae2:controller (gated output)")])
def test_a_canonical_chapter_reward_of_a_banned_or_gated_id_fails(tmp_path, monkeypatch, capsys, item, line):
    # c0 (a FORBIDDEN and EXCLUDED id) and c10 (a gated output, in tools/bag_banned.json only)
    root, _ = _chapter_tree(tmp_path, OLD_REWARD.replace("count: 3, id: \"kubejs:coin\"", f'count: 1, id: "{item}"'))
    rc, out = _main(monkeypatch, capsys, root)
    assert rc == 1 and out[1:] == [line]


def test_emergency_items_in_data_snbt_fail(tmp_path, monkeypatch, capsys):
    # e1: BaseQuestFile reads data.snbt's emergency_items into its emergencyItems list, which GetEmergencyItemsMessage hands
    # out (ftb-quests-neoforge-2101.1.35.jar, javap -p -c); the reviewers' P3.java read one dragon egg back
    root = _tree(tmp_path, _real_tables())
    data = root / "data.snbt"
    text = data.read_text()
    assert text.count("\temergency_items_cooldown: 300\n") == 1
    data.write_text(text.replace("\temergency_items_cooldown: 300\n",
                                 '\temergency_items: [{ count: 1, id: "minecraft:dragon_egg" }]\n\temergency_items_cooldown: 300\n'))
    line = data.read_text().split("\n").index('\temergency_items: [{ count: 1, id: "minecraft:dragon_egg" }]') + 1
    rc, out = _main(monkeypatch, capsys, root)
    assert rc == 1 and out[1:] == [f"  NON-CANONICAL data.snbt:{line}: emergency_items (FTB Quests hands these items out)"]


def test_the_real_chapters_and_data_pass():
    longs = check_quests.table_longs(sorted((QUESTS / "reward_tables").glob("*.snbt")))
    assert {p.name: check_quests.chapter_problems(p.read_text(), longs) for p in (QUESTS / "chapters").glob("*.snbt")} == {
        p.name: [] for p in (QUESTS / "chapters").glob("*.snbt")}
    assert check_quests.data_problems((QUESTS / "data.snbt").read_text()) == []


# ---- Dependency mirror, both ways (v0.3 Task 11 fix round 1, B2/B3). "deps: 0 mismatched" used to mean only that each
# tree ref sits in its quest's block; the Task 11 gates lens showed an extra dep (probe A), a dropped helper dep (B) and a
# dangling dep id (E) all passed it. Now a tree-node quest's dependencies must equal its gate refs that have a quest (plus
# check_quests.TREE_DEP_EXCEPTIONS), a pinned helper's must equal check_quests.HELPER_DEPS, and every dependency id must
# name a quest. The probes edit a copy of the shipped chapters and run main() over tiers 0-6. Each first reads the copy's
# clean summary line and expects it back with only the dep count changed: node counts are not pinned here (see CLEAN).
ALL = "0,1,2,3,4,5,6"


def _main_tiers(monkeypatch, capsys, root, tiers):
    monkeypatch.setattr(check_quests, "QUESTS", root)
    rc = check_quests.main(["--tiers", tiers])
    return rc, capsys.readouterr().out.splitlines()


def _clean(monkeypatch, capsys, root, tiers):
    """main()'s one summary line on an unedited copy: exit 0, no missing node, no dep mismatch, the shipped tables."""
    rc, out = _main_tiers(monkeypatch, capsys, root, tiers)
    assert rc == 0 and len(out) == 1 and ", 0 missing; deps: 0 mismatched; " in out[0] and out[0].endswith(CLEAN), out
    return out[0]


def _failing(clean, n):
    """The clean summary line with `n` dependency mismatches."""
    assert clean.count("; deps: 0 mismatched;") == 1
    return clean.replace("; deps: 0 mismatched;", f"; deps: {n} mismatched;")


def _edit_deps(root, chapter, node, edit):
    """Apply `edit` to `node`'s `dependencies:` line in the copy, inside its own quest block (keys are alphabetical, so
    the line sits between the block's opening brace and its `id:`); an empty result drops the line."""
    path = root / "chapters" / chapter
    text = path.read_text()
    assert text.count(f'\t\t\tid: "{quest_id(node)}"\n') == 1
    idx = text.index(f'\t\t\tid: "{quest_id(node)}"\n')
    start = text.rindex("\n\t\t{\n", 0, idx)
    head = text[start:idx]
    line = next(l for l in head.split("\n") if l.startswith("\t\t\tdependencies: "))
    new_head = head.replace(line + "\n", edit(line) + "\n" if edit(line) else "")
    assert new_head != head
    path.write_text(text[:start] + new_head + text[idx:])


def _probe(tmp_path, monkeypatch, capsys, chapter, node, edit, tiers=ALL):
    """(clean summary line, exit code, output) of main() on a copy of the shipped chapters, before and after the edit."""
    root = _tree(tmp_path, _real_tables())
    clean = _clean(monkeypatch, capsys, root, tiers)
    _edit_deps(root, chapter, node, edit)
    rc, out = _main_tiers(monkeypatch, capsys, root, tiers)
    return clean, rc, out


def test_the_shipped_book_is_clean_at_tiers_0_6_and_0_4(tmp_path, monkeypatch, capsys):
    root = _tree(tmp_path, _real_tables())
    _clean(monkeypatch, capsys, root, ALL)
    _clean(monkeypatch, capsys, root, "0,1,2,3,4")


def test_probe_a_an_extra_tree_dep_fails(tmp_path, monkeypatch, capsys):
    # D6.8 (Glacio) gates on [D6.6] only; giving it D6.3 as well is an extra dependency
    clean, rc, out = _probe(tmp_path, monkeypatch, capsys, "space.snbt", "D6.8",
                            lambda l: l[:-1] + f', "{quest_id("D6.3")}"]')
    assert rc == 1 and out == [_failing(clean, 1), "  EXTRA DEP D6.8: D6.3"], out


def test_probe_b_a_dropped_helper_dep_fails(tmp_path, monkeypatch, capsys):
    # ES.2 (Starlight Golem) is pinned to [D6.10] by D135; drop its only dependency
    clean, rc, out = _probe(tmp_path, monkeypatch, capsys, "starlight.snbt", "ES.2", lambda l: "")
    assert rc == 1 and out == [_failing(clean, 1), "  DEP ES.2 should depend on D6.10"], out


def test_probe_b2_an_extra_helper_dep_fails(tmp_path, monkeypatch, capsys):
    clean, rc, out = _probe(tmp_path, monkeypatch, capsys, "starlight.snbt", "ES.2",
                            lambda l: l[:-1] + f', "{quest_id("ES.1")}"]')
    assert rc == 1 and out == [_failing(clean, 1), "  EXTRA DEP ES.2: ES.1"], out


def test_an_extra_dep_on_an_unpinned_helper_prints_its_yaml_name(tmp_path, monkeypatch, capsys):
    # AETHER.1 is neither a tree node nor in HELPER_DEPS; main() names every quest from the YAML, so no raw hex here
    clean, rc, out = _probe(tmp_path, monkeypatch, capsys, "space.snbt", "D6.8",
                            lambda l: l[:-1] + f', "{quest_id("AETHER.1")}"]')
    assert rc == 1 and out == [_failing(clean, 1), "  EXTRA DEP D6.8: AETHER.1"], out


def test_probe_e_a_dangling_dep_id_fails(tmp_path, monkeypatch, capsys):
    clean, rc, out = _probe(tmp_path, monkeypatch, capsys, "space.snbt", "D6.8", lambda l: l[:-1] + ', "0123456789ABCDEF"]')
    assert rc == 1 and out == [_failing(clean, 1),
                               "  DANGLING DEP space.snbt: D6.8 depends on 0123456789ABCDEF, which names no quest"], out


def test_a_dangling_dep_fails_outside_the_checked_tiers_too(tmp_path, monkeypatch, capsys):
    # the dangling scan covers every quest in every chapter, whatever --tiers says
    clean, rc, out = _probe(tmp_path, monkeypatch, capsys, "space.snbt", "D6.8", lambda l: l[:-1] + ', "0123456789ABCDEF"]',
                            tiers="0,1,2,3,4")
    assert rc == 1 and out == [_failing(clean, 1),
                               "  DANGLING DEP space.snbt: D6.8 depends on 0123456789ABCDEF, which names no quest"], out


def test_the_d1_3_exception_is_required_not_just_allowed(tmp_path, monkeypatch, capsys):
    # D66 (1)-(2) and D135: v0.1's [D1.3] waits on its chapter's boss-kill helper CATA.1, the one tree-node quest that
    # depends on a helper. Dropping it is a missing dependency like any other.
    assert check_quests.TREE_DEP_EXCEPTIONS == {"D1.3": ["CATA.1"]}
    clean, rc, out = _probe(tmp_path, monkeypatch, capsys, "cataclysm.snbt", "D1.3",
                            lambda l: l.replace(f', "{quest_id("CATA.1")}"', ""), tiers="0,1,2,3,4")
    assert rc == 1 and out == [_failing(clean, 1), "  DEP D1.3 should depend on CATA.1"], out


def test_a_quest_block_the_reader_misses_is_unread(tmp_path, monkeypatch, capsys):
    # [X2.4] has no dependencies and no quest depends on it, so a block quest_deps cannot read used to pass with no line
    # at all. Here the block's opening brace carries its first key, a layout QUEST_BLOCK does not match.
    root = _tree(tmp_path, _real_tables())
    clean = _clean(monkeypatch, capsys, root, ALL)
    path = root / "chapters" / "twilight.snbt"
    text = path.read_text()
    qid = quest_id("X2.4")
    every = {q: deps for c in (root / "chapters").glob("*.snbt")
             for q, deps in check_quests.quest_deps(c.read_text()).items()}
    assert every[qid] == [] and not any(qid in deps for deps in every.values())
    old = f'\t\t{{\n\t\t\tid: "{qid}"\n'
    assert text.count(old) == 1
    path.write_text(text.replace(old, f'\t\t{{ id: "{qid}"\n'))
    assert qid not in check_quests.quest_deps(path.read_text())
    rc, out = _main_tiers(monkeypatch, capsys, root, ALL)
    assert rc == 1 and out == [_failing(clean, 1), "  UNREAD quest X2.4"], out


def test_quest_deps_reads_one_line_and_ftb_resaved_arrays():
    one = '\t\t{\n\t\t\tdependencies: ["7402B74889DEA9C1", "426E087DF5AC9F9E"]\n\t\t\tid: "51B7CA5D3BD490D1"\n\t\t}\n'
    multi = ('\t\t{\n\t\t\tdependencies: [\n\t\t\t\t"7402B74889DEA9C1"\n\t\t\t\t"426E087DF5AC9F9E"\n\t\t\t]\n'
             '\t\t\tid: "51B7CA5D3BD490D1"\n\t\t}\n')
    none = '\t\t{\n\t\t\tid: "426E087DF5AC9F9E"\n\t\t}\n'
    want = {"51B7CA5D3BD490D1": ["7402B74889DEA9C1", "426E087DF5AC9F9E"]}
    assert check_quests.quest_deps(one) == want and check_quests.quest_deps(multi) == want
    assert check_quests.quest_deps(none) == {"426E087DF5AC9F9E": []}


# B3: the nine helper-quest dependencies D135 logs (design/decisions.md D135, "Helper-quest dependencies"): OTHER5.1 on
# [D5.1]; OTHER5.2 and OTHER5.3 on OTHER5.1; OTHER5.4 on [M3.1]; SPACE.1 on [T6.1]; SPACE.2 on [M0.2]; ES.1 on nothing;
# ES.2 and ES.3 on [D6.10]. check_quests.main() holds the shipped SNBT to HELPER_DEPS; this pins HELPER_DEPS and the YAML.
D135_HELPERS = {"OTHER5.1": ["D5.1"], "OTHER5.2": ["OTHER5.1"], "OTHER5.3": ["OTHER5.1"], "OTHER5.4": ["M3.1"],
                "SPACE.1": ["T6.1"], "SPACE.2": ["M0.2"], "ES.1": [], "ES.2": ["D6.10"], "ES.3": ["D6.10"]}


def test_helper_deps_are_d135s_nine():
    from scaffold_chapter import CHAPTERS_DIR, parse_chapter
    assert check_quests.HELPER_DEPS == D135_HELPERS
    yaml = {q["node"]: q["deps"] for p in CHAPTERS_DIR.glob("*.yaml") for q in parse_chapter(p.read_text())["quests"]}
    assert {h: yaml.get(h) for h in D135_HELPERS} == D135_HELPERS
