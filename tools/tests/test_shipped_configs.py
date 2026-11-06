"""The configs the pack ships under config/ (v0.3 Task 9 review, I3).

Each file is the server's generated copy with one value the pack pins on purpose, so the value is pinned here. Whether the
server kept the file on load is tools/check_configs.py's job (tools/server_boot.sh runs it after every boot). The tests
below drive that checker against a scratch server directory: a synthetic log line or a doctored copy must fail it.
"""
import graphlib
import importlib.util
import io
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kjs import JAR_SKIP, MODS, PW_MODS  # noqa: E402

CONFIG = ROOT / "config"
CHECKER = ROOT / "tools" / "check_configs.py"
SHIPPED = ["fml.toml", "tombstone-common.toml", "twilightforest-common.toml"]
MOD_CONFIGS = [n for n in SHIPPED if n != "fml.toml"]
WARN = "[30Sep2026 03:16:04.700] [modloading-worker-0/WARN] [net.neoforged.fml.config.ConfigTracker/CONFIG]: "
DEBUG = "[30Sep2026 03:16:04.682] [modloading-worker-0/DEBUG] [net.neoforged.fml.config.ConfigTracker/CONFIG]: "


def load(name):
    with open(CONFIG / name, "rb") as f:
        return tomllib.load(f)


def test_the_pack_ships_exactly_these_configs():
    assert sorted(p.relative_to(CONFIG).as_posix() for p in CONFIG.rglob("*.toml")) == SHIPPED


def test_tombstone_lost_tablets_stay_in_their_dimension():
    """D110, v0.3 spec §4.4: the one changed line. teleport_dim is the value §4.4 leaves alone."""
    d = load("tombstone-common.toml")
    assert d["magic_item"]["lost_tablet_search_outside_world"] is False
    assert d["general"]["teleport_dim"] is True


# The shipped dependencyOverrides, in the order FML's banner lists them (a HashMap's order; the D137 boots' latest.log lines
# 4-8). D134's chain: FML constructs Supplementaries after Moonlight and Amendments after Supplementaries. D137's edge: FML
# constructs Twilight Forest after KubeJS, so kubejs/startup_scripts/tf_gamerules_guard.js (which runs inside KubeJS's
# constructor) registers Twilight Forest's three game rules before TwilightForestMod.<init> hands them to Worker-Main threads.
# The file still carries no comment (FMLConfig.loadFrom rewrites it; see the test below), so the reasons live here.
CHAIN = {"twilightforest": ["+kubejs"], "supplementaries": ["+moonlight"], "amendments": ["+supplementaries"]}


def test_fml_toml_pins_the_moonlight_chain_and_one_thread():
    """D134, two measures. The dependencyOverrides chain is the guarantee for the Moonlight domain: a "+dep" override adds the
    same ModSorter graph edge as ordering = AFTER, and FML starts a mod's construction only once its predecessors' futures
    complete (allOf(...).handleAsync), at any thread count. So Moonlight's constructor finishes before Supplementaries' starts,
    and Supplementaries' before Amendments'; their Moonlight registrations (the provider multimap and DispenserHelper's
    listener lists) never overlap. maxThreads = 1 is the pack-wide backstop for construction races nobody has found yet: a
    pool of parallelism 1 runs one constructor at a time until a constructor blocks in a managed wait, when the pool adds a
    compensating worker and the rest of construction runs two at a time, so it alone does not make overlap impossible. Every
    other key is the default FML 4.0.44 writes (loader-4.0.44.jar FMLConfig$ConfigValue.<clinit>, javap -c). The file is
    FML's own canonical rewrite (an FMLConfig.load harness leaves it byte-identical; research/phase7-d134-evidence/) and carries
    no D134 comment: FMLConfig.loadFrom rewrites the file on every launch with its spec's comments (offsets 179-193), so any
    other comment or layout would make the server's copy differ (tools/check_configs.py). D137 adds one edge with the same
    mechanism, twilightforest = ["+kubejs"], for Twilight Forest's game-rule race (CHAIN's comment)."""
    assert load("fml.toml") == {
        "disableConfigWatcher": False, "earlyWindowControl": True, "maxThreads": 1, "versionCheck": True,
        "defaultConfigPath": "defaultconfigs", "disableOptimizedDFU": True, "earlyWindowProvider": "fmlearlywindow",
        "earlyWindowWidth": 854, "earlyWindowHeight": 480, "earlyWindowFBScale": 1, "earlyWindowMaximized": False,
        "earlyWindowSkipGLVersions": [], "earlyWindowSquir": False, "dependencyOverrides": CHAIN,
    }


def mods_toml(raw):
    return tomllib.loads(raw.decode("utf-8"))


def moonlight_dependents():
    """{mod id: jar} for every mod whose META-INF/neoforge.mods.toml, in a jar under MODS or a jar nested in one
    (META-INF/jarjar/), lists a dependency on moonlight."""
    found = {}

    def scan(name, z):
        try:
            raw = z.read("META-INF/neoforge.mods.toml")
        except KeyError:
            raw = None
        if raw is not None:
            for mod, deps in (mods_toml(raw).get("dependencies") or {}).items():
                if any(isinstance(d, dict) and d.get("modId") == "moonlight" for d in deps):
                    found[mod] = name
        for n in z.namelist():
            if n.startswith("META-INF/jarjar/") and n.endswith(".jar"):
                scan(f"{name}!{n}", zipfile.ZipFile(io.BytesIO(z.read(n))))

    for jar in sorted(MODS.glob("*.jar")):
        with zipfile.ZipFile(jar) as z:
            scan(jar.name, z)
    return found


def after(mod, chain=CHAIN):
    """Every mod `mod` is ordered after through the chain's "+" edges, transitively."""
    seen, todo = set(), [mod]
    while todo:
        for o in chain.get(todo.pop(), []):
            if o.startswith("+") and o[1:] not in seen:
                seen.add(o[1:])
                todo.append(o[1:])
    return seen


def test_every_moonlight_dependent_is_in_the_chain():
    """Drift guard (Task 10b fix round 1): a mod added later that depends on Moonlight registers with it from its constructor
    too, so it must join the chain, after moonlight. Reads the installed jars; at the time of writing it finds exactly
    supplementaries and amendments (both "required", ordering NONE)."""
    if not MODS.is_dir():
        pytest.skip(f"{MODS} {JAR_SKIP}")
    dependents = moonlight_dependents()
    assert dependents, f"no jar in {MODS} depends on moonlight; the chain is stale (D134)"
    missing = {m: j for m, j in dependents.items() if "moonlight" not in after(m, load("fml.toml")["dependencyOverrides"])}
    assert not missing, (f"these mods depend on moonlight but config/fml.toml's dependencyOverrides does not order them after "
                         f"it (D134): {missing}")


# The .pw.toml that ships each chain mod, and the jar-name prefix its `filename` starts with.
CHAIN_FILES = {"moonlight": "moonlight.pw.toml", "supplementaries": "supplementaries.pw.toml", "amendments": "amendments.pw.toml",
               "twilightforest": "the-twilight-forest.pw.toml", "kubejs": "kubejs.pw.toml"}


def test_every_chain_mod_is_in_the_pack():
    """Reverse pin: each target and each dependency the chain names is a mod the pack ships, so a removed mod fails here
    rather than as FML's unknown-override warning at boot. With the jars installed, the jar each .pw.toml names must declare
    that mod id."""
    ids = set(CHAIN) | {o[1:] for entries in CHAIN.values() for o in entries}
    assert ids == set(CHAIN_FILES), f"map each chain id to its .pw.toml: {sorted(ids ^ set(CHAIN_FILES))}"
    for mod, pw in CHAIN_FILES.items():
        toml = PW_MODS / pw
        assert toml.is_file(), f"{mod}: {toml} does not exist"
        with open(toml, "rb") as f:
            name = tomllib.load(f)["filename"]
        assert name.startswith(mod + "-"), f"{pw} ships {name}, not a {mod}- jar"
        if MODS.is_dir():
            assert (MODS / name).is_file(), f"{MODS} has no {name}: the installed jars predate mods/{pw}; boot first"
            with zipfile.ZipFile(MODS / name) as z:
                declared = [m["modId"] for m in mods_toml(z.read("META-INF/neoforge.mods.toml"))["mods"]]
            assert mod in declared, f"{name} declares {declared}, not {mod}"


def test_twilight_uncrafting_table_is_off():
    """D69 (5): the whole generated file with only disableUncraftingTable = true (X2.6 also removes its recipe in bypass.js)."""
    d = load("twilightforest-common.toml")
    assert d["Uncrafting Table"]["disableUncraftingTable"] is True


# ---- tools/check_configs.py against a scratch server directory -------------------------------------------------------

def tracking(name):
    return DEBUG + f"Config file {name} for mod tracking\n"


def loaded(path):
    return DEBUG.replace("modloading-worker-0", "modloading-sync-worker") + f"Loaded TOML config file {path}\n"


def server(tmp_path, latest="", debug=None, copy=True, config=CONFIG, names=SHIPPED):
    """A scratch RUN_DIR: config/ holds copies of `config`'s files `names` (when `copy`), logs/latest.log `latest`, and
    logs/debug.log, unless `debug` is given, the tracking line and the load line (with the scratch copy's absolute path) for
    each of them, as a real boot writes both. When `config`'s fml.toml is the shipped one, latest.log starts with FML's
    override banner for it, as a real boot's does."""
    (tmp_path / "logs").mkdir()
    (tmp_path / "config").mkdir()
    if copy:
        for name in names:
            shutil.copyfile(config / name, tmp_path / "config" / name)
    if debug is None:
        debug = "".join(fml_debug(tmp_path / "config" / name) if name == "fml.toml" else
                        tracking(name) + loaded(tmp_path / "config" / name) for name in names)
    if latest is not None:
        shipped_fml = "fml.toml" in names and (config / "fml.toml").read_bytes() == (CONFIG / "fml.toml").read_bytes()
        (tmp_path / "logs" / "latest.log").write_text((BANNER if shipped_fml else "") + latest)
    (tmp_path / "logs" / "debug.log").write_text(debug)
    return tmp_path


def run_checker(run):
    proc = subprocess.run([sys.executable, str(CHECKER), str(run)], capture_output=True, text=True, timeout=60)
    return proc.returncode, proc.stdout


def test_checker_passes_a_clean_install(tmp_path):
    rc, out = run_checker(server(tmp_path, latest=WARN + "Configuration file /srv/config/other-mod.toml is not correct. "
                                                        "Correcting\n"))
    assert (rc, out) == (0, f"check_configs: {len(SHIPPED)} shipped config(s) checked, 0 problem(s)\n")


@pytest.mark.parametrize("line,problem", [
    (WARN + "Configuration file /srv/pack/.run/server/config/tombstone-common.toml is not correct. Correcting",
     "config/tombstone-common.toml: NeoForge corrected it on load"),
    (WARN + "Configuration file config\\twilightforest-common.toml is not correct. Correcting",
     "config/twilightforest-common.toml: NeoForge corrected it on load"),
    (WARN + "Failed to load config tombstone-common.toml: com.electronwill.nightconfig.core.io.ParsingException: bad. "
            "Attempting to recreate",
     "config/tombstone-common.toml: NeoForge could not parse it and recreated it"),
])
def test_checker_fails_on_a_correction_or_recreation_warning(tmp_path, line, problem):
    rc, out = run_checker(server(tmp_path, latest=line + "\n"))
    assert rc == 1 and problem in out, out


def test_checker_fails_on_a_changed_server_copy(tmp_path):
    run = server(tmp_path)
    copy = run / "config" / "tombstone-common.toml"
    copy.write_text(copy.read_text().replace("lost_tablet_search_outside_world = false", "lost_tablet_search_outside_world = true"))
    rc, out = run_checker(run)
    assert rc == 1 and "config/tombstone-common.toml: the server's copy differs from the pack's" in out, out
    assert "FML rewrites this file" not in out, out


def test_checker_fails_on_a_changed_fml_toml_naming_the_likely_causes(tmp_path):
    """Task 10b quality review M5: a server copy of fml.toml that differs was edited by hand or rewritten by another FML."""
    run = server(tmp_path)
    copy = run / "config" / "fml.toml"
    copy.write_text(copy.read_text().replace("maxThreads = 1", "maxThreads = -1"))
    rc, out = run_checker(run)
    assert (rc, out) == (1, f"  BAD config/fml.toml: the server's copy differs from the pack's ({copy}); {FML_HINT}\n"
                            f"check_configs: {len(SHIPPED)} shipped config(s) checked, 1 problem(s)\n")


def test_checker_fails_on_a_missing_server_copy(tmp_path):
    rc, out = run_checker(server(tmp_path, copy=False))
    assert rc == 1 and out.count(": not installed at ") == len(SHIPPED), out


def test_checker_fails_when_no_mod_tracks_the_file(tmp_path):
    debug = (DEBUG + "Config file tombstone-common.toml for tombstone tracking\n"
             + "".join(loaded(tmp_path / "config" / n) for n in MOD_CONFIGS) + fml_debug(tmp_path / "config" / "fml.toml"))
    rc, out = run_checker(server(tmp_path, debug=debug))
    assert rc == 1 and out.splitlines() == [
        "  BAD config/twilightforest-common.toml: no mod tracks a config file of that name (debug.log); the pack's copy is "
        "unread", f"check_configs: {len(SHIPPED)} shipped config(s) checked, 1 problem(s)"], out


def test_checker_fails_when_a_tracked_file_is_never_loaded(tmp_path):
    """Task 8b: a dedicated server tracks CLIENT configs too, so tracking alone passed a file the server never read. Only
    ConfigTracker.openConfig's "Loaded TOML config file <path>" line (check_configs.py docstring) shows the read."""
    run = tmp_path / "run"
    run.mkdir()
    debug = ("".join(tracking(name) for name in MOD_CONFIGS) + loaded(run / "config" / "tombstone-common.toml")
             + fml_debug(run / "config" / "fml.toml"))
    rc, out = run_checker(server(run, debug=debug))
    assert rc == 1, out
    assert out.splitlines() == [
        f"  BAD config/twilightforest-common.toml: the server never loaded it (debug.log has no 'Loaded TOML config file "
        f"{run / 'config' / 'twilightforest-common.toml'}' line); the pack's copy is unread",
        f"check_configs: {len(SHIPPED)} shipped config(s) checked, 1 problem(s)"]


@pytest.mark.parametrize("where", ["elsewhere", "defaultconfigs"])
def test_checker_fails_when_the_load_line_names_another_path(tmp_path, where):
    """The load line must name RUN_DIR/config/<file>: a same-named file loaded from another server directory, or from a
    defaultconfigs/ override, leaves the installed copy unread."""
    run = tmp_path / "run"
    run.mkdir()
    other = tmp_path / "other" / "config" if where == "elsewhere" else run / "defaultconfigs"
    debug = "".join(tracking(name) + loaded((run / "config" if name != "tombstone-common.toml" else other) / name)
                    for name in MOD_CONFIGS) + fml_debug(run / "config" / "fml.toml")
    rc, out = run_checker(server(run, debug=debug))
    assert rc == 1 and "config/tombstone-common.toml: the server never loaded it" in out, out
    assert "twilightforest-common.toml" not in out, out


def test_checker_matches_the_load_line_through_links(tmp_path):
    """The load line carries the path Java resolved; a RUN_DIR given through a symlink still matches it."""
    real = tmp_path / "real"
    real.mkdir()
    server(real)
    (tmp_path / "link").symlink_to(real)
    assert run_checker(tmp_path / "link") == (0, f"check_configs: {len(SHIPPED)} shipped config(s) checked, 0 problem(s)\n")


def _checker_module():
    spec = importlib.util.spec_from_file_location("check_configs", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checker_fails_on_a_shipped_client_config(tmp_path):
    """Task 8b: a *-client.toml is a CLIENT config. The Task 9 re-review's case: with config/tombstone-client.toml shipped
    and a boot that tracks it (as this pack's debug.log does) but never loads it, the tracking-only check passed. The pack
    root here is a scratch copy, so the real config/ is untouched."""
    pack = tmp_path / "pack"
    (pack / "config").mkdir(parents=True)
    names = SHIPPED + ["tombstone-client.toml"]
    for name in SHIPPED:
        shutil.copyfile(CONFIG / name, pack / "config" / name)
    (pack / "config" / "tombstone-client.toml").write_text("[general]\n")
    run = tmp_path / "run"
    run.mkdir()
    debug = ("".join(tracking(name) for name in names) + "".join(loaded(run / "config" / name) for name in MOD_CONFIGS)
             + fml_debug(run / "config" / "fml.toml"))
    server(run, debug=debug, config=pack / "config", names=names)
    files, problems = _checker_module().check(run, root=pack)
    assert files == sorted(names)
    assert problems == ["config/tombstone-client.toml: a CLIENT config (*-client.toml); a dedicated server never loads one, "
                        "so the pack cannot ship it as a server setting (remove it, or change this check on purpose)"]


def test_checker_fails_without_the_logs(tmp_path):
    rc, out = run_checker(server(tmp_path, latest=None))
    assert rc == 1 and "latest.log: missing; boot the server first" in out, out


def test_a_missing_debug_log_is_one_problem(tmp_path):
    """Task 8b review nit: without debug.log, one problem, not one more per shipped file for each check that reads it."""
    run = server(tmp_path)
    (run / "logs" / "debug.log").unlink()
    rc, out = run_checker(run)
    assert (rc, out) == (1, f"  BAD {run / 'logs' / 'debug.log'}: missing; boot the server first\n"
                            f"check_configs: {len(SHIPPED)} shipped config(s) checked, 1 problem(s)\n")


def test_a_missing_latest_log_is_one_problem(tmp_path):
    """Task 10b quality review I1: without latest.log, one problem, not one more for each fml.toml banner line it lacks."""
    run = server(tmp_path, latest=None)
    rc, out = run_checker(run)
    assert (rc, out) == (1, f"  BAD {run / 'logs' / 'latest.log'}: missing; boot the server first\n"
                            f"check_configs: {len(SHIPPED)} shipped config(s) checked, 1 problem(s)\n")


# ---- config/fml.toml: FML's own config, not a mod config (v0.3 Task 10b, D134) ---------------------------------------
#
# FMLConfig (loader-4.0.44.jar) reads config/fml.toml at launch, outside ConfigTracker: no "Config file ... tracking" or
# "Loaded TOML config file" line names it. debug.log shows the read instead, at TRACE ("Loaded FML config from <path>",
# FMLConfig.load offsets 28-42), and the value that matters at DEBUG ("Using {} threads for parallel mod-loading",
# ModWorkManager.parallelExecutor offsets 13-25). FMLConfig.loadFrom corrects a file its spec rejects with a WARN ("Configuration
# file {} is not correct. Correcting", offsets 114-123; "Incorrect key {} was corrected from {} to {}", lambda$loadFrom$2) and
# always writes the file back (saveConfig, offsets 191-193), so the byte-identity check also proves FML kept every line.

FML_TRACE = "[02Oct2026 00:05:21.488] [main/TRACE] [net.neoforged.fml.loading.FMLConfig/CORE]: "
FML_THREADS = "[02Oct2026 00:05:37.120] [main/DEBUG] [net.neoforged.fml.ModWorkManager/LOADING]: "
FML_WARN = "[02Oct2026 00:05:21.488] [main/WARN] [net.neoforged.fml.loading.FMLConfig/CORE]: "
# FML's dependency-override banner (FMLConfig.load, offsets 188-248; lambda$load$5 logs "Dependency overrides for mod '{}': {}"
# with each override's getMessage() joined by ","), verbatim from the first fix-round boot's latest.log (the shipped chain; the
# 2026-10-02 04:22 boot, lines 4-7, and again at 10-13 from FML's second FMLConfig.load). D137's line, and the order of the
# three, verbatim from the D137 verification boot (C2, 2026-10-02 18:18, lines 4-8; research/phase7-d137-evidence/).
BANNER_LOGGER = "[02Oct2026 04:22:11.666] [main/WARN] [net.neoforged.fml.loading.FMLConfig/]: "
BANNER = "".join(BANNER_LOGGER + m + "\n" for m in (
    "*" * 30 + " Found dependency overrides " + "*" * 30,
    "Dependency overrides for mod 'twilightforest': adding explicit AFTER ordering against 'kubejs'",
    "Dependency overrides for mod 'supplementaries': adding explicit AFTER ordering against 'moonlight'",
    "Dependency overrides for mod 'amendments': adding explicit AFTER ordering against 'supplementaries'",
    "*" * 88))


# check_configs.py's operator hint on the fml.toml failures a server-side change can cause (Task 10b quality review M5).
FML_HINT = ("FML rewrites this file on every launch: a hand edit on the server, or a NeoForge/FML bump (regenerate from a "
            "fresh FML write and re-check these log lines, D134)")


def fml_debug(path, threads=1):
    return FML_TRACE + f"Loaded FML config from {path}\n" + FML_THREADS + f"Using {threads} threads for parallel mod-loading\n"


def fml_pack(tmp_path, max_threads=1, overrides=None):
    """A scratch pack root shipping the two mod configs plus an fml.toml with `max_threads` and, when given, a
    dependencyOverrides table {target: [entries]}."""
    pack = tmp_path / "pack"
    (pack / "config").mkdir(parents=True)
    for name in MOD_CONFIGS:
        shutil.copyfile(CONFIG / name, pack / "config" / name)
    table = "".join(f'\t{t} = [{", ".join(chr(34) + o + chr(34) for o in entries)}]\n'
                    for t, entries in (overrides or {}).items())
    (pack / "config" / "fml.toml").write_text(f"#Max threads\nmaxThreads = {max_threads}\n"
                                              + (f"[dependencyOverrides]\n{table}" if overrides else ""))
    return pack


def fml_server(tmp_path, pack, latest="", fml=None):
    """A scratch RUN_DIR for `pack`: the mod configs' lines as a boot writes them, plus `fml` (default: FML's lines for the
    installed fml.toml, 1 thread)."""
    run = tmp_path / "run"
    run.mkdir()
    mods = MOD_CONFIGS
    debug = "".join(tracking(n) + loaded(run / "config" / n) for n in mods)
    debug += fml_debug(run / "config" / "fml.toml") if fml is None else fml
    server(run, latest=latest, debug=debug, config=pack / "config", names=mods + ["fml.toml"])
    return run


def test_checker_passes_fml_toml_loaded_by_fml(tmp_path):
    pack = fml_pack(tmp_path)
    files, problems = _checker_module().check(fml_server(tmp_path, pack), root=pack)
    assert (files, problems) == (["fml.toml", "tombstone-common.toml", "twilightforest-common.toml"], [])


def test_checker_accepts_the_fml_lines_under_any_marker(tmp_path):
    """FMLConfig's load line and ModWorkManager's thread line are matched with any log4j marker ([A-Z]*), as the override
    banner is: a loader that drops or renames CORE/LOADING must not make the checker report a file FML did read."""
    pack = fml_pack(tmp_path)
    run = tmp_path / "run"
    fml = fml_debug(run / "config" / "fml.toml").replace("FMLConfig/CORE]", "FMLConfig/]").replace(
        "ModWorkManager/LOADING]", "ModWorkManager/]")
    files, problems = _checker_module().check(fml_server(tmp_path, pack, fml=fml), root=pack)
    assert problems == []


@pytest.mark.parametrize("case", ["no load line", "another path"])
def test_checker_fails_when_fml_never_loaded_the_file(tmp_path, case):
    pack = fml_pack(tmp_path)
    other = tmp_path / "elsewhere" / "config" / "fml.toml"
    fml = (FML_THREADS + "Using 1 threads for parallel mod-loading\n") if case == "no load line" else fml_debug(other)
    run = fml_server(tmp_path, pack, fml=fml)
    files, problems = _checker_module().check(run, root=pack)
    assert problems == [f"config/fml.toml: FML never loaded it (debug.log has no 'Loaded FML config from "
                        f"{run / 'config' / 'fml.toml'}' line); the pack's copy is unread; {FML_HINT}"]


@pytest.mark.parametrize("threads,problem", [
    (11, "config/fml.toml: the server used 11 threads for parallel mod-loading, not the shipped maxThreads = 1 (debug.log)"),
    (None, "config/fml.toml: debug.log has no 'Using N threads for parallel mod-loading' line, so maxThreads = 1 is unproven"),
])
def test_checker_fails_when_the_thread_count_is_not_the_shipped_one(tmp_path, threads, problem):
    pack = fml_pack(tmp_path)
    run = tmp_path / "run"
    fml = fml_debug(run / "config" / "fml.toml", threads) if threads else (
        FML_TRACE + f"Loaded FML config from {run / 'config' / 'fml.toml'}\n")
    files, problems = _checker_module().check(fml_server(tmp_path, pack, fml=fml), root=pack)
    assert problems == [problem]


def test_checker_fails_when_any_thread_line_is_not_the_shipped_count(tmp_path):
    """Task 10b fix round 1 (mutant M4e): every "Using N threads" line must show the shipped count, not just one of them."""
    pack = fml_pack(tmp_path)
    run = tmp_path / "run"
    fml = fml_debug(run / "config" / "fml.toml", 1) + FML_THREADS + "Using 11 threads for parallel mod-loading\n"
    files, problems = _checker_module().check(fml_server(tmp_path, pack, fml=fml), root=pack)
    assert problems == ["config/fml.toml: the server used 11 threads for parallel mod-loading, not the shipped maxThreads = 1 "
                        "(debug.log)"]


@pytest.mark.parametrize("line,problem", [
    (FML_WARN + "Configuration file /srv/pack/.run/server/config/fml.toml is not correct. Correcting",
     "config/fml.toml: NeoForge corrected it on load"),
    (FML_WARN + "Incorrect key maxThreads was corrected from x to 11",
     "config/fml.toml: FML corrected key maxThreads on load"),
])
def test_checker_fails_when_fml_corrects_the_file(tmp_path, line, problem):
    pack = fml_pack(tmp_path)
    files, problems = _checker_module().check(fml_server(tmp_path, pack, latest=line + "\n"), root=pack)
    assert len(problems) == 1 and problems[0].startswith(problem), problems


# ---- config/fml.toml's dependency overrides: FML's banner proves it read them (Task 10b fix round 1, D134) -------------
#
# FMLConfig.load logs a WARN banner listing every override it parsed, once per load; ModSorter turns an override naming a mod
# that is not loaded into a ModLoadingIssue.warning (fml.modloadingissue.depoverride.unknown_target / unknown_dependency), and
# FMLConfig logs an override with no +/- as "Found invalid dependency override ...". check_configs.py requires each shipped
# override's banner line in latest.log and fails on any line of those kinds. A fix-round boot with "+moonlite" in the server's
# copy (TYPO_BOOT below) booted with no ERROR at all and constructed Supplementaries before Moonlight again: only this check
# (and the byte comparison) caught it.

# That boot's latest.log:572, verbatim: a dedicated server logs the issue as its bare translation key and arguments.
TYPO_LINE = ("[02Oct2026 04:30:41.363] [main/WARN] [net.neoforged.neoforge.server.loading.ServerModLoader/LOADING]: "
             "fml.modloadingissue.depoverride.unknown_dependency [[moonlite, supplementaries]]")


def banner(overrides, logger=BANNER_LOGGER):
    msg = {"+": "adding explicit AFTER ordering against", "-": "softening dependency constraints against"}
    lines = ["*" * 30 + " Found dependency overrides " + "*" * 30]
    lines += [f"Dependency overrides for mod '{t}': " + ",".join(f"{msg[o[0]]} '{o[1:]}'" for o in entries)
              for t, entries in overrides.items()]
    return "".join(logger + line + "\n" for line in lines + ["*" * 88])


def test_the_banner_helper_reproduces_the_boot_lines():
    assert banner(CHAIN) == BANNER


def test_checker_passes_the_override_banner(tmp_path):
    pack = fml_pack(tmp_path, overrides=CHAIN)
    files, problems = _checker_module().check(fml_server(tmp_path, pack, latest=banner(CHAIN) * 2), root=pack)
    assert problems == []


def test_checker_passes_a_minus_override_banner(tmp_path):
    """A "-dep" override's message is "softening dependency constraints against '<dep>'", and one target's messages are
    joined with "," (FMLConfig$DependencyOverride.getMessage and lambda$load$5, javap -c -v: the ldc strings, the concat recipe
    "\\u0001 '\\u0001'", and the joining(",") argument)."""
    overrides = {**CHAIN, "quark": ["-moonlight", "+supplementaries"]}
    pack = fml_pack(tmp_path, overrides=overrides)
    latest = banner(overrides)
    assert "Dependency overrides for mod 'quark': softening dependency constraints against 'moonlight',adding explicit AFTER " \
           "ordering against 'supplementaries'\n" in latest
    files, problems = _checker_module().check(fml_server(tmp_path, pack, latest=latest), root=pack)
    assert problems == []


def test_checker_passes_the_shipped_file_with_its_banner(tmp_path):
    assert run_checker(server(tmp_path)) == (0, f"check_configs: {len(SHIPPED)} shipped config(s) checked, 0 problem(s)\n")


@pytest.mark.parametrize("drop", ["supplementaries", "amendments", "twilightforest"])
def test_checker_fails_without_an_override_banner_line(tmp_path, drop):
    pack = fml_pack(tmp_path, overrides=CHAIN)
    latest = "".join(line + "\n" for line in banner(CHAIN).splitlines() if f"mod '{drop}'" not in line)
    files, problems = _checker_module().check(fml_server(tmp_path, pack, latest=latest), root=pack)
    want = f"adding explicit AFTER ordering against '{CHAIN[drop][0][1:]}'"
    assert problems == [f"config/fml.toml: latest.log has no FML banner line \"Dependency overrides for mod '{drop}': {want}\", "
                        f"so FML never applied that override; {FML_HINT}"], problems


def test_checker_fails_on_an_unexpected_banner_line(tmp_path):
    pack = fml_pack(tmp_path, overrides=CHAIN)
    latest = banner({**CHAIN, "quark": ["+moonlight"]})
    files, problems = _checker_module().check(fml_server(tmp_path, pack, latest=latest), root=pack)
    assert problems == ["config/fml.toml: latest.log has an FML banner line \"Dependency overrides for mod 'quark': adding "
                        "explicit AFTER ordering against 'moonlight'\" for an override the pack does not ship"], problems


def test_checker_passes_fml_toml_without_overrides_and_without_a_banner(tmp_path):
    pack = fml_pack(tmp_path)
    files, problems = _checker_module().check(fml_server(tmp_path, pack), root=pack)
    assert problems == []


@pytest.mark.parametrize("line", [
    # ModSorter's ModLoadingIssue warnings: as a dedicated server logs them (the typo boot's line, and its unknown_target
    # sibling in the same form), and as loader-4.0.44.jar lang/en_us.json renders them (a client screen), with and without
    # their colour codes
    TYPO_LINE[len("[02Oct2026 04:30:41.363] "):],
    "[main/WARN] [net.neoforged.neoforge.server.loading.ServerModLoader/LOADING]: fml.modloadingissue.depoverride.unknown_target "
    "[[supplementarie]]",
    "[main/WARN] [net.neoforged.fml.ModLoader/LOADING]: Unknown dependency override target with id \u00a7esupplementarie\u00a7r",
    "[main/WARN] [net.neoforged.fml.ModLoader/LOADING]: Unknown mod moonlite referenced in dependency overrides for mod "
    "supplementaries",
    # FMLConfig.load's own lines for a malformed table or entry
    "[main/ERROR] [net.neoforged.fml.loading.FMLConfig/]: Found invalid dependency override for mod 'supplementaries'. Expected "
    "+/- in override 'moonlight'. Did you forget to specify the override type?",
    "[main/ERROR] [net.neoforged.fml.loading.FMLConfig/]: Invalid dependency overrides declaration in config. Expected object "
    "but found []",
    # ModSorter's cycle failure
    "[main/ERROR] [net.neoforged.fml.loading.ModSorter/LOADING]: Mod Sorting failed.",
    "[main/ERROR] [net.neoforged.fml.ModLoader/]: Detected a mod dependency cycle: [a, b]",
])
def test_checker_fails_on_an_override_problem_line(tmp_path, line):
    pack = fml_pack(tmp_path, overrides=CHAIN)
    latest = banner(CHAIN) + "[02Oct2026 04:22:11.700] " + line + "\n"
    files, problems = _checker_module().check(fml_server(tmp_path, pack, latest=latest), root=pack)
    assert len(problems) == 1 and problems[0].startswith("config/fml.toml: FML reported a dependency-override problem "
                                                         "(latest.log: "), problems


def test_checker_fails_the_typo_boot(tmp_path):
    """The typo boot's own lines: its banner names moonlite, and ServerModLoader warns about it. With D134's chain in the
    pack (the pack of that boot, before D137's edge), the checker names all three (the byte comparison adds a fourth on the
    real boot)."""
    typo = {"supplementaries": ["+moonlite"], "amendments": ["+supplementaries"]}
    pack = fml_pack(tmp_path, overrides={t: o for t, o in CHAIN.items() if t != "twilightforest"})
    files, problems = _checker_module().check(fml_server(tmp_path, pack, latest=banner(typo) * 2 + TYPO_LINE + "\n"), root=pack)
    assert problems == [
        "config/fml.toml: latest.log has no FML banner line \"Dependency overrides for mod 'supplementaries': adding explicit "
        f"AFTER ordering against 'moonlight'\", so FML never applied that override; {FML_HINT}",
        "config/fml.toml: latest.log has an FML banner line \"Dependency overrides for mod 'supplementaries': adding explicit "
        "AFTER ordering against 'moonlite'\" for an override the pack does not ship",
        f"config/fml.toml: FML reported a dependency-override problem (latest.log: {TYPO_LINE})"], problems


# ---- D137: the shipped overrides leave FML's mod-ordering graph without a cycle ------------------------------------------
#
# FML 4.0.44's ModSorter (loader-4.0.44.jar, javap -c) builds one graph of every loaded mod. addDependency adds, for each
# dependency a mod declares on another loaded mod, an edge owner -> target for ordering BEFORE and target -> owner for
# AFTER (offsets 56-118; NONE adds nothing, and no side filter applies). Each "+dep" override adds dep -> target (sort's
# override loop, offsets 131-149). A cycle fails the launch ("Mod Sorting failed", fml.modloadingissue.cycle). So an
# override is safe only if no declared ordering already puts its target before its dependency. These tests rebuild the
# graph from the jars' META-INF/neoforge.mods.toml (jar-in-jar included) plus the shipped overrides, for the server's mods
# and for a client's (the same minus the server-only jars, plus the client-only ones tools/check_client_mixins.py downloads
# into .run/client-jars).

CLIENT_JARS = ROOT / ".run" / "client-jars"


def declared_mods(jars):
    """[(jar label, parsed neoforge.mods.toml)] for each jar and each jar nested in it (META-INF/jarjar/). A jar with only a
    Forge-era META-INF/mods.toml is not a mod to FML 4.0.44 (the loader jar names that file only in IncompatibleModReason;
    a boot logs Supplementaries' nested mixinsquared-forge as 'Found gamelibrary file'), so it is not in the graph."""
    out = []

    def scan(label, z):
        try:
            out.append((label, mods_toml(z.read("META-INF/neoforge.mods.toml"))))
        except KeyError:
            pass
        for n in z.namelist():
            if n.startswith("META-INF/jarjar/") and n.endswith(".jar"):
                scan(f"{label}!{n}", zipfile.ZipFile(io.BytesIO(z.read(n))))

    for jar in jars:
        with zipfile.ZipFile(jar) as z:
            scan(jar.name, z)
    return out


def ordering_graph(declared, overrides):
    """(mod ids, {(before, after): why}) as ModSorter builds them from `declared` and the "+dep" overrides."""
    mods = {m["modId"] for _, t in declared for m in t.get("mods", [])} | {"minecraft", "neoforge"}
    edges = {}
    for label, t in declared:
        for owner, deps in (t.get("dependencies") or {}).items():
            for d in deps if isinstance(deps, list) else []:
                target, order = d.get("modId"), str(d.get("ordering", "NONE")).upper()
                if owner in mods and target in mods and target != owner and order in ("BEFORE", "AFTER"):
                    edge = (owner, target) if order == "BEFORE" else (target, owner)
                    edges.setdefault(edge, f"{owner} {order} {target} ({label})")
    for target, entries in overrides.items():
        for o in entries:
            if o.startswith("+") and target in mods and o[1:] in mods:
                edges[(o[1:], target)] = f"override {target} = {o}"
    return mods, edges


def ordering_cycle(mods, edges):
    """A cycle in the graph as a list of mod ids, or None."""
    ts = graphlib.TopologicalSorter({m: () for m in mods})
    for before, after_ in edges:
        ts.add(after_, before)
    try:
        list(ts.static_order())
    except graphlib.CycleError as e:
        return e.args[1]
    return None


def test_the_cycle_check_finds_a_cycle():
    declared = [("a.jar", {"mods": [{"modId": "a"}], "dependencies": {"a": [{"modId": "b", "ordering": "BEFORE"}]}}),
                ("b.jar", {"mods": [{"modId": "b"}]})]
    mods, edges = ordering_graph(declared, {})
    assert edges == {("a", "b"): "a BEFORE b (a.jar)"} and ordering_cycle(mods, edges) is None
    mods, edges = ordering_graph(declared, {"a": ["+b"]})
    assert sorted(ordering_cycle(mods, edges)) in (["a", "a", "b"], ["a", "b", "b"])
    # A "-dep" override, an override naming a mod that is not loaded, and NONE ordering add nothing.
    declared[1][1]["dependencies"] = {"b": [{"modId": "a", "ordering": "NONE"}, {"modId": "zz", "ordering": "AFTER"}]}
    mods, edges = ordering_graph(declared, {"a": ["-b"], "zz": ["+a"]})
    assert edges == {("a", "b"): "a BEFORE b (a.jar)"}


def side_jars(side):
    """The jars a dedicated server ('server') or a client ('client') of the pack loads."""
    if not MODS.is_dir():
        pytest.skip(f"{MODS} {JAR_SKIP}")
    jars = sorted(MODS.glob("*.jar"))
    if side == "client":
        sides = {}
        for pw in PW_MODS.glob("*.pw.toml"):
            with open(pw, "rb") as f:
                t = tomllib.load(f)
            sides[t["filename"]] = t.get("side", "both")
        if not CLIENT_JARS.is_dir():
            pytest.skip(f"{CLIENT_JARS} does not exist (tools/check_client_mixins.py downloads the client-only jars there)")
        jars = [j for j in jars if sides.get(j.name, "both") != "server"] + sorted(CLIENT_JARS.glob("*.jar"))
    return jars


@pytest.mark.parametrize("side", ["server", "client"])
def test_the_shipped_overrides_leave_no_ordering_cycle(side):
    mods, edges = ordering_graph(declared_mods(side_jars(side)), load("fml.toml")["dependencyOverrides"])
    assert ordering_cycle(mods, edges) is None
    # Each shipped edge is in the graph, so the check above covered it: both of its mods are loaded on this side.
    for target, entries in load("fml.toml")["dependencyOverrides"].items():
        assert {(o[1:], target) for o in entries if o.startswith("+")} <= set(edges), (side, target)
    assert edges[("kubejs", "twilightforest")] == "override twilightforest = +kubejs"
