"""v1.0 Catalyst chapter (spec docs/superpowers/specs/2026-11-11-v1.0-catalyst-tier-design.md §4.1, A11, A12): the
chapter's shape, rewards, task items and key text, and A11's rule that nothing depends on a side quest."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_quests  # noqa: E402
from scaffold_chapter import parse_chapter, validate_chapter, quest_id, CHAPTERS_DIR  # noqa: E402

SIDE = ["X7.2", "X7.3", "X7.4", "X7.5", "X7.6", "X7.7", "X7.8"] + [f"CAT.{n}" for n in range(1, 7)]
TASKS = {  # spec §4.1
    "X7.1": "kubejs:confluence_catalyst", "X7.2": "mekanism:creative_energy_cube", "CAT.1": "mekanism:creative_chemical_tank",
    "X7.3": "ae2:creative_energy_cell", "X7.4": "powah:energy_cell_creative", "X7.5": "ars_nouveau:creative_source_jar",
    "X7.6": "mysticalagradditions:creative_essence", "X7.7": "functionalstorage:creative_vending_upgrade",
    "X7.8": "irons_spellbooks:netherite_spell_book", "CAT.2": "toms_storage:adv_wireless_terminal",
    "CAT.3": "ad_astra:jet_suit", "CAT.4": "industrialforegoing:infinity_drill",
    "CAT.5": "productivelib:upgrade_productivity_4", "CAT.6": "twilightforest:triple_bow"}


def _chapter(text=None) -> dict:
    return parse_chapter((CHAPTERS_DIR / "catalyst.yaml").read_text() if text is None else text)


def check_catalyst_chapter(ch: dict) -> list[str]:
    bad = []
    if (ch["group"], ch["order"]) != ("0C0F1A0000000001", 8):
        bad.append("group/order")
    qs = {q["node"]: q for q in ch["quests"]}
    if sorted(qs) != sorted(TASKS):
        bad.append("quest set")
    top = qs.get("X7.1", {})
    if top.get("coins") != 30 or top.get("bag") != "legendary_bag":
        bad.append("X7.1 reward")
    for n in SIDE:
        q = qs.get(n, {})
        if q.get("coins") != 10 or q.get("bag") or q.get("deps") != ["X7.1"]:
            bad.append(f"{n} reward/deps")
        if not q.get("desc", "").startswith("Optional"):
            bad.append(f"{n} not Optional")
    for n, item in TASKS.items():
        if qs.get(n, {}).get("task") != f"item:{item}":
            bad.append(f"{n} task")
    text = lambda n: qs.get(n, {}).get("desc", "")  # noqa: E731
    musts = {"X7.1": ["Astral Focus", "seven Arcane Pedestals", "dragon egg crop", "uses up one catalyst"],
             "X7.2": ["not kept"], "CAT.1": ["not kept"], "CAT.3": ["chestplate"], "CAT.6": ["Snow Queen"],
             "X7.8": ["Arcane Cloth"], "X7.4": ["Energy Cell (Nitro)"]}
    for n, phrases in musts.items():
        bad += [f"{n} lacks {p!r}" for p in phrases if p not in text(n)]
    return bad


def test_v1_catalyst_chapter():
    ch = _chapter()
    assert validate_chapter(ch) == []
    assert check_catalyst_chapter(ch) == []


def test_v1_catalyst_chapter_check_catches_a_dropped_bag():
    text = (CHAPTERS_DIR / "catalyst.yaml").read_text().replace("    bag: legendary_bag\n", "", 1)
    assert check_catalyst_chapter(_chapter(text)) == ["X7.1 reward"]


def test_nothing_depends_on_a_side_quest_yaml():
    side, hits = set(SIDE), []
    for p in CHAPTERS_DIR.glob("*.yaml"):
        for q in parse_chapter(p.read_text())["quests"]:
            hits += [(p.name, q["node"], d) for d in q["deps"] if d in side]
    assert hits == []


def test_nothing_depends_on_a_side_quest_snbt():
    side = {quest_id(n) for n in SIDE}
    hits = []
    for p in (CHAPTERS_DIR.parent.parent / "config/ftbquests/quests/chapters").glob("*.snbt"):
        hits += [(p.name, q, d) for q, ds in check_quests.quest_deps(p.read_text()).items() for d in ds if d in side]
    assert hits == []
