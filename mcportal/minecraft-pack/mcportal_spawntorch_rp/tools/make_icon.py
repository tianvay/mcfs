"""Draws textures/items/mcfs_spawn_torch.png (16x16) - a torch with a hot flame standing on a red veil -
and textures/particle/mcfs_spawn_veil.png, the veil drawn on dark blocks (size and lifetime: particles/spawn_veil.json).

Plain Python (zlib + struct), no image library needed:
    python tools/make_icon.py            -> both textures
    python tools/make_icon.py <file> 16  -> an enlarged preview (16x) to look at
"""
import struct
import sys
import zlib
from pathlib import Path

# . transparent, h red glow, y/Y flame orange/yellow, W flame core, c glowing tip,
# b/B stick light/dark, v/V red veil / its bright edge
ART = [
    "................",
    ".......hh.......",
    "......hyyh......",
    ".....hyYYyh.....",
    ".....yYWWYy.....",
    ".....yYWWYy.....",
    "......yYYy......",
    "......hccy......",
    ".......bB.......",
    ".......bB.......",
    ".......bB.......",
    "......vbBv......",
    "...vvvvbBvvvv...",
    ".VvvvvvvvvvvvvV.",
    "...VvvvvvvvvV...",
    "......VVVV......",
]
COLORS = {
    ".": (0, 0, 0, 0),
    "h": (255, 70, 40, 120),
    "y": (255, 140, 30, 255),
    "Y": (255, 220, 70, 255),
    "W": (255, 255, 220, 255),
    "c": (255, 170, 60, 255),
    "b": (160, 115, 65, 255),
    "B": (100, 70, 40, 255),
    "v": (220, 30, 30, 170),
    "V": (255, 80, 70, 230),
    "r": (230, 30, 30, 80),
    "R": (255, 60, 50, 190),
}
# the veil: see-through red with a stronger edge, so neighbouring dark blocks still read as single blocks
VEIL = ["R" * 16] + ["R" + "r" * 14 + "R" for _ in range(14)] + ["R" * 16]


def png(rows, scale=1):
    rows = [row for row in rows for _ in range(scale)]
    raw = b"".join(b"\x00" + b"".join(bytes(COLORS[c]) * scale for c in row) for row in rows)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    w, h = len(rows[0]) * scale, len(rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    assert all(len(r) == 16 for r in ART + VEIL) and len(ART) == len(VEIL) == 16
    if len(sys.argv) > 1:
        jobs = [(Path(sys.argv[1]), ART, int(sys.argv[2]) if len(sys.argv) > 2 else 16)]
    else:
        tex = Path(__file__).resolve().parent.parent / "textures"
        jobs = [(tex / "items" / "mcfs_spawn_torch.png", ART, 1), (tex / "particle" / "mcfs_spawn_veil.png", VEIL, 1)]
    for out, art, scale in jobs:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(png(art, scale))
        print(f"geschrieben: {out} ({out.stat().st_size} Bytes)")
