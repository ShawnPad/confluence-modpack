"""tools/check_boot_log.py: every ERROR or FATAL record in logs/latest.log must match a documented tools/boot_allowlist.txt entry
(v0.3 Task 8c); Minecraft's missing-tag WARN fails a boot whatever the allowlist says, and Moonlight's generated data packs must
be the pinned set (Task 10b, D134). Synthetic logs only; the real boot is tools/server_boot.sh's job."""
import re
import shutil
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
SUMMARY = "boot log: {} failing records (ERROR, FATAL, missing-tag WARN) in logs/latest.log, {} allowlisted, {} unknown"
NEVER = "(missing-tag WARN: never allowlisted) "
ALLOW = """\
# header comment, separated from the first entry by a blank line

# Curios API: IF ships a curios entities file naming a slot "example" that no mod registers; Curios skips it.
\\[Curios API/\\]: example is not a registered slot type!
"""


def run_dir(tmp_path, log, allow=ALLOW, done=True, gen=True):
    """A scratch RUN_DIR whose logs/latest.log is `log`, then a good boot's Moonlight line (`gen`) and the Done line (`done`)."""
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "latest.log").write_text(log + (GEN if gen else "") + (DONE if done else ""))
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
