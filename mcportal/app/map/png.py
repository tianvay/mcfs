"""Minimal PNG writer (RGBA, 8 bit) - no Pillow needed on the server."""
from __future__ import annotations

import struct
import zlib


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def encode_rgba(width: int, height: int, rgba: bytes, level: int = 6) -> bytes:
    if len(rgba) != width * height * 4:
        raise ValueError("pixel buffer has the wrong size")
    stride = width * 4
    raw = b"".join(b"\x00" + rgba[r * stride:(r + 1) * stride] for r in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(raw, level))
            + _chunk(b"IEND", b""))
