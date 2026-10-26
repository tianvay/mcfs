"""Read-only reader for the world database (Mojang's LevelDB variant), pure Python.

Only used on a snapshot copy of the world, never on the live directory. Differences to plain LevelDB:
blocks are compressed with zlib (2) or raw deflate (4) instead of snappy. Keys are compared bytewise.

iterate(db) yields (key, value) of all live keys in ascending key order, newest version only,
streaming block by block so memory stays small even for large worlds.
"""
from __future__ import annotations

import heapq
import struct
import zlib
from collections.abc import Iterator
from pathlib import Path

TYPE_DELETION, TYPE_VALUE = 0, 1
LOG_BLOCK = 32768


class CorruptDatabase(ValueError):
    pass


def _varint(b: bytes, i: int) -> tuple[int, int]:
    r = s = 0
    while True:
        if i >= len(b) or s > 63:
            raise CorruptDatabase("varint out of range")
        c = b[i]
        i += 1
        r |= (c & 0x7F) << s
        s += 7
        if c < 0x80:
            return r, i


def _decompress(raw: bytes, kind: int) -> bytes:
    if kind == 0:
        return raw
    if kind == 2:
        return zlib.decompress(raw)
    if kind == 4:
        return zlib.decompress(raw, -15)
    raise CorruptDatabase(f"unknown block compression {kind}")


def _block_entries(data: bytes) -> Iterator[tuple[bytes, bytes]]:
    if len(data) < 4:
        raise CorruptDatabase("block too short")
    restarts = struct.unpack_from("<I", data, len(data) - 4)[0]
    end = len(data) - 4 - 4 * restarts
    i, key = 0, b""
    while i < end:
        shared, i = _varint(data, i)
        own, i = _varint(data, i)
        vlen, i = _varint(data, i)
        key = key[:shared] + data[i:i + own]
        i += own
        yield key, data[i:i + vlen]
        i += vlen


def _read_block(f, handle: bytes) -> bytes:
    off, j = _varint(handle, 0)
    size, _ = _varint(handle, j)
    f.seek(off)
    raw = f.read(size + 5)  # + compression type + crc
    if len(raw) != size + 5:
        raise CorruptDatabase("block truncated")
    return _decompress(raw[:size], raw[size])


def _table(path: Path) -> Iterator[tuple[bytes, int, int, bytes]]:
    """(user_key, sequence, type, value) of one .ldb table, in table order."""
    with open(path, "rb") as f:
        f.seek(-48, 2)
        footer = f.read(48)
        _, i = _varint(footer, 0)
        _, i = _varint(footer, i)  # metaindex handle (not needed)
        index = _read_block(f, footer[i:])
        for _, handle in _block_entries(index):
            for k, v in _block_entries(_read_block(f, handle)):
                tag = struct.unpack("<Q", k[-8:])[0]
                yield k[:-8], tag >> 8, tag & 0xFF, v


def _log_records(path: Path) -> Iterator[bytes]:
    data = path.read_bytes()
    i, frag = 0, b""
    while i + 7 <= len(data):
        left = LOG_BLOCK - i % LOG_BLOCK
        if left < 7:
            i += left
            continue
        length, kind = struct.unpack_from("<HB", data, i + 4)
        payload = data[i + 7:i + 7 + length]
        i += 7 + length
        if kind == 1:
            yield payload
        elif kind == 2:
            frag = payload
        elif kind == 3:
            frag += payload
        elif kind == 4:
            yield frag + payload
            frag = b""


def _log(path: Path) -> list[tuple[bytes, int, int, bytes]]:
    out = []
    for rec in _log_records(path):
        if len(rec) < 12:
            continue
        seq, count = struct.unpack_from("<QI", rec, 0)
        i = 12
        for n in range(count):
            kind = rec[i]
            i += 1
            klen, i = _varint(rec, i)
            key = rec[i:i + klen]
            i += klen
            value = b""
            if kind == TYPE_VALUE:
                vlen, i = _varint(rec, i)
                value = rec[i:i + vlen]
                i += vlen
            out.append((key, seq + n, kind, value))
    return out


def live_files(db: Path) -> tuple[set[int], int]:
    """Table numbers listed in the current MANIFEST and the current log number."""
    current = (db / "CURRENT").read_text(encoding="ascii").strip()
    if "/" in current or not current.startswith("MANIFEST-"):
        raise CorruptDatabase("unexpected CURRENT")
    tables: set[int] = set()
    log_no = 0
    for rec in _log_records(db / current):
        i = 0
        while i < len(rec):
            tag, i = _varint(rec, i)
            if tag == 1:  # comparator
                n, i = _varint(rec, i)
                i += n
            elif tag in (2, 3, 4, 9):  # log, next file, last sequence, previous log
                v, i = _varint(rec, i)
                if tag == 2:
                    log_no = v
            elif tag == 5:  # compact pointer
                _, i = _varint(rec, i)
                n, i = _varint(rec, i)
                i += n
            elif tag == 6:  # deleted file
                _, i = _varint(rec, i)
                n, i = _varint(rec, i)
                tables.discard(n)
            elif tag == 7:  # new file
                _, i = _varint(rec, i)
                n, i = _varint(rec, i)
                _, i = _varint(rec, i)
                for _ in range(2):
                    m, i = _varint(rec, i)
                    i += m
                tables.add(n)
            else:
                raise CorruptDatabase(f"unknown manifest tag {tag}")
    return tables, log_no


def iterate(db: Path) -> Iterator[tuple[bytes, bytes]]:
    tables, log_no = live_files(db)
    sources: list = []
    for n in sorted(tables):
        path = db / f"{n:06d}.ldb"
        if not path.exists():
            raise CorruptDatabase(f"missing table {path.name}")
        sources.append(_table(path))
    for path in sorted(db.glob("*.log")):
        if path.stem.isdigit() and int(path.stem) >= log_no:
            sources.append(iter(sorted(_log(path), key=lambda e: (e[0], -e[1]))))
    last = None
    for key, _, kind, value in heapq.merge(*sources, key=lambda e: (e[0], -e[1])):
        if key == last:
            continue  # older version
        last = key
        if kind == TYPE_VALUE:
            yield key, value
