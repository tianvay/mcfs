import json
import tempfile
import unittest
from pathlib import Path

from app.adapters.bedrock.files import ServerFiles

# permissions.json exactly as the Bedrock server writes it
ORIGINAL = """[
   {
      "permission" : "operator",
      "xuid" : "2535400000000001"
   },
   {
      "permission" : "operator",
      "xuid" : "2535400000000002"
   }
]"""


class PermissionsFileTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        d = Path(self.dir.name)
        (d / "permissions.json").write_text(ORIGINAL, encoding="utf-8")
        (d / "allowlist.json").write_text("[]", encoding="utf-8")
        self.files = ServerFiles(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def test_roundtrip_keeps_server_layout(self):
        self.files.write_permissions(self.files.read_permissions())
        self.assertEqual(self.files.permissions.read_text(encoding="utf-8"), ORIGINAL)

    def test_operator_xuids(self):
        self.assertEqual(self.files.operator_xuids(), {"2535400000000001", "2535400000000002"})
        self.files.write_permissions([{"permission": "member", "xuid": "2535400000000001"}])
        self.assertEqual(self.files.operator_xuids(), set())
        self.assertEqual(json.loads(self.files.permissions.read_text()), [{"permission": "member", "xuid": "2535400000000001"}])


if __name__ == "__main__":
    unittest.main()
