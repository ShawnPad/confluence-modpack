"""tools/gate_probe.py runs under Rhino, so here only its packaging and the lints it can fail are checked (v0.3, D138)."""
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
