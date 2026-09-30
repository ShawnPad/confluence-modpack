"""v0.3 Task 7: the AE2 recipes in tiers/tier5.js and tiers/tier6.js match the v0.3 spec's rows S5.1–S5.3 (§5) and
S6.1–S6.2 (§6), decisions D107 and D117.

node loads lib/ids.js, lib/gates.js, tiers/tier5.js and tiers/tier6.js into ONE vm context, as KubeJS 2101 gives every server
script one shared scope, runs each ServerEvents.recipes handler against an event that records what it adds and removes, and
prints the record as JSON. The tests compare each AE2 recipe with the spec's shape and literal ids. This catches, before any
boot, a wrong or missing IDS key: KubeJS's kubejs:key_pattern_cleanup post-processor drops a key whose ingredient is null or
empty and turns its cells into spaces (kubejs-neoforge-2101.7.2-build.377.jar, KeyPatternCleanupPostProcessor.process), so such
a slip can load as a cheaper recipe instead of an error.

node runs V8, not the pack's Rhino, so this test pins the recipes the handlers record, not that the files load in KubeJS;
tools/tests/test_rhino_hazards.py lints the known Rhino trap. The load proof is tools/server_boot.sh (its KubeJS ERROR check and
its check for "Parsing error loading recipe" in logs/latest.log) and the boot's "with 0 failed recipes" line. node must be on
PATH: the `recorded` fixture asserts it, so this test runs rather than skips. The last test reads AE2's ten defaults (DEFAULTS)
from appliedenergistics2-19.2.17.jar in .run/server/mods; it skips only when that folder does not exist, and fails on any other
AE2 jar or on a default that moved or changed.
"""
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = [
    "kubejs/server_scripts/lib/ids.js",
    "kubejs/server_scripts/lib/gates.js",
    "kubejs/server_scripts/tiers/tier5.js",
    "kubejs/server_scripts/tiers/tier6.js",
]
MODS = ROOT / ".run" / "server" / "mods"
AE2_JAR = MODS / "appliedenergistics2-19.2.17.jar"

HARNESS = r"""
const fs = require('fs'), path = require('path'), vm = require('vm')
const out = { recipes: [], removed: [], errors: [] }
const handlers = []
const noop = () => {}
// `any` stands in for every other KubeJS global a tier file might touch at top level (Java.loadClass, JsonIO, ...):
// callable, constructible, and every property is itself.
const any = new Proxy(function () {}, { get: (t, k) => (k === Symbol.toPrimitive ? () => '' : any), apply: () => any, construct: () => any })
const sandbox = {
  console: { log: noop, info: noop, warn: noop, error: noop },
  ServerEvents: new Proxy({}, { get: (t, k) => (k === 'recipes' ? fn => { handlers.push(fn) } : any) }),
  // Item.of(id), Item.of(id, n), Item.of(stack): kubejs-neoforge-2101.7.2-build.377.jar ItemWrapper.of(ItemStack) returns its
  // argument and ItemWrapper.of(ItemStack, int) a copy with count n. A stack is {id, count} here, as in test_mek_tier5.py.
  Item: { of: (x, n) => (typeof x === 'string' ? { id: x, count: n === undefined ? 1 : n } : (n === undefined ? x : { id: x && x.id, count: n })) },
}
for (const g of ['Java', 'JsonIO', 'Utils', 'Ingredient', 'Fluid', 'Text', 'Platform', 'NativeEvents', 'BlockEvents',
                 'PlayerEvents', 'EntityEvents', 'LootJS']) sandbox[g] = any
vm.createContext(sandbox)
for (const f of process.env.FILES.split(',')) {
  const p = path.join(process.env.PACK_ROOT, f)
  if (!fs.existsSync(p)) { out.errors.push(f + ': missing'); continue }
  try { vm.runInContext(fs.readFileSync(p, 'utf8'), sandbox, { filename: f }) } catch (e) { out.errors.push(f + ': ' + e) }
}
// Any call on a recipe returns the recipe, so chains like .id(...) work; .id records the id.
const handle = entry => { const h = new Proxy({}, { get: (t, k) => (k === 'id' ? i => { entry.id = String(i); return h } : () => h) }); return h }
const event = new Proxy({}, { get: (t, k) => {
  if (k === 'shaped') return (output, pattern, keys) => { const e = { kind: 'shaped', output, pattern, keys }; out.recipes.push(e); return handle(e) }
  if (k === 'shapeless') return (output, inputs) => { const e = { kind: 'shapeless', output, inputs }; out.recipes.push(e); return handle(e) }
  if (k === 'custom') return json => { const e = { kind: 'custom', json }; out.recipes.push(e); return handle(e) }
  if (k === 'remove') return filter => { out.removed.push(filter) }
  return () => handle({})
} })
// One handler's error (another task's block using an API this stub lacks) must not hide the others' records.
handlers.forEach((h, i) => { try { h(event) } catch (e) { out.errors.push('handler ' + i + ': ' + e) } })
process.stdout.write(JSON.stringify(out, (k, v) => (v === undefined ? '<undefined>' : v)))
"""

# Literal ids, each re-read from a jar in .run/server/mods or from the boot's tags.json when this test was written:
# ae2:* -- appliedenergistics2-19.2.17.jar lang block.ae2.* / item.ae2.* (semi_dark_monitor = "Illuminated Panel");
# mekanism:hdpe_sheet, qio_* -- Mekanism-1.21.1-10.7.19.85.jar lang item.mekanism.hdpe_sheet / block.mekanism.qio_*; the Supreme frame tag -- industrialforegoing-1.21-3.6.39.jar
# data/industrialforegoing/tags/item/machine_frame/supreme.json (1 entry); #c:ingots/{copper,iron} -- libraries/net/neoforged/
# neoforge/21.1.250/neoforge-21.1.250-universal.jar data/c/tags/item/ingots/{copper,iron}.json (tags.json: 1 entry each);
# #c:ingots/knightmetal -- twilightforest-1.21.1-4.8.3345-universal.jar; #c:ingots/{desh,ostrum} -- adastra-1.21.1-1.16.25-neoforge.jar;
# undergarden:forgotten_ingot -- The_Undergarden-1.21.1-0.9.6.jar lang; toms_storage:inventory_connector -- toms_storage-1.21-2.4.2.jar.
SUPREME = "#industrialforegoing:machine_frame/supreme"
COPPER, IRON = "#c:ingots/copper", "#c:ingots/iron"

# recipe id -> (output, pattern, key). Shapes: v0.3 spec §5/§6, from OSR2 1.7.1 (research/phase7-ae2-ids.md §3).
EXPECTED = {
    "confluence:tier5/inscriber": ("ae2:inscriber", ["ABA", "CDC", "ABA"],
        {"A": "mekanism:hdpe_sheet", "B": "minecraft:piston", "C": COPPER, "D": SUPREME}),
    "confluence:tier5/charger": ("ae2:charger", ["ABA", "A  ", "ABA"],
        {"A": "#c:ingots/knightmetal", "B": COPPER}),
    "confluence:tier5/controller": ("ae2:controller", ["ABA", "CDC", "EFE"],
        {"A": "ae2:fluix_crystal", "B": "undergarden:forgotten_ingot", "C": "ae2:engineering_processor", "D": SUPREME,
         "E": "ae2:smooth_sky_stone_block", "F": "toms_storage:inventory_connector"}),
    "confluence:tier5/drive": ("ae2:drive", ["ABA", "CDC", "ABA"],
        {"A": IRON, "B": "ae2:engineering_processor", "C": "ae2:fluix_glass_cable", "D": "mekanism:qio_drive_array"}),
    "confluence:tier5/import_bus": ("ae2:import_bus", [" A ", " B ", "CDC"],
        {"A": "mekanism:qio_importer", "B": "ae2:annihilation_core", "C": IRON, "D": "minecraft:piston"}),
    "confluence:tier5/export_bus": ("ae2:export_bus", [" A ", " B ", "CDC"],
        {"A": "mekanism:qio_exporter", "B": "ae2:formation_core", "C": IRON, "D": "minecraft:piston"}),
    "confluence:tier5/terminal": ("ae2:terminal", [" A ", "BCD", "EFE"],
        {"A": "ae2:semi_dark_monitor", "B": "ae2:formation_core", "C": SUPREME, "D": "ae2:annihilation_core",
         "E": "ae2:logic_processor", "F": "mekanism:qio_dashboard"}),
    "confluence:tier6/wireless_receiver": ("ae2:wireless_receiver", [" A ", "BCB", " B "],
        {"A": "ae2:fluix_pearl", "B": "#c:ingots/desh", "C": "ae2:quartz_fiber"}),
    "confluence:tier6/crafting_unit": ("ae2:crafting_unit", ["ABA", "CDF", "AEA"],
        {"A": "ae2:fluix_crystal", "B": "ae2:calculation_processor", "C": "#c:ingots/ostrum", "D": SUPREME,
         "E": "ae2:logic_processor", "F": "ae2:fluix_glass_cable"}),
    "confluence:tier6/pattern_provider": ("ae2:pattern_provider", ["ABA", "COD", "ABA"],
        {"A": IRON, "B": "minecraft:crafting_table", "C": "ae2:annihilation_core", "D": "ae2:formation_core",
         "O": "#c:ingots/ostrum"}),
}

# AE2's defaults, each the only recipe for its item except the provider (appliedenergistics2-19.2.17.jar!data/ae2/recipe/...).
REMOVED_BY_ID = [
    "ae2:network/blocks/inscribers", "ae2:network/blocks/crystal_processing_charger", "ae2:network/blocks/controller",
    "ae2:network/blocks/storage_drive", "ae2:network/parts/import_bus", "ae2:network/parts/export_bus",
    "ae2:network/parts/terminals", "ae2:network/wireless_part", "ae2:network/crafting/cpu_crafting_unit",
    "ae2:network/blocks/pattern_providers_interface",
]
# The same ten, as AE2_JAR!data/ae2/recipe/<path>.json held them when this test was written (AE2 §1.2; the tier5.js and
# tier6.js comments describe them): default id -> (the confluence: recipe that replaces it, type, pattern, key with tags
# written '#tag', result (id, count)). The shapeless terminal has no pattern; its key is the ingredient list, in the jar's order.
DEFAULTS = {
    "ae2:network/blocks/inscribers": ("confluence:tier5/inscriber", "minecraft:crafting_shaped", ["aba", "c a", "aba"],
        {"a": IRON, "b": "minecraft:piston", "c": COPPER}, ("ae2:inscriber", 1)),
    "ae2:network/blocks/crystal_processing_charger": ("confluence:tier5/charger", "minecraft:crafting_shaped",
        ["aba", "a  ", "aba"], {"a": IRON, "b": COPPER}, ("ae2:charger", 1)),
    "ae2:network/blocks/controller": ("confluence:tier5/controller", "minecraft:crafting_shaped", ["aba", "bcb", "aba"],
        {"a": "ae2:smooth_sky_stone_block", "b": "ae2:fluix_crystal", "c": "ae2:engineering_processor"}, ("ae2:controller", 1)),
    "ae2:network/blocks/storage_drive": ("confluence:tier5/drive", "minecraft:crafting_shaped", ["aba", "c c", "aba"],
        {"a": IRON, "b": "ae2:engineering_processor", "c": "ae2:fluix_glass_cable"}, ("ae2:drive", 1)),
    "ae2:network/parts/import_bus": ("confluence:tier5/import_bus", "minecraft:crafting_shaped", [" a ", "bcb"],
        {"a": "ae2:annihilation_core", "b": IRON, "c": "minecraft:piston"}, ("ae2:import_bus", 1)),
    "ae2:network/parts/export_bus": ("confluence:tier5/export_bus", "minecraft:crafting_shaped", ["aba", " c "],
        {"a": IRON, "b": "ae2:formation_core", "c": "minecraft:piston"}, ("ae2:export_bus", 1)),
    "ae2:network/parts/terminals": ("confluence:tier5/terminal", "minecraft:crafting_shapeless", None,
        ["ae2:formation_core", "#ae2:illuminated_panel", "ae2:logic_processor", "ae2:annihilation_core"], ("ae2:terminal", 1)),
    "ae2:network/wireless_part": ("confluence:tier6/wireless_receiver", "minecraft:crafting_shaped", [" a ", "bcb", " b "],
        {"a": "ae2:fluix_pearl", "b": IRON, "c": "ae2:quartz_fiber"}, ("ae2:wireless_receiver", 1)),
    "ae2:network/crafting/cpu_crafting_unit": ("confluence:tier6/crafting_unit", "minecraft:crafting_shaped",
        ["aba", "cdc", "aba"], {"a": IRON, "b": "ae2:calculation_processor", "c": "ae2:fluix_glass_cable",
                                "d": "ae2:logic_processor"}, ("ae2:crafting_unit", 1)),
    "ae2:network/blocks/pattern_providers_interface": ("confluence:tier6/pattern_provider", "minecraft:crafting_shaped",
        ["aba", "c d", "aba"], {"a": IRON, "b": "minecraft:crafting_table", "c": "ae2:annihilation_core",
                                "d": "ae2:formation_core"}, ("ae2:pattern_provider", 1)),
}
# Defaults this task must leave alone: the provider's part <-> block conversions (AE2 §4.5) and the D117 defaults.
KEPT = [
    "ae2:network/blocks/pattern_providers_interface_alt", "ae2:network/blocks/pattern_providers_interface_part",
    "ae2:network/crafting/molecular_assembler", "ae2:network/parts/terminals_pattern_encoding",
    "ae2:network/parts/terminals_crafting",
]


@pytest.fixture(scope="module")
def recorded():
    node = shutil.which("node")
    assert node, "node is not on PATH; `node --version` must print a version (v22.3.0 was used when this test was written)"
    env = {**os.environ, "PACK_ROOT": str(ROOT), "FILES": ",".join(SCRIPTS)}
    proc = subprocess.run([node, "-e", HARNESS], env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def assert_vanilla_shape(pattern, keys):
    """What vanilla's ShapedRecipePattern accepts; kubejs:shaped parses through its MAP_CODEC
    (kubejs-neoforge-2101.7.2-build.377.jar ShapedKubeJSRecipe$SerializerKJS). Error strings in
    server-1.21.1-20240808.144430-srg.jar: "too many rows, 3 is maximum", "too many columns, 3 is maximum",
    "each row must be the same width", "' ' is a reserved symbol", "Pattern references symbol '…' but it's not defined
    in the key", "Key defines symbols that aren't used in pattern". A row of spaces inside the grid is fine: AE2's own
    charger default has the row "a  "."""
    assert 1 <= len(pattern) <= 3
    assert len({len(row) for row in pattern}) == 1 and 1 <= len(pattern[0]) <= 3
    assert " " not in keys
    assert set("".join(pattern)) - {" "} == set(keys)
    assert all(isinstance(v, str) and v and v != "<undefined>" for v in keys.values()), keys


@pytest.mark.parametrize("rid", sorted(EXPECTED))
def test_ae2_recipe_matches_spec(recorded, rid):
    hits = [r for r in recorded["recipes"] if r.get("id") == rid]
    assert len(hits) == 1, f"{rid}: {len(hits)} recipes recorded; script errors: {recorded['errors']}"
    r = hits[0]
    assert r["kind"] == "shaped"
    assert_vanilla_shape(r["pattern"], r["keys"])
    output, pattern, keys = EXPECTED[rid]
    # gate.shaped passes Item.of(output); the harness records that stack as {id, count}.
    assert (r["output"], r["pattern"], r["keys"]) == ({"id": output, "count": 1}, pattern, keys)


def test_ae2_defaults_removed_by_id_only(recorded):
    filters = [f for f in recorded["removed"] if isinstance(f, dict)]
    # A regex id (bypass.js uses one) reaches here as {} after JSON.stringify, so keep only string ids.
    removed_ids = {f["id"] for f in filters if isinstance(f.get("id"), str)}
    assert sorted(set(REMOVED_BY_ID) - removed_ids) == []
    assert sorted(removed_ids & set(KEPT)) == []
    assert [f for f in filters if str(f.get("output", "")).startswith("ae2:")] == []


def ingredient(v):
    """A jar key value or shapeless ingredient ({"item": ...} or {"tag": ...}) as DEFAULTS writes it: an item id or '#tag'."""
    assert isinstance(v, dict) and set(v) in ({"item"}, {"tag"}), v
    return "#" + v["tag"] if "tag" in v else v["item"]


def ae2_jar():
    """AE2_JAR, after the checks test_tier6_space_recipes.py's jar tests make: skip only when no server has been booted from
    this clone, and fail on any other AE2 jar."""
    if not MODS.is_dir():
        pytest.skip(f"{MODS} does not exist (no server has been booted from this clone)")
    # 'appliedenergistics2-*.jar' needs the hyphen right after the mod id, so an add-on jar with a longer name does not match.
    found = sorted(MODS.glob("appliedenergistics2-*.jar"))
    assert found == [AE2_JAR], f"DEFAULTS were read from {AE2_JAR.name}; {MODS} holds {[p.name for p in found]}"
    return AE2_JAR


def jar_json(jar, entry, what):
    try:
        return json.loads(jar.read(entry))
    except KeyError:
        pytest.fail(f"id moved: {AE2_JAR.name} has no {entry}, so {what}")


@pytest.mark.parametrize("rid", REMOVED_BY_ID)
def test_ae2_default_matches_the_jar(rid):
    """Each default this task removes by id is still at that id in AE2_JAR, and still the recipe DEFAULTS (and the tier5.js /
    tier6.js comments) describe, making the item its confluence: replacement makes. A moved id would leave the default
    loaded beside ours; a changed default would make the comments' "the default's ... stays" untrue."""
    assert list(DEFAULTS) == REMOVED_BY_ID
    ours, want = DEFAULTS[rid][0], DEFAULTS[rid][1:]
    assert want[3][0] == EXPECTED[ours][0], (rid, want[3], ours, EXPECTED[ours][0])
    ns, path = rid.split(":")
    with zipfile.ZipFile(ae2_jar()) as jar:
        d = jar_json(jar, f"data/{ns}/recipe/{path}.json", f"removing {rid} by id no longer removes AE2's default")
    if d["type"] == "minecraft:crafting_shapeless":
        got = (d["type"], None, [ingredient(v) for v in d["ingredients"]], (d["result"]["id"], d["result"]["count"]))
    else:
        got = (d["type"], d["pattern"], {k: ingredient(v) for k, v in d["key"].items()},
               (d["result"]["id"], d["result"]["count"]))
    assert got == want, f"{rid}: {AE2_JAR.name} holds {got}"
