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
    assert r.tokens({"chemical": "mekanism:oxygen", "amount": 1}) == frozenset({"chem:mekanism:oxygen"})   # C8
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


# --- Task 17: SKIPPABLE, EARLY, ACCEPTED_UNUSED, CLI ---------------------------------------------------------------------

def test_first_tier_and_json_row():
    rep = run_checks(world())
    assert rep.nodes["T1.1"] == {"product": "x:gem", "reachable": True, "first_tier": 1,
                                 "witness": ["r:gem", "blaze", "dim:minecraft:the_nether#0", "r:fas"], "skippable_by": []}
    assert rep.nodes["D0.1"]["first_tier"] == 0


def test_a_bypass_is_skippable_and_early():
    rep = run_checks(world(rows=ROWS + [BYPASS]))
    assert "SKIPPABLE T1.1 without [D1.1] (dim:minecraft:the_nether): r:cheap_gem" in rep.failures
    assert "EARLY T1.1: reachable at tier 0, before its gate ref [D1.1] (tier 1)" in rep.failures
    assert rep.nodes["T1.1"]["skippable_by"] == ["D1.1"]


def test_a_leaf_without_the_catalyst_is_skippable():
    rows = ROWS + [shapeless("r:free", "x:creative", "minecraft:stick")]
    rep = run_checks(world(rows=rows))
    assert "SKIPPABLE X7.2 without [X7.1] (kubejs:confluence_catalyst): r:free" in rep.failures


def test_accepted_routes_clear_skippable_and_early():
    accepted = [{"node": "T1.1", "code": "SKIPPABLE", "route": ["r:cheap_gem"], "decision": "D1"},
                {"node": "T1.1", "code": "EARLY", "route": ["r:cheap_gem"], "decision": "D1"}]
    rep = run_checks(world(rows=ROWS + [BYPASS], sources=edited(accepted=accepted)))
    assert rep.failures == []


def test_accepted_unused():
    accepted = [{"node": "T1.1", "code": "SKIPPABLE", "route": ["r:nope"], "decision": "D2"},
                {"node": "D4.3", "code": "QUEST_ORDER", "route": [], "decision": "D3"}]
    soft = SOURCES["soft_refs"] + [{"node": "T1.1", "ref": "D0.1", "cite": "t"}]
    rep = run_checks(world(sources=edited(accepted=accepted, soft_refs=soft)))
    assert rep.failures == ["ACCEPTED_UNUSED T1.1 SKIPPABLE (D2): r:nope never runs",
                            "ACCEPTED_UNUSED D4.3 QUEST_ORDER (D3): not a dep-less quest on X7.1's chains",
                            "ACCEPTED_UNUSED soft_ref T1.1 -> D0.1: not one of its gate refs"]


def test_main_prints_and_writes_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check_route, "load_inputs", lambda include_sources=True: world(rows=ROWS + [BYPASS]))
    out = tmp_path / "route.json"
    assert check_route.main(["--json", str(out), "--explain", "x:gem"]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "x:gem <- r:cheap_gem"
    assert lines[2] == "route: 5 trunk nodes, 5 reachable, 0 unreachable, 1 skippable, 1 early, 0 unmodelled types"
    assert json.loads(out.read_text())["T1.1"]["skippable_by"] == ["D1.1"]


def test_cli_ban_and_disable_reach_every_run(monkeypatch, capsys):
    """--disable removes a unit and --ban a token in the full run and in every SKIPPABLE/EARLY re-run (spec §7.5)."""
    monkeypatch.setattr(check_route, "load_inputs", lambda include_sources=True: world(rows=ROWS + [BYPASS]))
    assert check_route.main(["--disable", "r:cheap_gem"]) == 0
    assert capsys.readouterr().out.splitlines()[0].endswith("0 skippable, 0 early, 0 unmodelled types")
    assert check_route.main(["--ban", "minecraft:stick"]) == 1    # no bypass, no leaf: X7.2 unreachable
    out = capsys.readouterr().out
    assert "1 unreachable, 0 skippable, 0 early" in out and "UNREACHABLE X7.2 (x:creative)" in out


def test_empty_accepted_routes_are_unused():
    """A SKIPPABLE or EARLY entry with `route: []` disables nothing and accepts nothing: ACCEPTED_UNUSED."""
    accepted = [{"node": "T1.1", "code": "SKIPPABLE", "route": [], "decision": "D7"},
                {"node": "T1.1", "code": "EARLY", "route": [], "decision": "D8"}]
    rep = run_checks(world(rows=ROWS + [BYPASS], sources=edited(accepted=accepted)))
    assert "ACCEPTED_UNUSED T1.1 SKIPPABLE (D7): empty route" in rep.failures
    assert "ACCEPTED_UNUSED T1.1 EARLY (D8): empty route" in rep.failures
    # and the bypass itself is still reported: an empty route hides nothing
    assert "SKIPPABLE T1.1 without [D1.1] (dim:minecraft:the_nether): r:cheap_gem" in rep.failures
    assert any(f.startswith("EARLY T1.1:") for f in rep.failures)


# A second Overworld gem. It needs the stick too, so in the fixpoint it fires after r:cheap_gem: a run that left the accepted
# r:cheap_gem on would name r:cheap_gem as the witness, not r:cheap_gem2.
CHEAP2 = shapeless("r:cheap_gem2", "x:gem", "minecraft:flint", "minecraft:stick")


def test_an_accepted_route_does_not_hide_a_second_one():
    """SKIPPABLE and EARLY disable N's accepted routes in their re-runs, so an unaccepted second bypass is still reported,
    with its own witness (spec §6.1 revised)."""
    accepted = [{"node": "T1.1", "code": "SKIPPABLE", "route": ["r:cheap_gem"], "decision": "D1"},
                {"node": "T1.1", "code": "EARLY", "route": ["r:cheap_gem"], "decision": "D1"}]
    rep = run_checks(world(rows=ROWS + [BYPASS, CHEAP2], sources=edited(accepted=accepted)))
    assert rep.failures == ["SKIPPABLE T1.1 without [D1.1] (dim:minecraft:the_nether): r:cheap_gem2",
                            "EARLY T1.1: reachable at tier 0, before its gate ref [D1.1] (tier 1)"]


def test_each_accepted_route_must_still_bypass_on_its_own():
    """An accepted SKIPPABLE/EARLY route whose units all run but which no longer reaches its node without the gate (or before
    it), with the node's other accepted routes off, is ACCEPTED_UNUSED. Two real bypasses, both accepted, each pass alone."""
    accepted = [{"node": "T1.1", "code": "SKIPPABLE", "route": ["r:gem", "blaze"], "decision": "D9"},
                {"node": "T1.1", "code": "EARLY", "route": ["r:gem"], "decision": "D9"}]
    rep = run_checks(world(sources=edited(accepted=accepted)))
    assert rep.failures == ["ACCEPTED_UNUSED T1.1 SKIPPABLE (D9): does not reach T1.1 without any gate ref on its own",
                            "ACCEPTED_UNUSED T1.1 EARLY (D9): does not reach T1.1 before its gate refs on its own"]
    both = [{"node": "T1.1", "code": c, "route": [rid], "decision": d}
            for c in ("SKIPPABLE", "EARLY") for rid, d in (("r:cheap_gem", "D1"), ("r:cheap_gem2", "D5"))]
    assert run_checks(world(rows=ROWS + [BYPASS, CHEAP2], sources=edited(accepted=both))).failures == []


def test_an_accepted_route_for_an_unchecked_node_is_unused():
    accepted = [{"node": "Z9.9", "code": "SKIPPABLE", "route": ["r:gem"], "decision": "D6"}]
    assert run_checks(world(sources=edited(accepted=accepted))).failures == [
        "ACCEPTED_UNUSED Z9.9 SKIPPABLE (D6): not a trunk node or tier-7 leaf"]


def test_early_compares_with_gate_refs_not_the_tree_tier_and_skips_top():
    """A tier-1 node gated only by a tier-0 node is not EARLY even when reachable at tier 0 (spec §6.1 revised), and X7.1 (the
    top tier, no dimension) is never EARLY; it is still SKIPPABLE."""
    tree = TREE.replace("### Tier 1", "- [T0.1] Lighter\n  - gate: [D0.1]\n### Tier 1").replace(
        "### Top", "- [T1.2] Torch\n  - gate: [T0.1]\n### Top").replace(
        "- [X7.1] Catalyst\n  - gate: [T1.1]", "- [X7.1] Catalyst\n  - gate: [T1.1], [T1.2]")
    chapters = copy.deepcopy(CHAPTERS)
    chapters["tier0"]["quests"].append({"node": "T0.1", "task": "item:minecraft:flint_and_steel", "deps": ["D0.1"]})
    chapters["tier1"]["quests"].append({"node": "T1.2", "task": "item:x:torch", "deps": ["T0.1"]})
    chapters["catalyst"]["quests"][0]["deps"] = ["T1.1", "T1.2"]
    rows = [r for r in ROWS if r["id"] != "r:cat"] + [
        shapeless("r:torch", "x:torch", "minecraft:flint_and_steel", "minecraft:stick"),
        shapeless("r:cat", "kubejs:confluence_catalyst", "x:gem", "x:torch")]
    soft = SOURCES["soft_refs"] + [{"node": "T0.1", "ref": "D0.1", "cite": "t"}]
    srcs = edited(soft_refs=soft)
    rep = run_checks(world(rows=rows, chapters=chapters, tree=tree, sources=srcs))
    assert rep.nodes["T1.2"]["first_tier"] == 0 and rep.nodes["T0.1"]["first_tier"] == 0
    assert rep.failures == []
    cheap_cat = shapeless("r:cheap_cat", "kubejs:confluence_catalyst", "minecraft:stick")
    rep = run_checks(world(rows=rows + [cheap_cat], chapters=chapters, tree=tree, sources=srcs))
    assert rep.nodes["X7.1"]["first_tier"] == 0
    assert not any(f.startswith("EARLY") for f in rep.failures)
    assert "SKIPPABLE X7.1 without [T1.1] (x:gem): r:cheap_cat" in rep.failures


# --- Task 18: review fixes (research/phase7-v1.0-route-review.md) ---------------------------------------------------------

def test_c1_fluid_key_is_read_per_type():
    """`fluid` is consumed by productivebees:bottler and irons alchemist_cauldron_empty, and made by productivebees:centrifuge
    and irons alchemist_cauldron_fill (the 0.3 dump's rows); on any other type it is not read."""
    r = Reader({}, {"c:experience": ["x:xp"]}, [])
    bottler = {"type": "productivebees:bottler", "fluid": {"fluid": "minecraft:milk", "amount": 250},
               "ingredient": {"item": "minecraft:glass_bottle"}, "result": {"id": "productivebees:milk_bottle"}}
    assert r.recipe_groups(bottler) == ((frozenset({"fluid:minecraft:milk"}), frozenset({"minecraft:glass_bottle"})), None)
    empty = {"type": "irons_spellbooks:alchemist_cauldron_empty", "fluid": {"amount": 250, "id": "i:rare_ink"},
             "input": {"item": "minecraft:glass_bottle"}, "result": {"count": 1, "id": "i:rare_ink"}}
    assert r.recipe_groups(empty) == ((frozenset({"fluid:i:rare_ink"}), frozenset({"minecraft:glass_bottle"})), None)
    centrifuge = {"type": "productivebees:centrifuge", "ingredient": {"item": "minecraft:honeycomb"},
                  "outputs": [{"item": {"item": "productivebees:wax"}}], "fluid": {"fluid": "allthemodium:soul_lava", "amount": 20}}
    assert r.recipe_groups(centrifuge) == ((frozenset({"minecraft:honeycomb"}),), None)
    assert r.products(centrifuge) == frozenset({"productivebees:wax", "fluid:allthemodium:soul_lava"})
    xp = {**centrifuge, "fluid": {"tag": "c:experience", "amount": 100}}
    assert r.products(xp) == frozenset({"productivebees:wax", "fluid:x:xp"})
    fill = {"type": "irons_spellbooks:alchemist_cauldron_fill", "fluid": {"amount": 250, "id": "i:epic_ink"},
            "input": {"item": "i:epic_ink"}, "result": {"count": 1, "id": "minecraft:glass_bottle"}}
    assert r.recipe_groups(fill) == ((frozenset({"i:epic_ink"}),), None)
    assert r.products(fill) == frozenset({"minecraft:glass_bottle", "fluid:i:epic_ink"})
    other = {"type": "foo:bar", "fluid": {"fluid": "minecraft:lava", "amount": 1}, "result": {"id": "x:y"}}
    assert r.recipe_groups(other) == (None, ("fluid", {"fluid": "minecraft:lava", "amount": 1}))


def test_c1_a_centrifuge_making_a_watched_fluid_is_unmodelled():
    rows = ROWS + [{"id": "r:soul", "type": "productivebees:centrifuge", "json": json.dumps(
        {"type": "productivebees:centrifuge", "ingredient": {"item": "minecraft:honeycomb"}, "outputs": [],
         "fluid": {"fluid": "allthemodium:soul_lava", "amount": 20}})}]
    inp = world(rows=rows)
    inp.sole = {**inp.sole, "allthemodium:soul_lava": ("chemical", [])}
    assert ("UNMODELLED (a) productivebees:centrifuge: 1 recipes make watched items (r:soul): fluid:allthemodium:soul_lava"
            in run_checks(inp).failures)


def test_c2_other_keys_naming_ids_are_unread():
    """A key the role table calls "other" whose value names a resource location is not read (UNMODELLED (c)), unless it is a
    listed setting (group, sound); settings without ids (time, experience) pass."""
    r = Reader({}, {}, [])
    body = {"type": "farmersdelight:cooking", "ingredients": [{"item": "minecraft:beetroot"}],
            "container": {"count": 1, "id": "minecraft:bowl"}, "result": {"count": 1, "id": "minecraft:beetroot_soup"},
            "experience": 0.35, "cookingtime": 200, "group": "x:soups", "sound": "minecraft:item.bucket.fill"}
    assert r.recipe_groups(body) == (None, ("container", {"count": 1, "id": "minecraft:bowl"}))
    del body["container"]
    assert r.recipe_groups(body) == ((frozenset({"minecraft:beetroot"}),), None)
    rows = ROWS + [{"id": "r:soup_gem", "type": "minecraft:crafting_shapeless", "json": json.dumps(
        {"type": "minecraft:crafting_shapeless", "ingredients": [{"item": "minecraft:stick"}],
         "materials": [{"count": 1, "ingredient": {"item": "x:rare"}}], "result": {"id": "x:gem"}})}]
    assert ("UNMODELLED (c) minecraft:crafting_shapeless: 1 recipes make watched items (r:soup_gem): x:gem"
            in run_checks(world(rows=rows)).failures)


def test_c3_products_not_read_are_reported_for_any_type():
    """A product the reader cannot read, or a key not read, that names a watched item is reported whether the type is a
    machine, ignored or unlisted."""
    conv = {"id": "r:conv", "type": "foo:conv", "json": json.dumps(
        {"type": "foo:conv", "from": {"Name": "minecraft:stick"}, "result": {"Name": "x:gem"}})}
    line = ("UNMODELLED (c) foo:conv: 1 recipes have a product or key not read that names watched items (r:conv): x:gem")
    assert line in run_checks(world(rows=ROWS + [conv])).failures
    ign = edited(ignored_types=[{"type": "foo:conv", "cite": "t"}])
    assert line in run_checks(world(rows=ROWS + [conv], sources=ign)).failures
    mach = edited(machines=SOURCES["machines"] + [{"type": "foo:conv", "needs": [], "cite": "t"}])
    assert line in run_checks(world(rows=ROWS + [conv], sources=mach)).failures
    hidden = {"id": "r:hid", "type": "foo:hid", "json": json.dumps({"type": "foo:hid", "becomes": "x:gem"})}
    assert ("UNMODELLED (c) foo:hid: 1 recipes have a product or key not read that names watched items (r:hid): x:gem"
            in run_checks(world(rows=ROWS + [hidden])).failures)
    harmless = {"id": "r:h2", "type": "foo:hid", "json": json.dumps({"type": "foo:hid", "becomes": "x:decor"})}
    assert run_checks(world(rows=ROWS + [harmless])).failures == []


def test_c6_unsourced_needs():
    mach = edited(machines=[{"type": "minecraft:crafting_shapeless", "needs": ["x:table"], "cite": "t"}],
                  sources=SOURCES["sources"] + [{"key": "pig", "item": "x:pork", "dimension": "minecraft:overworld",
                                                 "kind": "mob", "needs": [["minecraft:stick", "x:sword"]], "cite": "t"}])
    fails = run_checks(world(sources=mach)).failures
    assert "UNSOURCED NEEDS x:table (minecraft:crafting_shapeless)" in fails
    assert "UNSOURCED NEEDS x:sword (pig)" in fails


def test_c7_nested_ingredient_with_amount_is_a_fluid_and_unknown_fluid_tags_are_unread():
    r = Reader({"c:water": ["x:water_item"]}, {"c:water": ["minecraft:water"]}, [])
    assert r.tokens({"ingredient": {"tag": "c:water"}, "amount": 100}) == frozenset({"fluid:minecraft:water"})
    assert r.tokens({"tag": "c:nothing", "amount": 100}) is None


def test_c8_chemicals_have_their_own_prefix():
    r = Reader({}, {"c:hydrogen": ["mekanism:hydrogen"]}, [], {"mekanism:hydrogen": ["mekanism:hydrogen"],
                                                               "mekanism:water_vapor": ["mekanism:steam"]})
    assert r.tokens({"chemical": "mekanism:oxygen", "amount": 1}) == frozenset({"chem:mekanism:oxygen"})
    assert r.tokens({"fluid": "mekanism:oxygen", "amount": 1}) == frozenset({"fluid:mekanism:oxygen"})
    inj = {"type": "mekanism:injecting", "chemical_input": {"amount": 1, "tag": "mekanism:water_vapor"},
           "item_input": {"count": 1, "item": "x:a"}, "output": {"count": 1, "id": "x:b"}, "per_tick_usage": True}
    assert r.recipe_groups(inj) == ((frozenset({"chem:mekanism:steam"}), frozenset({"x:a"})), None)
    rot = {"type": "mekanism:rotary", "chemical_output": {"amount": 1, "id": "mekanism:hydrogen"},
           "fluid_output": {"amount": 1, "id": "mekanism:hydrogen"}}
    assert r.products(rot) == frozenset({"chem:mekanism:hydrogen", "fluid:mekanism:hydrogen"})
    ox = {"type": "mekanism:oxidizing", "input": {"count": 1, "item": "x:a"}, "output": {"amount": 10, "id": "mekanism:x"}}
    assert r.products(ox) == frozenset({"chem:mekanism:x"})
    evap = {"type": "mekanism:evaporating", "input": {"amount": 10, "tag": "c:hydrogen"},
            "output": {"amount": 1, "id": "mekanism:lithium"}}
    assert r.recipe_groups(evap) == ((frozenset({"fluid:mekanism:hydrogen"}),), None)
    assert r.products(evap) == frozenset({"fluid:mekanism:lithium"})
    odd = {"type": "mekanism:new_machine", "input": {"amount": 1, "id": "x:y"}, "output": {"count": 1, "id": "x:z"}}
    assert r.recipe_groups(odd)[0] is None    # a Mekanism amount stack of a kind not listed: not read


def test_c9_a_leaf_on_the_trunk_fails():
    chapters = copy.deepcopy(CHAPTERS)
    gem = chapters["tier1"]["quests"].pop()
    chapters["catalyst"]["quests"].append(gem)
    rep = run_checks(world(chapters=chapters))
    assert "LEAF IN TRUNK T1.1: a catalyst.yaml quest node is also on X7.1's trunk" in rep.failures


def test_c11_a_string_ingredient_that_is_no_id_is_unread():
    r = Reader({}, {}, [])
    assert r.tokens("<inert>") is None and r.tokens("Not An Id") is None
    assert r.tokens("minecraft:stick") == frozenset({"minecraft:stick"})


def test_c12_gate_inputs_not_read_fail():
    rows = [r for r in ROWS if r["id"] != "r:cat"] + [{"id": "r:cat", "type": "minecraft:crafting_shapeless", "json": json.dumps(
        {"type": "minecraft:crafting_shapeless", "ingredients": [{"item": "x:gem"}, {"type": "neoforge:intersection"}],
         "result": {"id": "kubejs:confluence_catalyst"}})}]
    fails = run_checks(world(rows=rows)).failures
    assert 'GATE INPUT r:cat: ingredients {"type": "neoforge:intersection"} not read' in fails
    inp = world()
    inp.gates = ["r:missing"]
    assert "GATE INPUT r:missing: not in the dump" in run_checks(inp).failures


def test_s1_early_disables_accepted_routes_per_node():
    """An accepted EARLY route for one node does not hide another node's EARLY, and the reported first_tier is from the run
    with nothing disabled."""
    other = [{"node": "D1.1", "code": "EARLY", "route": ["r:cheap_gem"], "decision": "D11"}]
    rep = run_checks(world(rows=ROWS + [BYPASS], sources=edited(accepted=other)))
    assert "EARLY T1.1: reachable at tier 0, before its gate ref [D1.1] (tier 1)" in rep.failures
    own = [{"node": "T1.1", "code": "EARLY", "route": ["r:cheap_gem"], "decision": "D12"},
           {"node": "T1.1", "code": "SKIPPABLE", "route": ["r:cheap_gem"], "decision": "D12"}]
    rep = run_checks(world(rows=ROWS + [BYPASS], sources=edited(accepted=own)))
    assert rep.failures == [] and rep.nodes["T1.1"]["first_tier"] == 0


def test_s3_a_gate_refs_node_sources_are_disabled():
    """A boss source makes its drop and node:R. N needs the drop and is gated by [R]; banning node:R alone would leave the
    drop, so SKIPPABLE must disable R's own sources too."""
    tree = TREE.replace("### Top", "- [M1.1] Boss\n  - gate: [D1.1]\n- [T1.2] Trophy\n  - gate: [M1.1]\n### Top").replace(
        "- [X7.1] Catalyst\n  - gate: [T1.1]", "- [X7.1] Catalyst\n  - gate: [T1.1], [T1.2]")
    chapters = copy.deepcopy(CHAPTERS)
    chapters["tier1"]["quests"] += [{"node": "M1.1", "task": "kill:x:boss", "deps": ["D1.1"]},
                                    {"node": "T1.2", "task": "item:x:trophy", "deps": ["M1.1"]}]
    chapters["catalyst"]["quests"][0]["deps"] = ["T1.1", "T1.2"]
    srcs = edited(sources=SOURCES["sources"] + [{"key": "boss", "item": "x:drop", "dimension": "minecraft:the_nether",
                                                 "kind": "boss", "needs": [], "node": "M1.1", "cite": "t"}])
    rows = [r for r in ROWS if r["id"] != "r:cat"] + [shapeless("r:trophy", "x:trophy", "x:drop"),
                                                       shapeless("r:cat", "kubejs:confluence_catalyst", "x:gem", "x:trophy")]
    rep = run_checks(world(rows=rows, chapters=chapters, tree=tree, sources=srcs))
    assert rep.nodes["T1.2"]["reachable"] and rep.failures == []


def test_s5_an_accepted_early_on_a_node_without_a_tree_tier_is_unused():
    chapters = copy.deepcopy(CHAPTERS)
    chapters["catalyst"]["quests"].append({"node": "CAT.1", "task": "item:x:creative", "deps": ["X7.1"]})
    accepted = [{"node": "CAT.1", "code": "EARLY", "route": ["r:creative"], "decision": "D13"}]
    rep = run_checks(world(chapters=chapters, sources=edited(accepted=accepted)))
    assert rep.failures == ["ACCEPTED_UNUSED CAT.1 EARLY (D13): not a trunk node with a tree tier"]


def test_s12_base_tags_root_seed_and_duplicate_units():
    inp = world(sources=edited(base=SOURCES["base"] + [{"tag": "c:empty", "cite": "t"}]))
    assert "BASE TAG c:empty: no members in the item tag export" in run_checks(inp).failures
    home = edited(dimensions=[{**SOURCES["dimensions"][0], "id": "x:home"},
                              {**SOURCES["dimensions"][1], "from": "x:home"}],
                  sources=[SOURCES["sources"][0], {**SOURCES["sources"][1], "dimension": "x:home"}])
    rep = run_checks(world(sources=home))
    assert rep.failures == [] and rep.nodes["D0.1"]["reachable"]
    dup = edited(sources=SOURCES["sources"] + [{"key": "r:gem", "item": "x:gem", "dimension": "minecraft:overworld",
                                                "kind": "loot", "needs": ["x:never"], "cite": "t"}])
    assert any(f.startswith("DUPLICATE UNIT r:gem:") for f in run_checks(world(sources=dup)).failures)
