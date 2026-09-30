import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_recipes import run_checks

DUMP = [
    {"id": "confluence:tier1/flint_and_steel", "type": "minecraft:crafting_shaped", "output": "minecraft:flint_and_steel"},
    {"id": "minecraft:stone", "type": "minecraft:smelting", "output": "minecraft:stone"},
    {"id": "modx:stone_dup", "type": "minecraft:smelting", "output": "minecraft:stone"},
]

def test_all_good():
    r = run_checks(DUMP, gates=["confluence:tier1/flint_and_steel"], removed=["minecraft:flint_and_steel"])
    assert r.missing == [] and r.still_present == []

def test_missing_and_present():
    r = run_checks(DUMP, gates=["confluence:tier1/nope"], removed=["minecraft:stone"])
    assert r.missing == ["confluence:tier1/nope"]
    assert r.still_present == ["minecraft:stone"]

def test_duplicates_listed():
    r = run_checks(DUMP, gates=[], removed=[])
    assert ("minecraft:smelting", "minecraft:stone") in r.duplicates

def test_rows_without_a_json_body_fail_and_are_named(tmp_path, monkeypatch, capsys):
    """v0.3: dump.js gives every row its recipe JSON (the column later tasks read). A missing or empty `json` means the
    dump broke silently -- a Rhino `const` inside `try` once emptied all 18880 rows while this check stayed green -- so
    exit 1, naming the count and up to 10 ids. A clean export prints nothing new."""
    import check_recipes
    manifest = tmp_path / "gates.yaml"
    manifest.write_text("gates:\n  - confluence:tier1/flint_and_steel\nremoved:\n  - minecraft:flint_and_steel\n")
    dump = tmp_path / "recipes.json"
    monkeypatch.setattr(check_recipes, "DUMP", dump)
    monkeypatch.setattr(check_recipes, "MANIFEST", manifest)
    rows = [dict(r, json=json.dumps({"type": r["type"]})) for r in DUMP]
    dump.write_text(json.dumps(rows))
    assert check_recipes.main() == 0
    clean = capsys.readouterr().out.splitlines()
    assert clean[0] == "gates: 1 expected, 0 missing, 0 removed-still-present"
    assert not any("json" in line.lower() for line in clean)
    rows[0]["json"] = ""
    del rows[2]["json"]
    rows += [{"id": f"modx:r{i:02}", "type": "minecraft:smelting", "output": "", "json": ""} for i in range(11)]
    dump.write_text(json.dumps(rows))
    assert check_recipes.main() == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "gates: 1 expected, 0 missing, 0 removed-still-present"
    bad = [line for line in out if "NO JSON" in line]
    assert len(bad) == 1 and "13 rows" in bad[0]
    assert "confluence:tier1/flint_and_steel" in bad[0] and "modx:stone_dup" in bad[0]
    assert sum(bad[0].count(f"modx:r{i:02}") for i in range(11)) == 8   # 10 named: the 2 above + the first 8 of 11
