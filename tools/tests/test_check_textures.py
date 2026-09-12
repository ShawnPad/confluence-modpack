import struct
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_textures
import packitems
import pngio

T = (0, 0, 0, 0)
O = (27, 18, 32, 255)
B = (242, 182, 50, 255)


def item_rows():
    """A 14x14 outlined box inside a clear 1-px border: passes every item rule."""
    rows = [[T] * 16 for _ in range(16)]
    for y in range(1, 15):
        for x in range(1, 15):
            rows[y][x] = O if y in (1, 14) or x in (1, 14) else B
    return rows


def block_rows():
    return [[B] * 16 for _ in range(16)]


def test_good_item_passes():
    assert check_textures.check_png(pngio.encode(item_rows()), "item") == []


def test_good_block_passes():
    assert check_textures.check_png(pngio.encode(block_rows()), "block") == []


def test_r2_wrong_size():
    data = pngio.encode([[B] * 8 for _ in range(8)])
    assert check_textures.check_png(data, "block") == ["R2 is 8x8, must be 16x16"]


def test_r2_indexed_png_names_the_colour_type():
    ihdr = struct.pack(">IIBBBBB", 16, 16, 8, 3, 0, 0, 0)
    data = pngio.SIGNATURE + pngio.chunk(b"IHDR", ihdr) + pngio.chunk(b"IEND", b"")
    [msg] = check_textures.check_png(data, "item")
    assert msg == "R2 indexed (palette); export as RGBA (colour type 6) - " \
        "convert the sprite to RGB colour mode with an alpha channel before saving"


def test_r3_partial_alpha():
    rows = item_rows()
    rows[5][5] = (242, 182, 50, 128)
    assert check_textures.check_png(pngio.encode(rows), "item") == \
        ["R3 1 pixel(s) with partial alpha; use only fully opaque or fully transparent pixels"]


def test_r4_item_border_must_be_clear():
    rows = item_rows()
    rows[0][3] = O
    rows[7][15] = O
    assert check_textures.check_png(pngio.encode(rows), "item") == \
        ["R4 2 non-transparent pixel(s) on the outer 1-px border; keep the outline inside it"]


def test_r4_counts_each_corner_once():
    rows = item_rows()
    rows[0][0] = O
    assert check_textures.check_png(pngio.encode(rows), "item") == \
        ["R4 1 non-transparent pixel(s) on the outer 1-px border; keep the outline inside it"]


def test_r2_interlaced_and_16_bit_are_refused():
    for depth, interlace, word in ((8, 1, "interlaced"), (16, 0, "16-bit")):
        ihdr = struct.pack(">IIBBBBB", 16, 16, depth, 6, 0, 0, interlace)
        data = pngio.SIGNATURE + pngio.chunk(b"IHDR", ihdr) + pngio.chunk(b"IEND", b"")
        [msg] = check_textures.check_png(data, "item")
        assert msg.startswith("R2 ") and word in msg, msg


def test_unknown_kind_raises():
    with pytest.raises(ValueError, match="unknown texture kind 'fluid'"):
        check_textures.check_png(pngio.encode(block_rows()), "fluid")


def test_r5_block_must_be_opaque():
    rows = block_rows()
    rows[2][2] = T
    assert check_textures.check_png(pngio.encode(rows), "block") == \
        ["R5 1 non-opaque pixel(s); a block texture must be fully opaque"]


def test_run_reports_missing_and_bad_files(tmp_path):
    coin = packitems.texture_path("item", "coin", tmp_path)
    coin.parent.mkdir(parents=True)
    coin.write_bytes(pngio.encode(item_rows()))
    ore = packitems.texture_path("block", "mercury_ore", tmp_path)
    ore.parent.mkdir(parents=True)
    holed = block_rows()
    holed[2][2] = T
    ore.write_bytes(pngio.encode(holed))
    failures = check_textures.run({"item": ["coin", "ghost"], "block": ["mercury_ore"]}, tmp_path)
    assert failures == [
        (Path("kubejs/assets/kubejs/textures/item/ghost.png"), "R1 missing"),
        (Path("kubejs/assets/kubejs/textures/block/mercury_ore.png"),
         "R5 1 non-opaque pixel(s); a block texture must be fully opaque"),
    ]
