"""v0.3 Task 4: the Mekanism recipes in tiers/tier5.js and the D113 elite-circuit swaps in tiers/tier3.js match the v0.3
spec's §5 rows T5.1, "T5.1 side" and X5.3 (decisions D104, D113, D116).

node loads lib/ids.js, lib/gates.js, tiers/tier3.js and tiers/tier5.js into ONE vm context, as KubeJS 2101 gives every server
script one shared scope, runs each ServerEvents.recipes handler against an event that records what it adds and removes, and
prints the record as JSON. Each record names the file whose handler made it. The tests compare the six D113 rewrites and the
Digital Miner with Mekanism's own defaults (DEFAULTS, checked against the jar by the last test), T5.1 with the spec, and check
that tier3.js no longer asks for an ultimate circuit. A missing IDS key shows up before any boot, as '<undefined>' or as a
tagId error in `errors`. Later tasks append their own handlers to tier5.js; one that throws here (an API this stub lacks) is
listed in `errors` and does not hide the others' records. Each record also carries the index of the handler that made it, so
a test can pin one handler's adds and removes (v0.3 Task 5's block, the last tests below).

The harness runs under node's V8, not the pack's Rhino: it pins the recipes the handlers record, not that the files load in
KubeJS. tools/server_boot.sh (KubeJS `0 errors`, `0 failed recipes`) is the load proof; tools/tests/test_rhino_hazards.py lints
one known Rhino trap.
"""
import json
import os
import shutil
import subprocess
import zipfile
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TIER3 = "kubejs/server_scripts/tiers/tier3.js"
TIER5 = "kubejs/server_scripts/tiers/tier5.js"
SCRIPTS = ["kubejs/server_scripts/lib/ids.js", "kubejs/server_scripts/lib/gates.js", TIER3, TIER5]
MODS = ROOT / ".run" / "server" / "mods"
MEK_JAR = MODS / "Mekanism-1.21.1-10.7.19.85.jar"

HARNESS = r"""
const fs = require('fs'), path = require('path'), vm = require('vm')
const out = { recipes: [], removed: [], errors: [] }
const handlers = []
let loading = null, current = null, currentHandler = null
const noop = () => {}
// `any` stands in for every other KubeJS global a script might touch at top level: callable, constructible, and every
// property is itself.
const any = new Proxy(function () {}, { get: (t, k) => (k === Symbol.toPrimitive ? () => '' : any), apply: () => any, construct: () => any })
const sandbox = {
  console: { log: noop, info: noop, warn: noop, error: noop },
  ServerEvents: new Proxy({}, { get: (t, k) => (k === 'recipes' ? fn => { handlers.push([loading, fn]) } : any) }),
  // Item.of(id), Item.of(id, n), Item.of(stack): kubejs-neoforge-2101.7.2-build.377.jar ItemWrapper.of(ItemStack) returns its
  // argument and ItemWrapper.of(ItemStack, int) a copy with count n. A stack is {id, count} here.
  Item: { of: (x, n) => (typeof x === 'string' ? { id: x, count: n === undefined ? 1 : n } : (n === undefined ? x : { id: x && x.id, count: n })) },
}
for (const g of ['Java', 'JsonIO', 'Utils', 'Ingredient', 'Fluid', 'Text', 'Platform', 'NativeEvents', 'BlockEvents',
                 'PlayerEvents', 'EntityEvents', 'LootJS']) sandbox[g] = any
vm.createContext(sandbox)
for (const f of process.env.FILES.split(',')) {
  const p = path.join(process.env.PACK_ROOT, f)
  if (!fs.existsSync(p)) { out.errors.push(f + ': missing'); continue }
  loading = f
  try { vm.runInContext(fs.readFileSync(p, 'utf8'), sandbox, { filename: f }) } catch (e) { out.errors.push(f + ': ' + e) }
}
// Any call on a recipe returns the recipe, so chains like .id(...) work; .id records the id.
const handle = entry => { const h = new Proxy({}, { get: (t, k) => (k === 'id' ? i => { entry.id = String(i); return h } : () => h) }); return h }
const add = e => { e.file = current; e.handler = currentHandler; out.recipes.push(e); return handle(e) }
const event = new Proxy({}, { get: (t, k) => {
  if (k === 'shaped') return (output, pattern, keys) => add({ kind: 'shaped', output, pattern, keys })
  if (k === 'shapeless') return (output, inputs) => add({ kind: 'shapeless', output, inputs })
  if (k === 'custom') return json => add({ kind: 'custom', json })
  if (k === 'remove') return filter => { out.removed.push({ file: current, handler: currentHandler, filter }) }
  return () => handle({})
} })
handlers.forEach(([f, h], i) => { current = f; currentHandler = i; try { h(event) } catch (e) { out.errors.push(f + ' handler ' + i + ': ' + e) } })
process.stdout.write(JSON.stringify(out, (k, v) => (v === undefined ? '<undefined>' : v)))
"""

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
# A recipe's loaded type, keyed by its jar default's type: gate.shaped loads as kubejs:shaped (research/phase7-v0.3-test-log.md
# §2); raw-JSON types load as written.
LOADED_AS = {"minecraft:crafting_shaped": "kubejs:shaped"}


@pytest.fixture(scope="module")
def recorded():
    node = shutil.which("node")
    assert node, "node is not on PATH; `node --version` must print a version (v22.3.0 was used when this test was written)"
    env = {**os.environ, "PACK_ROOT": str(ROOT), "FILES": ",".join(SCRIPTS)}
    proc = subprocess.run([node, "-e", HARNESS], env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def ingredient(v):
    """A key value as a script writes it ('#tag' or an item id) or as raw JSON ({"tag": ...} or {"item": ...})."""
    if isinstance(v, dict):
        return "#" + v["tag"] if "tag" in v else v.get("item", v)
    return v


def view(r):
    """(loaded_type, pattern, key, (result id, count)) of a recorded gate.shaped or gate.custom recipe. A gate.shaped recipe
    loads as kubejs:shaped (research/phase7-v0.3-test-log.md §2), a crafting-grid shaped recipe all the same (javap,
    kubejs-neoforge-2101.7.2-build.377.jar: ShapedKubeJSRecipe extends net.minecraft.world.item.crafting.ShapedRecipe).
    A gate.custom recipe loads with its JSON's own type."""
    if r["kind"] == "shaped":
        out = r["output"] if isinstance(r["output"], dict) else {"id": r["output"], "count": None}
        return ("kubejs:shaped", r["pattern"], {k: ingredient(v) for k, v in r["keys"].items()},
                (out["id"], out["count"]))
    j = r["json"]
    return (j["type"], j["pattern"], {k: ingredient(v) for k, v in j["key"].items()}, (j["result"]["id"], j["result"]["count"]))


def one(recorded, rid):
    hits = [r for r in recorded["recipes"] if r.get("id") == rid]
    assert len(hits) == 1, f"{rid}: {len(hits)} recipes recorded; script errors: {recorded['errors']}"
    return hits[0]


@pytest.mark.parametrize("rid", sorted(REWRITES))
def test_rewrite_keeps_the_default_except_the_circuit(recorded, rid):
    name, letter, circuit = REWRITES[rid]
    r = one(recorded, rid)
    assert r["file"] == (TIER5 if rid.startswith("confluence:tier5/") else TIER3)
    typ, pattern, key, result = DEFAULTS[name]
    assert view(r) == (LOADED_AS.get(typ, typ), pattern, {**key, letter: circuit}, result)


def test_t51_ultimate_control_circuit(recorded):
    r = one(recorded, "confluence:tier5/ultimate_control_circuit")
    assert r["file"] == TIER5
    assert view(r) == ("kubejs:shaped", ["EAE", "UTU", "EAE"],
                       {"E": ELITE, "A": "#mekanism:alloys/atomic", "U": "#c:ingots/unobtainium", "T": "ars_nouveau:wilden_tribute"},
                       (ULTIMATE_ITEM, 4))


def test_defaults_removed_by_id(recorded):
    removed = {e["filter"].get("id") for e in recorded["removed"] if isinstance(e["filter"], dict)}
    assert sorted(set(REMOVED_BY_ID) - removed) == []
    # No over-removal: no MOVED_TO_TIER5 id is removed, and nothing is removed by the circuit as output.
    filters = [e["filter"] if isinstance(e["filter"], dict) else {"id": e["filter"]} for e in recorded["removed"]]
    over = [f for f in filters if f.get("id") in MOVED_TO_TIER5 or f.get("output") in (ULTIMATE_ITEM, ULTIMATE)]
    assert over == []


@pytest.mark.parametrize("rid,cells", [("confluence:tier3/qio_drive_array", 2), ("confluence:tier3/qio_importer", 1),
                                       ("confluence:tier3/qio_exporter", 1)])
def test_v02_qio_recipe_takes_elite_circuits(recorded, rid, cells):
    _, pattern, key, _ = view(one(recorded, rid))
    assert sum(key.get(ch) == ELITE for ch in "".join(pattern)) == cells, f"{rid}: pattern {pattern}, key {key}"


def test_tier3_asks_for_no_ultimate_circuit(recorded):
    tier3 = [r for r in recorded["recipes"] if r["file"] == TIER3]
    assert tier3, recorded["errors"]
    asks = [r.get("id") for r in tier3
            if "c:circuits/ultimate" in json.dumps(r) or '"%s"' % ULTIMATE_ITEM in json.dumps(r)]
    assert asks == []


def test_defaults_match_the_jar():
    if not MODS.is_dir():
        pytest.skip(f"{MODS} does not exist (no server has been booted from this clone)")
    # 'Mekanism-*.jar' does not match MekanismGenerators-*.jar or MekanismAdditions-*.jar: the hyphen follows 'Mekanism'.
    found = sorted(MODS.glob("Mekanism-*.jar"))
    assert found == [MEK_JAR], f"DEFAULTS were read from {MEK_JAR.name}; {MODS} holds {[p.name for p in found]}"
    with zipfile.ZipFile(MEK_JAR) as jar:
        for name, want in DEFAULTS.items():
            d = json.loads(jar.read(f"data/mekanism/recipe/{name}.json"))
            got = (d["type"], d["pattern"], {k: ingredient(v) for k, v in d["key"].items()},
                   (d["result"]["id"], d["result"]["count"]))
            assert got == want, name


# v0.3 Task 5: the three script recipes of tier5.js's "Key, Supreme frame, alloys" block (spec §4.1 D5.1, §5 M5.1 and X5.1;
# D105, D115). Literals are the spec's. The four elemental essences are ars_nouveau-1.21.1-5.13.1.jar's lang
# item.ars_nouveau.{air,earth,fire,water}_essence. T5.2 and X5.2 are datapack JSON: tools/tests/test_if_dissolution_data.py.
KEY, UNOB_ATM, VIB_ATM = ("confluence:tier5/other_key", "confluence:tier5/unobtainium_allthemodium_alloy_ingot",
                          "confluence:tier5/vibranium_allthemodium_alloy_ingot")
HEART = "allthemodium:piglich_heart"


def test_d51_key_to_the_other(recorded):
    r = one(recorded, KEY)
    assert r["file"] == TIER5
    assert view(r) == ("kubejs:shaped", [" E ", "VFB", " D "],
                       {"E": "kubejs:end_focus", "V": "#c:ingots/vibranium", "F": "#industrialforegoing:machine_frame/advanced",
                        "B": "the_bumblezone:essence_of_the_bees", "D": "minecraft:dragon_egg"},
                       ("kubejs:other_key", 1))


def test_m51_unobtainium_allthemodium_alloy(recorded):
    r = one(recorded, UNOB_ATM)
    assert r["file"] == TIER5
    j = r["json"]
    assert set(j) == {"type", "keepNbtOfReagent", "sourceCost", "reagent", "pedestalItems", "result"}, sorted(j)
    assert j["type"] == "ars_nouveau:enchanting_apparatus"
    assert ingredient(j["reagent"]) == "#c:ingots/unobtainium"
    assert Counter(map(ingredient, j["pedestalItems"])) == Counter([
        "#c:ingots/allthemodium", HEART, "ars_nouveau:air_essence", "ars_nouveau:earth_essence", "ars_nouveau:fire_essence",
        "ars_nouveau:water_essence"])
    assert j["sourceCost"] == 10000 and j["keepNbtOfReagent"] is False
    assert j["result"] == {"count": 1, "id": "allthemodium:unobtainium_allthemodium_alloy_ingot"}


def test_x51_vibranium_allthemodium_alloy(recorded):
    r = one(recorded, VIB_ATM)
    assert r["file"] == TIER5
    j = r["json"]
    assert set(j) == {"type", "energy", "ingredients", "result"}, sorted(j)
    assert j["type"] == "powah:energizing"
    assert Counter(map(ingredient, j["ingredients"])) == Counter([
        "#c:ingots/allthemodium", "#c:ingots/vibranium", HEART, "powah:nitro_crystal_block"])
    assert j["energy"] == 1000000000
    assert j["result"] == {"count": 1, "id": "allthemodium:vibranium_allthemodium_alloy_ingot"}


def test_task5_block_is_add_only(recorded):
    """One handler makes all three and removes nothing. No loaded recipe makes the key or an alloy ingot except Allthemodium's
    9-from-1 block recipes, which stay (research/phase7-tier5-ids.md §4.3); gate.custom given an `output` would remove every
    recipe of that output, the block recipe included."""
    handlers = {one(recorded, rid)["handler"] for rid in (KEY, UNOB_ATM, VIB_ATM)}
    assert len(handlers) == 1, handlers
    h = handlers.pop()
    assert sorted(r.get("id") for r in recorded["recipes"] if r["handler"] == h) == sorted([KEY, UNOB_ATM, VIB_ATM])
    assert [e["filter"] for e in recorded["removed"] if e["handler"] == h] == []
