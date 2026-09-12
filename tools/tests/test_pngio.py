import base64
import random
import struct
import zlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pngio


def image(w=16, h=16):
    """Deterministic RGBA rows: a gradient with a transparent top-left quadrant."""
    return [[(x * 16 % 256, y * 16 % 256, (x + y) * 8 % 256, 0 if x < 8 and y < 8 else 255)
             for x in range(w)] for y in range(h)]


def paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def noise(w=16, h=16, seed=0):
    rng = random.Random(seed)
    return [[(rng.randrange(256), rng.randrange(256), rng.randrange(256), rng.choice((0, 255)))
             for _ in range(w)] for _ in range(h)]


def filtered_png(rows, ftype, idat_split=1, colour_type=6, depth=8, interlace=0):
    """Build a PNG by applying filter `ftype` to every scanline, so decode must undo it."""
    w, h = len(rows[0]), len(rows)
    flat = [bytes(c for px in row for c in px) for row in rows]
    prev = bytes(w * 4)
    raw = b""
    for line in flat:
        out = bytearray()
        for x in range(len(line)):
            a = line[x - 4] if x >= 4 else 0
            b = prev[x]
            c = prev[x - 4] if x >= 4 else 0
            pred = {0: 0, 1: a, 2: b, 3: (a + b) // 2, 4: paeth(a, b, c)}[ftype]
            out.append((line[x] - pred) & 0xFF)
        raw += bytes([ftype]) + bytes(out)
        prev = line
    comp = zlib.compress(raw)
    step = max(1, len(comp) // idat_split)
    idats = [comp[i:i + step] for i in range(0, len(comp), step)]
    ihdr = struct.pack(">IIBBBBB", w, h, depth, colour_type, 0, 0, interlace)
    data = pngio.SIGNATURE + pngio.chunk(b"IHDR", ihdr)
    for part in idats:
        data += pngio.chunk(b"IDAT", part)
    return data + pngio.chunk(b"IEND", b"")


# A 16x16 RGBA PNG matching image()'s pixels, re-encoded by macOS `sips` (its own filters, plus ancillary
# chunks sRGB and eXIf) so decode() is proven against a real encoder, not just against itself.
GOLDEN = ("iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAAXNSR0IArs4c6QAAAERlWElmTU0AKgAAAAgAAYdpAAQAAAAB"
          "AAAAGgAAAAAAA6ABAAMAAAABAAEAAKACAAQAAAABAAAAEKADAAQAAAABAAAAEAAAAAA0VXHyAAAAMUlEQVQ4EWNkAAIBBg58"
          "+D8+eRYGAQ6gEeTjUQM4GAZHGPwfjUbykzEo7AZHNFKUGwEe/AwUHXNUBQAAAABJRU5ErkJggg==")


def test_decodes_a_png_written_by_a_real_encoder():
    data = base64.b64decode(GOLDEN)
    assert pngio.header(data)[:2] == (16, 16)
    assert pngio.decode(data)[2] == image()


def test_encode_decode_round_trip():
    rows = image()
    w, h, back = pngio.decode(pngio.encode(rows))
    assert (w, h) == (16, 16)
    assert back == rows


def test_header_reads_ihdr():
    assert pngio.header(pngio.encode(image())) == (16, 16, 8, 6, 0)


@pytest.mark.parametrize("ftype", [1, 2, 3, 4])
def test_decode_unfilters_every_filter_type(ftype):
    rows = noise()
    assert pngio.decode(filtered_png(rows, ftype))[2] == rows


def test_paeth_prefers_a_on_tie_with_c():
    # red of pixel (1,1): a=40, b=10, c=20 -> p=30, pa=10, pb=20, pc=10; the spec picks a.
    tie = [[(20, 0, 0, 255), (10, 0, 0, 255)], [(40, 0, 0, 255), (99, 0, 0, 255)]]
    assert pngio.decode(filtered_png(tie, 4))[2] == tie


def test_decode_joins_multiple_idat_chunks():
    rows = noise()
    assert pngio.decode(filtered_png(rows, 2, idat_split=4))[2] == rows


def test_indexed_png_is_refused_with_reason():
    data = filtered_png(image(), 0, colour_type=3)
    assert pngio.header(data)[3] == 3
    with pytest.raises(pngio.PngError, match="indexed"):
        pngio.decode(data)


def test_interlaced_png_is_refused_with_reason():
    with pytest.raises(pngio.PngError, match="interlaced"):
        pngio.decode(filtered_png(image(), 0, interlace=1))


def test_bad_signature_is_refused():
    with pytest.raises(pngio.PngError, match="signature"):
        pngio.header(b"not a png")


@pytest.mark.parametrize("colour_type, depth, reason", [(2, 8, "RGB without alpha"), (6, 16, "16-bit")])
def test_other_unsupported_formats_are_refused(colour_type, depth, reason):
    with pytest.raises(pngio.PngError, match=reason):
        pngio.decode(filtered_png(image(), 0, colour_type=colour_type, depth=depth))


@pytest.mark.parametrize("cut", [20, 40, 60])
def test_truncated_file_raises_png_error(cut):
    data = pngio.encode(image())
    with pytest.raises(pngio.PngError):
        pngio.decode(data[:cut])


def test_encode_writes_valid_crcs():
    data = pngio.encode(image())
    pos = 8
    while pos < len(data):
        length, tag = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        crc, = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        assert crc == zlib.crc32(tag + body) & 0xFFFFFFFF, tag
        pos += 12 + length
