"""The dev-only route exports (v1.0 plan Task 13; spec §6.1 inputs, §7.2): routeexport.js and tagcheck.js's block and fluid
member files. The source tests pin the scripts' shape; the data tests read the files the last dev boot wrote.

The data tests follow test_dump_bodies.py's rules: they skip only when the dump (recipes.json) does not exist (no server has
been booted from this clone), fail with "stale dump: boot first" when a boot input is newer than the dump, and otherwise fail
when a route export is missing, empty or disagrees with tags.json. $CONFLUENCE_EXPORTED_DIR points them at another exported/
directory (a doctored copy, for a red run)."""
import json
import os
import re
from pathlib import Path

import pytest

from kjs import ROOT

ROUTE = ROOT / "kubejs" / "server_scripts" / "routeexport.js"
TAGCHECK = ROOT / "kubejs" / "server_scripts" / "tagcheck.js"
EXPORTED_ENV = "CONFLUENCE_EXPORTED_DIR"
EXPORTED = Path(os.environ[EXPORTED_ENV]).resolve() if os.environ.get(EXPORTED_ENV) else (
    ROOT / ".run" / "server" / "kubejs" / "exported")
CROP_KEYS = ["biomes", "crux", "enabled", "essence", "id", "material", "seeds"]


def test_routeexport_is_behind_the_dev_flag():
    text = ROUTE.read_text()
    assert "if (!CONFLUENCE_DEV) console.log('confluence routeexport: skipped (confluence.dev unset)')\n" \
           "else ServerEvents.loaded(event => {" in text
    assert len(re.findall(r"^(?:else )?ServerEvents\.", text, re.M)) == 1
    assert "JsonIO.write('kubejs/exported/ma_crops.json', { crops: out })" in text


def test_tagcheck_writes_block_and_fluid_members():
    text = TAGCHECK.read_text()
    assert "const TAGCHECK_ROUTE_REGISTRIES = { 'minecraft:block': true, 'minecraft:fluid': true, 'mekanism:chemical': true }" in text
    assert "JsonIO.write('kubejs/exported/block_tag_members.json'" in text
    assert "JsonIO.write('kubejs/exported/fluid_tag_members.json'" in text


def test_production_expects_the_routeexport_skip_line():
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    from ptero_wait import SKIP_LINES
    assert "confluence routeexport: skipped (confluence.dev unset)" in SKIP_LINES


# ---- data: the files the last dev boot wrote ----

@pytest.fixture(scope="module")
def exported():
    # Imported here, as test_tier7.py does: test_dump_bodies imports test_tier7, which a top-level import here need not pull in.
    from test_dump_bodies import newest_kubejs_file, staleness
    dump = EXPORTED / "recipes.json"
    if not dump.is_file():
        pytest.skip(f"{dump} does not exist (no server has been booted from this clone)")
    stale = staleness(dump.stat().st_mtime, newest_kubejs_file())
    if stale:
        pytest.fail(stale)
    return EXPORTED


def load(directory, name):
    path = directory / name
    assert path.is_file(), f"{path} is missing: the dev boot did not write it (routeexport.js / tagcheck.js)"
    return json.loads(path.read_text())


def test_ma_crops_export(exported):
    doc = load(exported, "ma_crops.json")
    assert isinstance(doc, dict) and list(doc) == ["crops"], f"ma_crops.json top level is {type(doc).__name__} {list(doc)[:5]}"
    crops = doc["crops"]
    assert len(crops) >= 1, "ma_crops.json holds no crops"
    bad = [c.get("id") for c in crops if sorted(c) != CROP_KEYS]
    assert not bad, f"crops without exactly the keys {CROP_KEYS}: {bad[:5]}"
    ids = [c["id"] for c in crops]
    assert len(ids) == len(set(ids)), f"duplicate crop ids: {sorted({i for i in ids if ids.count(i) > 1})[:5]}"
    assert any(i.startswith("mysticalagradditions:") for i in ids), "no Mystical Agradditions crop in the registry export"
    assert not [c["id"] for c in crops if c["crux"] == "minecraft:air"], "a crux exported as minecraft:air, not null"


@pytest.mark.parametrize("name, registries", [
    ("block_tag_members.json", ["minecraft:block"]),
    ("fluid_tag_members.json", ["minecraft:fluid", "mekanism:chemical"]),
])
def test_route_member_export_matches_tags_json(exported, name, registries):
    doc = load(exported, name)
    tags = load(exported, "tags.json")
    assert sorted(doc) == sorted(registries), f"{name} registries are {sorted(doc)}, expected {registries}"
    for reg in registries:
        assert doc[reg], f"{name} has no {reg} tags"
        wrong = [f"{t}: {len(ms)} members, tags.json counts {tags[reg].get(t)}" for t, ms in sorted(doc[reg].items())
                 if len(ms) != tags[reg].get(t)]
        missing = sorted(set(tags[reg]) - set(doc[reg]))
        assert not wrong and not missing, f"{name} {reg}: {wrong[:5]} missing {missing[:5]}"
