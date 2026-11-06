"""tools/probe_worldgen.sh and tools/probe_loot.sh release the forceload they add (v0.3 Task 11c fix, D136).

Each probe runs `forceload add` on a block of chunks. A forceload is saved in the world (data/chunks.dat) and re-added at
every later boot, and a stop that arrives while those chunks load waits for every one of them: the 5,121 chunks the two
probes had leaked made tools/server_boot.sh's stop take 25-199 s (SERVER DID NOT STOP). So each probe:
  - on its normal path sends `forceload remove` for the same area, in the same dimension, before it stops the server;
  - when it fails mid-run (set -e, or a signal), removes it in its EXIT trap, before the `stop`, whenever the server still runs;
  - fails (exit 1, "FORCELOAD NOT RELEASED") when the removal is not confirmed by an "Unmarked" reply
    (commands.forceload.removed.single/.multiple in the 1.21.1 server jar's en_us.json), even if every count passed;
  - sets what it must remove before it sends the add, so a probe ended while it waits for the add's reply still removes it;
  - when the server is already gone, fails and says so, and does not hang (Task 11c fix round 2, M4): it holds the console pipe
    itself (`exec 3<>`, in tools/probe_lib.sh), so no write waits in open(2) for a reader, and it sends nothing to a server
    that is gone, so the pipe's buffer cannot fill;
  - refuses a worldgen radius whose area forceload would refuse (over 256 chunks), before it boots anything (M6).

Each scenario copies the probe and tools/probe_lib.sh under a tmp ROOT and runs it on stubs, in the style of
test_server_boot.py: packwiz and sleep stubs first on PATH (sleep naps 0.01 s), a canary directory next (a packwiz, java or
curl found there means a lookup skipped the stubs), then /usr/bin:/bin. JAVA_HOME is a stub jdk whose java, run by a
NeoForge-shaped run.sh, is a stub server: it logs each console command it reads, answers in the server's
[minecraft/MinecraftServer] format, tracks what is force-loaded per dimension, and writes that to forced_at_exit.json when it
stops.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

STUB_SERVER = r'''import json, os, re, sys
state = os.environ["PROBE_STUB_STATE"]


def note(name, text):
    with open(os.path.join(state, name), "a") as f:
        f.write(text + "\n")


if sys.argv[1:2] == ["-jar"]:      # the packwiz-installer-bootstrap sync
    note("events", "java-stub " + " ".join(sys.argv[1:]))
    sys.exit(0)
open(os.path.join(state, "java.pid"), "w").write(str(os.getpid()))
try:                               # the probe's own end of the console pipe, fd 3, is not the server's to hold
    os.fstat(3)
    note("events", "server holds fd 3")
except OSError:
    pass
open(os.path.join(state, "runsh.pid"), "w").write(str(os.getppid()))
forced = {}


def say(msg):
    if not mute:
        print("[13:00:00] [Server thread/INFO] [minecraft/MinecraftServer]: " + msg, flush=True)


def leave(code):
    json.dump(forced, open(os.path.join(state, "forced_at_exit.json"), "w"))
    sys.exit(code)


print('[13:00:00] [Server thread/INFO] [minecraft/DedicatedServer]: Done (1.0s)! For help, type "help"', flush=True)
# STUB_SILENT_ON: a command containing it is ignored. STUB_MUTE_ON: it takes effect, but no reply is logged. STUB_CRASH_ON: the
# STUB_CRASH_AT-th command containing it (default the first) ends the server, with no reply and no stop.
silent, crash = os.environ.get("STUB_SILENT_ON", ""), os.environ.get("STUB_CRASH_ON", "")
crash_at, seen, mute = int(os.environ.get("STUB_CRASH_AT", "1")), 0, False
while True:
    line = sys.stdin.readline()
    if not line:
        leave(3)
    command = line.strip()
    note("commands", command)
    m = re.fullmatch(r"execute in (\S+) run (.*)", command)
    dim, run = m.groups() if m else ("minecraft:overworld", command)
    if crash and crash in command:
        seen += 1
        if seen == crash_at:
            leave(1)               # the server dies: no reply, no stop
    if silent and silent in command:
        continue
    mute = bool(os.environ.get("STUB_MUTE_ON")) and os.environ["STUB_MUTE_ON"] in command
    words = run.split()
    area = " ".join(words[2:])
    if run == "stop":
        print("[13:00:01] [Server thread/INFO] [minecraft/MinecraftServer]: Stopping server", flush=True)
        leave(0)
    elif words[:2] == ["forceload", "add"]:
        forced.setdefault(dim, []).append(area)
        say("Marked chunks %s in %s to be force loaded" % (area, dim))
    elif words[:2] == ["forceload", "remove"]:
        if os.environ.get("STUB_REMOVE_REPLY"):
            say(os.environ["STUB_REMOVE_REPLY"])
        elif area in forced.get(dim, []):
            forced[dim].remove(area)
            say("Unmarked chunks %s in %s for force loading" % (area, dim))
        else:
            say("No chunks were removed from force loading")
    elif words[:1] == ["gamerule"]:
        say("Gamerule %s is now set to: %s" % (words[1], words[2]))
    elif words[:1] == ["fill"]:
        say("Successfully filled 4096 block(s)")
    elif words[:1] == ["setblock"]:
        say("Changed the block at 0, 300, 0")
    elif words[:2] == ["loot", "insert"]:
        say("Dropped 1 item(s)")
    elif words[:2] == ["data", "get"]:
        say('0, 300, 0 has the following block data: [{Slot: 0b, count: 1, id: "minecraft:diamond"}]')
    elif words[:2] == ["data", "merge"]:
        say("Modified block data of 0, 300, 0")
    else:
        say("Unknown or incomplete command, see below for error")
'''
STUB_SH = {
    "packwiz": 'echo $$ > "$PROBE_STUB_STATE/packwiz.pid"\nexec /bin/sleep 300\n',
    # STUB_SLEEP_FAIL_WHEN=text: the first sleep after the stub server has read a command containing text fails (once), so
    # set -e ends the probe mid-run.
    "sleep": 'if [ -n "${STUB_SLEEP_FAIL_WHEN:-}" ] && [ ! -e "$PROBE_STUB_STATE/sleep-failed" ] && \\\n'
             '   grep -qF -- "$STUB_SLEEP_FAIL_WHEN" "$PROBE_STUB_STATE/commands" 2>/dev/null; then\n'
             '  : > "$PROBE_STUB_STATE/sleep-failed"; echo "sleep stub: fail after $STUB_SLEEP_FAIL_WHEN" >&2; exit 1\n'
             'fi\n'
             'exec /bin/sleep 0.01\n',
}
CANARY = '{ echo "CANARY $(basename "$0") $*" >> "$PROBE_STUB_STATE/canary"; exit 99; }\n'
RUN_SH = '#!/usr/bin/env sh\njava @user_jvm_args.txt @libraries/net/neoforged/neoforge/21.1.250/unix_args.txt "$@"\n'
STUB_NAMES = ("packwiz", "runsh", "java")

WORLDGEN_ARGS = ["-d", "twilightforest:twilight_forest", "-y", "-32,10", "-r", "2", "allthemodium:allthemodium_ore"]
WG_AREA = "-32 -32 31 31"      # -r 2 around chunk 0,0: blocks (0-2)*16 .. (0+2)*16-1
PROBES = {
    # name: (script, args, the add it sends, the remove it must send, the main-shell command a failure is staged on)
    "worldgen": ("probe_worldgen.sh", WORLDGEN_ARGS,
                 f"execute in twilightforest:twilight_forest run forceload add {WG_AREA}",
                 f"execute in twilightforest:twilight_forest run forceload remove {WG_AREA}", "gamerule"),
    "loot": ("probe_loot.sh", ["-n", "3", "twilightforest:stronghold_cache,minecraft:diamond,1,3"],
             "forceload add 0 0", "forceload remove 0 0", "setblock"),
}


def write_exec(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


def running(pid):
    stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(stat) and "Z" not in stat


@pytest.fixture(scope="module")
def kit(tmp_path_factory):
    kit = tmp_path_factory.mktemp("probe_kit")
    for name, body in STUB_SH.items():
        write_exec(kit / "bin" / name, "#!/bin/bash\n" + body)
    for name in ("packwiz", "java", "curl"):
        write_exec(kit / "canary" / name, "#!/bin/bash\n" + CANARY)
    write_exec(kit / "jdk" / "bin" / "java", f"#!{sys.executable}\n" + STUB_SERVER)
    write_exec(kit / "run.sh", RUN_SH)
    return kit


@pytest.fixture
def probe(tmp_path, kit):
    state = tmp_path / "state"
    state.mkdir()
    started = []

    def run(name, env=None, term_on=None, args=None):
        script, default_args = PROBES[name][:2]
        root = tmp_path / name
        (root / "tools").mkdir(parents=True)
        shutil.copy(ROOT / "tools" / script, root / "tools" / script)
        if (ROOT / "tools" / "probe_lib.sh").exists():
            shutil.copy(ROOT / "tools" / "probe_lib.sh", root / "tools" / "probe_lib.sh")
        (root / ".run" / "server").mkdir(parents=True)
        (root / ".run" / "server" / "run.sh").symlink_to(kit / "run.sh")
        path = f"{kit / 'bin'}:{kit / 'canary'}:/usr/bin:/bin"
        assert shutil.which("java", path=f"{kit / 'jdk' / 'bin'}:{path}") == str(kit / "jdk" / "bin" / "java")
        full = {"PATH": path, "HOME": str(tmp_path), "TMPDIR": str(tmp_path), "JAVA_HOME": str(kit / "jdk"),
                "PROBE_STUB_STATE": str(state), "PYTHONDONTWRITEBYTECODE": "1", **(env or {})}
        p = subprocess.Popen(["/bin/bash", str(root / "tools" / script), *(args or default_args)], env=full,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, start_new_session=True)
        started.append(p)
        if term_on:
            deadline = time.time() + 20
            while time.time() < deadline and term_on not in commands(state):
                time.sleep(0.02)
            assert term_on in commands(state), f"the probe never sent {term_on!r}"
            p.send_signal(signal.SIGTERM)        # the probe's bash only, as a `kill <pid>` would
        out, _ = p.communicate(timeout=60)
        pids = {n: int((state / f"{n}.pid").read_text()) for n in STUB_NAMES if (state / f"{n}.pid").exists()}
        deadline = time.time() + 3
        while [n for n, pid in pids.items() if running(pid)] and time.time() < deadline:
            time.sleep(0.02)
        assert not (state / "canary").exists(), (state / "canary").read_text()
        at_exit_file = state / "forced_at_exit.json"
        at_exit = json.loads(at_exit_file.read_text()) if at_exit_file.exists() else {}
        return p.returncode, out, commands(state).splitlines(), {d: a for d, a in at_exit.items() if a}, \
            {n: pid for n, pid in pids.items() if running(pid)}

    run.state = state
    yield run
    for p in started:
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGKILL)
    for n in STUB_NAMES:
        f = state / f"{n}.pid"
        if f.exists() and running(int(f.read_text())):
            os.kill(int(f.read_text()), signal.SIGKILL)


def commands(state):
    f = state / "commands"
    return f.read_text() if f.exists() else ""


def removed_before_stop(sent, name):
    """The probe's remove matches its add (same area, same dimension) and comes after it and before the `stop`."""
    _, _, add, remove, _ = PROBES[name]
    assert add in sent and remove in sent and "stop" in sent, sent
    assert sent.index(add) < sent.index(remove) < sent.index("stop"), sent
    return True


@pytest.mark.parametrize("name", PROBES)
def test_a_passing_probe_removes_its_forceload_before_the_stop(probe, name):
    code, out, sent, still_forced, alive = probe(name)
    assert code == 0, out
    assert removed_before_stop(sent, name)
    assert sent.count(PROBES[name][3]) == 1, "removed once: the EXIT trap does not repeat it"
    assert still_forced == {} and alive == {}, (still_forced, alive)
    assert "FORCELOAD NOT RELEASED" not in out
    assert "server holds fd 3" not in (probe.state / "events").read_text()


@pytest.mark.parametrize("name", PROBES)
def test_a_probe_that_fails_mid_run_removes_its_forceload_in_its_exit_trap(probe, name):
    """set -e ends the probe while it waits for a reply (the stub server never answers that command, and the next sleep
    fails); its EXIT trap removes the forceload, then stops the server. The probe still fails."""
    trigger = PROBES[name][4]
    code, out, sent, still_forced, alive = probe(name, {"STUB_SILENT_ON": trigger, "STUB_SLEEP_FAIL_WHEN": trigger})
    assert code != 0 and "sleep stub: fail after" in out, out
    assert removed_before_stop(sent, name)
    assert still_forced == {} and alive == {}, (still_forced, alive)


@pytest.mark.parametrize("name", PROBES)
def test_a_probe_ended_by_sigterm_removes_its_forceload(probe, name):
    trigger = PROBES[name][4]
    code, out, sent, still_forced, alive = probe(name, {"STUB_SILENT_ON": trigger}, term_on=trigger)
    assert code != 0, out
    assert removed_before_stop(sent, name)
    assert still_forced == {} and alive == {}, (still_forced, alive)


@pytest.mark.parametrize("name", PROBES)
def test_a_probe_ended_while_its_add_waits_for_a_reply_still_removes_it(probe, name):
    """M5: the add takes effect but its reply has not come when the probe is ended. FORCED was set before the add was sent,
    so the EXIT trap removes it, before the stop."""
    code, out, sent, still_forced, alive = probe(name, {"STUB_MUTE_ON": "forceload add"}, term_on="forceload add")
    assert code != 0, out
    assert removed_before_stop(sent, name)
    assert still_forced == {} and alive == {}, (still_forced, alive, out)


@pytest.mark.parametrize("name", PROBES)
@pytest.mark.parametrize("env, reason", [
    ({"STUB_REMOVE_REPLY": "No chunks were removed from force loading"}, "No chunks were removed from force loading"),
    ({"STUB_SILENT_ON": "forceload remove"}, "no forceload reply within 60 s"),
    ({"STUB_REMOVE_REPLY": "Too many chunks in the specified area (maximum 256, specified 289)"},
     "Too many chunks in the specified area (maximum 256, specified 289)"),
], ids=["not-unmarked", "no-reply", "too-many-chunks"])
def test_a_removal_that_is_not_confirmed_fails_the_probe(probe, name, env, reason):
    """Every count passes, but the server does not confirm the removal: the probe fails, naming the command and the reply,
    and still stops the server."""
    code, out, sent, still_forced, alive = probe(name, env)
    assert code == 1, out
    assert f"FORCELOAD NOT RELEASED ({PROBES[name][3]}): {reason}" in out.splitlines(), out
    assert removed_before_stop(sent, name) and alive == {}


@pytest.mark.parametrize("name, crash, at, args", [
    ("worldgen", "forceload add", 1, None),
    ("worldgen", "fill", 1, WORLDGEN_ARGS + ["minecraft:stone"]),
    ("loot", "forceload add", 1, None),
    ("loot", "data merge", 3, None),
    ("loot", "loot insert", 1, ["-n", "300", "twilightforest:stronghold_cache,minecraft:diamond,1,300"]),
], ids=["worldgen-on-the-add", "worldgen-on-the-first-of-two-fills", "loot-on-the-add", "loot-on-the-last-roll",
        "loot-on-the-first-of-300-rolls"])
def test_a_probe_whose_server_died_fails_and_does_not_hang(probe, name, crash, at, args):
    """The server dies mid-run with the forceload still saved. Nothing can remove it now (the next boot's forced-chunk guard
    reports it): the probe says so and fails, and does not hang, wherever the death falls: before more commands (the old
    holder left the pipe without a reader, so the next write blocked in open(2)), or before 300 rolls whose 35 KB of commands
    would fill the pipe's buffer (8,192 bytes on macOS) with nobody reading. The fixture's 60 s timeout is the hang check."""
    code, out, sent, still_forced, alive = probe(name, {"STUB_CRASH_ON": crash, "STUB_CRASH_AT": str(at)}, args=args)
    assert code == 1, out
    assert f"FORCELOAD NOT RELEASED ({PROBES[name][3]}): the server is gone" in out.splitlines(), out
    assert PROBES[name][3] not in sent and "stop" not in sent, sent
    assert alive == {}, alive
    if crash == "forceload add":       # the next command is not sent: it would only sit in the pipe's buffer
        assert [line for line in out.splitlines() if line.startswith("the server is gone; not sent: ")], out


@pytest.mark.parametrize("radius", ["9", "0", "x", "08"])
def test_a_radius_forceload_would_refuse_is_refused_before_the_boot(probe, radius):
    """M6: forceload refuses an area over 256 chunks ("Too many chunks", ForceLoadCommand.changeForceLoad offsets 108-153 in
    neoforge-21.1.250-server.jar), and the probe would then count an area nothing keeps loaded. -r 9 is 324 chunks; the
    probe exits 2 before it syncs or boots anything."""
    args = WORLDGEN_ARGS[:4] + ["-r", radius] + WORLDGEN_ARGS[6:]
    code, out, sent, still_forced, alive = probe("worldgen", args=args)
    assert code == 2, out
    assert "forceload takes 1 to 256 chunks: -r 1 to 8" in out, out
    assert sent == [] and alive == {}, (sent, alive)
    assert not list(probe.state.glob("*.pid")), list(probe.state.glob("*.pid"))
