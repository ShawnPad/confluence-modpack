"""Fail a boot on any ERROR or FATAL line in logs/latest.log that tools/boot_allowlist.txt does not explain (v0.3 Task 8c).

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

The allowlist holds one regex per line, each right below its own '#' comment line(s) naming the mod and saying why the line is
harmless: a comment covers only the entry right below it. Blank lines separate entries; a regex with no comment right above
it, a regex that does not compile and a repeated regex all fail the check. WARN lines are never checked here: the config
WARNs belong to tools/check_configs.py and the rest are noise (the allowlist header lists the known ones).

Output: a summary line, then one UNKNOWN block per record no entry matches, then the entries no record used (informational: a
fixed mod leaves a stale entry). Exit status: 0 every record allowlisted; 1 an unknown record, an incomplete log or no log;
2 a usage error (argparse); 3 a missing or bad allowlist. tools/server_boot.sh labels 2 and 3 apart from 1.
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


def log_lines(text: str) -> list[str]:
    """The lines as grep counts them: split on '\n' only, one trailing '\r' dropped from each."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def scan(text: str):
    """(records, suspects, done): [(1-based header line, record text)] for each ERROR or FATAL record; [(line, text)] for each
    '[' line that is no header but names an ERROR or FATAL level; and whether the Done line is there."""
    out, suspects, current, done = [], [], None, False
    for n, line in enumerate(log_lines(text), 1):
        m = HEADER.match(line) if line.startswith("[") else None
        if m:
            current = None
            if m.group("level") in FAILING:
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
    """[(1-based line number of the header, record text)] for each ERROR or FATAL record."""
    return scan(text)[0]


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
    parser = argparse.ArgumentParser(prog="check_boot_log.py", description="Check logs/latest.log's ERROR/FATAL records.")
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
    recs, suspects, done = scan(log.read_bytes().decode("utf-8", "replace"))
    if not done:
        print(f"INCOMPLETE LOG logs/latest.log has no '{DONE}' line: the server never finished starting")
    used, unknown = set(), []
    for n, text in recs:
        hit = next((e for e in entries if e.fullmatch(text)), None)
        if hit is None:
            unknown.append((n, text))
        else:
            used.add(hit.pattern)
    unknown += [(n, "(not a log4j header line) " + line) for n, line in suspects]
    unknown.sort()
    total = len(recs) + len(suspects)
    print(f"boot log: {total} ERROR/FATAL records in logs/latest.log, {total - len(unknown)} allowlisted, {len(unknown)} unknown")
    for n, text in unknown:
        first, *rest = text.split("\n")
        print(f"  UNKNOWN latest.log:{n}: {first}")
        for line in rest[:20]:
            print(f"  {line}")
    for e in entries:
        if e.pattern not in used:
            print(f"  (unused allowlist entry: {e.pattern})")
    return EXIT_UNKNOWN if (unknown or not done) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
