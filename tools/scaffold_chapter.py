"""Scaffold an FTB Quests chapter (SNBT + lang) from tools/chapters/<name>.yaml.
Refuses to overwrite an existing chapter file (spec §5.5). Layout: column = dependency depth, row = order in file.

The lang file is ONE flat file, config/ftbquests/quests/lang/en_us.snbt, rebuilt from every tools/chapters/*.yaml
plus GROUPS on every run: FTB Quests 2101.1.35 lists `lang/` non-recursively and keeps only names matching
`^\\w+\\.snbt$` (TranslationManager.loadFromNBT / isValidLangFile, research/phase7-ftbquests-translations.md §2), so the
per-type `lang/en_us/{chapter,chapter_group}.snbt` + `chapters/*.snbt` layout the v0.1 build copied from ATM10 loaded
zero entries — ATM10 ships the FTB Quests Lang Splitter mod to merge that layout; this pack does not (§5).
`--lang-only` rebuilds the lang file without scaffolding chapters (chapter SNBT is untouched; quest ids are
deterministic in `node`, so the two never drift).
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTS = ROOT / "config" / "ftbquests" / "quests"
MAX_ID = 0x7FFFFFFFFFFFFFFF  # Java Long.MAX_VALUE
LANG = QUESTS / "lang" / "en_us.snbt"
CHAPTERS_DIR = ROOT / "tools" / "chapters"
# Chapter-group titles. Ids are the ones committed in config/ftbquests/quests/chapter_groups.snbt (D63); the key shape
# is `chapter_group.<%016X id>.title` (TranslationManager.makeKey, QuestObjectType.CHAPTER_GROUP, report §2).
GROUPS = {"0C0F1A0000000001": "Trunk", "0C0F1A0000000002": "Spurs", "0C0F1A0000000003": "Shop"}


def quest_id(node: str) -> str:
    # FTB Quests 1.21.1 reads string ids with Long.parseLong(id, 16) (BaseQuestFile.readID(Tag), QuestObjectBase.parseCodeString,
    # branch 1.21.1/main), which throws for values above Long.MAX_VALUE: readID then falls back to a random newID() and
    # parseCodeString to 0L, so such a quest gets a fresh id on every load and any dependency on it is silently dropped.
    # readID(long) also rerolls 0 and 1. So: clear the top bit and floor at 2 (deviation from the plan, review finding 1).
    h = int(hashlib.sha1(f"confluence:{node}".encode()).hexdigest()[:16], 16) & MAX_ID
    return f"{max(h, 2):016X}"


def load_reward_tables(folder: Path | None = None) -> dict[str, int]:
    """Map reward-table name -> the long FTB Quests uses in a quest reward's `table_id`.

    A reward table's long id IS its SNBT hex `id:`: BaseQuestFile.loadRewardTableFile builds it as
    `new RewardTable(readID(tableNBT.get("id")), this, filename)` and readID(Tag) parses the string with
    `Long.parseLong(id, 16)` (branch 1.21.1/main, L779 and L1364-1371); RandomReward.writeData then writes
    `nbt.putLong("table_id", table.id)` and readData resolves it with `file.getRewardTable(id)` (RandomReward.java
    L49/L65-67). So `table_id` is derivable after all -- this refutes D58 and the tooling report §4.6, which said the
    long was generated independently of the hex id and had to be wired in the in-game editor.
    Keyed by both the loot_crate `string_id` and the filename stem.
    """
    folder = folder if folder is not None else QUESTS / "reward_tables"
    tables: dict[str, int] = {}
    if not folder.exists():
        return tables
    for path in sorted(folder.glob("*.snbt")):
        text = path.read_text()
        m = re.search(r'^\tid: "([0-9A-Fa-f]{16})"', text, re.M)
        if not m:
            continue
        tables[path.stem] = int(m.group(1), 16)
        s = re.search(r'string_id: "([^"]+)"', text)
        if s:
            tables[s.group(1)] = int(m.group(1), 16)
    return tables


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
        q.setdefault("repeat", False)
        q.setdefault("bag", "")
    return ch


def validate_chapter(ch: dict, tables: dict[str, int] | None = None) -> list[str]:
    """Problems that FTB Quests would swallow silently (no log line) rather than reject."""
    tables = load_reward_tables() if tables is None else tables
    problems = []
    if not parseable_id(str(ch.get("group", ""))):
        # BaseQuestFile.readChapterGroupsFile / readChapterFiles (1.21.1/main): an unparseable group id gets a random id
        # and `group:` resolves via parseCodeString -> 0L -> the default chapter group.
        problems.append(f'group "{ch.get("group")}" is not a parseable FTB Quests id (16 hex digits, first digit 0-7, not 0 or 1)')
    for q in ch["quests"]:
        if q["consume"] and not q["task"].startswith("item:"):
            problems.append(f'{q["node"]}: consume is only meaningful on an item task (ItemTask.consume_items)')
        if q["bag"] and q["bag"] not in tables:
            # An unknown table_id resolves to null in RandomReward.readData and the reward silently pays nothing.
            problems.append(f'{q["node"]}: no reward table named "{q["bag"]}" in config/ftbquests/quests/reward_tables/')
        if q["repeat"] and q["task"].split(":", 1)[0] in ("dimension", "kill", "advancement"):
            # These tasks auto-submit on a player tick (task-shapes §1-§3); a repeatable one re-completes every few seconds.
            problems.append(f'{q["node"]}: repeat on a {q["task"].split(":", 1)[0]} task would re-complete itself')
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
    if kind == "advancement":
        # AdvancementTask (FTB Quests 2101.1.35): keys `advancement` and `criterion`; readData defaults criterion to "" when absent
        # (research/phase7-ftbquests-task-shapes.md §3, §9). rest = "<namespace>:<path>[:<criterion>]" -- the id itself holds one ':'.
        ns, _, tail = rest.partition(":")
        path, _, crit = tail.partition(":")
        keys = [f'advancement: "{ns}:{path}"']
        if crit:
            keys.append(f'criterion: "{crit}"')
        keys += [f'id: "{tid}"', 'type: "advancement"']
        return "{ " + " ".join(keys) + " }"
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


def render_snbt(ch: dict, tables: dict[str, int] | None = None) -> str:
    tables = load_reward_tables() if tables is None else tables
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
        if q["bag"]:
            # LootReward extends RandomReward and is registered as `loot` (RewardTypes L27); it inherits the
            # `table_id` long and always excludes itself from claim-all (LootReward.getExcludeFromClaimAll), so
            # `exclude_from_claim_all` is not written. Keys alphabetical, as FTB Quests writes them.
            rewards.append(f'{{ id: "{quest_id(q["node"] + ":bag")}" table_id: {tables[q["bag"]]}L type: "loot" }}')
        out.append("\t\t{")
        if q["repeat"]:
            # `can_repeat` is a quest-level Tristate: Quest.java holds `private Tristate canRepeat` and writes it as
            # `canRepeat.write(nbt, "can_repeat")` (tag v2101.1.35 L325, read back L446) -- research/phase6-tier0-2-ids-2.md
            # Q3. There is no task-level equivalent, and `consume_items` is NOT a quest key (it is chapter- and
            # task-level only), so the two must not be written in the same place. Keys alphabetical, as FTB Quests writes them.
            out.append("\t\t\tcan_repeat: true")
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


def lang_entries(ch: dict) -> dict[str, str]:
    """Translation keys for one chapter: its title and every quest's title and description (values are SNBT literals).
    No node-id line in quest_desc any more: descs are player-facing (session 10), and check_quests.py finds a node's
    quest through quest_id(node) instead."""
    entries = {f"chapter.{quest_id('chapter:' + ch['chapter'])}.title": f'"{ch["title"]}"'}
    for q in ch["quests"]:
        qid = quest_id(q["node"])
        entries[f"quest.{qid}.title"] = f'"{q["title"]}"'
        if q["desc"]:
            entries[f"quest.{qid}.quest_desc"] = f'["{q["desc"]}"]'
    return entries


def render_lang_text(entries: dict[str, str]) -> str:
    return "{\n" + "\n".join(f"\t{k}: {v}" for k, v in sorted(entries.items())) + "\n}\n"


def render_lang(ch: dict) -> str:
    """One chapter's entries as an SNBT compound (tests and previews); the shipped file merges every chapter."""
    return render_lang_text(lang_entries(ch))


def build_lang(chapter_paths: list[Path]) -> str:
    """The whole lang/en_us.snbt: GROUPS plus every chapter YAML given (normally all of tools/chapters/*.yaml)."""
    entries = {f"chapter_group.{gid}.title": f'"{title}"' for gid, title in GROUPS.items()}
    for p in chapter_paths:
        entries.update(lang_entries(parse_chapter(p.read_text())))
    return render_lang_text(entries)


def main(argv: list[str]) -> int:
    lang_only = "--lang-only" in argv
    paths = [a for a in argv if a != "--lang-only"]
    if not lang_only:
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
            print("wrote", target)
    LANG.parent.mkdir(parents=True, exist_ok=True)
    LANG.write_text(build_lang(sorted(CHAPTERS_DIR.glob("*.yaml"))))
    print("wrote", LANG)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
