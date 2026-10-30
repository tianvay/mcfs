"""Portal icon: a pixel zombie head (own 12x12 design), for the iPad home screen and the browser tab.

    python tools/make_icon.py      -> app/web/icon-180.png (apple-touch-icon), app/web/icon-48.png

Fully opaque on purpose: iOS rounds the corners itself and shows transparent parts black.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.map.png import encode_rgba  # noqa: E402

COLORS = {
    "D": (0x2f, 0x5e, 0x2a),  # dark green (hair line, shadow)
    "G": (0x4f, 0x8a, 0x3c),  # skin
    "L": (0x6a, 0xa8, 0x4f),  # light skin spots
    "E": (0x14, 0x14, 0x14),  # eye socket
    "C": (0x3f, 0xd0, 0xb8),  # glowing pupil
    "N": (0x38, 0x6b, 0x30),  # nose
    "M": (0x1f, 0x38, 0x1b),  # mouth
}
FACE = [
    "DDDGDDDDGDDD",
    "DGDDDGDDDDGD",
    "GGLGGGGLGGGG",
    "GLGGLGGGGLGG",
    "GEECGGGGCEEG",
    "GEEEGGGGEEEG",
    "GLGGGNNGGGLG",
    "GGGGGNNGGGGG",
    "GGMMMMMMMMGG",
    "GLMGGMMGGMLG",
    "GGGGLGGLGGGG",
    "DGGGGGGGGGGD",
]


def render(size: int) -> bytes:
    n = len(FACE)
    px = bytearray()
    for y in range(size):
        row = FACE[y * n // size]
        for x in range(size):
            px += bytes(COLORS[row[x * n // size]]) + b"\xff"
    return encode_rgba(size, size, bytes(px), level=9)


def main() -> None:
    web = ROOT / "app" / "web"
    for size in (180, 48):  # whole multiples of the 12x12 grid
        (web / f"icon-{size}.png").write_bytes(render(size))
        print(f"app/web/icon-{size}.png")


if __name__ == "__main__":
    main()
