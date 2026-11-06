"""v0.3 Task 7: the AE2 recipes in tiers/tier5.js and tiers/tier6.js match the v0.3 spec's rows S5.1–S5.3 (§5) and
S6.1–S6.2 (§6), decisions D107 and D117.

tools/tests/run_server_scripts.js (the shared runner, through kjs.run) loads lib/*.js, tiers/tier5.js and tiers/tier6.js into
ONE vm context, as KubeJS 2101 gives every server script one shared scope, runs each ServerEvents.recipes handler against an
event that records what it adds and removes, and prints the record as JSON. The tests compare each AE2 recipe with the spec's shape and literal ids before any boot, because a
wrong key value does not always fail the boot. What each kind of slip does (javap -p -c on kubejs-neoforge-2101.7.2-build.377.jar;
hasNoItems on NeoForge's patched Ingredient in neoforge-21.1.250-server.jar):
  - null, or an ingredient KubeJS counts as empty: silent. kubejs:shaped's schema (data/minecraft/kubejs/recipe_schema/
    shaped.json) runs the kubejs:key_pattern_cleanup post-processor, whose default component is IngredientComponent.INGREDIENT.
    KeyPatternCleanupPostProcessor.process drops each key whose value is null or component.isEmpty, and turns that symbol's
    cells into spaces, so the recipe loads cheaper, with no error.
  - a tag that is unbound or empty: silent too. IngredientComponent.isEmpty is Ingredient.isEmpty() || hasNoItems(), and
    hasNoItems is true when the only stack is the "Empty Tag: …" barrier that Ingredient$TagValue.getItems gives for an empty
    tag. tools/check_tags.py, run after the boot, fails on it; the six tags here all come from lib/ids.js and bind one item each.
  - '', '-', 'air', 'minecraft:air' (IngredientWrapper.parseString), a blank string or any string starting with '-'
    (IngredientWrapper.read): Ingredient.EMPTY, silent. The literal comparison below catches these, and an undefined IDS key,
    which the harness records as '<undefined>'.
  - an unknown item id: not silent. IngredientWrapper.read resolves a plain id with ItemWrapper.findItem, which returns
    DataResult.error("Item with ID … does not exist!"); IngredientWrapper.wrap (the type wrapper BuiltinKubeJSPlugin registers
    for Ingredient) throws it as KubeRuntimeException "Failed to read ingredient from …"; RecipeTypeFunction.call catches it
    and logs it with ConsoleJS.SERVER.error, a KubeJS ERROR line that fails tools/server_boot.sh.

node runs V8, not the pack's Rhino, so this test pins the recipes the handlers record, not that the files load in KubeJS;
tools/tests/test_rhino_hazards.py lints the known Rhino trap. The load proof is tools/server_boot.sh (its KubeJS ERROR check and
its check for "Parsing error loading recipe" in logs/latest.log) and the boot's "with 0 failed recipes" line. node must be on
PATH: kjs.run asserts it, so this test runs rather than skips. The last two tests read AE2's ten defaults (DEFAULTS) and the
five defaults this task keeps (KEPT) from appliedenergistics2-19.2.17.jar in .run/server/mods (kjs.pinned_jar, which also
checks mods/ae2.pw.toml); they skip only when that folder does not exist, and fail on any other AE2 jar or on a default that
moved or changed. tools/gates.yaml asserts the same ids at boot: the ten under `removed:`, the five kept ones under `gates:`.
SOLE_MAKERS (each pinned output -> the one recipe id that may make it) is imported by test_recipe_scripts.py, which checks it
over every server script.
"""
import zipfile

import pytest

from kjs import ingredient, jar_json, one, one_maker, pinned_jar, run

TIER5 = "kubejs/server_scripts/tiers/tier5.js"
TIER6 = "kubejs/server_scripts/tiers/tier6.js"
AE2_JAR = "appliedenergistics2-19.2.17.jar"

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

# AE2's ten defaults this task removes by id, each the only recipe for its item except the provider, as
# AE2_JAR!data/ae2/recipe/<path>.json held them when this test was written (AE2 §1.2; the tier5.js and tier6.js comments
# describe them): default id -> (the confluence: recipe that replaces it, type, pattern, key with tags written '#tag', result
# (id, count)). The shapeless terminal has no pattern; its key is the ingredient list, in the jar's order.
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
REMOVED_BY_ID = list(DEFAULTS)
# Defaults this task must leave alone: the provider's part <-> block conversions (AE2 §4.5) and the D117 defaults.
KEPT = [
    "ae2:network/blocks/pattern_providers_interface_alt", "ae2:network/blocks/pattern_providers_interface_part",
    "ae2:network/crafting/molecular_assembler", "ae2:network/parts/terminals_pattern_encoding",
    "ae2:network/parts/terminals_crafting",
]
# The two conversions, verbatim from AE2_JAR (AE2 §1.2). _part is the only recipe that makes the cable pattern provider, and it
# consumes a provider block; _alt turns that part back into the block. So _alt returns a block that already paid ostrum
# (confluence:tier6/pattern_provider) and is not a bypass, as long as both bodies stay what they are here.
CONVERSIONS = {
    "ae2:network/blocks/pattern_providers_interface_part": {
        "type": "minecraft:crafting_shapeless", "category": "misc", "ingredients": [{"item": "ae2:pattern_provider"}],
        "result": {"count": 1, "id": "ae2:cable_pattern_provider"}},
    "ae2:network/blocks/pattern_providers_interface_alt": {
        "type": "minecraft:crafting_shapeless", "category": "misc", "ingredients": [{"item": "ae2:cable_pattern_provider"}],
        "result": {"count": 1, "id": "ae2:pattern_provider"}},
}


# Each output this file pins -> the only recipe ids that may make it, in any server script (test_recipe_scripts.py).
SOLE_MAKERS = {output: [rid] for rid, (output, _, _) in EXPECTED.items()}


@pytest.fixture(scope="module")
def recorded():
    return run(TIER5, TIER6)


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
    for v in keys.values():
        ingredient(v)   # '#tag' or an item id: not '<inert>' or any other stand-in


@pytest.mark.parametrize("rid", sorted(EXPECTED))
def test_ae2_recipe_matches_spec(recorded, rid):
    """The spec's shape and ids, and one maker: no other shaped, shapeless or custom recipe in these scripts makes the item,
    with or without an id (each default's removal leaves this one as the only recipe, except the provider's _alt conversion,
    KEPT). kjs.products reads a custom recipe's json.result, json.output, each element of json.results and any other
    result/output key. Nothing is chained on the recipe."""
    r = one(recorded, rid)   # exactly one recipe with this id; nothing chained, no extra arguments
    assert r["kind"] == "shaped"
    assert_vanilla_shape(r["pattern"], r["key"])
    output, pattern, keys = EXPECTED[rid]
    # gate.shaped passes Item.of(output); the runner records that stack as {id, count} (plus `components` for an 'id[...]'
    # string).
    assert (r["output"], r["pattern"], r["key"]) == ({"id": output, "count": 1}, pattern, keys)
    makers = one_maker(recorded, output)
    assert makers == [rid], f"{output} is made by {makers}"


def test_ae2_defaults_removed_by_id_only(recorded):
    """Two filter shapes only, as test_tier6_space_recipes.py allows: {id: <a string>} and {output: <a string outside ae2:>}
    (Task 6's Ad Astra machines). Anything else fails: a filter by mod, type or input, a regex id (the harness writes it as
    {"RegExp": …}), a bare string, an ae2: output or tag, or a combined filter. The ae2: ids removed are exactly the ten
    defaults, so no KEPT default and no other AE2 recipe goes. Nor may these scripts make any other recipes-event call
    (replaceInput, replaceOutput and the like), which could change an AE2 recipe without removing it."""
    def by_id(f):
        return isinstance(f, dict) and set(f) == {"id"} and isinstance(f["id"], str)

    def by_other_output(f):
        return isinstance(f, dict) and set(f) == {"output"} and isinstance(f["output"], str) and "ae2:" not in f["output"]

    filters = [e["filter"] for e in recorded["filters"]]
    odd = [f for f in filters if not by_id(f) and not by_other_output(f)]
    assert odd == [], odd
    assert sorted(f["id"] for f in filters if by_id(f) and f["id"].startswith("ae2:")) == sorted(REMOVED_BY_ID)
    assert recorded["other"] == [], recorded["other"]


def ae2_jar():
    """AE2_JAR, after kjs.pinned_jar's checks: mods/ae2.pw.toml ships it, the test skips only when no server has been booted
    from this clone, and any other AE2 jar fails ('appliedenergistics2-*.jar' needs the hyphen right after the mod id, so an
    add-on jar with a longer name does not match). DEFAULTS, KEPT and CONVERSIONS were read from it."""
    return pinned_jar("appliedenergistics2-", AE2_JAR, "ae2.pw.toml")


@pytest.mark.parametrize("rid", REMOVED_BY_ID)
def test_ae2_default_matches_the_jar(rid):
    """Each default this task removes by id is still at that id in AE2_JAR, and still the recipe DEFAULTS (and the tier5.js /
    tier6.js comments) describe, making the item its confluence: replacement makes. A moved id would leave the default
    loaded beside ours; a changed default would make the comments' "the default's ... stays" untrue."""
    ours, want = DEFAULTS[rid][0], DEFAULTS[rid][1:]
    assert want[3][0] == EXPECTED[ours][0], (rid, want[3], ours, EXPECTED[ours][0])
    ns, path = rid.split(":")
    with zipfile.ZipFile(ae2_jar()) as jar:
        d = jar_json(jar, f"data/{ns}/recipe/{path}.json", f"removing {rid} by id no longer removes AE2's default")
    if d["type"] == "minecraft:crafting_shapeless":
        got = (d["type"], None, [ingredient(v, json_only=True) for v in d["ingredients"]],
               (d["result"]["id"], d["result"]["count"]))
    else:
        got = (d["type"], d["pattern"], {k: ingredient(v, json_only=True) for k, v in d["key"].items()},
               (d["result"]["id"], d["result"]["count"]))
    assert got == want, f"{rid}: {AE2_JAR} holds {got}"


@pytest.mark.parametrize("rid", KEPT)
def test_ae2_kept_default_is_in_the_jar(rid):
    """Each default this task leaves loaded is still at its id in AE2_JAR, so tools/gates.yaml's `gates:` row for it keeps
    meaning "AE2's own recipe still loads". The two provider conversions must also keep their bodies (CONVERSIONS): if _part
    stopped consuming a provider block, _alt would turn into a way round the ostrum in confluence:tier6/pattern_provider."""
    ns, path = rid.split(":")
    with zipfile.ZipFile(ae2_jar()) as jar:
        d = jar_json(jar, f"data/{ns}/recipe/{path}.json", f"{rid}, which this task keeps loaded, is gone or renamed")
    if rid in CONVERSIONS:
        assert d == CONVERSIONS[rid], f"{rid}: {AE2_JAR} holds {d}"
