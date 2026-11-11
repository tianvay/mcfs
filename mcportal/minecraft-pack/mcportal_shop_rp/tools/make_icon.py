"""Draws the 16x16 item textures of the Sterntaler shop:
    textures/items/mcfs_bergbrecher.png   pickaxe with a turquoise head and a gold star
    textures/items/mcfs_holzfaeller.png   axe with a green blade
    textures/items/mcfs_magnet.png        red horseshoe magnet on a gold chain
    textures/items/mcfs_erntesichel.png   sickle with a gold blade

Plain Python (zlib + struct), no image library needed:
    python tools/make_icon.py                  -> all textures
    python tools/make_icon.py <name> <file> 16 -> an enlarged preview (16x) of one item to look at
"""
import struct
import sys
import zlib
from pathlib import Path

# . transparent; h/H handle dark/light; c/C/w turquoise edge/body/shine; g/G gold/dark gold;
# e/E/l green edge/body/shine; r/R/p red dark/body/shine; s/S steel dark/light
BERGBRECHER = [
    "................",
    "....ccccccc.....",
    "...cCwwCCCCcc...",
    "....cccCCCCCCc..",
    ".......ccgGCCc..",
    "........hgggCCc.",
    ".......hHhGcCCc.",
    "......hHh..cCCc.",
    ".....hHh...cCwc.",
    "....hHh....cCwc.",
    "...hHh.....cCc..",
    "..hHh.......c...",
    ".hHh............",
    ".hh.............",
    "................",
    "................",
]
HOLZFAELLER = [
    "................",
    ".........ee.....",
    "........eEEe....",
    ".......eElEEe...",
    "......eEllEEEe..",
    ".....eEEEEhEEEe.",
    ".....eEEEhHhEEe.",
    "......eEhHhEEEe.",
    ".......hHh.eEe..",
    "......hHh...e...",
    ".....hHh........",
    "....hHh.........",
    "...hHh..........",
    "..hHh...........",
    "..hh............",
    "................",
]
MAGNET = [
    ".....gGgGg......",
    "....g.....g.....",
    "....G.....G.....",
    "..SSS.....SSS...",
    "..sSS.....sSS...",
    "..rRp.....rRp...",
    "..rRp.....rRp...",
    "..rRp.....rRp...",
    "..rRp.....rRp...",
    "..rRRp...rRRp...",
    "..rRRRpppRRRp...",
    "...rRRRRRRRp....",
    "....rRRRRRr.....",
    ".....rrrrr......",
    "................",
    "................",
]
ERNTESICHEL = [
    "................",
    "....GGGGGG......",
    "..GGggggggGG....",
    ".GgggGGGGgggG...",
    ".GgGG....GGggG..",
    "..G........GgG..",
    "............GgG.",
    "............GgG.",
    "............GgG.",
    "...........GgG..",
    "..........GgG...",
    ".........hGG....",
    "........hHh.....",
    ".......hHh......",
    "......hHh.......",
    "......hh........",
]
COLORS = {
    ".": (0, 0, 0, 0),
    "h": (73, 47, 21, 255), "H": (137, 94, 44, 255),
    "c": (14, 92, 104, 255), "C": (51, 196, 204, 255), "w": (190, 250, 250, 255),
    "g": (255, 216, 77, 255), "G": (190, 138, 24, 255),
    "e": (24, 92, 44, 255), "E": (62, 176, 86, 255), "l": (170, 240, 170, 255),
    "r": (120, 20, 20, 255), "R": (214, 48, 48, 255), "p": (255, 150, 140, 255),
    "s": (110, 116, 128, 255), "S": (214, 220, 230, 255),
}
ITEMS = {"mcfs_bergbrecher": BERGBRECHER, "mcfs_holzfaeller": HOLZFAELLER, "mcfs_magnet": MAGNET,
         "mcfs_erntesichel": ERNTESICHEL}


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
    for out, art, scale in jobs:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(png(art, scale))
        print(f"geschrieben: {out} ({out.stat().st_size} Bytes)")
