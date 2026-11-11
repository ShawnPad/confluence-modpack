"""Route check (v1.0 spec §6.1, the D143 automated half; A18; plan Tasks 16-17).

Shows that every trunk node up to [X7.1] and every tier-7 leaf has a survival route, and that every gate on the way is
needed. A fixpoint over tokens (plan "Route group": items, fluid:, dim:, node:, bee:, comb:, egg:) from:
  - the boot's dump (.run/server/kubejs/exported/recipes.json), read with check_recipes.py's producer rule (made_by) and its
    key roles (key_role); a recipe is usable when its type is in route_sources.yaml machines: (whose items it then needs too);
  - the tag exports (item, block, fluid and chemical tag members) and kubejs/exported/ma_crops.json;
  - tools/route_sources.yaml (base, dimensions, sources, machines, ignored_types, accepted, soft_refs);
  - tools/route_generated.py (Mystical Agriculture crops, Productive Bees bees and combs);
  - progression/combined-tree.md (nodes and bracketed gate refs, check_quests.tree_nodes) and tools/chapters/*.yaml (each
    node's product: its quest task; each quest's deps).
Counts, energy, Source, chances and components are ignored (spec §6.1 model steps 5-6). The summary's "trunk nodes" are the
trunk (X7.1's ancestor closure) plus the 13 tier-7 leaves of the Catalyst chapter.

Failure codes (exit 1): UNREACHABLE, SKIPPABLE, EARLY, QUEST_ORDER, UNMODELLED (a/b/c), ACCEPTED_UNUSED, STALE, and the
generated sources' problems (UNMAPPED BIOME, BEE FLOWER, BEE DEFINITION, NO GENERATED SOURCE).

    python3 tools/check_route.py [--ban TOKEN]... [--disable UNIT]... [--json PATH] [--explain TOKEN] [--sources-edited]

--ban makes a token unobtainable and --disable removes a recipe id or source key, in every run (spec §7.5's fire charge
test). --sources-edited skips the STALE comparison against tools/gates.yaml and tools/route_sources.yaml while those files are
being written (plan Task 19); the loop and the release never pass it.
"""
import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "tests"))
from check_quests import NO_QUEST, TREE, tree_nodes  # noqa: E402
from check_recipes import DUMP, ITEM_MEMBERS, MANIFEST, json_item_id, key_role, load_manifest, load_sole_producers, made_by  # noqa: E402,E501
from route_generated import (GENERATED_TYPES, MA_CROPS, coverage_problems, load_bee_definitions, load_crops,  # noqa: E402
                             loaded_mod_ids, ma_rules, pb_jar, pb_rules)
from route_sources import ROUTE_SOURCES, Rule, load as load_sources, needs_groups  # noqa: E402
from scaffold_chapter import CHAPTERS_DIR, parse_chapter  # noqa: E402

ROOT = TOOLS.parent
EXPORTED = DUMP.parent
BLOCK_MEMBERS = EXPORTED / "block_tag_members.json"
FLUID_MEMBERS = EXPORTED / "fluid_tag_members.json"
EXPORTS = (DUMP, ITEM_MEMBERS, BLOCK_MEMBERS, FLUID_MEMBERS, MA_CROPS)
OVERWORLD = "minecraft:overworld"
TOP = "X7.1"
LEAF_CHAPTER = "catalyst"
ROOT_CHAPTERS = ("intro", "tier0")
TOP_TIER = 7
# Keys outside check_recipes.INGREDIENT_KEYS that hold a consumed fluid, read from the 0.3 dump at plan time (Task 16):
# Industrial Foregoing's inputFluid, Productive Bees' bottler `fluid`. Every other key the role table calls "other" is a
# setting (time, experience, energy) and is not read (A18).
FLUID_KEYS = frozenset({"inputFluid", "fluid"})
NOT_INPUTS = frozenset({"type", "pattern", "neoforge:conditions", "neoforge:load_conditions", "fabric:load_conditions"})
EACH_ELEMENT = frozenset({"ingredients", "input", "inputs", "pedestalItems"})   # a list here is one ingredient per element
PB_COMBS = frozenset({"productivebees:configurable_honeycomb", "productivebees:configurable_comb_block"})


class Reader:
    """Ingredient and product tokens of recipe bodies (spec §6.1 model step 7: a shape it does not read is None)."""

    def __init__(self, item_members, fluid_members, crops):
        self.items = item_members
        self.fluids = fluid_members
        self.crops = {c["id"]: c for c in crops}

    def tag(self, t, fluid=False):
        t = t.lstrip("#")
        if fluid:
            return frozenset("fluid:" + x for x in self.fluids.get(t, ()))
        return frozenset(self.items.get(t, ()))

    def tokens(self, v):
        """The tokens any one of which satisfies ingredient `v`, or None for a shape not read."""
        if isinstance(v, str):
            return self.tag(v) if v.startswith("#") else frozenset([json_item_id(v)])
        if isinstance(v, list):
            out = set()
            for x in v:
                t = self.tokens(x)
                if t is None:
                    return None
                out |= t
            return frozenset(out)
        if not isinstance(v, dict):
            return None
        typ = v.get("type")
        if typ == "neoforge:compound":
            return self.tokens(v.get("children", v.get("ingredients")))
        if typ == "neoforge:components":
            return self.tokens(v["items"]) if "items" in v else None
        if typ == "neoforge:difference":
            return self.tokens(v["base"]) if "base" in v else None   # the subtracted part is ignored: the generous reading
        if typ == "functionalstorage:tag_without_component":
            return self.tag(v["tag"]) if isinstance(v.get("tag"), str) else None
        if typ == "mysticalagriculture:crop_component":
            return self.crop_part(v.get("crop"), v.get("component"))
        if typ == "productivebees:component":
            bee = (v.get("components") or {}).get("productivebees:bee_type")
            return frozenset(["comb:" + bee]) if bee and v.get("items") in PB_COMBS else None
        if typ is not None:
            return None   # neoforge:intersection and every other custom ingredient type: fails closed
        if "ingredient" in v:
            return self.tokens(v["ingredient"])
        if isinstance(v.get("item"), str):
            return frozenset([v["item"]])
        if isinstance(v.get("tag"), str):
            return self.tag(v["tag"], fluid="amount" in v and "count" not in v)
        for k in ("fluid", "chemical", "gas"):
            if isinstance(v.get(k), str):
                return frozenset(["fluid:" + v[k]])
        if isinstance(v.get("id"), str):
            return frozenset(["fluid:" + v["id"]] if "amount" in v and "count" not in v else [v["id"]])
        return None

    def crop_part(self, crop, component):
        """Mystical Agriculture's CropComponentIngredient (MysticalAgriculture-1.21.1-8.0.28.jar, plan Task 16 correction C1):
        essence -> crop.getTier().getEssence() (ma_crops.json tier_essence), seed -> crop.getType().getCraftingSeed()
        (crafting_seed), material -> the crop's material. Not the crop's own essence and seeds."""
        c = self.crops.get(crop)
        if c is None:
            return None
        if component == "seed" and c.get("crafting_seed"):
            return frozenset([c["crafting_seed"]])
        if component == "essence" and c.get("tier_essence"):
            return frozenset([c["tier_essence"]])
        if component == "material" and c["material"]:
            m = c["material"]
            return self.tag(m["id"]) if m["tag"] else frozenset([m["id"]])
        return None

    def recipe_groups(self, body):
        """(groups, None), or (None, (key, value)) for the first ingredient not read."""
        rtype = body.get("type")
        groups = []
        for k, v in body.items():
            if k in NOT_INPUTS or v is None:
                continue
            role = key_role(rtype, k)
            if role in ("product", None) or (role == "other" and k not in FLUID_KEYS):
                continue
            if k == "key" and isinstance(v, dict):
                parts = list(v.values())
            elif k in EACH_ELEMENT and isinstance(v, list):
                parts = v
            else:
                parts = [v]
            for part in parts:
                t = self.tokens(part)
                if t is None:
                    return None, (k, part)
                groups.append(t)
        return tuple(groups), None

    def products(self, body):
        made = made_by(body)
        out = set(made.items) | {"fluid:" + c for c in made.chemicals}
        for t, kind in made.tags:
            out |= self.tag(t, fluid=kind == "chemical")
        out.discard("minecraft:air")
        return frozenset(out)


@dataclass
class Inputs:
    rows: list
    item_members: dict
    fluid_members: dict
    block_members: dict
    crops: list
    bee_defs: dict
    sources: dict
    tree_text: str
    chapters: dict
    gates: list
    sole: dict
    stale: list = field(default_factory=list)
    problems: list = field(default_factory=list)   # loading problems (bee definitions)


@dataclass
class Model:
    rules: list = field(default_factory=list)
    seed: frozenset = frozenset()
    unmodelled: list = field(default_factory=list)   # (code, type, recipe id, [watched products])
    problems: list = field(default_factory=list)
    by_unit: dict = field(default_factory=dict)
    makers: dict = field(default_factory=dict)
    waiting: dict = field(default_factory=dict)

    def index(self):
        for ri, r in enumerate(self.rules):
            if r.unit in self.by_unit:
                self.problems.append(f"DUPLICATE UNIT {r.unit}: a recipe id and a source key (or two keys) share it")
            self.by_unit[r.unit] = r
            for o in r.outputs:
                self.makers.setdefault(o, []).append(ri)
            for gi, g in enumerate(r.groups):
                for t in g:
                    self.waiting.setdefault(t, []).append((ri, gi))


def _body(row):
    return json.loads(row["json"]) if row and row.get("json") else None


def gate_inputs(reader, body):
    """Every token a gate recipe's readable ingredients name (an unread part adds nothing; the gate row itself is read as
    any other row below)."""
    out = set()
    if not body:
        return out
    rtype = body.get("type")
    for k, v in body.items():
        if k in NOT_INPUTS or v is None:
            continue
        role = key_role(rtype, k)
        if role in ("product", None) or (role == "other" and k not in FLUID_KEYS):
            continue
        parts = list(v.values()) if k == "key" and isinstance(v, dict) else v if isinstance(v, list) else [v]
        for part in parts:
            out |= reader.tokens(part) or frozenset()
    return out


def build_model(inp, watched_nodes):
    """The rules of every usable recipe, source, dimension and generated source. watched_nodes: the checked nodes' products;
    gate inputs and sole_producers outputs are added here (spec §6.1 UNMODELLED)."""
    srcs = inp.sources
    reader = Reader(inp.item_members, inp.fluid_members, inp.crops)
    model = Model()
    seed = {"dim:" + OVERWORLD}
    for b in srcs["base"]:
        seed |= {b["id"]} if "id" in b else reader.tag(b["tag"])
    model.seed = frozenset(seed)
    for d in srcs["dimensions"]:
        if d["from"] is None:
            continue
        for i, lst in enumerate(d["enter"]):
            model.rules.append(Rule(f"dim:{d['id']}#{i}", ("dim:" + d["id"],),
                                    (frozenset(["dim:" + d["from"]]),) + needs_groups(lst)))
    for s in srcs["sources"]:
        outs = tuple(x for x in (s["item"], "node:" + s["node"] if s.get("node") else None) if x)
        model.rules.append(Rule(s["key"], outs, (frozenset(["dim:" + s["dimension"]]),) + needs_groups(s["needs"])))
    machines = {m["type"]: needs_groups(m["needs"]) for m in srcs["machines"]}
    ignored = {i["type"] for i in srcs["ignored_types"]}
    rows = {r["id"]: r for r in inp.rows}
    watched = set(watched_nodes)
    watched |= {o if kind == "item" else "fluid:" + o for o, (kind, _) in inp.sole.items()}
    for g in inp.gates:
        watched |= gate_inputs(reader, _body(rows.get(g)))
    for row in inp.rows:
        body = _body(row)
        t = row.get("type")
        if body is None or t in GENERATED_TYPES:
            continue
        prods = reader.products(body)
        hits = sorted(prods & watched)
        if t in ignored:
            if hits:
                model.unmodelled.append(("b", t, row["id"], hits))
            continue
        if t not in machines:
            if hits:
                model.unmodelled.append(("a", t, row["id"], hits))
            continue
        groups, bad = reader.recipe_groups(body)
        if bad is not None:
            if hits:
                model.unmodelled.append(("c", t, row["id"], hits))
            continue
        model.rules.append(Rule(row["id"], tuple(sorted(prods)), groups + machines[t]))
    biome_map = {b["biome"]: b["dimension"] for b in srcs["biome_dimensions"]}
    ma, p1 = ma_rules(inp.crops, biome_map)
    pb, p2 = pb_rules(inp.rows, inp.bee_defs, inp.block_members, inp.fluid_members, inp.item_members, biome_map,
                      {t: machines[t] for t in GENERATED_TYPES if t in machines}, reader.tokens, reader.products)
    model.rules += ma + pb
    model.problems += list(inp.problems) + p1 + p2 + coverage_problems(inp.crops, ma + pb, inp.rows, inp.item_members)
    model.index()
    return model


def fixpoint(model, ban=frozenset(), disable=frozenset()):
    """({token: the unit that first made it, 'base' for the seed}, {units that ran}) under the bans."""
    reached, fired, queue = {}, set(), []
    left = [-1 if r.unit in disable else len(r.groups) for r in model.rules]
    met = [None] * len(model.rules)

    def give(t, unit):
        if t not in reached and t not in ban:
            reached[t] = unit
            queue.append(t)

    def fire(ri):
        r = model.rules[ri]
        fired.add(r.unit)
        for o in r.outputs:
            give(o, r.unit)

    for t in sorted(model.seed):
        give(t, "base")
    for ri, n in enumerate(left):
        if n == 0:
            fire(ri)
    i = 0
    while i < len(queue):
        t = queue[i]
        i += 1
        for ri, gi in model.waiting.get(t, ()):
            if left[ri] <= 0:
                continue
            if met[ri] is None:
                met[ri] = set()
            if gi in met[ri]:
                continue
            met[ri].add(gi)
            left[ri] -= 1
            if left[ri] == 0:
                fire(ri)
    return reached, fired


def blockers(model, reached, token, ban=frozenset(), limit=400):
    """Why a token is not reached, down to the raw leaves: 'unsourced <t>' (no rule makes it), 'banned <t>'."""
    out, seen, stack = set(), set(), [token]
    while stack and len(seen) < limit:
        t = stack.pop()
        if t in seen or t in reached:
            continue
        seen.add(t)
        if t in ban:
            out.add(f"banned {t}")
            continue
        makers = model.makers.get(t, ())
        if not makers:
            out.add(f"unsourced {t}")
            continue
        for ri in makers:
            for g in model.rules[ri].groups:
                if not any(x in reached for x in g):
                    stack.extend(sorted(g)[:3] if g else [])
                    if not g:
                        out.add(f"empty group in {model.rules[ri].unit}")
    return sorted(out)


def explain(model, reached, token, ban=frozenset()):
    """(lines, units): one witness tree for `token`, each step the earliest-reached token of each group."""
    order = {t: i for i, t in enumerate(reached)}
    lines, units, seen = [], [], set()

    def walk(t, depth):
        unit = reached.get(t)
        if unit is None:
            lines.append("  " * depth + f"{t} NOT REACHED: " + ", ".join(blockers(model, reached, t, ban)))
            return
        if t in seen:
            lines.append("  " * depth + f"{t} <- {unit} (above)")
            return
        seen.add(t)
        lines.append("  " * depth + f"{t} <- {unit}")
        if unit == "base":
            return
        units.append(unit)
        for g in model.by_unit[unit].groups:
            walk(min((x for x in g if x in reached), key=order.__getitem__), depth + 1)

    walk(token, 0)
    return lines, units


def task_product(node, task):
    """A quest task's product token (spec §6.1 inputs): item:<id>[:count] -> the item; dimension:<id> -> dim:<id>;
    kill:, advancement: and checkmark -> node:<node>."""
    kind, _, rest = task.partition(":")
    if kind == "item":
        return ":".join(rest.split(":")[:2])
    if kind == "dimension":
        return "dim:" + rest
    if kind in ("kill", "advancement", "checkmark"):
        return "node:" + node
    return None


def node_products(chapters):
    return {q["node"]: task_product(q["node"], q.get("task", "")) for ch in chapters.values() for q in ch["quests"]
            if q.get("node")}


def trunk_nodes(tree):
    """TOP and every node its gate refs reach, transitively (NO_QUEST nodes are not tree_nodes keys and are left out)."""
    seen, stack = set(), [TOP]
    while stack:
        n = stack.pop()
        if n in seen or n not in tree:
            continue
        seen.add(n)
        stack.extend(tree[n])
    return seen


def quest_order(chapters, accepted_roots):
    """(problems, accepted roots used): every dependency chain back from TOP's quest ends at a dep-less quest of
    ROOT_CHAPTERS, or at an accepted QUEST_ORDER root; no cycle. Dangling ids are check_quests.py's job and are skipped."""
    deps, home = {}, {}
    for name, ch in chapters.items():
        for q in ch["quests"]:
            if q.get("node"):
                deps[q["node"]] = q.get("deps") or []
                home[q["node"]] = name
    problems, used, state = [], set(), {}

    def walk(n, path):
        if state.get(n) == 2:
            return
        if state.get(n) == 1:
            problems.append("QUEST_ORDER cycle " + " -> ".join(path[path.index(n):] + [n]))
            return
        state[n] = 1
        if not deps[n]:
            if n in accepted_roots:
                used.add(n)
            elif home[n] not in ROOT_CHAPTERS:
                problems.append(f"QUEST_ORDER {n} ({home[n]}.yaml) has no deps and is not in intro.yaml or tier0.yaml")
        for d in deps[n]:
            if d in deps:
                walk(d, path + [n])
        state[n] = 2

    if TOP in deps:
        walk(TOP, [])
    else:
        problems.append(f"QUEST_ORDER no quest for {TOP} in tools/chapters")
    return problems, used


@dataclass
class Report:
    summary: str
    failures: list
    nodes: dict
    model: object = None
    full: dict = field(default_factory=dict)


def tree_tier(n):
    return int(n[1:].split(".")[0])


def run_checks(inp, ban=frozenset(), disable=frozenset()):
    if inp.stale:
        return Report(f"route: not run ({len(inp.stale)} export problems)", list(inp.stale), {})
    srcs = inp.sources
    tree = tree_nodes(inp.tree_text, set(range(TOP_TIER + 1)))
    products = node_products(inp.chapters)
    leaves = {n: p for n, p in node_products({LEAF_CHAPTER: inp.chapters.get(LEAF_CHAPTER, {"quests": []})}).items()
              if n != TOP}
    trunk = trunk_nodes(tree)
    checked = sorted(trunk) + sorted(leaves)
    refs = {n: [r for r in tree[n] if r not in NO_QUEST] for n in trunk}
    refs.update({n: [TOP] for n in leaves})
    model = build_model(inp, {p for n in checked if (p := products.get(n))})
    fails = list(model.problems)
    full, fired = fixpoint(model, ban, disable)
    nodes, counts = {}, Counter()
    for n in checked:
        p = products.get(n)
        if p is None:
            fails.append(f"UNREACHABLE {n}: no quest in tools/chapters names this node")
            nodes[n] = {"product": None, "reachable": False, "first_tier": None, "witness": [], "skippable_by": []}
            counts["unreachable"] += 1
            continue
        ok = p in full
        nodes[n] = {"product": p, "reachable": ok, "first_tier": None,
                    "witness": explain(model, full, p, ban)[1] if ok else [], "skippable_by": []}
        counts["reachable" if ok else "unreachable"] += 1
        if not ok:
            fails.append(f"UNREACHABLE {n} ({p}): " + ", ".join(blockers(model, full, p, ban)))
    ctx = Ctx(model, srcs, refs, products, nodes, frozenset(ban), frozenset(disable))
    fails += skippable_checks(ctx, checked, counts)
    fails += early_checks(ctx, trunk, counts)
    qo, roots_used = quest_order(inp.chapters, {n for e in srcs["accepted"] if e["code"] == "QUEST_ORDER"
                                                for n in _nodes(e)})
    fails += qo
    fails += accepted_checks(ctx, checked, tree, leaves, fired, roots_used)
    kinds = sorted({(code, t) for code, t, _, _ in model.unmodelled})
    for code, t in kinds:
        rids = sorted(rid for c, tt, rid, _ in model.unmodelled if (c, tt) == (code, t))
        hits = sorted({h for c, tt, _, hs in model.unmodelled if (c, tt) == (code, t) for h in hs})
        fails.append(f"UNMODELLED ({code}) {t}: {len(rids)} recipes make watched items ({', '.join(rids[:5])}"
                     f"{', …' if len(rids) > 5 else ''}): {', '.join(hits[:8])}{', …' if len(hits) > 8 else ''}")
    summary = (f"route: {len(checked)} trunk nodes, {counts['reachable']} reachable, {counts['unreachable']} unreachable, "
               f"{counts['skippable']} skippable, {counts['early']} early, {len(kinds)} unmodelled types")
    return Report(summary, fails, nodes, model, full)


def _nodes(entry):
    return entry["node"] if isinstance(entry["node"], list) else [entry["node"]]


@dataclass
class Ctx:
    """What SKIPPABLE, EARLY and ACCEPTED_UNUSED share: the model, the bans of every run, and each checked node's refs."""
    model: object
    srcs: dict
    refs: dict
    products: dict
    nodes: dict
    ban: frozenset
    disable: frozenset
    soft: set = field(default_factory=set)
    by_node: dict = field(default_factory=dict)      # tree node -> keys of the sources whose node: it is
    cache: dict = field(default_factory=dict)

    def __post_init__(self):
        self.soft = {(s["node"], s["ref"]) for s in self.srcs["soft_refs"]}
        for s in self.srcs["sources"]:
            if s.get("node"):
                self.by_node.setdefault(s["node"], set()).add(s["key"])

    def run(self, ban, disable):
        key = (frozenset(ban), frozenset(disable))
        if key not in self.cache:
            self.cache[key] = fixpoint(self.model, *key)
        return self.cache[key]

    def accepted_units(self, code, node, but=None):
        """The units of every accepted `code` route for `node`, except entry `but` (whose own units stay on)."""
        out = set()
        for e in self.srcs["accepted"]:
            if e["code"] == code and e is not but and node in _nodes(e):
                out |= set(e["route"])
        return out - set(but["route"] if but else ())

    def gate_refs(self, n):
        """(ref, its product) for each non-soft gate ref of n that has a product."""
        return [(r, self.products[r]) for r in self.refs.get(n, []) if (n, r) not in self.soft and self.products.get(r)]

    def skip_runs(self, n, off):
        """(ref, product, (reached, fired)) for each gate ref R of n: R's product banned, R's own sources and `off` disabled."""
        return [(r, rp, self.run(self.ban | {rp}, self.disable | self.by_node.get(r, set()) | off))
                for r, rp in self.gate_refs(n)]

    def first_tiers(self, off):
        """({token: first dimension tier it is reached at}, {tier: units that ran}): a tier-k run closes every dimension of a
        higher tier."""
        first, fired_at = {}, {}
        for k in sorted({d["tier"] for d in self.srcs["dimensions"]}):
            closed = {"dim:" + d["id"] for d in self.srcs["dimensions"] if d["tier"] > k}
            reached, fired_at[k] = self.run(self.ban | closed, self.disable | off)
            for t in reached:
                first.setdefault(t, k)
        return first, fired_at

    def early(self, n, first):
        """(n's first tier, (ref tier, ref)) when n is reached before its latest gate ref, else None. TOP is skipped."""
        if tree_tier(n) >= TOP_TIER or not self.nodes[n]["reachable"]:
            return None
        ft = first.get(self.nodes[n]["product"])
        ref_ft = [(first[rp], r) for r, rp in self.gate_refs(n) if rp in first]
        if ft is None or not ref_ft or ft >= max(ref_ft)[0]:
            return None
        return ft, max(ref_ft)


def skippable_checks(ctx, checked, counts):
    """SKIPPABLE: N still reachable with a gate ref's product banned, the ref's own sources and every accepted SKIPPABLE route
    for N disabled, so an accepted route cannot hide a second one (spec §6.1)."""
    fails = []
    for n in checked:
        if not ctx.nodes[n]["reachable"]:
            continue
        p = ctx.nodes[n]["product"]
        for r, rp, (got, _) in ctx.skip_runs(n, ctx.accepted_units("SKIPPABLE", n)):
            if p in got:
                ctx.nodes[n]["skippable_by"].append(r)
                ban = ctx.ban | {rp}
                fails.append(f"SKIPPABLE {n} without [{r}] ({rp}): " + " ".join(explain(ctx.model, got, p, ban)[1]))
        if ctx.nodes[n]["skippable_by"]:
            counts["skippable"] += 1
    return fails


def early_checks(ctx, trunk, counts):
    """EARLY: N's first tier is below the highest first tier of its (non-soft) gate refs' products, not N's tree tier; accepted
    EARLY routes are disabled in these runs (spec §6.1). The top tier adds no dimension and is skipped."""
    off = set()
    for e in ctx.srcs["accepted"]:
        if e["code"] == "EARLY":
            off |= set(e["route"])
    first, _ = ctx.first_tiers(off)
    for n in ctx.nodes:
        ctx.nodes[n]["first_tier"] = first.get(ctx.nodes[n]["product"])
    fails = []
    for n in sorted(trunk):
        hit = ctx.early(n, first)
        if hit:
            counts["early"] += 1
            fails.append(f"EARLY {n}: reachable at tier {hit[0]}, before its gate ref [{hit[1][1]}] (tier {hit[1][0]})")
    return fails


def accepted_checks(ctx, checked, tree, leaves, fired, roots_used):
    """ACCEPTED_UNUSED: an accepted route that is empty or has a unit that never runs in the full fixpoint; a SKIPPABLE/EARLY
    route that no longer reaches its node on its own (its node's other accepted routes of that code off, the route's units all
    run, and the node is reached without a gate ref / before its gate refs); an accepted QUEST_ORDER root that no chain reaches;
    or a soft_refs pair that is no longer a gate ref."""
    fails = []
    for e in ctx.srcs["accepted"]:
        head = f"ACCEPTED_UNUSED {'/'.join(_nodes(e))} {e['code']} ({e['decision']}): "
        if e["code"] == "QUEST_ORDER":
            for n in _nodes(e):
                if n not in roots_used:
                    fails.append(f"ACCEPTED_UNUSED {n} QUEST_ORDER ({e['decision']}): not a dep-less quest on {TOP}'s chains")
            continue
        if not e["route"]:
            fails.append(head + "empty route")
            continue
        idle = [u for u in e["route"] if u not in fired]
        if idle:
            fails.append(head + ", ".join(f"{u} never runs" for u in idle))
            continue
        route = set(e["route"])
        for n in _nodes(e):
            if n not in ctx.nodes or n not in checked:
                fails.append(head + "not a trunk node or tier-7 leaf")
                continue
            p = ctx.nodes[n]["product"]
            off = ctx.accepted_units(e["code"], n, but=e)
            if e["code"] == "SKIPPABLE":
                ok = any(p in got and route <= ran for _, _, (got, ran) in ctx.skip_runs(n, off))
                if not ok:
                    fails.append(head + f"does not reach {n} without any gate ref on its own")
            elif e["code"] == "EARLY":
                first, fired_at = ctx.first_tiers(off)
                hit = ctx.early(n, first)
                if not (hit and route <= fired_at[hit[0]]):
                    fails.append(head + f"does not reach {n} before its gate refs on its own")
    for s in ctx.srcs["soft_refs"]:
        if s["ref"] not in tree.get(s["node"], []) and not (s["node"] in leaves and s["ref"] == TOP):
            fails.append(f"ACCEPTED_UNUSED soft_ref {s['node']} -> {s['ref']}: not one of its gate refs")
    return fails


def staleness_problems(exports, newest):
    """STALE lines: exports maps each export path to its mtime (None when missing); newest is (mtime, name) of the newest
    input the exports must not be older than. The comparison is test_dump_bodies.staleness (spec §6.1 STALE)."""
    from test_dump_bodies import staleness
    out = []
    for path, mtime in exports.items():
        if mtime is None:
            out.append(f"STALE {path.name} missing (boot with tools/server_boot.sh first)")
        elif staleness(mtime, newest) is not None:
            out.append(f"STALE {path.name} is older than {newest[1]} (boot first)")
    return out


def newest_input(include_sources=True):
    import test_dump_bodies   # looked up at call time (the tests replace newest_kubejs_file)
    candidates = [test_dump_bodies.newest_kubejs_file(ROOT)]
    if include_sources:
        candidates += [(MANIFEST.stat().st_mtime, "tools/gates.yaml"), (ROUTE_SOURCES.stat().st_mtime, "tools/route_sources.yaml")]
    return max(candidates, key=lambda c: c[0])


def load_inputs(include_sources=True):
    stale = staleness_problems({p: (p.stat().st_mtime if p.is_file() else None) for p in EXPORTS},
                               newest_input(include_sources))
    if stale:
        return Inputs([], {}, {}, {}, [], {}, {}, "", {}, [], {}, stale)
    items = json.loads(ITEM_MEMBERS.read_text())["minecraft:item"]
    fluid_doc = json.loads(FLUID_MEMBERS.read_text())
    fluids = {**fluid_doc["minecraft:fluid"], **fluid_doc["mekanism:chemical"]}
    jar = pb_jar()
    defs, problems = (load_bee_definitions(jar, loaded_mod_ids(), items, fluids) if jar
                      else ({}, ["BEE DEFINITION no productivebees jar in .run/server/mods"]))
    gates, _ = load_manifest(MANIFEST)
    return Inputs(
        rows=json.loads(DUMP.read_text()), item_members=items, fluid_members=fluids,
        block_members=json.loads(BLOCK_MEMBERS.read_text())["minecraft:block"], crops=load_crops(), bee_defs=defs,
        sources=load_sources(), tree_text=TREE.read_text(),
        chapters={p.stem: parse_chapter(p.read_text()) for p in sorted(CHAPTERS_DIR.glob("*.yaml"))},
        gates=gates, sole=load_sole_producers(MANIFEST), problems=problems)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ban", action="append", default=[], help="a token to make unobtainable in every run")
    ap.add_argument("--disable", action="append", default=[], help="a recipe id or source key to remove in every run")
    ap.add_argument("--json", help="write {node: {product, reachable, first_tier, witness, skippable_by}} here")
    ap.add_argument("--explain", help="print one witness tree for this token")
    ap.add_argument("--sources-edited", action="store_true", help="skip STALE against gates.yaml and route_sources.yaml")
    a = ap.parse_args(argv)
    rep = run_checks(load_inputs(not a.sources_edited), frozenset(a.ban), frozenset(a.disable))
    if a.explain and rep.model is not None:
        print("\n".join(explain(rep.model, rep.full, a.explain, frozenset(a.ban))[0]))
    print(rep.summary)
    for f in rep.failures:
        print("  " + f)
    if a.json:
        Path(a.json).write_text(json.dumps(rep.nodes, indent=1, sort_keys=True) + "\n")
    return 1 if rep.failures else 0


if __name__ == "__main__":
    sys.exit(main())
