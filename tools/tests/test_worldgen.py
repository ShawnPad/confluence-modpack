"""worldgen.js emits the worldgen JSON of spec §4.2 and the v0.3 spec §8 (v0.3 Task 3).

tools/tests/worldgen_harness.js runs lib/ids.js and worldgen.js under node in one shared scope, as KubeJS does, and hands
back every file the generateData handler writes. So these tests read the exact configured_feature / placed_feature /
biome_modifier objects the server loads. Whether a row actually places ore is tools/probe_worldgen.sh's job
(research/phase7-v0.3-test-log.md §1).
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = Path(__file__).resolve().parent / "worldgen_harness.js"

# allthemodium-3.0.1_mc_1.21.1.jar!data/allthemodium/dimension/the_other.json biome_source, in file order (OD §1).
OTHER_BIOMES = [
    "allthemodium:soul_sand_valley", "allthemodium:the_other", "allthemodium:desert", "allthemodium:basalt_deltas",
    "allthemodium:warped_forest", "allthemodium:desert_hills", "allthemodium:crimson_forest",
]
FLOOR_SCAN = {
    "type": "minecraft:environment_scan", "direction_of_search": "down",
    "target_condition": {"type": "minecraft:has_sturdy_face", "direction": "up"},
    "allowed_search_condition": {"type": "minecraft:matching_blocks", "blocks": ["minecraft:air", "minecraft:cave_air"]},
    "max_steps": 12,
}
V02_ROWS = {   # path -> (modifier biomes, number of ore targets); the v0.1/v0.2 rows must come out as they shipped
    "allthemodium_twilight": ("#twilightforest:in_twilight_forest", 2),
    "uraninite_mining": ("allthemodium:mining", 2),
    "uraninite_poor_mining": ("allthemodium:mining", 2),
    "uraninite_dense_mining": ("allthemodium:mining", 2),
    "vibranium_undergarden": ("#undergarden:is_undergarden", 3),
}


@pytest.fixture(scope="module")
def gen():
    node = shutil.which("node")
    assert node, "node is not on PATH: tools/tests/test_worldgen.py runs worldgen.js under node"
    out = subprocess.run([node, str(HARNESS), str(ROOT / "kubejs")], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr   # a script that throws under node would also throw in KubeJS
    return json.loads(out.stdout)


def files_for(gen, path):
    f = gen["files"]
    return (f[f"confluence:worldgen/configured_feature/{path}.json"], f[f"confluence:worldgen/placed_feature/{path}.json"],
            f[f"confluence:neoforge/biome_modifier/{path}.json"])


def ore(tag, block):
    return {"target": {"predicate_type": "minecraft:tag_match", "tag": tag}, "state": {"Name": block}}


def test_eight_rows_three_files_each(gen):
    assert gen["phases"] == ["after_mods"]
    assert gen["log"] == ["confluence worldgen: 8 placements"]
    assert len(gen["files"]) == 24
    for path in list(V02_ROWS) + ["unobtainium_other", "mercury_ore", "glacio_ore"]:
        files_for(gen, path)   # KeyError if a row is missing


def test_unobtainium_other_row(gen):
    configured, placed, modifier = files_for(gen, "unobtainium_other")
    assert configured == {"type": "minecraft:ore", "config": {
        "size": 4, "discard_chance_on_air_exposure": 0,
        "targets": [ore("allthemodium:ancient_stone", "allthemodium:unobtainium_ore")]}}
    assert placed["feature"] == "confluence:unobtainium_other"
    count, rest = placed["placement"][0], placed["placement"][1:]
    assert count["type"] == "minecraft:count" and isinstance(count["count"], int) and count["count"] >= 1   # tuned by probe
    assert rest == [
        {"type": "minecraft:in_square"},
        {"type": "minecraft:height_range", "height": {"type": "minecraft:uniform",
                                                      "min_inclusive": {"absolute": 8}, "max_inclusive": {"absolute": 128}}},
        FLOOR_SCAN,
        {"type": "minecraft:biome"},
    ]
    assert modifier == {"type": "neoforge:add_features", "biomes": OTHER_BIOMES,
                        "features": ["confluence:unobtainium_other"], "step": "underground_ores"}


@pytest.mark.parametrize("path, biomes, targets, lo, hi", [
    ("mercury_ore", ["ad_astra:mercury_deltas"],
     [ore("ad_astra:mercury_stone_replaceables", "kubejs:mercury_ore")], -32, 96),
    ("glacio_ore", ["ad_astra:glacio_ice_peaks", "ad_astra:glacio_snowy_barrens"],
     [ore("ad_astra:glacio_stone_replaceables", "kubejs:glacio_ore"),
      ore("minecraft:deepslate_ore_replaceables", "kubejs:glacio_ore")], -48, 64),
])
def test_planet_rows(gen, path, biomes, targets, lo, hi):
    configured, placed, modifier = files_for(gen, path)
    assert configured == {"type": "minecraft:ore", "config": {
        "size": 3, "discard_chance_on_air_exposure": 0.5, "targets": targets}}
    assert placed == {"feature": f"confluence:{path}", "placement": [
        {"type": "minecraft:count", "count": 4},
        {"type": "minecraft:in_square"},
        {"type": "minecraft:height_range", "height": {"type": "minecraft:trapezoid",
                                                      "min_inclusive": {"absolute": lo}, "max_inclusive": {"absolute": hi}}},
        {"type": "minecraft:biome"},
    ]}
    assert modifier == {"type": "neoforge:add_features", "biomes": biomes,
                        "features": [f"confluence:{path}"], "step": "underground_ores"}


def test_v02_rows_keep_discard_zero_and_their_biomes(gen):
    for path, (biomes, n_targets) in V02_ROWS.items():
        configured, _, modifier = files_for(gen, path)
        assert configured["config"]["discard_chance_on_air_exposure"] == 0, path
        assert len(configured["config"]["targets"]) == n_targets, path
        assert modifier["biomes"] == biomes, path
