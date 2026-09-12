"""Scaffold an FTB Quests chapter (SNBT + lang) from tools/chapters/<name>.yaml.
Refuses to overwrite an existing chapter file (spec §5.5). Layout: column = dependency depth, row = order in file.
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTS = ROOT / "config" / "ftbquests" / "quests"
MAX_ID = 0x7FFFFFFFFFFFFFFF  # Java Long.MAX_VALUE


def quest_id(node: str) -> str:
    # FTB Quests 1.21.1 reads string ids with Long.parseLong(id, 16) (BaseQuestFile.readID(Tag), QuestObjectBase.parseCodeString,
    # branch 1.21.1/main), which throws for values above Long.MAX_VALUE: readID then falls back to a random newID() and
    # parseCodeString to 0L, so such a quest gets a fresh id on every load and any dependency on it is silently dropped.
    # readID(long) also rerolls 0 and 1. So: clear the top bit and floor at 2 (deviation from the plan, review finding 1).
    h = int(hashlib.sha1(f"confluence:{node}".encode()).hexdigest()[:16], 16) & MAX_ID
    return f"{max(h, 2):016X}"


def parseable_id(hex_id: str) -> bool:
    """True when FTB Quests' readID accepts it: 16 hex digits, 2 <= value <= Long.MAX_VALUE."""
    try:
        v = int(hex_id, 16)
    except (TypeError, ValueError):
        return False
    return len(hex_id) == 16 and 2 <= v <= MAX_ID


def _val(v: str):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [x.strip().strip('"') for x in inner.split(",")] if inner else []
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    if v.isdigit():
        return int(v)
    if v in ("true", "false"):
        return v == "true"
    return v


def parse_chapter(text: str) -> dict:
    ch: dict = {"quests": []}
    cur = None
    for raw in text.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        if raw.startswith("  - "):
            cur = {}
            ch["quests"].append(cur)
            k, v = raw[4:].split(":", 1)
            cur[k.strip()] = _val(v)
        elif raw.startswith("    ") and cur is not None:
            k, v = raw.strip().split(":", 1)
            cur[k.strip()] = _val(v)
        elif raw.startswith("quests:"):
            continue
        else:
            k, v = raw.split(":", 1)
            ch[k.strip()] = _val(v)
    for q in ch["quests"]:
        q.setdefault("deps", [])
        q.setdefault("coins", 3)
        q.setdefault("desc", "")
        q.setdefault("consume", False)
    return ch


def validate_chapter(ch: dict) -> list[str]:
    """Problems that FTB Quests would swallow silently (no log line) rather than reject."""
    problems = []
    if not parseable_id(str(ch.get("group", ""))):
        # BaseQuestFile.readChapterGroupsFile / readChapterFiles (1.21.1/main): an unparseable group id gets a random id
        # and `group:` resolves via parseCodeString -> 0L -> the default chapter group.
        problems.append(f'group "{ch.get("group")}" is not a parseable FTB Quests id (16 hex digits, first digit 0-7, not 0 or 1)')
    for q in ch["quests"]:
        if q["consume"] and not q["task"].startswith("item:"):
            problems.append(f'{q["node"]}: consume is only meaningful on an item task (ItemTask.consume_items)')
    return problems


def _task(q: dict, tid: str) -> str:
    kind, _, rest = q["task"].partition(":")
    if kind == "item":
        parts = rest.split(":")
        count = int(parts[2]) if len(parts) == 3 else 1
        item = ":".join(parts[:2])
        # ItemTask (1.21.1/main) writeData: `item` is saved with count 1, the requirement is a task-level long `count`
        # (readData: `count = Math.max(nbt.getLong("count"), 1L)`) and `consume_items` is a task key, not a quest key
        # (review findings 3 and 4). Keys alphabetical, as FTB Quests writes them.
        keys = []
        if q["consume"]:
            keys.append("consume_items: true")
        if count > 1:
            keys.append(f"count: {count}L")
        keys += [f'id: "{tid}"', f'item: {{ count: 1, id: "{item}" }}', 'type: "item"']
        return "{ " + " ".join(keys) + " }"
    if kind == "dimension":
        return f'{{ dimension: "{rest}" id: "{tid}" type: "dimension" }}'
    if kind == "kill":
        ent, n = rest.rsplit(":", 1)
        return f'{{ entity: "{ent}" id: "{tid}" type: "kill" value: {n}L }}'
    return f'{{ id: "{tid}" type: "checkmark" }}'


def _depth(q: dict, by_node: dict, memo: dict) -> int:
    if q["node"] in memo:
        return memo[q["node"]]
    d = 0
    for dep in q["deps"]:
        if dep in by_node:
            d = max(d, _depth(by_node[dep], by_node, memo) + 1)
    memo[q["node"]] = d
    return d


def render_snbt(ch: dict) -> str:
    by_node = {q["node"]: q for q in ch["quests"]}
    memo: dict = {}
    rows_at: dict = {}
    out = ["{", "\tdefault_hide_dependency_lines: false", '\tdefault_quest_shape: "rsquare"',
           f'\tfilename: "{ch["chapter"]}"', f'\tgroup: "{ch["group"]}"',
           f'\ticon: {{ id: "{ch["icon"]}" }}', f'\tid: "{quest_id("chapter:" + ch["chapter"])}"',
           "\timages: [ ]", f'\torder_index: {ch["order"]}', '\tprogression_mode: "flexible"',
           "\tquest_links: [ ]", "\tquests: ["]
    for q in ch["quests"]:
        qid = quest_id(q["node"])
        col = _depth(q, by_node, memo)
        row = rows_at.get(col, 0)
        rows_at[col] = row + 1
        deps = ", ".join(f'"{quest_id(d)}"' for d in q["deps"])
        rewards = []
        if q["coins"]:
            rewards.append(f'{{ id: "{quest_id(q["node"] + ":coin")}" item: {{ count: {q["coins"]}, id: "kubejs:coin" }} type: "item" }}')
        out.append("\t\t{")
        if deps:
            out.append(f"\t\t\tdependencies: [{deps}]")
        out.append(f'\t\t\tid: "{qid}"')
        out.append(f"\t\t\trewards: [{', '.join(rewards)}]")
        out.append(f"\t\t\ttasks: [{_task(q, quest_id(q['node'] + ':task'))}]")
        out.append(f"\t\t\tx: {col * 2}.0d")
        out.append(f"\t\t\ty: {row * 2}.0d")
        out.append("\t\t}")
    out += ["\t]", "}", ""]
    return "\n".join(out)


def render_lang(ch: dict) -> str:
    out = ["{"]
    for q in ch["quests"]:
        qid = quest_id(q["node"])
        out.append(f'\tquest.{qid}.title: "{q["title"]}"')
        desc = f'"[{q["node"]}]"'
        if q["desc"]:
            desc += f', "{q["desc"]}"'
        out.append(f"\tquest.{qid}.quest_desc: [{desc}]")
    out += ["}", ""]
    return "\n".join(out)


def main(paths: list[str]) -> int:
    chapter_lang = QUESTS / "lang" / "en_us" / "chapter.snbt"
    titles = {}
    if chapter_lang.exists():
        for line in chapter_lang.read_text().splitlines():
            if line.strip().startswith("chapter."):
                k, v = line.strip().split(":", 1)
                titles[k] = v.strip()
    for p in paths:
        ch = parse_chapter(Path(p).read_text())
        problems = validate_chapter(ch)
        if problems:
            for m in problems:
                print(f"{p}: {m}")
            return 1
        target = QUESTS / "chapters" / f"{ch['chapter']}.snbt"
        if target.exists():
            print(f"refusing to overwrite {target}")
            return 1
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_snbt(ch))
        lang = QUESTS / "lang" / "en_us" / "chapters" / f"{ch['chapter']}.snbt"
        lang.parent.mkdir(parents=True, exist_ok=True)
        lang.write_text(render_lang(ch))
        titles[f"chapter.{quest_id('chapter:' + ch['chapter'])}.title"] = f'"{ch["title"]}"'
        print("wrote", target, "and", lang)
    chapter_lang.write_text("{\n" + "\n".join(f"\t{k}: {v}" for k, v in sorted(titles.items())) + "\n}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
