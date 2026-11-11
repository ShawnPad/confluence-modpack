"""check_tags.py's dev-flag check (v1.0 spec §7.2): a local boot that lost -Dconfluence.dev=true fails loudly."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_tags import SKIP_MARK, dev_flag_problems  # noqa: E402
from ptero_wait import SKIP_LINES  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[2] / "kubejs" / "server_scripts"


def test_a_boot_with_the_flag_has_no_problem():
    log = ("[12:32:08] [INFO] server_scripts:dump.js#38: confluence dump: 18880 recipes, 0 without json\n"
           "[12:32:13] [INFO] confluence tagcheck: 5603 tags in 192 registries (381 bound-but-empty)\n")
    assert dev_flag_problems(log) == []


def test_each_skip_line_is_one_problem():
    log = ("[12:32:08] [INFO] server_scripts:dump.js#39: confluence dump: skipped (confluence.dev unset)\n"
           "[12:32:08] [INFO] server_scripts:tagcheck.js#62: confluence tagcheck: skipped (confluence.dev unset)\n")
    got = dev_flag_problems(log)
    assert len(got) == 2 and all(p.startswith("DEV FLAG UNSET: ") for p in got), got
    assert SKIP_MARK == "skipped (confluence.dev unset)"


def test_script_skip_lines_match_the_deploy_check():
    """ptero_wait.SKIP_LINES (production evidence) must be logged verbatim by the scripts that skip."""
    owner = {"confluence dump:": "dump.js", "confluence tagcheck:": "tagcheck.js"}
    assert len(SKIP_LINES) == len(owner)
    for line in SKIP_LINES:
        name = next(f for k, f in owner.items() if line.startswith(k))
        assert line in (SCRIPTS / name).read_text(encoding="utf-8"), (line, name)
