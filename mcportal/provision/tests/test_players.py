"""python -m unittest discover -s provision/tests"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import players as P  # noqa: E402

STEVE = {"ignoresPlayerLimit": False, "name": "Steve", "xuid": "2535400000000001"}
ALEX = {"ignoresPlayerLimit": False, "name": "Alex", "xuid": "2535400000000002"}
SUNNY = {"ignoresPlayerLimit": False, "name": "Sunny"}  # added by name, never joined yet


class CheckTest(unittest.TestCase):
    def test_valid_entries_are_normalised(self):
        self.assertEqual(P.check_allowlist([{"name": "Steve", "xuid": 2535400000000001}]), [STEVE])
        self.assertEqual(P.check_allowlist([{"name": "Sunny", "xuid": ""}]), [SUNNY])
        self.assertEqual(P.check_permissions([{"permission": "operator", "xuid": "2535400000000001", "x": 1}]),
                         [{"permission": "operator", "xuid": "2535400000000001"}])

    def test_bad_entries_are_refused(self):
        for bad in [[{"name": ""}], [{"name": "a;rm -rf /"}], [{"name": "Steve", "xuid": "12ab"}], ["Steve"], [{}]]:
            with self.assertRaises(P.PlayersError, msg=bad):
                P.check_allowlist(bad)
        for bad in [[{"permission": "admin", "xuid": "1"}], [{"permission": "operator"}], [{"permission": "member",
                                                                                              "xuid": "x"}]]:
            with self.assertRaises(P.PlayersError, msg=bad):
                P.check_permissions(bad)


class MergeTest(unittest.TestCase):
    def test_source_wins_target_kept(self):
        target = [dict(ALEX, ignoresPlayerLimit=True), SUNNY]
        source = [STEVE, ALEX, {"ignoresPlayerLimit": False, "name": "sunny", "xuid": "2535400000000003"}]
        merged = P.merge_allowlist(target, source)
        self.assertEqual([e["name"] for e in merged], ["Steve", "Alex", "sunny"], "no duplicates by XUID or name")
        self.assertFalse(merged[1]["ignoresPlayerLimit"], "source wins")
        self.assertEqual(P.merge_allowlist([SUNNY], [STEVE]), [SUNNY, STEVE], "target entries stay")

    def test_permissions(self):
        target = [{"permission": "member", "xuid": "1"}, {"permission": "operator", "xuid": "2"}]
        source = [{"permission": "operator", "xuid": "1"}]
        self.assertEqual(P.merge_permissions(target, source),
                         [{"permission": "operator", "xuid": "2"}, {"permission": "operator", "xuid": "1"}])


class ImportTest(unittest.TestCase):
    def test_import_writes_server_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp, "old"), Path(tmp, "new")
            src.mkdir(), dst.mkdir()
            (src / "allowlist.json").write_text(json.dumps([STEVE, ALEX]))
            (src / "permissions.json").write_text('[{"permission":"operator","xuid":"2535400000000001"}]')
            (dst / "allowlist.json").write_text("[]\n")   # fresh from Mojang's zip
            (dst / "permissions.json").write_text("[]\n")
            counts = P.import_players(src, dst)
            self.assertEqual(counts, {"from_allowlist": 2, "from_operators": 1, "kept": 0, "allowlist": 2,
                                      "operators": 1})
            self.assertNotIn(" ", (dst / "allowlist.json").read_text(), "compact like the server")
            self.assertIn('"permission" : "operator"', (dst / "permissions.json").read_text())
            self.assertEqual(P.import_players(src, dst)["allowlist"], 2, "running twice changes nothing")

    def test_allowlist_only_keeps_operators_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp, "old"), Path(tmp, "new")
            src.mkdir(), dst.mkdir()
            (src / "allowlist.json").write_text(json.dumps([STEVE, ALEX]))
            (src / "permissions.json").write_text('[{"permission":"operator","xuid":"2535400000000001"}]')
            (dst / "allowlist.json").write_text("[]\n")
            (dst / "permissions.json").write_text("[]\n")
            counts = P.import_players(src, dst, operators=False)
            self.assertEqual((counts["allowlist"], counts["from_operators"], counts["operators"]), (2, 0, 0))
            self.assertEqual(json.loads((dst / "permissions.json").read_text()), [])
            self.assertEqual(P.main(["players.py", "import", str(src), str(dst), "--allowlist-only"]), 0)
            self.assertEqual(P.main(["players.py", "import", str(src), str(dst), "--everything"]), 2)

    def test_broken_source_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp, "old"), Path(tmp, "new")
            src.mkdir(), dst.mkdir()
            (src / "allowlist.json").write_text("[{")
            (dst / "allowlist.json").write_text("[]")
            with self.assertRaises(P.PlayersError):
                P.import_players(src, dst)
            self.assertEqual((dst / "allowlist.json").read_text(), "[]")


if __name__ == "__main__":
    unittest.main()
