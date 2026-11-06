"""Prove that every tag the pack references is bound and non-empty.

An ingredient that points at a tag no mod defines loads with zero KubeJS errors, shows up in the recipe
dump, passes tools/check_recipes.py -- and is uncraftable in game (the `#c:gems/zanite` defect, D69).
This checker closes that hole: kubejs/server_scripts/tagcheck.js exports every bound tag with its element
count at ServerEvents.loaded, and this script asserts that every tag the pack *references* is in there
with a count > 0. A tag that passes in its registry but is bound with 0 entries in another one (the "empty twin", e.g. a
block tag missing from NON_ITEM_TAGS that passes as an item tag of the same id) fails too.

References are collected from three places:
  1. every `'#namespace:path'` / `"#namespace:path"` literal in kubejs/{server,startup,client}_scripts/**/*.js
     (this covers the whole IDS object in lib/ids.js, including nested objects), comments stripped;
  2. every `"tag": "<id>"` value, at any depth, in kubejs/data/**/*.json (recipe ingredients drop the '#');
  3. nothing else -- a tag the pack neither names in a script nor in a datapack file is not its problem.

A second, closed check proves spec §7 D112(a) at every boot (v0.3 plan Task 8; events.js). The nine tool-tier deny tags that
ship empty get ATM's four netherite-tier tags, so each must hold exactly the sum of those four (4 + 3 + 20 + 0 = 27 at 0.3.0).
Both lists are read from lib/ids.js (IDS.tierOres.incorrectForTags, needsToolTags and alloyToolTagEmpty). The export holds
counts, not members, so the check is that arithmetic, and a deny tag or needs tag missing from the export fails as well.
Its result is printed on its own line after the reference lines, and its failures are also added to the first line's bad
count, so that line reads "0 bad" exactly when the exit status is 0 (later steps read it with `head -1`).

A third check (v0.3 Task 8c) reads members, not counts: tagcheck.js also writes kubejs/exported/tag_members.json, the block ids
in each D112 tag (the nine deny tags, the four needs tags, wither_immune and the four Cataclysm immune tags; lib/ids.js's
IDS.tierOres lists). It asserts spec §7 D112 by name, which the counts cannot (a deny tag of 27 may hold the wrong 27):
  - D112(b): the five tier ores (IDS.tierOres.blocks) are in wither_immune and in each Cataclysm immune tag;
  - D112(a): no deny tag holds a block outside the union of the four needs tags, and the Vibranium and Unobtainium ores are in
    every deny tag (IDS.allthemodium.vibraniumOre, otherVibraniumOre and unobtainiumOre: allthemodium-3.0.1_mc_1.21.1.jar!data/
    c/tags/block/needs_allthemodium_tool.json lists both Vibranium ores and needs_vibranium_tool.json the Unobtainium ore; the
    two Allthemodium ores are in no needs tag, so no deny tag holds them);
  - a members file, a registry or a tag missing from it fails.
Its line follows the deny-tags line, and its failures count in the first line's bad count too.

Both members exports are this boot's (Task 8c round 2, R4): tagcheck.js writes tags.json, tag_members.json and
item_tag_members.json (the members of every bound minecraft:item tag, which tools/check_recipes.py reads to expand tag products)
from one registry walk, so every exported tag's member list must be as long as tags.json's count for it (STALE otherwise), and
the item export must hold every minecraft:item tag tags.json binds (NOT EXPORTED otherwise). A member value that is not a list
of strings fails (BAD MEMBERS). The item export's line comes last, and its failures count in the first line's bad count too.

Run after tools/server_boot.sh:  python3 tools/check_tags.py
"""
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / ".run" / "server" / "kubejs" / "exported" / "tags.json"
MEMBERS = ROOT / ".run" / "server" / "kubejs" / "exported" / "tag_members.json"
ITEM_MEMBERS = ROOT / ".run" / "server" / "kubejs" / "exported" / "item_tag_members.json"
IDS_JS = ROOT / "kubejs" / "server_scripts" / "lib" / "ids.js"

SCRIPT_DIRS = ("kubejs/server_scripts", "kubejs/startup_scripts", "kubejs/client_scripts")
DATA_DIR = "kubejs/data"

ITEM_REGISTRY = "minecraft:item"

# Referenced tags that live in a registry other than minecraft:item. Every entry needs the source line that
# proves it, because guessing the registry is how an empty tag slips through in the first place.
NON_ITEM_TAGS = {
    # worldgen.js PLACEMENTS[0].biomes -> the `biomes` field of a neoforge:add_features biome modifier.
    "twilightforest:in_twilight_forest": "minecraft:worldgen/biome",
    # ids.js IDS.undergarden.{depthrock,shiverstone,dreadrock}Replaceables: The_Undergarden-1.21.1-0.9.6.jar
    # data/undergarden/tags/block/{depthrock,shiverstone,dreadrock}_ore_replaceables.json -- ore-gen replacement
    # tags are block tags, not item tags (confirmed against the boot's .run/server/kubejs/exported/tags.json,
    # where each is bound under minecraft:block with count 1, and absent from minecraft:item).
    "undergarden:depthrock_ore_replaceables": "minecraft:block",
    "undergarden:shiverstone_ore_replaceables": "minecraft:block",
    "undergarden:dreadrock_ore_replaceables": "minecraft:block",
    # ids.js IDS.undergarden.biomes: The_Undergarden-1.21.1-0.9.6.jar data/undergarden/tags/worldgen/biome/
    # is_undergarden.json -- a biome tag (bound under minecraft:worldgen/biome with count 20 in the export).
    "undergarden:is_undergarden": "minecraft:worldgen/biome",
    # worldgen.js's default `targets` pair (the pair used by rows without their own `targets`, D86) -- vanilla's own
    # ore-replacement tags, which are block tags: the boot's .run/server/kubejs/exported/tags.json binds
    # minecraft:stone_ore_replaceables under minecraft:block with count 4 and
    # minecraft:deepslate_ore_replaceables with count 2, and neither appears under minecraft:item.
    "minecraft:stone_ore_replaceables": "minecraft:block",
    "minecraft:deepslate_ore_replaceables": "minecraft:block",
    # v0.3, spec §7 D112a: ids.js IDS.tierOres.needsToolTags, ATM's three tool-tier tags, are block tags:
    # allthemodium-3.0.1_mc_1.21.1.jar!data/c/tags/block/needs_{allthemodium,vibranium,unobtainium}_tool.json; the boot's
    # tags.json binds them under minecraft:block with counts 4, 3 and 20. The fourth, needs_allthemodiumalloy_tool, is bound
    # with 0 blocks, so ids.js keeps it bare and the tier-ore script builds it as '#' + ..., which is never looked up.
    "c:needs_allthemodium_tool": "minecraft:block",
    "c:needs_vibranium_tool": "minecraft:block",
    "c:needs_unobtainium_tool": "minecraft:block",
    # v0.3, spec §7 D112b: ids.js IDS.tierOres.immuneTags, the blocks a boss may not break:
    # server-1.21.1-20240808.144430-extra.jar!data/minecraft/tags/block/wither_immune.json and L_Ender's Cataclysm
    # 1.21.1-3.33.jar!data/cataclysm/tags/block/{ignis,maledictus,scylla,netherite_monstrosity}_immune.json; tags.json
    # minecraft:block counts 102, 26, 26, 26 and 39.
    "minecraft:wither_immune": "minecraft:block",
    "cataclysm:ignis_immune": "minecraft:block",
    "cataclysm:maledictus_immune": "minecraft:block",
    "cataclysm:scylla_immune": "minecraft:block",
    "cataclysm:netherite_monstrosity_immune": "minecraft:block",
    # v0.3, spec §8: ids.js IDS.worldgen ore-target stone tags: allthemodium-3.0.1_mc_1.21.1.jar!data/allthemodium/tags/
    # block/ancient_stone.json and adastra-1.21.1-1.16.25-neoforge.jar!data/ad_astra/tags/block/
    # {mercury,glacio}_stone_replaceables.json; tags.json minecraft:block counts 1, 1 and 2.
    "allthemodium:ancient_stone": "minecraft:block",
    "ad_astra:mercury_stone_replaceables": "minecraft:block",
    "ad_astra:glacio_stone_replaceables": "minecraft:block",
}

# A tag literal: a quoted string whose first character is '#', followed by a well-formed resource location.
# The `namespace:path` requirement is what keeps `{ '#': 'minecraft:furnace' }` (tier2.js grid key) and the
# bare "leading '#'" in a prose comment out of the results.
TAG_LITERAL = re.compile(r"""['"]#([a-z0-9_.\-]+:[a-z0-9_.\-/]+)['"]""")


@dataclass
class Result:
    checked: dict = field(default_factory=dict)   # tag -> element count (passing tags)
    absent: list = field(default_factory=list)    # (tag, registry, sources) -- no such tag is bound
    empty: list = field(default_factory=list)     # (tag, registry, sources) -- bound but 0 elements
    empty_twin: list = field(default_factory=list)   # (tag, other registries, sources) -- non-empty where checked, 0 elsewhere
    no_registry: list = field(default_factory=list)

    @property
    def failures(self):
        return self.absent + self.empty + self.empty_twin + self.no_registry


# After one of these, a '/' starts a regex literal; after anything else (a name, number, ')', ']' or a string) it divides.
# The same rule as tools/tests/jslex.py's tokenizer.
REGEX_AFTER_CHARS = set("(,=:[!&|?{};+-*%<>~^")
REGEX_AFTER_WORDS = {"return", "typeof", "case", "do", "else", "in", "of", "new", "delete", "void", "throw", "instanceof",
                     "yield", "await"}


def _regex_may_start(out: list) -> bool:
    """Whether a '/' may start a regex literal here, judged by the last code character kept so far. The rule is
    tools/tests/jslex.py's REGEX_AFTER (test_check_tags.py keeps the two in step), including its reading of '++' and '--':
    JS takes a run of '+' (or '-') two at a time from the left, so an even run ends in '++' (after `i++`, '/' divides)
    and an odd run in a single '+' (after `a+++`, '/' starts a regex)."""
    j = len(out) - 1
    while j >= 0 and out[j].isspace():
        j -= 1
    if j >= 0 and out[j] in "+-":
        k = j
        while k >= 0 and out[k] == out[j]:
            k -= 1
        return (j - k) % 2 == 1
    if j < 0 or out[j] in REGEX_AFTER_CHARS:
        return True
    if out[j].isalnum() or out[j] in "_$":
        k = j
        while k >= 0 and (out[k].isalnum() or out[k] in "_$"):
            k -= 1
        return "".join(out[k + 1:j + 1]) in REGEX_AFTER_WORDS
    return False


def strip_js_comments(text: str) -> str:
    r"""Drop // and /* */ comments, leaving string and regex literals intact (template literals: see the last limit).

    Comments are stripped so that a tag named in prose (e.g. ids.js explaining which tag is *wrong*) is not
    mistaken for a reference. A block comment becomes one space, as JS reads it, so `a+/**/+/x/` keeps its two separate
    '+' (and the regex after them). Regex literals are copied verbatim, so a regex holding '//', '/*' or a quote (such as
    /https?:\/\//, /[/*]/ or /'/) neither starts a comment nor opens a string. A '/' starts a regex only where JS allows
    one (after an operator, an opening bracket, a comma or semicolon, or a keyword such as return); elsewhere it divides.
    The pack has one regex literal today, bypass.js's /^deeperdarker:.*gloomslate_.*_ore$/, which holds none of the three.
    Limit (the same as tools/tests/jslex.py's): '}' counts as a place a regex may start (a block's end), so a '/' after an
    object literal or a function expression, `x = {} / 2` or `function () {} / 2`, is misread as a regex. The pack writes
    neither; test_check_tags.py pins the limit.
    Limit (unlike jslex): a template literal is read as a plain quote, from one backtick to the next. So a comment inside a
    ${ ... } is kept (a tag named in it counts as a reference), and a backtick inside a substitution (a nested template)
    ends the outer template early. HEAD (61f1a11) read templates the same way; the pack's templates hold neither, and
    test_check_tags.py pins both.
    """
    out = []
    i, n = 0, len(text)
    quote = None
    while i < n:
        c = text[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "'\"`":
            quote = c
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            out.append(" ")
            continue
        if c == "/" and _regex_may_start(out):
            # Copy the regex literal up to its closing '/' (not one escaped or inside a [...] class), or to the line end.
            j, in_class = i + 1, False
            while j < n and text[j] != "\n":
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == "[":
                    in_class = True
                elif text[j] == "]":
                    in_class = False
                elif text[j] == "/" and not in_class:
                    break
                j += 1
            j = min(j + 1, n) if j < n and text[j] == "/" else min(j, n)
            out.extend(text[i:j])
            i = j
            continue
        out.append(c)
        i += 1
    return "".join(out)


def tags_from_script(text: str) -> set:
    return set(TAG_LITERAL.findall(strip_js_comments(text)))


def tags_from_json(node) -> set:
    """Every value of a "tag" key, at any depth."""
    found = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "tag" and isinstance(value, str):
                found.add(value.lstrip("#"))
            else:
                found |= tags_from_json(value)
    elif isinstance(node, list):
        for value in node:
            found |= tags_from_json(value)
    return found


def collect_references(root: Path) -> dict:
    """tag id -> sorted list of the files that reference it."""
    refs = {}

    def note(tag, path):
        refs.setdefault(tag, set()).add(str(path.relative_to(root)))

    for rel in SCRIPT_DIRS:
        for path in sorted((root / rel).rglob("*.js")):
            for tag in tags_from_script(path.read_text()):
                note(tag, path)
    for path in sorted((root / DATA_DIR).rglob("*.json")):
        for tag in tags_from_json(json.loads(path.read_text())):
            note(tag, path)
    return {tag: sorted(sources) for tag, sources in refs.items()}


def run_checks(refs: dict, export: dict) -> Result:
    res = Result()
    for tag in sorted(refs):
        registry = NON_ITEM_TAGS.get(tag, ITEM_REGISTRY)
        row = (tag, registry, refs[tag])
        if registry not in export:
            res.no_registry.append(row)
        elif tag not in export[registry]:
            res.absent.append(row)
        elif export[registry][tag] == 0:
            res.empty.append(row)
        else:
            # The empty twin: a block tag missing from NON_ITEM_TAGS passes as a non-empty item tag of the same id, while
            # the tag the script means is bound with 0 entries in its own registry. Only a tag whose registry is the
            # default is checked: an explicit NON_ITEM_TAGS entry is the cited way to accept a tag's registry.
            twins = [] if tag in NON_ITEM_TAGS else sorted(
                other for other, tags in export.items() if other != registry and tags.get(tag) == 0)
            if twins:
                res.empty_twin.append((tag, ", ".join(twins), refs[tag]))
            else:
                res.checked[tag] = export[registry][tag]
    return res


# D112(a). The four needs tags are disjoint (allthemodium-3.0.1_mc_1.21.1.jar!data/c/tags/block/needs_*.json), so a deny tag
# that nests all four holds their sum. A deny tag missing from the export fails too: vanilla builds no tag with a missing
# reference (server-1.21.1-20240808.144430-srg.jar net.minecraft.tags.TagLoader.build logs "Couldn't load tag {} as it is
# missing following references" and does not put it). The nine are created in code (Tool$Rule.forTag ->
# DefaultedRegistry.getOrCreateTag), so they stay in the export at 0 even when unbuilt: if ATM stopped shipping the empty
# needs_allthemodiumalloy_tool, the nine would read 0 and that needs tag would be absent. Both fail this check.
DENY_REGISTRY = "minecraft:block"
QUOTED = re.compile(r"'([^'\\]*)'|\"([^\"\\]*)\"")


def ids_value(src: str, key: str):
    """The literal value of `key:` in comment-stripped JS source: a list of strings for an array of string literals, or a
    string. Raises ValueError unless the key appears exactly once with a literal value, so a renamed or computed key fails
    the check instead of checking nothing."""
    found = re.findall(r"\b" + re.escape(key) + r"\s*:\s*(\[[^\]]*\]|'[^']*'|\"[^\"]*\")", src)
    if len(found) != 1:
        raise ValueError(f"expected one literal `{key}:` in lib/ids.js, found {len(found)}")
    value = found[0]
    if not value.startswith("["):
        return value[1:-1]
    items = [a or b for a, b in QUOTED.findall(value)]
    if QUOTED.sub("", value[1:-1]).replace(",", "").strip() or not items:
        raise ValueError(f"`{key}:` in lib/ids.js is not a non-empty array of string literals")
    return items


def read_tier_ore_tags(ids_js_text: str):
    """(the nine deny tags, the four ATM needs tags) from lib/ids.js's IDS.tierOres, without the leading '#'."""
    src = strip_js_comments(ids_js_text)
    nine = ids_value(src, "incorrectForTags")
    needs = [t.lstrip("#") for t in ids_value(src, "needsToolTags")] + [ids_value(src, "alloyToolTagEmpty")]
    return nine, needs


def check_deny_tags(export: dict, nine: list, needs: list):
    """(expected count or None, bad lines) for D112(a): each of `nine` must be bound in minecraft:block with exactly the sum
    of the `needs` counts, and that sum must be above 0."""
    block = export.get(DENY_REGISTRY)
    if block is None:
        return None, [f"NO SUCH REGISTRY {DENY_REGISTRY} in the export"]
    bad = [f"ABSENT #{t} (an ATM needs tag) not bound in {DENY_REGISTRY}" for t in needs if t not in block]
    expected = None if bad else sum(block[t] for t in needs)
    if expected == 0:
        bad.append("the ATM needs tags hold 0 blocks between them, so the deny tags would deny nothing")
    for t in nine:
        if t not in block:
            bad.append(f"ABSENT #{t} (a D112a deny tag) not bound in {DENY_REGISTRY}")
        elif expected is not None and block[t] != expected:
            bad.append(f"DENY TAG #{t} holds {block[t]} blocks, expected {expected}")
    return expected, bad


# D112 members (v0.3 Task 8c). The ores every deny tag must hold, by their IDS.allthemodium key (see the module docstring).
DENY_ORE_REFS = ("IDS.allthemodium.vibraniumOre", "IDS.allthemodium.otherVibraniumOre", "IDS.allthemodium.unobtainiumOre")
IDS_REF = re.compile(r"IDS\.([A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)")


def ids_ref(src: str, ref: str) -> str:
    """The string literal `ref` (IDS.<group>.<key>) names in comment-stripped lib/ids.js source: either the one assignment
    `IDS.<group>.<key> = '...'`, or the one `<key>: '...'` inside the one flat `<group>: { ... }` object literal. Raises
    ValueError otherwise (absent, repeated, or not a literal), so a renamed id fails the check instead of checking nothing."""
    m = IDS_REF.fullmatch(ref)
    if not m:
        raise ValueError(f"{ref!r} is not an IDS.<group>.<key> reference")
    group, key = m.groups()
    assigned = re.findall(r"\bIDS\." + re.escape(group) + r"\." + re.escape(key) + r"\s*=\s*('[^']*'|\"[^\"]*\")", src)
    literal = re.findall(r"(?<![\w$.])" + re.escape(group) + r"\s*:\s*\{([^{}]*)\}", src)
    in_literal = re.findall(r"(?<![\w$])" + re.escape(key) + r"\s*:\s*('[^']*'|\"[^\"]*\")", literal[0]) if len(literal) == 1 else []
    found = assigned + in_literal
    if len(found) != 1:
        raise ValueError(f"expected one literal value for {ref} in lib/ids.js, found {len(found)}")
    return found[0][1:-1]


def read_tier_ore_members(ids_js_text: str):
    """(the five immune tags, the five tier ores, the deny ores) from lib/ids.js: IDS.tierOres.immuneTags without '#',
    IDS.tierOres.blocks resolved through ids_ref, and DENY_ORE_REFS resolved the same way."""
    src = strip_js_comments(ids_js_text)
    immune = [t.lstrip("#") for t in ids_value(src, "immuneTags")]
    blocks = re.findall(r"\bblocks\s*:\s*\[([^\]]*)\]", src)
    if len(blocks) != 1:
        raise ValueError(f"expected one `blocks:` array in lib/ids.js, found {len(blocks)}")
    refs = [r.strip() for r in blocks[0].split(",") if r.strip()]
    ores = [ids_ref(src, r) for r in refs]
    deny_ores = [ids_ref(src, r) for r in DENY_ORE_REFS]
    if not set(deny_ores) <= set(ores):
        raise ValueError(f"the deny ores {deny_ores} are not all among IDS.tierOres.blocks {ores}")
    return immune, ores, deny_ores


def member_shape(members: dict, registry: str, name: str):
    """(that registry's {tag: [id, ...]}, []) or (None, [the bad line]) for a members export of another shape."""
    tags = members.get(registry) if isinstance(members, dict) else None
    if tags is None:
        return None, [f"NO SUCH REGISTRY {registry} in {name}"]
    if not isinstance(tags, dict):
        return None, [f"BAD MEMBERS {registry} in {name}: not a {{tag: [id, ...]}} map"]
    bad = [f"BAD MEMBERS #{t} in {name}: not a list of strings" for t, ms in tags.items()
           if not (isinstance(ms, list) and all(isinstance(m, str) for m in ms))]
    return (None if bad else tags), bad


FRESHNESS_LINES = 10


def check_freshness(members: dict, export: dict, registry: str, name: str, complete: bool = False) -> list:
    """Bad lines unless `name` (a members export) is from the same walk as tags.json (module docstring): well formed, each
    tag's member count equal to tags.json's, and, when `complete`, every tag tags.json binds in `registry` present. At most
    FRESHNESS_LINES STALE lines, then one line for the rest."""
    tags, bad = member_shape(members, registry, name)
    if tags is None:
        return bad
    counts = export.get(registry, {})
    stale = []
    for t, ms in tags.items():
        if t not in counts:
            stale.append(f"STALE #{t} in {name}: not bound in tags.json")
        elif len(ms) != counts[t]:
            stale.append(f"STALE #{t} in {name}: {len(ms)} members, tags.json counts {counts[t]}")
    if len(stale) > FRESHNESS_LINES:
        stale = stale[:FRESHNESS_LINES] + [f"STALE ... and {len(stale) - FRESHNESS_LINES} more tags in {name}"]
    missing = sorted(set(counts) - set(tags)) if complete else []
    if missing:
        shown = ", ".join("#" + t for t in missing[:FRESHNESS_LINES]) + (", ..." if len(missing) > FRESHNESS_LINES else "")
        stale.append(f"NOT EXPORTED {len(missing)} of {len(counts)} {registry} tags bound in tags.json are missing from "
                     f"{name}: {shown}")
    return stale


def check_members(members: dict, nine: list, needs: list, immune: list, ores: list, deny_ores: list) -> list:
    """Bad lines for D112 by member (module docstring), from tag_members.json's {registry: {tag: [block id, ...]}}."""
    block, shape_bad = member_shape(members, DENY_REGISTRY, "tag_members.json")
    if block is None:
        return shape_bad
    bad = [f"NO MEMBERS #{t} in tag_members.json" for t in nine + needs + immune if t not in block]
    for t in immune:
        bad += [f"NOT IMMUNE {o} is missing from #{t}" for o in ores if t in block and o not in block[t]]
    if all(t in block for t in needs):
        union = set().union(*(block[t] for t in needs))
        for t in nine:
            outside = sorted(set(block.get(t, [])) - union)
            if outside:
                bad.append(f"DENY TAG #{t} holds blocks outside the {len(needs)} needs tags: {outside}")
    for t in nine:
        bad += [f"NOT DENIED {o} is missing from #{t}" for o in deny_ores if t in block and o not in block[t]]
    return bad


def main() -> int:
    if not EXPORT.exists():
        print(f"MISSING EXPORT {EXPORT}")
        print("  kubejs/server_scripts/tagcheck.js writes it at ServerEvents.loaded; run tools/server_boot.sh first.")
        return 1
    export = json.loads(EXPORT.read_text())
    refs = collect_references(ROOT)
    res = run_checks(refs, export)
    try:
        nine, needs = read_tier_ore_tags(IDS_JS.read_text())
        expected, deny_bad = check_deny_tags(export, nine, needs)
    except (OSError, ValueError) as e:
        nine, needs, expected, deny_bad = [], [], None, [f"CANNOT READ IDS.tierOres from {IDS_JS.relative_to(ROOT)}: {e}"]
    try:
        immune, ores, deny_ores = read_tier_ore_members(IDS_JS.read_text())
        if not MEMBERS.exists():
            members_bad = [f"MISSING EXPORT {MEMBERS} (tagcheck.js writes it at ServerEvents.loaded)"]
        else:
            block_members = json.loads(MEMBERS.read_text())
            members_bad = check_members(block_members, nine, needs, immune, ores, deny_ores)
            if not any(line.startswith(("NO SUCH REGISTRY", "BAD MEMBERS")) for line in members_bad):
                members_bad += check_freshness(block_members, export, DENY_REGISTRY, MEMBERS.name)
    except (OSError, ValueError) as e:
        immune, ores, deny_ores, members_bad = [], [], [], [f"CANNOT CHECK tag members: {e}"]
    item_tags = 0
    try:
        if not ITEM_MEMBERS.exists():
            item_bad = [f"MISSING EXPORT {ITEM_MEMBERS} (tagcheck.js writes it at ServerEvents.loaded)"]
        else:
            item_members = json.loads(ITEM_MEMBERS.read_text())
            item_bad = check_freshness(item_members, export, ITEM_REGISTRY, ITEM_MEMBERS.name, complete=True)
            item_tags = len(item_members.get(ITEM_REGISTRY) or {}) if isinstance(item_members, dict) else 0
    except (OSError, ValueError) as e:
        item_bad = [f"CANNOT CHECK item tag members: {e}"]
    bad_total = len(res.failures) + len(deny_bad) + len(members_bad) + len(item_bad)

    print(f"tags: {len(refs)} referenced, {len(res.checked)} verified non-empty, {bad_total} bad")
    for tag, count in sorted(res.checked.items()):
        print(f"  ok {tag} ({count})")
    for tag, registry, sources in res.no_registry:
        print(f"  NO SUCH REGISTRY {registry} for {tag} <- {', '.join(sources)}")
    for tag, registry, sources in res.absent:
        print(f"  ABSENT #{tag} not bound in {registry} <- {', '.join(sources)}")
    for tag, registry, sources in res.empty:
        print(f"  EMPTY #{tag} bound in {registry} with 0 elements <- {', '.join(sources)}")
    for tag, registries, sources in res.empty_twin:
        checked_in = NON_ITEM_TAGS.get(tag, ITEM_REGISTRY)
        print(f"  EMPTY TWIN #{tag} bound in {registries} with 0 elements, though {checked_in} has "
              f"{export[checked_in][tag]}; map its registry in NON_ITEM_TAGS <- {', '.join(sources)}")
    sums = " + ".join(f"#{t} ({export.get(DENY_REGISTRY, {}).get(t, 'absent')})" for t in needs)
    total = "an unknown count" if expected is None else expected
    print(f"deny tags (D112a): {len(nine)} checked in {DENY_REGISTRY}, each must hold {total} = {sums or '?'}; "
          f"{len(deny_bad)} bad")
    for line in deny_bad:
        print(f"  {line}")
    print(f"tag members (D112): {len(nine) + len(needs) + len(immune)} tags; {len(ores)} tier ores in {len(immune)} immune tags, "
          f"{len(deny_ores)} ores in {len(nine)} deny tags, {len(nine)} deny tags within the {len(needs)} needs tags; "
          f"{len(members_bad)} bad")
    for line in members_bad:
        print(f"  {line}")
    print(f"item tag members: {item_tags} tags exported, {len(export.get(ITEM_REGISTRY, {}))} bound in tags.json; "
          f"{len(item_bad)} bad")
    for line in item_bad:
        print(f"  {line}")
    return 1 if res.failures or deny_bad or members_bad or item_bad else 0


if __name__ == "__main__":
    sys.exit(main())
