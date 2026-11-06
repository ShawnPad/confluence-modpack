"""Unit tests for tools/server_session.sh: every path that needs no Minecraft server (plan v0.3 Task 12).

CONFLUENCE_RUN points the script at a temporary folder, so nothing here touches .run/server. The two `cmd` tests stand
in for the server with a bash process that reads the console pipe and appends log lines."""
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "server_session.sh"


def run(args, run_dir):
    env = dict(os.environ, CONFLUENCE_RUN=str(run_dir))
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=30)


def test_no_subcommand_prints_usage(tmp_path):
    r = run([], tmp_path)
    assert r.returncode == 2
    assert "tools/server_session.sh start [--offline] [--world NAME]" in r.stdout


def test_status_without_a_session_is_down(tmp_path):
    r = run(["status"], tmp_path)
    assert (r.returncode, r.stdout.strip()) == (1, "session: down")


def test_status_with_a_dead_server_pid_is_down(tmp_path):
    dead = subprocess.Popen(["true"])
    dead.wait()
    (tmp_path / "session.pids").write_text(f"server={dead.pid}\nworld=probe_v03\n")
    r = run(["status"], tmp_path)
    assert (r.returncode, r.stdout.strip()) == (1, "session: down")


def test_wait_without_a_session_is_down(tmp_path):
    r = run(["wait"], tmp_path)
    assert (r.returncode, r.stdout.strip()) == (1, "session: down")


def test_cmd_without_a_session_refuses(tmp_path):
    r = run(["cmd", "list"], tmp_path)
    assert r.returncode == 2
    assert r.stdout.startswith("no session")


def test_stop_without_a_session_is_a_no_op(tmp_path):
    r = run(["stop"], tmp_path)
    assert (r.returncode, r.stdout.strip()) == (0, "session: not running")


def test_start_without_a_server_folder_refuses(tmp_path):
    r = run(["start", "--offline"], tmp_path)
    assert r.returncode == 2
    assert r.stdout.startswith(f"no server in {tmp_path}")
    assert not (tmp_path / "server.properties.session-backup").exists()


# Lines the server logs through the same [minecraft/MinecraftServer] logger as a console reply: a lag warning
# (pack/.run/server/console.probe.log line 816), chat (MinecraftServer.logChatMessage, "[{}] {}" with the
# "<%s> %s" chat format) and a join broadcast (vanilla lang multiplayer.player.joined).
NOISE = [
    "[12:00:01] [Server thread/WARN] [minecraft/MinecraftServer]: Can't keep up! Is the server overloaded? Running 20473ms or 409 ticks behind",
    "[12:00:01] [Server thread/INFO] [minecraft/MinecraftServer]: [Not Secure] <P2> hello",
    "[12:00:01] [Server thread/INFO] [minecraft/MinecraftServer]: P2 joined the game",
]
REPLY = "[12:00:03] [Server thread/INFO] [minecraft/MinecraftServer]: Gamerule doMobSpawning is currently set to: false"


def fake_session(run_dir, reply_lines):
    """A 'server' that takes one console line from the pipe, logs NOISE at once and reply_lines 2 s later."""
    (run_dir / "console.session.log").write_text('[12:00:00] [Server thread/INFO] [minecraft/DedicatedServer]: Done (9.9s)! For help, type "help"\n')
    (run_dir / "noise.txt").write_text("\n".join(NOISE) + "\n")
    (run_dir / "reply.txt").write_text("".join(line + "\n" for line in reply_lines))
    os.mkfifo(run_dir / "session.in")
    server = subprocess.Popen(["bash", "-c", 'read -r _ < session.in; cat noise.txt >> console.session.log; sleep 2; '
                               'cat reply.txt >> console.session.log; exec sleep 30'], cwd=run_dir)
    (run_dir / "session.pids").write_text(f"world=probe_v03\nserver={server.pid}\n")
    return server


def test_cmd_skips_lag_chat_and_join_lines(tmp_path):
    server = fake_session(tmp_path, [REPLY])
    try:
        r = run(["cmd", "gamerule doMobSpawning", "10"], tmp_path)
    finally:
        server.kill()
        server.wait()
    assert (r.returncode, r.stdout) == (0, "Gamerule doMobSpawning is currently set to: false\n")


def test_cmd_without_a_reply_times_out(tmp_path):
    # vanilla gamemode logs nothing for a player already in that mode (GameModeCommand.setMode), so only noise arrives
    server = fake_session(tmp_path, [])
    try:
        r = run(["cmd", "gamemode survival P2", "4"], tmp_path)
    finally:
        server.kill()
        server.wait()
    assert r.returncode == 1
    assert r.stdout.startswith("(no reply within 4 s; see ")
