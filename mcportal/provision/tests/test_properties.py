"""python -m unittest discover -s provision/tests"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import properties as P  # noqa: E402

EXAMPLE = (HERE.parent / "server.conf.example").read_text(encoding="utf-8")
OVERRIDES = (HERE.parent / "server.properties.overrides").read_text(encoding="utf-8")
UNIT = (HERE.parent / "minecraft-bedrock.service.in").read_text(encoding="utf-8")

MOJANG = """# comment from Mojang
server-name=Dedicated Server
# Allowed values: "survival", "creative", or "adventure"
gamemode=survival
allow-cheats=false
level-name=Bedrock level
level-seed=
content-log-console-output-enabled=false
content-log-level=info
texturepack-required=false
"""


class ConfTest(unittest.TestCase):
    def test_example_is_valid(self):
        conf = P.read_conf(EXAMPLE)
        self.assertEqual(conf["MC_DIR"], "/opt/minecraft/bedrock")
        self.assertEqual(conf["LEVEL_SEED"], "")

    def test_bad_values_are_refused(self):
        for bad in ["SERVER_NAME=a\x00b", "WORLD_NAME=../etc", "MC_DIR=/opt", "MC_DIR=/opt/../etc", "PORT_V4=80",
                    "DIFFICULTY=hardcore", "MC_USER=Root Admin", "MAX_PLAYERS=0", "SERVER_NAME=x;rm -rf /",
                    "UNKNOWN=1", "SERVER_NAME"]:
            text = "\n".join(l for l in EXAMPLE.splitlines() if not l.startswith(bad.split("=")[0] + "=")) + "\n" + bad
            with self.assertRaises(P.ConfError, msg=bad):
                P.read_conf(text)
        with self.assertRaises(P.ConfError):
            P.read_conf(EXAMPLE.replace("PORT_V6=19133", "PORT_V6=19132"))
        with self.assertRaises(P.ConfError):
            P.read_conf(EXAMPLE.replace("MAX_PLAYERS=10\n", ""))


class MergeTest(unittest.TestCase):
    def test_overrides_go_into_mojangs_file(self):
        conf = P.read_conf(EXAMPLE.replace("SERVER_NAME=Family Server", "SERVER_NAME=Familie Muster"))
        out = P.merge(MOJANG, P.parse_overrides(P.render(OVERRIDES, conf)))
        self.assertIn("server-name=Familie Muster\n", out)
        self.assertIn("allow-cheats=true\n", out)
        self.assertIn("content-log-level=warning\n", out)
        self.assertIn("texturepack-required=true\n", out)
        self.assertIn('# Allowed values: "survival"', out, "Mojang's comments stay")
        self.assertEqual(out.count("allow-cheats="), 1, "replaced, not duplicated")
        self.assertLess(out.index("server-name="), out.index("gamemode="), "order stays")
        self.assertIn("# added by provision/setup.sh\ndifficulty=easy\nmax-players=10", out,
                      "keys Mojang's file doesn't have are appended")

    def test_unit_template(self):
        conf = P.read_conf(EXAMPLE)
        unit = P.render(UNIT, conf)
        self.assertIn("User=minecraft\n", unit)
        self.assertIn("ExecStart=/opt/minecraft/bedrock/bedrock_server\n", unit)
        self.assertIn("ReadWritePaths=/opt/minecraft/bedrock\n", unit)
        self.assertNotIn("@", unit.replace("# Bedrock Dedicated Server - main unit, rendered by provision/setup.sh "
                                           "(@MC_USER@, @MC_DIR@ from server.conf).", ""))
        with self.assertRaises(P.ConfError):
            P.render("User=@MC_USR@", conf)


if __name__ == "__main__":
    unittest.main()
