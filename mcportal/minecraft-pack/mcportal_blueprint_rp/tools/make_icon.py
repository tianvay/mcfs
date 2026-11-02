"""Draws the blueprint textures (16x16 items, 4x4 particles):
    textures/items/mcfs_blueprint.png          empty blueprint: blue paper with a white grid
    textures/items/mcfs_blueprint_marking.png  corner 1 set: a yellow corner mark top left
    textures/items/mcfs_blueprint_filled.png   saved area: a white wall with battlements on the paper
    textures/particle/mcfs_blueprint_dot.png   outline dot (light blue), ..._red.png (area too big)

Plain Python (zlib + struct), no image library needed:
    python tools/make_icon.py                 -> all textures
    python tools/make_icon.py <name> <file> 16 -> an enlarged preview (16x) of one item to look at
"""
import struct
import sys
import zlib
from pathlib import Path

# . transparent, e paper edge (dark blue), b paper (blue), g grid line, w white drawing, y yellow mark
BLANK = [
    "................",
    ".eeeeeeeeeeeeee.",
    ".ebbbgbbbbgbbbe.",
    ".ebbbgbbbbgbbbe.",
    ".egggggggggggge.",
    ".ebbbgbbbbgbbbe.",
    ".ebbbgbbbbgbbbe.",
    ".ebbbgbbbbgbbbe.",
    ".egggggggggggge.",
    ".ebbbgbbbbgbbbe.",
    ".ebbbgbbbbgbbbe.",
    ".ebbbgbbbbgbbbe.",
    ".egggggggggggge.",
    ".ebbbgbbbbgbbbe.",
    ".eeeeeeeeeeeeee.",
    "................",
]
MARKING = [
    "................",
    ".eeeeeeeeeeeeee.",
    ".eyyybbbbbgbbbe.",
    ".eybbgbbbbgbbbe.",
    ".eyggggggggggge.",
    ".ebbbgbbbbgbbbe.",
    ".ebbbgbbbbgbbbe.",
    ".ebbbgbbbbgbbbe.",
    ".egggggggggggge.",
    ".ebbbgbbbbgbbbe.",
    ".ebbbgbbbbgbbbe.",
    ".ebbbgbbbbgbbbe.",
    ".egggggggggggge.",
    ".ebbbgbbbbgbbbe.",
    ".eeeeeeeeeeeeee.",
    "................",
]
FILLED = [
    "................",
    ".eeeeeeeeeeeeee.",
    ".ebbbbbbbbbbbbe.",
    ".ebbbbbbbbbbbbe.",
    ".ebwwbwwbwwbwwe.",
    ".ebwwbwwbwwbwwe.",
    ".ebwwwwwwwwwwwe.",
    ".ebwbbbbbbbbbwe.",
    ".ebwbbbwwbbbbwe.",
    ".ebwbbwbbwbbbwe.",
    ".ebwbbwbbwbbbwe.",
    ".ebwwwwwwwwwwwe.",
    ".ebbbbbbbbbbbbe.",
    ".ebbbbbbbbbbbbe.",
    ".eeeeeeeeeeeeee.",
    "................",
]
DOT = ["cccc"] * 4
DOT_RED = ["rrrr"] * 4
COLORS = {
    ".": (0, 0, 0, 0),
    "e": (20, 50, 120, 255),
    "b": (45, 100, 200, 255),
    "g": (130, 175, 235, 255),
    "w": (240, 248, 255, 255),
    "y": (255, 215, 60, 255),
    "c": (120, 220, 255, 230),
    "r": (255, 70, 60, 230),
}
ITEMS = {"mcfs_blueprint": BLANK, "mcfs_blueprint_marking": MARKING, "mcfs_blueprint_filled": FILLED}


def png(rows, scale=1):
    rows = [row for row in rows for _ in range(scale)]
    raw = b"".join(b"\x00" + b"".join(bytes(COLORS[c]) * scale for c in row) for row in rows)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    w, h = len(rows[0]) * scale, len(rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    assert all(len(r) == 16 for art in ITEMS.values() for r in art) and all(len(a) == 16 for a in ITEMS.values())
    tex = Path(__file__).resolve().parent.parent / "textures"
    if len(sys.argv) > 2:
        jobs = [(Path(sys.argv[2]), ITEMS[sys.argv[1]], int(sys.argv[3]) if len(sys.argv) > 3 else 16)]
    else:
        jobs = [(tex / "items" / f"{n}.png", art, 1) for n, art in ITEMS.items()]
        jobs += [(tex / "particle" / "mcfs_blueprint_dot.png", DOT, 1),
                 (tex / "particle" / "mcfs_blueprint_dot_red.png", DOT_RED, 1)]
    for out, art, scale in jobs:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(png(art, scale))
        print(f"geschrieben: {out} ({out.stat().st_size} Bytes)")
