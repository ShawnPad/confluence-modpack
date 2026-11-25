"""tools/route_sources.yaml: the hand-kept, cited non-recipe sources of tools/check_route.py (v1.0 spec §6.1, A18; plan Task 14).

No PyYAML is installed, so the file is a YAML subset this module reads by itself:
  - a section header `name:` at column 0, one of SECTIONS;
  - entries `  - {...}`, one JSON object per line;
  - blank lines, and comment lines whose first non-blank character is '#'.
Anything else is an error naming its line. Every entry carries "cite" (a research section, a decision or a jar path), except
accepted: entries, which carry "decision" (the D-number the owner confirmed). parse() checks each entry's keys and value
shapes and never guesses: id-like fields are non-blank strings, an object may not repeat a key, NaN and Infinity are
refused, and kind "quest" goes with item null (and a node). After the entries it cross-checks that exactly one dimension
is the root (from: null) and that every dimensions.from, sources.dimension and biome_dimensions.dimension names a listed
dimension.

Rule and needs_groups are shared by route_generated.py and check_route.py. Tokens (plan "Route group"): an item id,
'fluid:<id>' (a fluid), 'chem:<id>' (a Mekanism chemical; Task 18 review C8: 12 ids are both), 'dim:<id>', 'node:<id>',
'bee:<id>', 'comb:<bee id>'.
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE_SOURCES = ROOT / "tools" / "route_sources.yaml"
# section -> (required keys, optional keys). base: exactly one of id/tag.
SECTIONS = {
    "base": ({"cite"}, {"id", "tag"}),
    "dimensions": ({"id", "tier", "from", "enter", "cite"}, set()),
    "biome_dimensions": ({"biome", "dimension", "cite"}, set()),
    "sources": ({"key", "item", "dimension", "kind", "needs", "cite"}, {"node"}),
    "machines": ({"type", "needs", "cite"}, set()),
    "ignored_types": ({"type", "cite"}, set()),
    "accepted": ({"node", "code", "route", "decision"}, {"note"}),
    "soft_refs": ({"node", "ref", "cite"}, set()),
}
# Spec §6.1's kinds, plus "quest": the source that is a checkmark quest itself (it makes node:<id> and no item; plan Task 14).
KINDS = {"worldgen", "loot", "mob", "boss", "trade", "process", "crop", "comb", "quest"}
CODES = {"SKIPPABLE", "EARLY", "QUEST_ORDER"}
MAX_TIER = 7
HEADER = re.compile(r"^([A-Za-z_]+):\s*$")
ENTRY = re.compile(r"^  - (.*)$")
DECISION = re.compile(r"^D[0-9]+$")


class RouteSourceError(ValueError):
    pass


@dataclass(frozen=True)
class Rule:
    """One way to make tokens. `unit` is a dump recipe id or a sources: key (what --disable and accepted: routes name);
    `outputs` become reachable once every group in `groups` has any one of its tokens reachable."""
    unit: str
    outputs: tuple
    groups: tuple


def needs_groups(needs) -> tuple:
    """`needs` as rule groups: each element is a token (a group of one) or a list of tokens (any one of them)."""
    return tuple(frozenset([n]) if isinstance(n, str) else frozenset(n) for n in needs)


def _str(v):
    return isinstance(v, str) and v.strip() != ""


# Fields that hold an id or a name: a non-blank string, or (the second set) a non-blank string or null. Checked before any
# other test, so a list or a number never reaches a set or a dict as a raw TypeError.
STR_FIELDS = {
    "dimensions": ({"id"}, {"from"}),
    "biome_dimensions": ({"biome", "dimension"}, set()),
    "sources": ({"key", "dimension", "node"}, {"item"}),
    "machines": ({"type"}, set()),
    "ignored_types": ({"type"}, set()),
    "accepted": ({"note"}, set()),
    "soft_refs": ({"node", "ref"}, set()),
}


class _BadJSON(ValueError):
    pass


def _no_dup_keys(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise _BadJSON(f"duplicate JSON key {k}")
        out[k] = v
    return out


def _no_constant(name):
    raise _BadJSON(f"{name} is not allowed")


def _needs_ok(v):
    return isinstance(v, list) and all(_str(n) or (isinstance(n, list) and n and all(_str(x) for x in n)) for n in v)


def _entry_problem(section, e):
    """The first problem with one entry, or None."""
    required, optional = SECTIONS[section]
    for k in sorted(required - set(e)):
        return f"missing {k}"
    for k in sorted(set(e) - required - optional):
        return f"unknown key {k}"
    if "cite" in e and not _str(e["cite"]):
        return "missing cite"
    strs, nullable = STR_FIELDS.get(section, (set(), set()))
    for k in sorted(strs & set(e)):
        if not _str(e[k]):
            return f"{k} must be a non-empty string"
    for k in sorted(nullable & set(e)):
        if not (e[k] is None or _str(e[k])):
            return f"{k} must be a non-empty string or null"
    if section == "base" and (("id" in e) == ("tag" in e) or not _str(e.get("id", e.get("tag")))):
        return "base entry needs exactly one of id or tag"
    if section == "dimensions":
        if not isinstance(e["tier"], int) or isinstance(e["tier"], bool) or not 0 <= e["tier"] <= MAX_TIER:
            return f"tier must be an integer 0-{MAX_TIER}"
        if not (e["from"] is None or _str(e["from"])):
            return "from must be a dimension id or null"
        if not (isinstance(e["enter"], list) and e["enter"] and all(isinstance(x, list) and all(_str(i) for i in x)
                                                                     for x in e["enter"])):
            return "enter must be a list of lists of ids"
    if section == "sources":
        if not isinstance(e["kind"], str) or e["kind"] not in KINDS:
            return f"kind {e['kind']} is not one of {sorted(KINDS)}"
        if not _needs_ok(e["needs"]):
            return "needs must be a list of ids or non-empty lists of ids"
        if e["item"] is None and not _str(e.get("node")):
            return "item null needs node"
        if e["kind"] == "quest" and e["item"] is not None:
            return "kind quest needs item null"
        if e["kind"] != "quest" and e["item"] is None:
            return f"item null needs kind quest (kind is {e['kind']})"
    if section == "machines" and not _needs_ok(e["needs"]):
        return "needs must be a list of ids or non-empty lists of ids"
    if section == "accepted":
        nodes = e["node"] if isinstance(e["node"], list) else [e["node"]]
        if not nodes or not all(_str(n) for n in nodes):
            return "node must be a node id or a list of them"
        if not isinstance(e["code"], str) or e["code"] not in CODES:
            return f"code {e['code']} is not one of {sorted(CODES)}"
        if not (isinstance(e["route"], list) and all(_str(u) for u in e["route"])):
            return "route must be a list of recipe ids and source keys"
        if not (isinstance(e["decision"], str) and DECISION.match(e["decision"])):
            return "decision must be D<digits>"
    return None


def parse(text: str, name: str = "tools/route_sources.yaml") -> dict:
    out = {s: [] for s in SECTIONS}
    section = None
    lines = []  # (line, section, entry), for the cross-checks after the loop
    header_line = {}
    seen = {"sources": {}, "dimensions": {}, "machines": {}, "ignored_types": {}}
    unique = {"sources": "key", "dimensions": "id", "machines": "type", "ignored_types": "type"}
    for n, line in enumerate(text.splitlines(), 1):
        def fail(msg):
            raise RouteSourceError(f"{name} line {n}: {msg}")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        h = HEADER.match(line)
        if h:
            if h.group(1) not in SECTIONS:
                fail(f"unknown section {h.group(1)}")
            section = h.group(1)
            header_line.setdefault(section, n)
            continue
        m = ENTRY.match(line)
        if not m or section is None:
            fail("not a header, entry or comment")
        try:
            e = json.loads(m.group(1), object_pairs_hook=_no_dup_keys, parse_constant=_no_constant)
        except ValueError as err:
            fail(f"not JSON ({err})")
        if not isinstance(e, dict):
            fail("not JSON object")
        problem = _entry_problem(section, e)
        if problem:
            fail(problem)
        if section in unique:
            k = e[unique[section]]
            if k in seen[section]:
                fail(f"duplicate {unique[section]} {k} (first at line {seen[section][k]})")
            seen[section][k] = n
        out[section].append(e)
        lines.append((n, section, e))
    both = sorted(set(seen["machines"]) & set(seen["ignored_types"]))
    if both:
        raise RouteSourceError(f"{name} line {seen['ignored_types'][both[0]]}: {both[0]} is both machine and ignored")
    _cross_check(name, lines, seen["dimensions"], header_line, n_lines=len(text.splitlines()))
    return out


def _cross_check(name, lines, dims, header_line, n_lines):
    """Exactly one root dimension (from: null); every dimensions.from, sources.dimension and biome_dimensions.dimension is a
    listed dimension (Task 18 review C6)."""
    roots = [(n, e["id"]) for n, s, e in lines if s == "dimensions" and e["from"] is None]
    if not roots:
        where = header_line.get("dimensions", n_lines)
        raise RouteSourceError(f"{name} line {where}: no root dimension (one dimensions: entry needs from: null)")
    if len(roots) > 1:
        raise RouteSourceError(f"{name} line {roots[1][0]}: {roots[1][1]} is a second root dimension "
                               f"(first {roots[0][1]} at line {roots[0][0]})")
    for n, s, e in lines:
        ref = e["from"] if s == "dimensions" else e["dimension"] if s in ("sources", "biome_dimensions") else None
        if ref is not None and ref not in dims:
            raise RouteSourceError(f"{name} line {n}: unknown dimension {ref} (not in dimensions:)")


def load(path: Path = ROUTE_SOURCES) -> dict:
    return parse(path.read_text(), str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path))
