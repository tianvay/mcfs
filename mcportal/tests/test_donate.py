import asyncio
import tempfile
import unittest
from pathlib import Path

from app.adapters.bedrock import commands
from app.audit import AuditLog
from app.services.donate import CATALOG, DonateService
from app.services.minecraft import PortalError


class Player:
    def __init__(self, name):
        self.name = name


class Tracker:
    def __init__(self, names):
        self.players = {n.lower(): Player(n) for n in names}


class FakeMc:
    def __init__(self, names):
        self.tracker = Tracker(names)


class Files:
    def read_allowlist(self):
        return [{"name": "Steve"}, {"name": "Alex"}, {"name": "Sunny"}]


class FakeAdapter:
    def __init__(self, console=True):
        self.files = Files()
        self.console = console
        self.sent = []

    def console_available(self):
        return self.console

    def give_live(self, name, item_id, count, item_name):
        # what the real adapter sends - also checks the command builders
        self.sent.append((commands.give(name, item_id, count), commands.tell_gift(name, item_name, count)))


class CommandsTest(unittest.TestCase):
    def test_give(self):
        self.assertEqual(commands.give("Steve", "diamond", 16), "give Steve diamond 16")
        self.assertEqual(commands.give("Big Steve", "torch", 64), 'give "Big Steve" torch 64')
        self.assertEqual(commands.give("@a", "bread", 5), "give @a bread 5")

    def test_give_refuses_bad_input(self):
        for args in [("Steve", "diamond 64 0\nstop", 1), ("Steve", "Diamond", 1), ("Steve", "diamond", 0),
                     ("Steve", "diamond", 1000), ("@s", "diamond", 1), ("Steve;op", "diamond", 1)]:
            with self.assertRaises(ValueError, msg=args):
                commands.give(*args)

    def test_tell_gift(self):
        cmd = commands.tell_gift("Steve", "Goldener Apfel", 3)
        self.assertTrue(cmd.startswith("tellraw Steve {"))
        self.assertIn("3x Goldener Apfel", cmd)
        with self.assertRaises(ValueError):
            commands.tell_gift("Steve", '"}]} op Steve', 1)

    def test_every_catalog_entry_builds(self):
        for item in CATALOG.values():
            commands.give("Steve", item["id"], 1)
            commands.tell_gift("Steve", item["name"], 1)
            self.assertTrue(item["texture"].startswith(("items/", "blocks/")))


class DonateServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.audit = AuditLog(self.dir / "audit.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def service(self, online=("Steve",), console=True):
        self.adapter = FakeAdapter(console)
        return DonateService(self.adapter, FakeMc(list(online)), self.audit, self.dir)

    def give(self, svc, *args):
        return asyncio.run(svc.give(*args, "127.0.0.1"))

    def test_give_to_online_player(self):
        svc = self.service()
        r = self.give(svc, "steve", "diamond", 16)
        self.assertEqual(r["player"], "Steve")
        self.assertEqual(self.adapter.sent[0][0], "give Steve diamond 16")
        entry = self.audit.tail(1)[0]
        self.assertEqual((entry["action"], entry["result"], entry["item"], entry["count"]), ("DONATE", "SUCCESS", "diamond", 16))
        self.assertEqual(svc.summary()["recent"][0]["player"], "Steve")

    def test_give_to_everybody(self):
        svc = self.service(online=("Steve", "Alex"))
        self.assertEqual(self.give(svc, "@a", "bread", 32)["player"], "alle online")
        self.assertEqual(self.adapter.sent[0][0], "give @a bread 32")

    def test_refusals(self):
        svc = self.service()
        cases = [("Alex", "diamond", 1),          # offline
                 ("Steve", "command_block", 1),   # not in the catalog
                 ("Steve", "diamond_sword", 37),  # more than a full inventory of swords
                 ("Steve", "diamond", 0)]
        for args in cases:
            with self.assertRaises(PortalError, msg=args):
                self.give(svc, *args)
        self.assertEqual(self.adapter.sent, [])
        with self.assertRaises(PortalError):
            self.give(self.service(online=()), "@a", "diamond", 1)
        with self.assertRaises(PortalError):
            self.give(self.service(console=False), "Steve", "diamond", 1)

    def test_summary(self):
        s = self.service(online=("Steve",)).summary()
        self.assertEqual(s["online"], ["Steve"])
        self.assertEqual(s["offline"], ["Alex", "Sunny"])
        sword = next(i for i in s["items"] if i["id"] == "diamond_sword")
        self.assertEqual((sword["stack"], sword["max"], sword["icon"]), (1, 36, False))
        self.assertTrue(any(i["popular"] for i in s["items"]))

    def test_icon_path(self):
        svc = self.service()
        with self.assertRaises(PortalError):
            svc.icon_path("../config")
        with self.assertRaises(PortalError):
            svc.icon_path("diamond")  # not downloaded yet
        (self.dir / "item-icons").mkdir()
        (self.dir / "item-icons" / "diamond.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        self.assertEqual(svc.icon_path("diamond").name, "diamond.png")


if __name__ == "__main__":
    unittest.main()
