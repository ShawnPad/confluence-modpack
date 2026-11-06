"""Dry runs of tools/server_session.sh's start path: the parts of plan v0.3 Task 12's script that test_server_session.py, pinned at
the plan's 9 tests, does not reach. A copy of the script and its checkers runs from a temporary pack root, against a temporary
server folder, so nothing here touches .run/ and failed-boot archives stay in the temporary folder. run.sh's java child is
session_fake_server.sh, and its latest.log is golden/session-latest-log.txt: the verbatim lines the boot check reads (see
test_check_boot_log.py for each one's source). The real boot was rehearsed once (research/phase7-v0.3-session-rehearsal.out).

Stub `java`, `curl` and `packwiz` come first on PATH. So does `pgrep`, whose -f form finds only what PGREP_FOUND names: start's
check for any server on this machine would otherwise fail these tests while a real one, or another test's stub, runs. The
script's waits are shortened through its environment overrides. Every script call is in
its own process group with its output in a file, because a child left holding a pipe would hang the run. BOUND only stops a
hang: exceeding it fails the test and kills the group."""
import os
import shutil
import signal
import stat
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

TOOLS = Path(__file__).resolve().parents[1]
TESTS = TOOLS / "tests"
BOUND = 300
PROPS = "#Minecraft server properties\nlevel-name=world\nonline-mode=true\nserver-port=25565\nwhite-list=false\n"


def write_x(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    p.chmod(p.stat().st_mode | stat.S_IXUSR)


def kill_group(p):
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except OSError:
        pass


@pytest.fixture
def tree(tmp_path):
    pack = tmp_path / "pack"
    tools = pack / "tools"
    tools.mkdir(parents=True)
    for f in ("server_session.sh", "check_boot_log.py", "boot_allowlist.txt", "gamerules.toml", "count_forced_chunks.py"):
        shutil.copy(TOOLS / f, tools / f)
    run = pack / ".run/server"
    (run / "world").mkdir(parents=True)
    (run / "world/level.dat").write_text("")     # a real world: the level.dat guard must not hide the case guard
    (run / "server.properties").write_text(PROPS)
    shutil.copy(TESTS / "golden/session-latest-log.txt", run / "good.log")
    (run / "mode").write_text("ok\n")
    shutil.copy(TESTS / "session_fake_server.sh", run / "session_fake_server.sh")
    write_x(run / "run.sh", '#!/usr/bin/env bash\n"$PWD/session_fake_server.sh" "$@"\n')
    stubs = tmp_path / "jh/bin"
    write_x(stubs / "java", '#!/usr/bin/env bash\n[ -f "$SYNC_SLEEP" ] && { touch "$SYNC_SLEEP.started"; sleep 3; }\nexit "${SYNC_RC:-0}"\n')
    write_x(stubs / "curl", '#!/usr/bin/env bash\nwhile [ $# -gt 0 ]; do [ "$1" = -o ] && : > "$2"; shift; done\nexit 0\n')
    write_x(stubs / "packwiz", '#!/usr/bin/env bash\nwhile :; do sleep 1; done\n')
    real_pgrep = shutil.which("pgrep")
    write_x(stubs / "pgrep", f'#!/usr/bin/env bash\nif [ "$1" = -f ]; then [ -n "$PGREP_FOUND" ] && [[ "$2" == *"$PGREP_FOUND"* ]] && exit 0; exit 1; fi\n'
                            f'exec {real_pgrep} "$@"\n')
    env = dict(os.environ, JAVA_HOME=str(tmp_path / "jh"), PATH=f"{stubs}:{os.environ['PATH']}", PGREP_FOUND="",
               CONFLUENCE_SESSION_SETTLE="0", CONFLUENCE_SESSION_POLL="0.2", CONFLUENCE_SESSION_STOP_WAIT="2")
    env.pop("CONFLUENCE_RUN", None)
    procs = []
    script = tools / "server_session.sh"

    def spawn(args, extra):
        out = tmp_path / f"out{len(procs)}.txt"
        with open(out, "w") as f:
            p = subprocess.Popen(["bash", str(script), *args], stdout=f, stderr=subprocess.STDOUT, env=dict(env, **extra),
                                 start_new_session=True)
        p.out_path = out
        procs.append(p)
        return p

    def finish(p, bound=BOUND):
        try:
            return p.wait(bound)
        except subprocess.TimeoutExpired:
            kill_group(p)
            pytest.fail(f"server_session.sh {p.args[2:]} did not finish within {bound} s")

    def s(*args, bound=BOUND, **extra):
        p = spawn(args, extra)
        finish(p, bound)
        return SimpleNamespace(returncode=p.returncode, stdout=p.out_path.read_text())

    def pid(key):
        for line in (run / "session.pids").read_text().splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1]
        return None

    yield SimpleNamespace(pack=pack, run=run, s=s, start=lambda *a, **e: spawn(("start", *a), e), finish=finish, pid=pid,
                          out=lambda p: p.out_path.read_text())
    # Leave nothing behind, whatever the test did: everything is in a recorded process group or names this folder.
    for p in procs:
        kill_group(p)
    subprocess.run(["/usr/bin/pkill", "-9", "-f", str(tmp_path)], capture_output=True)


def gone(t):
    assert not (t.run / "session.pids").exists()
    assert not (t.run / "session.in").exists()
    assert not (t.run / "server.properties.session-backup").exists()
    assert (t.run / "server.properties").read_text() == PROPS


def archives(t):
    d = t.pack / ".run/failed-boots"
    return sorted(d.iterdir()) if d.exists() else []


def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def dead(*pids):
    """An orphan is reaped in its parent's own time, so give each signalled process a while to go."""
    for pid in pids:
        for _ in range(60):
            if not alive(pid):
                break
            time.sleep(1)
        assert not alive(pid), f"pid {pid} is still running"


def up(t, world="probe_v03"):
    r = t.s("wait")
    assert (r.returncode, r.stdout.strip()) == (0, f"session: up (world {world})")


def test_a_full_session(tree):
    t = tree
    p = t.start()
    up(t)
    hold, serve = t.pid("hold"), t.pid("serve")
    props = (t.run / "server.properties").read_text()
    assert "level-name=probe_v03\n" in props and "online-mode=true\n" in props
    assert t.s("status").returncode == 0
    r = t.s("cmd", "list", "20")
    assert (r.returncode, r.stdout) == (0, "reply to list\n")
    o = t.out(p)
    assert "confluence tf-gamerules guard OK" in o and "confluence gamerules:" in o
    assert "game rules: 55 expected, server 55, registry 55, guard OK" in o
    assert "SESSION UP world=probe_v03 online-mode=true port=25565" in o
    r = t.s("stop")
    assert r.returncode == 0, r.stdout
    assert r.stdout.strip().endswith("session: stopped") and "forced chunks: 0" in r.stdout
    assert t.finish(p) == 0
    gone(t)
    dead(hold, serve)
    assert (t.run / "probe_v03/marker").exists() and not (t.run / "world/marker").exists()
    assert "the server has exited" in t.out(p) and "kept in" in t.out(p)
    assert not archives(t)


def test_b_offline_is_for_the_session_only(tree):
    t = tree
    p = t.start("--offline", "--world", "other_probe")
    up(t, "other_probe")
    assert "online-mode=false\n" in (t.run / "server.properties").read_text()
    assert t.s("stop").returncode == 0
    assert t.finish(p) == 0
    gone(t)


@pytest.mark.parametrize("mode,label", [("wrongworld", "did not open world probe_v03"), ("nodone", "BOOT FAILED"),
                                        ("noguard", "BOOT LOG ERRORS")])
def test_c_a_failed_start_is_a_finding_and_is_archived(tree, mode, label):
    t = tree
    (t.run / "mode").write_text(mode + "\n")
    # noguard: a poll long enough that wait sees the live server before the boot checks, or the ready gate goes untested.
    p = t.start(CONFLUENCE_SESSION_POLL="3") if mode == "noguard" else t.start()
    if mode == "noguard":     # wait's 5 s grace period: one case is enough
        r = t.s("wait")
        assert (r.returncode, r.stdout.strip()) == (1, "session: down")
    assert t.finish(p) == 1
    o = t.out(p)
    assert label in o and "SESSION UP" not in o and "failed-boot archive: " in o
    gone(t)
    a = archives(t)
    assert len(a) == 1 and (a[0] / "console.session.log").exists() and (a[0] / "SOURCE").read_text().strip() == str(t.run)
    if mode == "noguard":
        assert (a[0] / "logs/latest.log").exists() and "NO GUARD LINE" in o


def test_d_kill9_of_start_then_cmd_and_stop(tree):
    t = tree
    p = t.start()
    up(t)
    hold, serve, server = t.pid("hold"), t.pid("serve"), t.pid("server")
    p.send_signal(signal.SIGKILL)
    p.wait()
    assert t.s("status").returncode == 0
    r = t.s("cmd", "list", "20")
    assert (r.returncode, r.stdout) == (0, "reply to list\n")   # the holder keeps the server's stdin open
    r = t.s("stop")
    assert r.returncode == 0 and r.stdout.strip().endswith("session: stopped"), r.stdout
    gone(t)
    dead(hold, serve, server)


def test_e_everything_killed_then_stop_repairs(tree):
    t = tree
    p = t.start()
    up(t)
    serve, server, hold = t.pid("serve"), t.pid("server"), t.pid("hold")
    subprocess.run(["/usr/bin/pkill", "-9", "-P", server], capture_output=True)
    os.kill(int(server), signal.SIGKILL)
    p.send_signal(signal.SIGKILL)
    p.wait()
    assert "level-name=probe_v03\n" in (t.run / "server.properties").read_text()
    r = t.s("stop")
    assert r.returncode == 0 and "session: not running" in r.stdout and "restored server.properties" in r.stdout, r.stdout
    gone(t)
    dead(hold, serve)


def test_f_second_start_refused(tree):
    t = tree
    p = t.start()
    up(t)
    r = t.s("start")
    assert r.returncode == 2 and "already running" in r.stdout
    assert t.s("status").returncode == 0     # the refused start did not clean up the live session
    assert t.s("stop").returncode == 0
    assert t.finish(p) == 0
    gone(t)


# A name the guard let through would start a whole session, in the foreground: the bound turns that into a failure.
@pytest.mark.parametrize("name", ["world", "WORLD", "World", "./world", "world/", "a/b", "../world", ""])
def test_g_names_that_reach_the_test_world_or_leave_the_folder_are_refused(tree, name):
    r = tree.s("start", "--world", name, bound=60)
    assert r.returncode == 2 and "refusing --world" in r.stdout, r.stdout
    gone(tree)


def test_h_stop_while_syncing(tree):
    t = tree
    flag = t.run / "syncflag"
    flag.write_text("")
    p = t.start(SYNC_SLEEP=str(flag))
    for _ in range(BOUND * 10):                  # the stub java's marker: the sync itself is running, not the settle before it
        if (t.run / "syncflag.started").exists():
            break
        time.sleep(0.1)
    r = t.s("stop")
    assert r.stdout.strip() == "session: stopped while starting", r.stdout
    t.finish(p)
    gone(t)
    assert not (t.run / "probe_v03").exists()    # it never got as far as the server


def test_i_sync_failure(tree):
    t = tree
    p = t.start(SYNC_RC="3")
    assert t.finish(p) != 0
    assert "pack sync failed" in t.out(p)
    gone(t)
    assert not archives(t)


def test_j_crash_during_a_session_is_archived(tree):
    t = tree
    (t.run / "mode").write_text("crash\n")
    p = t.start()
    assert t.finish(p) == 1
    assert "without a stop" in t.out(p)
    gone(t)
    assert len(archives(t)) == 1


def live_server_without_a_reader(t, log):
    """A pipe nobody reads and a live "server" that is not reading it."""
    os.mkfifo(t.run / "session.in")
    (t.run / "console.session.log").write_text(log)
    live = subprocess.Popen(["sleep", "600"])
    (t.run / "session.pids").write_text(f"world=probe_v03\nserver={live.pid}\n")
    return live


def test_k_cmd_does_not_block_on_a_pipe_without_a_reader(tree):
    # a plain `printf > FIFO` would wait in open(2) for ever here (D136, Task 11c review M4)
    live = live_server_without_a_reader(tree, "")
    try:
        r = tree.s("cmd", "list", "2", bound=60)
        assert r.returncode == 1 and "(no reply within 2 s" in r.stdout
    finally:
        live.kill()
        live.wait()


def test_l_cmd_refuses_a_server_that_opened_another_world(tree):
    live = live_server_without_a_reader(tree, '[x] Preparing level "world"\n')
    try:
        r = tree.s("cmd", "forceload add 0 0", "2", bound=60)
        assert r.returncode == 2 and "no session" in r.stdout
    finally:
        live.kill()
        live.wait()


def test_m_interrupt_stops_the_server_and_restores(tree):
    t = tree
    p = t.start()
    up(t)
    server = t.pid("server")
    p.send_signal(signal.SIGTERM)
    assert t.finish(p) == 130
    gone(t)
    assert not alive(server)


def test_n_a_server_that_ignores_stop_and_sigterm_is_sigkilled_and_archived(tree):
    t = tree
    (t.run / "mode").write_text("nostop\n")
    p = t.start()
    up(t)
    server, java = t.pid("server"), (t.run / "java.pid").read_text().strip()
    p.send_signal(signal.SIGTERM)
    assert t.finish(p) == 1
    o = t.out(p)
    assert "SERVER DID NOT STOP" in o and "failed-boot archive: " in o
    gone(t)
    dead(server, java)
    assert len(archives(t)) == 1


def test_o_a_bad_chunks_file_in_the_test_world_fails_the_stop(tree):
    t = tree
    (t.run / "world/data").mkdir(parents=True)
    (t.run / "world/data/chunks.dat").write_bytes(b"not gzip")
    p = t.start()
    up(t)
    r = t.s("stop")
    assert r.returncode == 1 and "FORCED CHUNKS" in r.stdout, r.stdout
    assert t.finish(p) == 1
    gone(t)


def test_p_a_running_server_is_refused_and_nothing_is_touched(tree):
    r = tree.s("start", PGREP_FOUND="unix_args", bound=60)
    assert r.returncode == 2 and "a Minecraft server is already running" in r.stdout, r.stdout
    gone(tree)
    assert not (tree.run / "packwiz-serve.session.log").exists()


def test_q_a_running_packwiz_serve_is_refused_and_nothing_is_touched(tree):
    r = tree.s("start", PGREP_FOUND="packwiz serve", bound=60)
    assert r.returncode == 2 and "packwiz serve is already running" in r.stdout, r.stdout
    gone(tree)
    assert not (tree.run / "packwiz-serve.session.log").exists()


def test_r_a_second_signal_does_not_skip_the_restore(tree):
    t = tree
    (t.run / "mode").write_text("nostop\n")
    p = t.start()
    up(t)
    java = (t.run / "java.pid").read_text().strip()
    p.send_signal(signal.SIGTERM)
    for _ in range(BOUND * 10):                  # the stop has reached the server, so cleanup is in its wait
        if (t.run / "stop-seen").exists():
            break
        time.sleep(0.1)
    p.send_signal(signal.SIGTERM)
    t.finish(p)
    gone(t)
    dead(java)


def test_s_no_level_name_line_stops_before_the_server(tree):
    t = tree
    props = "online-mode=true\nserver-port=25565\n"
    (t.run / "server.properties").write_text(props)
    p = t.start()
    assert t.finish(p) == 1
    assert "no level-name line" in t.out(p)
    assert (t.run / "server.properties").read_text() == props
    assert not (t.run / "server.properties.session-backup").exists()
    assert not (t.run / "java.pid").exists()


def test_t_no_online_mode_line_stops_an_offline_start(tree):
    t = tree
    props = "level-name=world\nserver-port=25565\n"
    (t.run / "server.properties").write_text(props)
    p = t.start("--offline")
    assert t.finish(p) == 1
    assert "no online-mode line" in t.out(p)
    assert (t.run / "server.properties").read_text() == props
    assert not (t.run / "java.pid").exists()


def test_u_an_older_boots_good_log_does_not_pass_the_check(tree):
    t = tree
    (t.run / "logs").mkdir()
    shutil.copy(t.run / "good.log", t.run / "logs/latest.log")
    (t.run / "mode").write_text("nolog\n")
    p = t.start()
    assert t.finish(p) == 1
    o = t.out(p)
    assert "MISSING LOG" in o and "BOOT LOG ERRORS" in o and "SESSION UP" not in o
    gone(t)


def test_v_a_dead_holder_leaves_a_way_out(tree):
    t = tree
    p = t.start()
    up(t)
    hold, java = t.pid("hold"), (t.run / "java.pid").read_text().strip()
    p.send_signal(signal.SIGKILL)
    p.wait()
    os.kill(int(hold), signal.SIGKILL)
    dead(hold)
    r = t.s("stop", bound=60)
    assert r.returncode == 1 and f"kill {java}" in r.stdout and "still saves" in r.stdout, r.stdout
    os.kill(int(java), signal.SIGTERM)
    dead(java)
    assert "session: not running" in t.s("stop").stdout
    gone(t)


def test_w_a_reused_start_pid_is_not_signalled(tree):
    t = tree
    other = subprocess.Popen(["sleep", "600"])
    try:
        (t.run / "session.pids").write_text(f"start={other.pid}\nworld=probe_v03\n")
        r = t.s("stop", bound=60)
        assert other.poll() is None, "stop signalled a process that is not a session"
        assert "session: not running" in r.stdout and "reused" in r.stdout, r.stdout
        gone(t)
    finally:
        other.kill()
        other.wait()


def test_x_a_reused_server_pid_gets_a_hint_and_survives_stop(tree):
    t = tree
    live = live_server_without_a_reader(t, "")
    try:
        assert "reused" in t.s("status", bound=60).stdout
        assert "reused" in t.s("cmd", "list", "1", bound=60).stdout
        r = t.s("stop", bound=60)
        assert live.poll() is None, "stop signalled a process that is not the server"
        assert "session: not running" in r.stdout and "reused" in r.stdout, r.stdout
        gone(t)
    finally:
        live.kill()
        live.wait()


def test_y_a_folder_that_is_not_a_world_is_refused(tree):
    t = tree
    (t.run / "mods").mkdir()
    r = t.s("start", "--world", "mods", bound=60)
    assert r.returncode == 2 and "refusing --world" in r.stdout, r.stdout
    gone(t)
    assert not (t.run / "java.pid").exists()


def test_z_a_world_from_an_earlier_session_is_accepted(tree):
    t = tree
    (t.run / "probe_v03").mkdir()
    (t.run / "probe_v03/level.dat").write_text("")
    p = t.start()
    up(t)
    assert t.s("stop").returncode == 0
    assert t.finish(p) == 0
    gone(t)


def test_aa_a_first_boot_that_failed_early_can_start_again(tree):
    # Main opens the world's session.lock before the datapack load, so a failed first boot leaves a folder with no level.dat.
    t = tree
    (t.run / "probe_v03").mkdir()
    (t.run / "probe_v03/session.lock").write_text("")
    p = t.start()
    up(t)
    assert t.s("stop").returncode == 0
    assert t.finish(p) == 0
    gone(t)


def script_pattern(name):
    for line in (TOOLS / "server_session.sh").read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip("'")
    pytest.fail(name)


@pytest.mark.parametrize("name,line,found", [
    ("SERVER_PATTERN", "java @user_jvm_args.txt @libraries/net/neoforged/neoforge/21.1.250/unix_args.txt nogui", True),
    ("SERVER_PATTERN", "/usr/bin/java @user_jvm_args.txt @libraries/net/neoforged/neoforge/21.1.250/unix_args.txt nogui", True),
    ("SERVER_PATTERN", "bash -c pgrep -fl unix_args.txt", False),
    ("SERVE_PATTERN", "packwiz serve -p 8087", True),
    ("SERVE_PATTERN", "/Users/x/go/bin/packwiz serve -p 8087", True),
    ("SERVE_PATTERN", "bash /tmp/stubs/packwiz serve -p 8087", False),
])
def test_bb_the_real_patterns_match_the_real_command_lines(name, line, found):
    r = subprocess.run(["grep", "-Eq", script_pattern(name)], input=line, text=True)
    assert (r.returncode == 0) == found


def test_cc_an_empty_ps_does_not_call_a_live_session_reused(tree):
    t = tree
    stub = t.pack.parent / "psbin"
    write_x(stub / "ps", "#!/usr/bin/env bash\nexit 1\n")
    live = live_server_without_a_reader(t, "")
    try:
        r = t.s("status", bound=60, PATH=f"{stub}:{os.environ['PATH']}")
        assert "reused" not in r.stdout, r.stdout
    finally:
        live.kill()
        live.wait()


def test_dd_starts_refusal_names_a_reused_pid(tree):
    t = tree
    live = live_server_without_a_reader(t, "")
    try:
        r = t.s("start", bound=60)
        assert r.returncode == 2 and "already running" in r.stdout and "reused" in r.stdout, r.stdout
    finally:
        live.kill()
        live.wait()
