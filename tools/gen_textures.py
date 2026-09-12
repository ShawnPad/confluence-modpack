"""Render art/grids/<id>.txt through art/palette.gpl into the pack's texture folders.

A grid file is the maintainer's drafting source (art/STYLE.md, art/CONTRIBUTING.md). Legend lines `X name`
map one character to a palette colour name (or `transparent`); the sixteen 16-character rows are the pixels;
`#` starts a comment. The PNG in kubejs/assets is canonical once it exists: this script never overwrites one
unless told to with --force <id>, so an artist's edit is safe from a re-run.

  python3 tools/gen_textures.py                        render every grid whose PNG is missing
  python3 tools/gen_textures.py --force coin other_key re-render those ids from their grids
  python3 tools/gen_textures.py --preview art/preview/x8
                                                       also write 8x upscales of every CURRENT PNG (the
                                                       canonical file, human-edited or not) into that folder
                                                       (a relative path is taken from the pack root, not the
                                                       current directory)
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import packitems
import pngio

SIZE = 16


def parse_palette(text: str) -> dict[str, tuple[int, int, int]]:
    """GIMP .gpl -> {name: (r, g, b)}. Skips the `GIMP Palette` line, `Key: value` lines and `#` comments."""
    colours = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line == "GIMP Palette" or line.split()[0].endswith(":"):
            continue
        parts = line.split(None, 3)
        if len(parts) < 4:
            raise ValueError(f"palette line without a name: {line!r}")
        try:
            rgb = tuple(int(p) for p in parts[:3])
        except ValueError:
            raise ValueError(f"palette line is not R G B name: {line!r}") from None
        if not all(0 <= v <= 255 for v in rgb):
            raise ValueError(f"palette component out of range: {line!r}")
        colours[parts[3].strip()] = rgb
    return colours


def parse_grid(text: str, palette: dict) -> list[list[tuple]]:
    """-> 16 rows of 16 (r, g, b, a). Legend lines have two tokens; pixel rows are 16 legend characters.

    `#` starts a comment anywhere, so it cannot be a legend key or appear in a name.
    """
    legend, rows = {}, []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if len(line.split()) > 1:
            key, name = line.split(None, 1)
            if len(key) != 1:
                raise ValueError(f"legend key must be one character: {line!r}")
            if name == "transparent":
                legend[key] = (0, 0, 0, 0)
            elif name in palette:
                legend[key] = palette[name] + (255,)
            else:
                raise ValueError(f"unknown palette colour {name!r}")
        else:
            rows.append(line)
    if len(rows) != SIZE or any(len(r) != SIZE for r in rows):
        raise ValueError(f"grid must be {SIZE} rows of {SIZE} characters, got {len(rows)} rows with lengths "
                         f"{[len(r) for r in rows]}")
    out = []
    for y, row in enumerate(rows):
        try:
            out.append([legend[ch] for ch in row])
        except KeyError as e:
            raise ValueError(f"row {y}: pixel character {e.args[0]!r} is not in the legend") from None
    return out


def upscale(rows: list, factor: int) -> list:
    """Nearest-neighbour upscale: every pixel becomes a factor×factor block."""
    return [[px for px in row for _ in range(factor)] for row in rows for _ in range(factor)]


def run(root: Path, kinds: dict[str, list[str]], force=(), preview: Path | None = None) -> tuple[list, list, list]:
    """Render every grid under root/art/grids; optionally write 8x previews of every registered PNG.

    Returns (written, kept, previewed) paths. A target that exists is kept unless its id is in `force`; its grid
    is then not even parsed, so a stale draft never blocks a run. Previews come from the canonical PNG, whatever
    drew it, and may not be written into the assets tree.
    """
    assets = (root / "kubejs" / "assets").resolve()
    if preview is not None and (preview.resolve() == assets or assets in preview.resolve().parents):
        raise ValueError(f"--preview {preview}: must not point inside kubejs/assets (those PNGs are canonical)")
    palette = parse_palette((root / "art" / "palette.gpl").read_text())
    grids = sorted((root / "art" / "grids").glob("*.txt"))
    unknown = set(force) - {g.stem for g in grids}
    if unknown:
        raise ValueError(f"--force: no grid for {sorted(unknown)}")
    written, kept, previewed = [], [], []
    for grid in grids:
        item_id = grid.stem
        kind = next((k for k, ids in kinds.items() if item_id in ids), None)
        if kind is None:
            raise ValueError(f"{grid.name}: no item or block with id {item_id!r} in items.js")
        target = packitems.texture_path(kind, item_id, root)
        if target.exists() and item_id not in force:
            kept.append(target)
            continue
        try:
            rows = parse_grid(grid.read_text(), palette)
        except ValueError as e:
            raise ValueError(f"{grid.name}: {e}") from None
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".png.tmp")
        try:
            tmp.write_bytes(pngio.encode(rows))
            os.replace(tmp, target)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        written.append(target)
    if preview is not None:
        preview.mkdir(parents=True, exist_ok=True)
        for kind, ids in kinds.items():
            for item_id in ids:
                target = packitems.texture_path(kind, item_id, root)
                if not target.exists():
                    continue
                try:
                    _, _, current = pngio.decode(target.read_bytes())
                except pngio.PngError as e:
                    raise ValueError(f"{target.relative_to(root)}: {e}") from None
                out = preview / f"{item_id}.png"
                out.write_bytes(pngio.encode(upscale(current, 8)))
                previewed.append(out)
    return written, kept, previewed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", nargs="+", default=[], metavar="ID", help="re-render these ids even if their PNG exists")
    ap.add_argument("--preview", metavar="DIR", type=Path, help="write 8x upscales of every current PNG into DIR")
    args = ap.parse_args(argv)
    if args.preview is not None and not args.preview.is_absolute():
        args.preview = packitems.ROOT / args.preview
    written, kept, previewed = run(packitems.ROOT, packitems.load(), force=args.force, preview=args.preview)
    for p in written:
        print("wrote", p.relative_to(packitems.ROOT))
    print(f"{len(written)} written, {len(kept)} kept (an existing PNG is canonical; --force <id> to redraw)"
          + (f", {len(previewed)} previews in {args.preview}" if args.preview else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
