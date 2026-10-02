"""tools/server_boot.sh's post-boot checks (v0.3 Task 8c round 2, minors 5 and 11), run in bash against a synthetic server
directory with stand-in checker scripts; the real boot is the script's own job.

  - post_boot_checks runs every check, prints each failing check's label, and exits with the combined status: one failing
    check no longer hides the ones after it;
  - tools/check_boot_log.py's exit codes get distinct labels: 1 BOOT LOG ERRORS (an unknown record or an incomplete log),
    2 a usage error, 3 BAD ALLOWLIST; none of them reads as an unknown log error it is not;
  - the background processes the boot starts (packwiz serve, run.sh and its java child) are killed by an EXIT trap, so a boot
    that dies under `set -e` leaves nothing running;
  - a boot whose checks fail keeps its evidence (v0.3 Task 10b, D134): post_boot_checks copies logs/latest.log,
    logs/debug.log, console.log, logs/kubejs/startup.log, logs/kubejs/server.log and kubejs/exported/recipes.json into
    .run/failed-boots/<UTC timestamp>/ and prints the path, since the next boot deletes or rotates every one of them. When
    that directory cannot be made, it says so ("NOT CREATED") and the boot still ends with BOOT CHECKS FAILED. The archive
    is always under the pack's own .run/, so a SOURCE file in it names the server directory the evidence came from.
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

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "server_boot.sh"
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


@pytest.mark.parametrize("rc, label", [("1", "BOOT LOG ERRORS"), ("2", "BOOT LOG CHECK USAGE ERROR"), ("3", "BAD ALLOWLIST")])
def test_each_boot_log_exit_code_has_its_own_label(fake, rc, label):
    code, out = checks(fake, STUB_BOOT_LOG=rc)
    assert code == 1 and "BOOT OK" not in out, out
    assert [line for line in out if line.isupper() or line.startswith(("BOOT", "BAD"))] == [label, "BOOT CHECKS FAILED"]
    assert "UNKNOWN LOG ERRORS" not in out


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
            deadline = time.time() + 5
            while not (state / f"{signal_on}.pid").exists() and time.time() < deadline:
                time.sleep(0.01)
            assert (state / f"{signal_on}.pid").exists(), f"the {signal_on} stub never started"
            os.killpg(p.pid, sig)
        out, _ = p.communicate(timeout=30)
        pids = {n: int((state / f"{n}.pid").read_text()) for n in STUB_NAMES if (state / f"{n}.pid").exists()}
        deadline = time.time() + 3
        while [n for n, pid in pids.items() if running(pid)] and time.time() < deadline:
            time.sleep(0.02)
        assert not (state / "canary").exists(), (state / "canary").read_text()
        return p.returncode, out, pids, {n: pid for n, pid in pids.items() if running(pid)}

    boot.root = root
    yield boot
    for p in started:   # never leave a stub behind, whatever the test did
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGKILL)
    for n in STUB_NAMES:
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
