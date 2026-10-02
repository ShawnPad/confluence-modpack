"""Spec §10's bag rule, checked against the recipes the server loaded (v0.3 Task 10 rounds 2-4; D126, D133).

check_quests.py reads the reward tables as text against two id lists, FORBIDDEN and EXCLUDED. This file reads what the last
boot loaded: the recipe dump (.run/server/kubejs/exported/recipes.json, written by dump.js) and the item-tag export beside
it (item_tag_members.json). It checks:
  (a) the Epic bag (tier 5) holds no input of a tier-5 or tier-6 recipe;
  (b) the Legendary bag (tier 6) holds no input of a tier-6 recipe, and its tier-5 inputs are exactly
      check_quests.LEGENDARY_ALLOWED (spec §10: "A tier-5 input may appear in the tier-6 bag");
  (c) no table holds a gated output: an item under sole_producers: in tools/gates.yaml that a tier-5 or tier-6 recipe makes;
  (d) no table holds a precursor (below) of a FORBIDDEN or EXCLUDED id, a tier-5 or tier-6 input or a gated output, except
      that the Legendary bag may hold a precursor of a tier-5 input or of LEGENDARY_ALLOWED (check_quests.LEGENDARY_MAY_HOLD).
      The shipped bags' hits are pinned in SHIPPED_PRECURSORS, reported for the owner;
  (e) the shipped bags' tier-5/6 input hits, pinned in SHIPPED_TIER_HITS: reported, not judged (none since B1, below);
  (f) tools/bag_banned.json (check_quests.SNAPSHOT) is what this file computes from the dump (snapshot_of), so
      check_quests.py applies (a)-(e) to every table and chapter reward with no dump present. Rewrite it with
      `python3 tools/tests/test_bag_collisions.py --write-snapshot` (check_quests.SNAPSHOT_COMMAND), from pack/, after a
      boot; test_the_snapshot_is_the_dump_recomputed fails until it is current.

Inputs are read over-inclusively: every namespaced string anywhere in a recipe body outside its product keys
(check_recipes.key_role), except the recipe `type` and its load conditions. Fluids and chemicals count. A tag (a '#' string,
or the value of a `tag` key) also stands for its members in item_tag_members.json.

Precursors (round 3, I4, I5). An edge X -> Y is a dump recipe, other than a tier-5 or tier-6 one, whose body names exactly one
distinct input (X, or a tag X is a member of) and makes Y (an item product, or a member of an item-tag product). Nothing is
taken off the inputs: an input fluid with its output's id (industrialforegoing:pink_slime) is still an input. X is a
precursor of every target a chain of edges reaches from it: the closure, taken to a fixed point. The targets are the
FORBIDDEN and EXCLUDED ids, the tier-5 and tier-6 inputs and the gated outputs. A tier-5/6 recipe makes no edge, because its
inputs are targets already. An item is not its own precursor: a round trip such as iron ingot -> iron block -> iron ingot
adds nothing.

Base materials (rounds 4-5). Spec §10 ¶1: "Base vanilla materials (iron, copper, pistons, buckets, furnaces, crafting
tables) are not gate inputs, as in D89" (check_quests.SPEC_BASE_MATERIALS), plus the glass pane and the vanilla wools, the
same class (orchestrator interpretation, D133). base_materials() takes the wools from #minecraft:wool in the tag export
(its minecraft: members), and check_quests.BASE_MATERIALS must equal the result. They are taken out of the tier-5 and
tier-6 inputs, so they are no target, and the closure ends at them: an edge into one is followed no further, so neither a
base material nor anything whose only way to a target runs through one is a precursor.

Which recipes are tier 5 and tier 6 is the classification below, over the gates: rows of tools/gates.yaml; it is the
orchestrator's (Task 10 dispatch, correction 2) and every constant cites its source. A gates.yaml row it does not classify
fails test_every_gates_row_is_classified.

The dump rules are test_dump_bodies.py's, through its own helpers: with no dump the dump tests skip, and a dump older than
any file a boot reads fails with "stale dump: boot first". The planted tests run each check on a doctored copy of the
tables (or of gates.yaml) in a tmp directory, so each of (a)-(d), the closure and the classification is shown to fail; (e)
is a pinned equality. The (f) planted tests read the committed snapshot only, so they run without a dump too.
"""
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_quests import (BANNED, BASE_MATERIALS, ENTRY, LEGENDARY_ALLOWED, LEGENDARY_MAY_HOLD, QUESTS, SNAPSHOT,  # noqa: E402
                          SNAPSHOT_COMMAND, SPEC_BASE_MATERIALS, VANILLA_WOOL, bag_collisions, load_snapshot)
from check_recipes import MANIFEST, key_role, load_item_members, load_manifest, load_sole_producers, made_by  # noqa: E402
from test_dump_bodies import DUMP, newest_kubejs_file, staleness  # noqa: E402

MEMBERS = DUMP.with_name("item_tag_members.json")
TABLES = QUESTS / "reward_tables"
SHIPPED_BAGS = ("common_bag", "uncommon_bag", "rare_bag")   # v0.1-v0.2 tables, which Task 10 reports on and does not change

# ---- the classification (Task 10 dispatch, correction 2) ----
# Tier 5: the pack's tier-5 recipes, and Allthemodium's kept Unobtainium ingot recipes (Unobtainium is the tier-5 ore,
# [D5.2] in progression/combined-tree.md; the four rows are Task 8's kept defaults in gates.yaml).
TIER5_PREFIXES = ("confluence:tier5/", "allthemodium:unobtainium_ingot_from_")
# T5.2, the Supreme frame: a datapack file at Industrial Foregoing's own id (spec §5 row T5.2, "datapack override at the
# default's own id"; kubejs/data/industrialforegoing/recipe/dissolution_chamber/supreme_machine_frame.json).
T5_OVERRIDE = "industrialforegoing:dissolution_chamber/supreme_machine_frame"
KEPT_T5 = ("ae2:network/parts/terminals_crafting",)   # made from the tier-5 ME terminal (S5.3): spec §6 row S6.2, D117
# Tier 6: the pack's tier-6 recipes, and the X2.2 Unobtainium crystal recipes, which take an Etrium ingot (spec §7 row X2.2).
TIER6_PREFIXES = ("confluence:tier6/", "confluence:bypass/unobtainium_crystal_from_")
KEPT_T6 = ("ae2:network/blocks/pattern_providers_interface_alt",   # part <-> block conversions of the S6.2 pattern
           "ae2:network/blocks/pattern_providers_interface_part")  # provider (spec §6 row S6.2; AE2 §4.5; D117)
# Default recipes v0.3 keeps that are tier-6 content, so their inputs are tier-6 inputs too. Bodies: the jar files
# adastra-1.21.1-1.16.25-neoforge.jar!data/ad_astra/recipe/<path>.json and appliedenergistics2-19.2.17.jar!data/ae2/recipe/
# <path>.json. D6.2 (D118): the four rockets and the launch pad; the parts the rocket recipes name (nose cone, fins, the
# steel/desh/ostrum/calorite tanks, and the desh/ostrum/calorite engines that nest the T6.2 steel engine); the other three
# space-suit pieces next to D6.3's chest piece. S6.2 (D117): the molecular assembler and the pattern encoding terminal.
TIER6_DEFAULTS = (
    "ad_astra:nasa_workbench/tier_1_rocket_from_nasa_workbench", "ad_astra:nasa_workbench/tier_2_rocket_from_nasa_workbench",
    "ad_astra:nasa_workbench/tier_3_rocket_from_nasa_workbench", "ad_astra:nasa_workbench/tier_4_rocket_from_nasa_workbench",
    "ad_astra:launch_pad", "ad_astra:rocket_nose_cone", "ad_astra:rocket_fin",
    "ad_astra:steel_tank", "ad_astra:desh_tank", "ad_astra:ostrum_tank", "ad_astra:calorite_tank",
    "ad_astra:desh_engine", "ad_astra:ostrum_engine", "ad_astra:calorite_engine",
    "ad_astra:space_helmet", "ad_astra:space_pants", "ad_astra:space_boots",
    "ae2:network/crafting/molecular_assembler", "ae2:network/parts/terminals_pattern_encoding",
)
# Shipped tiers (v0.1-v0.2): tiers 1-4, the Allthemodium and Vibranium bypass crystals, the advanced frame (v0.2's T4.1
# override), and Task 8's kept Allthemodium (tier 2) and Vibranium (tier 3) ingot recipes.
SHIPPED = ("confluence:tier1/", "confluence:tier2/", "confluence:tier3/", "confluence:tier4/",
           "confluence:bypass/allthemodium_crystal_from_", "confluence:bypass/vibranium_crystal_from_",
           "industrialforegoing:dissolution_chamber/advanced_machine_frame",
           "allthemodium:allthemodium_ingot_from_", "allthemodium:vibranium_ingot_from_")

# ---- what the shipped bags hit today (reported, not judged; the owner's call, D133) ----
# (e): none. Round 3 pinned the Common bag's iron and copper ingots here; spec §10 ¶1 exempts both (BASE_MATERIALS).
SHIPPED_TIER_HITS = {
    "common_bag": {"tier5": [], "tier6": []},
    "uncommon_bag": {"tier5": [], "tier6": []},
    "rare_bag": {"tier5": [], "tier6": []},
}
# (d): (table, item) -> the precursor codes it holds (PRE_CODES), with the shortest chain of dump recipes behind each.
SHIPPED_PRECURSORS = {
    # Round 3 also pinned the Common bag's copper ingot (a lightning rod), iron ingot (a bucket) and oak planks (a crafting
    # table). Spec §10 ¶1 exempts the iron and copper ingots, buckets and crafting tables (BASE_MATERIALS), and none of the
    # three reaches another target, so no Common bag pin is left.
    # The steel plate (ad_astra:compressing/steel_plate_from_compressing_steel_ingots): spec §10's "steel plates" (EXCLUDED)
    # and a tier-6 input (#ad_astra:steel_plates in ad_astra:launch_pad, rocket_fin, rocket_nose_cone). The pin skips
    # nothing: steel is a [T1.2] material (progression/combined-tree.md L181-185), and no gate touches the routes to the
    # ingot (the Metallurgic Infuser's mekanism:processing/steel/enriched_iron_to_dust, then .../ingot/from_dust_smelting),
    # the block (the plain crafts mekanism:storage_blocks/steel and ad_astra:steel_block) or the plate (the compressor,
    # whose default recipe ad_astra:compressor takes iron ingots and pistons). Spec §10 still lists tier-1 "steel plates and
    # blocks" as excluded: an open question for the owner (D133).
    ("uncommon_bag", "mekanism:ingot_steel"): ["banned", "in6"],
    ("rare_bag", "mekanism:ingot_steel"): ["banned", "in6"],
    # quartz -> quartz block (minecraft:quartz_block) -> quartz bricks (minecraft:quartz_bricks) -> cataclysm:
    # quartz_brick_wall (cataclysm:quartz_brick_wall), Cataclysm decor that FORBIDDEN's v0.1 cataclysm: alternative
    # over-catches (D133).
    ("uncommon_bag", "minecraft:quartz"): ["banned"],
}

NSID = re.compile(r"#?[a-z0-9_.-]+:[a-z0-9_./-]+")
NOT_INPUTS = {"type", "neoforge:conditions", "neoforge:load_conditions", "fabric:load_conditions"}
# The precursor codes: what a chain from an item reaches. "banned" is a FORBIDDEN or EXCLUDED id other than
# LEGENDARY_ALLOWED, "allowed" one of LEGENDARY_ALLOWED; "in5"/"in6" a tier-5/6 input; "gated" a gated output.
PRE_CODES = ("allowed", "banned", "gated", "in5", "in6")


def classify(gates):
    """(tier-5 recipe ids, tier-6 recipe ids, unclassified gates rows). Tier 6 includes TIER6_DEFAULTS."""
    tier5 = sorted({g for g in gates if g.startswith(TIER5_PREFIXES)} | {T5_OVERRIDE} | set(KEPT_T5))
    tier6 = sorted({g for g in gates if g.startswith(TIER6_PREFIXES)} | set(KEPT_T6) | set(TIER6_DEFAULTS))
    unclassified = [g for g in gates if g not in tier5 and g not in tier6 and not g.startswith(SHIPPED)]
    return tier5, tier6, unclassified


def refs(body):
    """Every namespaced string in a recipe body outside its product keys, its type and load conditions; a tag as '#tag'."""
    out = set()

    def walk(node, key):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, key)
        elif isinstance(node, str):
            for s in NSID.findall(node):
                out.add("#" + s.lstrip("#") if (s.startswith("#") or key == "tag") else s)

    rtype = body.get("type")
    for k, v in body.items():
        if k not in NOT_INPUTS and key_role(rtype, k) not in ("product", None):
            walk(v, k)
    return out


def expand(ref_set, members):
    """Ids a set of refs stands for: each id itself, each tag's name and members, and any string that names a tag."""
    out = set()
    for r in ref_set:
        name = r.lstrip("#")
        out.add(name)
        out |= set(members.get(name, ()))
    return out


def single_ingredient_edges(rows, members, skip=frozenset()):
    """{item: {(recipe id, product), ...}}: an edge from the one distinct input of each dump recipe outside `skip` (each
    member, for a tag) to each item it makes. refs() never reads a product key, so nothing is subtracted from it (I5: the
    old `refs(body) - outputs` dropped an input fluid that shares its output's id and made glass panes a precursor)."""
    graph = {}
    for rid, r in rows.items():
        if rid in skip or not r.get("json"):
            continue
        body = json.loads(r["json"])
        made = made_by(body)
        outs = set(made.items) | {i for tag, kind in made.tags if kind == "item" for i in members.get(tag, ())}
        ins = refs(body)
        if not outs or len(ins) != 1:
            continue
        (only,) = ins
        for item in (members.get(only[1:], ()) if only.startswith("#") else (only,)):
            for out in outs - {item}:
                graph.setdefault(item, set()).add((rid, out))
    return graph


def _components(succ):
    """The strongly connected components of a graph ({node: [successor, ...]}), each listed after every component it
    reaches (Tarjan's order), iteratively."""
    index, low, on, stack, out = {}, {}, set(), [], []
    for root in sorted(succ):
        if root in index:
            continue
        index[root] = low[root] = len(index)
        stack.append(root)
        on.add(root)
        work = [(root, iter(succ[root]))]
        while work:
            v, it = work[-1]
            for w in it:
                if w not in index:
                    index[w] = low[w] = len(index)
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(succ[w])))
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            else:
                work.pop()
                if work:
                    u = work[-1][0]
                    low[u] = min(low[u], low[v])
                if low[v] == index[v]:
                    comp = []
                    while True:
                        w = stack.pop()
                        on.discard(w)
                        comp.append(w)
                        if w == v:
                            break
                    out.append(comp)
    return out


def precursor_closure(graph, own, ends=frozenset()):
    """{item: sorted codes} for every item a chain of `graph` edges leads from to an item other than itself whose own(item)
    codes are not empty, with the union of those codes. A chain stops at an item in `ends`: its own edges are not followed."""
    succ = {}
    for z, es in graph.items():
        succ.setdefault(z, set())
        if z in ends:
            continue
        succ[z].update(w for _, w in es)
        for _, w in es:
            succ.setdefault(w, set())
    succ = {z: sorted(ws) for z, ws in succ.items()}
    comps = _components(succ)
    comp_of = {v: k for k, comp in enumerate(comps) for v in comp}
    own_of = {v: set(own(v)) for v in succ}
    comp_own = [set().union(*(own_of[v] for v in comp)) for comp in comps]
    reach = [set() for _ in comps]
    for k, comp in enumerate(comps):          # every component a member reaches comes earlier in comps
        for v in comp:
            for w in succ[v]:
                j = comp_of[w]
                if j != k:
                    reach[k] |= comp_own[j] | reach[j]
    pre = {}
    for k, comp in enumerate(comps):
        for v in comp:
            codes = set(reach[k])
            if len(comp) > 1:                   # every other member of a cycle is reachable from v
                codes |= set().union(*(own_of[y] for y in comp if y != v))
            if codes:
                pre[v] = sorted(codes)
    return pre


def own_codes(item, in5, in6, gated):
    """The PRE_CODES an item is itself a target for."""
    codes = set()
    if BANNED.fullmatch(item):
        codes.add("allowed" if item in LEGENDARY_ALLOWED else "banned")
    if item in in5:
        codes.add("in5")
    if item in in6:
        codes.add("in6")
    if item in gated:
        codes.add("gated")
    return codes


def base_materials(members):
    """Spec §10 ¶1's six, the glass pane, and #minecraft:wool's minecraft: members in the tag export (round 5, D133)."""
    return SPEC_BASE_MATERIALS | {"minecraft:glass_pane"} | {i for i in members["minecraft:wool"] if i.startswith("minecraft:")}


def build(rows, members, gates, sole):
    """Everything the checks read, from the dump rows ({id: row}), the item-tag members, the gates: rows and sole_producers."""
    tier5, tier6, unclassified = classify(gates)
    missing = [i for i in tier5 + tier6 if not rows.get(i, {}).get("json")]
    if missing:
        return {"missing": missing}
    base = base_materials(members)
    in5 = set().union(*(expand(refs(json.loads(rows[i]["json"])), members) for i in tier5)) - base
    in6 = set().union(*(expand(refs(json.loads(rows[i]["json"])), members) for i in tier6)) - base
    t56 = set(tier5) | set(tier6)
    gated = {out for out, (kind, producers) in sole.items() if kind == "item" and t56 & set(producers)}
    graph = single_ingredient_edges(rows, members, skip=t56)
    pre = precursor_closure(graph, lambda i: own_codes(i, in5, in6, gated), ends=base)
    return {"missing": [], "tier5": tier5, "tier6": tier6, "unclassified": unclassified, "in5": in5, "in6": in6,
            "gated": gated, "graph": graph, "pre": pre, "base": base}


def load_tables(directory):
    """{table stem: [item id, ...]} for the canonical rows of each table (check_quests makes every row canonical)."""
    return {p.stem: [m.group(3) for m in ENTRY.finditer(p.read_text())] for p in sorted(Path(directory).glob("*.snbt"))}


# ---- the checks, each a function of the tables so a planted copy can run through it ----

def epic_hits(tables, ctx):                         # (a)
    return sorted(i for i in tables["epic_bag"] if i in ctx["in5"] | ctx["in6"])


def legendary_hits(tables, ctx):                    # (b): (tier-6 inputs held, tier-5 inputs held)
    held = tables["legendary_bag"]
    return sorted(i for i in held if i in ctx["in6"]), sorted({i for i in held if i in ctx["in5"]})


def gated_hits(tables, ctx):                        # (c)
    return sorted((t, i) for t, items in tables.items() for i in items if i in ctx["gated"])


def precursor_hits(tables, ctx):                    # (d): {(table, item): [codes the table may not hold]}
    out = {}
    for t, items in tables.items():
        for i in items:
            codes = [c for c in ctx["pre"].get(i, ()) if not (t == "legendary_bag" and "pre:" + c in LEGENDARY_MAY_HOLD)]
            if codes:
                out[(t, i)] = codes
    return out


def tier_hits(tables, ctx, names):                  # (e)
    return {t: {"tier5": sorted({i for i in tables[t] if i in ctx["in5"]}),
                "tier6": sorted({i for i in tables[t] if i in ctx["in6"]})} for t in names}


def pinned():
    """The shipped bags' pinned hits as tools/bag_banned.json holds them: {table: {id: [code, ...]}} ("in5"/"in6" for (e),
    "pre:<code>" for (d)). Taken from the reviewed constants, so regenerating the snapshot never pins a new hit."""
    out = {}
    for t, hits in SHIPPED_TIER_HITS.items():
        for tier, code in (("tier5", "in5"), ("tier6", "in6")):
            for i in hits[tier]:
                out.setdefault(t, {}).setdefault(i, []).append(code)
    for (t, i), codes in SHIPPED_PRECURSORS.items():
        out.setdefault(t, {}).setdefault(i, []).extend("pre:" + c for c in codes)
    return {t: {i: sorted(c) for i, c in sorted(ids.items())} for t, ids in sorted(out.items())}


def snapshot_of(ctx):
    """tools/bag_banned.json's content (check_quests.load_snapshot): the ids neither list names."""
    def free(ids):
        return sorted(i for i in ids if not BANNED.fullmatch(i))
    return {"_comment": f"Generated by tools/tests/test_bag_collisions.py from the recipe dump; do not edit. Regenerate with "
                        f"`{SNAPSHOT_COMMAND}` (from pack/, after a boot).",
            "tier5_inputs": free(ctx["in5"]), "tier6_inputs": free(ctx["in6"]), "gated_outputs": free(ctx["gated"]),
            "precursors": {i: ctx["pre"][i] for i in free(ctx["pre"])}, "pinned": pinned()}


def snapshot_text(snap):
    """JSON with one list item or one dict entry per line, keys sorted, so a regeneration diffs by id."""
    lines = ["{"]
    keys = sorted(snap)
    for n, k in enumerate(keys):
        v, end = snap[k], "," if n < len(keys) - 1 else ""
        if isinstance(v, list):
            body = [f" {json.dumps(x)}" for x in v]
            lines += [f" {json.dumps(k)}: ["] + [b + ("," if j < len(body) - 1 else "") for j, b in enumerate(body)] + [f" ]{end}"]
        elif isinstance(v, dict):
            body = [f" {json.dumps(a)}: {json.dumps(b, sort_keys=True)}" for a, b in sorted(v.items())]
            lines += [f" {json.dumps(k)}: {{"] + [b + ("," if j < len(body) - 1 else "") for j, b in enumerate(body)] + [f" }}{end}"]
        else:
            lines.append(f" {json.dumps(k)}: {json.dumps(v)}{end}")
    return "\n".join(lines + ["}"]) + "\n"


def dump_problem():
    """None when the dump and the tag export can be read, else ("skip" or "stale", message)."""
    for path in (DUMP, MEMBERS):
        if not path.is_file():
            return "skip", f"{path} does not exist (no server has been booted from this clone)"
    newest = newest_kubejs_file()
    stale = staleness(DUMP.stat().st_mtime, newest)
    if not stale and staleness(MEMBERS.stat().st_mtime, newest):
        stale = f"stale dump: boot first ({MEMBERS} is older than {newest[1]})"
    return ("stale", stale) if stale else None


def context():
    rows = {r["id"]: r for r in json.loads(DUMP.read_text())}
    gates, _ = load_manifest(MANIFEST)
    return build(rows, load_item_members(MEMBERS), gates, load_sole_producers(MANIFEST))


@pytest.fixture(scope="module")
def ctx():
    problem = dump_problem()
    if problem:
        (pytest.skip if problem[0] == "skip" else pytest.fail)(problem[1])
    c = context()
    assert c["missing"] == [], f"classified recipes with no body in the dump: {c['missing']}"
    return c


@pytest.fixture(scope="module")
def tables():
    t = load_tables(TABLES)
    assert sorted(t) == ["common_bag", "epic_bag", "legendary_bag", "rare_bag", "uncommon_bag"]
    return t


def _planted(tmp_path, table, *swaps):
    """load_tables on a copy of the tables with entries of `table` swapped: _planted(tmp_path, table, old, new) or
    _planted(tmp_path, table, (old, new), (old, new), ...)."""
    if swaps and isinstance(swaps[0], str):
        swaps = (swaps,)
    shutil.copytree(TABLES, tmp_path / "reward_tables")
    path = tmp_path / "reward_tables" / f"{table}.snbt"
    text = path.read_text()
    for old_item, new_item in swaps:
        assert text.count(f'id: "{old_item}"') == 1
        text = text.replace(f'id: "{old_item}"', f'id: "{new_item}"')
    path.write_text(text)
    return load_tables(tmp_path / "reward_tables")


# ---- the classification ----

def test_every_gates_row_is_classified(ctx):
    assert ctx["unclassified"] == []
    assert (len(ctx["tier5"]), len(ctx["tier6"])) == (19, 16 + len(TIER6_DEFAULTS)), (ctx["tier5"], ctx["tier6"])


def test_a_planted_gates_row_is_unclassified(tmp_path):
    text = MANIFEST.read_text()
    assert len(re.findall(r"^gates:\n", text, re.M)) == 1
    planted = tmp_path / "gates.yaml"
    planted.write_text(re.sub(r"^gates:\n", "gates:\n  - confluence:tier7/planted\n", text, flags=re.M))
    gates, _ = load_manifest(planted)
    assert classify(gates)[2] == ["confluence:tier7/planted"]


# ---- (a)-(e) on the shipped tables ----

def test_epic_holds_no_tier5_or_tier6_input(ctx, tables):
    assert epic_hits(tables, ctx) == []


def test_legendary_holds_no_tier6_input_and_exactly_the_allowed_tier5_ones(ctx, tables):
    assert legendary_hits(tables, ctx) == ([], sorted(LEGENDARY_ALLOWED))


def test_no_table_holds_a_gated_output(ctx, tables):
    assert "ae2:controller" in ctx["gated"] and "kubejs:other_key" in ctx["gated"]
    assert gated_hits(tables, ctx) == []


def test_no_table_holds_a_precursor_beyond_the_pinned_shipped_ones(ctx, tables):
    assert precursor_hits(tables, ctx) == SHIPPED_PRECURSORS


def test_shipped_bags_tier_input_hits_are_the_reported_ones(ctx, tables):
    assert tier_hits(tables, ctx, SHIPPED_BAGS) == SHIPPED_TIER_HITS


# ---- the precursor rule (I4, I5) ----

# industrialforegoing:dissolution_chamber/pink_slime_ball, as the dump holds it (load conditions aside): glass pane and
# pink slime fluid make the pink slime item.
PINK_SLIME_BALL = {"type": "industrialforegoing:dissolution_chamber", "input": [{"item": "minecraft:glass_pane"}],
                   "inputFluid": {"amount": 300, "fluid": "industrialforegoing:pink_slime"},
                   "output": {"count": 1, "id": "industrialforegoing:pink_slime"},
                   "outputFluid": {"amount": 150, "id": "minecraft:water"}, "processingTime": 200}


def test_a_fluid_named_like_its_output_is_still_an_ingredient():
    rid = "industrialforegoing:dissolution_chamber/pink_slime_ball"
    assert single_ingredient_edges({rid: {"id": rid, "json": json.dumps(PINK_SLIME_BALL)}}, {}) == {}


def test_the_closure_follows_a_chain_and_skips_round_trips():
    graph = {"a:x": {("r:1", "a:y")}, "a:y": {("r:2", "a:t")}, "a:t": {("r:3", "a:u")}, "a:u": {("r:4", "a:t")}}
    own = {"a:t": {"in6"}}.get
    assert precursor_closure(graph, lambda i: own(i, set())) == {"a:x": ["in6"], "a:y": ["in6"], "a:u": ["in6"]}


def test_the_closure_ends_at_a_base_material():
    # round 4, B1: an edge into a base material ends there, so a:x (whose only way to a:t is through the bucket) and the
    # bucket itself are no one's precursors; a:y, which makes a:t directly, still is
    graph = {"a:x": {("r:1", "minecraft:bucket")}, "minecraft:bucket": {("r:2", "a:t")}, "a:y": {("r:3", "a:t")}}
    own = {"a:t": {"in6"}}.get
    assert precursor_closure(graph, lambda i: own(i, set())) == {"a:x": ["in6"], "minecraft:bucket": ["in6"],
                                                                 "a:y": ["in6"]}
    assert precursor_closure(graph, lambda i: own(i, set()), ends=BASE_MATERIALS) == {"a:y": ["in6"]}


def test_base_materials_are_no_tier_input_and_no_precursor(ctx):
    # spec §10 ¶1 (D89): a tier recipe that takes one (ae2:network/parts/terminals_crafting takes a crafting table;
    # confluence:tier6/fuel_refinery a bucket) does not make it a tier input, and nothing is a precursor through one
    rows = {r["id"]: r for r in json.loads(DUMP.read_text())}
    assert "minecraft:crafting_table" in refs(json.loads(rows["ae2:network/parts/terminals_crafting"]["json"]))
    assert "minecraft:bucket" in refs(json.loads(rows["confluence:tier6/fuel_refinery"]["json"]))
    base = BASE_MATERIALS
    assert base & (ctx["in5"] | ctx["in6"] | ctx["gated"] | set(ctx["pre"])) == set()


def test_the_base_wools_are_the_dumps_vanilla_wools(ctx):
    # round 5: build() takes the wools from #minecraft:wool in item_tag_members.json (its minecraft: members); the explicit
    # check_quests.BASE_MATERIALS, which reads without a dump, must match. The tag's other 321 members (320 chipped: wools
    # and ad_astra:glacian_fur) are no vanilla common and stay tier-6 inputs.
    wool = load_item_members(MEMBERS)["minecraft:wool"]
    assert {i for i in wool if i.startswith("minecraft:")} == VANILLA_WOOL
    assert ctx["base"] == BASE_MATERIALS
    assert "ad_astra:glacian_fur" in ctx["in6"] and "minecraft:white_wool" not in ctx["in6"]


def test_precursors_close_over_chains(ctx):
    # mysticalagriculture:fluix_seeds reprocess into fluix essence, and 8 essence craft 6 fluix crystals (EXCLUDED)
    assert ("mysticalagriculture:seed/reprocessor/fluix", "mysticalagriculture:fluix_essence") in ctx["graph"][
        "mysticalagriculture:fluix_seeds"]
    assert ("mysticalagriculture:essence/appliedenergistics2/fluix", "ae2:fluix_crystal") in ctx["graph"][
        "mysticalagriculture:fluix_essence"]
    assert "banned" in ctx["pre"]["mysticalagriculture:fluix_seeds"]
    # ae2:dark_monitor -> ae2:semi_dark_monitor (ae2:network/parts/panels_semi_dark_monitor_alt), a tier-5 input (S5.3)
    assert ctx["pre"]["ae2:dark_monitor"] == ["in5"]


# ---- planted tables: each check fails on a doctored copy ----

def test_a_tier6_input_in_epic_fails(ctx, tmp_path):
    # ad_astra:rocket_nose_cone (item.ad_astra.rocket_nose_cone, adastra-1.21.1-1.16.25-neoforge.jar) is an input of the
    # kept tier-1 rocket recipe (D6.2) and of no tier-5 recipe; neither list in check_quests names it
    assert "ad_astra:rocket_nose_cone" in ctx["in6"] - ctx["in5"] and not BANNED.fullmatch("ad_astra:rocket_nose_cone")
    assert epic_hits(_planted(tmp_path, "epic_bag", "minecraft:diamond", "ad_astra:rocket_nose_cone"), ctx) == [
        "ad_astra:rocket_nose_cone"]


def test_a_third_tier5_input_in_legendary_fails(ctx, tmp_path):
    # ae2:semi_dark_monitor (item.ae2.semi_dark_monitor, appliedenergistics2-19.2.17.jar) is the S5.3 terminal's monitor
    assert "ae2:semi_dark_monitor" in ctx["in5"] - ctx["in6"] and not BANNED.fullmatch("ae2:semi_dark_monitor")
    planted = _planted(tmp_path, "legendary_bag", "minecraft:diamond_block", "ae2:semi_dark_monitor")
    assert legendary_hits(planted, ctx) == ([], sorted(LEGENDARY_ALLOWED | {"ae2:semi_dark_monitor"}))


def test_the_me_controller_in_a_bag_fails(ctx, tmp_path):
    # ae2:controller: gates.yaml sole_producers [confluence:tier5/controller] (S5.2)
    assert gated_hits(_planted(tmp_path, "rare_bag", "mekanism:ingot_steel", "ae2:controller"), ctx) == [
        ("rare_bag", "ae2:controller")]


def test_a_piglich_heart_block_in_a_bag_fails(ctx, tmp_path):
    # allthemodium:piglich_heart_block crafts to 9 piglich hearts (recipe allthemodium:piglich_heart, shapeless)
    assert ("allthemodium:piglich_heart", "allthemodium:piglich_heart") in ctx["graph"]["allthemodium:piglich_heart_block"]
    planted = _planted(tmp_path, "epic_bag", "minecraft:diamond", "allthemodium:piglich_heart_block")
    hits = precursor_hits(planted, ctx)
    assert set(hits) - set(SHIPPED_PRECURSORS) == {("epic_bag", "allthemodium:piglich_heart_block")}
    assert "banned" in hits[("epic_bag", "allthemodium:piglich_heart_block")]


# The reviewers' chains (round 3, I4): each is two or more edges from a target, so the round-2 one-step rule passed it.
#   mysticalagriculture:fluix_seeds -> fluix_essence -> ae2:fluix_crystal (EXCLUDED "fluix");
#   mysticalagriculture:sky_stone_seeds -> sky_stone_essence (seed/reprocessor/sky_stone) -> ae2:sky_stone_block
#     (essence/appliedenergistics2/sky_stone; EXCLUDED "sky stone");
#   ae2:sky_stone_small_brick -> ae2:sky_stone_brick -> ae2:smooth_sky_stone_block (EXCLUDED; Mekanism's crushing rows
#     mekanism:compat/ae2/decorative/sky_stone/crushing/small_brick_to_brick and .../brick_to_smooth);
#   ae2:dark_monitor -> ae2:semi_dark_monitor (a tier-5 input, which the Legendary bag may hold the precursors of).
CHAINS = [("epic_bag", "mysticalagriculture:fluix_seeds", "banned"),
          ("legendary_bag", "mysticalagriculture:sky_stone_seeds", "banned"),
          ("epic_bag", "ae2:sky_stone_small_brick", "banned"),
          ("epic_bag", "ae2:dark_monitor", "in5")]


@pytest.mark.parametrize("table,item,code", CHAINS)
def test_a_planted_precursor_chain_fails(ctx, tmp_path, table, item, code):
    hits = precursor_hits(_planted(tmp_path, table, "minecraft:experience_bottle", item), ctx)
    assert set(hits) - set(SHIPPED_PRECURSORS) == {(table, item)} and code in hits[(table, item)]


# round 4, B3: the Common bag with a crafting table and a bucket in place of its bread and gold, beside its oak planks
BASE_SWAPS = [("minecraft:bread", "minecraft:crafting_table"), ("minecraft:gold_ingot", "minecraft:bucket")]


def test_a_common_bag_of_base_materials_passes(ctx, tmp_path):
    planted = _planted(tmp_path, "common_bag", *BASE_SWAPS)
    assert {"minecraft:crafting_table", "minecraft:bucket", "minecraft:oak_planks"} <= set(planted["common_bag"])
    assert precursor_hits(planted, ctx) == SHIPPED_PRECURSORS
    assert tier_hits(planted, ctx, SHIPPED_BAGS) == SHIPPED_TIER_HITS


def test_the_legendary_bag_may_hold_a_precursor_of_a_tier5_input(ctx, tmp_path):
    planted = _planted(tmp_path, "legendary_bag", "minecraft:experience_bottle", "ae2:dark_monitor")
    assert precursor_hits(planted, ctx) == SHIPPED_PRECURSORS


# ---- (f) the snapshot (round 3, I3): check_quests.py applies (a)-(e) from tools/bag_banned.json, with or without a dump ----

def test_the_snapshot_is_the_dump_recomputed(ctx):
    assert SNAPSHOT.is_file(), f"no {SNAPSHOT}: write it with `{SNAPSHOT_COMMAND}` (from pack/, after a boot)"
    assert json.loads(SNAPSHOT.read_text()) == snapshot_of(ctx), (
        f"{SNAPSHOT} is stale: regenerate with `{SNAPSHOT_COMMAND}` (from pack/, after a boot)")


# One planted table per check, read through check_quests.bag_collisions and the committed snapshot alone (no dump):
# (a) a tier-6 input in Epic, (b) a third tier-5 input in Legendary, (c) the ME controller, (d) the reviewers' chains.
PLANTS = [("epic_bag", "minecraft:diamond", "ad_astra:rocket_nose_cone"),
          ("legendary_bag", "minecraft:diamond_block", "ae2:semi_dark_monitor"),
          ("rare_bag", "mekanism:ingot_steel", "ae2:controller")] + [
          (t, "minecraft:experience_bottle", i) for t, i, _ in CHAINS]


@pytest.mark.parametrize("table,old,new", PLANTS)
def test_check_quests_fails_each_planted_table_from_the_snapshot(tmp_path, table, old, new):
    planted = _planted(tmp_path, table, old, new)
    assert [i for i, _ in bag_collisions(table, planted[table], load_snapshot(SNAPSHOT))] == [new]


# round 5: string, sand and glass make white wool and glass panes, which the base set now holds
COMMON_SWAPS = [("minecraft:bread", "minecraft:string"), ("minecraft:gold_ingot", "minecraft:sand"),
                ("mekanism:ingot_osmium", "minecraft:glass"), ("ars_nouveau:source_gem", "minecraft:white_wool")]


def test_a_common_bag_of_string_sand_glass_and_wool_passes(ctx, tmp_path):
    planted = _planted(tmp_path, "common_bag", *COMMON_SWAPS)
    assert {"minecraft:string", "minecraft:sand", "minecraft:glass", "minecraft:white_wool"} <= set(planted["common_bag"])
    assert precursor_hits(planted, ctx) == SHIPPED_PRECURSORS
    assert tier_hits(planted, ctx, SHIPPED_BAGS) == SHIPPED_TIER_HITS


def test_check_quests_passes_a_common_bag_of_string_sand_glass_and_wool(tmp_path):
    planted = _planted(tmp_path, "common_bag", *COMMON_SWAPS)
    assert bag_collisions("common_bag", planted["common_bag"], load_snapshot(SNAPSHOT)) == []


def test_check_quests_passes_a_common_bag_of_base_materials(tmp_path):
    planted = _planted(tmp_path, "common_bag", *BASE_SWAPS)
    assert bag_collisions("common_bag", planted["common_bag"], load_snapshot(SNAPSHOT)) == []


def test_the_exemption_spares_no_gate_item_in_epic(tmp_path):
    # round 4, B3: the ME controller (gated), a rocket nose cone (a tier-6 input) and fluix seeds (a precursor of fluix)
    planted = _planted(tmp_path, "epic_bag", ("minecraft:diamond", "ae2:controller"),
                       ("minecraft:experience_bottle", "ad_astra:rocket_nose_cone"),
                       ("minecraft:netherite_ingot", "mysticalagriculture:fluix_seeds"))
    hits = dict(bag_collisions("epic_bag", planted["epic_bag"], load_snapshot(SNAPSHOT)))
    assert sorted(hits) == ["ad_astra:rocket_nose_cone", "ae2:controller", "mysticalagriculture:fluix_seeds"]
    assert ("gated" in hits["ae2:controller"] and "in6" in hits["ad_astra:rocket_nose_cone"]
            and "pre:banned" in hits["mysticalagriculture:fluix_seeds"]), hits


def test_the_snapshot_names_no_base_material():
    doc = json.loads(SNAPSHOT.read_text())
    named = set(doc["tier5_inputs"]) | set(doc["tier6_inputs"]) | set(doc["gated_outputs"]) | set(doc["precursors"])
    assert named & BASE_MATERIALS == set()


def test_check_quests_passes_the_shipped_tables_and_legendarys_allowance(tmp_path, tables):
    snap = load_snapshot(SNAPSHOT)
    assert {t: bag_collisions(t, items, snap) for t, items in tables.items()} == {t: [] for t in tables}
    planted = _planted(tmp_path, "legendary_bag", "minecraft:experience_bottle", "ae2:dark_monitor")
    assert bag_collisions("legendary_bag", planted["legendary_bag"], snap) == []


if __name__ == "__main__":
    if sys.argv[1:] != ["--write-snapshot"]:
        sys.exit(f"usage: {SNAPSHOT_COMMAND}")
    problem = dump_problem()
    if problem:
        sys.exit(problem[1])
    built = context()
    if built["missing"]:
        sys.exit(f"classified recipes with no body in the dump: {built['missing']}")
    snapshot = snapshot_of(built)
    SNAPSHOT.write_text(snapshot_text(snapshot))
    print(f"wrote {SNAPSHOT}: {len(snapshot['tier5_inputs'])} tier-5 inputs, {len(snapshot['tier6_inputs'])} tier-6 inputs, "
          f"{len(snapshot['gated_outputs'])} gated outputs, {len(snapshot['precursors'])} precursors")
