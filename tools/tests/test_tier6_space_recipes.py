"""Pin the Space recipes in kubejs/server_scripts/tiers/tier6.js (v0.3 spec §6; plan Task 6).

tools/tests/run_server_scripts.js (the shared runner, through kjs.run) loads lib/*.js and tiers/tier6.js into one shared
scope, the way KubeJS 2101 runs server scripts, and records every recipes-event call. The expected values are the spec §6
rows, with ids read from the jars when the plan was written (see the comments in tier6.js). This test catches an undefined
IDS key or a wrong slot before any boot: the runner writes an undefined value as '<undefined>', so the exact comparison
fails. It cannot prove the recipes load. node runs V8, not the pack's Rhino, so this test pins the recorded recipes, not
that tier6.js loads in KubeJS; tools/tests/test_rhino_hazards.py lints the known Rhino trap. tools/server_boot.sh (its
KubeJS ERROR check, and its check for "Parsing error loading recipe" in logs/latest.log) and the "with 0 failed recipes"
summary line prove the recipes load; tools/check_recipes.py proves the ids are added and removed. check_recipes alone is not
enough: dump.js writes recipes.json inside ServerEvents.recipes, before the recipe codecs run, so a recipe that later fails
to parse is still listed.
(kubejs-neoforge-2101.7.2-build.377.jar: RecipesKubeEvent.post runs postEvent, the handlers, then
applyChanges; a codec failure reaches RecipeManagerMixin.catchFailingRecipes -> handleFailedRecipe, which
logs "Error parsing recipe %s" as an ERROR when DevProperties log_erroring_recipes is set, default true, and
adds one to the failed count that finishEvent prints.)
The dump check in plan Task 6 Step 6 imports SHAPED and CUSTOM from this module and keeps no copy of its
own, so a slot fix touches tier6.js, SHAPED and SLOT_CHANGES, and a custom-recipe fix touches tier6.js and
CUSTOM. SOLE_MAKERS (each pinned output -> the one recipe id that may make it) is imported by test_recipe_scripts.py, which
checks it over every server script. The jar tests read adastra-1.21.1-1.16.25-neoforge.jar from .run/server/mods (kjs.pinned_jar,
which also checks mods/ad-astra.pw.toml): each machine must be that jar's default with exactly its SLOT_CHANGES cells changed,
and the Etrium recipes must keep the fields of Ad Astra's own alloying and compressing recipes. They skip only when
.run/server/mods does not exist, and fail on any other Ad Astra jar. node must be on PATH: kjs.run asserts it (plan Step 2:
this test must run, not skip). A tier6.js handler that throws, or that calls a recipes-event member the runner does not
model (replaceInput, smelting, ...), fails every test here through the `recorded` fixture, as the Task 6 harness did.
"""
import json
import zipfile

import pytest

from kjs import EMPTY, all_rows, cell_diff, grid, jar_json, one, one_maker, pinned_jar, run

TIER6 = "kubejs/server_scripts/tiers/tier6.js"

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

ADASTRA_JAR = "adastra-1.21.1-1.16.25-neoforge.jar"

# Spec §6's slot changes to each jar default, and nothing else: recipe id -> {(row, col): (default cell, our cell)}. A cell is
# '#tag', an item id or EMPTY. The defaults are ADASTRA_JAR's data/ad_astra/recipe/<item>.json (AA §1.1–1.4). The jar is pinned;
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


# Each output this file pins -> the only recipe ids that may make it, in any server script (test_recipe_scripts.py).
SOLE_MAKERS = {**{output: [rid] for rid, (output, _, _) in SHAPED.items()},
               **{body["result"]["id"]: [rid] for rid, body in CUSTOM.items()}}


@pytest.fixture(scope="module")
def recorded():
    recorded = run(TIER6)
    # The Task 6 harness stopped at the first error and knew no other event member; keep that strictness.
    assert recorded["errors"] == [] and recorded["other"] == [], (recorded["errors"], recorded["other"])
    return recorded


def calls(recorded, kind):
    """The recorded rows of one kind: 'shaped', 'shapeless', 'custom' (recipes), or 'remove' (the raw filters)."""
    if kind == "remove":
        return [f["filter"] for f in recorded["filters"]]
    return [r for r in all_rows(recorded) if r["kind"] == kind]


def test_space_shaped_rows(recorded):
    """The five machines' shaped rows (SHAPED), and one maker per machine: no other shaped, shapeless or custom recipe makes
    it (kjs.products: an output stack or id, or a custom recipe's json.result, json.output, an element of json.results, or
    any other result/output key), whether or not .id() was called on it. Nothing is chained on a machine's recipe."""
    for rid, (output, pattern, keys) in SHAPED.items():
        c = one(recorded, rid)   # exactly one recipe with this id, of any kind; nothing chained, no extra arguments
        assert c["kind"] == "shaped", (rid, c["kind"])
        # gate.shaped passes Item.of(output); the runner records that stack as {id, count} (plus `components` for an
        # 'id[...]' string), so a count or components change fails here.
        assert (c["output"], c["pattern"], c["key"]) == ({"id": output, "count": 1}, pattern, keys), rid
        # One maker per machine: a second recipe with this output would load beside ours.
        assert one_maker(recorded, output) == [rid], output


def test_space_removals_are_the_five_defaults_only(recorded):
    """Two filter shapes only: {output: <one of the five machines>} and {id: <a string id outside ad_astra:>} (plan Task 7's
    AE2 block removes by id). Anything else fails: a filter by type, mod or input, a regex or ad_astra: id, another output,
    or a combined filter. So D6.2 / D118 hold (rockets, the launch pad and the desh, ostrum and calorite engines keep their
    default recipes), and Etrium and the Astral Focus lose nothing (no default exists, AA §2.3)."""
    filters = calls(recorded, "remove")
    outputs = {v[0] for v in SHAPED.values()}

    def by_machine_output(f):
        return isinstance(f, dict) and set(f) == {"output"} and isinstance(f["output"], str) and f["output"] in outputs

    def by_other_id(f):
        return isinstance(f, dict) and set(f) == {"id"} and isinstance(f["id"], str) and not f["id"].startswith("ad_astra:")

    odd = [f for f in filters if not by_machine_output(f) and not by_other_id(f)]
    assert odd == [], f"filters other than {{output: <one of the five machines>}} or {{id: <id outside ad_astra:>}}: {odd}"
    assert sorted(f["output"] for f in filters if by_machine_output(f)) == sorted(outputs)


def test_space_custom_json(recorded):
    """Each CUSTOM body, made by exactly one event.custom call with that id and nothing chained on it."""
    for rid, body in CUSTOM.items():
        c = one(recorded, rid)   # exactly one recipe with this id, of any kind; nothing chained
        assert (c["kind"], c["json"]) == ("custom", body), rid


def adastra_jar():
    """ADASTRA_JAR, after kjs.pinned_jar's checks: mods/ad-astra.pw.toml ships it, the test skips only when no server has been
    booted from this clone, and any other Ad Astra jar fails ('adastra-*.jar' needs the hyphen right after the mod id, so an
    add-on jar with a longer name does not match)."""
    return pinned_jar("adastra-", ADASTRA_JAR, "ad-astra.pw.toml")


@pytest.mark.parametrize("rid", list(SLOT_CHANGES))
def test_space_machine_is_the_jar_default_plus_spec_slots(recorded, rid):
    """Each of the five machines tier6.js records is Ad Astra's jar default with exactly the SLOT_CHANGES cells changed. It
    fails when Ad Astra moves the id (remove-by-output would then miss it, or a second recipe appears) or changes the default
    (ours would silently drop the change), and when tier6.js changes a slot spec §6 keeps."""
    output = SHAPED[rid][0]
    ns, name = output.split(":")
    entry = f"data/{ns}/recipe/{name}.json"
    with zipfile.ZipFile(adastra_jar()) as jar:
        default = jar_json(jar, entry, "SLOT_CHANGES no longer describe Ad Astra's default")
    assert default["type"] == "minecraft:crafting_shaped" and default["result"] == {"count": 1, "id": output}, default
    ours = one(recorded, rid)   # exactly one recipe with this id: a dict keyed by id would keep only the last of two
    assert ours["kind"] == "shaped" and ours["output"] == {"id": output, "count": 1}, (rid, ours)
    # kjs.grid checks each grid is 3x3 with every symbol keyed and every key used; the jar's cells must be recipe JSON.
    before = grid(default["pattern"], default["key"], json_only=True)
    after = grid(ours["pattern"], ours["key"])
    # The recipe loads through vanilla's ShapedRecipePattern.unpack, which shrinks the pattern: it trims empty edge rows and
    # columns (see the tier6.js comment above the five machines). Ours has none, so the grid that loads is this one.
    assert all(any(after[r, c] for c in range(3)) and any(after[c, r] for c in range(3)) for r in range(3)), ours["pattern"]
    changed = cell_diff(before, after)
    assert changed == SLOT_CHANGES[rid], f"{rid}: cells that differ from {ADASTRA_JAR}'s default, as (default, ours)"


ALLOYING = "data/ad_astra/recipe/alloying/steel_ingot_from_alloying_iron_ingot_and_barrier.json"
DESH_PLATE = "data/ad_astra/recipe/compressing/desh_plate_from_compressing_desh_ingots.json"


def test_etrium_recipes_keep_ad_astras_own_fields():
    """tier6.js takes the Etrium ingot's fields from "the jar's only alloying recipe" (ALLOYING), and the plate's fields and
    numbers from the desh plate ("cookingtime 100, energy 20, count 1", DESH_PLATE). Pin both claims against the jar, so a
    renamed field in a new Ad Astra version fails here before a boot does. The ingot's own numbers are spec §6 D6.9's."""
    ingot, plate = CUSTOM["confluence:tier6/etrium_ingot"], CUSTOM["confluence:tier6/etrium_plate"]
    with zipfile.ZipFile(adastra_jar()) as jar:
        steel = jar_json(jar, ALLOYING, "tier6.js cites a recipe the jar no longer has")
        desh = jar_json(jar, DESH_PLATE, "tier6.js cites a recipe the jar no longer has")
        alloying = [n for n in jar.namelist() if n.startswith("data/") and "/recipe/" in n and n.endswith(".json")
                    and json.loads(jar.read(n)).get("type") == ingot["type"]]
    assert alloying == [ALLOYING], f"tier6.js calls {ALLOYING} the jar's only alloying recipe; the jar has {alloying}"
    assert set(ingot) == set(steel), (sorted(ingot), sorted(steel))
    assert set(plate) == set(desh), (sorted(plate), sorted(desh))
    numbers = lambda body: (body["cookingtime"], body["energy"], body["result"]["count"])
    assert numbers(plate) == numbers(desh), (numbers(plate), numbers(desh))
