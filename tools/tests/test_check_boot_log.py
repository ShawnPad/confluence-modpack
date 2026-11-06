"""tools/check_boot_log.py: every ERROR or FATAL record in logs/latest.log must match a documented tools/boot_allowlist.txt entry
(v0.3 Task 8c); Minecraft's missing-tag WARN fails a boot whatever the allowlist says, Moonlight's generated data packs must
be the pinned set (Task 10b, D134), and the game rules must be the pinned set with the Twilight Forest guard's OK line (Task
11d, D137). Synthetic logs plus two verbatim detector lines (tools/tests/golden/gamerules-shipped-*.txt); the real boot is
tools/server_boot.sh's job."""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_boot_log  # noqa: E402
from check_boot_log import ALLOWLIST, load_allowlist, records  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

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
# Moonlight's generation line, verbatim. GEN is a good boot's (2026-10-02 00:05, the boot after the bad one: logs/latest.log:595);
# BOOT1_GEN is the bad boot's (2026-10-02 00:01; its debug.log is kept at .run/failed-boots/task10-boot1/debug.log.gz,
# line 10462), which lost Supplementaries' provider (D134).
GEN = ("[02Oct2026 00:05:38.524] [main/INFO] [Moonlight/]: Starting runtime resource generation for pack type SERVER_DATA "
       "with generators [supplementaries:generated_pack, amendments:generated_server_pack]\n")
BOOT1_GEN = ("[02Oct2026 00:01:26.185] [main/INFO] [Moonlight/]: Starting runtime resource generation for pack type SERVER_DATA "
             "with generators [amendments:generated_server_pack]\n")
# The same bad boot's WARN (that debug.log.gz:11132, and again at :11725), verbatim: the biome tags Supplementaries'
# generated pack defines were missing.
BOOT1_WARN = ("[02Oct2026 00:01:31.973] [main/WARN] [net.minecraft.core.MappedRegistry/]: Not all defined tags for registry "
              "ResourceKey[minecraft:root / minecraft:worldgen/biome] are present in data pack: supplementaries:has_barnacles, "
              "supplementaries:has_basalt_ash, supplementaries:has_cave_urns, supplementaries:has_galleons, "
              "supplementaries:has_road_signs, supplementaries:has_wild_flax\n")
# The item- and block-registry forms, verbatim from the boot of 2026-09-29 22:26, before D132 (.run/server/logs/
# 2026-09-29-1.log.gz:690-691): Allthemodium's dead item tags and Cataclysm's tool-tier block tags.
ITEM_WARN = ("[29Sep2026 22:27:00.448] [main/WARN] [net.minecraft.core.MappedRegistry/]: Not all defined tags for registry "
             "ResourceKey[minecraft:root / minecraft:item] are present in data pack: minecraft:enchantable/bow, "
             "minecraft:enchantable/crossbow, minecraft:enchantable/equippable\n")
BLOCK_WARN = ("[29Sep2026 22:27:00.552] [main/WARN] [net.minecraft.core.MappedRegistry/]: Not all defined tags for registry "
              "ResourceKey[minecraft:root / minecraft:block] are present in data pack: cataclysm:needs_black_steel_tool, "
              "cataclysm:needs_monstrosity_tool\n")
# Task 11d (D137): the game-rule detector's line, verbatim from two clone boots of the shipped pack (scratchpad boots shipped-09,
# latest.log:747, all 55 rules; shipped-10, latest.log:745, which lost Twilight Forest's playersTfPortalDefaultDelay), and the
# Twilight Forest guard's OK line, verbatim from a clone boot of the fix (scratchpad boot soak-01, latest.log:430).
GOLDEN = Path(__file__).resolve().parent / "golden"
RULES_09 = (GOLDEN / "gamerules-shipped-09.txt").read_text()
RULES_10 = (GOLDEN / "gamerules-shipped-10.txt").read_text()
GUARD_OK = ("[02Oct2026 18:59:31.625] [modloading-worker-0/INFO] [KubeJS Startup/]: startup_scripts:tf_gamerules_guard.js#112: "
            "confluence tf-gamerules guard OK: registered tfEnforcedProgression, playersTfPortalDefaultDelay, "
            "playersTfPortalCreativeDelay before Twilight Forest construction (rules 51 -> 54)\n")
SUMMARY = "boot log: {} failing records (ERROR, FATAL, missing-tag WARN) in logs/latest.log, {} allowlisted, {} unknown"
NEVER = "(missing-tag WARN: never allowlisted) "
ALLOW = """\
# header comment, separated from the first entry by a blank line

# Curios API: IF ships a curios entities file naming a slot "example" that no mod registers; Curios skips it.
\\[Curios API/\\]: example is not a registered slot type!
"""


def run_dir(tmp_path, log, allow=ALLOW, done=True, gen=True, guard=True, rules=True):
    """A scratch RUN_DIR whose logs/latest.log is `log`, then a good boot's Moonlight line (`gen`), the Twilight Forest guard's
    OK line (`guard`), a good boot's game-rule detector line (`rules`) and the Done line (`done`)."""
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "latest.log").write_text(log + (GEN if gen else "") + (GUARD_OK if guard else "")
                                                  + (RULES_09 if rules else "") + (DONE if done else ""))
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
    assert out.splitlines()[0] == SUMMARY.format(2, 1, 1)
    assert "  UNKNOWN latest.log:4: [SomeMod/]: Exception loading thing" in out
    assert "  java.lang.IllegalStateException: boom\n  \tat a.b.C.d(C.java:1)" in out
    assert "Curios" not in out.split("\n", 1)[1]


def test_allowlisted_errors_and_warnings_pass(tmp_path, capsys):
    d = run_dir(tmp_path, INFO + CURIOS + WARN + CURIOS)
    assert check_boot_log.main([str(d), "--allowlist", str(d / "allow.txt")]) == 0
    assert capsys.readouterr().out.splitlines()[0] == SUMMARY.format(2, 2, 0)


def test_an_entry_must_match_the_whole_record(tmp_path):
    """fullmatch: an entry for one TagLoader record does not cover the same tag missing one more reference."""
    allow = ("# NeoForge: c:tools misses only its bow and crossbow references.\n"
             "\\[net\\.minecraft\\.tags\\.TagLoader/\\]: Couldn't load tag c:tools as it is missing following references: "
             "\\n\\t#c:tools/bow \\(from mod/neoforge\\)\\n\\t#c:tools/crossbow \\(from mod/neoforge\\)\n")
    d = run_dir(tmp_path, TAG_ERR, allow)
    assert check_boot_log.main([str(d), "--allowlist", str(d / "allow.txt")]) == 0
    more = TAG_ERR + "\t#c:tools/shield (from mod/neoforge)\n" + GEN + DONE
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
    """Never allowlist "Tried to load invalid item" (Task 8c brief), but for the air message (D141). Real record shapes, matched as the check matches them
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
    # The owner's one exception (D141): old empty slots in mod structures, this wording and logger only.
    invalid = [e for e in entries if "invalid item" in e.pattern]
    assert len(invalid) == 1, "only the air message may be allowlisted"
    assert invalid[0].fullmatch("[net.minecraft.world.item.ItemStack/]: Tried to load invalid item: 'Item must not be minecraft:air'")
    assert not invalid[0].fullmatch("[KubeJS/]: Tried to load invalid item: 'Item must not be minecraft:air'")


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
    assert out[0] == SUMMARY.format(2, 1, 1)
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


def test_the_help_text_names_the_missing_tag_warning(capsys):
    """Task 10b fix round 1: the description, like the summary line, says the WARN is checked too."""
    with pytest.raises(SystemExit) as e:
        check_boot_log.main(["--help"])
    assert e.value.code == 0
    assert "missing-tag WARN" in " ".join(capsys.readouterr().out.split())


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


# ---- Task 10b (D134): Moonlight's generated data packs must be the pinned set -------------------------------------------
#
# Supplementaries and Amendments each register a SERVER_DATA provider with Moonlight from their mod constructors, and
# Moonlight 3.6.4's registry of them is not thread-safe: on a parallel mod construction one provider can be lost, with no log
# line of its own (D134). Moonlight's one INFO line naming the generators it runs is the signal.

def gen_line(ids, thread="main", level="INFO", kind="SERVER_DATA"):
    return (f"{T} [{thread}/{level}] [Moonlight/]: Starting runtime resource generation for pack type {kind} with generators "
            f"[{', '.join(ids)}]\n")


def check(tmp_path, log, capsys, **kw):
    d = run_dir(tmp_path, log, **kw)
    rc = check_boot_log.main([str(d), "--allowlist", str(d / "allow.txt")])
    return rc, capsys.readouterr().out.splitlines()


SUPP, AMEND = "supplementaries:generated_pack", "amendments:generated_server_pack"


def test_the_pinned_generator_set():
    """EXPECTED_DYNAMIC_PACKS is the set logged by every good boot on record (D134)."""
    assert check_boot_log.EXPECTED_DYNAMIC_PACKS == {"SERVER_DATA": frozenset({SUPP, AMEND})}


@pytest.mark.parametrize("ids", [[SUPP, AMEND], [AMEND, SUPP]])
def test_either_generator_order_passes(tmp_path, capsys, ids):
    """The order varies per JVM (HashMultimap): the check compares sets."""
    rc, out = check(tmp_path, INFO + gen_line(ids), capsys, gen=False)
    assert rc == 0, out
    assert out[-1] == "dynamic packs: 1 Moonlight generation line(s), 0 bad", out


def test_generator_lines_parse_the_real_lines():
    assert check_boot_log.generator_lines(INFO + GEN + BOOT1_GEN) == [
        (2, "SERVER_DATA", frozenset({SUPP, AMEND})), (3, "SERVER_DATA", frozenset({AMEND}))]


def test_boot_1_fails_naming_supplementaries(tmp_path, capsys):
    rc, out = check(tmp_path, INFO + BOOT1_GEN, capsys, gen=False)
    assert rc == 1, out
    assert out[-2:] == ["dynamic packs: 1 Moonlight generation line(s), 1 bad",
                        "  DYNAMIC PACKS latest.log:2: SERVER_DATA missing [supplementaries:generated_pack], unexpected []"]


def test_supplementaries_alone_fails_naming_amendments(tmp_path, capsys):
    rc, out = check(tmp_path, gen_line([SUPP]), capsys, gen=False)
    assert rc == 1, out
    assert out[-1] == "  DYNAMIC PACKS latest.log:1: SERVER_DATA missing [amendments:generated_server_pack], unexpected []"


def test_no_generator_line_fails(tmp_path, capsys):
    """Moonlight logs nothing when its provider list is empty, so a missing line is a failure, not a pass."""
    rc, out = check(tmp_path, INFO + CURIOS, capsys, gen=False)
    assert rc == 1, out
    assert out[-2] == "dynamic packs: 0 Moonlight generation line(s), 1 bad"
    assert out[-1].startswith("  NO DYNAMIC PACK LINE latest.log: no Moonlight generation line for pack type SERVER_DATA"), out
    assert check_boot_log.dynamic_pack_problems(INFO)[0].startswith("NO DYNAMIC PACK LINE")


def test_an_unexpected_generator_fails(tmp_path, capsys):
    """A new id fails too, so the pin is updated when the mod list changes."""
    rc, out = check(tmp_path, gen_line([AMEND, "foo:generated_pack", SUPP]), capsys, gen=False)
    assert rc == 1, out
    assert out[-1] == "  DYNAMIC PACKS latest.log:1: SERVER_DATA missing [], unexpected [foo:generated_pack]"


def test_a_bad_second_line_fails(tmp_path, capsys):
    """Moonlight logs the line again on /reload (from the thread running it) [UNVERIFIED]; every line must hold the set."""
    log = GEN + INFO + gen_line([AMEND], thread="Server thread")
    rc, out = check(tmp_path, log, capsys, gen=False)
    assert rc == 1, out
    assert out[-2:] == ["dynamic packs: 2 Moonlight generation line(s), 1 bad",
                        "  DYNAMIC PACKS latest.log:3: SERVER_DATA missing [supplementaries:generated_pack], unexpected []"]


def test_a_bad_first_line_fails_even_when_a_later_one_is_good(tmp_path, capsys):
    """Task 10b fix round 1 (mutant M6c): a later good line (a /reload) does not excuse a bad first one."""
    log = gen_line([AMEND]) + INFO + GEN
    rc, out = check(tmp_path, log, capsys, gen=False)
    assert rc == 1, out
    assert out[-2:] == ["dynamic packs: 2 Moonlight generation line(s), 1 bad",
                        "  DYNAMIC PACKS latest.log:1: SERVER_DATA missing [supplementaries:generated_pack], unexpected []"]


def test_a_server_thread_line_is_parsed(tmp_path, capsys):
    rc, out = check(tmp_path, gen_line([SUPP, AMEND], thread="Server thread"), capsys, gen=False)
    assert (rc, out[-1]) == (0, "dynamic packs: 1 Moonlight generation line(s), 0 bad"), out


def test_only_info_header_lines_count():
    """A DEBUG copy, a line inside another record, and a line with trailing text are not Moonlight's INFO line."""
    log = (gen_line([AMEND], level="DEBUG") + CURIOS.rstrip("\n") + "\n" + gen_line([AMEND])[len(T) + 1:]
           + gen_line([AMEND]).rstrip("\n") + " (again)\n")
    assert check_boot_log.generator_lines(log) == []


def test_a_client_resources_line_is_ignored(tmp_path, capsys):
    rc, out = check(tmp_path, gen_line(["supplementaries:generated_assets"], kind="CLIENT_RESOURCES"), capsys)
    assert (rc, out[-1]) == (0, "dynamic packs: 1 Moonlight generation line(s), 0 bad"), out


def test_dynamic_pack_problems_takes_the_expected_sets():
    assert check_boot_log.dynamic_pack_problems(GEN, expected={"SERVER_DATA": frozenset({SUPP, AMEND})}) == []
    assert check_boot_log.dynamic_pack_problems(GEN, expected={"SERVER_DATA": frozenset({AMEND})}) == [
        "DYNAMIC PACKS latest.log:1: SERVER_DATA missing [], unexpected [supplementaries:generated_pack]"]


def test_the_problem_is_reported_beside_an_unknown_error(tmp_path, capsys):
    rc, out = check(tmp_path, UNKNOWN + BOOT1_GEN, capsys, gen=False)
    assert rc == 1, out
    assert out[0] == SUMMARY.format(1, 0, 1)
    assert "  UNKNOWN latest.log:1: [SomeMod/]: Exception loading thing" in out
    assert out[-1] == "  DYNAMIC PACKS latest.log:4: SERVER_DATA missing [supplementaries:generated_pack], unexpected []"


def test_the_problem_is_reported_on_an_incomplete_log(tmp_path, capsys):
    rc, out = check(tmp_path, INFO + BOOT1_GEN, capsys, gen=False, done=False)
    assert rc == 1, out
    assert out[0].startswith("INCOMPLETE LOG")
    assert out[-1] == "  DYNAMIC PACKS latest.log:2: SERVER_DATA missing [supplementaries:generated_pack], unexpected []"


def test_each_expected_generator_has_its_mod_in_the_pack():
    """Drift guard: mods/<file> exists exactly when its generator is pinned. Removing Supplementaries or Amendments, or pinning
    a generator with no mapped mod, fails here first. Ids: supplementaries-1.21.1-3.9.9-neoforge.jar ModServerDynamicResources
    and amendments-1.21-2.1.10-neoforge.jar WallLanternServerResources (javap -c: their constructors pass "generated_pack" and
    "generated_server_pack" to Supplementaries.res / Amendments.res)."""
    owners = {SUPP: "supplementaries.pw.toml", AMEND: "amendments.pw.toml"}
    pinned = set().union(*check_boot_log.EXPECTED_DYNAMIC_PACKS.values())
    assert pinned <= set(owners), f"no mod file mapped for {sorted(pinned - set(owners))}"
    assert {gen: (ROOT / "mods" / f).is_file() for gen, f in owners.items()} == {gen: gen in pinned for gen in owners}


# ---- Task 10b (D134): Minecraft's missing-tag WARN fails a boot, whatever the allowlist says -----------------------------

def unknown_line(n, warn):
    return f"  UNKNOWN latest.log:{n}: {NEVER}{warn[warn.index('[net.'):].rstrip(chr(10))}"


@pytest.mark.parametrize("warn", [BOOT1_WARN, ITEM_WARN, BLOCK_WARN], ids=["biome", "item", "block"])
def test_the_missing_tag_warning_is_a_failing_record(tmp_path, capsys, warn):
    """Each registry's verbatim WARN is an unknown record, whichever registry it names (a biome-only pattern fails here)."""
    rc, out = check(tmp_path, INFO + warn, capsys)
    assert rc == 1, out
    assert out[0] == SUMMARY.format(1, 0, 1)
    assert out[1] == unknown_line(2, warn)


# Entries that would cover the WARN if it went through the allowlist: the verify lens's crafted form (Mapped\w+, \s), a plain
# one, and a catch-all.
CRAFTED = [
    "\\[net\\.minecraft\\.core\\.Mapped\\w+/\\]:\\sNot\\sall\\sdefined\\stags\\sfor\\sregistry\\s.*",
    "\\[net\\.minecraft\\.core\\.MappedRegistry/\\]: Not all defined tags for registry ResourceKey\\[minecraft:root / .*",
    ".*",
]


@pytest.mark.parametrize("entry", CRAFTED)
@pytest.mark.parametrize("warn", [BOOT1_WARN, ITEM_WARN, BLOCK_WARN], ids=["biome", "item", "block"])
def test_no_allowlist_entry_can_cover_the_missing_tag_warning(tmp_path, capsys, warn, entry):
    """Task 10b fix round 1 (F2): the policy is mechanical. Even with an entry that fullmatches the WARN in a scratch copy of the
    shipped allowlist, the record stays unknown and the entry is reported unused."""
    assert re.fullmatch(entry, warn[warn.index("[net."):].rstrip("\n")), "the scratch entry must match the record"
    run_dir(tmp_path, INFO + warn + CURIOS)
    allow = tmp_path / "allow-copy.txt"
    shutil.copyfile(ALLOWLIST, allow)
    with allow.open("a") as f:
        f.write(f"\n# scratch entry for this test only\n{entry}\n")
    assert check_boot_log.main([str(tmp_path), "--allowlist", str(allow)]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0] == SUMMARY.format(2, 1, 1), out   # the shipped Curios entry covers the ERROR; nothing covers the WARN
    assert unknown_line(2, warn) in out
    assert f"  (unused allowlist entry: {entry})" in out


@pytest.mark.parametrize("level", ["INFO", "DEBUG"])
def test_the_missing_tag_text_at_another_level_is_not_a_record(tmp_path, capsys, level):
    """Task 10b fix round 1 (mutant M2c): only the WARN header fails; the same text logged at INFO or DEBUG is not a record."""
    for warn in (BOOT1_WARN, ITEM_WARN):
        rc, out = check(tmp_path, INFO + warn.replace("/WARN]", f"/{level}]"), capsys)
        assert (rc, out[0]) == (0, SUMMARY.format(0, 0, 0)), out
        shutil.rmtree(tmp_path / "logs")


def test_scan_takes_the_missing_tag_warning_with_its_line():
    assert records(INFO + WARN + BOOT1_WARN) == [(3, BOOT1_WARN[BOOT1_WARN.index("[net."):].rstrip("\n"))]
    assert [n for n, _ in records(ITEM_WARN + INFO + BLOCK_WARN)] == [1, 3]


@pytest.mark.parametrize("warn", [
    WARN,
    f"{T} [main/WARN] [net.minecraft.core.MappedRegistry/]: Something else about tags\n",
    f"{T} [main/WARN] [some.Other/]: Not all defined tags for registry ResourceKey[minecraft:root / minecraft:item] are x\n",
    "[20:50:32] [main/WARN] [minecraft/MappedRegistry]: Not all defined tags for registry ResourceKey[minecraft:root / "
    "minecraft:item] are present in data pack: a:b\n",
])
def test_other_warnings_are_still_ignored(tmp_path, capsys, warn):
    """Only MappedRegistry's missing-tag WARN in latest.log's form fails; console.log's short logger name is not latest.log's."""
    rc, out = check(tmp_path, INFO + warn, capsys)
    assert rc == 0, out
    assert out[0] == SUMMARY.format(0, 0, 0)


def test_the_shipped_allowlist_never_covers_a_missing_tag_warning():
    """Task 10b brief: no allowlist entry for the missing-tag WARN; it is fixed at the source or it fails the boot. main()
    never consults the allowlist for it (above); this keeps the shipped file free of such an entry too."""
    recs = [text for _, text in records(BOOT1_WARN + ITEM_WARN + BLOCK_WARN)]
    assert len(recs) == 3
    entries = load_allowlist(ALLOWLIST)
    assert not [e.pattern for e in entries for r in recs if e.fullmatch(r)]
    assert not [e for e in entries if "MappedRegistry" in e.pattern or "defined tags" in e.pattern]


# ---- Task 11d (D137): the game rules must be the pinned set, and the Twilight Forest guard must have run ------------------
#
# Twilight Forest 4.8.3345 registers its three game rules from three Worker-Main tasks at once, into vanilla's unsynchronised
# TreeMap GameRules.GAME_RULE_TYPES, which can lose any key (shipped-10 lost playersTfPortalDefaultDelay and this check's
# predecessor passed it). kubejs/startup_scripts/tf_gamerules_guard.js registers them first, on one thread, and logs one OK
# line; kubejs/server_scripts/gamerules.js logs the rule names of the server's GameRules and of a fresh GameRules() once per
# server start. tools/gamerules.toml pins the names (51 vanilla + 3 Twilight Forest + 1 Accessories).

RULES_SUMMARY = "game rules: 55 expected, server {}, registry {}, guard {}"
NO_GUARD = ("NO GUARD LINE latest.log: no INFO line '[KubeJS Startup/]: startup_scripts:tf_gamerules_guard.js#<n>: confluence "
            "tf-gamerules guard OK: ...'; the Twilight Forest game-rule guard did not run (D137)")
NO_RULES = ("NO GAMERULES LINE latest.log: no INFO line '[KubeJS Server/]: confluence gamerules: ...'; the detector "
            "(kubejs/server_scripts/gamerules.js) never logged, or the server never reached ServerStartingEvent (D137)")


def names_of(line, which):
    """The names listed in a detector line's `which` part ('server' or 'registry')."""
    part = line.split(f"{which} ", 1)[1]
    return part[part.index("[") + 1:part.index("]")].split(",")


def rules_line(server, registry, level="INFO", ts="[02Oct2026 10:18:48.908]"):
    return (f"{ts} [Server thread/{level}] [KubeJS Server/]: confluence gamerules: server {len(server)} "
            f"[{','.join(sorted(server))}]; registry {len(registry)} [{','.join(sorted(registry))}]\n")


ALL = names_of(RULES_09, "server")


def rules_out(out):
    """The game-rule section of main()'s output: its summary line and the problem lines under it."""
    i = next(i for i, line in enumerate(out) if line.startswith("game rules: "))
    j = next((k for k in range(i + 1, len(out)) if not out[k].startswith("  ")), len(out))
    return out[i:j]


def test_the_pinned_game_rules_are_51_vanilla_and_4_modded():
    pin = check_boot_log.load_gamerules()
    assert len(pin.vanilla) == 51 and len(set(pin.vanilla)) == 51
    assert {m["id"]: m["mod"] for m in pin.modded} == {
        "tfEnforcedProgression": "twilightforest", "playersTfPortalDefaultDelay": "twilightforest",
        "playersTfPortalCreativeDelay": "twilightforest", "accessories.keepAccessoryInventory": "accessories"}
    assert check_boot_log.expected_gamerules(pin) == frozenset(pin.vanilla) | {m["id"] for m in pin.modded}
    assert len(check_boot_log.expected_gamerules(pin)) == 55
    assert "playersSleepingPercentage" in pin.vanilla   # the rule the 2026-09-12 and 2026-10-02 crashes found null


def test_the_good_fixture_lists_exactly_the_pinned_rules():
    assert sorted(ALL) == sorted(check_boot_log.expected_gamerules(check_boot_log.load_gamerules()))
    assert names_of(RULES_09, "registry") == ALL


@pytest.mark.parametrize("text,msg", [
    ('[vanilla]\nnames = ["a", "a"]\n', "vanilla name 'a' is listed twice"),
    ('[vanilla]\nnames = ["a"]\n[[modded]]\nid = "a"\nmod = "m"\n', "modded id 'a' is also a vanilla name"),
    ('[vanilla]\nnames = ["a"]\n[[modded]]\nid = "b"\n', "modded entry 'b' has no mod"),
    ('[vanilla]\nnames = []\n', "no vanilla names"),
    ('names = ["a"]\n', "no vanilla names"),
    ('[vanilla]\nnames = ["a"]\n[[modded]]\nmod = "m"\n', "a modded entry has no id"),
    ('[vanilla]\nnames = ["a"]\n[[modded]]\nid = ""\nmod = "m"\n', "a modded entry has no id"),
    ('[vanilla]\nnames = ["a"]\n[[modded]]\nid = 7\nmod = "m"\n', "a modded entry has no id"),
    ('vanilla = 3\n', "no vanilla names"),
    ('[vanilla]\nnames = "abc"\n', "no vanilla names"),
    ('[vanilla]\nnames = [1]\n', "no vanilla names"),
    ('modded = 3\n[vanilla]\nnames = ["a"]\n', "modded is not a list of tables"),
    ('modded = [3]\n[vanilla]\nnames = ["a"]\n', "modded is not a list of tables"),
    ('register_call = 5\n[vanilla]\nnames = ["a"]\n', "register_call is not a list of tables"),
    ('register_call = true\n[vanilla]\nnames = ["a"]\n', "register_call is not a list of tables"),
    ('register_call = "x"\n[vanilla]\nnames = ["a"]\n', "register_call is not a list of tables"),
    ('register_call = [1]\n[vanilla]\nnames = ["a"]\n', "register_call is not a list of tables"),
])
def test_a_bad_game_rule_pin_is_rejected(tmp_path, text, msg):
    f = tmp_path / "gamerules.toml"
    f.write_text(text)
    with pytest.raises(ValueError, match=msg):
        check_boot_log.load_gamerules(f)


def standalone_checker(tmp_path, pin=None):
    """A copy of the checker under tmp_path/tools, so its ROOT is tmp_path: an empty allowlist, and tools/gamerules.toml only
    when `pin` is given. A callable pin makes the file itself."""
    tools = tmp_path / "tools"
    tools.mkdir()
    shutil.copy(ROOT / "tools" / "check_boot_log.py", tools)
    (tools / "boot_allowlist.txt").write_text("")
    if callable(pin):
        pin(tools / "gamerules.toml")
    elif pin is not None:
        (tools / "gamerules.toml").write_text(pin)
    return tools / "check_boot_log.py"


def run_checker(script, *args):
    res = subprocess.run([sys.executable, "-I", str(script), *map(str, args)], capture_output=True, text=True, timeout=60)
    return res.returncode, res.stdout, res.stderr


BAD_PINS = {
    "missing": None,
    "a directory": lambda p: p.mkdir(),
    "not TOML": "[vanilla\n",
    "not UTF-8": lambda p: p.write_bytes(b"\xff\xfe"),
    "a repeated name": '[vanilla]\nnames = ["a", "a"]\n',
    "a modded entry with no id": '[vanilla]\nnames = ["a"]\n[[modded]]\nmod = "m"\n',
    "the wrong shape": "vanilla = 3\n",
}


@pytest.mark.parametrize("pin", BAD_PINS.values(), ids=BAD_PINS.keys())
def test_help_works_with_a_bad_pin(tmp_path, pin):
    rc, out, err = run_checker(standalone_checker(tmp_path, pin), "--help")
    assert rc == 0 and "usage: check_boot_log.py" in out and err == "", (out, err)


@pytest.mark.parametrize("pin", BAD_PINS.values(), ids=BAD_PINS.keys())
def test_a_usage_error_is_a_usage_error_with_a_bad_pin(tmp_path, pin):
    rc, _, err = run_checker(standalone_checker(tmp_path, pin))
    assert rc == 2 and "usage: check_boot_log.py" in err and "Traceback" not in err, err


@pytest.mark.parametrize("pin", BAD_PINS.values(), ids=BAD_PINS.keys())
def test_a_bad_pin_exits_4_and_still_prints_the_other_sections(tmp_path, pin):
    script = standalone_checker(tmp_path, pin)
    run = run_dir(tmp_path, UNKNOWN)
    rc, out, err = run_checker(script, run)
    lines = out.splitlines()
    assert rc == 4, (out, err)
    assert "Traceback" not in err, err
    assert lines[0].startswith(f"BAD GAMERULES PIN {script.parent / 'gamerules.toml'}: "), lines
    assert "boot log: 1 failing records (ERROR, FATAL, missing-tag WARN) in logs/latest.log, 0 allowlisted, 1 unknown" in lines
    assert "  UNKNOWN latest.log:1: [SomeMod/]: Exception loading thing" in lines
    assert "game rules: not checked (bad pin)" in lines
    assert "dynamic packs: 1 Moonlight generation line(s), 0 bad" in lines


def test_a_bad_pin_still_names_a_missing_log(tmp_path):
    rc, out, _ = run_checker(standalone_checker(tmp_path), tmp_path / "no-run-dir")
    assert rc == 1
    assert [line.split(" ")[0] for line in out.splitlines()] == ["BAD", "MISSING"]


def test_a_good_pin_is_read_from_tools_when_the_checker_runs(tmp_path):
    """The standalone copy passes with a pin it can read, so the bad-pin tests above fail because of the pin."""
    script = standalone_checker(tmp_path, (ROOT / "tools" / "gamerules.toml").read_text())
    rc, out, err = run_checker(script, run_dir(tmp_path, INFO))
    assert rc == 0, (out, err)


def test_gamerule_problems_requires_the_expected_set():
    with pytest.raises(TypeError):
        check_boot_log.gamerule_problems(GUARD_OK + RULES_09)


def test_a_good_boot_passes_with_one_summary_line(tmp_path, capsys):
    rc, out = check(tmp_path, INFO, capsys)
    assert rc == 0, out
    assert rules_out(out) == [RULES_SUMMARY.format(55, 55, "OK")]


def test_shipped_10_fails_naming_the_lost_rule(tmp_path, capsys):
    """The real line of the boot that lost Twilight Forest's playersTfPortalDefaultDelay (the old check passed it)."""
    rc, out = check(tmp_path, INFO + RULES_10, capsys, rules=False)
    assert rc == 1, out
    assert rules_out(out) == [
        RULES_SUMMARY.format(54, 54, "OK") + ", 2 bad",
        "  GAMERULES latest.log:2: server missing [playersTfPortalDefaultDelay], unexpected []",
        "  GAMERULES latest.log:2: registry missing [playersTfPortalDefaultDelay], unexpected []"]


def test_a_lost_vanilla_rule_is_named(tmp_path, capsys):
    """The crash's rule: a server instance without playersSleepingPercentage."""
    short = [n for n in ALL if n != "playersSleepingPercentage"]
    rc, out = check(tmp_path, rules_line(short, short), capsys, rules=False)
    assert rc == 1, out
    assert rules_out(out)[1:] == [
        "  GAMERULES latest.log:1: server missing [playersSleepingPercentage], unexpected []",
        "  GAMERULES latest.log:1: registry missing [playersSleepingPercentage], unexpected []"]


@pytest.mark.parametrize("level", ["WARN", "ERROR"])
def test_a_detector_line_at_another_level_fails(tmp_path, capsys, level):
    """Only an INFO line is the detector's: the same text at WARN or ERROR is reported, and does not count as the line."""
    rc, out = check(tmp_path, RULES_09.replace("/INFO]", f"/{level}]"), capsys, rules=False)
    assert rc == 1, out
    assert rules_out(out) == [RULES_SUMMARY.format("none", "none", "OK") + ", 2 bad",
                              f"  GAMERULES latest.log:1: the detector line is logged at {level}, not INFO",
                              f"  {NO_RULES}"]


def test_a_missing_guard_line_fails(tmp_path, capsys):
    rc, out = check(tmp_path, INFO, capsys, guard=False)
    assert rc == 1, out
    assert rules_out(out) == [RULES_SUMMARY.format(55, 55, "missing") + ", 1 bad", f"  {NO_GUARD}"]


@pytest.mark.parametrize("line", [
    GUARD_OK.replace("/INFO]", "/WARN]"),                                              # not INFO
    GUARD_OK.replace("[KubeJS Startup/]", "[KubeJS Server/]"),                          # another script type
    GUARD_OK.replace("tf_gamerules_guard.js", "zz_tf_gamerules_guard_v2.js"),          # another script
    GUARD_OK.replace("startup_scripts:tf_gamerules_guard.js#112: ", ""),               # no script prefix
    GUARD_OK.replace("guard OK: ", "guard: "),                                         # not the OK line
    GUARD_OK.replace(" guard OK: registered", " guard: startup scripts reloaded;"),    # the reload line
    GUARD_OK[len("[02Oct2026 18:59:31.625] "):],                                       # not a log4j header line
])
def test_only_the_guard_ok_line_counts(tmp_path, capsys, line):
    rc, out = check(tmp_path, line, capsys, guard=False)
    assert rc == 1, out
    assert rules_out(out)[-1] == f"  {NO_GUARD}"


def test_the_guard_line_number_is_not_pinned(tmp_path, capsys):
    rc, out = check(tmp_path, GUARD_OK.replace("#112:", "#7:"), capsys, guard=False)
    assert rc == 0, out


def test_two_guard_lines_fail(tmp_path, capsys):
    rc, out = check(tmp_path, GUARD_OK, capsys)
    assert rc == 1, out
    assert rules_out(out) == [RULES_SUMMARY.format(55, 55, "2 lines") + ", 1 bad",
                              "  GUARD latest.log: 2 guard OK lines (lines 1, 3); expected exactly one per boot"]


def test_server_and_registry_diverging_fails(tmp_path, capsys):
    short = [n for n in ALL if n != "randomTickSpeed"]
    rc, out = check(tmp_path, rules_line(ALL, short), capsys, rules=False)
    assert rc == 1, out
    assert rules_out(out) == [
        RULES_SUMMARY.format(55, 54, "OK") + ", 2 bad",
        "  GAMERULES latest.log:1: registry missing [randomTickSpeed], unexpected []",
        "  GAMERULES latest.log:1: server and registry differ: only in server [randomTickSpeed], only in registry []"]


def test_an_unexpected_extra_rule_fails(tmp_path, capsys):
    """A new rule fails too, so the pin follows the mod list (tools/gamerules.toml)."""
    more = ALL + ["bogus.newRule"]
    rc, out = check(tmp_path, rules_line(more, more), capsys, rules=False)
    assert rc == 1, out
    assert rules_out(out)[1:] == ["  GAMERULES latest.log:1: server missing [], unexpected [bogus.newRule]",
                                  "  GAMERULES latest.log:1: registry missing [], unexpected [bogus.newRule]"]


def test_two_detector_lines_fail(tmp_path, capsys):
    """One line per server start: a second one is reported even when both are good."""
    rc, out = check(tmp_path, RULES_09, capsys)
    assert rc == 1, out
    assert rules_out(out) == [RULES_SUMMARY.format("55/55", "55/55", "OK") + ", 1 bad",
                              "  GAMERULES latest.log: 2 detector lines (lines 1, 4); expected exactly one per boot"]


def test_each_of_two_detector_lines_is_checked(tmp_path, capsys):
    rc, out = check(tmp_path, RULES_10, capsys)
    assert rc == 1, out
    assert rules_out(out)[1:] == [
        "  GAMERULES latest.log: 2 detector lines (lines 1, 4); expected exactly one per boot",
        "  GAMERULES latest.log:1: server missing [playersTfPortalDefaultDelay], unexpected []",
        "  GAMERULES latest.log:1: registry missing [playersTfPortalDefaultDelay], unexpected []"]


def test_no_detector_line_on_a_boot_that_reached_done_fails(tmp_path, capsys):
    rc, out = check(tmp_path, INFO, capsys, rules=False)
    assert rc == 1, out
    assert out[0] == SUMMARY.format(0, 0, 0)            # nothing else is wrong: the Done line is there
    assert rules_out(out) == [RULES_SUMMARY.format("none", "none", "OK") + ", 1 bad", f"  {NO_RULES}"]


def test_no_detector_line_on_an_incomplete_log_is_reported_too(tmp_path, capsys):
    rc, out = check(tmp_path, INFO, capsys, rules=False, guard=False, done=False)
    assert rc == 1, out
    assert out[0].startswith("INCOMPLETE LOG")
    assert rules_out(out)[1:] == [f"  {NO_GUARD}", f"  {NO_RULES}"]


def test_a_count_that_disagrees_with_its_names_fails(tmp_path, capsys):
    rc, out = check(tmp_path, RULES_09.replace("server 55 [", "server 54 ["), capsys, rules=False)
    assert rc == 1, out
    assert rules_out(out)[1:] == ["  GAMERULES latest.log:1: server count 54 but 55 names listed"]


def test_a_repeated_name_fails(tmp_path, capsys):
    twice = ALL[:-1] + [ALL[0]]
    rc, out = check(tmp_path, rules_line(twice, ALL), capsys, rules=False)
    assert rc == 1, out
    assert f"  GAMERULES latest.log:1: server lists {ALL[0]} twice" in rules_out(out)


def test_a_script_prefixed_detector_line_is_read(tmp_path, capsys):
    """KubeJS prefixes a console line with its script and line when it has them (worldgen.js's line does); either form is
    the detector's line."""
    line = RULES_09.replace("[KubeJS Server/]: ", "[KubeJS Server/]: server_scripts:gamerules.js#30: ")
    rc, out = check(tmp_path, line, capsys, rules=False)
    assert rc == 0, out


def test_a_detector_line_inside_another_record_is_not_read(tmp_path, capsys):
    rc, out = check(tmp_path, CURIOS.rstrip("\n") + " " + RULES_09[len("[02Oct2026 10:18:48.908] "):], capsys, rules=False)
    assert rc == 1, out
    assert rules_out(out)[-1] == f"  {NO_RULES}"


def test_detector_text_inside_another_info_line_is_not_read(tmp_path, capsys):
    """The whole text after the header must be the detector's: a mod's INFO line quoting it proves nothing about this boot."""
    quoted = RULES_09[RULES_09.index("[KubeJS Server/]: "):]
    rc, out = check(tmp_path, f"{T} [main/INFO] [SomeMod/]: saw {quoted}", capsys, rules=False)
    assert rc == 1, out
    assert rules_out(out) == ["game rules: 55 expected, server none, registry none, guard OK, 1 bad", f"  {NO_RULES}"]


def test_gamerule_problems_takes_the_expected_set():
    summary, problems = check_boot_log.gamerule_problems(GUARD_OK + RULES_09, expected=frozenset(ALL) - {"doFireTick"})
    assert summary == "game rules: 54 expected, server 55, registry 55, guard OK, 2 bad"
    assert problems == ["GAMERULES latest.log:2: server missing [], unexpected [doFireTick]",
                        "GAMERULES latest.log:2: registry missing [], unexpected [doFireTick]"]


def test_the_game_rule_problem_is_reported_beside_the_others(tmp_path, capsys):
    rc, out = check(tmp_path, UNKNOWN + BOOT1_GEN + RULES_10, capsys, gen=False, rules=False)
    assert rc == 1, out
    assert out[0] == SUMMARY.format(1, 0, 1)
    assert rules_out(out)[0] == RULES_SUMMARY.format(54, 54, "OK") + ", 2 bad"
    assert out[-1] == "  DYNAMIC PACKS latest.log:4: SERVER_DATA missing [supplementaries:generated_pack], unexpected []"


def test_the_help_text_names_the_game_rules(capsys):
    with pytest.raises(SystemExit):
        check_boot_log.main(["--help"])
    assert "game rules" in " ".join(capsys.readouterr().out.split())
