from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scaffold_chapter import parse_chapter, quest_id, parseable_id, render_snbt, render_lang, validate_chapter, MAX_ID

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
    assert '"[D1.1]"' in render_lang(ch)  # node id kept as first quest_desc line in lang for check_quests (plan Step 3 note, line 1317; Task 14 regex, line 1634)

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
    assert 'quest_desc: ["[D1.1]", "Gate text."]' in l  # node id first, then desc (plan Step 3 note, line 1317; Task 14 test fixture, line 1583)

def test_validate_rejects_unparseable_group():
    ch = parse_chapter(YAML)
    problems = validate_chapter(ch)
    assert len(problems) == 1 and "group" in problems[0] and "C0F1A0000000001A" in problems[0]
    ch["group"] = quest_id("chapter:nether")  # any masked id is parseable
    assert validate_chapter(ch) == []
    ch["quests"][0]["consume"] = True          # consume on a non-item task is caught too
    ch["quests"][0]["task"] = "checkmark"
    assert len(validate_chapter(ch)) == 1 and "D1.1" in validate_chapter(ch)[0]
