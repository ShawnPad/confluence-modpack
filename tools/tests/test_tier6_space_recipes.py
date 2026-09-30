"""Pin the Space recipes in kubejs/server_scripts/tiers/tier6.js (v0.3 spec §6; plan Task 6).

node evaluates lib/ids.js, lib/gates.js and tiers/tier6.js as one script, the way KubeJS 2101 runs server
scripts (one shared scope). A stub `event` records every gate call. The expected values are the spec §6
rows, with ids read from the jars when the plan was written (see the comments in tier6.js). This test
catches an undefined IDS key or a wrong slot before any boot: JSON.stringify drops an undefined object
value, so the exact comparison fails. It cannot prove the recipes load. node runs V8, not the pack's Rhino,
so this test pins the recorded recipes, not that tier6.js loads in KubeJS; tools/tests/test_rhino_hazards.py
lints the one known Rhino trap. tools/server_boot.sh (its KubeJS ERROR check, and its check for "Parsing
error loading recipe" in logs/latest.log) and the "with 0 failed recipes" summary line prove the recipes
load; tools/check_recipes.py proves the ids are added and removed. check_recipes alone is not enough:
dump.js writes recipes.json inside ServerEvents.recipes, before the recipe codecs run, so a recipe that
later fails to parse is still listed.
(kubejs-neoforge-2101.7.2-build.377.jar: RecipesKubeEvent.post runs postEvent, the handlers, then
applyChanges; a codec failure reaches RecipeManagerMixin.catchFailingRecipes -> handleFailedRecipe, which
logs "Error parsing recipe %s" as an ERROR when DevProperties log_erroring_recipes is set, default true, and
adds one to the failed count that finishEvent prints.)
The dump check in plan Task 6 Step 6 imports SHAPED and CUSTOM from this module, so these two dicts are
the only copy of the expectations.
"""
import json
import os
import shutil
import subprocess
import zipfile
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not on PATH")

HARNESS = r"""
const fs = require('fs'), vm = require('vm'), path = require('path')
const dir = path.join(process.env.PACK_ROOT, 'kubejs', 'server_scripts')
const src = ['lib/ids.js', 'lib/gates.js', 'tiers/tier6.js'].map(f => fs.readFileSync(path.join(dir, f), 'utf8')).join('\n;\n')
const handlers = []
const ctx = { ServerEvents: { recipes: fn => handlers.push(fn) }, Item: { of: x => x }, console: console }
vm.createContext(ctx)
vm.runInContext(src, ctx)
const calls = []
const event = {
  shaped: (output, pattern, keys) => ({ id: id => calls.push({ kind: 'shaped', id: id, output: output, pattern: pattern, keys: keys }) }),
  shapeless: (output, inputs) => ({ id: id => calls.push({ kind: 'shapeless', id: id, output: output, inputs: inputs }) }),
  remove: filter => calls.push({ kind: 'remove', filter: filter }),
  custom: json => ({ id: id => calls.push({ kind: 'custom', id: id, json: json }) }),
}
handlers.forEach(h => h(event))
process.stdout.write(JSON.stringify(calls))
"""

PLATE = "#ad_astra:steel_plates"
ULTIMATE = "mekanism:ultimate_control_circuit"

# recipe id -> (output, pattern, keys). Defaults: adastra-1.21.1-1.16.25-neoforge.jar!data/ad_astra/recipe/<item>.json.
SHAPED = {
    # D6.1: default |#| / TCT / #B#; rods and torches -> circuit, Unob-ATM alloy, Unobtainium block, Unrealium.
    "confluence:tier6/nasa_workbench": ("ad_astra:nasa_workbench", ["X#Y", "ZCW", "#B#"], {
        "X": ULTIMATE, "Y": "allthemodium:unobtainium_allthemodium_alloy_ingot", "Z": "#c:storage_blocks/unobtainium",
        "W": "#c:ingots/unrealium", "#": PLATE, "C": "minecraft:crafting_table", "B": "#ad_astra:steel_blocks"}),
    # D6.3: default '# #' / TOT / #W#; elytra in the empty top-middle (D107).
    "confluence:tier6/space_suit": ("ad_astra:space_suit", ["#E#", "TOT", "#W#"], {
        "#": PLATE, "E": "minecraft:elytra", "T": "ad_astra:gas_tank", "O": "ad_astra:oxygen_gear", "W": "#minecraft:wool"}),
    # D6.3: default #F# / G|G / #R#; electric pump for the redstone block.
    "confluence:tier6/oxygen_loader": ("ad_astra:oxygen_loader", ["#F#", "G|G", "#P#"], {
        "#": PLATE, "F": "ad_astra:fan", "G": "ad_astra:gas_tank", "|": "minecraft:lightning_rod", "P": "mekanism:electric_pump"}),
    # T6.1: default ### / BFB / ###; the six plates -> four essences, circuit, Vib-ATM alloy.
    "confluence:tier6/fuel_refinery": ("ad_astra:fuel_refinery", ["aCe", "BFB", "wVf"], {
        "a": "ars_nouveau:air_essence", "e": "ars_nouveau:earth_essence", "w": "ars_nouveau:water_essence",
        "f": "ars_nouveau:fire_essence", "C": ULTIMATE, "V": "allthemodium:vibranium_allthemodium_alloy_ingot",
        "B": "minecraft:bucket", "F": "minecraft:furnace"}),
    # T6.2 (D118): default ### / #E# / ' F '; nitro for the top-middle plate, circuit and Unob-Vib alloy in the empty corners.
    "confluence:tier6/steel_engine": ("ad_astra:steel_engine", ["#N#", "#E#", "CFA"], {
        "#": PLATE, "N": "powah:crystal_nitro", "E": "ad_astra:engine_frame", "F": "ad_astra:fan", "C": ULTIMATE,
        "A": "allthemodium:unobtainium_vibranium_alloy_ingot"}),
}

CUSTOM = {
    # D6.9 (D119): ad_astra:alloying, fields as recipe/alloying/steel_ingot_from_alloying_iron_ingot_and_barrier.json.
    "confluence:tier6/etrium_ingot": {
        "type": "ad_astra:alloying", "cookingtime": 200, "energy": 40,
        "ingredients": [{"tag": "c:ingots/desh"}, {"tag": "c:ingots/ostrum"}, {"tag": "c:ingots/calorite"}, {"item": "ad_astra:ice_shard"}],
        "result": {"count": 1, "id": "ad_astra:etrium_ingot"}},
    # D6.9: ad_astra:compressing, fields and numbers as recipe/compressing/desh_plate_from_compressing_desh_ingots.json.
    "confluence:tier6/etrium_plate": {
        "type": "ad_astra:compressing", "cookingtime": 100, "energy": 20,
        "ingredient": {"item": "ad_astra:etrium_ingot"}, "result": {"count": 1, "id": "ad_astra:etrium_plate"}},
    # M6.1 (D120): Ars apparatus, the six keys of ars_nouveau-1.21.1-5.13.1.jar!data/ars_nouveau/recipe/planarium.json.
    "confluence:tier6/astral_focus": {
        "type": "ars_nouveau:enchanting_apparatus", "keepNbtOfReagent": False, "sourceCost": 0,
        "reagent": {"item": "ad_astra:etrium_ingot"},
        "pedestalItems": [{"item": "irons_spellbooks:divine_soulshard"}, {"item": "kubejs:mercury_shard"}, {"item": "kubejs:glacio_shard"}],
        "result": {"count": 1, "id": "kubejs:astral_focus"}},
}

MODS = ROOT / ".run" / "server" / "mods"
ADASTRA_JAR = MODS / "adastra-1.21.1-1.16.25-neoforge.jar"
EMPTY = None  # a ' ' cell of a pattern

# Spec §6's slot changes to each jar default, and nothing else: recipe id -> {(row, col): (default cell, our cell)}. A cell is
# '#tag', an item id or EMPTY. The defaults are ADASTRA_JAR!data/ad_astra/recipe/<item>.json (AA §1.1–1.4). The jar is pinned;
# a new Ad Astra version means re-reading the five defaults and this table by hand.
SLOT_CHANGES = {
    # D6.1: the two iron rods (top corners) and the two redstone torches (middle-row ends) become the four gate items.
    "confluence:tier6/nasa_workbench": {
        (0, 0): ("#ad_astra:iron_rods", ULTIMATE),
        (0, 2): ("#ad_astra:iron_rods", "allthemodium:unobtainium_allthemodium_alloy_ingot"),
        (1, 0): ("minecraft:redstone_torch", "#c:storage_blocks/unobtainium"),
        (1, 2): ("minecraft:redstone_torch", "#c:ingots/unrealium")},
    # D6.3: the elytra fills the empty top-middle (D107).
    "confluence:tier6/space_suit": {
        (0, 1): (EMPTY, "minecraft:elytra")},
    # D6.3: the electric pump replaces the redstone block (bottom-middle).
    "confluence:tier6/oxygen_loader": {
        (2, 1): ("minecraft:redstone_block", "mekanism:electric_pump")},
    # T6.1: the six steel plates (top and bottom rows) become the four essences, the circuit and the Vib-ATM alloy.
    "confluence:tier6/fuel_refinery": {
        (0, 0): (PLATE, "ars_nouveau:air_essence"), (0, 1): (PLATE, ULTIMATE), (0, 2): (PLATE, "ars_nouveau:earth_essence"),
        (2, 0): (PLATE, "ars_nouveau:water_essence"), (2, 1): (PLATE, "allthemodium:vibranium_allthemodium_alloy_ingot"),
        (2, 2): (PLATE, "ars_nouveau:fire_essence")},
    # T6.2 (D118): nitro for the top-middle plate; the circuit and the Unob-Vib alloy in the two empty bottom corners (D107).
    "confluence:tier6/steel_engine": {
        (0, 1): (PLATE, "powah:crystal_nitro"),
        (2, 0): (EMPTY, ULTIMATE),
        (2, 2): (EMPTY, "allthemodium:unobtainium_vibranium_alloy_ingot")},
}


@lru_cache(maxsize=None)
def recorded() -> str:
    out = subprocess.run([NODE, "-e", HARNESS], capture_output=True, text=True, env={**os.environ, "PACK_ROOT": str(ROOT)})
    assert out.returncode == 0, out.stderr
    return out.stdout


def calls(kind: str) -> list:
    return [c for c in json.loads(recorded()) if c["kind"] == kind]


def test_space_shaped_rows():
    shaped = {c["id"]: c for c in calls("shaped")}
    for rid, (output, pattern, keys) in SHAPED.items():
        assert rid in shaped, rid
        c = shaped[rid]
        assert (c["output"], c["pattern"], c["keys"]) == (output, pattern, keys), rid


def test_space_removals_are_the_five_defaults_only():
    filters = [c["filter"] for c in calls("remove")]
    removed_outputs = sorted(f["output"] for f in filters if isinstance(f.get("output"), str) and f["output"].startswith("ad_astra:"))
    assert removed_outputs == sorted(v[0] for v in SHAPED.values())
    # D6.2 / D118: rockets, the launch pad and the desh, ostrum and calorite engines keep their default recipes.
    assert not [f for f in filters if isinstance(f.get("id"), str) and f["id"].startswith("ad_astra:")]
    # Etrium and the Astral Focus have no default to remove (AA §2.3; kubejs:astral_focus is a pack item).
    assert not [f for f in filters if f.get("output") in ("ad_astra:etrium_ingot", "ad_astra:etrium_plate", "kubejs:astral_focus")]


def test_space_custom_json():
    custom = {c["id"]: c["json"] for c in calls("custom")}
    for rid, body in CUSTOM.items():
        assert custom.get(rid) == body, rid


def ingredient(v):
    """A key value as tier6.js writes it ('#tag' or an item id) or as recipe JSON ({"tag": ...} or {"item": ...})."""
    if isinstance(v, dict):
        assert set(v) in ({"item"}, {"tag"}), v
        return "#" + v["tag"] if "tag" in v else v["item"]
    return v


def grid(pattern, key):
    """{(row, col): cell} of a 3x3 shaped pattern. Every symbol in the pattern is in the key and every key symbol is used."""
    assert len(pattern) == 3 and all(len(row) == 3 for row in pattern), pattern
    assert set("".join(pattern)) - {" "} == set(key), (pattern, sorted(key))
    return {(r, c): EMPTY if ch == " " else ingredient(key[ch]) for r, row in enumerate(pattern) for c, ch in enumerate(row)}


@pytest.mark.parametrize("rid", list(SLOT_CHANGES))
def test_space_machine_is_the_jar_default_plus_spec_slots(rid):
    """Each of the five machines tier6.js records is Ad Astra's jar default with exactly the SLOT_CHANGES cells changed. It
    fails when Ad Astra moves the id (remove-by-output would then miss it, or a second recipe appears) or changes the default
    (ours would silently drop the change), and when tier6.js changes a slot spec §6 keeps."""
    if not MODS.is_dir():
        pytest.skip(f"{MODS} does not exist (no server has been booted from this clone)")
    # 'adastra-*.jar' needs the hyphen right after the mod id, so an add-on jar with a longer name does not match.
    found = sorted(MODS.glob("adastra-*.jar"))
    assert found == [ADASTRA_JAR], f"SLOT_CHANGES were read against {ADASTRA_JAR.name}; {MODS} holds {[p.name for p in found]}"
    output = SHAPED[rid][0]
    ns, name = output.split(":")
    entry = f"data/{ns}/recipe/{name}.json"
    with zipfile.ZipFile(ADASTRA_JAR) as jar:
        try:
            default = json.loads(jar.read(entry))
        except KeyError:
            pytest.fail(f"id moved: {ADASTRA_JAR.name} has no {entry}, so SLOT_CHANGES no longer describe Ad Astra's default")
    assert default["type"] == "minecraft:crafting_shaped" and default["result"] == {"count": 1, "id": output}, default
    ours = {c["id"]: c for c in calls("shaped")}.get(rid)
    assert ours is not None and ours["output"] == output, (rid, ours)
    before, after = grid(default["pattern"], default["key"]), grid(ours["pattern"], ours["keys"])
    # KubeJS's shrink trims an empty edge row or column; ours has none, so the grid it loads is this one.
    assert all(any(after[r, c] for c in range(3)) and any(after[c, r] for c in range(3)) for r in range(3)), ours["pattern"]
    changed = {cell: (before[cell], after[cell]) for cell in before if before[cell] != after[cell]}
    assert changed == SLOT_CHANGES[rid], f"{rid}: cells that differ from {ADASTRA_JAR.name}'s default, as (default, ours)"
