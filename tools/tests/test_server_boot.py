"""tools/server_boot.sh's post-boot checks (v0.3 Task 8c round 2, minors 5 and 11), run in bash against a synthetic server
directory with stand-in checker scripts; the real boot is the script's own job.

  - post_boot_checks runs every check, prints each failing check's label, and exits with the combined status: one failing
    check no longer hides the ones after it;
  - tools/check_boot_log.py's exit codes get distinct labels: 1 BOOT LOG ERRORS (an unknown record, a game-rule or
    dynamic-pack problem, or an incomplete log), 2 a usage error, 3 BAD ALLOWLIST, 4 BAD GAMERULES PIN; none of them reads as an
    unknown log error it is not;
  - the background processes the boot starts (packwiz serve, run.sh and its java child) are killed by an EXIT trap, so a boot
    that dies under `set -e` leaves nothing running;
  - a boot whose checks fail keeps its evidence (v0.3 Task 10b, D134): post_boot_checks copies logs/latest.log,
    logs/debug.log, console.log, logs/kubejs/startup.log, logs/kubejs/server.log and kubejs/exported/recipes.json into
    .run/failed-boots/<UTC timestamp>/ and prints the path, since the next boot deletes or rotates every one of them. When
    that directory cannot be made, it says so ("NOT CREATED") and the boot still ends with BOOT CHECKS FAILED. The archive
    is always under the pack's own .run/, so a SOURCE file in it names the server directory the evidence came from.
  - a server still running at the end of the 60 s stop wait is thread-dumped before its SIGKILL (v0.3 Task 11c): `jcmd <java
    pid> Thread.print -l`, given 30 s, goes to stop-threads.txt and is appended to console.log (so the failed-boot archive
    keeps it) once java is dead; a stale stop-threads.txt is deleted at boot start. When java exits on its own while jcmd
    runs (a stop just over 60 s; jcmd then fails to attach), the dump says so.
  - forced chunks fail the boot (v0.3 Task 11c fix, D136): post_boot_checks runs tools/count_forced_chunks.py on the server
    directory (so a boot runs it after the server has stopped, and --check runs it too). It prints `forced chunks: 0 (mod
    tickets: 0; ...)` when none are left; otherwise its per-dimension counts and hint, and the label FORCED CHUNKS, and the
    boot fails and is archived like any other failed check. A chunks.dat it cannot read fails too (FORCED CHUNKS CHECK
    ERROR), and so does a boot whose run directory has no world; --check on a folder without one (a failed-boot archive)
    says so (`forced chunks: 0 (no world at ...)`) and passes.
  - once the server is declared hung (alive at the end of the 60 s wait), the EXIT trap is re-armed to SIGKILL java and the
    jcmd dump, so an interrupt during the dump leaves neither behind (Task 11c fix round 2, M1); a jcmd still running after
    its 30 s is SIGKILLed and reaped before its note is appended, so it cannot write over the note (M2); and java is
    SIGKILLed only while it still runs (M3).
"""
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from test_count_forced_chunks import chunks_dat  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "server_boot.sh"
# The real reader, not a stub: an empty world folder holds no forced chunk, so it prints `forced chunks: 0 (...)` and exits 0.
FORCED_READER = ROOT / "tools" / "count_forced_chunks.py"
STUB = '''import os, sys
print("ran {name}", " ".join(sys.argv[1:]))
sys.exit(int(os.environ.get("{env}", "0")))
'''


def function_source():
    m = re.search(r"^post_boot_checks\(\) \{\n.*?^\}\n", SCRIPT.read_text(), re.M | re.S)
    assert m, "tools/server_boot.sh has no post_boot_checks() { ... } block"
    return m.group(0)


@pytest.fixture
def fake(tmp_path):
    root, run = tmp_path / "root", tmp_path / "run"
    (root / "tools").mkdir(parents=True)
    for name, env in (("check_configs.py", "STUB_CONFIGS"), ("check_boot_log.py", "STUB_BOOT_LOG")):
        (root / "tools" / name).write_text(STUB.format(name=name, env=env))
    shutil.copy(FORCED_READER, root / "tools")
    (run / "world").mkdir(parents=True)   # a server that reached Done has always created its world
    (run / "logs" / "kubejs").mkdir(parents=True)
    for log in ("logs/latest.log", "logs/kubejs/startup.log", "logs/kubejs/server.log"):
        (run / log).write_text("[01Oct2026 22:26:26.226] [main/INFO] [x/]: fine\n")
    (run / "console.log").write_text('[22:26:26] [Server thread/INFO] [minecraft/DedicatedServer]: Done (6.4s)! For help\n'
                                     "[22:26:27] [Server thread/INFO] [FTB Quests/]: Loaded 3 chapters\n")
    return root, run


def checks(fake, **env):
    root, run = fake
    cmd = f'set -euo pipefail\nROOT="{root}"\n{function_source()}post_boot_checks "{run}"\n'
    res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, env={**os.environ, **env}, timeout=60)
    return res.returncode, res.stdout.splitlines()


def test_all_checks_pass(fake):
    code, out = checks(fake)
    assert code == 0 and out[-1] == "BOOT OK", out


@pytest.mark.parametrize("rc, label", [("1", "BOOT LOG ERRORS"), ("2", "BOOT LOG CHECK USAGE ERROR"), ("3", "BAD ALLOWLIST"),
                                       ("4", "BAD GAMERULES PIN")])
def test_each_boot_log_exit_code_has_its_own_label(fake, rc, label):
    code, out = checks(fake, STUB_BOOT_LOG=rc)
    assert code == 1 and "BOOT OK" not in out, out
    assert [line for line in out if line.isupper() or line.startswith(("BOOT", "BAD"))] == [label, "BOOT CHECKS FAILED"]
    assert "UNKNOWN LOG ERRORS" not in out


def test_the_real_checker_with_no_pin_gets_the_pin_label(fake):
    """The real tools/check_boot_log.py, no stub, under a root with no tools/gamerules.toml: not an unknown log error, and the
    boot still fails (v0.3 Task 11d, D137)."""
    root, _ = fake
    (root / "tools" / "check_boot_log.py").unlink()
    shutil.copy(SCRIPT.parent / "check_boot_log.py", root / "tools")
    (root / "tools" / "boot_allowlist.txt").write_text("")
    code, out = checks(fake)
    assert code == 1 and "BOOT OK" not in out, out
    assert "BAD GAMERULES PIN" in out and "BOOT CHECKS FAILED" in out and "BOOT LOG ERRORS" not in out, out
    assert "Traceback" not in "\n".join(out), out


def test_every_check_runs_and_the_status_is_combined(fake):
    root, run = fake
    (run / "console.log").write_text("[22:26:26] [main/INFO] [x/]: no done line\n")
    (run / "logs" / "kubejs" / "server.log").write_text("[22:26:26] [ERROR] boom\n")
    (run / "logs" / "latest.log").write_text("Parsing error loading recipe x:y\n")
    code, out = checks(fake, STUB_CONFIGS="1", STUB_BOOT_LOG="3")
    labels = [line for line in out if re.fullmatch(r"[A-Z][A-Z ]+[A-Z]", line)]
    assert code == 1
    assert labels == ["BOOT FAILED", "KUBEJS ERRORS", "RECIPE PARSE ERRORS", "CONFIG ERRORS", "BAD ALLOWLIST",
                      "BOOT CHECKS FAILED"], out
    assert any(line.startswith("ran check_configs.py") for line in out) and any(
        line.startswith("ran check_boot_log.py") for line in out)


# ---- Task 10b: a failed boot's evidence is archived ------------------------------------------------------------------

ARCHIVED = ("logs/latest.log", "logs/debug.log", "console.log", "logs/kubejs/startup.log", "logs/kubejs/server.log",
            "kubejs/exported/recipes.json")


def archives(root):
    base = root / ".run" / "failed-boots"
    return sorted(base.iterdir()) if base.is_dir() else []


def full_run(run):
    """The two files the fake run directory lacks, so every archived file exists."""
    (run / "logs" / "debug.log").write_text("[01Oct2026 22:26:26.226] [main/DEBUG] [x/]: debug\n")
    (run / "kubejs" / "exported").mkdir(parents=True)
    (run / "kubejs" / "exported" / "recipes.json").write_text('{"recipes": 1}\n')


def test_a_failed_check_archives_the_boot_evidence(fake):
    root, run = fake
    full_run(run)
    code, out = checks(fake, STUB_BOOT_LOG="1")
    assert code == 1 and out[-1] == "BOOT CHECKS FAILED", out
    [archive] = archives(root)
    assert re.fullmatch(r"\d{8}T\d{6}Z", archive.name), archive.name
    assert f"failed-boot archive: {archive}" in out
    assert sorted(str(p.relative_to(archive)) for p in archive.rglob("*") if p.is_file()) == sorted(ARCHIVED + ("SOURCE",))
    for rel in ARCHIVED:
        assert (archive / rel).read_bytes() == (run / rel).read_bytes(), rel


def test_the_archive_names_the_run_dir_it_came_from(fake):
    """Task 10b quality review M1: the archive always goes under ROOT/.run/failed-boots, whatever RUN_DIR `--check` was given,
    so each archive's SOURCE file holds that directory's absolute path."""
    root, run = fake
    full_run(run)
    checks(fake, STUB_CONFIGS="1")
    [archive] = archives(root)
    assert archive.parent == root / ".run" / "failed-boots" and not run.is_relative_to(root)
    assert (archive / "SOURCE").read_text() == f"{run}\n"


def test_each_failure_gets_its_own_archive(fake):
    """Two failures, even in the same second, never share (or overwrite) an archive."""
    root, run = fake
    full_run(run)
    checks(fake, STUB_CONFIGS="1")
    checks(fake, STUB_CONFIGS="1")
    got = archives(root)
    assert len(got) == 2 and all(re.fullmatch(r"\d{8}T\d{6}Z(-\d+)?", a.name) for a in got), got


def test_an_absent_file_is_named_and_the_rest_archived(fake):
    root, run = fake
    code, out = checks(fake, STUB_BOOT_LOG="1")
    [archive] = archives(root)
    assert code == 1 and out[-1] == "BOOT CHECKS FAILED", out
    assert "  (not present, not archived: logs/debug.log kubejs/exported/recipes.json)" in out
    assert sorted(str(p.relative_to(archive)) for p in archive.rglob("*") if p.is_file()) == sorted(
        ["logs/latest.log", "console.log", "logs/kubejs/startup.log", "logs/kubejs/server.log", "SOURCE"])


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores the read-only mode, so mkdir would succeed")
def test_an_archive_that_cannot_be_made_is_reported_and_the_boot_still_fails(fake):
    """Task 10b fix round 1: with .run/ read-only, mkdir fails. The script names the path it could not make, never prints it as
    an archive, and still ends with BOOT CHECKS FAILED and 1 (under set -e a bare failing mkdir would end it first, rc 1 but
    no label)."""
    root, run = fake
    full_run(run)
    (root / ".run").mkdir()
    (root / ".run").chmod(0o555)
    try:
        code, out = checks(fake, STUB_BOOT_LOG="1")
    finally:
        (root / ".run").chmod(0o755)
    assert (code, out[-1]) == (1, "BOOT CHECKS FAILED"), out
    [line] = [x for x in out if x.startswith("failed-boot archive:")]
    assert re.fullmatch(rf"failed-boot archive: NOT CREATED \({re.escape(str(root))}/\.run/failed-boots/\d{{8}}T\d{{6}}Z\)",
                        line), line
    assert archives(root) == []
    assert "BOOT LOG ERRORS" in out


def test_passing_checks_archive_nothing(fake):
    root, run = fake
    full_run(run)
    code, out = checks(fake)
    assert (code, out[-1], archives(root)) == (0, "BOOT OK", []), out
    assert not [line for line in out if "failed-boot archive" in line]


def test_the_archive_stays_out_of_git_and_the_pack():
    """.run/ (where failed-boots/ lives) is ignored by git and by packwiz."""
    for name in (".gitignore", ".packwizignore"):
        assert ".run/" in (ROOT / name).read_text().splitlines(), name


def test_a_missing_log_fails_without_stopping_the_other_checks(fake):
    root, run = fake
    (run / "logs" / "kubejs" / "startup.log").unlink()
    code, out = checks(fake)
    assert code == 1 and f"MISSING LOG: {run}/logs/kubejs/startup.log" in out
    assert any(line.startswith("ran check_boot_log.py") for line in out)


# ---- round 3, H2/H3: the whole script, run on stubs, leaves no process behind ----
#
# Each scenario copies tools/server_boot.sh under a tmp ROOT and runs it with stub packwiz, curl and sleep first on PATH (the
# sleep stub naps 0.01 s whatever it is asked, so the 60 s stop wait takes about a second), a canary directory next (a
# packwiz, java or curl found there means a lookup skipped the stubs: it records the hit and fails), then /usr/bin:/bin, which
# hold neither packwiz nor curl's stand-ins for the real tools. JAVA_HOME is a stub jdk whose bin/java is a single python
# process; the run directory holds a run.sh shaped like NeoForge's (a plain `java ...` call, no exec), so run.sh is the
# script's $SERVER_PID and the stub java its child, as on a real boot. Every stub records its PID, and each scenario ends
# by checking that none of them is still running.

STUB_SH = {
    "packwiz": 'echo $$ > "$BOOT_STUB_STATE/packwiz.pid"\necho "packwiz-stub $*" >> "$BOOT_STUB_STATE/events"\n'
               "exec /bin/sleep 300\n",
    "curl": 'echo "curl-stub $*" >> "$BOOT_STUB_STATE/events"\n'
            '[ -n "${STUB_CURL_FAIL:-}" ] && { echo "curl stub: simulated failure" >&2; exit 22; }\n'
            'while [ $# -gt 0 ]; do [ "$1" = -o ] && { : > "$2"; shift; }; shift; done\n',
    # STUB_SLEEP_FAIL=N: `sleep N` fails, once the stub java has recorded its PID (so a failure "after the server starts" is)
    "sleep": 'if [ -n "${STUB_SLEEP_FAIL:-}" ] && [ "$1" = "$STUB_SLEEP_FAIL" ]; then\n'
             '  for i in $(seq 1 500); do [ -f "$BOOT_STUB_STATE/java.pid" ] && break; /bin/sleep 0.01; done\n'
             '  echo "sleep stub: fail on $1" >&2; exit 1\nfi\n'
             "exec /bin/sleep 0.01\n",
}
CANARY = '{ echo "CANARY $(basename "$0") $*" >> "$BOOT_STUB_STATE/canary"; exit 99; }\n'
STUB_JAVA = r"""import os, signal, sys, time
state = os.environ["BOOT_STUB_STATE"]
with open(os.path.join(state, "events"), "a") as f:
    f.write("java-stub " + " ".join(sys.argv[1:]) + "\n")
if sys.argv[1:2] == ["-jar"]:
    sys.exit(0)
if os.environ.get("STUB_JAVA_IGNORES_TERM"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
open(os.path.join(state, "runsh.pid"), "w").write(str(os.getppid()))
open(os.path.join(state, "java.pid"), "w").write(str(os.getpid()))
T = "[01Oct2026 23:15:24.886]"
if not os.environ.get("STUB_NO_WORLD"):
    os.makedirs("world", exist_ok=True)
os.makedirs("logs/kubejs", exist_ok=True)
open("logs/latest.log", "w").write(T + " [main/INFO] [x/]: starting\n")
for name in ("startup", "server"):
    open("logs/kubejs/%s.log" % name, "w").write("[23:15:00] [INFO] ok\n")
open("logs/debug.log", "w").write(T + " [main/DEBUG] [x/]: stub debug\n")
os.makedirs("kubejs/exported", exist_ok=True)
open("kubejs/exported/recipes.json", "w").write('{"stub": %d}\n' % os.getpid())
time.sleep(float(os.environ.get("STUB_DONE_AFTER", "0")))
print('[23:15:24] [Server thread/INFO] [minecraft/DedicatedServer]: Done (1.0s)! For help, type "help"', flush=True)
print("[23:15:25] [Server thread/INFO] [FTB Quests/]: Loaded 4 chapter groups", flush=True)
time.sleep(300)
"""
RUN_SH = '#!/usr/bin/env sh\njava @user_jvm_args.txt @libraries/net/neoforged/neoforge/21.1.250/unix_args.txt "$@"\n'
STUB_NAMES = ("packwiz", "runsh", "java")
# The stub jdk's jcmd (Task 11c): it records its PID and its arguments, and whether the PID it was given still ran when it
# was called; then it prints a stand-in dump, or with STUB_JCMD_HANGS never returns (exec, so its PID is the sleep's; with
# STUB_JCMD_HANGS=stubborn it instead catches SIGTERM, writes a late line at its own file offset, and keeps running), or
# with STUB_JCMD_JAVA_EXITS has java end while it runs (a stop that took just over 60 s) and fails as the real jcmd does then.
STUB_JCMD = r'''echo $$ > "$BOOT_STUB_STATE/jcmd.pid"
if kill -0 "$1" 2>/dev/null; then state=alive; else state=gone; fi
echo "jcmd-stub $* (java $state)" >> "$BOOT_STUB_STATE/events"
if [ "${STUB_JCMD_HANGS:-}" = stubborn ]; then
  printf 'partial dump\n'
  trap 'printf "LATE JCMD OUTPUT OVER THE NOTE\n"' TERM
  while :; do /bin/sleep 0.05; done
fi
[ -n "${STUB_JCMD_HANGS:-}" ] && exec /bin/sleep 300
if [ -n "${STUB_JCMD_JAVA_EXITS:-}" ]; then
  kill -9 "$1"; for i in $(seq 1 300); do kill -0 "$1" 2>/dev/null || break; /bin/sleep 0.01; done
  printf '%s:\ncom.sun.tools.attach.AttachNotSupportedException: pid: %s, %s\n' "$1" "$1" \
    'state is not ready to participate in attach handshake!'
  exit 1
fi
printf '%s:\nFull thread dump stub (jcmd %s)\n"Server thread" #1 stuck\n' "$1" "$*"
'''


def write_exec(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


@pytest.fixture(scope="module")
def stub_kit(tmp_path_factory):
    """The executable stubs, written once: macOS scans a new executable on its first exec (about 0.3 s each)."""
    kit = tmp_path_factory.mktemp("stub_kit")
    for name, body in STUB_SH.items():
        write_exec(kit / "bin" / name, "#!/bin/bash\n" + body)
    (kit / "bin" / "python3").symlink_to(sys.executable)
    for name in ("packwiz", "java", "curl"):
        write_exec(kit / "canary" / name, "#!/bin/bash\n" + CANARY)
    write_exec(kit / "jdk" / "bin" / "java", f"#!{sys.executable}\n" + STUB_JAVA)
    write_exec(kit / "jdk" / "bin" / "jcmd", "#!/bin/bash\n" + STUB_JCMD)
    write_exec(kit / "run.sh", RUN_SH)
    return kit


@pytest.fixture
def stub_boot(tmp_path, stub_kit):
    root, state = tmp_path / "root", tmp_path / "state"
    bin_dir, canary, jdk = stub_kit / "bin", stub_kit / "canary", stub_kit / "jdk"
    state.mkdir()
    (root / "tools").mkdir(parents=True)
    shutil.copy(SCRIPT, root / "tools" / "server_boot.sh")
    for name, env in (("check_configs.py", "STUB_CONFIGS"), ("check_boot_log.py", "STUB_BOOT_LOG")):
        (root / "tools" / name).write_text(STUB.format(name=name, env=env))
    shutil.copy(FORCED_READER, root / "tools")
    (root / ".run" / "server").mkdir(parents=True)
    (root / ".run" / "server" / "run.sh").symlink_to(stub_kit / "run.sh")
    path = f"{bin_dir}:{canary}:/usr/bin:/bin"
    # the PATH half of the canary: no lookup here reaches a real packwiz or java
    assert shutil.which("packwiz", path=path) == str(bin_dir / "packwiz")
    assert shutil.which("curl", path=path) == str(bin_dir / "curl")
    assert shutil.which("java", path=f"{jdk / 'bin'}:{path}") == str(jdk / "bin" / "java")
    base = {"PATH": path, "HOME": str(tmp_path), "JAVA_HOME": str(jdk), "BOOT_STUB_STATE": str(state),
            "PYTHONDONTWRITEBYTECODE": "1"}
    started = []

    def boot(env=None, signal_on=None, sig=None, trace=False):
        cmd = ["/bin/bash"] + (["-x"] if trace else []) + [str(root / "tools" / "server_boot.sh")]
        p = subprocess.Popen(cmd, env={**base, **(env or {})}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             start_new_session=True)
        started.append(p)
        if signal_on:
            deadline = time.time() + 15   # at load 40-50 a stub took more than 3 s to start
            while not (state / f"{signal_on}.pid").exists() and time.time() < deadline:
                time.sleep(0.01)
            assert (state / f"{signal_on}.pid").exists(), f"the {signal_on} stub never started"
            os.killpg(p.pid, sig)
        out, _ = p.communicate(timeout=30)
        pids = {n: int((state / f"{n}.pid").read_text()) for n in STUB_NAMES if (state / f"{n}.pid").exists()}
        deadline = time.time() + 15
        while [n for n, pid in pids.items() if running(pid)] and time.time() < deadline:
            time.sleep(0.02)
        assert not (state / "canary").exists(), (state / "canary").read_text()
        return p.returncode, out, pids, {n: pid for n, pid in pids.items() if running(pid)}

    boot.root, boot.state = root, state
    yield boot
    for p in started:   # never leave a stub behind, whatever the test did
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGKILL)
    for n in STUB_NAMES + ("jcmd",):
        f = state / f"{n}.pid"
        if f.exists() and running(int(f.read_text())):
            os.kill(int(f.read_text()), signal.SIGKILL)


def running(pid):
    """True while `pid` runs; an exited process its parent has not reaped yet (a zombie) counts as stopped."""
    stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(stat) and "Z" not in stat


def labels(out):
    return [line for line in out.splitlines() if re.fullmatch(r"[A-Z][A-Z ]+[A-Z]", line)]


def test_a_clean_stub_boot_passes_and_clears_the_trap_before_the_checks(stub_boot):
    code, out, pids, alive = stub_boot(trace=True)
    assert (set(pids), alive) == (set(STUB_NAMES), {})
    assert (code, labels(out)) == (0, ["BOOT OK"]), out
    assert archives(stub_boot.root) == [], "a clean boot archives nothing (Task 10b)"
    # after the shutdown nothing signals a PID again: no kill or pgrep runs once the checks start (the EXIT trap is gone)
    trace = out.splitlines()
    first = next(i for i, line in enumerate(trace) if re.match(r"^\++ post_boot_checks ", line))
    assert [line for line in trace[first:] if re.match(r"^\++ (kill|pgrep)\b", line)] == []


def test_a_probe_session_not_cleaned_up_refuses_the_boot(stub_boot):
    """After a crash, level-name can still be the session's: the boot would then check, and pass, the wrong world (Task 12)."""
    (stub_boot.root / ".run/server/server.properties.session-backup").write_text("level-name=world\n")
    code, out, pids, alive = stub_boot()
    assert (code, pids, alive) == (2, {}, {}), out
    assert "tools/server_session.sh stop" in out and "BOOT OK" not in out, out
    assert "no one is playing" in out, out      # the session may be live: stop would end someone's game


def test_check_mode_ignores_a_session_backup(fake):
    """--check starts nothing, and its folder may be an archive: the guard is for a boot only."""
    root, run = fake
    (run / "server.properties.session-backup").write_text("level-name=world\n")
    shutil.copy(SCRIPT, root / "tools" / "server_boot.sh")
    res = subprocess.run(["bash", str(root / "tools" / "server_boot.sh"), "--check", str(run)], capture_output=True, text=True,
                         timeout=60)
    assert res.returncode == 0 and "BOOT OK" in res.stdout, res.stdout


def test_a_failure_before_the_server_starts_leaves_nothing_running(stub_boot):
    code, out, pids, alive = stub_boot({"STUB_CURL_FAIL": "1"})
    assert (set(pids), alive) == ({"packwiz"}, {})
    assert code != 0 and "curl stub: simulated failure" in out and "BOOT OK" not in out, out


def test_a_failure_after_the_server_starts_leaves_nothing_running(stub_boot):
    """`sleep 5` in the wait for Done fails, so set -e ends the script while run.sh and java run."""
    code, out, pids, alive = stub_boot({"STUB_DONE_AFTER": "30", "STUB_SLEEP_FAIL": "5"})
    assert (set(pids), alive) == (set(STUB_NAMES), {})
    assert code != 0 and "sleep stub: fail on 5" in out and "BOOT OK" not in out, out


def test_sigint_to_the_process_group_leaves_nothing_running(stub_boot):
    """A non-interactive bash starts background jobs with SIGINT ignored, so ^C reaches only the script: its trap must stop
    the rest."""
    code, out, pids, alive = stub_boot({"STUB_DONE_AFTER": "30"}, signal_on="java", sig=signal.SIGINT)
    assert (set(pids), alive) == (set(STUB_NAMES), {})
    assert code != 0 and "BOOT OK" not in out, out


def test_a_server_that_ignores_sigterm_is_killed_and_fails_the_boot(stub_boot):
    code, out, pids, alive = stub_boot({"STUB_JAVA_IGNORES_TERM": "1"})
    assert (set(pids), alive) == (set(STUB_NAMES), {})
    assert (code, labels(out)) == (1, ["SERVER DID NOT STOP", "BOOT CHECKS FAILED"]), out


# ---- Task 11c: a server that does not stop is thread-dumped before the SIGKILL ----------------------------------------

DUMP_BANNER = "==== SERVER DID NOT STOP: jcmd Thread.print -l, taken before the SIGKILL ===="


def jcmd_calls(stub_boot):
    events = stub_boot.state / "events"
    return [e for e in events.read_text().splitlines() if e.startswith("jcmd-stub")] if events.exists() else []


def test_a_server_that_does_not_stop_is_thread_dumped_before_it_is_killed(stub_boot):
    """jcmd runs once, on java's PID, while java still runs (so before the SIGKILL); the dump is appended to console.log
    after the server's own output, and the failed-boot archive keeps that console.log. The labels are unchanged."""
    code, out, pids, alive = stub_boot({"STUB_JAVA_IGNORES_TERM": "1"})
    assert (set(pids), alive) == (set(STUB_NAMES), {})
    assert (code, labels(out)) == (1, ["SERVER DID NOT STOP", "BOOT CHECKS FAILED"]), out
    assert jcmd_calls(stub_boot) == [f"jcmd-stub {pids['java']} Thread.print -l (java alive)"]
    run = stub_boot.root / ".run" / "server"
    console = (run / "console.log").read_text()
    assert console.index("Done (1.0s)") < console.index(DUMP_BANNER) < console.index(
        f"Full thread dump stub (jcmd {pids['java']} Thread.print -l)"), console
    assert "thread dump appended to console.log" in out.splitlines(), out
    [archive] = archives(stub_boot.root)
    assert (archive / "console.log").read_text() == console
    assert not (run / "stop-threads.txt").exists()
    assert JAVA_EXITED_NOTE not in console, "java was still running after the dump: it was SIGKILLed"


JAVA_EXITED_NOTE = "(java exited on its own while jcmd ran: the stop took just over the 60 s wait)"


def test_a_server_that_exits_during_its_thread_dump_is_reported_as_such(stub_boot):
    """Task 11c, boot plain-04: a stop that takes just over 60 s ends while jcmd is still attaching, and jcmd then fails with
    AttachNotSupportedException ("state is not ready"), which reads like a broken diagnostic. The dump says java exited on its
    own; the labels and the status are unchanged (the 60 s rule stands)."""
    code, out, pids, alive = stub_boot({"STUB_JAVA_IGNORES_TERM": "1", "STUB_JCMD_JAVA_EXITS": "1"})
    assert (set(pids), alive) == (set(STUB_NAMES), {})
    assert (code, labels(out)) == (1, ["SERVER DID NOT STOP", "BOOT CHECKS FAILED"]), out
    assert jcmd_calls(stub_boot) == [f"jcmd-stub {pids['java']} Thread.print -l (java alive)"]
    console = (stub_boot.root / ".run" / "server" / "console.log").read_text()
    assert console.index(DUMP_BANNER) < console.index("state is not ready") < console.index(JAVA_EXITED_NOTE), console


def test_a_server_that_stops_is_not_thread_dumped(stub_boot):
    code, out, pids, alive = stub_boot()
    assert (code, labels(out)) == (0, ["BOOT OK"]), out
    assert jcmd_calls(stub_boot) == []
    assert DUMP_BANNER not in (stub_boot.root / ".run" / "server" / "console.log").read_text()


def test_a_thread_dump_that_hangs_is_abandoned_and_the_server_still_killed(stub_boot):
    """jcmd gets 30 s (30 one-second sleeps); one that has not returned by then is killed, the dump says so, and java is
    SIGKILLed as before: nothing is left running."""
    code, out, pids, alive = stub_boot({"STUB_JAVA_IGNORES_TERM": "1", "STUB_JCMD_HANGS": "1"})
    assert (set(pids), alive) == (set(STUB_NAMES), {})
    assert (code, labels(out)) == (1, ["SERVER DID NOT STOP", "BOOT CHECKS FAILED"]), out
    jcmd_pid = int((stub_boot.state / "jcmd.pid").read_text())
    deadline = time.time() + 15
    while running(jcmd_pid) and time.time() < deadline:
        time.sleep(0.02)
    assert not running(jcmd_pid), "the hung jcmd was left running"
    console = (stub_boot.root / ".run" / "server" / "console.log").read_text()
    assert console.index(DUMP_BANNER) < console.index("(jcmd did not finish within 30 s; killed)"), console


def test_a_stale_dump_file_never_reaches_a_later_boot(stub_boot):
    """A stop-threads.txt left by a boot that died mid-dump is deleted with the other per-boot files, so a later clean boot's
    console.log never carries it."""
    run = stub_boot.root / ".run" / "server"
    (run / "stop-threads.txt").write_text("STALE DUMP\n")
    code, out, pids, alive = stub_boot()
    assert (code, labels(out)) == (0, ["BOOT OK"]), out
    assert "STALE DUMP" not in (run / "console.log").read_text()
    assert not (run / "stop-threads.txt").exists()


def test_a_stub_boot_whose_checks_fail_keeps_its_evidence(stub_boot):
    """Task 10b: the forced boot-log failure leaves .run/failed-boots/<UTC timestamp>/ holding this boot's six files."""
    code, out, pids, alive = stub_boot({"STUB_BOOT_LOG": "1"})
    assert (set(pids), alive) == (set(STUB_NAMES), {})
    assert (code, labels(out)) == (1, ["BOOT LOG ERRORS", "BOOT CHECKS FAILED"]), out
    run = stub_boot.root / ".run" / "server"
    [archive] = archives(stub_boot.root)
    assert f"failed-boot archive: {archive}" in out.splitlines()
    for rel in ARCHIVED:
        assert (archive / rel).read_bytes() == (run / rel).read_bytes(), rel
    assert "Done (1.0s)" in (archive / "console.log").read_text()
    assert (archive / "SOURCE").read_text() == f"{run}\n"
    assert (archive / "kubejs" / "exported" / "recipes.json").read_text() == '{"stub": %s}\n' % pids["java"]


# ---- Task 11c fix (D136): forced chunks fail the boot -------------------------------------------------------------------

def leak(run, n=256, rel="world/dimensions/ad_astra/glacio/data/chunks.dat"):
    path = run / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(chunks_dat(n))
    return path


def test_a_clean_world_prints_its_zero_forced_chunks(fake):
    root, run = fake
    leak(run, 0, "world/data/chunks.dat")
    code, out = checks(fake)
    assert (code, out[-1]) == (0, "BOOT OK"), out
    assert f"forced chunks: 0 (mod tickets: 0; 1 chunks.dat files read in {run.resolve() / 'world'})" in out


def test_forced_chunks_fail_the_checks_and_are_archived(fake):
    root, run = fake
    full_run(run)
    leak(run, 256)
    leak(run, 1, "world/data/chunks.dat")
    code, out = checks(fake)
    assert code == 1 and labels("\n".join(out)) == ["FORCED CHUNKS", "BOOT CHECKS FAILED"], out
    w = run.resolve() / "world"
    assert f"forced chunks: 257 (mod tickets: 0; 2 chunks.dat files read in {w})" in out
    assert f"  ad_astra:glacio: 256 forced chunk(s) ({w}/dimensions/ad_astra/glacio/data/chunks.dat)" in out
    assert any("D136" in line for line in out)
    [archive] = archives(root)
    assert f"failed-boot archive: {archive}" in out
    assert sorted(str(p.relative_to(archive)) for p in archive.rglob("*") if p.is_file()) == sorted(ARCHIVED + ("SOURCE",))


def test_a_chunks_file_the_guard_cannot_read_fails_the_checks(fake):
    root, run = fake
    leak(run, 0, "world/data/chunks.dat").write_bytes(b"not gzip")
    code, out = checks(fake)
    assert code == 1 and labels("\n".join(out)) == ["FORCED CHUNKS CHECK ERROR", "BOOT CHECKS FAILED"], out


def test_check_mode_runs_the_forced_chunk_guard(fake, tmp_path):
    """`server_boot.sh --check RUN_DIR` runs the same guard, on RUN_DIR's world, without booting."""
    root, run = fake
    shutil.copy(SCRIPT, root / "tools" / "server_boot.sh")
    leak(run, 3)
    res = subprocess.run(["bash", str(root / "tools" / "server_boot.sh"), "--check", str(run)], capture_output=True,
                         text=True, timeout=60)
    assert res.returncode == 1 and labels(res.stdout) == ["FORCED CHUNKS", "BOOT CHECKS FAILED"], res.stdout
    assert any(line.startswith("forced chunks: 3 (mod tickets: 0;") for line in res.stdout.splitlines()), res.stdout


def test_a_boot_whose_run_dir_has_no_world_fails_the_guard(fake):
    """A server that reached Done has always created its world: a boot whose run directory has none was not read at all."""
    root, run = fake
    (run / "world").rmdir()
    code, out = checks(fake)
    assert code == 1 and labels("\n".join(out)) == ["FORCED CHUNKS CHECK ERROR", "BOOT CHECKS FAILED"], out


def test_check_mode_where_a_server_ran_but_the_world_is_gone_fails(fake):
    """Round 3: --check passes a missing world only where no server ran (no server.properties: a failed-boot archive)."""
    root, run = fake
    (run / "world").rmdir()
    (run / "server.properties").write_text("level-name=world\n")
    shutil.copy(SCRIPT, root / "tools" / "server_boot.sh")
    res = subprocess.run(["bash", str(root / "tools" / "server_boot.sh"), "--check", str(run)], capture_output=True,
                         text=True, timeout=60)
    assert (res.returncode, labels(res.stdout)) == (1, ["FORCED CHUNKS CHECK ERROR", "BOOT CHECKS FAILED"]), res.stdout


def test_a_check_only_exported_by_the_operator_does_not_reach_a_boot(stub_boot):
    """Round 3: CHECK_ONLY in the caller's environment must not turn a boot's guard into --check's. The stub server makes no
    world (STUB_NO_WORLD) and writes no server.properties, so only the flag decides: a boot fails on the missing world."""
    code, out, pids, alive = stub_boot({"CHECK_ONLY": "1", "STUB_NO_WORLD": "1"})
    assert alive == {}, alive
    assert (code, labels(out)) == (1, ["FORCED CHUNKS CHECK ERROR", "BOOT CHECKS FAILED"]), out


def test_check_mode_on_a_folder_without_a_world_says_so_and_passes(fake):
    """--check on a failed-boot archive (logs, no world): the guard has nothing to read there, says so, and does not fail
    the logs' own checks for it."""
    root, run = fake
    (run / "world").rmdir()
    shutil.copy(SCRIPT, root / "tools" / "server_boot.sh")
    res = subprocess.run(["bash", str(root / "tools" / "server_boot.sh"), "--check", str(run)], capture_output=True,
                         text=True, timeout=60)
    assert (res.returncode, labels(res.stdout)) == (0, ["BOOT OK"]), res.stdout
    assert f"forced chunks: 0 (no world at {run.resolve() / 'world'})" in res.stdout.splitlines()


def test_a_stub_boot_with_forced_chunks_fails_after_a_clean_stop(stub_boot):
    """The whole script: the server stops in time, and the world's forced chunks alone fail the boot."""
    leak(stub_boot.root / ".run" / "server", 1536, "world/dimensions/undergarden/undergarden/data/chunks.dat")
    code, out, pids, alive = stub_boot()
    assert (set(pids), alive) == (set(STUB_NAMES), {})
    assert (code, labels(out)) == (1, ["FORCED CHUNKS", "BOOT CHECKS FAILED"]), out
    assert any(line.startswith("forced chunks: 1536 (mod tickets: 0;") for line in out.splitlines()), out
    assert "SERVER DID NOT STOP" not in out.splitlines()
    assert len(archives(stub_boot.root)) == 1


def test_a_clean_stub_boot_reports_zero_forced_chunks(stub_boot):
    code, out, pids, alive = stub_boot()
    assert (code, labels(out)) == (0, ["BOOT OK"]), out
    world = (stub_boot.root / ".run" / "server" / "world").resolve()
    assert f"forced chunks: 0 (mod tickets: 0; 0 chunks.dat files read in {world})" in out.splitlines(), out


# ---- Task 11c fix round 2: the hung-server path leaves nothing behind (M1, M2, M3) ----------------------------------------

def test_an_interrupt_during_the_thread_dump_leaves_no_java_and_no_jcmd(stub_boot):
    """M1: java ignores SIGTERM (it is hung) and jcmd hangs; ^C to the process group during the dump window. The trap re-armed
    when java was declared hung SIGKILLs both."""
    code, out, pids, alive = stub_boot({"STUB_JAVA_IGNORES_TERM": "1", "STUB_JCMD_HANGS": "1"}, signal_on="jcmd",
                                       sig=signal.SIGINT)
    jcmd = int((stub_boot.state / "jcmd.pid").read_text())
    deadline = time.time() + 15
    while running(jcmd) and time.time() < deadline:
        time.sleep(0.02)
    assert (alive, running(jcmd)) == ({}, False), out
    # -SIGINT is the usual end. Under load (4 of 25 at load 40-50) the ^C lands around a short foreground child, so bash
    # survives it and exits 1 by its own check; either way nothing leaks and no boot is claimed.
    assert code in (-signal.SIGINT, 1) and "BOOT OK" not in out, (code, out)


def test_a_jcmd_that_ignores_sigterm_is_sigkilled_before_its_note(stub_boot):
    """M2: a hung jcmd that catches SIGTERM would keep running (and `wait` on it would hang the boot), and could write at its
    own offset in stop-threads.txt over the note appended after it. It is SIGKILLed and reaped first; the note is intact."""
    code, out, pids, alive = stub_boot({"STUB_JAVA_IGNORES_TERM": "1", "STUB_JCMD_HANGS": "stubborn"})
    assert (set(pids), alive) == (set(STUB_NAMES), {})
    assert (code, labels(out)) == (1, ["SERVER DID NOT STOP", "BOOT CHECKS FAILED"]), out
    assert not running(int((stub_boot.state / "jcmd.pid").read_text()))
    console = (stub_boot.root / ".run" / "server" / "console.log").read_text()
    assert console.index("partial dump") < console.index("(jcmd did not finish within 30 s; killed)"), console
    assert "LATE JCMD OUTPUT" not in console


def test_a_java_that_exited_on_its_own_is_not_sigkilled(stub_boot):
    """M3: when java has exited while jcmd ran, its PID is not signalled again (the system may have reused it): no
    `kill -9 <java pid>` runs, and the dump says java exited on its own."""
    code, out, pids, alive = stub_boot({"STUB_JAVA_IGNORES_TERM": "1", "STUB_JCMD_JAVA_EXITS": "1"}, trace=True)
    assert (code, labels(out)) == (1, ["SERVER DID NOT STOP", "BOOT CHECKS FAILED"]), out
    java = pids["java"]
    assert not [line for line in out.splitlines() if re.match(rf"^\++ kill -9 {java}\b", line)], out
    assert JAVA_EXITED_NOTE in (stub_boot.root / ".run" / "server" / "console.log").read_text()


def test_a_hung_java_is_still_sigkilled(stub_boot):
    """M3's other branch: java still running after the dump is SIGKILLed, once."""
    code, out, pids, alive = stub_boot({"STUB_JAVA_IGNORES_TERM": "1"}, trace=True)
    assert alive == {} and code == 1, out
    assert len([line for line in out.splitlines() if re.match(rf"^\++ kill -9 {pids['java']}\b", line)]) == 1, out
