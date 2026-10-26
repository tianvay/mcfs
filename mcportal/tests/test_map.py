import asyncio
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from app.adapters.bedrock.logparse import LogLine, parse_save_files
from app.map import leveldb
from app.map.chunk import SubChunk, chunks
from app.map.render import render
from app.services.map import MapService
from app.services.minecraft import PortalError


# ---------- a tiny LevelDB writer, just enough for the reader ----------

def varint(n):
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def block(entries):
    data = b"".join(varint(0) + varint(len(k)) + varint(len(v)) + k + v for k, v in entries)
    return data + struct.pack("<I", 0) + struct.pack("<I", 1)


def write_table(path, entries, compression=2):
    """entries: [(user_key, seq, type, value)] - sorted here like LevelDB (key asc, seq desc)."""
    entries = sorted(entries, key=lambda e: (e[0], -e[1]))
    internal = [(k + struct.pack("<Q", seq << 8 | t), v) for k, seq, t, v in entries]
    raw = block(internal)
    body = zlib.compress(raw) if compression == 2 else zlib.compress(raw)[2:-4]
    data = body + bytes([compression]) + b"\0\0\0\0"
    handle = varint(0) + varint(len(body))
    index = block([(internal[-1][0], handle)])
    index_off = len(data)
    data += index + b"\0" + b"\0\0\0\0"
    footer = varint(0) + varint(0) + varint(index_off) + varint(len(index))
    footer = footer.ljust(40, b"\0") + struct.pack("<Q", 0xDB4775248B80FB57)
    path.write_bytes(data + footer)


def log_file(records):
    out = b""
    for rec in records:
        out += b"\0\0\0\0" + struct.pack("<HB", len(rec), 1) + rec
    return out


def batch(seq, ops):
    rec = struct.pack("<QI", seq, len(ops))
    for kind, k, v in ops:
        rec += bytes([kind]) + varint(len(k)) + k + (varint(len(v)) + v if kind == 1 else b"")
    return rec


def nbt_name(name):
    b = name.encode()
    return b"\x0a" + struct.pack("<H", 0) + b"\x08" + struct.pack("<H", 4) + b"name" + struct.pack("<H", len(b)) + b + b"\x00"


def subchunk(blocks, palette):
    """blocks: {(x, y, z): palette index}; bits = 2."""
    bits, per = 2, 16
    words = [0] * (4096 // per)
    for (x, y, z), p in blocks.items():
        i = (x << 8) | (z << 4) | y
        words[i // per] |= p << ((i % per) * bits)
    return (bytes([8, 1, bits << 1]) + struct.pack(f"<{len(words)}I", *words)
            + struct.pack("<i", len(palette)) + b"".join(nbt_name(n) for n in palette))


def chunk_key(x, z, tag, dim=0, sy=None):
    k = struct.pack("<ii", x, z) + (struct.pack("<i", dim) if dim else b"") + bytes([tag])
    return k + (struct.pack("<b", sy) if sy is not None else b"")


def make_world(root: Path):
    """One overworld chunk at (0,0): grass at y=64 everywhere, a stone pillar at x=3,z=3 up to y=66,
    water (2 deep) at x=8,z=8. Chunk (1,0) only in the log, deleted chunk (5,5) is not drawn."""
    db = root / "db"
    db.mkdir(parents=True)
    pal = ["minecraft:air", "minecraft:grass_block", "minecraft:stone", "minecraft:water"]
    blocks = {(x, 0, z): 1 for x in range(16) for z in range(16)}  # y = 64 -> sub-chunk 4, local 0
    blocks.update({(3, 1, 3): 2, (3, 2, 3): 2})
    blocks.update({(8, 0, 8): 3, (8, 1, 8): 3})
    del blocks[(8, 0, 8)]
    blocks[(8, 0, 8)] = 3
    heights = [65 + 64] * 256
    heights[3 * 16 + 3] = 67 + 64
    heights[8 * 16 + 8] = 66 + 64
    hm = struct.pack("<256h", *heights) + b"\0" * 10
    write_table(db / "000005.ldb", [
        (chunk_key(0, 0, 0x2B), 1, 1, hm),
        (chunk_key(0, 0, 0x2F, sy=4), 2, 1, subchunk({(x, 0, z): 1 for x in range(16) for z in range(16)}, pal)),
        (chunk_key(0, 0, 0x2F, sy=4), 3, 1, subchunk(blocks, pal)),           # newer version wins
        (chunk_key(5, 5, 0x2B), 4, 1, hm),
        (b"~local_player", 5, 1, b"x"),
        (chunk_key(0, 0, 0x2B, dim=1), 6, 1, hm),                               # Nether: not drawn
    ], compression=4)
    (db / "000006.log").write_bytes(log_file([
        batch(10, [(1, chunk_key(1, 0, 0x2B), hm),
                   (1, chunk_key(1, 0, 0x2F, sy=4), subchunk({(0, 0, 0): 2, (5, 1, 5): 3},
                                                              ["minecraft:air", "minecraft:grass_block", "minecraft:stone", "minecraft:oak_planks"])),
                   (0, chunk_key(5, 5, 0x2B), b"")]),
    ]))
    manifest = varint(1) + varint(26) + b"leveldb.BytewiseComparator" + varint(2) + varint(6)
    manifest += varint(7) + varint(0) + varint(5) + varint(100) + varint(1) + b"a" + varint(1) + b"z"
    (db / "MANIFEST-000004").write_bytes(log_file([manifest]))
    (db / "CURRENT").write_text("MANIFEST-000004\n")
    return db


class LevelDbTest(unittest.TestCase):
    def test_newest_version_wins_log_overrides_and_deletes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = make_world(Path(tmp))
            got = dict(leveldb.iterate(db))
            self.assertIn(chunk_key(1, 0, 0x2B), got, "entry from the log")
            self.assertNotIn(chunk_key(5, 5, 0x2B), got, "deleted in the log")
            self.assertEqual(list(got), sorted(got), "ascending key order")
            sc = SubChunk.parse(got[chunk_key(0, 0, 0x2F, sy=4)])
            self.assertEqual(sc.block(3, 2, 3), "minecraft:stone", "newer sub-chunk version")
            found = [(c.dim, c.x, c.z) for c in chunks(db)]
            self.assertEqual(found, [(0, 0, 0), (0, 1, 0)], "no Nether chunks")

    def test_subchunk_decoding_matches_direct_formula(self):
        pal = ["minecraft:air", "a", "b", "c"]
        blocks = {(x, y, z): (x + 2 * y + 3 * z) % 4 for x in range(16) for y in range(16) for z in range(16)}
        sc = SubChunk.parse(subchunk(blocks, pal))
        for (x, y, z), p in list(blocks.items())[::97]:
            self.assertEqual(sc.block(x, y, z), pal[p])


class RenderTest(unittest.TestCase):
    def test_tiles_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            world = Path(tmp) / "snap"
            make_world(world)
            out = Path(tmp) / "map"
            out.mkdir()
            index = render(world, out)
            build = out / index["build"]
            self.assertEqual(json.loads((out / "current.json").read_text())["build"], index["build"])
            ow = index["dims"]["overworld"]
            self.assertEqual(ow["chunks"], 2)
            self.assertEqual(ow["bounds"], [0, 0, 31, 15])
            self.assertEqual(ow["tiles"]["0"], [[0, 0]])
            # chunk (1,0) has a plank block near the surface -> built; (0,0) only grass, stone, water
            built = json.loads((out / "built_chunks.json").read_text())["chunks"]
            self.assertEqual(built, ["o1,0"])
            self.assertEqual(index["built_chunks"], 1)
            png = (build / "overworld" / "0" / "0_0.png").read_bytes()
            self.assertTrue(png.startswith(b"\x89PNG"))
            # second render replaces the first build
            index2 = render(world, out)
            self.assertEqual(sorted(p.name for p in out.glob("build-*")), [index2["build"]])

    def test_column_colours(self):
        from app.map.render import DimensionImage, Palette, draw_chunk, COLORS_FILE
        with tempfile.TemporaryDirectory() as tmp:
            db = make_world(Path(tmp))
            pal = Palette(json.loads(COLORS_FILE.read_text(encoding="utf-8")))
            img = DimensionImage()
            for c in chunks(db):
                draw_chunk(img, pal, c)
            pixels, heights = img.tiles[(0, 0)]
            px = lambda x, z: pixels[z * 256 + x] & 0xFFFFFF
            self.assertEqual(heights[3 * 256 + 3], 66, "stone pillar top")
            self.assertEqual(heights[0], 64)
            self.assertNotEqual(px(3, 3), px(0, 0), "stone differs from grass")
            r, g, b = px(8, 8) & 255, px(8, 8) >> 8 & 255, px(8, 8) >> 16
            self.assertGreater(b, r, "water is blue")


class SaveQueryTest(unittest.TestCase):
    def test_parse_file_list(self):
        line = LogLine(1.0, "server", "Bedrock level/db/000005.ldb:600, Bedrock level/db/CURRENT:16, Bedrock level/level.dat:3037")
        self.assertEqual(parse_save_files(line)[0], ("Bedrock level/db/000005.ldb", 600))
        self.assertEqual(len(parse_save_files(line)), 3)
        self.assertIsNone(parse_save_files(LogLine(1.0, "server", "[2026-10-26 11:52:50:422 INFO] Saving...")))
        self.assertIsNone(parse_save_files(LogLine(1.0, "server", "Steve, Alex")))


class FakeFiles:
    def __init__(self, world):
        self.world = world

    def world_dir(self):
        return self.world


class FakeMc:
    def __init__(self, active=True):
        self.line_listeners, self.extras, self.busy, self.active = [], {}, None, active

    def publish(self):
        pass

    def _is_active(self):
        return self.active

    def snapshot(self):
        return {"seed": "42"}


class ConsoleAdapter:
    """Answers "save query" like the server: first not ready, then the file list."""

    def __init__(self, world, mc, lines):
        self.files = FakeFiles(world)
        self.mc, self.lines, self.sent, self.queries = mc, lines, [], 0

    def console_available(self):
        return True

    def world_save_live(self, step):
        self.sent.append(step)
        if step == "query":
            self.queries += 1
            if self.queries < 2:
                return
            loop = self.mc.loop
            for text in self.lines:
                loop.call_soon_threadsafe(lambda t=text: [fn(LogLine(1.0, "server", t)) for fn in self.mc.line_listeners])


class Audit:
    def write(self, *a, **k):
        pass


class SnapshotTest(unittest.TestCase):
    def run_snapshot(self, lines):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        world = root / "worlds" / "Bedrock level"
        (world / "db").mkdir(parents=True)
        (world / "db" / "000005.ldb").write_bytes(b"0123456789")
        (world / "level.dat").write_bytes(b"L" * 20)
        mc = FakeMc()
        adapter = ConsoleAdapter(world, mc, lines)
        svc = MapService(adapter, mc, Audit(), root / "data")
        svc.dir.mkdir(parents=True)

        async def go():
            mc.loop = asyncio.get_running_loop()
            await svc._snapshot()

        return svc, adapter, go

    def test_copies_listed_lengths_and_always_resumes(self):
        svc, adapter, go = self.run_snapshot([
            "[2026-10-26 11:52:51:970 INFO] Data saved. Files are now ready to be copied.",
            "Bedrock level/db/000005.ldb:6, Bedrock level/level.dat:20",
        ])
        asyncio.run(go())
        self.assertEqual((svc.snapshot_dir / "db" / "000005.ldb").read_bytes(), b"012345", "truncated to listed length")
        self.assertEqual(adapter.sent[0], "hold")
        self.assertEqual(adapter.sent[-1], "resume")
        self.assertGreaterEqual(adapter.queries, 2, "asked again while the save was not ready")
        self.assertFalse(svc.hold_marker.exists())

    def test_path_outside_the_world_is_refused_and_resumed(self):
        svc, adapter, go = self.run_snapshot([
            "[2026-10-26 11:52:51:970 INFO] Data saved. Files are now ready to be copied.",
            "Bedrock level/../../etc/passwd:10",
        ])
        with self.assertRaises(PortalError):
            asyncio.run(go())
        self.assertEqual(adapter.sent[-1], "resume")
        self.assertFalse(svc.hold_marker.exists())

    def test_tile_names_are_validated(self):
        svc, _, _ = self.run_snapshot([])
        for args in [("build-20261026-115957", "overworld", "0", "../x.png"),
                     ("..", "overworld", "0", "0_0.png"),
                     ("build-20261026-115957", "etc", "0", "0_0.png")]:
            with self.assertRaises(PortalError):
                svc.tile_path(*args)


if __name__ == "__main__":
    unittest.main()


class NaturalTest(unittest.TestCase):
    def test_natural_and_built_blocks(self):
        from app.map.natural import is_natural
        for n in ["minecraft:grass_block", "minecraft:oak_log", "minecraft:birch_leaves", "minecraft:deepslate_iron_ore",
                  "minecraft:water", "minecraft:red_tulip", "minecraft:raw_copper_block", "minecraft:end_stone"]:
            self.assertTrue(is_natural(n), n)
        for n in ["minecraft:oak_planks", "minecraft:torch", "minecraft:chest", "minecraft:stripped_oak_log",
                  "minecraft:glass_pane", "minecraft:grass_path", "minecraft:farmland", "minecraft:something_new"]:
            self.assertFalse(is_natural(n), n)
