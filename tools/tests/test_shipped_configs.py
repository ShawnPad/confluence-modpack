"""The configs the pack ships under config/ (v0.3 Task 9 review, I3).

Each file is the server's generated copy with one value the pack pins on purpose, so the value is pinned here. Whether the
server kept the file on load is tools/check_configs.py's job (tools/server_boot.sh runs it after every boot). The tests
below drive that checker against a scratch server directory: a synthetic log line or a doctored copy must fail it.
"""
import importlib.util
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
CHECKER = ROOT / "tools" / "check_configs.py"
SHIPPED = ["tombstone-common.toml", "twilightforest-common.toml"]
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
    each of them, as a real boot writes both."""
    (tmp_path / "logs").mkdir()
    (tmp_path / "config").mkdir()
    if copy:
        for name in names:
            shutil.copyfile(config / name, tmp_path / "config" / name)
    if debug is None:
        debug = "".join(tracking(name) + loaded(tmp_path / "config" / name) for name in names)
    if latest is not None:
        (tmp_path / "logs" / "latest.log").write_text(latest)
    (tmp_path / "logs" / "debug.log").write_text(debug)
    return tmp_path


def run_checker(run):
    proc = subprocess.run([sys.executable, str(CHECKER), str(run)], capture_output=True, text=True, timeout=60)
    return proc.returncode, proc.stdout


def test_checker_passes_a_clean_install(tmp_path):
    rc, out = run_checker(server(tmp_path, latest=WARN + "Configuration file /srv/config/other-mod.toml is not correct. "
                                                        "Correcting\n"))
    assert (rc, out) == (0, "check_configs: 2 shipped config(s) checked, 0 problem(s)\n")


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


def test_checker_fails_on_a_missing_server_copy(tmp_path):
    rc, out = run_checker(server(tmp_path, copy=False))
    assert rc == 1 and out.count(": not installed at ") == 2, out


def test_checker_fails_when_no_mod_tracks_the_file(tmp_path):
    rc, out = run_checker(server(tmp_path, debug=DEBUG + "Config file tombstone-common.toml for tombstone tracking\n"))
    assert rc == 1 and "config/twilightforest-common.toml: no mod tracks a config file of that name" in out, out


def test_checker_fails_when_a_tracked_file_is_never_loaded(tmp_path):
    """Task 8b: a dedicated server tracks CLIENT configs too, so tracking alone passed a file the server never read. Only
    ConfigTracker.openConfig's "Loaded TOML config file <path>" line (check_configs.py docstring) shows the read."""
    run = tmp_path / "run"
    run.mkdir()
    debug = "".join(tracking(name) for name in SHIPPED) + loaded(run / "config" / "tombstone-common.toml")
    rc, out = run_checker(server(run, debug=debug))
    assert rc == 1, out
    assert out.splitlines() == [
        f"  BAD config/twilightforest-common.toml: the server never loaded it (debug.log has no 'Loaded TOML config file "
        f"{run / 'config' / 'twilightforest-common.toml'}' line); the pack's copy is unread",
        "check_configs: 2 shipped config(s) checked, 1 problem(s)"]


@pytest.mark.parametrize("where", ["elsewhere", "defaultconfigs"])
def test_checker_fails_when_the_load_line_names_another_path(tmp_path, where):
    """The load line must name RUN_DIR/config/<file>: a same-named file loaded from another server directory, or from a
    defaultconfigs/ override, leaves the installed copy unread."""
    run = tmp_path / "run"
    run.mkdir()
    other = tmp_path / "other" / "config" if where == "elsewhere" else run / "defaultconfigs"
    debug = "".join(tracking(name) + loaded((run / "config" if name != "tombstone-common.toml" else other) / name)
                    for name in SHIPPED)
    rc, out = run_checker(server(run, debug=debug))
    assert rc == 1 and "config/tombstone-common.toml: the server never loaded it" in out, out
    assert "twilightforest-common.toml" not in out, out


def test_checker_matches_the_load_line_through_links(tmp_path):
    """The load line carries the path Java resolved; a RUN_DIR given through a symlink still matches it."""
    real = tmp_path / "real"
    real.mkdir()
    server(real)
    (tmp_path / "link").symlink_to(real)
    assert run_checker(tmp_path / "link") == (0, "check_configs: 2 shipped config(s) checked, 0 problem(s)\n")


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
    debug = "".join(tracking(name) for name in names) + "".join(loaded(run / "config" / name) for name in SHIPPED)
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
                            "check_configs: 2 shipped config(s) checked, 1 problem(s)\n")
