"""Chunks of a Bedrock world: grouping database keys, heightmap and sub-chunk block palettes.

Chunk keys: x(int32) z(int32) [dimension(int32), only Nether/End] tag(byte) [sub-chunk y(int8)].
"""
from __future__ import annotations

import struct
from array import array
from collections.abc import Iterator
from dataclasses import dataclass, field

from ..adapters.bedrock.leveldat import _COMPOUND, _Reader
from .leveldb import iterate

TAG_DATA3D = 0x2B      # heightmap (256 x int16) + biomes
TAG_SUBCHUNK = 0x2F    # 16 x 16 x 16 blocks
DIMENSIONS = {0: "overworld", 1: "nether", 2: "the_end"}
MIN_Y = {0: -64, 1: 0, 2: 0}
AIR = "minecraft:air"


@dataclass
class Chunk:
    dim: int
    x: int
    z: int
    heightmap: tuple[int, ...] | None = None
    raw_subchunks: dict[int, bytes] = field(default_factory=dict)
    _decoded: dict[int, "SubChunk | None"] = field(default_factory=dict)

    def subchunk(self, sy: int) -> "SubChunk | None":
        if sy not in self._decoded:
            raw = self.raw_subchunks.get(sy)
            try:
                self._decoded[sy] = SubChunk.parse(raw) if raw else None
            except (ValueError, IndexError, struct.error):
                self._decoded[sy] = None
        return self._decoded[sy]

    def block(self, x: int, y: int, z: int) -> str:
        sc = self.subchunk(y >> 4)
        return sc.block(x, y & 15, z) if sc else AIR

    def top_y(self, x: int, z: int) -> int | None:
        """Highest block (overworld/end heightmap), absolute y."""
        if not self.heightmap:
            return None
        return self.heightmap[z * 16 + x] + MIN_Y[self.dim] - 1


class SubChunk:
    __slots__ = ("indices", "palette")

    def __init__(self, indices, palette: list[str]):
        self.indices = indices
        self.palette = palette

    def block(self, x: int, y: int, z: int) -> str:
        return self.palette[self.indices[(x << 8) | (z << 4) | y]]

    @classmethod
    def parse(cls, v: bytes) -> "SubChunk | None":
        """First block storage of a version 8/9 sub-chunk (the second one only holds water in blocks)."""
        version = v[0]
        if version not in (8, 9):
            return None
        i = 3 if version == 9 else 2  # version, storage count, [y index]
        header = v[i]
        i += 1
        bits = header >> 1
        if bits == 0:
            indices = bytes(4096)
            count = 1
        else:
            per = 32 // bits
            nwords = -(-4096 // per)
            words = array("I")
            words.frombytes(v[i:i + nwords * 4])
            if words.itemsize != 4 or len(words) != nwords:
                raise ValueError("sub-chunk truncated")
            i += nwords * 4
            mask = (1 << bits) - 1
            # block n lives in word n // per at bit (n % per) * bits
            out = [0] * (nwords * per)
            for slot in range(per):
                s = slot * bits
                out[slot::per] = [(w >> s) & mask for w in words]
            indices = out[:4096]
            count = struct.unpack_from("<i", v, i)[0]
            i += 4
        r = _Reader(v[i:])
        palette = []
        for _ in range(count):
            if r.unpack("<b") != _COMPOUND:
                raise ValueError("palette entry is no compound")
            r.string()
            palette.append(str(r.payload(_COMPOUND).get("name", AIR)))
        if max(indices) >= len(palette):
            raise ValueError("palette index out of range")
        return cls(indices, palette)


def chunks(db) -> Iterator[Chunk]:
    """All chunks having a heightmap or sub-chunks, grouped from the sorted key stream."""
    current: Chunk | None = None
    for key, value in iterate(db):
        n = len(key)
        if n in (9, 10):
            dim, tag = 0, key[8]
        elif n in (13, 14):
            dim, tag = struct.unpack_from("<i", key, 8)[0], key[12]
        else:
            continue
        if tag not in (TAG_DATA3D, TAG_SUBCHUNK) or dim not in DIMENSIONS:
            continue
        if (tag == TAG_SUBCHUNK) != (n in (10, 14)):
            continue
        x, z = struct.unpack_from("<ii", key, 0)
        if current is None or (current.dim, current.x, current.z) != (dim, x, z):
            if current is not None:
                yield current
            current = Chunk(dim, x, z)
        if tag == TAG_DATA3D:
            if len(value) >= 512:
                current.heightmap = struct.unpack_from("<256h", value, 0)
        else:
            current.raw_subchunks[struct.unpack("<b", key[-1:])[0]] = value
    if current is not None:
        yield current
