"""Diff the tree against the questbook (spec §5.2, §5.4)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREE = ROOT.parent / "progression" / "combined-tree.md"
QUESTS = ROOT / "config" / "ftbquests" / "quests"
NO_QUEST = {"X0.3", "X3.3"}          # audit-only nodes with nothing to do (spec §5.2)
FORBIDDEN = re.compile(r'"(kubejs:(twilight_key|other_key|end_focus|astral_focus|confluence_catalyst)|allthemodium:[a-z_]*(allthemodium|vibranium|unobtainium)[a-z_]*|ad_astra:(desh|ostrum|calorite|etrium)[a-z_]*|allthemodium:piglich_heart|cataclysm:[a-z_]*|twilightforest:knightmetal[a-z_]*|undergarden:forgotten[a-z_]*)"')
NODE = re.compile(r"^- \[([A-Z]\d+\.\d+)\]")
# Skip source-pack citations such as "ozone [T4.2] pattern" / "atm10 [X2.1]" / "per evolution [M2.1]"
# (combined-tree.md Legend L49 and gate lines L175, L197, L236): they cite the source trees, not our gates.
GATE_REF = re.compile(r"(?<!ozone )(?<!atm10 )(?<!evolution )\[([A-Z]\d+\.\d+)\]")
TIER = re.compile(r"^### (Tier (\d+)|Top|Bypass)")


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


def quests_in_lang(text: str) -> dict[str, str]:
    found = {}
    # `\[\s*"` (plan L1634 has `\["`): the scaffolder writes `quest_desc: ["[D1.1]", "text"]` inline, but the editor
    # writes a multi-entry list one entry per line (research/phase6-tooling-worldgen-quests.md §4.7 L509-512), and
    # spec §5.5 finishes prose in the editor and copies the files back, so the checker must accept both shapes.
    for m in re.finditer(r'quest\.([0-9A-F]{16})\.quest_desc: \[\s*"\[([A-Z]+\d*\.\d+)\]"', text):
        found[m.group(2)] = m.group(1)
    return found


def forbidden_in_table(text: str) -> list[str]:
    return [m.group(1) for m in FORBIDDEN.finditer(text)]


def main(argv: list[str]) -> int:
    tiers = {int(t) for t in argv[argv.index("--tiers") + 1].split(",")} if "--tiers" in argv else {0, 1, 2}
    expected = tree_nodes(TREE.read_text(), tiers)
    lang_text = "".join(p.read_text() for p in (QUESTS / "lang" / "en_us" / "chapters").glob("*.snbt"))
    have = quests_in_lang(lang_text)
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
    print(f"nodes: {len(expected)} expected, {len(missing)} missing; deps: {len(mismatched)} mismatched; reward tables: {len(tables)}, forbidden items: {len(forbidden)}")
    for m in missing:
        print("  MISSING quest for", m)
    for n, d in mismatched:
        print(f"  DEP {n} should depend on {d}")
    for t, f in forbidden:
        print("  FORBIDDEN", t, f)
    return 1 if (missing or mismatched or forbidden) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
