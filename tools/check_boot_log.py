"""Fail a boot on any ERROR or FATAL line in logs/latest.log that tools/boot_allowlist.txt does not explain (v0.3 Task 8c), on
any Minecraft missing-tag WARN (never allowlisted), and on a Moonlight generated-pack set other than the pinned one (v0.3 Task
10b, D134).

Usage: python3 tools/check_boot_log.py RUN_DIR [--allowlist PATH]     (tools/server_boot.sh runs it last, before BOOT OK)

Lines are split on '\n' only, each losing one trailing '\r', so a line number is the one `grep -n` prints (a form feed or a
U+2028 inside a message is not a line break). A record is one log4j header line at level ERROR or FATAL,
    [01Oct2026 20:47:52.695] [Worker-Main-10/ERROR] [net.minecraft.tags.TagLoader/]: Couldn't load tag ...
plus the lines after it up to the next header line of any level (a TagLoader reference list, a stack trace, a printed
'[1, 2, 3]'). A header is HEADER below; the thread name may hold ']' (the shortest thread then '/<LEVEL>] [' wins). Its text,
the one an allowlist entry is matched against, drops the timestamp and the thread/level bracket: it starts at the logger
bracket ("[net.minecraft.tags.TagLoader/]: ...") and joins the continuation lines with '\n'. An entry must match the WHOLE
text (re.fullmatch), so an entry for one record never covers a longer one. A '[' line that is no header but carries
'/ERROR]' or '/FATAL]' is reported as an unknown record whatever the allowlist says (fail closed); it stays a continuation
line of the record before it.

The log must also hold the line the server prints when it finished starting, an INFO header whose text starts
"[net.minecraft.server.dedicated.DedicatedServer/]: Done (" (console.log prints it as "[minecraft/DedicatedServer]: Done (").
Without it the log is INCOMPLETE: the records after the crash point were never written.

One WARN is a failing record too: vanilla MappedRegistry's
    [02Oct2026 00:01:31.973] [main/WARN] [net.minecraft.core.MappedRegistry/]: Not all defined tags for registry ResourceKey[...
(its text fullmatches MISSING_TAGS, for any registry: worldgen/biome, item, block, ...). Some data pack declares a tag that no
loaded pack defines: on 2026-10-02 it was the six biome tags of Supplementaries' lost generated pack (D134); before D132,
Allthemodium's dead item tags. Normal boots since D132 log it 0 times. It is never allowlisted, mechanically: like a suspect
line, it is an unknown record whatever the allowlist says (printed with "(missing-tag WARN: never allowlisted)"), so an entry
that would match it is reported unused. The same text at another level (INFO, DEBUG) is not a record. Every other WARN is
ignored here: the config WARNs belong to tools/check_configs.py and the rest are noise (the allowlist header lists the known
ones). The summary line counts "failing records (ERROR, FATAL, missing-tag WARN)".

The allowlist holds one regex per line, each right below its own '#' comment line(s) naming the mod and saying why the line is
harmless: a comment covers only the entry right below it. Blank lines separate entries; a regex with no comment right above
it, a regex that does not compile and a repeated regex all fail the check.

Moonlight's generated data packs (D134). Supplementaries and Amendments each register a SERVER_DATA pack generator with
Moonlight from their mod constructors, and Moonlight 3.6.4 keeps them in an unsynchronised HashMultimap, so a parallel mod
construction can lose one with no log line of its own. Moonlight logs one INFO line per data load naming the generators it runs
(DynamicResourcesInternals.lambda$init$2, moonlight-1.21.1-3.6.4-neoforge.jar, javap -c offsets 104-112; it returns before
logging when the list is empty, offsets 15-24):
    [02Oct2026 00:05:38.524] [main/INFO] [Moonlight/]: Starting runtime resource generation for pack type SERVER_DATA with
    generators [supplementaries:generated_pack, amendments:generated_server_pack]
GENERATOR fullmatches it against a header's text on INFO lines of any thread (a /reload may log it again, from the thread
running the reload [UNVERIFIED]). For each pack type in EXPECTED_DYNAMIC_PACKS the log must hold at least one such line, and
every line of that type must name exactly the pinned set (compared as sets: the order varies per JVM). A missing id fails (a
lost provider), and so does an unexpected one, so the pin follows the mod list. Lines of other pack types are ignored.

Output: a summary line, then one UNKNOWN block per record no entry matches (and per missing-tag WARN or suspect line), then
the entries no record used (informational: a fixed mod leaves a stale entry), then "dynamic packs: K Moonlight generation
line(s), B bad" and one line per problem. Every part is printed whatever the others found. Exit status: 0 every record
allowlisted and no dynamic-pack problem; 1 an unknown record, a dynamic-pack problem, an incomplete log or no log; 2 a usage
error (argparse); 3 a missing or bad allowlist. tools/server_boot.sh labels 2 and 3 apart from 1.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / "tools" / "boot_allowlist.txt"
HEADER = re.compile(r"^\[[^\]]*\] \[(?P<thread>.*?)/(?P<level>[A-Z]+)\] (?P<rest>\[.*)$")
FAILING = {"ERROR", "FATAL"}
SUSPECT = re.compile(r"/(ERROR|FATAL)\]")
DONE = "[net.minecraft.server.dedicated.DedicatedServer/]: Done ("
EXIT_UNKNOWN, EXIT_USAGE, EXIT_ALLOWLIST = 1, 2, 3
# The one WARN that fails like an ERROR (docstring): vanilla MappedRegistry's missing-tag line.
MISSING_TAGS = re.compile(r"\[net\.minecraft\.core\.MappedRegistry/\]: Not all defined tags for registry .*")
# Moonlight's generator line and the generators each pack type must run (docstring; D134). The ids are the providers' names:
# supplementaries-1.21.1-3.9.9-neoforge.jar ModServerDynamicResources.<init> passes "generated_pack" to Supplementaries.res, and
# amendments-1.21-2.1.10-neoforge.jar WallLanternServerResources.<init> passes "generated_server_pack" to Amendments.res
# (javap -c, offsets 1-3 in each); both are SERVER_DATA providers (DynamicServerResourceProvider). Every logged boot since
# 2026-09-11 names exactly these two, except the three that lost Supplementaries' (D134).
GENERATOR = re.compile(r"\[Moonlight/\]: Starting runtime resource generation for pack type (?P<type>[A-Z_]+) with generators "
                       r"\[(?P<ids>[^\]]*)\]")
EXPECTED_DYNAMIC_PACKS = {"SERVER_DATA": frozenset({"supplementaries:generated_pack", "amendments:generated_server_pack"})}


def log_lines(text: str) -> list[str]:
    """The lines as grep counts them: split on '\n' only, one trailing '\r' dropped from each."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def never_allowlisted(text: str) -> bool:
    """Whether a failing record is the missing-tag WARN, which no allowlist entry may cover (docstring). Its header line is the
    record's first line; failing() only lets that text through at level WARN (or ERROR/FATAL, which the policy covers too)."""
    return MISSING_TAGS.fullmatch(text.split("\n", 1)[0]) is not None


def failing(level: str, rest: str) -> bool:
    """Whether a header at `level` with text `rest` starts a failing record: ERROR, FATAL, or the missing-tag WARN."""
    return level in FAILING or (level == "WARN" and MISSING_TAGS.fullmatch(rest) is not None)


def scan(text: str):
    """(records, suspects, done): [(1-based header line, record text)] for each failing record (ERROR, FATAL, the missing-tag
    WARN); [(line, text)] for each '[' line that is no header but names an ERROR or FATAL level; and whether the Done line is
    there."""
    out, suspects, current, done = [], [], None, False
    for n, line in enumerate(log_lines(text), 1):
        m = HEADER.match(line) if line.startswith("[") else None
        if m:
            current = None
            if failing(m.group("level"), m.group("rest")):
                current = [n, [m.group("rest")]]
                out.append(current)
            elif m.group("level") == "INFO" and m.group("rest").startswith(DONE):
                done = True
            continue
        if line.startswith("[") and SUSPECT.search(line):
            suspects.append((n, line))
        if current is not None:
            current[1].append(line)
    return [(n, "\n".join(lines)) for n, lines in out], suspects, done


def records(text: str) -> list[tuple[int, str]]:
    """[(1-based line number of the header, record text)] for each failing record."""
    return scan(text)[0]


def generator_lines(text: str) -> list[tuple[int, str, frozenset[str]]]:
    """[(1-based line, pack type, generator ids)] for each Moonlight generation line: an INFO header, any thread, whose text
    fullmatches GENERATOR."""
    out = []
    for n, line in enumerate(log_lines(text), 1):
        m = HEADER.match(line) if line.startswith("[") else None
        g = GENERATOR.fullmatch(m.group("rest")) if m and m.group("level") == "INFO" else None
        if g:
            out.append((n, g.group("type"), frozenset(i.strip() for i in g.group("ids").split(",") if i.strip())))
    return out


def dynamic_pack_problems(text: str, expected=EXPECTED_DYNAMIC_PACKS) -> list[str]:
    """One line per problem: an expected pack type with no generation line, or a line of an expected type whose generator set
    is not the pinned one (missing and unexpected ids named, sorted)."""
    lines, problems = generator_lines(text), []
    for kind, want in expected.items():
        hits = [(n, ids) for n, k, ids in lines if k == kind]
        if not hits:
            problems.append(f"NO DYNAMIC PACK LINE latest.log: no Moonlight generation line for pack type {kind} (expected "
                            f"[{', '.join(sorted(want))}]); Moonlight logs none when no generator is registered")
        problems += [f"DYNAMIC PACKS latest.log:{n}: {kind} missing [{', '.join(sorted(want - ids))}], unexpected "
                     f"[{', '.join(sorted(ids - want))}]" for n, ids in hits if ids != want]
    return problems


def load_allowlist(path: Path) -> list[re.Pattern]:
    """The compiled entries. Raises ValueError naming the line of an undocumented, invalid or repeated entry."""
    entries, seen, commented = [], {}, False
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            commented = False
            continue
        if line.lstrip().startswith("#"):
            commented = True
            continue
        if not commented:
            raise ValueError(f"{path.name} line {n}: an entry needs a comment line right above it (the mod, and why it is harmless)")
        if line in seen:
            raise ValueError(f"{path.name} line {n}: repeats line {seen[line]}")
        try:
            entries.append(re.compile(line))
        except re.error as e:
            raise ValueError(f"{path.name} line {n}: not a regex ({e})") from None
        seen[line] = n
        commented = False   # the next entry needs its own comment
    return entries


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="check_boot_log.py",
        description="Check logs/latest.log's failing records (ERROR, FATAL, and Minecraft's missing-tag WARN, which is never "
                    "allowlisted) against the allowlist, and Moonlight's generated data packs against the pinned set.")
    parser.add_argument("run_dir", type=Path, metavar="RUN_DIR")
    parser.add_argument("--allowlist", type=Path, default=ALLOWLIST, metavar="PATH")
    args = parser.parse_args(argv)
    log = args.run_dir / "logs" / "latest.log"
    if not log.is_file():
        print(f"MISSING LOG {log}")
        return EXIT_UNKNOWN
    if not args.allowlist.is_file():
        print(f"MISSING ALLOWLIST {args.allowlist}")
        return EXIT_ALLOWLIST
    try:
        entries = load_allowlist(args.allowlist)
    except ValueError as e:
        print(f"BAD ALLOWLIST {e}")
        return EXIT_ALLOWLIST
    # bytes, not text mode: text mode turns a lone '\r' into a line break, which grep -n does not count (round 3, H4)
    log_text = log.read_bytes().decode("utf-8", "replace")
    recs, suspects, done = scan(log_text)
    if not done:
        print(f"INCOMPLETE LOG logs/latest.log has no '{DONE}' line: the server never finished starting")
    used, unknown = set(), []
    for n, text in recs:
        if never_allowlisted(text):   # mechanical, like the suspect lines below: no entry is consulted
            unknown.append((n, "(missing-tag WARN: never allowlisted) " + text))
            continue
        hit = next((e for e in entries if e.fullmatch(text)), None)
        if hit is None:
            unknown.append((n, text))
        else:
            used.add(hit.pattern)
    unknown += [(n, "(not a log4j header line) " + line) for n, line in suspects]
    unknown.sort()
    total = len(recs) + len(suspects)
    print(f"boot log: {total} failing records (ERROR, FATAL, missing-tag WARN) in logs/latest.log, {total - len(unknown)} "
          f"allowlisted, {len(unknown)} unknown")
    for n, text in unknown:
        first, *rest = text.split("\n")
        print(f"  UNKNOWN latest.log:{n}: {first}")
        for line in rest[:20]:
            print(f"  {line}")
    for e in entries:
        if e.pattern not in used:
            print(f"  (unused allowlist entry: {e.pattern})")
    problems = dynamic_pack_problems(log_text)
    checked = sum(1 for _, kind, _ in generator_lines(log_text) if kind in EXPECTED_DYNAMIC_PACKS)
    print(f"dynamic packs: {checked} Moonlight generation line(s), {len(problems)} bad")
    for p in problems:
        print(f"  {p}")
    return EXIT_UNKNOWN if (unknown or not done or problems) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
