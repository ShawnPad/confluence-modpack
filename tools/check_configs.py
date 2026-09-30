"""Check that every config the pack ships reached the server unchanged (v0.3 Task 9 review, I3).

The pack ships whole generated config files under config/, each with a value it pins on purpose:
config/tombstone-common.toml (lost_tablet_search_outside_world = false; D110) and config/twilightforest-common.toml
(disableUncraftingTable = true; D69 (5)). NeoForge can undo such a value with nothing worse than a WARN. Its
ConfigTracker.loadConfig (loader-4.0.44.jar!net/neoforged/fml/config/ConfigTracker.class) handles two cases:
  - A file its spec calls incorrect is logged "Configuration file {} is not correct. Correcting" (offsets 18-28, with the
    file's path). The file is then corrected and written back (offsets 37-49). ModConfigSpec.correct
    (neoforge-21.1.250-universal.jar) re-adds a missing key at its default and removes a key the spec lacks
    (Iterator.remove, offsets 523-544). So a key a mod renamed silently reverts to the mod's default.
  - A file it cannot read or parse (IOException or ParsingException, exception table 0-52 -> 105) is logged "Failed to
    load config {}: {}. Attempting to recreate" (offsets 107-122, with the file name). The file is then deleted and
    recreated with defaults (offsets 127-137).
A mod that renames its config file leaves the pack's copy unread, just as silently. ConfigTracker logs each file a mod
registers, at DEBUG, as "Config file {} for {} tracking" (logs/debug.log; log4j2.xml in the same jar rolls it at every
start and at 200 MB, and a headless boot writes about 2.5 MB, so it holds this boot only).
So, after a boot, for every config/**/*.toml the pack ships:
  - logs/debug.log shows a mod tracking it under that name;
  - logs/latest.log names it in neither WARN message;
  - the server's copy under RUN_DIR/config/ is byte-identical to the pack's.
The pinned values themselves are checked by tools/tests/test_shipped_configs.py.

Usage, from pack/:  python3 tools/check_configs.py [RUN_DIR]   (default .run/server). tools/server_boot.sh runs it after
every boot. Prints one summary line and exits 0, or prints each problem and exits 1.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORRECTED = re.compile(r"Configuration file (.+?) is not correct\. Correcting")
RECREATED = re.compile(r"Failed to load config (.+?): .*Attempting to recreate")
TRACKED = re.compile(r"\]: Config file (.+?) for \S+ tracking$")


def shipped(root=ROOT):
    """Paths of the shipped config/**/*.toml files, relative to config/, with '/' separators."""
    base = root / "config"
    return sorted(p.relative_to(base).as_posix() for p in base.rglob("*.toml"))


def read_lines(log, problems):
    if log.is_file():
        return log.read_text(encoding="utf-8", errors="replace").splitlines()
    problems.append(f"{log}: missing; boot the server first")
    return []


def check(run, root=ROOT):
    """Return (the shipped paths, every problem found) for the server install at `run`."""
    files, problems = shipped(root), []
    lines = read_lines(run / "logs" / "latest.log", problems)
    debug = read_lines(run / "logs" / "debug.log", problems)
    tracked = {m.group(1).replace("\\", "/") for m in map(TRACKED.search, debug) if m}
    for rel in files:
        if rel not in tracked:
            problems.append(f"config/{rel}: no mod tracks a config file of that name (debug.log); the pack's copy is unread")
        for line in lines:
            m = CORRECTED.search(line)
            # The "not correct" line carries the file's path, the "recreate" line its name under config/.
            path = m.group(1).replace("\\", "/") if m else None
            if path is not None and (path == rel or ("/" + path).endswith("/config/" + rel)):
                problems.append(f"config/{rel}: NeoForge corrected it on load (latest.log: {line.strip()})")
            m = RECREATED.search(line)
            if m and m.group(1).replace("\\", "/") == rel:
                problems.append(f"config/{rel}: NeoForge could not parse it and recreated it (latest.log: {line.strip()})")
        installed = run / "config" / rel
        if not installed.is_file():
            problems.append(f"config/{rel}: not installed at {installed}")
        elif installed.read_bytes() != (root / "config" / rel).read_bytes():
            problems.append(f"config/{rel}: the server's copy differs from the pack's ({installed})")
    return files, problems


def main(argv):
    run = Path(argv[1]) if len(argv) > 1 else ROOT / ".run" / "server"
    files, problems = check(run)
    for p in problems:
        print("  BAD " + p)
    print(f"check_configs: {len(files)} shipped config(s) checked, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
