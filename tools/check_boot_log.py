"""Fail a boot on any ERROR or FATAL line in logs/latest.log that tools/boot_allowlist.txt does not explain (v0.3 Task 8c), on
any Minecraft missing-tag WARN (never allowlisted), on a Moonlight generated-pack set other than the pinned one (v0.3 Task
10b, D134), and on a game-rule set other than the pinned one or a missing Twilight Forest guard line (v0.3 Task 11d, D137).

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

Game rules (D137). Twilight Forest 4.8.3345's TwilightForestMod.<init> (offset 29) calls TFGameRules.register(), which hands
each of its three Suppliers.memoize suppliers to Util.backgroundExecutor() (twilightforest-1.21.1-4.8.3345-universal.jar,
TFGameRules.lambda$register$2, javap -c offsets 0-14), so up to three Worker-Main threads run GameRules.register at once, an
unsynchronised put into the TreeMap GameRules.GAME_RULE_TYPES (server-1.21.1-20240808.144430-srg.jar, GameRules.<clinit>
offsets 6-17). A racing put can lose any key, vanilla's too (a first-tick NullPointerException at ServerLevel.tick:345 when
playersSleepingPercentage is the one lost), or leave a cycle (`new GameRules()` then runs out of memory), with no log line of
its own. kubejs/startup_scripts/tf_gamerules_guard.js registers the three rules first, on one thread, and logs one INFO line
    [02Oct2026 18:59:31.625] [modloading-worker-0/INFO] [KubeJS Startup/]: startup_scripts:tf_gamerules_guard.js#112:
    confluence tf-gamerules guard OK: registered tfEnforcedProgression, ... before Twilight Forest construction (rules 51 -> 54)
and kubejs/server_scripts/gamerules.js logs one INFO line per server start naming the rules of the server's GameRules and of a
fresh GameRules() (sorted, comma-separated; KubeJS may prefix it with "server_scripts:gamerules.js#<n>: "):
    [02Oct2026 10:18:48.908] [Server thread/INFO] [KubeJS Server/]: confluence gamerules: server 55 [accessories.keep...,
    announceAdvancements, ...]; registry 55 [...]
tools/gamerules.toml pins the names, each with its jar provenance: 51 vanilla, 3 Twilight Forest, 1 Accessories. The log must
hold exactly one guard OK line (any script line number) and exactly one detector line at INFO; a detector line at another
level is reported; each detector line's two counts must match their lists, neither list may repeat a name, each must be
the pinned set (missing and unexpected names reported, so the pin follows the mod list), and the two must be equal. A line
inside another record is not a header line and does not count.

Output: a summary line, then one UNKNOWN block per record no entry matches (and per missing-tag WARN or suspect line), then
the entries no record used (informational: a fixed mod leaves a stale entry), then "game rules: E expected, server S,
registry R, guard G" (", B bad" appended when there are problems) and one line per problem, then "dynamic packs: K Moonlight
generation line(s), B bad" and one line per problem. Every part is printed whatever the others found. Exit status: 0 every
record allowlisted, no game-rule problem and no dynamic-pack problem; 1 an unknown record, a game-rule or dynamic-pack
problem, an incomplete log or no log; 2 a usage error (argparse); 3 a missing or bad allowlist; 4 a missing, unreadable or bad
tools/gamerules.toml. The pin is read after the arguments, so --help and a usage error never depend on it. A bad pin prints
"BAD GAMERULES PIN ..." first and "game rules: not checked (bad pin)" in that section's place, the other parts are printed as
usual, and 4 then wins over 1, so an unknown record under a bad pin shows in the output and not in the status. A missing log
(1) or allowlist (3) still ends the run where it does without a bad pin. tools/server_boot.sh labels 2, 3 and 4 apart from 1.
"""
import argparse
import re
import sys
import tomllib
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / "tools" / "boot_allowlist.txt"
HEADER = re.compile(r"^\[[^\]]*\] \[(?P<thread>.*?)/(?P<level>[A-Z]+)\] (?P<rest>\[.*)$")
FAILING = {"ERROR", "FATAL"}
SUSPECT = re.compile(r"/(ERROR|FATAL)\]")
DONE = "[net.minecraft.server.dedicated.DedicatedServer/]: Done ("
EXIT_UNKNOWN, EXIT_USAGE, EXIT_ALLOWLIST, EXIT_PIN = 1, 2, 3, 4
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
# The game-rule pin, the detector's line and the guard's OK line (docstring; D137).
GAMERULES = ROOT / "tools" / "gamerules.toml"
DETECTOR = re.compile(r"\[KubeJS Server/\]: (?:server_scripts:[^\s#]+#\d+: )?confluence gamerules: server (?P<sn>\d+) "
                      r"\[(?P<s>[^\]]*)\]; registry (?P<rn>\d+) \[(?P<r>[^\]]*)\]")
GUARD_OK = re.compile(r"\[KubeJS Startup/\]: startup_scripts:tf_gamerules_guard\.js#\d+: confluence tf-gamerules guard OK: .+")
NO_GUARD = ("NO GUARD LINE latest.log: no INFO line '[KubeJS Startup/]: startup_scripts:tf_gamerules_guard.js#<n>: confluence "
            "tf-gamerules guard OK: ...'; the Twilight Forest game-rule guard did not run (D137)")
NO_RULES = ("NO GAMERULES LINE latest.log: no INFO line '[KubeJS Server/]: confluence gamerules: ...'; the detector "
            "(kubejs/server_scripts/gamerules.js) never logged, or the server never reached ServerStartingEvent (D137)")


class GameRulePin(NamedTuple):
    """tools/gamerules.toml: the vanilla names in <clinit> order, the [[modded]] entries and the [[register_call]] entries."""
    vanilla: list
    modded: list
    register_calls: list


def load_gamerules(path: Path = GAMERULES) -> GameRulePin:
    """The pin. Raises ValueError naming an empty or malformed vanilla list, a repeated name or id, a modded or register_call list
    that is not a list of tables, or a modded entry without its id or mod."""
    with open(path, "rb") as f:
        data = tomllib.load(f)
    table = data.get("vanilla")
    vanilla = table.get("names") if isinstance(table, dict) else None
    if not vanilla or not isinstance(vanilla, list) or not all(isinstance(name, str) for name in vanilla):
        raise ValueError(f"{path.name}: no vanilla names ([vanilla] names = [...])")
    seen = set()
    for name in vanilla:
        if name in seen:
            raise ValueError(f"{path.name}: vanilla name '{name}' is listed twice")
        seen.add(name)
    modded = data.get("modded") or []
    if not isinstance(modded, list) or not all(isinstance(entry, dict) for entry in modded):
        raise ValueError(f"{path.name}: modded is not a list of tables ([[modded]])")
    for entry in modded:
        rule = entry.get("id")
        if not rule or not isinstance(rule, str):
            raise ValueError(f"{path.name}: a modded entry has no id ({entry})")
        if not entry.get("mod"):
            raise ValueError(f"{path.name}: modded entry '{rule}' has no mod")
        if rule in seen:
            raise ValueError(f"{path.name}: modded id '{rule}' is " + ("also a vanilla name" if rule in vanilla else
                                                                         "listed twice"))
        seen.add(rule)
    calls = data.get("register_call") or []
    if not isinstance(calls, list) or not all(isinstance(entry, dict) for entry in calls):
        raise ValueError(f"{path.name}: register_call is not a list of tables ([[register_call]])")
    return GameRulePin(list(vanilla), list(modded), list(calls))


def expected_gamerules(pin: GameRulePin) -> frozenset[str]:
    """Every rule name the pin says a boot must register."""
    return frozenset(pin.vanilla) | {m["id"] for m in pin.modded}


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


def gamerule_problems(text: str, expected) -> tuple[str, list[str]]:
    """(summary line, one line per problem) for the guard's OK line and the detector's line (docstring; D137)."""
    guards, detectors, problems = [], [], []
    for n, line in enumerate(log_lines(text), 1):
        m = HEADER.match(line) if line.startswith("[") else None
        if not m:
            continue
        if m.group("level") == "INFO" and GUARD_OK.fullmatch(m.group("rest")):
            guards.append(n)
        d = DETECTOR.fullmatch(m.group("rest"))
        if d:
            detectors.append((n, m.group("level"), d))
    if not guards:
        problems.append(NO_GUARD)
    elif len(guards) > 1:
        problems.append(f"GUARD latest.log: {len(guards)} guard OK lines (lines {', '.join(map(str, guards))}); expected "
                        "exactly one per boot")
    problems += [f"GAMERULES latest.log:{n}: the detector line is logged at {level}, not INFO"
                 for n, level, _ in detectors if level != "INFO"]
    found = [(n, d) for n, level, d in detectors if level == "INFO"]
    if not found:
        problems.append(NO_RULES)
    elif len(found) > 1:
        problems.append(f"GAMERULES latest.log: {len(found)} detector lines (lines {', '.join(str(n) for n, _ in found)}); "
                        "expected exactly one per boot")
    for n, d in found:
        lists = {}
        for which, count, names in (("server", d.group("sn"), d.group("s")), ("registry", d.group("rn"), d.group("r"))):
            names = [x for x in names.split(",") if x]
            lists[which] = set(names)
            if int(count) != len(names):
                problems.append(f"GAMERULES latest.log:{n}: {which} count {count} but {len(names)} names listed")
            problems += [f"GAMERULES latest.log:{n}: {which} lists {x} twice" for x in sorted({x for x in names
                                                                                               if names.count(x) > 1})]
            if set(names) != expected:
                problems.append(f"GAMERULES latest.log:{n}: {which} missing [{', '.join(sorted(expected - set(names)))}], "
                                f"unexpected [{', '.join(sorted(set(names) - expected))}]")
        if lists["server"] != lists["registry"]:
            problems.append(f"GAMERULES latest.log:{n}: server and registry differ: only in server "
                            f"[{', '.join(sorted(lists['server'] - lists['registry']))}], only in registry "
                            f"[{', '.join(sorted(lists['registry'] - lists['server']))}]")
    counts = {k: "/".join(d.group(k) for _, d in found) or "none" for k in ("sn", "rn")}
    guard = "OK" if len(guards) == 1 else "missing" if not guards else f"{len(guards)} lines"
    summary = (f"game rules: {len(expected)} expected, server {counts['sn']}, registry {counts['rn']}, guard {guard}"
               + (f", {len(problems)} bad" if problems else ""))
    return summary, problems


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
                    "allowlisted) against the allowlist, the game rules and the Twilight Forest guard line against "
                    "tools/gamerules.toml, and Moonlight's generated data packs against the pinned set.")
    parser.add_argument("run_dir", type=Path, metavar="RUN_DIR")
    parser.add_argument("--allowlist", type=Path, default=ALLOWLIST, metavar="PATH")
    args = parser.parse_args(argv)
    expected = None
    try:
        expected = expected_gamerules(load_gamerules(GAMERULES))
    except (OSError, tomllib.TOMLDecodeError, ValueError) as e:
        print(f"BAD GAMERULES PIN {GAMERULES}: {e}")
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
    rules_summary, rule_problems = ("game rules: not checked (bad pin)", []) if expected is None else (
        gamerule_problems(log_text, expected))
    print(rules_summary)
    for p in rule_problems:
        print(f"  {p}")
    problems = dynamic_pack_problems(log_text)
    checked = sum(1 for _, kind, _ in generator_lines(log_text) if kind in EXPECTED_DYNAMIC_PACKS)
    print(f"dynamic packs: {checked} Moonlight generation line(s), {len(problems)} bad")
    for p in problems:
        print(f"  {p}")
    if expected is None:
        return EXIT_PIN
    return EXIT_UNKNOWN if (unknown or not done or problems or rule_problems) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
