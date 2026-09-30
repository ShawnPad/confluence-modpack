"""The configs the pack ships under config/ (v0.3 Task 9 review, I3).

Each file is the server's generated copy with one value the pack pins on purpose, so the value is pinned here. Whether the
server kept the file on load is tools/check_configs.py's job (tools/server_boot.sh runs it after every boot). The tests
below drive that checker against a scratch server directory: a synthetic log line or a doctored copy must fail it.
"""
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

def server(tmp_path, latest="", debug=None, copy=True):
    """A scratch RUN_DIR: config/ holds the pack's copies (when `copy`), logs/latest.log `latest`, and logs/debug.log the
    tracking line for each shipped file unless `debug` is given."""
    (tmp_path / "logs").mkdir()
    (tmp_path / "config").mkdir()
    if copy:
        for name in SHIPPED:
            shutil.copyfile(CONFIG / name, tmp_path / "config" / name)
    if debug is None:
        debug = "".join(DEBUG + f"Config file {name} for mod tracking\n" for name in SHIPPED)
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


def test_checker_fails_without_the_logs(tmp_path):
    rc, out = run_checker(server(tmp_path, latest=None))
    assert rc == 1 and "latest.log: missing; boot the server first" in out, out
