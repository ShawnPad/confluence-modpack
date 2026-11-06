"""v0.3 Task 4: the Mekanism recipes in tiers/tier5.js and the D113 elite-circuit swaps in tiers/tier3.js match the v0.3
spec's §5 rows T5.1, "T5.1 side" and X5.3 (decisions D104, D113, D116).

tools/tests/run_server_scripts.js (the shared runner, through kjs.run) loads lib/*.js, tiers/tier3.js and tiers/tier5.js into
ONE vm context, as KubeJS 2101 gives every server script one shared scope, runs each ServerEvents.recipes handler against an
event that records what it adds and removes, and prints the record as JSON. Each record names the file whose handler made it.
The tests compare the six D113 rewrites and the Digital Miner with Mekanism's own defaults (DEFAULTS, checked against the jar
by test_defaults_match_the_jar), T5.1 with the spec, and check that tier3.js no longer asks for an ultimate circuit. A missing
IDS key shows up before any boot, as '<undefined>' or as a tagId error in `errors`. Later tasks append their own handlers to
tier5.js; one that throws is listed in `errors` and does not hide the others' records. Each record also carries the index of
the handler that made it, so a test can pin one handler's adds and removes (v0.3 Task 5's block, the last tests below).
SOLE_MAKERS (each pinned output -> the one recipe id that may make it) is imported by test_recipe_scripts.py, which checks it
over every server script.

The runner uses node's V8, not the pack's Rhino: it pins the recipes the handlers record, not that the files load in KubeJS.
tools/server_boot.sh (KubeJS `0 errors`, `0 failed recipes`) is the load proof; tools/tests/test_rhino_hazards.py lints the
known Rhino trap.
"""
import json
import zipfile
from collections import Counter

import pytest

from kjs import all_rows, ingredient, jar_json, one, one_maker, pinned_jar, run

TIER3 = "kubejs/server_scripts/tiers/tier3.js"
TIER5 = "kubejs/server_scripts/tiers/tier5.js"
MEK_JAR = "Mekanism-1.21.1-10.7.19.85.jar"
GEN_JAR = "MekanismGenerators-1.21.1-10.7.19.85.jar"

ELITE, ULTIMATE, ULTIMATE_ITEM = "#c:circuits/elite", "#c:circuits/ultimate", "mekanism:ultimate_control_circuit"

# Mekanism-1.21.1-10.7.19.85.jar!data/mekanism/recipe/<name>.json (research/phase7-tier5-ids.md §1.3, §1.5), read when this
# test was written: name -> (type, pattern, key with tags written '#tag', result (id, count)).
DEFAULTS = {
    "qio_drive_base": ("minecraft:crafting_shaped", ["ICI", "C#C", "ICI"],
        {"#": "#c:ender_pearls", "C": ULTIMATE_ITEM, "I": "#c:ingots/lead"}, ("mekanism:qio_drive_base", 1)),
    "qio_redstone_adapter": ("minecraft:crafting_shaped", ["IWI", "CRC", "ITI"],
        {"C": ULTIMATE, "I": "#c:ender_pearls", "R": "#c:dusts/redstone", "T": "mekanism:teleportation_core",
         "W": "minecraft:redstone_torch"}, ("mekanism:qio_redstone_adapter", 1)),
    "quantum_entangloporter": ("minecraft:crafting_shaped", ["ICI", "ATA", "ICI"],
        {"A": "#mekanism:alloys/atomic", "C": ULTIMATE, "I": "#c:ingots/refined_obsidian", "T": "mekanism:teleportation_core"},
        ("mekanism:quantum_entangloporter", 1)),
    "chemical_crystallizer": ("minecraft:crafting_shaped", ["IAI", "CXC", "IAI"],
        {"A": "#c:gems/fluorite", "C": ULTIMATE, "I": "#c:ingots/refined_obsidian", "X": "mekanism:steel_casing"},
        ("mekanism:chemical_crystallizer", 1)),
    "chemical_dissolution_chamber": ("mekanism:mek_data", ["ITI", "CXC", "ITI"],
        {"C": ULTIMATE, "I": "#c:ingots/refined_obsidian", "T": "mekanism:basic_chemical_tank", "X": "mekanism:steel_casing"},
        ("mekanism:chemical_dissolution_chamber", 1)),
    "chemical_washer": ("mekanism:mek_data", ["IBI", "CXC", "ITI"],
        {"B": "mekanism:basic_fluid_tank", "C": ULTIMATE, "I": "#c:ingots/refined_obsidian", "T": "mekanism:basic_chemical_tank",
         "X": "mekanism:steel_casing"}, ("mekanism:chemical_washer", 1)),
    "digital_miner": ("mekanism:mek_data", ["ACA", "SRS", "TXT"],
        {"A": "#mekanism:alloys/atomic", "C": "#c:circuits/basic", "R": "mekanism:robit", "S": "mekanism:logistical_sorter",
         "T": "mekanism:teleportation_core", "X": "mekanism:steel_casing"}, ("mekanism:digital_miner", 1)),
}
# Our id -> (default name, the circuit's key letter, the circuit it takes now): spec §5 "T5.1 side" (D113) and X5.3 (D116).
REWRITES = {
    "confluence:tier3/qio_drive_base": ("qio_drive_base", "C", ELITE),
    "confluence:tier3/qio_redstone_adapter": ("qio_redstone_adapter", "C", ELITE),
    "confluence:tier3/quantum_entangloporter": ("quantum_entangloporter", "C", ELITE),
    "confluence:tier3/chemical_crystallizer": ("chemical_crystallizer", "C", ELITE),
    "confluence:tier3/chemical_dissolution_chamber": ("chemical_dissolution_chamber", "C", ELITE),
    "confluence:tier3/chemical_washer": ("chemical_washer", "C", ELITE),
    "confluence:tier5/digital_miner": ("digital_miner", "C", ULTIMATE),
}
# Removed by id: T5.1's two default producers (the only two recipes in the 118 jars that output the circuit), the Digital
# Miner's default and the six D113 defaults.
REMOVED_BY_ID = ["mekanism:control_circuit/ultimate", "mekanism:control_circuit/infused_ultimate", "mekanism:digital_miner"] + [
    "mekanism:" + name for name in DEFAULTS if name != "digital_miner"]
# The 26 default consumers of the circuit that move to tier 5 with it and stay loaded: `moved` in the v0.3 plan's Task 4 Step 7
# script (T5 §1.5's 35 consumers minus D113's nine).
MOVED_TO_TIER5 = [
    "mekanism:antiprotonic_nucleosynthesizer", "mekanism:bin/ultimate", "mekanism:dimensional_stabilizer",
    "mekanism:induction/provider/ultimate", "mekanism:isotopic_centrifuge", "mekanism:meka_tool", "mekanism:mekasuit_bodyarmor",
    "mekanism:mekasuit_boots", "mekanism:mekasuit_helmet", "mekanism:mekasuit_pants", "mekanism:modification_station",
    "mekanism:module_blasting_unit", "mekanism:sps_port", "mekanism:supercharged_coil", "mekanism:tier_installer/ultimate",
    "mekanismgenerators:reactor/controller", "mekanismgenerators:reactor/port"] + [
    "mekanism:factory/ultimate/" + k for k in ("combining", "compressing", "crushing", "enriching", "infusing", "injecting",
                                               "purifying", "sawing", "smelting")]
# A recipe's loaded type, keyed by its jar default's type: gate.shaped loads as kubejs:shaped (research/phase7-v0.3-test-log.md,
# section "Mekanism tier 5"); raw-JSON types load as written.
LOADED_AS = {"minecraft:crafting_shaped": "kubejs:shaped"}


T51 = "confluence:tier5/ultimate_control_circuit"
# T5.1 as view() reads it: spec §5 row T5.1 (D104).
T51_VIEW = ("kubejs:shaped", ["EAE", "UTU", "EAE"],
            {"E": ELITE, "A": "#mekanism:alloys/atomic", "U": "#c:ingots/unobtainium", "T": "ars_nouveau:wilden_tribute"},
            (ULTIMATE_ITEM, 4))


@pytest.fixture(scope="module")
def recorded():
    return run(TIER3, TIER5)


def view(r):
    """(loaded_type, pattern, key, (result id, count)) of a recorded gate.shaped or gate.custom recipe. A gate.shaped recipe
    loads as kubejs:shaped (research/phase7-v0.3-test-log.md, section "Mekanism tier 5"), a crafting-grid shaped recipe all the same (javap,
    kubejs-neoforge-2101.7.2-build.377.jar: ShapedKubeJSRecipe extends net.minecraft.world.item.crafting.ShapedRecipe).
    A gate.custom recipe loads with its JSON's own type, and its key is recipe JSON ({"item"} or {"tag"} objects only)."""
    if r["kind"] == "shaped":
        out = r["output"] if isinstance(r["output"], dict) else {"id": r["output"], "count": None}
        # Only {id, count}: a components patch ('id[...]' through Item.of) is not the spec's item.
        assert set(out) == {"id", "count"}, out
        return ("kubejs:shaped", r["pattern"], {k: ingredient(v) for k, v in r["key"].items()},
                (out["id"], out["count"]))
    assert r["kind"] == "custom", r
    j = r["json"]
    return (j["type"], j["pattern"], {k: ingredient(v, json_only=True) for k, v in j["key"].items()},
            (j["result"]["id"], j["result"]["count"]))


@pytest.mark.parametrize("rid", sorted(REWRITES))
def test_rewrite_keeps_the_default_except_the_circuit(recorded, rid):
    name, letter, circuit = REWRITES[rid]
    r = one(recorded, rid)
    assert r["file"] == (TIER5 if rid.startswith("confluence:tier5/") else TIER3)
    typ, pattern, key, result = DEFAULTS[name]
    assert view(r) == (LOADED_AS.get(typ, typ), pattern, {**key, letter: circuit}, result)
    # One maker: no other recipe in these scripts makes the item (the default is removed by id).
    assert one_maker(recorded, result[0]) == [rid], f"{result[0]} is made by {one_maker(recorded, result[0])}"


def test_t51_ultimate_control_circuit(recorded):
    r = one(recorded, T51)
    assert r["file"] == TIER5
    assert view(r) == T51_VIEW
    assert one_maker(recorded, ULTIMATE_ITEM) == [T51], f"{ULTIMATE_ITEM} is made by {one_maker(recorded, ULTIMATE_ITEM)}"


def test_defaults_removed_by_id(recorded):
    filters = [e["filter"] for e in recorded["filters"]]
    # Two filter shapes only, as test_ae2_recipes.py and test_tier6_space_recipes.py allow: {id: <a string>} and
    # {output: <a string>} (tier3.js's replaceShaped). A regex id (written {"RegExp": ...}), a filter by mod, type or input,
    # a stack as output, or a combined filter fails here.
    odd = [f for f in filters if not (isinstance(f, dict) and len(f) == 1 and
                                      (isinstance(f.get("id"), str) or isinstance(f.get("output"), str)))]
    assert odd == [], odd
    removed = {f["id"] for f in filters if "id" in f}
    assert sorted(set(REMOVED_BY_ID) - removed) == []
    # No over-removal: no filter names the circuit (item or tag) or a MOVED_TO_TIER5 id, in any key. That catches
    # {input: '#c:circuits/ultimate'}, {output: <a moved id>} and {output: Item.of(circuit)} as well as {id: <a moved id>}.
    over = [f for f in filters
            if any(s in json.dumps(f) for s in (ULTIMATE_ITEM, "c:circuits/ultimate", *MOVED_TO_TIER5))]
    assert over == []


@pytest.mark.parametrize("rid,cells", [("confluence:tier3/qio_drive_array", 2), ("confluence:tier3/qio_importer", 1),
                                       ("confluence:tier3/qio_exporter", 1)])
def test_v02_qio_recipe_takes_elite_circuits(recorded, rid, cells):
    _, pattern, key, _ = view(one(recorded, rid))
    assert sum(key.get(ch) == ELITE for ch in "".join(pattern)) == cells, f"{rid}: pattern {pattern}, key {key}"


def test_tier3_asks_for_no_ultimate_circuit(recorded):
    """No recipe tier3.js adds, and no other recipes-event call it makes (replaceInput and the like), names the circuit."""
    tier3 = [r for r in all_rows(recorded) if r["file"] == TIER3]
    assert tier3, recorded["errors"]

    def names_it(x):
        return "c:circuits/ultimate" in json.dumps(x) or '"%s"' % ULTIMATE_ITEM in json.dumps(x)

    asks = [r["id"] for r in tier3 if names_it(r)]
    assert asks == []
    assert [o for o in recorded["other"] if o["file"] == TIER3 and names_it(o)] == []


def test_defaults_match_the_jar():
    """DEFAULTS are Mekanism's defaults, and each MOVED_TO_TIER5 id is still in its jar and still takes the ultimate control
    circuit. All 26 name it by tag, as key {"tag": "c:circuits/ultimate"} (checked in both jars when Task 8b wrote this);
    either form, tag or item, counts."""
    mek = pinned_jar("Mekanism-", MEK_JAR, "mekanism.pw.toml")
    gen = pinned_jar("MekanismGenerators-", GEN_JAR, "mekanism-generators.pw.toml")
    with zipfile.ZipFile(mek) as jar:
        for name, want in DEFAULTS.items():
            d = jar_json(jar, f"data/mekanism/recipe/{name}.json", f"DEFAULTS[{name!r}] no longer describes Mekanism's default")
            got = (d["type"], d["pattern"], {k: ingredient(v, json_only=True) for k, v in d["key"].items()},
                   (d["result"]["id"], d["result"]["count"]))
            assert got == want, name
    for rid in MOVED_TO_TIER5:
        ns, path = rid.split(":")
        with zipfile.ZipFile({"mekanism": mek, "mekanismgenerators": gen}[ns]) as jar:
            d = jar_json(jar, f"data/{ns}/recipe/{path}.json", f"MOVED_TO_TIER5 names a recipe that is gone ({rid})")
        letters = [k for k, v in d.get("key", {}).items() if ingredient(v, json_only=True) in (ULTIMATE, ULTIMATE_ITEM)]
        assert letters and all(k in "".join(d["pattern"]) for k in letters), (
            f"{rid} no longer takes the ultimate control circuit, so it no longer moves to tier 5 with it: {d}")


# v0.3 Task 5: the three script recipes of tier5.js's "Key, Supreme frame, alloys" block (spec §4.1 D5.1, §5 M5.1 and X5.1;
# D105, D115). Literals are the spec's. The four elemental essences are ars_nouveau-1.21.1-5.13.1.jar's lang
# item.ars_nouveau.{air,earth,fire,water}_essence. T5.2 and X5.2 are datapack JSON: tools/tests/test_if_dissolution_data.py.
KEY, UNOB_ATM, VIB_ATM = ("confluence:tier5/other_key", "confluence:tier5/unobtainium_allthemodium_alloy_ingot",
                          "confluence:tier5/vibranium_allthemodium_alloy_ingot")
KEY_ITEM, UNOB_ATM_ITEM, VIB_ATM_ITEM = ("kubejs:other_key", "allthemodium:unobtainium_allthemodium_alloy_ingot",
                                         "allthemodium:vibranium_allthemodium_alloy_ingot")
HEART = "allthemodium:piglich_heart"
# D5.1 as view() reads it (spec §4.1; D105).
KEY_VIEW = ("kubejs:shaped", [" E ", "VFB", " D "],
            {"E": "kubejs:end_focus", "V": "#c:ingots/vibranium", "F": "#industrialforegoing:machine_frame/advanced",
             "B": "the_bumblezone:essence_of_the_bees", "D": "minecraft:dragon_egg"},
            (KEY_ITEM, 1))
# M5.1 and X5.1, the whole custom JSON in the script's order (spec §5 rows M5.1, X5.1; D115). The tests below also check
# the pieces that matter on their own (pedestal multiset, energy as a long), so a failure names the slip.
CUSTOM_BODIES = {
    UNOB_ATM: {"type": "ars_nouveau:enchanting_apparatus", "keepNbtOfReagent": False, "sourceCost": 10000,
               "reagent": {"tag": "c:ingots/unobtainium"},
               "pedestalItems": [{"tag": "c:ingots/allthemodium"}, {"item": HEART}, {"item": "ars_nouveau:air_essence"},
                                 {"item": "ars_nouveau:earth_essence"}, {"item": "ars_nouveau:fire_essence"},
                                 {"item": "ars_nouveau:water_essence"}],
               "result": {"count": 1, "id": UNOB_ATM_ITEM}},
    VIB_ATM: {"type": "powah:energizing", "energy": 1000000000,
              "ingredients": [{"tag": "c:ingots/allthemodium"}, {"tag": "c:ingots/vibranium"}, {"item": HEART},
                              {"item": "powah:nitro_crystal_block"}],
              "result": {"count": 1, "id": VIB_ATM_ITEM}},
}

# Each output this file pins -> the only recipe ids that may make it, in any server script (test_recipe_scripts.py).
SOLE_MAKERS = {
    **{DEFAULTS[name][3][0]: [rid] for rid, (name, _, _) in REWRITES.items()},
    ULTIMATE_ITEM: [T51], KEY_ITEM: [KEY], UNOB_ATM_ITEM: [UNOB_ATM], VIB_ATM_ITEM: [VIB_ATM],
}


def test_d51_key_to_the_other(recorded):
    r = one(recorded, KEY)
    assert r["file"] == TIER5
    assert view(r) == KEY_VIEW
    assert one_maker(recorded, KEY_ITEM) == [KEY]


def test_m51_unobtainium_allthemodium_alloy(recorded):
    r = one(recorded, UNOB_ATM)
    assert r["file"] == TIER5
    j = r["json"]
    assert set(j) == {"type", "keepNbtOfReagent", "sourceCost", "reagent", "pedestalItems", "result"}, sorted(j)
    assert j["type"] == "ars_nouveau:enchanting_apparatus"
    assert ingredient(j["reagent"], json_only=True) == "#c:ingots/unobtainium"
    assert Counter(ingredient(v, json_only=True) for v in j["pedestalItems"]) == Counter([
        "#c:ingots/allthemodium", HEART, "ars_nouveau:air_essence", "ars_nouveau:earth_essence", "ars_nouveau:fire_essence",
        "ars_nouveau:water_essence"])
    assert j["sourceCost"] == 10000 and j["keepNbtOfReagent"] is False
    assert j["result"] == {"count": 1, "id": UNOB_ATM_ITEM}
    assert j == CUSTOM_BODIES[UNOB_ATM]
    assert one_maker(recorded, UNOB_ATM_ITEM) == [UNOB_ATM]


def test_x51_vibranium_allthemodium_alloy(recorded):
    r = one(recorded, VIB_ATM)
    assert r["file"] == TIER5
    j = r["json"]
    assert set(j) == {"type", "energy", "ingredients", "result"}, sorted(j)
    assert j["type"] == "powah:energizing"
    assert Counter(ingredient(v, json_only=True) for v in j["ingredients"]) == Counter([
        "#c:ingots/allthemodium", "#c:ingots/vibranium", HEART, "powah:nitro_crystal_block"])
    assert j["energy"] == 1000000000
    assert j["result"] == {"count": 1, "id": VIB_ATM_ITEM}
    assert j == CUSTOM_BODIES[VIB_ATM]
    assert one_maker(recorded, VIB_ATM_ITEM) == [VIB_ATM]


def test_task5_block_is_add_only(recorded):
    """One handler makes all three and removes nothing. No loaded recipe makes the key or an alloy ingot except Allthemodium's
    9-from-1 block recipes, which stay (research/phase7-tier5-ids.md §4.3); gate.custom given an `output` would remove every
    recipe of that output, the block recipe included. The handler makes no other recipes-event call either (replaceInput and
    the like)."""
    handlers = {one(recorded, rid)["handler"] for rid in (KEY, UNOB_ATM, VIB_ATM)}
    assert len(handlers) == 1, handlers
    h = handlers.pop()
    assert sorted(r["id"] for r in all_rows(recorded) if r["handler"] == h) == sorted([KEY, UNOB_ATM, VIB_ATM])
    assert [e["filter"] for e in recorded["filters"] if e["handler"] == h] == []
    assert [o for o in recorded["other"] if o["handler"] == h] == []
