"""Diff the tree against the questbook (spec §5.2, §5.4); check what the questbook pays out (v0.3 spec §10; D126, D133).

main() fails on: a tree node with no quest, a quest missing a gate dependency, a reward table not in the canonical shape
(canonical_problems), a chapter off the measured reward shapes (chapter_problems), an emergency_items key in data.snbt
(data_problems), a reward table holding a FORBIDDEN id, a reward table holding an EXCLUDED id (legendary_bag may hold
LEGENDARY_ALLOWED), a reward table holding what tools/bag_banned.json bars it from (bag_collisions: a tier-5/6 input, a
gated output, a precursor), a chapter's quest rewards paying out any of those (chapter_reward_hits, reward_ids), and a
missing tools/bag_banned.json. It prints one summary line, then one indented line per failure. It reads no recipes:
tools/tests/test_bag_collisions.py computes tools/bag_banned.json from the boot's recipe dump and checks it is current.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scaffold_chapter import LANG, quest_id  # noqa: E402
TREE = ROOT.parent / "progression" / "combined-tree.md"
QUESTS = ROOT / "config" / "ftbquests" / "quests"
NO_QUEST = {"X0.3", "X3.3"}          # audit-only nodes with nothing to do (spec §5.2)
# The recipe dump's verdicts on bag items (round 3, I3), written by tools/tests/test_bag_collisions.py from the last boot's
# .run/server/kubejs/exported/{recipes,item_tag_members}.json and tools/gates.yaml, which test_bag_collisions.py also checks
# it against whenever a dump exists. main() reads it, so a clone with no dump fails a gated output in a bag too.
SNAPSHOT = ROOT / "tools" / "bag_banned.json"
SNAPSHOT_COMMAND = "python3 tools/tests/test_bag_collisions.py --write-snapshot"
# FORBIDDEN: ids no reward table or chapter reward may hold: the keys and focus items, the tier metals, the planet materials,
# the Piglich heart, boss drops and tier-5/6 key inputs (D54 as D89/D94 read it), and their one-step precursors (D133; every
# longer chain is in SNAPSHOT's precursors). Spec §10's whole excluded set is EXCLUDED, below. Both match the WHOLE
# double-quoted id ('"(' + alternatives + ')"'), which is the only way a canonical table names an item
# (canonical_problems), so neither reads an id written any other way. One alternative per line. ID is the id-path grammar
# ENTRY accepts.
ID = r"[a-z0-9_./-]*"
FORBIDDEN_IDS = [
    # v0.1-v0.2: the keys and focus items, the ATM metals and alloys, the planet metals, the Piglich heart, boss drops
    r"kubejs:(twilight_key|other_key|end_focus|astral_focus|confluence_catalyst)",
    rf"allthemodium:{ID}(allthemodium|vibranium|unobtainium){ID}",
    rf"ad_astra:{ID}(desh|ostrum|calorite|etrium){ID}",      # D133: raw_*, *_ore and the ore-block forms smelt to ingots
    rf"allthemodium:piglich_heart{ID}",                      # D133: piglich_heart_block crafts to 9 hearts
    rf"cataclysm:{ID}",
    rf"twilightforest:knightmetal{ID}",
    rf"undergarden:forgotten{ID}",
    # v0.3 (spec §9.2, D126): tier-5/6 key inputs, boss drops and planet materials. Each id is a registered item, read at
    # plan time from its jar's assets/<ns>/lang/en_us.json: block.ad_astra.nasa_workbench (adastra-1.21.1-1.16.25-neoforge.jar),
    # item.ars_nouveau.wilden_tribute (ars_nouveau-1.21.1-5.13.1.jar), item.irons_spellbooks.divine_soulshard
    # (irons_spellbooks-1.21.1-3.16.3.jar), item.mekanism.ultimate_control_circuit (Mekanism-1.21.1-10.7.19.85.jar),
    # item.eternal_starlight.{unrealium,golem_steel}_ingot and the _nugget/_block/tool/armour forms
    # (eternalstarlight-0.9.0+1.21.1+neoforge.jar), block.minecraft.dragon_egg (server-1.21.1-20240808.144430-extra.jar),
    # item.the_bumblezone.essence_of_the_bees (the_bumblezone-7.15.3+1.21.1-neoforge.jar). The four kubejs: ids are
    # event.create() calls in kubejs/startup_scripts/items.js.
    r"ad_astra:nasa_workbench",
    r"ars_nouveau:wilden_tribute",
    r"irons_spellbooks:divine_soulshard",
    r"mekanism:ultimate_control_circuit",
    r"kubejs:(mercury|glacio)_(shard|ore)",
    # D133: any prefix, so the oxidized_ forms (which smelt back: golem_steel_ingot_smelting_from_oxidized_golem_steel_ingot)
    # and the waxed_/chiseled_ decor blocks (made from golem steel) are caught with the rest
    rf"eternal_starlight:{ID}(unrealium|golem_steel){ID}",
    r"minecraft:dragon_egg",
    r"the_bumblezone:essence_of_the_bees",
    # D133: one-step precursors, which the recipe dump (.run/server/kubejs/exported/recipes.json, Boot 2 of Task 10) turns
    # into a forbidden id by one recipe with one distinct ingredient, and three more key inputs (spec §4.1, §5, §6).
    # Lang keys from adastra-1.21.1-1.16.25-neoforge.jar, allthemodium-3.0.1_mc_1.21.1.jar,
    # industrialforegoing-1.21-3.6.39.jar, twilightforest-1.21.1-4.8.3345-universal.jar and
    # MysticalAgradditions-1.21.1-8.0.14.jar.
    rf"ad_astra:{ID}ice_shard{ID}",    # item.ad_astra.ice_shard (a tier-6 Etrium input); its ores smelt to it
    rf"allthemodium:soul_lava{ID}",    # block.allthemodium.soul_lava, item.allthemodium.soul_lava_bucket (an X5.2 input)
    r"industrialforegoing:machine_frame_(advanced|supreme)",  # §4.1 key input (advanced); T5.2 makes supreme from it
    rf"twilightforest:armor_shard{ID}",  # armor_shard x9 -> armor_shard_cluster -> knightmetal_ingot (smelting/blasting)
    # MA seeds/essences (members of #mysticalagriculture:seeds / :essences): seed/reprocessor/knightmetal and
    # essence/twilightforest/knightmetal_ingot; seed/reprocessor/dragon_egg, mysticalagradditions:essence/dragon_egg_chunk,
    # and mysticalagradditions:dragon_egg (3 chunks -> minecraft:dragon_egg)
    r"mysticalagriculture:knightmetal_(essence|seeds)",
    r"mysticalagriculture:dragon_egg_(essence|seeds)",
    r"mysticalagradditions:dragon_egg_chunk",
]
FORBIDDEN = re.compile('"(' + "|".join(FORBIDDEN_IDS) + ')"')
# Spec §10's excluded set (D126): the gate inputs of §4.1, §5 and §6, which no bag may hold, resolved to ids (D133). One
# alternative per spec phrase, in the spec's order; "[#tag]" is the spec recipe's own ingredient and the ids are its members
# in .run/server/kubejs/exported/item_tag_members.json (Boot 2 of Task 10); lang keys are in the named jar's
# assets/<ns>/lang/en_us.json. A fluid is listed with its bucket. Two plural phrases name the ids the gate recipes take
# (round 3, I6): "fluix" is the crystal (S5.2, S6.2), the glass cable (S5.3, S6.2) and the block, which deconstructs to 4
# crystals (ae2:misc/deconstruction_fluix_block), plus the 16 coloured glass cables, which wash back into the fluix one
# (ae2:network/cables/glass_fluix_clean: a #ae2:glass_cable member and a water bucket or snowball, #ae2:can_remove_color);
# "QIO parts and the QIO dashboard" is spec §5's tier-3 QIO parts (row "T5.1 side": confluence:tier3/qio_drive_array,
# qio_importer, qio_exporter) and S5.3's dashboard, the four parts of combined-tree [S3.1] (L380, L385). The other 14
# ae2:fluix_* and 5 mekanism:qio_* ids are left to tools/bag_banned.json (SNAPSHOT). The scope is spec §10's list, which
# omits ae2:semi_dark_monitor (S5.3's terminal) and the X5.3 Digital Miner's default inputs (logistical sorter, robit, steel
# casing, teleportation core); SNAPSHOT bars those as tier-5 inputs. Jars: adastra-1.21.1-1.16.25-neoforge,
# allthemodium-3.0.1_mc_1.21.1, appliedenergistics2-19.2.17, ars_nouveau-1.21.1-5.13.1, industrialforegoing-1.21-3.6.39,
# irons_spellbooks-1.21.1-3.16.3, Mekanism-1.21.1-10.7.19.85, Powah-6.2.10, the_bumblezone-7.15.3+1.21.1-neoforge,
# toms_storage-1.21-2.4.2, The_Undergarden-1.21.1-0.9.6, twilightforest-1.21.1-4.8.3345-universal,
# eternalstarlight-0.9.0+1.21.1+neoforge, server-1.21.1-20240808.144430-extra (minecraft).
EXCLUDED_IDS = [
    r"kubejs:end_focus",                          # "the End Focus" (items.js event.create)
    r"allthemodium:vibranium_ingot",              # "Vibranium" [#c:ingots/vibranium]
    # "the advanced and Supreme frames" [#industrialforegoing:machine_frame/advanced, #industrialforegoing:machine_frame/supreme]
    r"industrialforegoing:machine_frame_(advanced|supreme)",
    r"the_bumblezone:essence_of_the_bees",        # "Essence of the Bees" (item.the_bumblezone.essence_of_the_bees)
    r"minecraft:dragon_egg",                      # "the dragon egg" (block.minecraft.dragon_egg)
    r"mekanism:(elite|ultimate)_control_circuit",  # "elite and ultimate circuits" [#c:circuits/elite, #c:circuits/ultimate]
    r"mekanism:alloy_atomic",                     # "atomic alloy" [#mekanism:alloys/atomic]
    r"allthemodium:unobtainium_(ingot|block)",    # "Unobtainium" [#c:ingots/unobtainium, #c:storage_blocks/unobtainium]
    r"ars_nouveau:wilden_tribute",                # "the Wilden Tribute" (item.ars_nouveau.wilden_tribute)
    r"industrialforegoing:plastic",               # "plastic" [#c:plastics]
    # "nitro crystals and nitro crystal blocks" (item.powah.crystal_nitro, block.powah.nitro_crystal_block)
    r"powah:(crystal_nitro|nitro_crystal_block)",
    r"industrialforegoing:ether_gas(_bucket)?",   # "ether gas": the T5.2 fluid, item.industrialforegoing.ether_gas_bucket
    r"allthemodium:allthemodium_ingot",           # "Allthemodium" [#c:ingots/allthemodium]
    r"allthemodium:piglich_heart",                # "the Piglich heart" (item.allthemodium.piglich_heart)
    r"ars_nouveau:(air|earth|water|fire)_essence",  # "the four elemental essences" [#confluence:ars_essences]
    r"industrialforegoing:pink_slime",            # "pink slime" (item.industrialforegoing.pink_slime)
    r"allthemodium:soul_lava(_bucket)?",          # "soul lava": the X5.2 fluid (block.allthemodium.soul_lava), its bucket
    # "the three ATM alloys" (item.allthemodium.<pair>_alloy_ingot)
    r"allthemodium:(unobtainium_allthemodium|vibranium_allthemodium|unobtainium_vibranium)_alloy_ingot",
    r"mekanism:hdpe_sheet",                       # "HDPE sheet" (item.mekanism.hdpe_sheet)
    r"twilightforest:knightmetal_ingot",          # "knightmetal" [#c:ingots/knightmetal]
    r"ae2:fluix_(crystal|glass_cable|block)",     # "fluix" (S5.2 fluix_crystal, S5.3 fluix_glass_cable, 4 crystals a block)
    r"ae2:[a-z_]+_glass_cable",                   # (the coloured glass cables, which wash back into fluix_glass_cable)
    r"undergarden:forgotten_ingot",               # "the forgotten ingot" (item.undergarden.forgotten_ingot)
    r"ae2:(engineering|logic|calculation)_processor",  # "AE2 processors" (item.ae2.*_processor; the printed_ ones are not)
    r"ae2:(annihilation|formation)_core",         # "and cores" (item.ae2.{annihilation,formation}_core)
    r"ae2:(smooth_)?sky_stone_block",             # "sky stone": block.ae2.smooth_sky_stone_block "Sky Stone Block" (S5.2) and
                                                  # block.ae2.sky_stone_block "Sky Stone", which smelts to it
                                                  # (ae2:smelting/smooth_sky_stone_block)
    r"toms_storage:inventory_connector",          # "the inventory connector" (block.toms_storage.inventory_connector)
    r"mekanism:qio_(dashboard|drive_array|importer|exporter)",  # "QIO parts and the QIO dashboard"
    r"ad_astra:steel_(plate|block)",              # "steel plates and blocks" [#ad_astra:steel_plates, #ad_astra:steel_blocks]
    r"mekanism:block_steel",                      # (the other member of #ad_astra:steel_blocks)
    r"minecraft:elytra",                          # "the elytra" (item.minecraft.elytra)
    r"mekanism:electric_pump",                    # "the electric pump" (block.mekanism.electric_pump)
    r"ad_astra:engine_frame",                     # "the engine frame" (item.ad_astra.engine_frame)
    r"ad_astra:fan",                              # "the fan" (item.ad_astra.fan)
    r"ad_astra:(desh|ostrum|calorite)_ingot",     # "desh, ostrum, calorite" [#c:ingots/desh, ostrum, calorite]
    r"ad_astra:ice_shard",                        # "the ice shard" (item.ad_astra.ice_shard)
    r"ad_astra:etrium_ingot",                     # "Etrium" (item.ad_astra.etrium_ingot; no Etrium tag, spec §6)
    r"irons_spellbooks:divine_soulshard",         # "the divine soulshard" (item.irons_spellbooks.divine_soulshard)
    r"kubejs:(mercury|glacio)_shard",             # "the Mercury and Glacio shards" (items.js event.create)
    r"ae2:fluix_pearl",                           # "fluix pearls" (item.ae2.fluix_pearl; S6.1)
    r"ae2:quartz_fiber",                          # "quartz fiber" (item.ae2.quartz_fiber)
    r"eternal_starlight:unrealium_ingot",         # "Unrealium" [#c:ingots/unrealium]
]
EXCLUDED = re.compile('"(' + "|".join(EXCLUDED_IDS) + ')"')
# Both lists as one (round 3, M3): CHAPTER_BANNED below reads it quoted, and BANNED matches a bare id (fullmatch), as
# tools/tests/test_bag_collisions.py reads ids from the recipe dump.
BANNED_IDS = FORBIDDEN_IDS + EXCLUDED_IDS
BANNED = re.compile("(?:" + "|".join(BANNED_IDS) + ")")
# Spec §10: "A tier-5 input may appear in the tier-6 bag" (D89/D94, restated in D126). These are
# the Legendary bag's two tier-5 inputs, the only excluded ids any table may hold; test_bag_collisions.py checks that they
# are exactly the Legendary entries the recipe dump makes tier-5 inputs.
LEGENDARY_ALLOWED = {"industrialforegoing:plastic", "mekanism:elite_control_circuit"}
# What else the Legendary bag may hold (round 3, I4): a precursor of a tier-5 input, and of LEGENDARY_ALLOWED (the codes of
# tools/bag_banned.json's "precursors", below). Spec §10 lets a tier-5 input into the tier-6 bag, so what makes one may
# go there too; the Epic bag (tier 5) may hold neither.
LEGENDARY_MAY_HOLD = {"pre:allowed", "pre:in5"}
# Spec §10 ¶1's base vanilla materials, plus wool and glass panes, the same class (orchestrator interpretation, D133).
# SPEC_BASE_MATERIALS (round 4, B1) is ¶1's "Base vanilla materials (iron, copper, pistons, buckets, furnaces, crafting
# tables) are not gate inputs, as in D89", read as six items: iron and copper are the ingots (no block, nugget or raw form).
# Round 5 adds the glass pane and the 16 vanilla wools (the space helmet takes glass panes; the space suit, boots and pants
# take #minecraft:wool). VANILLA_WOOL is #minecraft:wool's minecraft: members, explicit so this reads without a dump;
# tools/tests/test_bag_collisions.py pins it against the dump's item_tag_members.json. The tag's other members in this
# pack (320 chipped: wools and ad_astra:glacian_fur) are no vanilla common and stay tier-6 inputs. A base material is no
# tier-5/6 input and no precursor target, and the closure ends at one (an edge into it is followed no further), so SNAPSHOT
# never names one.
SPEC_BASE_MATERIALS = {"minecraft:iron_ingot", "minecraft:copper_ingot", "minecraft:piston", "minecraft:bucket",
                       "minecraft:furnace", "minecraft:crafting_table"}
VANILLA_WOOL = {f"minecraft:{colour}_wool" for colour in (
    "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray", "light_gray", "cyan", "purple", "blue",
    "brown", "green", "red", "black")}
BASE_MATERIALS = SPEC_BASE_MATERIALS | {"minecraft:glass_pane"} | VANILLA_WOOL
# Round 3, M1: [0-9], never \d (which also reads fullwidth digits), and a weight of at least 1: FTB Quests pays a
# zero-weight row on every opening (RewardTable.generateWeightedRandomRewards starts its result from every reward whose
# getWeight() is 0, then draws loot_size times; ftb-quests-neoforge-2101.1.35.jar, javap -c offsets 18-68).
ENTRY = re.compile(r'^\t\t\{ id: "([0-9A-F]{16})" item: \{ count: ([0-9]+), id: "([a-z0-9_.-]+:[a-z0-9_./-]+)" \} '
                   r'weight: ([1-9][0-9]*)\.0f \}$', re.M)
# The one shape every reward table is written in (all 41 shipped rows, v0.3 Task 10). FTB Quests reads tables with
# ftb-library's SNBT parser, which also accepts shapes this file's regexes cannot read: single quotes, unknown escapes
# (dropped), bare words, ids with a leading colon or no namespace (both parse as minecraft:), item components, and typed
# rewards (RewardTable.createRewardForTable(long, String, ...) builds a reward from its "type", so type: "command" makes a
# CommandReward); and SNBT.readLines skips any line whose trimmed text starts with // or #. Review evidence, D133: javap
# of RewardTable and the SNBT parser (ftb-quests-neoforge-2101.1.35.jar, ftb-library-neoforge-2101.1.36.jar), and each
# shape run through the real parser (scratchpad t10-verify/forbidden/java/P.java, doctor.py). RewardTable also reads
# empty_weight and loot_table_id. So a table must match this template line for line, with one ENTRY per rewards line:
# the top-level keys are exactly id, loot_crate, loot_size, order_index, rewards, use_title. loot_size is at least 1 (0 draws
# nothing). FTB Quests' own re-saved form (drops on several lines, each row across several lines with a reward-level count,
# as in .run/server/config/ftbquests/quests/reward_tables after a boot) is not accepted: write one row per line, as the
# shipped tables do. The "expected the ... line" reasons say so (HINT).
TABLE_HEAD = [
    ("opening brace", r"\{"),
    ("id", r'\tid: "[0-9A-F]{16}"'),
    ("loot_crate", r"\tloot_crate: \{"),
    ("loot_crate color", r"\t\tcolor: [0-9]+"),
    ("loot_crate drops", r"\t\tdrops: \{ boss: [0-9]+ monster: [0-9]+ passive: [0-9]+ \}"),
    ("loot_crate glow", r"\t\tglow: [01]b"),
    ("loot_crate string_id", r'\t\tstring_id: "[a-z0-9_]+"'),
    ("end of loot_crate", r"\t\}"),
    ("loot_size", r"\tloot_size: [1-9][0-9]*"),
    ("order_index", r"\torder_index: [0-9]+"),
    ("rewards", r"\trewards: \["),
]
TABLE_TAIL = [("end of rewards", r"\t\]"), ("use_title", r"\tuse_title: true"), ("closing brace", r"\}")]
HINT = ("FTB's own re-saved form (multi-line drops, reward-level count) is not accepted; write one row per line as the "
        "shipped tables do")


def line_scan(lines: list[str]) -> list[tuple[int, str]]:
    """(line number, reason) for each line ftb-library's SNBT parser reads differently from the regexes here: a comment line
    (SNBT.readLines skips it), a single quote (a quoted string), a backslash (an escape, dropped when unknown)."""
    problems = []
    for n, line in enumerate(lines, 1):
        if line.strip().startswith(("//", "#")):
            problems.append((n, "comment line (FTB Quests drops it before parsing)"))
        if "'" in line:
            problems.append((n, "single quote"))
        if "\\" in line:
            problems.append((n, "backslash escape"))
    return problems


def canonical_problems(text: str) -> list[tuple[int, str]]:
    """(line number, reason) for every way `text` departs from the canonical reward-table shape; [] when it is canonical.
    The template check stops at its first mismatch, so one bad line is not reported as a cascade."""
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    problems = line_scan(lines)
    i = 0
    for name, pattern in TABLE_HEAD:
        if i >= len(lines) or not re.fullmatch(pattern, lines[i]):
            return sorted(set(problems + [(i + 1, f"expected the {name} line; {HINT}")]))
        i += 1
    while i < len(lines) and lines[i] != "\t]":
        if not ENTRY.fullmatch(lines[i]):
            problems.append((i + 1, 'not a canonical row: { id: "<16 hex>" item: { count: N, id: "ns:path" } weight: N.0f }'))
        i += 1
    for name, pattern in TABLE_TAIL:
        if i >= len(lines) or not re.fullmatch(pattern, lines[i]):
            return sorted(set(problems + [(i + 1, f"expected the {name} line; {HINT}")]))
        i += 1
    if i < len(lines):
        problems.append((i + 1, "content after the closing brace"))
    return sorted(set(problems))

NODE = re.compile(r"^- \[([A-Z][0-9]+\.[0-9]+)\]")
# Skip source-pack citations such as "ozone [T4.2] pattern" / "atm10 [X2.1]" / "per evolution [M2.1]"
# (combined-tree.md Legend L49 and gate lines L175, L197, L236): they cite the source trees, not our gates.
GATE_REF = re.compile(r"(?<!ozone )(?<!atm10 )(?<!evolution )\[([A-Z][0-9]+\.[0-9]+)\]")
TIER = re.compile(r"^### (Tier ([0-9]+)|Top|Bypass)")


def tree_nodes(text: str, tiers: set[int]) -> dict[str, list[str]]:
    nodes: dict[str, list[str]] = {}
    cur_tier, cur = None, None
    for line in text.splitlines():
        m = TIER.match(line)
        if m:
            cur_tier = int(m.group(2)) if m.group(2) else None
            continue
        m = NODE.match(line)
        if m:
            cur = m.group(1)
            nodes[cur] = None
            continue
        if cur and line.strip().startswith("- gate:") and nodes[cur] is None:
            nodes[cur] = GATE_REF.findall(line)
    out = {}
    for n, deps in nodes.items():
        tier = int(n[1:].split(".")[0])
        if tier in tiers and n not in NO_QUEST:
            out[n] = deps or []
    return out


def quests_in_lang(text: str, nodes) -> dict[str, str]:
    """node -> quest id for every node whose quest has a title in the lang file. Quest ids are quest_id(node)
    (scaffold_chapter), so the lang file no longer needs a "[D1.1]" first desc line (session 10); the title key is
    the one entry every quest has, and FTB Quests writes keys one per line in either form."""
    found = {}
    for n in nodes:
        qid = quest_id(n)
        if re.search(rf"^\s*quest\.{qid}\.title: ", text, re.M):
            found[n] = qid
    return found


def forbidden_in_table(text: str) -> list[str]:
    return [m.group(1) for m in FORBIDDEN.finditer(text)]


def excluded_in_table(text: str) -> list[str]:
    return [m.group(1) for m in EXCLUDED.finditer(text)]


REWARDS = re.compile(r"(?<![A-Za-z0-9_])rewards: \[")
CHAPTER_BANNED = re.compile('"(' + "|".join(BANNED_IDS) + ')"')   # one hit per id, whichever list names it


def reward_arrays(text: str) -> list[str]:
    """The text inside each `rewards: [...]` array of a chapter file, to its matching bracket (quote-aware), on one line or
    several. An array inside another (a table_data table's) is part of the outer one and is not returned again."""
    out, end = [], -1
    for m in REWARDS.finditer(text):
        if m.start() < end:
            continue
        depth, i, quote = 0, m.end() - 1, None
        while i < len(text):
            c = text[i]
            if quote:
                if c == "\\":
                    i += 1
                elif c == quote:
                    quote = None
            elif c in "\"'":
                quote = c
            elif c in "[{":
                depth += 1
            elif c in "]}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        out.append(text[m.end():i])
        end = i
    return out


def chapter_reward_hits(text: str) -> list[str]:
    """FORBIDDEN or EXCLUDED ids that a chapter's quest rewards pay out (D133, R6); tasks are not read."""
    return [m.group(1) for block in reward_arrays(text) for m in CHAPTER_BANNED.finditer(block)]


QUOTED_ID = re.compile(r'"([a-z0-9_.-]+:[a-z0-9_./-]+)"')


def reward_ids(text: str) -> list[str]:
    """Every double-quoted namespaced id in a chapter's `rewards:` arrays (main() checks them against SNAPSHOT)."""
    return [m.group(1) for block in reward_arrays(text) for m in QUOTED_ID.finditer(block)]


# Chapter files (round 3, I1, I2). FTB Quests reads them with the same parser as the tables, so a chapter can pay out what
# no regex above reads: a single-quoted, escaped or namespace-less id, a command or custom reward, a `"rewards"` or
# `rewards:[` key, an array split by a // line, and an inline table. RandomReward.readData (and LootReward, ChoiceReward
# and AllTableReward, which extend it) reads `table_id` and, when that is 0 or names no table, builds a RewardTable from
# `table_data` (ftb-quests-neoforge-2101.1.35.jar, javap -c: getLong("table_id"), getRewardTable(J),
# contains("table_data"), new RewardTable(-1L, ...).readData; RewardTypes registers item, choice, all_table, random, loot,
# command, custom, xp, xp_levels, advancement, toast, gamestage and currency). Measured over the 11 chapters before this went
# in: 73 rewards arrays, each one line `\t\t\trewards: [...]` as tools/scaffold_chapter.py writes it, holding 70 item rewards
# (all kubejs:coin) and 7 loot rewards whose table_id is a reward table's id, and nothing else; no `'`, `\`, // or # line,
# and no table_data. So a chapter may not hold a line_scan problem or table_data; every line naming `rewards` must be one
# REWARDS_LINE; reward types are REWARD_TYPES only; and every table_id is a table's id (table_longs). The item ids are
# checked against both lists and SNAPSHOT (main()).
REWARD_TYPES = ("item", "loot")
_REWARD = (r'\{ id: "[0-9A-F]{16}" (?:item: \{ count: [1-9][0-9]*, id: "[a-z0-9_.-]+:[a-z0-9_./-]+" \} type: "item"'
           r'|table_id: [0-9]+L type: "loot") \}')
REWARDS_LINE = re.compile(rf"\t\t\trewards: \[(?:{_REWARD}(?:, {_REWARD})*)?\]")
REWARDS_WORD = re.compile(r"(?<![A-Za-z0-9_])rewards(?![A-Za-z0-9_])")
REWARD_TYPE = re.compile(r'(?<![A-Za-z0-9_])type: "([^"]*)"')
TABLE_DATA_WORD = re.compile(r"(?<![A-Za-z0-9_])table_data(?![A-Za-z0-9_])")
TABLE_ID = re.compile(r"(?<![A-Za-z0-9_])table_id(?![A-Za-z0-9_])(?:: ([0-9]+)L)?")
# data.snbt: BaseQuestFile reads `emergency_items` into its emergencyItems list, which GetEmergencyItemsMessage hands out
# (same jar, javap -p -c); the reviewers' P3.java read a dragon egg back from it. The shipped file has none.
EMERGENCY_WORD = re.compile(r"(?<![A-Za-z0-9_])emergency_items(?![A-Za-z0-9_])")


def table_longs(paths) -> set[int]:
    """The longs a quest reward's table_id names the given reward tables by: each table's hex `id:`, read as base 16
    (scaffold_chapter.load_reward_tables)."""
    return {int(m.group(1), 16) for p in paths for m in re.finditer(r'^\tid: "([0-9A-F]{16})"$', p.read_text(), re.M)}


def chapter_problems(text: str, longs: set[int]) -> list[tuple[int, str]]:
    """(line number, reason) for each way a chapter file departs from the measured reward shapes; [] when it does not."""
    lines = text.split("\n")
    problems = line_scan(lines)
    for n, line in enumerate(lines, 1):
        if REWARDS_WORD.search(line):
            if not REWARDS_LINE.fullmatch(line):
                problems.append((n, "not a canonical rewards line (one line of item and loot rewards, as "
                                    "tools/scaffold_chapter.py writes it)"))
            problems += [(n, f'reward type "{t}" (chapters pay item and loot rewards only)')
                         for t in REWARD_TYPE.findall(line) if t not in REWARD_TYPES]
        if TABLE_DATA_WORD.search(line):
            problems.append((n, "table_data (an inline reward table, which RandomReward.readData builds when table_id "
                                "names no table)"))
        for m in TABLE_ID.finditer(line):
            if m.group(1) is None or int(m.group(1)) not in longs:
                problems.append((n, f"table_id {m.group(1) or '(not written as <digits>L)'} is not a reward table's id"))
    return sorted(dict.fromkeys(problems), key=lambda p: p[0])


def data_problems(text: str) -> list[tuple[int, str]]:
    """(line number, reason) for an emergency_items key in data.snbt, or a backslash that could spell one."""
    problems = []
    for n, line in enumerate(text.split("\n"), 1):
        if "\\" in line:
            problems.append((n, "backslash escape"))
        if EMERGENCY_WORD.search(line):
            problems.append((n, "emergency_items (FTB Quests hands these items out)"))
    return problems


# tools/bag_banned.json (SNAPSHOT) holds, for ids neither list names: "tier5_inputs" and "tier6_inputs" (every id a tier-5 or
# tier-6 recipe takes, tag members included), "gated_outputs" (sole_producers outputs a tier-5/6 recipe makes), "precursors"
# ({id: the codes a chain of single-ingredient recipes from it reaches: "banned" a FORBIDDEN or EXCLUDED id, "allowed" a
# LEGENDARY_ALLOWED id, "in5", "in6", "gated"}), and "pinned" ({table: {id: [code, ...]}}: the shipped bags' hits,
# reported and not judged, test_bag_collisions.SHIPPED_TIER_HITS and SHIPPED_PRECURSORS). A held id's codes are "in5",
# "in6" and "gated" for what it is, and "pre:<code>" for what it makes. Legendary may hold LEGENDARY_MAY_HOLD; a pinned
# (table, id, code) passes; every other code fails.
CODE_TEXT = {"in5": "tier-5 input", "in6": "tier-6 input", "gated": "gated output",
             "pre:banned": "precursor of a FORBIDDEN or EXCLUDED id", "pre:allowed": "precursor of a LEGENDARY_ALLOWED id",
             "pre:in5": "precursor of a tier-5 input", "pre:in6": "precursor of a tier-6 input",
             "pre:gated": "precursor of a gated output"}


def load_snapshot(path: Path):
    """SNAPSHOT as {"in5", "in6", "gated": set, "precursors": {id: [code]}, "pinned": {table: {id: [code]}}}, or None when
    the file does not exist."""
    if not path.is_file():
        return None
    doc = json.loads(path.read_text())
    return {"in5": set(doc["tier5_inputs"]), "in6": set(doc["tier6_inputs"]), "gated": set(doc["gated_outputs"]),
            "precursors": doc["precursors"], "pinned": doc["pinned"]}


def snapshot_codes(item: str, snap) -> list[str]:
    """The codes the snapshot holds for an id: "in5", "in6", "gated", then "pre:<code>" for each precursor code."""
    return [c for c in ("in5", "in6", "gated") if item in snap[c]] + ["pre:" + c for c in snap["precursors"].get(item, ())]


def bag_collisions(stem: str, items, snap) -> list[tuple[str, list[str]]]:
    """(id, codes) for each id of table `stem` whose snapshot codes it may not hold (after LEGENDARY_MAY_HOLD for the
    Legendary bag and the pinned shipped hits)."""
    out = []
    for i in items:
        allowed = set(snap["pinned"].get(stem, {}).get(i, ())) | (LEGENDARY_MAY_HOLD if stem == "legendary_bag" else set())
        codes = [c for c in snapshot_codes(i, snap) if c not in allowed]
        if codes:
            out.append((i, codes))
    return out


def main(argv: list[str]) -> int:
    tiers = {int(t) for t in argv[argv.index("--tiers") + 1].split(",")} if "--tiers" in argv else {0, 1, 2}
    expected = tree_nodes(TREE.read_text(), tiers)
    lang_text = LANG.read_text() if LANG.exists() else ""
    have = quests_in_lang(lang_text, expected)
    missing = sorted(n for n in expected if n not in have)
    # dependency mirror: every gate ref that has a quest must be a dependency of the node's quest
    chapters = "".join(p.read_text() for p in (QUESTS / "chapters").glob("*.snbt"))
    mismatched = []
    for node, deps in expected.items():
        if node not in have:
            continue
        qid = have[node]
        # FTB Quests writes keys alphabetically, so `dependencies:` precedes `id:` inside the quest block.
        idx = chapters.find(f'id: "{qid}"')
        start = chapters.rfind("\n\t\t{", 0, idx) if idx >= 0 else -1
        block_text = chapters[start:idx] if idx >= 0 else ""
        for d in deps:
            if d in have and have[d] not in block_text:
                mismatched.append((node, d))
    tables = list((QUESTS / "reward_tables").glob("*.snbt"))
    forbidden = [(t.name, f) for t in tables for f in forbidden_in_table(t.read_text())]
    noncanonical = [(t.name, n, why) for t in sorted(tables) for n, why in canonical_problems(t.read_text())]
    longs = table_longs(tables)
    chapter_files = sorted((QUESTS / "chapters").glob("*.snbt"))
    noncanonical += [(c.name, n, why) for c in chapter_files for n, why in chapter_problems(c.read_text(), longs)]
    data = QUESTS / "data.snbt"
    noncanonical += [(data.name, n, why) for n, why in data_problems(data.read_text())] if data.exists() else []
    excluded = [(t.stem, i) for t in sorted(tables) for i in excluded_in_table(t.read_text())
                if not (t.stem == "legendary_bag" and i in LEGENDARY_ALLOWED)]
    snap = load_snapshot(SNAPSHOT)
    rewarded = [(c.name, i) for c in chapter_files for i in chapter_reward_hits(c.read_text())]
    rewarded += [(c.name, f"{i} ({', '.join(CODE_TEXT[k] for k in codes)})") for c in chapter_files
                 for i in reward_ids(c.read_text()) if snap and not BANNED.fullmatch(i)
                 for codes in [snapshot_codes(i, snap)] if codes]
    collisions = [(t.stem, i, codes) for t in sorted(tables) for i, codes in
                  bag_collisions(t.stem, [m.group(3) for m in ENTRY.finditer(t.read_text())], snap)] if snap else []
    print(f"nodes: {len(expected)} expected, {len(missing)} missing; deps: {len(mismatched)} mismatched; reward tables: {len(tables)}, forbidden items: {len(forbidden)}")
    for m in missing:
        print("  MISSING quest for", m)
    for n, d in mismatched:
        print(f"  DEP {n} should depend on {d}")
    for t, f in forbidden:
        print("  FORBIDDEN", t, f)
    for t, n, why in noncanonical:
        print(f"  NON-CANONICAL {t}:{n}: {why}")
    for t, i in excluded:
        print(f"  EXCLUDED {t}: {i}")
    for t, i, codes in collisions:
        print(f"  COLLISION {t}: {i} ({', '.join(CODE_TEXT[c] for c in codes)})")
    for c, i in rewarded:
        print(f"  CHAPTER REWARD {c}: {i}")
    if snap is None:
        print(f"  NO SNAPSHOT {SNAPSHOT}: regenerate with `{SNAPSHOT_COMMAND}` (from pack/, after a boot)")
    return 1 if (missing or mismatched or forbidden or noncanonical or excluded or collisions or rewarded or snap is None) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
