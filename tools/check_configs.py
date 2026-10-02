"""Check that every config the pack ships reached the server unchanged (v0.3 Task 9 review, I3).

The pack ships whole generated config files under config/, each with a value it pins on purpose:
config/tombstone-common.toml (lost_tablet_search_outside_world = false; D110), config/twilightforest-common.toml
(disableUncraftingTable = true; D69 (5)) and config/fml.toml (maxThreads = 1 and a dependencyOverrides chain; D134, below).
NeoForge can undo such a value with nothing worse than a WARN. Its ConfigTracker.loadConfig
(loader-4.0.44.jar!net/neoforged/fml/config/ConfigTracker.class) handles two cases:
  - A file its spec calls incorrect is logged "Configuration file {} is not correct. Correcting" (offsets 18-28, with the
    file's path). The file is then corrected and written back (offsets 37-49). ModConfigSpec.correct
    (neoforge-21.1.250-universal.jar) re-adds a missing key at its default and removes a key the spec lacks
    (Iterator.remove, offsets 523-544). So a key a mod renamed silently reverts to the mod's default.
  - A file it cannot read or parse (IOException or ParsingException, exception table 0-52 -> 105) is logged "Failed to
    load config {}: {}. Attempting to recreate" (offsets 107-122, with the file name). The file is then deleted and
    recreated with defaults (offsets 127-137).
A mod that renames its config file leaves the pack's copy unread, just as silently. ConfigTracker logs each file a mod
registers, at DEBUG, as "Config file {} for {} tracking" (logs/debug.log; log4j2.xml in the same jar rolls it at every
start and at 200 MB, and a headless boot writes about 2.5 MB, so it holds this boot only). Tracking is not loading: a
dedicated server also tracks each mod's CLIENT config (this boot's debug.log lists tombstone-client.toml and
twilightforest-client.toml as tracked) and never opens it. A file is read only by ConfigTracker.openConfig, which calls
loadConfig on the resolved path (offsets 63-90) and then logs, at DEBUG, "Loaded TOML config file {}" with that same path
(ldc #233 at offset 99, the path at 101; javap -c -v of the same class, Task 8b).
So, after a boot, for every config/**/*.toml the pack ships:
  - it is not a *-client.toml: a CLIENT config never loads on a dedicated server, so nothing here could prove it read;
  - logs/debug.log shows a mod tracking it under that name, and a "Loaded TOML config file <path>" line whose path is
    RUN_DIR/config/<file> (compared after resolving links: a copy loaded from anywhere else, such as a defaultconfigs/
    override, does not count);
  - logs/latest.log names it in neither WARN message;
  - the server's copy under RUN_DIR/config/ is byte-identical to the pack's.
config/fml.toml is FML's own config, not a mod's (v0.3 Task 10b, D134: maxThreads = 1, and dependencyOverrides ordering
Supplementaries after Moonlight and Amendments after Supplementaries). FMLConfig (same loader jar) reads it at launch, outside
ConfigTracker, so no mod tracks it and no "Loaded TOML config file" line names it. For it, instead:
  - debug.log has FMLConfig's TRACE line "Loaded FML config from <path>" (FMLConfig.load offsets 28-42) with that same
    RUN_DIR/config/fml.toml path;
  - when the shipped maxThreads is above 0, every debug.log "Using {} threads for parallel mod-loading" line (ModWorkManager
    .parallelExecutor offsets 13-25, the pool size it builds) shows exactly that count;
  - for each target mod in the shipped dependencyOverrides, latest.log has FMLConfig.load's banner line (a WARN, logged on
    every load between two rows of asterisks, offsets 188-248) "Dependency overrides for mod '<target>': <messages>", where
    lambda$load$5 joins each override's getMessage() with "," and getMessage() is "adding explicit AFTER ordering against
    '<dep>'" for "+dep" or "softening dependency constraints against '<dep>'" for "-dep" (FMLConfig$DependencyOverride,
    javap -c -v: the two ldc strings and the concat recipe "\u0001 '\u0001'"); and no banner line names an override the pack
    does not ship;
  - latest.log has no line reporting an override problem (OVERRIDE_TROUBLE): FMLConfig's "Found invalid dependency override"
    and "Invalid dependency overrides declaration" ERRORs, ModSorter's "Mod Sorting failed" and its ModLoadingIssue warnings
    for an override naming a mod that is not loaded (fml.modloadingissue.depoverride.unknown_target / unknown_dependency) or
    a cycle (fml.modloadingissue.cycle). A dedicated server logs such a warning as its bare key and arguments, from
    net.neoforged.neoforge.server.loading.ServerModLoader: a Task 10b fix-round boot with "+moonlite" in the server's copy
    logged "fml.modloadingissue.depoverride.unknown_dependency [[moonlite, supplementaries]]", no ERROR, and booted with
    Supplementaries constructed before Moonlight again. loader-4.0.44.jar!lang/en_us.json renders the same keys as "Unknown
    dependency override target with id ...", "Unknown mod ... referenced in dependency overrides for mod ..." and "Detected
    a mod dependency cycle: ..."; both forms are matched;
  - latest.log names it in neither correction WARN: FMLConfig.loadFrom logs "Configuration file {} is not correct.
    Correcting" (offsets 114-123, with the path) or "Incorrect key {} was corrected from {} to {}" (lambda$loadFrom$2);
  - byte-identical, as above. FMLConfig.loadFrom always writes the file back (saveConfig, offsets 191-193), replacing every
    comment with its spec's, so a shipped copy with any other comment or layout fails here.
The fml.toml failures that a hand edit on the server or a NeoForge/FML bump can cause (the copy differs, FML never loaded it,
a banner line is missing) end with FML_HINT, which names both causes and the fix.
The pinned values themselves are checked by tools/tests/test_shipped_configs.py.

Usage, from pack/:  python3 tools/check_configs.py [RUN_DIR]   (default .run/server). tools/server_boot.sh runs it after
every boot. Prints one summary line and exits 0, or prints each problem and exits 1.
"""
import os
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORRECTED = re.compile(r"Configuration file (.+?) is not correct\. Correcting")
RECREATED = re.compile(r"Failed to load config (.+?): .*Attempting to recreate")
TRACKED = re.compile(r"\]: Config file (.+?) for \S+ tracking$")
LOADED = re.compile(r"\]: Loaded TOML config file (.+)$")
FML_CONFIG = "fml.toml"   # FMLConfig's file (docstring), checked by its own lines below
FML_LOADED = re.compile(r"\[net\.neoforged\.fml\.loading\.FMLConfig/[A-Z]*\]: Loaded FML config from (.+)$")
FML_THREADS = re.compile(r"\[net\.neoforged\.fml\.ModWorkManager/[A-Z]*\]: Using (\d+) threads for parallel mod-loading$")
FML_KEY_CORRECTED = re.compile(r"\[net\.neoforged\.fml\.loading\.FMLConfig/CORE\]: Incorrect key (.+?) was corrected from ")
FML_BANNER = re.compile(r"\[net\.neoforged\.fml\.loading\.FMLConfig/[A-Z]*\]: (Dependency overrides for mod '.*)$")
OVERRIDE_MESSAGES = {"+": "adding explicit AFTER ordering against", "-": "softening dependency constraints against"}
# Appended to the fml.toml failures a server-side change can cause: the copy differs, FML never loaded it, a banner line is
# missing (Task 10b quality review M5). One line, so each problem stays one line.
FML_HINT = ("FML rewrites this file on every launch: a hand edit on the server, or a NeoForge/FML bump (regenerate from a "
            "fresh FML write and re-check these log lines, D134)")
OVERRIDE_TROUBLE = ("Found invalid dependency override", "Invalid dependency overrides declaration", "Mod Sorting failed",
                    "Unknown dependency override target", "referenced in dependency overrides",
                    "fml.modloadingissue.depoverride", "Detected a mod dependency cycle", "fml.modloadingissue.cycle")


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
    """Return (the shipped paths, every problem found) for the server install at `run`. A missing log is one problem; the
    per-file checks that read it are then skipped rather than each failing on it."""
    files, problems = shipped(root), []
    have_latest = (run / "logs" / "latest.log").is_file()
    lines = read_lines(run / "logs" / "latest.log", problems)
    have_debug = (run / "logs" / "debug.log").is_file()
    debug = read_lines(run / "logs" / "debug.log", problems)
    tracked = {m.group(1).replace("\\", "/") for m in map(TRACKED.search, debug) if m}
    loaded = {os.path.realpath(m.group(1)) for m in map(LOADED.search, debug) if m}
    for rel in files:
        installed = run / "config" / rel
        if rel.rsplit("/", 1)[-1].endswith("-client.toml"):
            problems.append(f"config/{rel}: a CLIENT config (*-client.toml); a dedicated server never loads one, so the pack "
                            "cannot ship it as a server setting (remove it, or change this check on purpose)")
            continue
        if rel == FML_CONFIG:
            if have_debug:
                problems += fml_problems(installed, root / "config" / rel, debug)
            if have_latest:
                problems += fml_override_problems(root / "config" / rel, lines)
            for line in lines:
                m = FML_KEY_CORRECTED.search(line)
                if m:
                    problems.append(f"config/{rel}: FML corrected key {m.group(1)} on load (latest.log: {line.strip()})")
        else:
            if have_debug and rel not in tracked:
                problems.append(f"config/{rel}: no mod tracks a config file of that name (debug.log); the pack's copy is "
                                "unread")
            if have_debug and os.path.realpath(installed) not in loaded:
                problems.append(f"config/{rel}: the server never loaded it (debug.log has no 'Loaded TOML config file "
                                f"{installed}' line); the pack's copy is unread")
        for line in lines:
            m = CORRECTED.search(line)
            # The "not correct" line carries the file's path, the "recreate" line its name under config/.
            path = m.group(1).replace("\\", "/") if m else None
            if path is not None and (path == rel or ("/" + path).endswith("/config/" + rel)):
                problems.append(f"config/{rel}: NeoForge corrected it on load (latest.log: {line.strip()})")
            m = RECREATED.search(line)
            if m and m.group(1).replace("\\", "/") == rel:
                problems.append(f"config/{rel}: NeoForge could not parse it and recreated it (latest.log: {line.strip()})")
        if not installed.is_file():
            problems.append(f"config/{rel}: not installed at {installed}")
        elif installed.read_bytes() != (root / "config" / rel).read_bytes():
            problems.append(f"config/{rel}: the server's copy differs from the pack's ({installed})"
                            + (f"; {FML_HINT}" if rel == FML_CONFIG else ""))
    return files, problems


def fml_problems(installed, shipped_file, debug):
    """config/fml.toml's debug.log checks (docstring): FMLConfig loaded RUN_DIR's copy, and the server built the mod-loading
    pool with the shipped maxThreads when that is above 0."""
    problems = []
    fml_loaded = {os.path.realpath(m.group(1)) for m in map(FML_LOADED.search, debug) if m}
    if os.path.realpath(installed) not in fml_loaded:
        problems.append(f"config/{FML_CONFIG}: FML never loaded it (debug.log has no 'Loaded FML config from {installed}' "
                        f"line); the pack's copy is unread; {FML_HINT}")
    with open(shipped_file, "rb") as f:
        want = tomllib.load(f).get("maxThreads")
    if isinstance(want, int) and want > 0:
        used = [int(m.group(1)) for m in map(FML_THREADS.search, debug) if m]   # every line must match, not just one
        if not used:
            problems.append(f"config/{FML_CONFIG}: debug.log has no 'Using N threads for parallel mod-loading' line, so "
                            f"maxThreads = {want} is unproven")
        for n in sorted(set(used) - {want}):
            problems.append(f"config/{FML_CONFIG}: the server used {n} threads for parallel mod-loading, not the shipped "
                            f"maxThreads = {want} (debug.log)")
    return problems


def override_banners(shipped_file):
    """The banner lines FMLConfig.load logs for the shipped dependencyOverrides (docstring), one per target mod."""
    with open(shipped_file, "rb") as f:
        overrides = tomllib.load(f).get("dependencyOverrides") or {}
    return {f"Dependency overrides for mod '{target}': "
            + ",".join(f"{OVERRIDE_MESSAGES[o[0]]} '{o[1:]}'" for o in entries if o[:1] in OVERRIDE_MESSAGES)
            for target, entries in overrides.items()}


def fml_override_problems(shipped_file, lines):
    """config/fml.toml's latest.log checks for the dependency overrides (docstring): every shipped override's banner line, no
    banner line for one the pack does not ship, and no override-problem line."""
    problems, want = [], override_banners(shipped_file)
    seen = {m.group(1) for m in map(FML_BANNER.search, lines) if m}
    for line in sorted(want - seen):
        problems.append(f"config/{FML_CONFIG}: latest.log has no FML banner line \"{line}\", so FML never applied that "
                        f"override; {FML_HINT}")
    for line in sorted(seen - want):
        problems.append(f"config/{FML_CONFIG}: latest.log has an FML banner line \"{line}\" for an override the pack does not "
                        "ship")
    for line in lines:
        if any(t in line for t in OVERRIDE_TROUBLE):
            problems.append(f"config/{FML_CONFIG}: FML reported a dependency-override problem (latest.log: {line.strip()})")
    return problems


def main(argv):
    run = Path(argv[1]) if len(argv) > 1 else ROOT / ".run" / "server"
    files, problems = check(run)
    for p in problems:
        print("  BAD " + p)
    print(f"check_configs: {len(files)} shipped config(s) checked, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
