"""Write 16x16 placeholder PNGs for the pack items and blocks."""
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "kubejs" / "assets" / "kubejs" / "textures"
ITEMS = {
    "twilight_key": (90, 200, 120), "other_key": (200, 90, 200), "end_focus": (60, 60, 120),
    "astral_focus": (240, 220, 120), "confluence_catalyst": (255, 120, 40), "coin": (230, 190, 40),
    "mercury_shard": (200, 120, 60), "glacio_shard": (150, 220, 255),
}
BLOCKS = {"mercury_ore": (120, 70, 50), "glacio_ore": (170, 200, 230)}


def png(rgb, size=16):
    r, g, b = rgb
    dark = (r // 2, g // 2, b // 2)
    rows = b""
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            px = dark if (x in (0, size - 1) or y in (0, size - 1)) else (r, g, b)
            row += bytes(px) + b"\xff"
        rows += bytes(row)
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


if __name__ == "__main__":
    for folder, table in (("item", ITEMS), ("block", BLOCKS)):
        d = ROOT / folder
        d.mkdir(parents=True, exist_ok=True)
        for name, rgb in table.items():
            (d / f"{name}.png").write_bytes(png(rgb))
            print("wrote", d / f"{name}.png")
