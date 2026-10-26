import os
import struct
import tempfile
import unittest
from pathlib import Path

from app.adapters.bedrock import leveldat
from app.adapters.bedrock.files import ServerFiles


def _name(n):
    b = n.encode()
    return struct.pack("<H", len(b)) + b


def level_dat(seed):
    body = (b"\x0a" + _name("")
            + b"\x08" + _name("LevelName") + _name("Bedrock level")
            + b"\x09" + _name("experiments") + b"\x01" + struct.pack("<i", 2) + b"\x01\x00"
            + b"\x0a" + _name("abilities") + b"\x05" + _name("flySpeed") + struct.pack("<f", 0.05) + b"\x00"
            + b"\x04" + _name("RandomSeed") + struct.pack("<q", seed)
            + b"\x00")
    return struct.pack("<ii", 10, len(body)) + body


class LevelDatTest(unittest.TestCase):
    def test_seed_read_and_refreshed_when_world_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "server.properties").write_text("level-name=Testwelt\n")
            world = d / "worlds" / "Testwelt"
            world.mkdir(parents=True)
            files = ServerFiles(tmp)
            self.assertIsNone(files.seed(), "no level.dat yet")
            (world / "level.dat").write_bytes(level_dat(-2687023903840621904))
            self.assertEqual(files.seed(), -2687023903840621904)
            (world / "level.dat").write_bytes(level_dat(42))
            os.utime(world / "level.dat", ns=(1, 1))
            self.assertEqual(files.seed(), 42)

    def test_broken_file_gives_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "level.dat").write_bytes(level_dat(7)[:30])
            self.assertIsNone(leveldat.read_seed(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
