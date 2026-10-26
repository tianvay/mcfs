import os
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from app.adapters.bedrock.release import ReleaseError, release_from_url, stage, version_key

GOOD_URL = "https://www.minecraft.net/bedrockdedicatedserver/bin-linux/bedrock-server-1.26.52.3.zip"


def make_zip(path: Path, members: dict[str, bytes], exec_names=("bedrock_server",), links=()):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            info = zipfile.ZipInfo(name)
            mode = 0o755 if name in exec_names or name.endswith("/") else 0o644
            if name.endswith("/"):
                mode |= stat.S_IFDIR
            info.external_attr = (stat.S_IFREG | mode if not name.endswith("/") else mode) << 16
            zf.writestr(info, data)
        for name in links:
            info = zipfile.ZipInfo(name)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, "/etc/passwd")


SERVER = {
    "bedrock_server": b"\x7fELF fake",
    "server.properties": b"server-name=Dedicated Server\n",
    "allowlist.json": b"[]",
    "permissions.json": b"[]",
    "behavior_packs/": b"",
    "behavior_packs/vanilla/manifest.json": b"{}",
    "resource_packs/": b"",
    "resource_packs/vanilla/manifest.json": b"{}",
}


class UrlTest(unittest.TestCase):
    def test_good(self):
        r = release_from_url(GOOD_URL)
        self.assertEqual(r.version, "1.26.52.3")

    def test_rejected(self):
        for bad in [
            GOOD_URL.replace("https", "http"),
            GOOD_URL.replace("www.minecraft.net", "evil.example"),
            GOOD_URL.replace("bin-linux", "bin-linux-preview"),
            GOOD_URL.replace("bin-linux", "bin-win"),
            GOOD_URL.replace("1.26.52.3.zip", "latest.zip"),
        ]:
            with self.assertRaises(ReleaseError, msg=bad):
                release_from_url(bad)

    def test_version_order(self):
        self.assertGreater(version_key("1.26.52.3"), version_key("1.26.51.1"))
        self.assertGreater(version_key("1.26.100.1"), version_key("1.26.99.9"))


class StageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_good_zip(self):
        z = self.d / "ok.zip"
        make_zip(z, SERVER)
        stage(z, self.d / "out")
        self.assertEqual((self.d / "out/server.properties").read_bytes(), SERVER["server.properties"])
        if sys.platform != "win32":
            self.assertTrue(os.access(self.d / "out/bedrock_server", os.X_OK))
            self.assertEqual(stat.S_IMODE((self.d / "out/server.properties").stat().st_mode), 0o644)
            self.assertEqual(stat.S_IMODE((self.d / "out/behavior_packs").stat().st_mode), 0o755)

    def test_path_traversal(self):
        z = self.d / "evil.zip"
        make_zip(z, {**SERVER, "../outside.txt": b"x"})
        with self.assertRaises(ReleaseError):
            stage(z, self.d / "out")
        self.assertFalse((self.d / "outside.txt").exists())

    def test_absolute_path(self):
        z = self.d / "evil.zip"
        make_zip(z, {**SERVER, "/etc/cron.d/x": b"x"})
        with self.assertRaises(ReleaseError):
            stage(z, self.d / "out")

    def test_symlink(self):
        z = self.d / "link.zip"
        make_zip(z, SERVER, links=("bad_link",))
        with self.assertRaises(ReleaseError):
            stage(z, self.d / "out")

    def test_missing_server(self):
        z = self.d / "nope.zip"
        make_zip(z, {k: v for k, v in SERVER.items() if k != "bedrock_server"})
        with self.assertRaises(ReleaseError):
            stage(z, self.d / "out")

    def test_not_a_zip(self):
        z = self.d / "html.zip"
        z.write_bytes(b"<html>Access denied</html>")
        with self.assertRaises(ReleaseError):
            stage(z, self.d / "out")

    def test_corrupt_member(self):
        z = self.d / "corrupt.zip"
        make_zip(z, {**SERVER, "big.bin": b"A" * 5000})
        data = bytearray(z.read_bytes())
        i = data.find(b"A" * 100)
        data[i:i + 10] = b"B" * 10  # stored (uncompressed) -> CRC mismatch
        z.write_bytes(bytes(data))
        with self.assertRaises(ReleaseError):
            stage(z, self.d / "out")


if __name__ == "__main__":
    unittest.main()
