"""Stdlib PNG read/write for 8-bit RGBA textures (there is no Pillow in the pack toolchain).

encode(rows)  rows of (r, g, b, a) tuples -> PNG bytes; filter type 0, one IDAT chunk.
header(data)  -> (width, height, bit_depth, colour_type, interlace) from IHDR, for any PNG.
decode(data)  -> (width, height, rows) for 8-bit colour-type-6 non-interlaced files, undoing scanline filters
              0-4 and joining every IDAT chunk. Anything else (indexed, RGB without alpha, 16-bit, Adam7)
              raises PngError with a reason an artist can act on.
CRCs are written but not checked on read; a truncated or corrupt file raises PngError from the chunk walk or
from zlib, so callers only ever handle PngError.
"""
import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"
COLOUR_TYPE_NAMES = {0: "greyscale", 2: "RGB without alpha", 3: "indexed (palette)",
                     4: "greyscale with alpha", 6: "RGBA"}


class PngError(ValueError):
    pass


def chunk(tag: bytes, data: bytes) -> bytes:
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def encode(rows: list) -> bytes:
    height, width = len(rows), len(rows[0])
    raw = b"".join(b"\x00" + bytes(c for px in row for c in px) for row in rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return SIGNATURE + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def chunks(data: bytes):
    if data[:8] != SIGNATURE:
        raise PngError("not a PNG file (bad signature)")
    pos = 8
    while pos + 8 <= len(data):
        length, tag = struct.unpack(">I4s", data[pos:pos + 8])
        if pos + 12 + length > len(data):
            raise PngError("truncated chunk " + tag.decode("latin-1"))
        yield tag, data[pos + 8:pos + 8 + length]
        if tag == b"IEND":
            return
        pos += 12 + length


def header(data: bytes) -> tuple:
    for tag, body in chunks(data):
        if tag == b"IHDR":
            if len(body) < 13:
                raise PngError("truncated IHDR")
            w, h, depth, ctype, _comp, _filt, interlace = struct.unpack(">IIBBBBB", body[:13])
            return w, h, depth, ctype, interlace
    raise PngError("no IHDR chunk")


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode(data: bytes) -> tuple:
    w, h, depth, ctype, interlace = header(data)
    if depth != 8:
        raise PngError(f"{depth}-bit; export as 8-bit")
    if ctype != 6:
        raise PngError(f"{COLOUR_TYPE_NAMES.get(ctype, ctype)}; export as RGBA (colour type 6) - "
                       "convert the sprite to RGB colour mode with an alpha channel before saving")
    if interlace:
        raise PngError("interlaced (Adam7); save without interlacing")
    try:
        raw = zlib.decompress(b"".join(body for tag, body in chunks(data) if tag == b"IDAT"))
    except zlib.error:
        raise PngError("image data is corrupt or truncated") from None
    stride = w * 4
    if len(raw) != h * (stride + 1):
        raise PngError("image data length does not match the header")
    rows, prev = [], bytearray(stride)
    for y in range(h):
        start = y * (stride + 1)
        f = raw[start]
        if f > 4:
            raise PngError(f"unknown filter type {f} on row {y}")
        line = bytearray(raw[start + 1:start + 1 + stride])
        for x in range(stride):
            a = line[x - 4] if x >= 4 else 0        # already unfiltered: in-place, left to right
            b = prev[x]
            c = prev[x - 4] if x >= 4 else 0
            if f == 1:
                line[x] = (line[x] + a) & 0xFF
            elif f == 2:
                line[x] = (line[x] + b) & 0xFF
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 0xFF
            elif f == 4:
                line[x] = (line[x] + _paeth(a, b, c)) & 0xFF
        rows.append([tuple(line[i:i + 4]) for i in range(0, stride, 4)])
        prev = line
    return w, h, rows
