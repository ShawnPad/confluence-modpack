"""tools/ptero_wait.py's pure rules (v1.0 plan Task 2; spec §4.2, §7.2, §9). The panel calls are not tested here: they are
the 0.3.0 helper's, unchanged, and Task 27 runs them against the live server."""
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import ptero_wait  # noqa: E402
from ptero_wait import SKIP_LINES, exported_problem, local_expectations, problems  # noqa: E402

FTBQ_TAIL = "4 chapter groups, 15 chapters, 126 quests, 5 reward tables"


def good_ev():
    return {"packFileHash": "ab", "pack_sha256": "ab", "done_line": "[Server thread/INFO]: Done (41.2s)!",
            "ftbq_line": "[Server thread/INFO] [FTB Quests/]: Loaded " + FTBQ_TAIL,
            "worldgen_line": "[INFO] server_scripts:worldgen.js#150: confluence worldgen: 8 placements",
            "kubejs_errors": 0, "tombstone_line": "150: lost_tablet_search_outside_world = false",
            "lang_same_as_pack": True, "skip_lines": list(SKIP_LINES), "exported": None}


EXPECT = {"ftbq": FTBQ_TAIL, "worldgen": "8 placements"}


def test_import_is_lazy():
    code = ("import sys; sys.path.insert(0, %r); import ptero_wait; "
            "print('requests' in sys.modules, 'ptero' in sys.modules)" % str(TOOLS))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "False False"


def test_local_expectations_read_the_local_boot(tmp_path):
    (tmp_path / "logs" / "kubejs").mkdir(parents=True)
    (tmp_path / "logs" / "latest.log").write_text(
        "[12:00:00] [Server thread/INFO] [FTB Quests/]: Loaded 4 chapter groups, 14 chapters, 112 quests, 5 reward tables\n"
        "[12:05:00] [Server thread/INFO] [FTB Quests/]: Loaded " + FTBQ_TAIL + "\n")
    (tmp_path / "logs" / "kubejs" / "server.log").write_text(
        "[12:00:01] [INFO] server_scripts:worldgen.js#150: confluence worldgen: 8 placements\n")
    assert local_expectations(tmp_path) == EXPECT


def test_local_expectations_without_a_boot_are_empty(tmp_path):
    assert local_expectations(tmp_path) == {"ftbq": "", "worldgen": ""}


def test_a_matching_server_passes():
    assert problems(good_ev(), EXPECT) == []


def test_each_rule_fires():
    cases = {
        "packFileHash": ("cd", "packFileHash"),
        "done_line": ("", "Done ("),
        "ftbq_line": ("[FTB Quests/]: Loaded 4 chapter groups, 14 chapters, 112 quests, 5 reward tables", "FTB Quests"),
        "worldgen_line": ("confluence worldgen: 7 placements", "worldgen"),
        "kubejs_errors": (2, "ERROR"),
        "tombstone_line": ("150: lost_tablet_search_outside_world = true", "Tombstone"),
        "lang_same_as_pack": (False, "lang"),
        "exported": ("kubejs/exported/recipes.json modified 2026-11-20T10:00:00+00:00, after the restart", "exported"),
    }
    for key, (value, word) in cases.items():
        ev = good_ev()
        ev[key] = value
        got = problems(ev, EXPECT)
        assert len(got) == 1 and word in got[0], (key, got)


def test_a_missing_skip_line_fails_by_name():
    for line in SKIP_LINES:
        ev = good_ev()
        ev["skip_lines"] = [s for s in SKIP_LINES if s != line]
        assert problems(ev, EXPECT) == [f"skip line missing from logs/kubejs/server.log: '{line}'"]


def test_an_empty_local_expectation_fails_instead_of_matching_anything():
    got = problems(good_ev(), {"ftbq": "", "worldgen": ""})
    assert len(got) == 2 and all("local boot" in m for m in got), got


def test_exported_absent_or_old_passes_and_new_fails():
    since = 1_800_000_000.0
    assert exported_problem(None, since) is None
    old = [{"name": "recipes.json", "modified_at": "2027-01-15T08:00:00+00:00"}]   # 1 800 000 000 is 2027-01-15T08:00Z
    assert exported_problem(old, since) is None
    new = [{"name": "tags.json", "modified_at": "2027-01-15T08:00:01+00:00"}]
    assert exported_problem(new, since) == "kubejs/exported/tags.json modified 2027-01-15T08:00:01+00:00, after the restart"
