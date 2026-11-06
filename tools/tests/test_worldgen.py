"""worldgen.js emits the worldgen JSON of spec §4.2 and the v0.3 spec §8 (v0.3 Task 3).

tools/tests/worldgen_harness.js runs lib/ids.js and worldgen.js under node in one shared scope, as KubeJS does, and hands
back every file the generateData handler writes. So these tests read the exact configured_feature / placed_feature /
biome_modifier objects the server loads. They run under V8, not Rhino: they pin the JSON, not that the file loads in
KubeJS (tools/server_boot.sh is that proof; tools/tests/test_rhino_hazards.py lints one known Rhino trap). Whether a row
actually places ore is tools/probe_worldgen.sh's job (research/phase7-v0.3-test-log.md §1).
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = Path(__file__).resolve().parent / "worldgen_harness.js"
WORLDGEN = ROOT / "kubejs" / "server_scripts" / "worldgen.js"
# The 15 files the five v0.1/v0.2 rows emitted before v0.3 Task 3: the harness output at pack 8f1b187, which is the same JSON
# the harness gets from release 0.2.1 (e89783a). v0.3 must leave them untouched.
GOLDEN_V02 = Path(__file__).resolve().parent / "golden" / "worldgen_v02.json"

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
V02_PATHS = ["allthemodium_twilight", "uraninite_mining", "uraninite_poor_mining", "uraninite_dense_mining",
             "vibranium_undergarden"]
V03_PATHS = ["unobtainium_other", "mercury_ore", "glacio_ore"]


def run_harness(kubejs):
    node = shutil.which("node")
    assert node, "node is not on PATH: tools/tests/test_worldgen.py runs worldgen.js under node"
    return subprocess.run([node, str(HARNESS), str(kubejs)], capture_output=True, text=True, timeout=60)


@pytest.fixture(scope="module")
def gen():
    out = run_harness(ROOT / "kubejs")
    assert out.returncode == 0, out.stderr   # a script that throws under node would also throw in KubeJS
    return json.loads(out.stdout)


def file_ids(path):
    return [f"confluence:worldgen/configured_feature/{path}.json", f"confluence:worldgen/placed_feature/{path}.json",
            f"confluence:neoforge/biome_modifier/{path}.json"]


def files_for(gen, path):
    missing = [i for i in file_ids(path) if i not in gen["files"]]
    assert not missing, f"row {path}: worldgen.js emitted no {', '.join(missing)}"
    return tuple(gen["files"][i] for i in file_ids(path))


def ore(tag, block):
    return {"target": {"predicate_type": "minecraft:tag_match", "tag": tag}, "state": {"Name": block}}


def with_row(tmp_path, name, row):
    """A scratch kubejs/ holding lib/ids.js and worldgen.js with `row` (JS source) pushed onto PLACEMENTS after the table."""
    kubejs = tmp_path / name
    (kubejs / "server_scripts" / "lib").mkdir(parents=True)
    shutil.copy(ROOT / "kubejs" / "server_scripts" / "lib" / "ids.js", kubejs / "server_scripts" / "lib" / "ids.js")
    (kubejs / "server_scripts" / "worldgen.js").write_text(WORLDGEN.read_text() + f"\nPLACEMENTS.push({row})\n")
    return kubejs


def test_eight_rows_three_files_each_and_bad_rows_throw(gen, tmp_path):
    assert gen["phases"] == ["after_mods"]
    assert gen["log"] == ["confluence worldgen: 8 placements"]
    assert len(gen["files"]) == 24
    for path in V02_PATHS + V03_PATHS:
        files_for(gen, path)
    # The row check in worldgen.js's loop throws, naming the row, on a biomes list that is empty or holds a '#' entry, and
    # on an exposed (floor-scan) row with discard > 0. A valid injected row is the control: the injection itself is sound.
    base = ("feature: 'confluence:{p}', size: 3, count: 1, min: {{ absolute: 0 }}, max: {{ absolute: 8 }}, "
            "targets: [{{ tag: IDS.worldgen.deepslate, block: IDS.pack.glacioOre }}]")
    ok = run_harness(with_row(tmp_path, "ok", "{ path: 'ok_row', biomes: ['minecraft:plains'], exposed: true, "
                                              + base.format(p="ok_row") + " }"))
    assert ok.returncode == 0, ok.stderr
    assert json.loads(ok.stdout)["log"] == ["confluence worldgen: 9 placements"]
    for path, fields, why in [
        ("bad_empty_biomes", "biomes: [], exposed: false", "biomes"),
        ("bad_tag_in_list", "biomes: ['#minecraft:is_overworld'], exposed: false", "biomes"),
        ("bad_exposed_discard", "biomes: IDS.worldgen.otherBiomes, exposed: true, discard: 0.5", "exposed"),
    ]:
        out = run_harness(with_row(tmp_path, path, "{ path: '" + path + "', " + fields + ", " + base.format(p=path) + " }"))
        assert out.returncode != 0, f"{path}: the harness exited 0"
        assert f"worldgen: row {path}: {why}" in out.stderr, out.stderr


def test_unobtainium_other_row(gen):
    configured, placed, modifier = files_for(gen, "unobtainium_other")
    assert configured == {"type": "minecraft:ore", "config": {
        "size": 4, "discard_chance_on_air_exposure": 0,
        "targets": [ore("allthemodium:ancient_stone", "allthemodium:unobtainium_ore")]}}
    assert placed["feature"] == "confluence:unobtainium_other"
    count, rest = placed["placement"][0], placed["placement"][1:]
    assert count["type"] == "minecraft:count" and type(count["count"]) is int and count["count"] >= 1   # tuned by probe
    assert rest == [
        {"type": "minecraft:in_square"},
        {"type": "minecraft:height_range", "height": {"type": "minecraft:uniform",
                                                      "min_inclusive": {"absolute": 8}, "max_inclusive": {"absolute": 128}}},
        FLOOR_SCAN,
        {"type": "minecraft:biome"},
    ]
    assert modifier == {"type": "neoforge:add_features", "biomes": OTHER_BIOMES,
                        "features": ["confluence:unobtainium_other"], "step": "underground_ores"}
    # The row's comment records the probed count ("count N averages M ore/chunk in y 8..128 …"); it must be the one shipped.
    comments = re.sub(r"\s*\n\s*//\s*", " ", WORLDGEN.read_text())
    measured = re.findall(r"count (\d+) averages [\d.]+ ore/chunk in y 8\.\.128", comments)
    assert measured == [str(count["count"])], f"unobtainium_other comment says count {measured}, the row emits {count['count']}"


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


def test_v02_rows_match_golden(gen):
    golden = json.loads(GOLDEN_V02.read_text())
    assert sorted(golden) == sorted(i for p in V02_PATHS for i in file_ids(p)), "golden file lists the wrong 15 files"
    for file_id, body in golden.items():
        assert file_id in gen["files"], f"worldgen.js no longer emits {file_id}"
        assert gen["files"][file_id] == body, f"{file_id} differs from tools/tests/golden/worldgen_v02.json"
