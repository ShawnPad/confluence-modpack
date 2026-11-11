"""Pin the catalyst tier in kubejs/server_scripts/tiers/tier7.js (v1.0 spec docs/superpowers/specs/2026-11-11-v1.0-catalyst-tier-design.md
§3; v1.0 plan Tasks 4-7 and 9).

tools/tests/run_server_scripts.js (through kjs.run) loads lib/*.js and tiers/tier7.js into one shared scope and records every
recipes-event call, as test_tier6_space_recipes.py does for tier6.js; its docstring says what that does and does not prove.
The tables below are the spec's rows, with ids read from the jars at plan time (the tier7.js comments cite each). The jar tests
read the pinned jars from .run/server/mods (kjs.pinned_jar): each replaced default must be the jar's default with exactly its
SLOT_CHANGES cells changed. The dump tests (plan Task 9) read the boot's .run/server/kubejs/exported/recipes.json.
SOLE_MAKERS and REMOVED_BY_ID are imported by test_recipe_scripts.py; SHAPED and CUSTOM by test_dump_bodies.py.
"""
import io
import json
import re
import zipfile
from collections import Counter

import pytest

from kjs import EMPTY, ROOT, all_rows, cell_diff, grid, ingredient, jar_json, one, one_maker, pinned_jar, run

TIER7 = "kubejs/server_scripts/tiers/tier7.js"
CATALYST = "kubejs:confluence_catalyst"
HANDLERS = 3   # ServerEvents.recipes handlers in tier7.js: X7.1 (Task 4), X7.2-X7.7 (Task 5), X7.8 (Task 6)

# X7.1 (spec §3.1, A2): the Enchanting Apparatus, the six keys of tier6.js's Astral Focus.
CUSTOM = {
    "confluence:tier7/confluence_catalyst": {
        "type": "ars_nouveau:enchanting_apparatus", "keepNbtOfReagent": False, "sourceCost": 0,
        "reagent": {"item": "kubejs:astral_focus"},
        "pedestalItems": [{"item": "ad_astra:etrium_ingot"}, {"item": "allthemodium:vibranium_allthemodium_alloy_ingot"},
                          {"item": "allthemodium:unobtainium_allthemodium_alloy_ingot"},
                          {"item": "allthemodium:unobtainium_vibranium_alloy_ingot"}, {"item": "minecraft:dragon_egg"},
                          {"item": "ae2:wireless_receiver"}, {"item": "ae2:crafting_unit"}],
        "result": {"count": 1, "id": CATALYST}},
}
# recipe id -> (output, [inputs]): X7.2-X7.7 (Task 5), the terminal and the Tri-Bow (Task 6).
SHAPELESS = {
    # X7.2-X7.7 (spec §3.2, A3, A4): base + catalyst, add-only. Bases: CT §2 (the top non-creative item of each family).
    "confluence:tier7/creative_energy_cube": ("mekanism:creative_energy_cube", ["mekanism:ultimate_energy_cube", CATALYST]),
    "confluence:tier7/creative_chemical_tank": ("mekanism:creative_chemical_tank", ["mekanism:ultimate_chemical_tank", CATALYST]),
    "confluence:tier7/creative_energy_cell": ("ae2:creative_energy_cell", ["ae2:dense_energy_cell", CATALYST]),
    "confluence:tier7/energy_cell_creative": ("powah:energy_cell_creative", ["powah:energy_cell_nitro", CATALYST]),
    "confluence:tier7/creative_source_jar": ("ars_nouveau:creative_source_jar", ["ars_nouveau:source_jar", CATALYST]),
    "confluence:tier7/creative_essence": ("mysticalagradditions:creative_essence",
                                          ["mysticalagriculture:awakened_supremium_essence", CATALYST]),
    "confluence:tier7/creative_vending_upgrade": ("functionalstorage:creative_vending_upgrade",
                                                  ["functionalstorage:netherite_upgrade", CATALYST]),
    # X7.8 terminal (spec §3.4, A6): the smithing default's three inputs + catalyst, on the crafting grid.
    "confluence:tier7/adv_wireless_terminal": ("toms_storage:adv_wireless_terminal",
                                               ["toms_storage:wireless_terminal", "#c:ingots/netherite",
                                                "minecraft:netherite_upgrade_smithing_template", CATALYST]),
    # X7.8 Tri-Bow (spec §3.8, A10): no default; the Snow Queen's own structure's items + catalyst.
    "confluence:tier7/triple_bow": ("twilightforest:triple_bow",
                                    ["twilightforest:ice_bow", "minecraft:bow", "minecraft:bow", "twilightforest:aurora_block", CATALYST]),
}
# recipe id -> (output, pattern, keys): the codex, jet suit and Productivity IV (Task 6).
SHAPED = {
    # X7.8 Ancient Codex (spec §3.3, A5): default TNT / BRB / TLT; the catalyst replaces the top-left magic cloth.
    "confluence:tier7/netherite_spell_book": ("irons_spellbooks:netherite_spell_book", ["KNT", "BRB", "TLT"], {
        "K": CATALYST, "N": "#c:ingots/netherite", "T": "irons_spellbooks:magic_cloth", "B": "irons_spellbooks:blood_vial",
        "R": "irons_spellbooks:ruined_book", "L": "irons_spellbooks:lightning_bottle"}),
    # X7.8 Jet Suit (spec §3.5, A7): default '# #' / TNT / CEC; the catalyst fills the empty top-middle (D107).
    "confluence:tier7/jet_suit": ("ad_astra:jet_suit", ["#K#", "TNT", "CEC"], {
        "#": "#ad_astra:calorite_plates", "K": CATALYST, "T": "ad_astra:calorite_tank", "N": "ad_astra:netherite_space_suit",
        "C": "ad_astra:etrionic_capacitor", "E": "ad_astra:calorite_engine"}),
    # X7.8 Upgrade: Productivity Omega (spec §3.7, A9): default CEC / EBE / CEC; the catalyst replaces the bottom-middle heart.
    "confluence:tier7/upgrade_productivity_4": ("productivelib:upgrade_productivity_4", ["CEC", "EBE", "CKC"], {
        "C": "productivelib:upgrade_productivity_3", "E": "minecraft:heart_of_the_sea", "B": "productivelib:upgrade_block",
        "K": CATALYST}),
}
# The defaults tier7.js removes by id (Task 6).
REMOVED_BY_ID = ["irons_spellbooks:netherite_spell_book", "toms_storage:adv_wireless_terminal", "ad_astra:jet_suit",
                 "productivelib:upgrades/productivity_4"]
# Each output this file pins -> the only recipe ids that may make it, in any server script (test_recipe_scripts.py).
SOLE_MAKERS = {**{body["result"]["id"]: [rid] for rid, body in CUSTOM.items()},
               **{output: [rid] for rid, (output, _) in SHAPELESS.items()},
               **{output: [rid] for rid, (output, _, _) in SHAPED.items()}}


@pytest.fixture(scope="module")
def recorded():
    recorded = run(TIER7)
    assert recorded["errors"] == [] and recorded["other"] == [], (recorded["errors"], recorded["other"])
    return recorded


def test_tier7_handler_count():
    text = (ROOT / TIER7).read_text()
    assert len(re.findall(r"^ServerEvents\.recipes\(", text, re.M)) == HANDLERS


def test_tier7_records_exactly_the_tables(recorded):
    """Every recipe tier7.js records is in CUSTOM, SHAPELESS or SHAPED, with an id; none is missing."""
    ids = sorted(r["id"] for r in all_rows(recorded) if r["file"] == TIER7)
    assert ids == sorted([*CUSTOM, *SHAPELESS, *SHAPED])


def test_tier7_custom_json(recorded):
    for rid, body in CUSTOM.items():
        c = one(recorded, rid)   # exactly one recipe with this id; nothing chained
        assert (c["kind"], c["json"]) == ("custom", body), rid
        assert one_maker(recorded, body["result"]["id"]) == [rid]


def test_tier7_removes_only_its_defaults_by_id(recorded):
    """One filter shape only: {id: <string>}; the ids are exactly REMOVED_BY_ID (spec §3: the X7.8 rows remove by id)."""
    filters = [f["filter"] for f in recorded["filters"] if f["file"] == TIER7]
    odd = [f for f in filters if not (isinstance(f, dict) and set(f) == {"id"} and isinstance(f["id"], str))]
    assert odd == []
    assert sorted(f["id"] for f in filters) == sorted(REMOVED_BY_ID)


def test_tier7_shapeless_rows(recorded):
    """Each SHAPELESS row: one shapeless recipe with that id, output {id, count 1}, the inputs in order, nothing chained, and the
    only maker of its output."""
    for rid, (output, inputs) in SHAPELESS.items():
        c = one(recorded, rid)
        assert c["kind"] == "shapeless", (rid, c["kind"])
        assert (c["output"], c["ingredients"]) == ({"id": output, "count": 1}, inputs), rid
        for v in c["ingredients"]:
            ingredient(v)   # '#tag' or an item id, never '<undefined>'
        assert one_maker(recorded, output) == [rid], output


# ---- the jar defaults (plan Task 6) ----
# recipe id -> (pinned jar: (prefix, name, pw.toml), nested jar entry or None, default recipe entry). Read at plan time.
PB_JAR = ("productivebees-", "productivebees-1.21.1-13.13.5.jar", "productivebees.pw.toml")
DEFAULTS = {
    "confluence:tier7/netherite_spell_book": (("irons_spellbooks-", "irons_spellbooks-1.21.1-3.16.3.jar",
                                               "irons-spells-n-spellbooks.pw.toml"), None,
                                              "data/irons_spellbooks/recipe/netherite_spell_book.json"),
    "confluence:tier7/jet_suit": (("adastra-", "adastra-1.21.1-1.16.25-neoforge.jar", "ad-astra.pw.toml"), None,
                                  "data/ad_astra/recipe/jet_suit.json"),
    "confluence:tier7/upgrade_productivity_4": (PB_JAR, "META-INF/jarjar/productivelib-1.21.1-0.2.0.jar",
                                                "data/productivelib/recipe/upgrades/productivity_4.json"),
}
# Spec §3's slot changes to each jar default, and nothing else: recipe id -> {(row, col): (default cell, our cell)}.
SLOT_CHANGES = {
    "confluence:tier7/netherite_spell_book": {(0, 0): ("irons_spellbooks:magic_cloth", CATALYST)},
    "confluence:tier7/jet_suit": {(0, 1): (EMPTY, CATALYST)},
    "confluence:tier7/upgrade_productivity_4": {(2, 1): ("minecraft:heart_of_the_sea", CATALYST)},
}


def default_recipe(rid):
    (prefix, name, pw), nested, entry = DEFAULTS[rid]
    with zipfile.ZipFile(pinned_jar(prefix, name, pw)) as jar:
        if nested is None:
            return jar_json(jar, entry, "SLOT_CHANGES no longer describe the default")
        try:
            inner = io.BytesIO(jar.read(nested))
        except KeyError:
            pytest.fail(f"id moved: {name} has no {nested}")
    with zipfile.ZipFile(inner) as jar:
        return jar_json(jar, entry, "SLOT_CHANGES no longer describe the default")


@pytest.mark.parametrize("rid", sorted(SLOT_CHANGES))
def test_x78_shaped_is_the_jar_default_plus_one_cell(recorded, rid):
    output = SHAPED[rid][0]
    default = default_recipe(rid)
    assert default["type"] == "minecraft:crafting_shaped" and default["result"]["id"] == output, default
    assert default["result"].get("count", 1) == 1, default
    ours = one(recorded, rid)
    assert ours["kind"] == "shaped" and (ours["output"], ours["pattern"], ours["key"]) == (
        {"id": output, "count": 1}, SHAPED[rid][1], SHAPED[rid][2]), rid
    before = grid(default["pattern"], default["key"], json_only=True)
    after = grid(ours["pattern"], ours["key"])
    # Every row and column of ours holds an item, so vanilla's ShapedRecipePattern.shrink trims nothing (tier6.js note).
    assert all(any(after[r, c] for c in range(3)) and any(after[c, r] for c in range(3)) for r in range(3)), ours["pattern"]
    assert cell_diff(before, after) == SLOT_CHANGES[rid], f"{rid}: cells that differ from the jar default, as (default, ours)"
    assert one_maker(recorded, output) == [rid]


def test_terminal_is_the_smithing_default_plus_catalyst():
    """A6: Tom's default is a smithing transform (base, addition, template); ours takes the same three plus the catalyst. The
    addition is written as the c: tag ours uses (the dump shows Almost Unified rewriting the jar's netherite ingot to it)."""
    with zipfile.ZipFile(pinned_jar("toms_storage-", "toms_storage-1.21-2.4.2.jar", "toms-storage.pw.toml")) as jar:
        d = jar_json(jar, "data/toms_storage/recipe/adv_wireless_terminal.json", "A6 no longer describes Tom's default")
    assert d["type"] == "minecraft:smithing_transform" and d["result"]["id"] == "toms_storage:adv_wireless_terminal", d
    default_inputs = [ingredient(d[k], json_only=True) for k in ("base", "addition", "template")]
    assert default_inputs == ["toms_storage:wireless_terminal", "minecraft:netherite_ingot",
                              "minecraft:netherite_upgrade_smithing_template"]
    ours = SHAPELESS["confluence:tier7/adv_wireless_terminal"][1]
    assert Counter(ours) == Counter(["toms_storage:wireless_terminal", "#c:ingots/netherite",
                                     "minecraft:netherite_upgrade_smithing_template", CATALYST])


def test_tri_bow_has_no_jar_recipe():
    """A10: Twilight Forest ships no recipe for the Tri-Bow, so ours removes nothing."""
    with zipfile.ZipFile(pinned_jar("twilightforest-", "twilightforest-1.21.1-4.8.3345-universal.jar",
                                    "the-twilight-forest.pw.toml")) as jar:
        hits = [n for n in jar.namelist() if n.startswith("data/") and "/recipe/" in n and "triple_bow" in n]
    assert hits == []


def test_x78_shaped_rows(recorded):
    """Pins the shapes without a booted server; the jar test below skips when there is none."""
    for rid, (output, pattern, keys) in SHAPED.items():
        c = one(recorded, rid)
        assert c["kind"] == "shaped", (rid, c["kind"])
        assert (c["output"], c["pattern"], c["key"]) == ({"id": output, "count": 1}, pattern, keys), rid


# ---- the boot dump (plan Task 9; spec §3.9) ----
DRILL_ID = "industrialforegoing:dissolution_chamber/infinity_drill"
DRILL_FILE = ROOT / "kubejs" / "data" / "industrialforegoing" / "recipe" / "dissolution_chamber" / "infinity_drill.json"
# Almost Unified's load-time rewrite of the drill's inputs, read from the 0.3 dump row of IF's default at plan time.
AU_REWRITES = {json.dumps({"item": "minecraft:diamond_block"}, sort_keys=True): {"tag": "c:storage_blocks/diamond"}}
# Spec §5 / CT §2: every creative item family in the pack (A14's FORBIDDEN alternatives).
CREATIVE = re.compile(r"mekanism:creative_(energy_cube|chemical_tank|fluid_tank|bin)|ae2:creative_(energy_cell|storage_cell)"
                      r"|powah:energy_cell_creative|ars_nouveau:creative_(source_jar|spell_book)|mysticalagradditions:creative_essence"
                      r"|functionalstorage:(creative_vending_upgrade|max_storage_upgrade)|mysticalagriculture:creative_soulium_dagger"
                      r"|sophisticated(backpacks|storage):(survival_)?infinity_upgrade|twilightforest:glass_sword")
# CT §2: its input is the creative spell book itself (type ars_nouveau:dye), so it creates nothing.
CREATIVE_EXEMPT = {"ars_nouveau:dye_creative_spell_book"}


@pytest.fixture(scope="module")
def dump_rows():
    # Imported here, not at the top: test_dump_bodies imports this module (its tier-7 tables), so a top-level import would be
    # circular whichever module pytest collects first.
    from test_dump_bodies import DUMP, newest_kubejs_file, staleness
    if not DUMP.is_file():
        pytest.skip(f"{DUMP} does not exist (no server has been booted from this clone)")
    stale = staleness(DUMP.stat().st_mtime, newest_kubejs_file())
    if stale:
        pytest.fail(stale)
    return {r["id"]: r for r in json.loads(DUMP.read_text())}


def body(rows, rid):
    assert rid in rows and rows[rid].get("json"), f"{rid} has no body in the dump"
    return json.loads(rows[rid]["json"])


def unwrap_au(b):
    """The body with Almost Unified's runtime form undone: each almostunified:conditional condition replaced by its
    original_conditions, and AU_REWRITES applied to each input."""
    b = json.loads(json.dumps(b))
    conds = []
    for c in b.get("neoforge:conditions", []):
        conds.extend(c["original_conditions"] if c.get("type") == "almostunified:conditional" else [c])
    if "neoforge:conditions" in b:
        b["neoforge:conditions"] = conds
    if "input" in b:
        b["input"] = [AU_REWRITES.get(json.dumps(i, sort_keys=True), i) for i in b["input"]]
    return b


def test_every_x72_to_x78_body_holds_the_catalyst(dump_rows):
    for rid in [*SHAPELESS, *SHAPED, DRILL_ID]:
        assert CATALYST in dump_rows[rid]["json"], rid


def test_catalyst_body_is_a2(dump_rows):
    b = body(dump_rows, "confluence:tier7/confluence_catalyst")
    want = CUSTOM["confluence:tier7/confluence_catalyst"]
    assert b["type"] == want["type"] and b["sourceCost"] == 0 and b["reagent"] == want["reagent"], b
    assert Counter(ingredient(i, json_only=True) for i in b["pedestalItems"]) == Counter(
        ingredient(i, json_only=True) for i in want["pedestalItems"]), b["pedestalItems"]


def test_shapeless_bodies_are_the_table(dump_rows):
    """The loaded type of a gate.shapeless row is read from the dump, not assumed; inputs and result must be the table's."""
    for rid, (output, inputs) in SHAPELESS.items():
        b = body(dump_rows, rid)
        assert b["type"] in ("kubejs:shapeless", "minecraft:crafting_shapeless"), (rid, b["type"])
        assert Counter(ingredient(i, json_only=True) for i in b["ingredients"]) == Counter(inputs), rid
        assert b["result"]["id"] == output and b["result"].get("count", 1) == 1, (rid, b["result"])


def test_drill_override_is_spec_36_and_loaded_as_written(dump_rows):
    ours = json.loads(DRILL_FILE.read_text())
    assert ours["inputFluid"] == {"amount": 2000, "fluid": "industrialforegoing:pink_slime"} and ours["processingTime"] == 400
    assert ours["output"] == {"components": {"industrialforegoing:infinity_can_charge": True,
                                             "industrialforegoing:infinity_item_power": 0,
                                             "industrialforegoing:infinity_item_selected_tier": "poor",
                                             "industrialforegoing:infinity_item_special": False},
                              "count": 1, "id": "industrialforegoing:infinity_drill"}
    assert Counter(ingredient(i, json_only=True) for i in ours["input"]) == Counter({
        "minecraft:diamond_block": 3, "minecraft:diamond_shovel": 1, "industrialforegoing:range_addon_tier_11": 1,
        "#c:gears/gold": 2, CATALYST: 1})
    loaded = unwrap_au(body(dump_rows, DRILL_ID))
    written = unwrap_au(ours)
    for key in sorted(set(written) | set(loaded)):
        if key == "input":
            assert Counter(json.dumps(i, sort_keys=True) for i in loaded[key]) == Counter(
                json.dumps(i, sort_keys=True) for i in written[key]), loaded[key]
        else:
            assert loaded.get(key) == written.get(key), key


def test_no_stray_creative_producer(dump_rows):
    """No dump row makes a creative id unless gates.yaml sole_producers names it as that id's producer (CREATIVE_EXEMPT aside)."""
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    from check_recipes import MANIFEST, load_sole_producers, products
    sole = load_sole_producers(MANIFEST)
    stray, seen = [], set()
    for rid, row in dump_rows.items():
        if not row.get("json") or rid in CREATIVE_EXEMPT:
            continue
        for item in products(json.loads(row["json"]))[0]:
            if CREATIVE.fullmatch(item):
                seen.add(item)
                if rid not in sole.get(item, ("item", []))[1]:
                    stray.append((rid, item))
    assert stray == []
    # The scan is live: it saw the seven creative outputs, and the exemption names a row that still exists.
    assert {o for _, (o, _) in SHAPELESS.items() if CREATIVE.fullmatch(o)} <= seen
    assert len({o for o in seen if o in sole}) >= 7
    assert all(dump_rows.get(rid, {}).get("json") for rid in CREATIVE_EXEMPT), "the exempt row is gone from the dump"
