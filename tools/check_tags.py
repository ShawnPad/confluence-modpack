"""Prove that every tag the pack references is bound and non-empty.

An ingredient that points at a tag no mod defines loads with zero KubeJS errors, shows up in the recipe
dump, passes tools/check_recipes.py -- and is uncraftable in game (the `#c:gems/zanite` defect, D69).
This checker closes that hole: kubejs/server_scripts/tagcheck.js exports every bound tag with its element
count at ServerEvents.loaded, and this script asserts that every tag the pack *references* is in there
with a count > 0.

References are collected from three places:
  1. every `'#namespace:path'` / `"#namespace:path"` literal in kubejs/{server,startup,client}_scripts/**/*.js
     (this covers the whole IDS object in lib/ids.js, including nested objects), comments stripped;
  2. every `"tag": "<id>"` value, at any depth, in kubejs/data/**/*.json (recipe ingredients drop the '#');
  3. nothing else -- a tag the pack neither names in a script nor in a datapack file is not its problem.

Run after tools/server_boot.sh:  python3 tools/check_tags.py
"""
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / ".run" / "server" / "kubejs" / "exported" / "tags.json"

SCRIPT_DIRS = ("kubejs/server_scripts", "kubejs/startup_scripts", "kubejs/client_scripts")
DATA_DIR = "kubejs/data"

ITEM_REGISTRY = "minecraft:item"

# Referenced tags that live in a registry other than minecraft:item. Every entry needs the source line that
# proves it, because guessing the registry is how an empty tag slips through in the first place.
NON_ITEM_TAGS = {
    # worldgen.js PLACEMENTS[0].biomes -> the `biomes` field of a neoforge:add_features biome modifier.
    "twilightforest:in_twilight_forest": "minecraft:worldgen/biome",
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
    no_registry: list = field(default_factory=list)

    @property
    def failures(self):
        return self.absent + self.empty + self.no_registry


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
            res.checked[tag] = export[registry][tag]
    return res


def main() -> int:
    if not EXPORT.exists():
        print(f"MISSING EXPORT {EXPORT}")
        print("  kubejs/server_scripts/tagcheck.js writes it at ServerEvents.loaded; run tools/server_boot.sh first.")
        return 1
    export = json.loads(EXPORT.read_text())
    refs = collect_references(ROOT)
    res = run_checks(refs, export)

    print(f"tags: {len(refs)} referenced, {len(res.checked)} verified non-empty, {len(res.failures)} bad")
    for tag, count in sorted(res.checked.items()):
        print(f"  ok {tag} ({count})")
    for tag, registry, sources in res.no_registry:
        print(f"  NO SUCH REGISTRY {registry} for {tag} <- {', '.join(sources)}")
    for tag, registry, sources in res.absent:
        print(f"  ABSENT #{tag} not bound in {registry} <- {', '.join(sources)}")
    for tag, registry, sources in res.empty:
        print(f"  EMPTY #{tag} bound in {registry} with 0 elements <- {', '.join(sources)}")
    return 1 if res.failures else 0


if __name__ == "__main__":
    sys.exit(main())
