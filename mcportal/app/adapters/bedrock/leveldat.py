"""Read-only access to the world's level.dat (Bedrock: 8 byte header + little-endian NBT)."""
from __future__ import annotations

import struct
from pathlib import Path

_END, _BYTE, _SHORT, _INT, _LONG, _FLOAT, _DOUBLE, _BYTES, _STRING, _LIST, _COMPOUND, _INTS, _LONGS = range(13)
_FIXED = {_BYTE: "<b", _SHORT: "<h", _INT: "<i", _LONG: "<q", _FLOAT: "<f", _DOUBLE: "<d"}
MAX_SIZE = 1 << 20


class _Reader:
    def __init__(self, data: bytes):
        self.d, self.i = data, 0

    def take(self, n: int) -> bytes:
        if n < 0 or self.i + n > len(self.d):
            raise ValueError("level.dat truncated")
        b = self.d[self.i:self.i + n]
        self.i += n
        return b

    def unpack(self, fmt: str):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def string(self) -> str:
        return self.take(self.unpack("<H")).decode("utf-8", "replace")

    def payload(self, tag: int, depth: int = 0):
        if depth > 32:
            raise ValueError("level.dat nested too deep")
        if tag in _FIXED:
            return self.unpack(_FIXED[tag])
        if tag == _STRING:
            return self.string()
        if tag in (_BYTES, _INTS, _LONGS):
            n = self.unpack("<i")
            fmt = {_BYTES: "<b", _INTS: "<i", _LONGS: "<q"}[tag]
            return [self.unpack(fmt) for _ in range(n)]
        if tag == _LIST:
            inner, n = self.unpack("<b"), self.unpack("<i")
            return [self.payload(inner, depth + 1) for _ in range(n)]
        if tag == _COMPOUND:
            out = {}
            while (t := self.unpack("<b")) != _END:
                name = self.string()
                out[name] = self.payload(t, depth + 1)
            return out
        raise ValueError(f"unknown NBT tag {tag}")


def parse(data: bytes) -> dict:
    r = _Reader(data[8:])
    if r.unpack("<b") != _COMPOUND:
        raise ValueError("level.dat has no root compound")
    r.string()
    return r.payload(_COMPOUND)


def read_seed(world_dir: Path) -> int | None:
    path = world_dir / "level.dat"
    try:
        if path.stat().st_size > MAX_SIZE:
            return None
        seed = parse(path.read_bytes()).get("RandomSeed")
    except (OSError, ValueError, struct.error):
        return None
    return seed if isinstance(seed, int) else None
