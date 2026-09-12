from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gen_textures
import packitems
import pngio

GPL = """GIMP Palette
Name: T
Columns: 2
#
 27  18  32\toutline
242 182  50\tgold_base
"""

GRID_OK = "# a comment\n. transparent\no outline\nB gold_base\n" + "\n".join(
    ["." * 16] + ["." + "o" * 14 + "."] + ["." + "o" + "B" * 12 + "o" + "."] * 12 + ["." + "o" * 14 + "."] + ["." * 16]
) + "\n"

KINDS = {"item": ["coin"], "block": ["mercury_ore"]}


def test_parse_palette():
    assert gen_textures.parse_palette(GPL) == {"outline": (27, 18, 32), "gold_base": (242, 182, 50)}


def test_parse_grid_maps_legend_to_rgba():
    rows = gen_textures.parse_grid(GRID_OK, gen_textures.parse_palette(GPL))
    assert len(rows) == 16 and all(len(r) == 16 for r in rows)
    assert rows[0][0] == (0, 0, 0, 0)
    assert rows[1][1] == (27, 18, 32, 255)
    assert rows[2][2] == (242, 182, 50, 255)


def test_parse_grid_rejects_wrong_row_count():
    with pytest.raises(ValueError, match="16 rows"):
        gen_textures.parse_grid(". transparent\n" + "\n".join(["." * 16] * 15), {})


def test_parse_grid_rejects_unknown_palette_name():
    with pytest.raises(ValueError, match="unknown palette colour 'nope'"):
        gen_textures.parse_grid("x nope\n" + "\n".join(["x" * 16] * 16), {})


def test_parse_grid_rejects_unlisted_pixel_character():
    with pytest.raises(ValueError, match="row 0: pixel character 'z' is not in the legend"):
        gen_textures.parse_grid(". transparent\n" + "\n".join(["." * 15 + "z"] * 16), {})


def test_upscale():
    rows = [[(1, 1, 1, 255), (2, 2, 2, 255)]]
    assert gen_textures.upscale(rows, 2) == [[(1, 1, 1, 255)] * 2 + [(2, 2, 2, 255)] * 2] * 2


def setup_tree(tmp_path):
    grids = tmp_path / "art" / "grids"
    grids.mkdir(parents=True)
    (tmp_path / "art" / "palette.gpl").write_text(GPL)
    (grids / "coin.txt").write_text(GRID_OK)
    (grids / "mercury_ore.txt").write_text("B gold_base\n" + "\n".join(["B" * 16] * 16))
    return tmp_path


def test_run_writes_missing_and_keeps_existing(tmp_path):
    root = setup_tree(tmp_path)
    written, kept, _ = gen_textures.run(root, KINDS)
    assert [p.name for p in written] == ["coin.png", "mercury_ore.png"] and kept == []
    coin = packitems.texture_path("item", "coin", root)
    assert pngio.header(coin.read_bytes()) == (16, 16, 8, 6, 0)
    coin.write_bytes(b"human edit")
    written, kept, _ = gen_textures.run(root, KINDS)
    assert written == [] and [p.name for p in kept] == ["coin.png", "mercury_ore.png"]
    assert coin.read_bytes() == b"human edit"
    written, kept, _ = gen_textures.run(root, KINDS, force=["coin"])
    assert [p.name for p in written] == ["coin.png"]
    assert coin.read_bytes() != b"human edit"


def test_run_preview_upscales_the_current_png(tmp_path):
    root = setup_tree(tmp_path)
    gen_textures.run(root, KINDS)
    coin = packitems.texture_path("item", "coin", root)
    coin.write_bytes(pngio.encode([[(255, 0, 0, 255)] * 16] * 16))
    out = tmp_path / "x8"
    _, _, previewed = gen_textures.run(root, KINDS, preview=out)
    assert sorted(p.name for p in previewed) == ["coin.png", "mercury_ore.png"]
    w, h, rows = pngio.decode((out / "coin.png").read_bytes())
    assert (w, h) == (128, 128) and rows[8][8] == (255, 0, 0, 255)


def test_run_refuses_grid_for_unknown_id(tmp_path):
    root = setup_tree(tmp_path)
    (root / "art" / "grids" / "ghost.txt").write_text(GRID_OK)
    with pytest.raises(ValueError, match="ghost.txt: no item or block with id 'ghost'"):
        gen_textures.run(root, KINDS)


def test_run_rejects_unknown_force_id(tmp_path):
    root = setup_tree(tmp_path)
    with pytest.raises(ValueError, match=r"--force: no grid for \['coni'\]"):
        gen_textures.run(root, KINDS, force=["coni"])


def test_run_refuses_preview_inside_assets(tmp_path):
    root = setup_tree(tmp_path)
    with pytest.raises(ValueError, match="must not point inside kubejs/assets"):
        gen_textures.run(root, KINDS, preview=root / "kubejs" / "assets" / "kubejs" / "textures" / "item")


def test_run_previews_a_registered_png_that_has_no_grid(tmp_path):
    root = setup_tree(tmp_path)
    hand = packitems.texture_path("item", "handmade", root)
    hand.parent.mkdir(parents=True, exist_ok=True)
    hand.write_bytes(pngio.encode([[(0, 0, 255, 255)] * 16] * 16))
    kinds = {"item": ["coin", "handmade"], "block": ["mercury_ore"]}
    _, _, previewed = gen_textures.run(root, kinds, preview=tmp_path / "x8")
    assert (tmp_path / "x8" / "handmade.png").exists() and len(previewed) == 3


def test_run_error_names_the_grid_file_and_row(tmp_path):
    root = setup_tree(tmp_path)
    (root / "art" / "grids" / "coin.txt").write_text(". transparent\n" + "\n".join(["." * 16] * 15 + ["." * 15 + "z"]))
    with pytest.raises(ValueError, match="coin.txt: row 15: pixel character 'z' is not in the legend"):
        gen_textures.run(root, KINDS)


def test_legend_line_may_use_a_tab():
    rows = gen_textures.parse_grid("x\tgold_base\n" + "\n".join(["x" * 16] * 16), gen_textures.parse_palette(GPL))
    assert rows[0][0] == (242, 182, 50, 255)


def test_parse_palette_rejects_out_of_range():
    with pytest.raises(ValueError, match="out of range"):
        gen_textures.parse_palette("GIMP Palette\n300  18  32\toutline\n")
