"""v0.3 questbook content (spec docs/superpowers/specs/2026-09-25-v0.3-tiers-5-6-design.md §9.1, §9.2, §10).
check_quests.py already diffs the tree against the questbook; these tests pin what it cannot see: the bags and shop
prices, the quest-text musts of §9.1 plus spec §14's heart count and the X5.2 pink-slime route, and text that the
scaffolder would write into broken SNBT."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scaffold_chapter import parse_chapter, validate_chapter, CHAPTERS_DIR  # noqa: E402

NEW = ("the_other", "space", "starlight")


def _quests(name: str) -> dict:
    return {q["node"]: q for q in parse_chapter((CHAPTERS_DIR / f"{name}.yaml").read_text())["quests"]}


def test_v03_chapters_scaffold_cleanly():
    # group ids: chapter_groups.snbt Trunk ...01, Spurs ...02 (scaffold_chapter.GROUPS); orders follow end = 5 and bumblezone = 13
    want = {"the_other": ("0C0F1A0000000001", 6), "space": ("0C0F1A0000000001", 7), "starlight": ("0C0F1A0000000002", 14)}
    for name in NEW:
        ch = parse_chapter((CHAPTERS_DIR / f"{name}.yaml").read_text())
        assert (ch["group"], ch["order"]) == want[name]
        assert validate_chapter(ch) == [], name


def test_v03_bags_and_shop_prices():
    other, space, shop = _quests("the_other"), _quests("space"), _quests("shop")
    assert other["D5.1"]["bag"] == "epic_bag"
    assert space["D6.1"]["bag"] == "epic_bag"
    assert space["D6.7"]["bag"] == "legendary_bag"
    for node, price, dep, bag in (("SHOP.4", 192, "D5.1", "epic_bag"), ("SHOP.5", 384, "D6.7", "legendary_bag")):
        q = shop[node]
        assert (q["task"], q["deps"], q["bag"], q["coins"], q["consume"], q["repeat"]) == \
            (f"item:kubejs:coin:{price}", [dep], bag, 0, True, True)


# Spec §9.1 "Quest text must state" musts, plus spec §14's heart count and the X5.2 pink-slime route: each must, the
# quest that carries it, and the words that carry it.
MUSTS = [
    ("the_other", "OTHER5.1", ["in either hand", "sneak and right-click the pad with both hands empty"]),  # two-click pad
    ("the_other", "OTHER5.1", ["whole FTB team", "cannot follow you in"]),                               # team scope, no follow-in
    ("the_other", "OTHER5.1", ["The Beyond", "is closed"]),                                               # Beyond closed
    ("the_other", "D5.3", ["1024 health", "up to one Witch each time it takes damage"]),  # Piglich (BP §1; attacks only once Task 12's probe confirms them)
    # Heart count: spec §14's erratum to §5 (9 hearts gate the end of tier 6; 10 with quest S5.2's ME Controller, D117).
    ("the_other", "D5.3", ["nine to reach the end of Space", "ten with the ME Controller"]),
    ("the_other", "OTHER5.3", ["Ancient Basalt Deltas", "4 by 3 pool"]),                                  # both soul-lava sources
    # Pink slime route: industrialforegoing-1.21-3.6.39.jar data/industrialforegoing/recipe/dissolution_chamber/pink_slime_ball.json
    # (glass pane in 300 mB pink slime fluid) and SlaughterFactoryTile (fills its pink_slime tank); tree [T4.1].
    ("the_other", "X5.2", ["glass pane", "300 mB of pink slime fluid", "Mob Slaughter Factory"]),
    ("space", "SPACE.2", ["one per kill", "uses up the Soulcaller"]),                                     # Tyros, soulcaller
    ("space", "D6.6", ["Fire Resistance"]),                                                               # Venus heat
    ("space", "D6.7", ["Fire Resistance"]),                                                               # Mercury heat
    ("space", "D6.6", ["Acid rain", "whenever it rains in the Overworld", "only a roof, a rocket or a lander"]),
    ("space", "D6.8", ["no suit is needed"]),                                                             # Glacio
    ("space", "D6.5", ["Cryo Freezer", "ostrum plates", "no oil and no refinery", "1000 mB", "3000 mB"]),  # Mars cryo fuel
    ("starlight", "D6.10", ["never used up", "five centre cells"]),                                       # ES Orb and frame
]


def test_v03_quest_text_musts():
    # every missing phrase in one failure, so one run shows all of them
    missing = [f"{c}.yaml {n} lacks {p!r}" for c, n, ps in MUSTS for p in ps if p not in _quests(c)[n]["desc"]]
    assert not missing, "\n".join(missing)


def test_every_quest_text_is_scaffold_safe():
    # lang_entries writes title and desc inside SNBT double quotes with no escaping, so a '"' or '\\' would break the
    # lang file; '%', braces and non-ASCII are kept out by pack convention (none in any chapter shipped up to 0.2.1).
    # The chapter title goes into the same file (lang_entries' chapter.<id>.title line), so it gets the same scan.
    for path in sorted(CHAPTERS_DIR.glob("*.yaml")):
        ch = parse_chapter(path.read_text())
        assert ch["title"], f"{path.name} has no chapter title"
        bad = sorted({c for c in ch["title"] if ord(c) > 127 or c in '"%{}\\'})
        assert not bad, f"{path.name} chapter title: {bad}"
        for q in ch["quests"]:
            assert q["title"], f"{path.name} {q['node']} has no title"
            for key in ("title", "desc"):
                bad = sorted({c for c in q[key] if ord(c) > 127 or c in '"%{}\\'})
                assert not bad, f"{path.name} {q['node']} {key}: {bad}"
