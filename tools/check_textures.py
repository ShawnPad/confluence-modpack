"""Prove that every item and block the pack registers has a texture that follows art/STYLE.md.

The headless server never loads client resources (the D73 blind spot), so this is the only automated check
textures get. For every id in kubejs/startup_scripts/items.js (read by tools/packitems.py):
  R1  the PNG exists at kubejs/assets/kubejs/textures/<item|block>/<id>.png
  R2  it is 16x16, 8-bit, colour type 6 (RGBA), not interlaced
  R3  every pixel is fully opaque or fully transparent (no anti-aliasing; STYLE.md rule 1)
  R4  items: the outer 1-px border is transparent, so the outline is never clipped by the slot (rule 2)
  R5  blocks: every pixel is opaque, because the texture tiles (rule 3)
No palette-conformance check: STYLE.md rule 5 lets the artist tune the palette in the same PR.

Run: python3 tools/check_textures.py      exit 1 with one FAIL line per problem
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import packitems
import pngio

SIZE = 16


def check_png(data: bytes, kind: str) -> list[str]:
    """Failure messages for one texture (empty list = pass). kind is 'item' or 'block'."""
    try:
        w, h, _depth, _ctype, _interlace = pngio.header(data)
    except pngio.PngError as e:
        return [f"R2 {e}"]
    if (w, h) != (SIZE, SIZE):
        return [f"R2 is {w}x{h}, must be {SIZE}x{SIZE}"]
    try:
        _, _, rows = pngio.decode(data)
    except pngio.PngError as e:
        return [f"R2 {e}"]
    failures = []
    partial = sum(1 for row in rows for px in row if 0 < px[3] < 255)
    if partial:
        failures.append(f"R3 {partial} pixel(s) with partial alpha; use only fully opaque or fully transparent pixels")
    if kind == "item":
        border = rows[0] + rows[SIZE - 1] + \
                 [px for row in rows[1:SIZE - 1] for px in (row[0], row[SIZE - 1])]
        opaque = sum(1 for px in border if px[3])
        if opaque:
            failures.append(f"R4 {opaque} non-transparent pixel(s) on the outer 1-px border; keep the outline inside it")
    elif kind == "block":
        holes = sum(1 for row in rows for px in row if px[3] != 255)
        if holes:
            failures.append(f"R5 {holes} non-opaque pixel(s); a block texture must be fully opaque")
    else:
        raise ValueError(f"unknown texture kind {kind!r}")
    return failures


def run(kinds: dict[str, list[str]], root: Path = packitems.ROOT) -> list[tuple[Path, str]]:
    """[(path relative to root, message)] over every registered id."""
    out = []
    for kind, ids in kinds.items():
        for item_id in ids:
            path = packitems.texture_path(kind, item_id, root)
            rel = path.relative_to(root)
            if not path.exists():
                out.append((rel, "R1 missing"))
                continue
            out.extend((rel, msg) for msg in check_png(path.read_bytes(), kind))
    return out


def main() -> int:
    kinds = packitems.load()
    failures = run(kinds)
    for rel, msg in failures:
        print(f"FAIL {rel}: {msg}")
    print(f"check_textures: {sum(len(v) for v in kinds.values())} textures checked, {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
