import json
import re
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gen_preview
import gen_textures
import packitems
import pngio

B = (242, 182, 50, 255)

BRIEFS = {
    "families": {"single": "One-offs", "ores": "Ores"},
    "textures": {
        "coin": {"display": "Coin <1>", "family": "single", "role": "Currency & more.", "earned": "Quests.",
                 "consumed": "Bags.", "notes": "Plain."},
        "mercury_ore": {"display": "Mercury Ore", "family": "ores", "role": "Block.", "earned": "Mercury.",
                        "consumed": "Mined.", "notes": "Tiles.", "node": "D6.7"},
    },
}
KINDS = {"item": ["coin"], "block": ["mercury_ore"]}
PALETTE = "GIMP Palette\nName: T\nColumns: 1\n#\n 12  34  56\tzzz\n"  # a colour the page CSS never uses


def tree(tmp_path):
    for kind, ids in KINDS.items():
        for i in ids:
            p = packitems.texture_path(kind, i, tmp_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(pngio.encode([[B] * 16 for _ in range(16)]))
    (tmp_path / "art" / "preview" / "x8").mkdir(parents=True)
    (tmp_path / "art" / "briefs.json").write_text(json.dumps(BRIEFS))
    (tmp_path / "art" / "palette.gpl").write_text(PALETTE)
    return tmp_path


def test_markdown_has_a_section_per_texture_in_family_order(tmp_path):
    root = tree(tmp_path)
    md = gen_preview.markdown(root, KINDS)
    assert md.count("\n### ") == 2
    assert md.index("## One-offs") < md.index("### Coin <1> (`kubejs:coin`)") < md.index("## Ores") < md.index("### Mercury Ore")
    assert "![coin at 8x](preview/x8/coin.png)" in md
    assert "**Where it is earned:** Mercury." in md
    assert "*Maintainer ref: tree node [D6.7].*" in md
    assert gen_preview.PREAMBLE in md


def test_html_embeds_every_png_and_the_palette(tmp_path):
    root = tree(tmp_path)
    html = gen_preview.html(root, KINDS, round_no=3, date="2026-09-12")
    assert html.count("data:image/png;base64,") == 3  # coin at 8x and 1x, the ore tile once
    assert "Round 3" in html and "2026-09-12" in html
    assert '<i style="background:#0C2238"></i><b>zzz</b>#0C2238' in html
    assert re.findall(r"<h2>(.*?)</h2>", html) == ["Palette", "One-offs", "Ores"]
    assert 'class="slot"' in html and 'class="tile"' in html
    assert "Coin &lt;1&gt;" in html and "Currency &amp; more." in html and "<1>" not in html


def test_missing_brief_is_an_error(tmp_path):
    root = tree(tmp_path)
    with pytest.raises(KeyError, match="no brief for 'ghost'"):
        gen_preview.markdown(root, {"item": ["coin", "ghost"], "block": []})


def test_unknown_family_is_an_error(tmp_path):
    root = tree(tmp_path)
    briefs = json.loads((root / "art" / "briefs.json").read_text())
    briefs["textures"]["coin"]["family"] = "relics"
    (root / "art" / "briefs.json").write_text(json.dumps(briefs))
    with pytest.raises(KeyError, match="'coin': family 'relics' is not one of art/briefs.json families"):
        gen_preview.markdown(root, KINDS)


def test_missing_brief_field_names_the_texture(tmp_path):
    root = tree(tmp_path)
    briefs = json.loads((root / "art" / "briefs.json").read_text())
    del briefs["textures"]["coin"]["earned"]
    (root / "art" / "briefs.json").write_text(json.dumps(briefs))
    with pytest.raises(KeyError, match=r"'coin': brief is missing \['earned'\]"):
        gen_preview.markdown(root, KINDS)


def test_real_briefs_cover_every_registered_id():
    briefs = json.loads((packitems.ROOT / "art" / "briefs.json").read_text())
    ids = packitems.load()
    assert set(briefs["textures"]) == set(ids["item"]) | set(ids["block"])
    for entry in briefs["textures"].values():
        assert entry["family"] in briefs["families"]
        assert all(entry[k] for k in ("display", "role", "earned", "consumed", "notes"))


def test_committed_textures_md_is_current():
    committed = (packitems.ROOT / "art" / "TEXTURES.md").read_text()
    assert gen_preview.markdown(packitems.ROOT, packitems.load()) == committed, \
        "art/TEXTURES.md is stale: run python3 tools/gen_preview.py --round <n>"


def test_x8_previews_match_canonical_pngs():
    for kind, ids in packitems.load().items():
        for item_id in ids:
            _, _, rows = pngio.decode(packitems.texture_path(kind, item_id).read_bytes())
            w, h, preview = pngio.decode((packitems.ROOT / "art" / "preview" / "x8" / f"{item_id}.png").read_bytes())
            assert (w, h) == (128, 128), item_id
            assert preview == gen_textures.upscale(rows, 8), \
                f"art/preview/x8/{item_id}.png is stale: run python3 tools/gen_textures.py --preview art/preview/x8"
