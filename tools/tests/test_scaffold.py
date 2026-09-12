from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scaffold_chapter import (parse_chapter, quest_id, parseable_id, render_snbt, render_lang, validate_chapter, build_lang, GROUPS,
                              load_reward_tables, MAX_ID)

YAML = """
chapter: nether
title: Nether
group: C0F1A0000000001A
order: 2
icon: minecraft:netherrack
quests:
  - node: D1.1
    title: Nether Key
    task: item:minecraft:flint_and_steel
    deps: [T0.2]
    coins: 10
    desc: "Gate text."
  - node: X1.1
    title: Netherite
    task: item:minecraft:netherite_ingot
    deps: [D1.1]
"""

# Shop-chapter shape from plan Task 12 Step 1 ("Common Bag" task item:kubejs:coin:16, consume: true, coins: 0).
SHOP_YAML = """
chapter: shop
title: Coin Shop
group: C0F1A0000000001A
order: 20
icon: kubejs:coin
quests:
  - node: SHOP.1
    title: Common Bag
    task: item:kubejs:coin:16
    consume: true
    coins: 0
"""

def test_ids_are_stable_16_hex():
    a, b = quest_id("D1.1"), quest_id("D1.1")
    assert a == b and len(a) == 16 and a == a.upper()

def test_ids_parse_as_java_long():
    # FTB Quests reads ids with Long.parseLong(id, 16) (BaseQuestFile.readID, 1.21.1/main): the top bit must be clear,
    # and readID(long) rerolls 0 and 1. X1.1 / T1.1 / chapter:aether were unparseable with the unmasked sha1 prefix.
    nodes = ["D1.1", "X1.1", "X1.2", "D1.3", "T1.1", "T1.2", "M1.1", "M1.2", "S1.1", "chapter:nether", "chapter:aether"]
    for n in nodes:
        for suffix in ("", ":task", ":coin"):
            i = quest_id(n + suffix)
            assert len(i) == 16 and i == i.upper()
            assert 2 <= int(i, 16) <= MAX_ID, (n + suffix, i)
            assert parseable_id(i)
    assert not parseable_id("C0F1A0000000001A")   # top bit set -> NumberFormatException in Java
    assert not parseable_id("0000000000000001")   # rerolled by readID(long)
    assert not parseable_id("7402B74889DEA9C")    # 15 digits

def test_parse():
    ch = parse_chapter(YAML)
    assert ch["chapter"] == "nether" and len(ch["quests"]) == 2
    assert ch["quests"][0]["deps"] == ["T0.2"]

def test_snbt_has_dependency_and_task():
    ch = parse_chapter(YAML)
    s = render_snbt(ch)
    assert f'dependencies: ["{quest_id("D1.1")}"]' in s
    assert 'id: "minecraft:netherite_ingot"' in s
    assert 'type: "item"' in s
    # count-1 item task keeps the tooling report §4.3 shape exactly; no task-level count key
    assert f'tasks: [{{ id: "{quest_id("X1.1:task")}" item: {{ count: 1, id: "minecraft:netherite_ingot" }} type: "item" }}]' in s
    assert '"[D1.1]"' not in render_lang(ch)  # session 10: descs are player-facing; check_quests maps nodes via quest_id

def test_item_task_count_and_consume_live_on_the_task():
    # ItemTask.writeData/readData (1.21.1/main): `count` is a task-level long (stack saved with count 1) and
    # `consume_items` is a task key; Quest.java has no such key, so a quest-level one would be ignored.
    ch = parse_chapter(SHOP_YAML)
    s = render_snbt(ch)
    tid = quest_id("SHOP.1:task")
    assert f'tasks: [{{ consume_items: true count: 16L id: "{tid}" item: {{ count: 1, id: "kubejs:coin" }} type: "item" }}]' in s
    assert "\t\t\tconsume_items" not in s
    assert 'item: { count: 16' not in s
    assert "rewards: []" in s  # coins: 0 -> no coin reward

def test_lang():
    ch = parse_chapter(YAML)
    l = render_lang(ch)
    assert f'quest.{quest_id("D1.1")}.title: "Nether Key"' in l
    assert f'quest.{quest_id("D1.1")}.quest_desc: ["Gate text."]' in l  # desc only, no node-id line (session 10)
    assert f'chapter.{quest_id("chapter:nether")}.title: "' in l  # the chapter title lives in the same flat file
    assert l.startswith("{\n") and l.endswith("}\n")


def test_build_lang_is_one_flat_compound_with_group_titles(tmp_path):
    # FTB Quests 2101.1.35 reads lang/<locale>.snbt only (TranslationManager.isValidLangFile, `^\w+\.snbt$`):
    # everything - groups, chapters, quests - must sit in one compound.
    y = tmp_path / "nether.yaml"
    y.write_text(YAML)
    text = build_lang([y])
    for gid, title in GROUPS.items():
        assert f'\tchapter_group.{gid}.title: "{title}"' in text
    assert f'\tquest.{quest_id("D1.1")}.title: "Nether Key"' in text
    assert text.count("{") == 1 and text.count("}") == 1
    assert "\n\n" not in text

def test_validate_rejects_unparseable_group():
    ch = parse_chapter(YAML)
    problems = validate_chapter(ch)
    assert len(problems) == 1 and "group" in problems[0] and "C0F1A0000000001A" in problems[0]
    ch["group"] = quest_id("chapter:nether")  # any masked id is parseable
    assert validate_chapter(ch) == []
    ch["quests"][0]["consume"] = True          # consume on a non-item task is caught too
    ch["quests"][0]["task"] = "checkmark"
    assert len(validate_chapter(ch)) == 1 and "D1.1" in validate_chapter(ch)[0]

# Shop bags are the only repeatable quests in v0.1 (plan Task 13 Step 2 sets them repeatable; the `repeat:` YAML key
# does it at scaffold time instead of by hand in the editor).
REPEAT_YAML = """
chapter: shop
title: Coin Shop
group: 0C0F1A0000000003
order: 20
icon: kubejs:coin
quests:
  - node: SHOP.1
    title: Common Bag
    task: item:kubejs:coin:16
    consume: true
    repeat: true
    coins: 0
  - node: SHOP.2
    title: Uncommon Bag
    task: item:kubejs:coin:48
    deps: [D1.1]
    consume: true
    coins: 0
"""

def test_repeat_renders_a_quest_level_can_repeat():
    # Quest.java (tag v2101.1.35) holds `private Tristate canRepeat` and writes `canRepeat.write(nbt, "can_repeat")`
    # at L325, reading it back at L446 (research/phase6-tier0-2-ids-2.md Q3). There is no task-level `can_repeat`,
    # and unlike `consume_items` it is not a chapter key either, so it belongs in the quest block and nowhere else.
    ch = parse_chapter(REPEAT_YAML)
    assert ch["quests"][0]["repeat"] is True
    assert ch["quests"][1]["repeat"] is False          # default when the key is absent
    assert validate_chapter(ch) == []                  # 0C0F1A0000000003 (the Shop group) is a parseable id
    s = render_snbt(ch)
    # first key in the quest block: FTB Quests writes keys alphabetically and can_repeat < dependencies < id
    assert f'\t\t{{\n\t\t\tcan_repeat: true\n\t\t\tid: "{quest_id("SHOP.1")}"' in s
    assert s.count("can_repeat") == 1                  # not on SHOP.2
    for line in s.splitlines():
        if line.lstrip().startswith("tasks:"):
            assert "can_repeat" not in line            # never a task key


# Bag (loot) rewards. `table_id` is the reward table's own long id, i.e. its SNBT hex `id:` parsed with
# Long.parseLong(id, 16): BaseQuestFile.loadRewardTableFile L779 + readID(Tag) L1364-1371, RandomReward.writeData L49
# / readData L65-67, LootReward extends RandomReward and registers as `loot` (RewardTypes L27), all branch 1.21.1/main.
# This refutes D58 / tooling report §4.6 ("a runtime long the scaffolder cannot derive").
BAG_YAML = """
chapter: shop
title: Coin Shop
group: 0C0F1A0000000003
order: 20
icon: kubejs:coin
quests:
  - node: SHOP.1
    title: Common Bag
    task: item:kubejs:coin:16
    consume: true
    repeat: true
    coins: 0
    bag: common_bag
  - node: D1.1
    title: Nether Key
    task: item:minecraft:flint_and_steel
    coins: 10
    bag: uncommon_bag
"""
TABLES = {"common_bag": 0x0C0F1B0000000001, "uncommon_bag": 0x0C0F1B0000000002}


def test_load_reward_tables_reads_the_committed_tables():
    tables = load_reward_tables()
    assert tables["common_bag"] == 0x0C0F1B0000000001    # reward_tables/common_bag.snbt id: "0C0F1B0000000001" (D63)
    assert tables["uncommon_bag"] == 0x0C0F1B0000000002


def test_bag_renders_a_loot_reward_after_the_coin_reward():
    ch = parse_chapter(BAG_YAML)
    assert ch["quests"][0]["bag"] == "common_bag"
    s = render_snbt(ch, TABLES)
    assert f'rewards: [{{ id: "{quest_id("SHOP.1:bag")}" table_id: 868942939919745025L type: "loot" }}]' in s
    assert ('rewards: ['
            f'{{ id: "{quest_id("D1.1:coin")}" item: {{ count: 10, id: "kubejs:coin" }} type: "item" }}, '
            f'{{ id: "{quest_id("D1.1:bag")}" table_id: 868942939919745026L type: "loot" }}]') in s
    assert "exclude_from_claim_all" not in s   # LootReward.getExcludeFromClaimAll() is hard-coded true


def test_no_bag_means_no_loot_reward():
    assert "table_id" not in render_snbt(parse_chapter(YAML), TABLES)


def test_validate_rejects_an_unknown_bag():
    ch = parse_chapter(BAG_YAML)
    assert validate_chapter(ch, TABLES) == []
    ch["quests"][0]["bag"] = "epic_bag"
    problems = validate_chapter(ch, TABLES)
    assert len(problems) == 1 and "SHOP.1" in problems[0] and "epic_bag" in problems[0]
