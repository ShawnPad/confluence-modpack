"""Ids of the items and blocks the pack registers, read from kubejs/startup_scripts/items.js.

Every tool that needs "the pack's own items" (gen_textures.py, check_textures.py, gen_preview.py) reads them
here, so a new event.create() line is picked up everywhere without a second hand-kept list. Asset paths are
the ones verified in research/phase6-kubejs-2101-syntax.md §1.1 and §1.2 (default `kubejs` namespace).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_tags import strip_js_comments

ROOT = Path(__file__).resolve().parents[1]
ITEMS_JS = ROOT / "kubejs" / "startup_scripts" / "items.js"

REGISTRY = re.compile(r"StartupEvents\.registry\(\s*['\"]([a-z_]+)['\"]")
CREATE = re.compile(r"event\.create\(\s*['\"]([a-z0-9_]+)['\"]")
ANY_CREATE = re.compile(r"event\.create\(")


def registered_ids(source: str) -> dict[str, list[str]]:
    """{'item': [...], 'block': [...]} in file order; a create() before any registry() call is ignored."""
    source = strip_js_comments(source)
    out = {"item": [], "block": []}
    marks = [(m.start(), m.group(1)) for m in REGISTRY.finditer(source)]
    for i, (start, kind) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(source)
        seg = source[start:end]
        ids = CREATE.findall(seg)
        if len(ANY_CREATE.findall(seg)) != len(ids):
            raise ValueError(f"{kind} registry: an event.create() id is not a plain quoted "
                             "[a-z0-9_]+ literal (namespaced, template-literal or variable ids are not supported)")
        if kind in out:
            out[kind].extend(ids)
    return out


def load(path: Path = ITEMS_JS) -> dict[str, list[str]]:
    return registered_ids(path.read_text())


def texture_path(kind: str, item_id: str, root: Path = ROOT) -> Path:
    return root / "kubejs" / "assets" / "kubejs" / "textures" / kind / f"{item_id}.png"
