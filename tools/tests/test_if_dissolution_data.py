"""The Industrial Foregoing Dissolution Chamber recipes the pack ships as datapack JSON (pack spec §3 T2.1 and T4.1; v0.3 spec §5
T5.2 and X5.2). Each must fit IF's codec and the pack's conventions, the two v0.3 files must be their spec rows, and each
in-place override must still be IF's jar default with only our swaps.

Codec, from javap on industrialforegoing-1.21-3.6.39.jar!com/buuz135/industrial/recipe/DissolutionChamberRecipe
(lambda$static$5; research/phase7-tier5-ids.md §3.2):
  input          Ingredient.CODEC.listOf(0, 8), required  -> at most 8 entries; a 9th fails to parse (D114)
  inputFluid     SizedFluidIngredient.FLAT_CODEC, required -> {"amount": N, "fluid": id} or {"amount": N, "tag": id}; the codec
                 defaults a missing amount to 1000 (neoforge-21.1.250-universal.jar SizedFluidIngredient), the pack always writes it
  processingTime Codec.INT, required
  output         ItemStack.CODEC, optional                -> {"count": N, "id": id}
  outputFluid    FluidStack.CODEC, optional               -> key "id", not "fluid"
Matching is a multiset (every non-empty 1-item slot is claimed by one ingredient), so four of an item are four entries.

Why these files are checked here, before any boot. The recipe dump (server_scripts/dump.js) is taken inside the recipes event,
before any codec runs, so a file the codec rejects still has its row in the dump and tools/check_recipes.py still finds its id.
KubeJS's "failed recipes" count covers only recipes its scripts add or change (RecipesKubeEvent.handleFailedRecipe counts only
JSON that carries _kubejs_changed_marker). Vanilla drops the file and logs "Parsing error loading recipe <id>" in
logs/latest.log (RecipeManager.apply); tools/server_boot.sh fails the boot on that line. A broken in-place override also takes
IF's default with it, because both share the id, and leaves the product with no recipe at all.
"""
import json
import zipfile
from collections import Counter

import pytest

from kjs import ROOT, jar_json, pinned_jar
from kjs import ingredient as kjs_ingredient

DATA = ROOT / "kubejs" / "data"
IF_JAR = "industrialforegoing-1.21-3.6.39.jar"
TYPE = "industrialforegoing:dissolution_chamber"
FRAMES = "industrialforegoing/recipe/dissolution_chamber/"
SIMPLE, ADVANCED, SUPREME = (FRAMES + n + "_machine_frame.json" for n in ("simple", "advanced", "supreme"))
UNOB_VIB = "confluence/recipe/tier5/unobtainium_vibranium_alloy_ingot.json"

# In-place overrides: our file at IF's own path and id replaces the jar's default. Path under kubejs/data -> (default inputs
# ours drops, inputs ours adds). Every key but `input` must equal the default's. The jar is pinned; a new IF version means
# re-reading each default and this table by hand.
OVERRIDES = {
    # T2.1 (pack spec §3, "IF default + one Ars essence"): one of the two nether bricks becomes an elemental essence.
    SIMPLE: (Counter({"minecraft:nether_brick": 1}), Counter({"#confluence:ars_essences": 1})),
    # T4.1 (D91): both netherite scraps become Vibranium ingots and the first gold ingot the Lightning Upgrade Orb.
    ADVANCED: (Counter({"minecraft:netherite_scrap": 2, "#c:ingots/gold": 1}),
               Counter({"#c:ingots/vibranium": 2, "irons_spellbooks:lightning_upgrade_orb": 1})),
    # T5.2 (D114): both netherite ingots become Unobtainium ingots; diamond gem, diamond gear and diamond gem become a nitro
    # crystal, an ultimate control circuit and an Unobtainium-Allthemodium alloy ingot (research/phase7-tier5-ids.md §3.1).
    SUPREME: (Counter({"minecraft:netherite_ingot": 2, "#c:gems/diamond": 2, "#c:gears/diamond": 1}),
              Counter({"#c:ingots/unobtainium": 2, "powah:crystal_nitro": 1, "mekanism:ultimate_control_circuit": 1,
                       "allthemodium:unobtainium_allthemodium_alloy_ingot": 1})),
}


def dissolution_files():
    found = {}
    for path in sorted(DATA.glob("*/recipe/**/*.json")):
        body = json.loads(path.read_text())
        if body.get("type") == TYPE:
            found[path.relative_to(DATA).as_posix()] = body
    return found


def ingredient(entry):
    """kjs.ingredient for datapack JSON: exactly {"item": id} or {"tag": id}, never a bare string."""
    return kjs_ingredient(entry, json_only=True)


def test_every_pack_dissolution_recipe_fits_codec_and_pack_conventions():
    """IF's codec plus the pack's own conventions, which are stricter: `amount` is always written (the codec defaults it), a
    recipe has an output (the codec makes both optional), and each ingredient is one {"item"} or {"tag"} object. The codec
    also takes a list or a custom `type` ingredient: neoforge-21.1.250-universal.jar CraftingHelper.makeIngredientCodec is
    Codec.either(Ingredient.LIST_CODEC, makeIngredientMapCodec()), and the map codec dispatches `type` over
    NeoForgeRegistries.INGREDIENT_TYPES."""
    files = dissolution_files()
    assert SUPREME in files and UNOB_VIB in files, sorted(files)
    for path, body in files.items():
        assert 0 <= len(body["input"]) <= 8, path
        for entry in body["input"]:
            ingredient(entry)
        fluid = body["inputFluid"]
        assert isinstance(fluid["amount"], int) and fluid["amount"] > 0, path
        assert set(fluid) in ({"amount", "fluid"}, {"amount", "tag"}), path
        assert isinstance(body["processingTime"], int) and body["processingTime"] > 0, path
        assert "output" in body or "outputFluid" in body, path
        if "output" in body:
            assert "id" in body["output"] and set(body["output"]) <= {"id", "count"}, path
        if "outputFluid" in body:
            assert "id" in body["outputFluid"] and "fluid" not in body["outputFluid"], path


def test_supreme_frame_override_is_spec_t52():
    """Spec §5 T5.2 and D114: IF's default id, its fluid, time and condition kept; 8 items with one nitro crystal. IF's default
    is industrialforegoing-1.21-3.6.39.jar!data/industrialforegoing/recipe/dissolution_chamber/supreme_machine_frame.json
    (research/phase7-tier5-ids.md §3.1); test_override_is_the_jar_default_plus_our_swaps pins ours against it."""
    body = dissolution_files()[SUPREME]
    assert set(body) == {"neoforge:conditions", "type", "input", "inputFluid", "output", "processingTime"}, sorted(body)
    assert Counter(ingredient(e) for e in body["input"]) == Counter({
        "#industrialforegoing:machine_frame/advanced": 1, "#c:plastics": 2, "powah:crystal_nitro": 1,
        "mekanism:ultimate_control_circuit": 1, "#c:ingots/unobtainium": 2,
        "allthemodium:unobtainium_allthemodium_alloy_ingot": 1,
    })
    assert body["inputFluid"] == {"amount": 135, "fluid": "industrialforegoing:ether_gas"}
    assert body["output"] == {"count": 1, "id": "industrialforegoing:machine_frame_supreme"}
    assert body["processingTime"] == 300
    assert body["neoforge:conditions"] == [
        {"type": "neoforge:item_exists", "item": "industrialforegoing:machine_frame_supreme"}]


def test_unobtainium_vibranium_alloy_is_spec_x52():
    """Spec §5 X5.2, D105, D115: four pink slime, one of each tier ingot, one Piglich heart; 100 mB soul lava, 200 ticks."""
    body = dissolution_files()[UNOB_VIB]
    assert set(body) == {"type", "input", "inputFluid", "output", "processingTime"}, sorted(body)
    assert Counter(ingredient(e) for e in body["input"]) == Counter({
        "industrialforegoing:pink_slime": 4, "#c:ingots/vibranium": 1, "#c:ingots/unobtainium": 1,
        "allthemodium:piglich_heart": 1,
    })
    assert body["inputFluid"] == {"amount": 100, "fluid": "allthemodium:soul_lava"}
    assert body["output"] == {"count": 1, "id": "allthemodium:unobtainium_vibranium_alloy_ingot"}
    assert body["processingTime"] == 200


@pytest.mark.parametrize("rel", sorted(OVERRIDES))
def test_override_is_the_jar_default_plus_our_swaps(rel):
    """Each in-place override is IF's jar default at the same path, with only the OVERRIDES swaps. It fails when IF moves the id
    (ours would then add a second recipe instead of replacing one) or changes the default (ours would silently drop the change)."""
    # kjs.pinned_jar: mods/industrial-foregoing.pw.toml ships IF_JAR; skip only when .run/server/mods does not exist; fail on
    # any other 'industrialforegoing-*.jar' (the hyphen right after the mod id, so an add-on jar with a longer name does not
    # match). OVERRIDES were read from IF_JAR.
    with zipfile.ZipFile(pinned_jar("industrialforegoing-", IF_JAR, "industrial-foregoing.pw.toml")) as jar:
        default = jar_json(jar, "data/" + rel, f"kubejs/data/{rel} no longer replaces IF's default")
    ours = json.loads((DATA / rel).read_text())
    lose, add = OVERRIDES[rel]
    rest = lambda body: {k: v for k, v in body.items() if k != "input"}
    assert rest(ours) == rest(default), f"{rel}: a key other than `input` differs from {IF_JAR}'s default"
    have = Counter(map(ingredient, default["input"]))
    assert not lose - have, f"{rel}: {IF_JAR}'s default no longer holds {dict(lose - have)}"
    assert have - lose + add == Counter(map(ingredient, ours["input"])), f"{rel}: not {IF_JAR}'s default with our swaps"


# ---- v0.3 Task 8c: the two crafting-grid overrides at IF's own ids (pity frame, Dissolution Chamber block) ----
# Each is IF's jar default at the same path with only the documented swaps, written as edits to the default so a new IF
# default fails here instead of being silently replaced by ours. Where the swaps are documented:
#   T0.4 pity frame: pack spec (docs/superpowers/specs/2026-09-11-pack-build-design.md §3, row T0.4: "IF default +
#     #c:ingots/osmium x4 + Powah energized steel x4") and the v0.1 plan (docs/superpowers/plans/2026-09-11-v0.1-alpha.md,
#     Task 10 Step 1: "pattern keeps the redstone block centre, swaps logs for osmium and iron for energized steel"). That
#     step's file body, which kubejs/data ships verbatim, also leaves out the default's neoforge:conditions (item_exists for
#     IF's own machine_frame_pity, true whenever IF loads), so the drop is listed as a swap.
#   T2.2 Dissolution Chamber: pack spec §3 row T2.2 ("IF default + Mekanism basic control circuit") and the v0.1 plan's
#     Task 11 Step 2 ("T2.2 swaps one gold for a basic circuit"; its file body has the bottom row's second gold ingot as
#     #c:circuits/basic, key X).
# Defaults: industrialforegoing-1.21-3.6.39.jar!data/industrialforegoing/recipe/{machine_frame_pity,dissolution_chamber}.json
# (research/phase6-tier0-2-ids.md §B quotes both).
PITY = "industrialforegoing/recipe/machine_frame_pity.json"
CHAMBER = "industrialforegoing/recipe/dissolution_chamber.json"
GRID_OVERRIDES = {
    # rename: default key letter -> (our letter, our ingredient), every cell of it; cells: (row, col) -> (letter, ingredient);
    # drop: top-level keys of the default ours leaves out.
    PITY: {"rename": {"W": ("O", {"tag": "c:ingots/osmium"}), "I": ("E", {"item": "powah:steel_energized"})},
           "cells": {}, "drop": ["neoforge:conditions"]},
    CHAMBER: {"rename": {}, "cells": {(2, 2): ("X", {"tag": "c:circuits/basic"})}, "drop": []},
}


def with_swaps(default, swaps):
    """The default recipe body with the swaps applied: a key letter renamed (and its ingredient replaced) in every cell, single
    cells replaced, top-level keys dropped. A key letter no cell uses any more is removed, as a hand-written file would."""
    body = json.loads(json.dumps(default))
    pattern = [list(row) for row in body["pattern"]]
    for old, (new, ing) in swaps["rename"].items():
        assert any(old in row for row in pattern), f"the default no longer uses key {old!r}"
        pattern = [[new if ch == old else ch for ch in row] for row in pattern]
        body["key"].pop(old)
        body["key"][new] = ing
    for (r, c), (letter, ing) in swaps["cells"].items():
        assert pattern[r][c] != " ", f"the default's cell {(r, c)} is empty"
        pattern[r][c] = letter
        body["key"][letter] = ing
    body["pattern"] = ["".join(row) for row in pattern]
    used = {ch for row in body["pattern"] for ch in row}
    body["key"] = {k: v for k, v in body["key"].items() if k in used}
    for k in swaps["drop"]:
        assert k in body, f"the default no longer has {k!r}"
        body.pop(k)
    return body


def if_default(rel):
    with zipfile.ZipFile(pinned_jar("industrialforegoing-", IF_JAR, "industrial-foregoing.pw.toml")) as jar:
        return jar_json(jar, "data/" + rel, f"kubejs/data/{rel} no longer replaces IF's default")


@pytest.mark.parametrize("rel", sorted(GRID_OVERRIDES))
def test_grid_override_is_the_jar_default_plus_our_swaps(rel):
    assert json.loads((DATA / rel).read_text()) == with_swaps(if_default(rel), GRID_OVERRIDES[rel]), (
        f"kubejs/data/{rel} is not {IF_JAR}'s default with the documented swaps (GRID_OVERRIDES)")


def test_grid_override_drift_is_caught():
    """A changed default, an extra swap in ours, or a swap applied to the wrong cell all fail the comparison."""
    default = {"type": "minecraft:crafting_shaped", "category": "misc", "pattern": ["PCP", "BMB", "GDG"],
               "key": {k: {"item": "m:" + k.lower()} for k in "PCBMGD"}, "result": {"count": 1, "id": "m:out"}}
    swaps = {"rename": {}, "cells": {(2, 2): ("X", {"tag": "c:circuits/basic"})}, "drop": []}
    ours = dict(default, pattern=["PCP", "BMB", "GDX"], key=dict(default["key"], X={"tag": "c:circuits/basic"}))
    assert with_swaps(default, swaps) == ours
    assert with_swaps(dict(default, category="building"), swaps) != ours                       # the default changed
    assert with_swaps(default, swaps) != dict(ours, pattern=["PCP", "BXB", "GDX"])             # ours swaps one more cell
    assert with_swaps(default, dict(swaps, cells={(2, 0): ("X", {"tag": "c:circuits/basic"})})) != ours   # the wrong cell
    renamed = with_swaps(default, {"rename": {"G": ("O", {"tag": "c:ingots/osmium"})}, "cells": {}, "drop": []})
    assert renamed["pattern"] == ["PCP", "BMB", "ODO"] and "G" not in renamed["key"]
    with pytest.raises(AssertionError):
        with_swaps(default, {"rename": {"W": ("O", {})}, "cells": {}, "drop": []})            # key gone from the default
