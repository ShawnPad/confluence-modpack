"""events.js's item-tag handler (ServerEvents.tags('item', ...)): every edit it asks KubeJS to make, exactly and in order.

  - v0.1: the Twilight portal activator swap (diamonds out, the pack's Twilight key in).
  - v0.3, D132: six removes of the three items allthemodium-3.0.1_mc_1.21.1.jar names in its item tags but never registers
    (data/minecraft/tags/item/enchantable/{bow,crossbow,equippable}.json, data/c/tags/item/tools/{bow,crossbow,shield}.json).
    Without them vanilla's TagLoader drops those six tags and every tag that requires one, so no bow or crossbow takes power,
    punch, flame, infinity, multishot, piercing or quick_charge (the comment above the handler in events.js has the evidence).

The pairs are written out here, not imported from lib/ids.js, so a changed id or tag there fails this test. The boot-side
proof that the six tags then bind is tools/check_tags.py: lib/ids.js holds each as a '#' literal, which it requires bound and
non-empty in the boot's tags.json. The scripts run in node through the shared runner (kjs.run), as in test_bypass_v03.py.
"""
import sys
import zipfile
from pathlib import Path

import pytest

from kjs import jar_json, node_fixture, pinned_jar, run  # noqa: F401  (node_fixture provides the `node` fixture)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_tags  # noqa: E402

ATM_JAR = "allthemodium-3.0.1_mc_1.21.1.jar"

TWILIGHT_SWAP = [
    ("twilightforest:portal/activator", "remove", ["#c:gems/diamond"]),
    ("twilightforest:portal/activator", "add", ["kubejs:twilight_key"]),
]
ATM_UNREGISTERED = [
    ("minecraft:enchantable/bow", "remove", ["allthemodium:allthemodium_bow"]),
    ("minecraft:enchantable/crossbow", "remove", ["allthemodium:unobtainium_crossbow"]),
    ("minecraft:enchantable/equippable", "remove", ["allthemodium:vibranium_shield"]),
    ("c:tools/bow", "remove", ["allthemodium:allthemodium_bow"]),
    ("c:tools/crossbow", "remove", ["allthemodium:unobtainium_crossbow"]),
    ("c:tools/shield", "remove", ["allthemodium:vibranium_shield"]),
]


@pytest.fixture(scope="module")
def events(node):
    return run("kubejs/server_scripts/events.js")


def item_tag_edits(result):
    return [(row["tag"], row["op"], row["values"]) for row in result["tagEvents"] if row["registry"] == "minecraft:item"]


def test_item_tag_handler_registered_and_runs(events):
    assert events["handlers"]["tags"].get("minecraft:item") == 1
    assert events["errors"] == []


def test_item_tag_edits_are_exactly_the_twilight_swap_and_the_six_atm_removes(events):
    assert item_tag_edits(events) == TWILIGHT_SWAP + ATM_UNREGISTERED


# ---- Task 8c round 2, R5: what guards D132 against an Allthemodium bump ----

def test_the_pinned_allthemodium_jar_still_names_each_dead_id_and_registers_none():
    """D132 rests on two jar facts. Each of the six tag files lists its dead id, and no class but the datagen ItemModels spells
    any of the three names (ModRegistry, which registers the mod's items, does not; the ATMBow, Unobow and Vib_Shield classes
    are constructed nowhere). A version that drops an id from a tag, or names one in another class (as registering it would),
    fails here, before a boot: re-read the jar, then keep or drop the six removes in events.js."""
    with zipfile.ZipFile(pinned_jar("allthemodium-", ATM_JAR, "allthemodium.pw.toml")) as jar:
        for tag, _, (dead,) in ATM_UNREGISTERED:
            ns, path = tag.split(":")
            entry = f"data/{ns}/tags/item/{path}.json"
            values = jar_json(jar, entry, f"#{tag} no longer comes from {ATM_JAR}")["values"]
            names = [v if isinstance(v, str) else v.get("id") for v in values]
            assert dead in names, f"{ATM_JAR}!{entry} no longer lists {dead}: re-check D132"
        for dead in sorted({ids[0] for _, _, ids in ATM_UNREGISTERED}):
            name = dead.split(":")[1].encode()
            spelled = sorted(n for n in jar.namelist() if n.endswith(".class") and name in jar.read(n))
            assert spelled == ["com/thevortex/allthemodium/datagen/client/ItemModels.class"], (dead, spelled)


def test_the_six_tags_are_boot_checked_references():
    """tools/check_tags.py requires every tag the scripts name bound and non-empty at boot. The six D132 tags are among them
    (lib/ids.js names each as a '#' literal), so the boot proves the removes let vanilla bind them."""
    refs = check_tags.collect_references(check_tags.ROOT)
    assert {tag for tag, _, _ in ATM_UNREGISTERED} <= set(refs)
    assert all("kubejs/server_scripts/lib/ids.js" in refs[tag] for tag, _, _ in ATM_UNREGISTERED)
