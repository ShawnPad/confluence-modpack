"""tools/check_boot_log.py: every ERROR or FATAL record in logs/latest.log must match a documented tools/boot_allowlist.txt entry
(v0.3 Task 8c). Synthetic logs only; the real boot is tools/server_boot.sh's job."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_boot_log  # noqa: E402
from check_boot_log import ALLOWLIST, load_allowlist, records  # noqa: E402

T = "[01Oct2026 20:47:52.695]"
TAG_ERR = (f"{T} [Worker-Main-10/ERROR] [net.minecraft.tags.TagLoader/]: Couldn't load tag c:tools as it is missing following "
           "references: \n\t#c:tools/bow (from mod/neoforge)\n\t#c:tools/crossbow (from mod/neoforge)\n")
CURIOS = f"{T} [main/ERROR] [Curios API/]: example is not a registered slot type!\n"
UNKNOWN = f"{T} [main/ERROR] [SomeMod/]: Exception loading thing\njava.lang.IllegalStateException: boom\n\tat a.b.C.d(C.java:1)\n"
INFO = f"{T} [main/INFO] [KubeJS Server/]: Added 59 recipes\n"
WARN = (f"{T} [main/WARN] [KubeJS Server/]: RecipeComponentValue.java#102: Failed to parse recipe "
        "'allthemodium:allthemodium_dust_from_ore_crushing[minecraft:crafting_shapeless]' @ [ingredients][1]!\n")
# The line latest.log carries when the server finished starting (the 2026-10-01 22:26 boot, logs/latest.log:732). console.log
# prints the same line with the short logger name [minecraft/DedicatedServer].
DONE = (f"{T} [Server thread/INFO] [net.minecraft.server.dedicated.DedicatedServer/]: Done (6.436s)! For help, type "
        '"help"\n')
ALLOW = """\
# header comment, separated from the first entry by a blank line

# Curios API: IF ships a curios entities file naming a slot "example" that no mod registers; Curios skips it.
\\[Curios API/\\]: example is not a registered slot type!
"""


def run_dir(tmp_path, log, allow=ALLOW, done=True):
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "latest.log").write_text(log + (DONE if done else ""))
    (tmp_path / "allow.txt").write_text(allow)
    return tmp_path


def test_records_group_continuation_lines_and_skip_other_levels():
    got = records(INFO + TAG_ERR + WARN + CURIOS + UNKNOWN)
    assert [(line, text.splitlines()[0]) for line, text in got] == [
        (2, "[net.minecraft.tags.TagLoader/]: Couldn't load tag c:tools as it is missing following references: "),
        (6, "[Curios API/]: example is not a registered slot type!"),
        (7, "[SomeMod/]: Exception loading thing"),
    ]
    assert got[0][1].splitlines()[1:] == ["\t#c:tools/bow (from mod/neoforge)", "\t#c:tools/crossbow (from mod/neoforge)"]
    assert got[2][1].splitlines()[1:] == ["java.lang.IllegalStateException: boom", "\tat a.b.C.d(C.java:1)"]
    assert records(f"{T} [main/FATAL] [x/]: dead\n") == [(1, "[x/]: dead")]


def test_one_allowlisted_and_one_unknown_error_fail_naming_only_the_unknown(tmp_path, capsys):
    """The Task 8c proof: an allowlisted ERROR plus an unknown one exits 1 and names the unknown one only."""
    d = run_dir(tmp_path, INFO + CURIOS + WARN + UNKNOWN)
    assert check_boot_log.main([str(d), "--allowlist", str(d / "allow.txt")]) == 1
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "boot log: 2 ERROR/FATAL records in logs/latest.log, 1 allowlisted, 1 unknown"
    assert "  UNKNOWN latest.log:4: [SomeMod/]: Exception loading thing" in out
    assert "  java.lang.IllegalStateException: boom\n  \tat a.b.C.d(C.java:1)" in out
    assert "Curios" not in out.split("\n", 1)[1]


def test_allowlisted_errors_and_warnings_pass(tmp_path, capsys):
    d = run_dir(tmp_path, INFO + CURIOS + WARN + CURIOS)
    assert check_boot_log.main([str(d), "--allowlist", str(d / "allow.txt")]) == 0
    assert capsys.readouterr().out.splitlines()[0] == (
        "boot log: 2 ERROR/FATAL records in logs/latest.log, 2 allowlisted, 0 unknown")


def test_an_entry_must_match_the_whole_record(tmp_path):
    """fullmatch: an entry for one TagLoader record does not cover the same tag missing one more reference."""
    allow = ("# NeoForge: c:tools misses only its bow and crossbow references.\n"
             "\\[net\\.minecraft\\.tags\\.TagLoader/\\]: Couldn't load tag c:tools as it is missing following references: "
             "\\n\\t#c:tools/bow \\(from mod/neoforge\\)\\n\\t#c:tools/crossbow \\(from mod/neoforge\\)\n")
    d = run_dir(tmp_path, TAG_ERR, allow)
    assert check_boot_log.main([str(d), "--allowlist", str(d / "allow.txt")]) == 0
    more = TAG_ERR + "\t#c:tools/shield (from mod/neoforge)\n" + DONE
    (d / "logs" / "latest.log").write_text(more)
    assert check_boot_log.main([str(d), "--allowlist", str(d / "allow.txt")]) == 1


@pytest.mark.parametrize("allow,msg", [
    ("\\[Curios API/\\]: x\n", "line 1: an entry needs a comment line right above it"),
    ("# Curios: fine\n\n\\[Curios API/\\]: x\n", "line 3: an entry needs a comment line right above it"),
    ("# Curios: bad regex\n\\[Curios API/: (x\n", "line 2: not a regex"),
    ("# Curios: twice\nabc\n# again\nabc\n", "line 4: repeats line 2"),
    # round 2, minor 2: the comment covers the one entry right below it; the next entry needs its own
    ("# c\nA\nB\n", "line 3: an entry needs a comment line right above it"),
])
def test_allowlist_entries_are_documented_valid_and_unique(tmp_path, allow, msg):
    p = tmp_path / "allow.txt"
    p.write_text(allow)
    with pytest.raises(ValueError, match=msg):
        load_allowlist(p)


def test_missing_log_or_allowlist_fails(tmp_path, capsys):
    assert check_boot_log.main([str(tmp_path), "--allowlist", str(tmp_path / "nope.txt")]) == 1
    assert "MISSING LOG" in capsys.readouterr().out
    d = run_dir(tmp_path, INFO)
    assert check_boot_log.main([str(d), "--allowlist", str(d / "nope.txt")]) == 3   # round 2, minor 5: its own exit code
    assert "MISSING ALLOWLIST" in capsys.readouterr().out


def test_the_shipped_allowlist_loads():
    assert load_allowlist(ALLOWLIST), "tools/boot_allowlist.txt has no entries"


def test_the_shipped_allowlist_never_covers_an_invalid_item_record():
    """Never allowlist "Tried to load invalid item" (Task 8c brief). Real record shapes, matched as the check matches them
    (fullmatch, every entry): vanilla's, from server-1.21.1-20240808.144430-srg.jar net/minecraft/world/item/ItemStack
    (lambda$parse$15 logs LOGGER.error("Tried to load invalid item: '{}'", ...), and LOGGER is LogUtils.getLogger() in
    <clinit>, so the logger is the class name), and the same text logged through KubeJS."""
    log = (f"{T} [Worker-Main-3/ERROR] [net.minecraft.world.item.ItemStack/]: Tried to load invalid item: "
           "'Unknown registry key in ResourceKey[minecraft:root / minecraft:item]: modx:gone'\n"
           f"{T} [main/ERROR] [KubeJS/]: Tried to load invalid item: 'modx:gone'\n")
    recs = [text for _, text in records(log)]
    assert len(recs) == 2
    entries = load_allowlist(ALLOWLIST)
    assert not [(e.pattern, r) for e in entries for r in recs if e.fullmatch(r)]
    assert not [e for e in entries if "invalid item" in e.pattern], "never allowlist 'Tried to load invalid item'"


def test_the_shipped_allowlist_never_covers_a_tag_load_error():
    """D132: "Couldn't load tag" is fixed at the source, never allowlisted. Real records from the 2026-10-01 boot, both loggers."""
    log = TAG_ERR + (f"{T} [main/ERROR] [KubeJS/]: Couldn't load tag minecraft:enchantable/bow as it is missing following "
                     "references: \n\tallthemodium:allthemodium_bow (from mod/allthemodium)\n")
    recs = [text for _, text in records(log)]
    assert len(recs) == 2
    entries = load_allowlist(ALLOWLIST)
    assert not [(e.pattern, r) for e in entries for r in recs if e.fullmatch(r)]
    assert not [e for e in entries if "load tag" in e.pattern], "never allowlist a \"Couldn't load tag\" record (D132)"


# ---- round 2, minor 1: records split on '\n' only (as grep -n counts), end only at a log4j header, and fail closed ----

def grep_n(log: str, pattern: str, tmp_path) -> list[int]:
    import subprocess
    f = tmp_path / "grep.log"
    f.write_bytes(log.encode())
    out = subprocess.run(["grep", "-n", pattern, str(f)], capture_output=True, text=True).stdout
    return [int(line.split(":", 1)[0]) for line in out.split("\n") if line]


def test_a_thread_name_with_a_bracket_still_starts_a_record():
    log = f"{T} [Netty Server IO #1] (x)/ERROR] [SomeMod/]: boom\n"
    assert records(log) == [(1, "[SomeMod/]: boom")]


def test_a_bracketed_continuation_line_stays_in_its_record():
    """A '[' line that is no log4j header (a printed list) is a continuation line: it neither ends the record nor drops the
    stack trace after it, so an entry written for the shorter text cannot cover it."""
    log = UNKNOWN.replace("\tat a.b.C.d", "[1, 2, 3]\n\tat a.b.C.d")
    assert records(log) == [(1, "[SomeMod/]: Exception loading thing\njava.lang.IllegalStateException: boom\n[1, 2, 3]\n"
                                "\tat a.b.C.d(C.java:1)")]


def test_form_feed_and_line_separators_are_not_line_breaks(tmp_path):
    log = (INFO.replace("Added", "Added\f\u2028\u0085") + f"{T} [main/ERROR] [x/]: a\u2028b\fc\n" + INFO + CURIOS)
    got = records(log)
    assert [n for n, _ in got] == grep_n(log, "/ERROR]", tmp_path) == [2, 4]
    assert got[0][1] == "[x/]: a\u2028b\fc"


def test_crlf_lines_read_as_lf_lines(tmp_path):
    log = INFO + TAG_ERR + CURIOS
    assert records(log.replace("\n", "\r\n")) == records(log)
    assert [n for n, _ in records(log)] == grep_n(log, "/ERROR]", tmp_path)


def test_a_malformed_header_naming_an_error_level_is_an_unknown_record(tmp_path, capsys):
    """Fail closed: a '[' line that is no log4j header but carries '/ERROR]' or '/FATAL]' is reported, whatever the allowlist."""
    bad = "[22:26:19] [main/ERROR]: no logger bracket\n"
    d = run_dir(tmp_path, INFO + bad + CURIOS, ALLOW + "# anything: a catch-all must not hide it\n.*\n")
    assert check_boot_log.main([str(d), "--allowlist", str(d / "allow.txt")]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "boot log: 2 ERROR/FATAL records in logs/latest.log, 1 allowlisted, 1 unknown"
    assert out[1] == "  UNKNOWN latest.log:2: (not a log4j header line) [22:26:19] [main/ERROR]: no logger bracket"


# ---- round 2, minor 4: a log the server never finished is a failure ----

def test_a_log_without_the_done_line_is_incomplete(tmp_path, capsys):
    d = run_dir(tmp_path, INFO + CURIOS, done=False)
    assert check_boot_log.main([str(d), "--allowlist", str(d / "allow.txt")]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0] == ("INCOMPLETE LOG logs/latest.log has no '[net.minecraft.server.dedicated.DedicatedServer/]: Done (' "
                      "line: the server never finished starting")
    # the console.log form of the line, or a Done inside another record, does not count
    for text in (f"[22:26:26] [Server thread/INFO] [minecraft/DedicatedServer]: Done (6.436s)!\n",
                 CURIOS.rstrip("\n") + " [net.minecraft.server.dedicated.DedicatedServer/]: Done (1s)\n"):
        (d / "logs" / "latest.log").write_text(INFO + text)
        assert check_boot_log.main([str(d), "--allowlist", str(d / "allow.txt")]) == 1
        assert capsys.readouterr().out.startswith("INCOMPLETE LOG")


# ---- round 2, minor 5: argparse, and exit codes the boot script can tell apart ----

@pytest.mark.parametrize("argv", [[], ["a", "b"], ["a", "--allowlist"], ["--nope", "a"]])
def test_a_usage_error_exits_2(argv, capsys):
    with pytest.raises(SystemExit) as e:
        check_boot_log.main(argv)
    assert e.value.code == 2
    assert "usage: check_boot_log.py" in capsys.readouterr().err


def test_a_bad_or_missing_allowlist_exits_3(tmp_path, capsys):
    d = run_dir(tmp_path, INFO, "abc\n")
    assert check_boot_log.main([str(d), "--allowlist", str(d / "allow.txt")]) == 3
    assert capsys.readouterr().out.startswith("BAD ALLOWLIST allow.txt line 1")
    assert check_boot_log.main([str(d), "--allowlist", str(d / "nope.txt")]) == 3
    assert capsys.readouterr().out.startswith("MISSING ALLOWLIST")


def test_main_reads_a_lone_cr_as_part_of_its_line(tmp_path, capsys):
    """Round 3, H4: main() reads the log's bytes, so a lone '\\r' (text mode would make it a line break) keeps the line numbers
    grep -n prints."""
    log = INFO.replace("Added", "Added\r59\r") + UNKNOWN + DONE
    d = run_dir(tmp_path, "", done=False)
    (d / "logs" / "latest.log").write_bytes(log.encode())
    assert check_boot_log.main([str(d), "--allowlist", str(d / "allow.txt")]) == 1
    out = capsys.readouterr().out.splitlines()
    want = grep_n(log, "/ERROR]", tmp_path)
    assert want == [2]
    assert out[1] == f"  UNKNOWN latest.log:{want[0]}: [SomeMod/]: Exception loading thing"
