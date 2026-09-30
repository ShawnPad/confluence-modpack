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

Run after tools/server_boot.sh:  python3 tools/check_tags.py
"""
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / ".run" / "server" / "kubejs" / "exported" / "tags.json"
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


def strip_js_comments(text: str) -> str:
    """Drop // and /* */ comments, leaving string literals intact.

    Comments are stripped so that a tag named in prose (e.g. ids.js explaining which tag is *wrong*) is not
    mistaken for a reference. Regex literals are not tracked; no script in the pack uses one.
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

    print(f"tags: {len(refs)} referenced, {len(res.checked)} verified non-empty, {len(res.failures) + len(deny_bad)} bad")
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
    return 1 if res.failures or deny_bad else 0


if __name__ == "__main__":
    sys.exit(main())
