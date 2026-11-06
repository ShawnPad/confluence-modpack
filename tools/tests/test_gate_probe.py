"""tools/gate_probe.py runs under Rhino, so here only its packaging and the lints it can fail are checked (v0.3, D138)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_probe as gp  # noqa: E402
from test_rhino_hazards import hidden_or_renamed_calls, lexical_in_try  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def test_the_stand_in_never_ships():
    assert [p for p in (ROOT / "kubejs").rglob("*") if p.name in (gp.STANDIN.name, gp.INSTALLED.name) or "cprobe" in p.name] == []
    assert "tools/" in (ROOT / ".packwizignore").read_text().split()
    assert "gate_probe" not in (ROOT / "index.toml").read_text()


def test_the_stand_in_passes_the_rhino_lints_it_exists_to_back():
    src = gp.STANDIN.read_text(encoding="utf-8")
    assert hidden_or_renamed_calls(src) == []
    assert lexical_in_try(src) == ([], 0)


def test_the_throwaway_world_is_not_a_real_one():
    assert gp.WORLD not in ("world", "probe_v03")


def test_tolerated_errors_are_named_and_narrow():
    line = "[12:00:00] [Netty Local Client IO #1/ERROR] [net.minecraft.network.PacketEncoder/]: Error sending custom_payload"
    assert any(t.search(line) for t in gp.TOLERATED)
    for other in ("[12:00:00] [Server thread/ERROR] [net.minecraft.network.PacketEncoder/]: custom_payload",
                  "[12:00:00] [Netty Local Client IO #1/ERROR] [some.other.Logger/]: custom_payload",
                  "[12:00:00] [Server thread/ERROR] [KubeJS Server/]: anything"):
        assert not any(t.search(other) for t in gp.TOLERATED), other


def test_a_failed_row_is_counted_and_an_exception_fails_only_its_row(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gp, "KJ_LOG", tmp_path / "server.log")
    r = gp.Rows("x", None)
    r.row("A", "-", "d", "e", lambda: (True, "fine"))
    r.row("B", "-", "d", "e", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    out = capsys.readouterr().out
    assert (r.count, r.failed) == (2, 1) and "| A |" in out and "boom" in out and "| FAIL |" in out


def test_a_gate_error_line_fails_a_row_that_otherwise_passed(tmp_path, monkeypatch, capsys):
    log = tmp_path / "server.log"
    monkeypatch.setattr(gp, "KJ_LOG", log)

    def run():
        log.write_text("[00:00:00] [ERROR] ! confluence other-gate: pad handler error, click cancelled: TypeError\n")
        return True, "stayed in the Nether"
    r = gp.Rows("old", None)
    r.row("P2.1", "L", "d", "e", run)
    assert r.failed == 1 and "pad handler error" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [["--help"]])
def test_help_does_not_start_anything(argv, capsys, monkeypatch):
    monkeypatch.setattr(gp.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("started")))
    with pytest.raises(SystemExit) as e:
        gp.main(argv)
    assert e.value.code == 0 and "usage:" in capsys.readouterr().out


# ---- whose session is it (a refused `start` must not cost another session its world) --------------------------------------

class Proc:
    def __init__(self, code=None):
        self.code = code

    def poll(self):
        return self.code

    def wait(self, timeout=None):
        return self.code


class Result:
    def __init__(self, out="", rc=0):
        self.stdout, self.stderr, self.returncode = out, "", rc


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A fake run folder and a fake session script: `replies` sets each subcommand's answer, and `calls` records them."""
    run = tmp_path / ".run" / "server"
    (run / "kubejs" / "server_scripts").mkdir(parents=True)
    (run / "run.sh").write_text("")
    (run / gp.WORLD).mkdir()
    (run / gp.WORLD / "level.dat").write_text("")
    events = tmp_path / "events.js"
    events.write_text("working tree\n")
    (run / "kubejs" / "server_scripts" / "events.js").write_text("working tree\n")
    for name, value in (("ROOT", tmp_path), ("RUN", run), ("EVENTS", events), ("RUN_EVENTS", run / "kubejs" / "server_scripts" / "events.js"),
                        ("INSTALLED", run / "kubejs" / "server_scripts" / "zz.js"), ("KJ_LOG", tmp_path / "s.log"), ("LATEST", tmp_path / "l.log")):
        monkeypatch.setattr(gp, name, value)
    for stub in ("build_sites", "gate_rows", "piglich_rows"):
        monkeypatch.setattr(gp, stub, lambda *a: None)
    monkeypatch.setattr(gp.time, "sleep", lambda s: None)
    monkeypatch.setenv("PATH", os.environ["PATH"])   # main prepends go/bin
    calls, replies = [], {"status": ["session: down"], "wait": "session: up (world " + gp.WORLD + ")", "stop": "session: down",
                              "cmd": "cprobe> ok"}

    def fake_run(cmd, **kw):
        sub = cmd[1]
        calls.append(sub if sub != "cmd" else "cmd " + cmd[2])
        reply = replies[sub]
        if isinstance(reply, list):
            reply = reply.pop(0) if len(reply) > 1 else reply[0]
        if isinstance(reply, Exception):
            raise reply
        return Result(reply, 0 if "session: up" in reply or sub != "status" else 1) if sub != "stop" else Result(reply, replies.get("stop_rc", 0))
    monkeypatch.setattr(gp.subprocess, "run", fake_run)

    def fake_start(*a, **k):   # main removes any old throwaway world first; the start makes it again
        (run / gp.WORLD).mkdir(exist_ok=True)
        (run / gp.WORLD / "level.dat").write_text("")
        return replies.setdefault("proc", Proc())
    monkeypatch.setattr(gp.subprocess, "Popen", fake_start)
    return type("W", (), {"run": run, "calls": calls, "replies": replies, "events": events})


def test_a_session_already_up_is_refused_before_anything_is_touched(world, capsys):
    world.replies["status"] = ["session: up (world probe_v03, console log x)"]
    assert gp.main([]) == 2
    assert "stop" not in world.calls and not gp.INSTALLED.exists() and (world.run / gp.WORLD / "level.dat").exists()
    assert "probe_v03" in capsys.readouterr().out


@pytest.mark.parametrize("reply,code", [
    pytest.param("session: up (world probe_v03)", None, id="another-world"),
    pytest.param("session: up (world probe_v03)", 2, id="another-world-and-start-refused"),
    pytest.param("session: up (world " + gp.WORLD + ")", 2, id="own-name-but-start-has-exited"),
])
def test_a_session_that_is_not_its_own_is_left_alone(world, reply, code, capsys):
    # status says down at first, then the other session comes up during `start`.
    world.replies["status"] = ["session: down", "session: up (world probe_v03)"]
    world.replies["wait"], world.replies["proc"] = reply, Proc(code)
    assert gp.main([]) == 2
    assert "stop" not in world.calls and not [c for c in world.calls if c.startswith("cmd ")]
    assert not gp.INSTALLED.exists()


def test_a_stop_that_times_out_still_cleans_up_and_fails_and_keeps_a_live_world(world, tmp_path, capsys):
    old = tmp_path / "old.js"
    old.write_text("old code\n")
    world.replies["status"] = ["session: down", "session: up (world " + gp.WORLD + ")"]
    world.replies["stop"] = subprocess.TimeoutExpired("stop", 240)
    assert gp.main(["--events", str(old)]) == 1
    assert not gp.INSTALLED.exists() and gp.RUN_EVENTS.read_text() == "working tree\n"
    assert (world.run / gp.WORLD / "level.dat").exists()
    assert "stop" in capsys.readouterr().out.lower()


def test_a_stop_that_reports_failure_gives_a_non_zero_exit(world):
    world.replies["stop_rc"] = 1
    assert gp.main([]) == 1


def test_a_clean_run_removes_the_stand_in_and_the_world(world):
    world.replies["status"] = ["session: down"]
    assert gp.main([]) == 0
    assert "stop" in world.calls and not gp.INSTALLED.exists() and not (world.run / gp.WORLD).exists()


def test_piglich_only_says_the_gate_rows_did_not_run(world, capsys):
    assert gp.main(["--piglich-only"]) == 0
    assert "GATE ROWS DID NOT RUN" in capsys.readouterr().out.strip().splitlines()[-1]


# ---- what a row may accept ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("out,seen", [
    ("playerDamage=[3.5x2 1.0x4] playerSources=[fireballx2 onFirex4]", False),
    ("playerDamage=[17.0x1] playerSources=[fireballx1]", False),
    ("playerDamage=[7.0x4] playerSources=[fireballx4]", True),
    ("playerDamage=[12.0x4] playerSources=[mobx4]", True),
    ("playerDamage=[] playerSources=[]", False),
])
def test_p63_needs_melee_not_any_damage(out, seen):
    assert gp.melee_seen(out) is seen


def test_a_pad_that_stayed_only_because_travel_was_stopped_fails(tmp_path, monkeypatch):
    log = tmp_path / "s.log"
    log.write_text("")
    monkeypatch.setattr(gp, "KJ_LOG", log)
    monkeypatch.setattr(gp, "dim", lambda n: gp.NETHER)

    def click(n, pad):
        with log.open("a") as f:
            f.write("[00:00:00] [INFO] confluence other-gate: travel check stopped ProbeP2 going to allthemodium:the_other\n")
    monkeypatch.setattr(gp, "click", click)
    ok, observed = gp.pad_stays("ProbeP2", gp.NETHER_PAD, gp.NETHER)
    assert ok is False and "travel check" in observed
    monkeypatch.setattr(gp, "click", lambda n, pad: None)
    assert gp.pad_stays("ProbeP2", gp.NETHER_PAD, gp.NETHER)[0] is True
