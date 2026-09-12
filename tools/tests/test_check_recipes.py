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
