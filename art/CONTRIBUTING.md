# Contributing textures

Thanks for drawing for Confluence. Short version: edit the PNGs, push a branch, open a PR; the maintainer runs
the check and merges.

## Setup

1. You are a collaborator on `ShawnPad/confluence-modpack`. `git clone https://github.com/ShawnPad/confluence-modpack.git`
   (or GitHub Desktop). Work on a branch (`git switch -c art/<what-you-changed>`), push it, and open a PR
   against `main`.
2. Load `art/palette.gpl` (GIMP palette format) into your editor.
3. Read `art/STYLE.md` (the rules, one page) and `art/TEXTURES.md` (what each texture is, with 8× renders). A
   "tier" there is one rung of the pack's ladder of gated dimensions.

## Where the files are

| What | Path |
|---|---|
| Item textures (8) | `kubejs/assets/kubejs/textures/item/<id>.png` |
| Ore textures (2) | `kubejs/assets/kubejs/textures/block/<id>.png` |
| Palette | `art/palette.gpl` |

Edit the PNG in place and save it as 16×16 8-bit RGBA: convert the sprite to RGB colour mode before exporting,
and if the export dialog offers "interlaced" / "Adam7", leave it off. The file in the repo is the source of
truth: no tool overwrites it on its own.

Leave `art/TEXTURES.md` and `art/preview/` alone; they are generated from the PNGs and the maintainer
regenerates them after merging.

## Before the PR

Run the check if you have Python 3 (optional; the maintainer runs it too):

    python3 tools/check_textures.py

It checks the mechanical rules (size, RGBA, no half-transparent pixels, items keep the outer 1-px border
empty, ores fully opaque) and says which file and rule failed.

The maintainer checks the rest of `STYLE.md` by eye on the 8× sheet: the 1-px outline ring on items, the
minimum silhouette size (12 px on one axis, 8 on the other), the shared family silhouette (both keys, both foci,
both shards, both ores), colours from the palette, light from the top-left. Those are what a PR gets bounced
for. Taste is a conversation, not a rule.

## The PR

- Touch only `kubejs/assets/**` and `art/**`. Never edit `index.toml` or `pack.toml`: they are the manifest
  that packwiz (the pack's updater) uses to hand files to players, and the maintainer regenerates them after
  merging.
- One PR per family or per idea is easiest to review. Put an 8× image in the PR description
  (`python3 tools/gen_textures.py --preview /tmp/x8` writes one per texture, or zoom in and screenshot).
- Changing the palette is fine; do it in the same PR as the textures that need it and say why.
- Once merged and refreshed, players get the new textures on their next launch. No release is needed.

## The grids in `art/grids/`

Those text files are the maintainer's drafting format (one character per pixel). You do not need them. If you
redraw a texture, the grid is simply out of date; the PNG wins.

## For the maintainer

After merging a PR that changes a PNG or `art/briefs.json`:

    python3 tools/gen_textures.py --preview art/preview/x8
    python3 tools/gen_preview.py --round <n>
    packwiz refresh

then commit `art/`, `index.toml` and `pack.toml`, and push `main`. The tests fail until the first two have run.
