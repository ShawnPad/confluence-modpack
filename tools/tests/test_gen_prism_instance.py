"""Build the Prism instance zip into a temp dir with a stubbed download and check its shape.

Expected values come from research/phase6-prism-instance.md (§1 keys, §2 uids, §3 layout,
§4 command + escaping) and the pack.toml URL from the plan's Task 7.
"""
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gen_prism_instance as g  # noqa: E402

EXPECTED_ENTRIES = {"instance.cfg", "mmc-pack.json", "minecraft/packwiz-installer-bootstrap.jar"}
STUB_JAR = b"PK\x03\x04stub-jar-bytes"
PACK_TOML_URL = "https://raw.githubusercontent.com/ShawnPad/confluence-modpack/main/pack.toml"


def _stub_download(dest_dir):
    p = Path(dest_dir) / g.BOOTSTRAP_JAR
    p.write_bytes(STUB_JAR)
    return p


def _build(tmp_path, monkeypatch) -> zipfile.ZipFile:
    monkeypatch.setattr(g, "download_bootstrap", _stub_download)
    out = tmp_path / "confluence-prism.zip"
    assert g.main([str(out)]) == 0
    assert out.is_file()
    return zipfile.ZipFile(out)


def test_zip_has_exactly_the_three_root_entries(tmp_path, monkeypatch):
    zf = _build(tmp_path, monkeypatch)
    # prism §3: root-level, no wrapper folder, nothing else
    assert set(zf.namelist()) == EXPECTED_ENTRIES
    assert zf.read("minecraft/packwiz-installer-bootstrap.jar") == STUB_JAR


def test_instance_cfg_keys(tmp_path, monkeypatch):
    cfg = _build(tmp_path, monkeypatch).read("instance.cfg").decode("ascii")
    lines = cfg.splitlines()
    assert lines[0] == "[General]"
    kv = dict(line.split("=", 1) for line in lines[1:] if line)
    assert kv["ConfigVersion"] == "1.3"
    assert kv["InstanceType"] == "OneSix"
    assert kv["name"] == "Confluence"
    assert kv["OverrideCommands"] == "true"
    # prism §4 command with prism §1 (issue #1134) backslash-escaped quotes, verbatim
    assert kv["PreLaunchCommand"] == (
        '\\"$INST_JAVA\\" -jar packwiz-installer-bootstrap.jar ' + PACK_TOML_URL
    )
    assert not kv["PreLaunchCommand"].startswith('"'), "quotes must be escaped, not bare"
    # prism §1 memory override: both allocations are gated by OverrideMemory and are plain integers (MiB)
    assert kv["OverrideMemory"] == "true"
    assert kv["MinMemAlloc"] == "2048"
    assert kv["MaxMemAlloc"] == "6144"
    assert int(kv["MinMemAlloc"]) < int(kv["MaxMemAlloc"])
    assert cfg.endswith("\n")


def test_mmc_pack_json_parses_with_both_component_uids(tmp_path, monkeypatch):
    doc = json.loads(_build(tmp_path, monkeypatch).read("mmc-pack.json"))
    assert doc["formatVersion"] == 1  # prism §2: must be the integer 1
    by_uid = {c["uid"]: c for c in doc["components"]}
    assert by_uid["net.minecraft"]["version"] == "1.21.1"
    assert by_uid["net.minecraft"]["important"] is True
    assert by_uid["net.neoforged"]["version"] == "21.1.250"
    assert by_uid["org.lwjgl3"] == {"dependencyOnly": True, "uid": "org.lwjgl3", "version": "3.3.3"}


def test_build_zip_writes_into_a_fresh_directory(tmp_path):
    jar = tmp_path / "stub.jar"
    jar.write_bytes(STUB_JAR)
    out = g.build_zip(tmp_path / "nested" / "dir" / "out.zip", jar)
    assert out.is_file()
    assert set(zipfile.ZipFile(out).namelist()) == EXPECTED_ENTRIES
