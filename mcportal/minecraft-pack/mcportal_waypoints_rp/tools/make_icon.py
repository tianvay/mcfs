"""Draws textures/items/mcfs_waypoint.png (16x16) - the waypoint seen from above.

Plain Python (zlib + struct), no image library needed:
    python tools/make_icon.py
"""
import struct
import zlib
from pathlib import Path

# . transparent, s/S stone bricks light/dark, l lantern gold, L lantern dark, d/D diamond light/dark, o outline
ART = [
    "................",
    ".oooooooooooooo.",
    ".oLlLsSsssSsLlLo",
    ".olllsSssssSlllo",
    ".oLlLssSsssSLlLo",
    ".osssooooooosssO",
    ".oSssoddddDosSso",
    ".osSsodDdddossso",
    ".ossSoddDddoSsso",
    ".osssodddDdosSso",
    ".oSssooooooossso",
    ".oLlLsssSsssLlLo",
    ".olllSsssSssllLo",
    ".oLlLssSsssSLlLo",
    ".oooooooooooooo.",
    "................",
]
COLORS = {
    ".": (0, 0, 0, 0),
    "o": (40, 40, 44, 255),
    "O": (40, 40, 44, 255),
    "s": (140, 140, 140, 255),
    "S": (105, 105, 108, 255),
    "l": (255, 205, 80, 255),
    "L": (190, 120, 40, 255),
    "d": (120, 240, 230, 255),
    "D": (40, 170, 175, 255),
}


def png(rows):
    raw = b"".join(b"\x00" + b"".join(bytes(COLORS[c]) for c in row) for row in rows)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    w, h = len(rows[0]), len(rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    assert all(len(r) == 16 for r in ART) and len(ART) == 16
    out = Path(__file__).resolve().parent.parent / "textures" / "items" / "mcfs_waypoint.png"
    out.write_bytes(png(ART))
    print(f"geschrieben: {out} ({out.stat().st_size} Bytes)")
