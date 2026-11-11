"""tools/check_route.py on small hand-built worlds, never the real dump (v1.0 spec §6.1 outputs; plan Tasks 16-17).

The base world: flint and steel opens the Nether, where blazes drop rods; a rod makes a gem (T1.1, gated by the Nether [D1.1]);
the gem makes the catalyst (X7.1); the catalyst and a stick make the one tier-7 leaf (X7.2). D0.1 is a checkmark quest, made
by its own `quest` source, and is a soft ref of D1.1 (flint and steel does not consume it).
"""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_route  # noqa: E402
from check_route import Inputs, Reader, run_checks, staleness_problems  # noqa: E402
from route_sources import SECTIONS  # noqa: E402

TREE = """### Tier 0 — Overworld
- [D0.1] Start
  - gate: none
### Tier 1 — Nether
- [D1.1] Nether
  - gate: [D0.1]
- [T1.1] Gem
  - gate: [D1.1]
### Top
- [X7.1] Catalyst
  - gate: [T1.1]
"""
CHAPTERS = {
    "tier0": {"quests": [{"node": "D0.1", "task": "checkmark", "deps": []}]},
    "tier1": {"quests": [{"node": "D1.1", "task": "dimension:minecraft:the_nether", "deps": ["D0.1"]},
                         {"node": "T1.1", "task": "item:x:gem", "deps": ["D1.1"]}]},
    "catalyst": {"quests": [{"node": "X7.1", "task": "item:kubejs:confluence_catalyst", "deps": ["T1.1"]},
                            {"node": "X7.2", "task": "item:x:creative", "deps": ["X7.1"]}]},
}
SOURCES = {
    "base": [{"id": "minecraft:stick", "cite": "t"}, {"id": "minecraft:flint", "cite": "t"},
             {"id": "minecraft:iron_ingot", "cite": "t"}],
    "dimensions": [
        {"id": "minecraft:overworld", "tier": 0, "from": None, "enter": [[]], "cite": "t"},
        {"id": "minecraft:the_nether", "tier": 1, "from": "minecraft:overworld", "enter": [["minecraft:flint_and_steel"]],
         "cite": "t"}],
    "biome_dimensions": [],
    "sources": [
        {"key": "blaze", "item": "minecraft:blaze_rod", "dimension": "minecraft:the_nether", "kind": "mob", "needs": [],
         "cite": "t"},
        {"key": "q:D0.1", "item": None, "dimension": "minecraft:overworld", "kind": "quest", "needs": [], "node": "D0.1",
         "cite": "t"}],
    "machines": [{"type": "minecraft:crafting_shapeless", "needs": [], "cite": "t"}],
    "ignored_types": [],
    "accepted": [],
    "soft_refs": [{"node": "D1.1", "ref": "D0.1", "cite": "t"}],
}
assert set(SOURCES) == set(SECTIONS)


def shapeless(rid, out, *ins):
    return {"id": rid, "type": "minecraft:crafting_shapeless", "json": json.dumps(
        {"type": "minecraft:crafting_shapeless", "ingredients": [{"item": i} for i in ins], "result": {"id": out, "count": 1}})}


ROWS = [shapeless("r:fas", "minecraft:flint_and_steel", "minecraft:iron_ingot", "minecraft:flint"),
        shapeless("r:gem", "x:gem", "minecraft:blaze_rod"),
        shapeless("r:cat", "kubejs:confluence_catalyst", "x:gem"),
        shapeless("r:creative", "x:creative", "kubejs:confluence_catalyst", "minecraft:stick")]


def world(rows=None, sources=None, chapters=None, tree=TREE):
    return Inputs(rows=ROWS if rows is None else rows, item_members={}, fluid_members={}, block_members={}, crops=[],
                  bee_defs={}, sources=SOURCES if sources is None else sources, tree_text=tree,
                  chapters=CHAPTERS if chapters is None else chapters, gates=["r:cat"],
                  sole={"kubejs:confluence_catalyst": ("item", ["r:cat"])})


def edited(**sections):
    s = copy.deepcopy(SOURCES)
    for k, v in sections.items():
        s[k] = v
    return s


BYPASS = shapeless("r:cheap_gem", "x:gem", "minecraft:stick")   # a gem in the Overworld: skips the Nether


def test_the_base_world_is_green():
    rep = run_checks(world())
    assert rep.summary == "route: 5 trunk nodes, 5 reachable, 0 unreachable, 0 skippable, 0 early, 0 unmodelled types"
    assert rep.failures == []
    assert rep.nodes["T1.1"]["witness"] == ["r:gem", "blaze", "dim:minecraft:the_nether#0", "r:fas"]


def test_unreachable_names_the_raw_leaf():
    rep = run_checks(world(sources=edited(sources=SOURCES["sources"][1:])))
    assert "UNREACHABLE T1.1 (x:gem): unsourced minecraft:blaze_rod" in rep.failures
    assert rep.summary.startswith("route: 5 trunk nodes, 2 reachable, 3 unreachable,")


def test_quest_order_roots_and_cycles():
    chapters = copy.deepcopy(CHAPTERS)
    chapters["tier1"]["quests"][1]["deps"] = []
    rep = run_checks(world(chapters=chapters))
    assert rep.failures == ["QUEST_ORDER T1.1 (tier1.yaml) has no deps and is not in intro.yaml or tier0.yaml"]
    accepted = [{"node": "T1.1", "code": "QUEST_ORDER", "route": [], "decision": "D4"}]
    assert run_checks(world(chapters=chapters, sources=edited(accepted=accepted))).failures == []
    chapters = copy.deepcopy(CHAPTERS)
    chapters["tier0"]["quests"][0]["deps"] = ["T1.1"]
    assert run_checks(world(chapters=chapters)).failures == ["QUEST_ORDER cycle T1.1 -> D1.1 -> D0.1 -> T1.1"]


def test_unmodelled_a_b_c():
    odd = {"id": "r:odd", "type": "foo:bar", "json": json.dumps({"type": "foo:bar", "input": {"item": "minecraft:stick"},
                                                                "result": {"id": "x:gem"}})}
    rep = run_checks(world(rows=ROWS + [odd]))
    assert "UNMODELLED (a) foo:bar: 1 recipes make watched items (r:odd): x:gem" in rep.failures
    rep = run_checks(world(rows=ROWS + [odd], sources=edited(ignored_types=[{"type": "foo:bar", "cite": "t"}])))
    assert "UNMODELLED (b) foo:bar: 1 recipes make watched items (r:odd): x:gem" in rep.failures
    unread = {"id": "r:unread", "type": "minecraft:crafting_shapeless", "json": json.dumps(
        {"type": "minecraft:crafting_shapeless", "ingredients": [{"type": "neoforge:intersection", "children": []}],
         "result": {"id": "x:gem"}})}
    rep = run_checks(world(rows=ROWS + [unread]))
    assert "UNMODELLED (c) minecraft:crafting_shapeless: 1 recipes make watched items (r:unread): x:gem" in rep.failures
    harmless = {"id": "r:decor", "type": "foo:bar", "json": json.dumps({"type": "foo:bar", "result": {"id": "x:decor"}})}
    assert run_checks(world(rows=ROWS + [harmless])).failures == []


def test_ban_and_disable_and_explain():
    rep = run_checks(world(), ban=frozenset({"minecraft:flint_and_steel"}))
    assert rep.nodes["T1.1"]["reachable"] is False and rep.nodes["D1.1"]["reachable"] is False
    rep = run_checks(world(), disable=frozenset({"blaze"}))
    assert rep.nodes["T1.1"]["reachable"] is False
    rep = run_checks(world())
    lines, units = check_route.explain(rep.model, rep.full, "kubejs:confluence_catalyst")
    assert lines[:3] == ["kubejs:confluence_catalyst <- r:cat", "  x:gem <- r:gem", "    minecraft:blaze_rod <- blaze"]


# One ma_crops.json crop (9 keys, Task 15): crop_component reads tier_essence and crafting_seed, never essence/seeds (C1).
IRON_CROP = {"id": "mysticalagriculture:iron", "enabled": True, "seeds": "m:s", "essence": "m:e", "crux": None,
             "material": {"id": "c:ingots/iron", "tag": True}, "biomes": [], "tier_essence": "m:tertium_essence",
             "crafting_seed": "m:prosperity_seed_base"}


def test_reader_shapes():
    r = Reader({"c:ingots/iron": ["minecraft:iron_ingot"]}, {"c:water": ["minecraft:water"]}, [IRON_CROP])
    assert r.tokens("#c:ingots/iron") == frozenset({"minecraft:iron_ingot"})
    assert r.tokens({"tag": "c:water", "amount": 100}) == frozenset({"fluid:minecraft:water"})
    assert r.tokens({"chemical": "mekanism:oxygen", "amount": 1}) == frozenset({"fluid:mekanism:oxygen"})
    assert r.tokens({"count": 2, "ingredient": {"item": "a:b"}}) == frozenset({"a:b"})
    assert r.tokens({"type": "neoforge:compound", "children": [{"item": "a:b"}, {"item": "c:d"}]}) == frozenset({"a:b", "c:d"})
    assert r.tokens({"type": "neoforge:components", "items": "a:b", "components": {}}) == frozenset({"a:b"})
    assert r.tokens({"type": "neoforge:difference", "base": {"item": "a:b"}, "subtracted": {"item": "a:b"}}) == frozenset({"a:b"})
    assert r.tokens({"type": "functionalstorage:tag_without_component", "tag": "c:ingots/iron"}) == frozenset(
        {"minecraft:iron_ingot"})
    crop = {"type": "mysticalagriculture:crop_component", "crop": "mysticalagriculture:iron"}
    assert r.tokens({**crop, "component": "essence"}) == frozenset({"m:tertium_essence"})   # the tier's essence (C1)
    assert r.tokens({**crop, "component": "seed"}) == frozenset({"m:prosperity_seed_base"})   # the type's crafting seed
    assert r.tokens({**crop, "component": "material"}) == frozenset({"minecraft:iron_ingot"})
    assert r.tokens({**crop, "crop": "x:none", "component": "seed"}) is None
    assert r.tokens({"type": "productivebees:component", "components": {"productivebees:bee_type": "productivebees:lead"},
                     "items": "productivebees:configurable_honeycomb"}) == frozenset({"comb:productivebees:lead"})
    assert r.tokens({"type": "neoforge:intersection", "children": []}) is None
    assert r.recipe_groups({"type": "industrialforegoing:dissolution_chamber", "input": [{"item": "a:b"}, {"item": "c:d"}],
                            "inputFluid": {"fluid": "x:slime", "amount": 1}, "processingTime": 5,
                            "output": {"id": "e:f"}}) == (
        (frozenset({"a:b"}), frozenset({"c:d"}), frozenset({"fluid:x:slime"})), None)


def test_stale():
    a, b = Path("recipes.json"), Path("ma_crops.json")
    assert staleness_problems({a: 10.0, b: None}, (5.0, "kubejs/x.js")) == [
        "STALE ma_crops.json missing (boot with tools/server_boot.sh first)"]
    assert staleness_problems({a: 4.0}, (5.0, "tools/route_sources.yaml")) == [
        "STALE recipes.json is older than tools/route_sources.yaml (boot first)"]
    rep = run_checks(Inputs([], {}, {}, {}, [], {}, {}, "", {}, [], {}, ["STALE recipes.json missing"]))
    assert rep.summary == "route: not run (1 export problems)" and rep.failures == ["STALE recipes.json missing"]


def test_iron_seed_infusion_needs_the_tier_essence_the_crafting_seed_and_the_material():
    """The dump's mysticalagriculture:seed/infusion/iron body (Task 16 correction C1: MA CropComponentIngredient maps essence
    to crop.getTier().getEssence() and seed to crop.getType().getCraftingSeed())."""
    r = Reader({"c:ingots/iron": ["minecraft:iron_ingot"]}, {}, [IRON_CROP])
    part = {"type": "mysticalagriculture:crop_component", "crop": "mysticalagriculture:iron"}
    body = {"type": "mysticalagriculture:infusion",
            "ingredients": [{**part, "component": c} for c in ("material", "essence") * 4],
            "input": {**part, "component": "seed"}, "result": {"count": 1, "id": "m:s"}}
    groups, bad = r.recipe_groups(body)
    assert bad is None
    assert set(groups) == {frozenset({"minecraft:iron_ingot"}), frozenset({"m:tertium_essence"}),
                           frozenset({"m:prosperity_seed_base"})}
    assert frozenset({"m:e"}) not in groups and frozenset({"m:s"}) not in groups
    assert r.products(body) == frozenset({"m:s"})


def test_unmodelled_watches_leaves_gate_inputs_and_sole_outputs():
    """UNMODELLED (b) fires for an ignored type that makes a tier-7 leaf, a gate input or a sole_producers output, not only a
    trunk product (spec §6.1 revised), and stays quiet for one that makes none of them."""
    ign = edited(ignored_types=[{"type": "foo:bar", "cite": "t"}])

    def odd(out):
        return {"id": "r:odd", "type": "foo:bar", "json": json.dumps({"type": "foo:bar", "result": {"id": out}})}
    leaf = run_checks(world(rows=ROWS + [odd("x:creative")], sources=ign))
    assert "UNMODELLED (b) foo:bar: 1 recipes make watched items (r:odd): x:creative" in leaf.failures
    gate_input = world(rows=ROWS + [odd("minecraft:flint")], sources=ign)
    gate_input.gates = ["r:fas"]          # flint is an input of a gate recipe, and in no node's product
    assert "UNMODELLED (b) foo:bar: 1 recipes make watched items (r:odd): minecraft:flint" in run_checks(gate_input).failures
    gate_input.gates = []
    assert run_checks(gate_input).failures == []
    sole = world(rows=ROWS + [odd("x:only")], sources=ign)
    assert run_checks(sole).failures == []
    sole.sole = {"x:only": ("item", ["r:x"])}
    assert "UNMODELLED (b) foo:bar: 1 recipes make watched items (r:odd): x:only" in run_checks(sole).failures
    chem = world(rows=ROWS + [{"id": "r:gas", "type": "foo:bar", "json": json.dumps(
        {"type": "foo:bar", "output": {"id": "m:gas", "amount": 10}})}], sources=ign)
    chem.sole = {"m:gas": ("chemical", ["r:x"])}
    assert "UNMODELLED (b) foo:bar: 1 recipes make watched items (r:gas): fluid:m:gas" in run_checks(chem).failures


def test_a_reachable_world_is_not_trivially_green():
    """Each failure fixture differs from the green base world by one edit: the same checker passes the base and fails the
    edit, so no check is green because it checks nothing."""
    assert run_checks(world()).failures == []
    no_fire = edited(dimensions=[SOURCES["dimensions"][0], {**SOURCES["dimensions"][1], "enter": [["x:missing"]]}])
    rep = run_checks(world(sources=no_fire))
    assert "UNREACHABLE D1.1 (dim:minecraft:the_nether): unsourced x:missing" in rep.failures
    assert rep.nodes["X7.2"]["reachable"] is False
    no_machine = edited(machines=[])
    rep = run_checks(world(sources=no_machine))
    # r:fas makes flint and steel, which is no node product, gate input or sole output, so it is not watched (spec §6.1)
    assert ("UNMODELLED (a) minecraft:crafting_shapeless: 3 recipes make watched items (r:cat, r:creative, r:gem): "
            "kubejs:confluence_catalyst, x:creative, x:gem") in rep.failures
    assert rep.summary.endswith("1 unmodelled types")


def test_a_node_without_a_quest_and_a_missing_top_quest():
    chapters = copy.deepcopy(CHAPTERS)
    chapters["tier1"]["quests"].pop()          # no quest names T1.1, and X7.1's dep T1.1 now dangles
    rep = run_checks(world(chapters=chapters))
    assert "UNREACHABLE T1.1: no quest in tools/chapters names this node" in rep.failures
    chapters = copy.deepcopy(CHAPTERS)
    chapters["catalyst"]["quests"] = chapters["catalyst"]["quests"][1:]
    assert "QUEST_ORDER no quest for X7.1 in tools/chapters" in run_checks(world(chapters=chapters)).failures


def test_generated_source_problems_fail_the_run():
    """route_generated.py's problems are failures: an enabled crop in an unmapped biome (UNMAPPED BIOME) and a seeds item in
    the tag export with no crop (NO GENERATED SOURCE)."""
    inp = world()
    inp.crops = [{**IRON_CROP, "biomes": ["x:nowhere"]}]
    inp.item_members = {"c:seeds": ["mysticalagriculture:gold_seeds"]}
    fails = run_checks(inp).failures
    assert "UNMAPPED BIOME x:nowhere (ma:mysticalagriculture:iron): add it to route_sources.yaml biome_dimensions" in fails
    assert "NO GENERATED SOURCE mysticalagriculture:gold_seeds: no crop in ma_crops.json has these seeds" in fails
    inp.problems = ["BEE DEFINITION no productivebees jar in .run/server/mods"]
    assert "BEE DEFINITION no productivebees jar in .run/server/mods" in run_checks(inp).failures


def test_stale_compares_with_the_newest_input(tmp_path, monkeypatch):
    """load_inputs stops at STALE: a missing export, or one older than the newest kubejs file, gates.yaml or
    route_sources.yaml; --sources-edited leaves the last two out."""
    import os
    exports = []
    for name in ("recipes.json", "item_tag_members.json"):
        p = tmp_path / name
        p.write_text("{}")
        os.utime(p, (100, 100))
        exports.append(p)
    gates, srcs = tmp_path / "gates.yaml", tmp_path / "route_sources.yaml"
    for p, t in ((gates, 50), (srcs, 200)):
        p.write_text("")
        os.utime(p, (t, t))
    monkeypatch.setattr(check_route, "EXPORTS", tuple(exports) + (tmp_path / "ma_crops.json",))
    monkeypatch.setattr(check_route, "MANIFEST", gates)
    monkeypatch.setattr(check_route, "ROUTE_SOURCES", srcs)
    import test_dump_bodies
    monkeypatch.setattr(test_dump_bodies, "newest_kubejs_file", lambda root=None: (90.0, "kubejs/server_scripts/x.js"))
    inp = check_route.load_inputs()
    assert inp.stale == ["STALE recipes.json is older than tools/route_sources.yaml (boot first)",
                         "STALE item_tag_members.json is older than tools/route_sources.yaml (boot first)",
                         "STALE ma_crops.json missing (boot with tools/server_boot.sh first)"]
    assert check_route.load_inputs(include_sources=False).stale == [
        "STALE ma_crops.json missing (boot with tools/server_boot.sh first)"]
    rep = run_checks(inp)
    assert rep.summary == "route: not run (3 export problems)" and rep.model is None
