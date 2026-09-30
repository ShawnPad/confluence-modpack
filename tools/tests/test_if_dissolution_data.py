"""The Industrial Foregoing Dissolution Chamber recipes the pack ships as datapack JSON must fit IF's codec (v0.3 spec §5 T5.2, X5.2).

Codec, from javap on industrialforegoing-1.21-3.6.39.jar!com/buuz135/industrial/recipe/DissolutionChamberRecipe
(lambda$static$5; research/phase7-tier5-ids.md §3.2):
  input          Ingredient.CODEC.listOf(0, 8), required  -> at most 8 entries; a 9th fails to parse (D114)
  inputFluid     SizedFluidIngredient.FLAT_CODEC, required -> {"amount": N, "fluid": id} or {"amount": N, "tag": id}; the codec
                 defaults a missing amount to 1000 (neoforge-21.1.250-universal.jar SizedFluidIngredient), the pack always writes it
  processingTime Codec.INT, required
  output         ItemStack.CODEC, optional                -> {"count": N, "id": id}
  outputFluid    FluidStack.CODEC, optional               -> key "id", not "fluid"
Matching is a multiset (every non-empty 1-item slot is claimed by one ingredient), so four of an item are four entries.
After a boot, a datapack recipe that fails the codec shows only as a "Parsing error loading recipe <id>" line in
logs/latest.log: KubeJS's "failed recipes" count covers only recipes its scripts add or change, and the recipe dump is taken
before any codec runs. A broken in-place override also takes IF's default with it. So the JSON is checked here, before any boot.
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "kubejs" / "data"
TYPE = "industrialforegoing:dissolution_chamber"
SUPREME = "industrialforegoing/recipe/dissolution_chamber/supreme_machine_frame.json"
UNOB_VIB = "confluence/recipe/tier5/unobtainium_vibranium_alloy_ingot.json"


def dissolution_files():
    found = {}
    for path in sorted(DATA.glob("*/recipe/**/*.json")):
        body = json.loads(path.read_text())
        if body.get("type") == TYPE:
            found[path.relative_to(DATA).as_posix()] = body
    return found


def ingredient(entry):
    assert set(entry) in ({"item"}, {"tag"}), entry
    return entry["item"] if "item" in entry else "#" + entry["tag"]


def test_every_pack_dissolution_recipe_fits_the_codec():
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
    """Spec §5 T5.2 and D114: IF's default id, its fluid, time and condition kept; 8 items with one nitro crystal."""
    body = dissolution_files()[SUPREME]
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
    assert Counter(ingredient(e) for e in body["input"]) == Counter({
        "industrialforegoing:pink_slime": 4, "#c:ingots/vibranium": 1, "#c:ingots/unobtainium": 1,
        "allthemodium:piglich_heart": 1,
    })
    assert body["inputFluid"] == {"amount": 100, "fluid": "allthemodium:soul_lava"}
    assert body["output"] == {"count": 1, "id": "allthemodium:unobtainium_vibranium_alloy_ingot"}
    assert body["processingTime"] == 200
