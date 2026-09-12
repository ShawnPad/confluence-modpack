"""Render art/briefs.json as the artist's page (art/TEXTURES.md) and the round's preview page (HTML).

  python3 tools/gen_preview.py --round 1                    writes art/TEXTURES.md and art/preview/round-1.html
  python3 tools/gen_preview.py --round 2 --no-md            only the HTML
  python3 tools/gen_preview.py --round 1 --date 2026-09-12  pin the date shown on the page

TEXTURES.md is generated: edit art/briefs.json, not the markdown. The HTML embeds every current PNG as a data
URI, so the page stands on its own after the repo moves on; the maintainer publishes it as an Artifact. Round 2
and later: publish with the Artifact tool's `url` set to round 1's page so the link the artist has stays the same.
The 8x PNGs TEXTURES.md shows come from `python3 tools/gen_textures.py --preview art/preview/x8`;
tools/tests/test_gen_preview.py fails when they or TEXTURES.md are stale.
"""
import argparse
import base64
import datetime as dt
import html as htmlmod
import itertools
import json
import sys
from pathlib import Path
from string import Template

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_textures
import packitems

PREAMBLE = ("The pack ships tiers 0-2 today: the coin and the Twilight Key are in the game. Everything tagged "
            "(v0.2), (v0.3) or (v1.0) is designed but not built yet; the tag is the release it lands in. A \"tier\" "
            "is one rung of the pack's ladder of gated dimensions. The current PNGs are a baseline, not a "
            "constraint: redraw anything, keeping only the canvas rules (STYLE.md rules 1-3) and each family's "
            "shared silhouette (rule 6).")


def load_briefs(root: Path) -> dict:
    return json.loads((root / "art" / "briefs.json").read_text())


def ordered(kinds: dict, briefs: dict):
    """[(kind, id, brief)] grouped by family in the order briefs.json lists the families; items.js order inside."""
    order = list(briefs["families"])
    rows = []
    for kind, ids in kinds.items():
        for item_id in ids:
            if item_id not in briefs["textures"]:
                raise KeyError(f"no brief for {item_id!r} in art/briefs.json")
            brief = briefs["textures"][item_id]
            if brief["family"] not in order:
                raise KeyError(f"{item_id!r}: family {brief['family']!r} is not one of art/briefs.json families {order}")
            rows.append((kind, item_id, brief))
    return sorted(rows, key=lambda r: order.index(r[2]["family"]))


def by_family(kinds: dict, briefs: dict):
    """[(family label, [(kind, id, brief), ...])] in family order."""
    return [(briefs["families"][fam], list(rows))
            for fam, rows in itertools.groupby(ordered(kinds, briefs), key=lambda r: r[2]["family"])]


def markdown(root: Path, kinds: dict) -> str:
    briefs = load_briefs(root)
    out = ["# The pack's textures, one brief each", "",
           "Generated from `art/briefs.json` by `tools/gen_preview.py`; edit the JSON, not this file. "
           "Rules in `art/STYLE.md`; how to hand work back in `art/CONTRIBUTING.md`. The images are the current "
           "PNGs at 8x, regenerated with `python3 tools/gen_textures.py --preview art/preview/x8`.", "",
           PREAMBLE, ""]
    for label, rows in by_family(kinds, briefs):
        out += [f"## {label}", ""]
        for kind, item_id, b in rows:
            out += [f"### {b['display']} (`kubejs:{item_id}`)", "",
                    f"![{item_id} at 8x](preview/x8/{item_id}.png)", "",
                    f"`kubejs/assets/kubejs/textures/{kind}/{item_id}.png` - {kind}, family *{b['family']}*.", "",
                    f"**What it is:** {b['role']}", "",
                    f"**Where it is earned:** {b['earned']}", "",
                    f"**What consumes it:** {b['consumed']}", "",
                    f"**Drawing notes:** {b['notes']}", ""]
            if b.get("node"):
                out += [f"*Maintainer ref: tree node [{b['node']}].*", ""]
    return "\n".join(out)


PAGE = Template("""<title>Confluence Textures</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Pixelify+Sans:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono&display=swap">
<style>
:root { --bg:#F5F2F8; --ink:#1B1220; --mute:#6E6580; --line:#DCD5E6; --card:#FFFFFF;
        --panel:#C6C6C6; --slot:#8B8B8B; --slot-dark:#373737; --slot-light:#FFFFFF; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#16121C; --ink:#F2EEF5; --mute:#A69DB5; --line:#2E2840; --card:#1F1927; } }
:root[data-theme="dark"] { --bg:#16121C; --ink:#F2EEF5; --mute:#A69DB5; --line:#2E2840; --card:#1F1927; }
body { background:var(--bg); color:var(--ink); font-family:"IBM Plex Sans",system-ui,sans-serif; font-size:15px;
       line-height:1.5; padding:0 20px; padding-block:32px 56px; }
main { max-width:960px; margin:0 auto; }
h1, h2 { font-family:"Pixelify Sans","IBM Plex Sans",sans-serif; font-weight:600; text-wrap:balance; margin:0; }
h1 { font-size:2.2rem; letter-spacing:.01em; }
h2 { font-size:1.4rem; margin-top:40px; padding-bottom:6px; border-bottom:2px solid var(--line); }
.eyebrow { font-family:"IBM Plex Mono",monospace; font-size:.8rem; letter-spacing:.08em; text-transform:uppercase; color:var(--mute); }
.lede { max-width:62ch; color:var(--mute); margin:8px 0 0; }
.palette { display:flex; flex-wrap:wrap; gap:10px; margin-top:16px; }
.swatch { width:88px; font-family:"IBM Plex Mono",monospace; font-size:.72rem; color:var(--mute); }
.swatch i { display:block; height:36px; border:1px solid var(--mute); margin-bottom:4px; }
.swatch b { display:block; color:var(--ink); font-weight:500; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr)); gap:16px; margin-top:16px; }
.card { background:var(--card); border:1px solid var(--line); padding:14px; display:flex; flex-direction:column; gap:8px; }
.panel { background:var(--panel); padding:12px; display:flex; justify-content:center; align-items:center; gap:12px;
         border:2px solid; border-color:var(--slot-light) var(--slot-dark) var(--slot-dark) var(--slot-light); }
.slot { width:140px; height:140px; background:var(--slot); border:2px solid; padding:4px; box-sizing:border-box;
        border-color:var(--slot-dark) var(--slot-light) var(--slot-light) var(--slot-dark); }
.slot img, .mini img { image-rendering:pixelated; display:block; }
.slot img { width:128px; height:128px; }
.mini { width:24px; height:24px; background:var(--slot); border:2px solid; padding:2px; box-sizing:border-box;
        border-color:var(--slot-dark) var(--slot-light) var(--slot-light) var(--slot-dark); align-self:flex-end; }
.mini img { width:16px; height:16px; }
.tile { width:128px; height:128px; image-rendering:pixelated; background-size:64px 64px; background-repeat:repeat; }
.name { font-weight:600; }
.id { font-family:"IBM Plex Mono",monospace; font-size:.78rem; color:var(--mute); }
.role { font-size:.9rem; margin:0; }
footer { margin-top:48px; color:var(--mute); font-size:.85rem; max-width:62ch; }
code { font-family:"IBM Plex Mono",monospace; font-size:.85em; }
@media (max-width:480px) { .grid { grid-template-columns:1fr; } }
</style>
<main>
  <div class="eyebrow">Confluence &middot; Round $round &middot; $date</div>
  <h1>Confluence Textures</h1>
  <p class="lede">Every texture the pack owns: items at 1&times; and 8&times; in an inventory slot, blocks as a tile.
  Leave a comment on anything; the PNGs live in <code>kubejs/assets/kubejs/textures/</code> and the rules in
  <code>art/STYLE.md</code>.</p>
  <p class="lede">$preamble</p>
  <h2>Palette</h2>
  <div class="palette">$palette</div>
$sections
  <footer>Blocks are shown as a 2&times;2 tile at 4&times; so seams show. Items sit in a vanilla-style slot at 8&times;
  with the 1&times; original beside them. Generated by <code>tools/gen_preview.py</code> from
  <code>art/briefs.json</code>.</footer>
</main>
""")


def data_uri(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def html(root: Path, kinds: dict, round_no: int, date: str) -> str:
    briefs = load_briefs(root)
    palette = gen_textures.parse_palette((root / "art" / "palette.gpl").read_text())
    swatches = "".join(
        f'<div class="swatch"><i style="background:#{r:02X}{g:02X}{b:02X}"></i>'
        f'<b>{htmlmod.escape(name)}</b>#{r:02X}{g:02X}{b:02X}</div>'
        for name, (r, g, b) in palette.items())
    sections = []
    for label, rows in by_family(kinds, briefs):
        cards = []
        for kind, item_id, b in rows:
            uri = data_uri(packitems.texture_path(kind, item_id, root).read_bytes())
            if kind == "item":
                art = (f'<div class="panel"><div class="slot"><img src="{uri}" alt="{item_id} at 8x"></div>'
                       f'<div class="mini"><img src="{uri}" alt="{item_id} at 1x"></div></div>')
            else:
                art = (f'<div class="panel"><div class="tile" style="background-image:url({uri})" role="img" '
                       f'aria-label="{item_id} tiled"></div></div>')
            cards.append(f'<div class="card">{art}<div><div class="name">{htmlmod.escape(b["display"])}</div>'
                         f'<div class="id">kubejs:{item_id}</div></div><p class="role">{htmlmod.escape(b["role"])}</p></div>')
        sections.append(f'<h2>{htmlmod.escape(label)}</h2><div class="grid">{"".join(cards)}</div>')
    return PAGE.substitute(round=round_no, date=date, preamble=htmlmod.escape(PREAMBLE), palette=swatches,
                           sections="\n".join(sections))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--no-md", action="store_true", help="skip art/TEXTURES.md")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="date shown on the page (default: today)")
    args = ap.parse_args(argv)
    root, kinds = packitems.ROOT, packitems.load()
    if not args.no_md:
        (root / "art" / "TEXTURES.md").write_text(markdown(root, kinds))
        print("wrote art/TEXTURES.md")
    out = root / "art" / "preview" / f"round-{args.round}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html(root, kinds, args.round, args.date))
    print(f"wrote {out.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
