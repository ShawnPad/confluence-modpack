"""v0.3 bypass closures (spec §7; plan Task 8): the Unobtainium 5x chain (X2.2, D125), the six ore/raw smelting removals
(D112c), the tier-ore block tags (D112a, D112b) and the Drygmy blacklist (X3.4, D124).

The KubeJS scripts run in node through tools/tests/run_server_scripts.js with recording stand-ins, so these tests need no
server boot. They pin what the scripts ask KubeJS to do; the boot-time proof that KubeJS did it is tools/check_recipes.py
and the tags.json counts in the plan's Verify step. node runs V8, not the pack's Rhino, so the load proof is
tools/server_boot.sh. node must be on PATH: the `node` fixture asserts it, so these tests run rather than skip.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tools" / "tests" / "run_server_scripts.js"
DRYGMY = ROOT / "kubejs" / "data" / "ars_nouveau" / "tags" / "entity_type" / "drygmy_blacklist.json"

UNOB_CHAIN = [f"allthemodium:processing/unobtainium/slurry/dirty/{s}" for s in ("from_ore", "from_raw_ore", "from_raw_block")]
SMELTING = [f"allthemodium:{m}_ingot_from_{s}_smelting" for s in ("ore", "raw") for m in ("allthemodium", "vibranium", "unobtainium")]
NINE = [
    "cataclysm:needs_monstrosity_tool", "cataclysm:needs_black_steel_tool", "undergarden:incorrect_for_forgotten_tool",
    "deeperdarker:incorrect_for_resonarium_tool", "deeperdarker:incorrect_for_warden_tool", "mekanism:incorrect_for_disassembler",
    "mekanism:incorrect_for_meka_tool", "mysticalagriculture:incorrect_for_supremium_tool",
    "mysticalagriculture:incorrect_for_awakened_supremium_tool",
]
NEEDS = ["#c:needs_allthemodium_tool", "#c:needs_vibranium_tool", "#c:needs_unobtainium_tool", "#c:needs_allthemodiumalloy_tool"]
ORES = ["allthemodium:allthemodium_ore", "allthemodium:allthemodium_slate_ore", "allthemodium:vibranium_ore",
        "allthemodium:other_vibranium_ore", "allthemodium:unobtainium_ore"]
IMMUNE = ["minecraft:wither_immune", "cataclysm:ignis_immune", "cataclysm:maledictus_immune", "cataclysm:scylla_immune",
          "cataclysm:netherite_monstrosity_immune"]


@pytest.fixture(scope="module")
def node():
    path = shutil.which("node")
    assert path, "node is not on PATH; `node --version` must print a version (v22.3.0 was used when this test was written)"
    return path


def run(node, *scripts):
    res = subprocess.run([node, str(HARNESS), *scripts], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


@pytest.fixture(scope="module")
def bypass(node):
    return run(node, "kubejs/server_scripts/bypass.js")


@pytest.fixture(scope="module")
def events(node):
    return run(node, "kubejs/server_scripts/events.js")


def block_adds(result):
    adds = {}
    for row in result["blockTags"]:
        adds.setdefault(row["tag"], []).extend(row["values"])
    return adds


def test_bypass_loads_and_runs_cleanly(bypass):
    assert bypass["handlers"]["recipes"] == 1 and bypass["errors"] == []


def test_unobtainium_chain_needs_an_etrium_ingot(bypass):
    assert set(UNOB_CHAIN) <= set(bypass["removed"])
    etrium = {"count": 1, "item": "ad_astra:etrium_ingot"}
    crystal = "allthemodium:unobtainium_crystal"
    got = {c["id"]: c["json"] for c in bypass["custom"] if c["id"].startswith("confluence:bypass/unobtainium_")}
    assert got == {
        "confluence:bypass/unobtainium_crystal_from_ore": {
            "type": "mekanism:combining", "main_input": {"count": 1, "tag": "c:ores/unobtainium"},
            "extra_input": etrium, "output": {"count": 5, "id": crystal}},
        "confluence:bypass/unobtainium_crystal_from_raw_ore": {
            "type": "mekanism:combining", "main_input": {"count": 3, "tag": "c:raw_materials/unobtainium"},
            "extra_input": etrium, "output": {"count": 10, "id": crystal}},
        "confluence:bypass/unobtainium_crystal_from_raw_block": {
            "type": "mekanism:combining", "main_input": {"count": 1, "tag": "c:storage_blocks/raw_unobtainium"},
            "extra_input": etrium, "output": {"count": 30, "id": crystal}},
    }


def test_ore_and_raw_smelting_removed_blasting_and_dust_kept(bypass):
    removed = set(bypass["removed"])
    assert set(SMELTING) <= removed
    assert [r for r in removed if "blasting" in r or "from_dust" in r] == []


def test_block_tag_handler_registered_and_runs(events):
    assert events["handlers"]["blockTags"] == 1
    assert [e for e in events["errors"] if "block tags handler" in e] == [], events["errors"]


def test_nine_empty_deny_tags_get_atms_netherite_set(events):
    adds = block_adds(events)
    assert {t: sorted(adds.get(t, [])) for t in NINE} == {t: sorted(NEEDS) for t in NINE}


def test_vanilla_netherite_deny_tag_is_not_nested(events):
    """It holds #undergarden:needs_forgotten_tool, so nesting it would stop the Forgotten pickaxe mining its own tier."""
    adds = block_adds(events)
    assert "minecraft:incorrect_for_netherite_tool" not in adds
    assert not any("#minecraft:incorrect_for_netherite_tool" in values for values in adds.values())


def test_tier_ores_immune_to_the_wither_and_four_cataclysm_bosses(events):
    adds = block_adds(events)
    assert {t: sorted(adds.get(t, [])) for t in IMMUNE} == {t: sorted(ORES) for t in IMMUNE}


def test_drygmy_blacklist_has_the_v03_bosses():
    data = json.loads(DRYGMY.read_text())
    ids = [v["id"] if isinstance(v, dict) else v for v in data["values"]]
    assert data["replace"] is False
    assert {"allthemodium:piglich", "irons_spellbooks:fire_boss", "irons_spellbooks:dead_king"} <= set(ids)
    assert "ars_nouveau:wilden_boss" not in ids   # D124: the Tribute is a code drop a Drygmy cannot produce
    assert len(ids) == len(set(ids)) == 12
