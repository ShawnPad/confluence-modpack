from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest

import packitems

SRC = """
const junk = () => event.create('not_real')   // before any registry call
StartupEvents.registry('item', event => {
  event.create('twilight_key').displayName('Twilight Key').maxStackSize(16)
  event.create("coin").displayName('Confluence Coin')
})

StartupEvents.registry('block', event => {
  event.create('mercury_ore').displayName('Mercury Ore')
    .drops(() => Java.loadClass('x').createDefault(Item.of('kubejs:mercury_shard', 1)))
})
"""


def test_ids_attributed_to_their_registry_block():
    assert packitems.registered_ids(SRC) == {"item": ["twilight_key", "coin"], "block": ["mercury_ore"]}


def test_create_before_any_registry_is_ignored():
    assert "not_real" not in sum(packitems.registered_ids(SRC).values(), [])


def test_texture_path_uses_verified_asset_layout(tmp_path):
    assert packitems.texture_path("block", "mercury_ore", tmp_path) == \
        tmp_path / "kubejs" / "assets" / "kubejs" / "textures" / "block" / "mercury_ore.png"


def test_real_items_js_drops_nothing():
    ids = packitems.load()
    src = packitems.strip_js_comments(packitems.ITEMS_JS.read_text())
    assert len(ids["item"]) + len(ids["block"]) == src.count("event.create(")
    assert len(set(ids["item"] + ids["block"])) == len(ids["item"]) + len(ids["block"])
    assert "coin" in ids["item"] and "mercury_ore" in ids["block"]   # fixed by the design (D54, D56)


def test_commented_out_create_is_ignored():
    src = "StartupEvents.registry('item', event => {\n  // event.create('old_item')\n  event.create('kept')\n})"
    assert packitems.registered_ids(src) == {"item": ["kept"], "block": []}


def test_unreadable_create_id_raises():
    src = "StartupEvents.registry('item', event => { event.create('confluence:x') })"
    with pytest.raises(ValueError, match="item registry: an event.create\\(\\) id is not a plain"):
        packitems.registered_ids(src)


def test_other_registry_kinds_are_a_boundary_but_not_collected():
    src = ("StartupEvents.registry('block', event => { event.create('ore') })\n"
           "StartupEvents.registry('fluid', event => { event.create('juice') })")
    assert packitems.registered_ids(src) == {"item": [], "block": ["ore"]}
