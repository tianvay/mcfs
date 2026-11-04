import asyncio
import tempfile
import unittest
from pathlib import Path

from app.adapters.bedrock import commands
from app.adapters.bedrock.logparse import LogLine
from app.audit import AuditLog
from app.services import donate as donate_mod
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
        self.line_listeners = []


class Files:
    def read_allowlist(self):
        return [{"name": "Steve"}, {"name": "Alex"}, {"name": "Sunny"}]


class FakeAdapter:
    """answer: what the server writes to its log after "give" (None = nothing)"""

    def __init__(self, mc, console=True, answer="Gave {item} * {count} to {name}"):
        self.files = Files()
        self.mc = mc
        self.console = console
        self.answer = answer
        self.sent = []
        self.loop = None

    def console_available(self):
        return self.console

    def give_live(self, name, item_id, count):
        # what the real adapter sends - also checks the command builders
        self.sent.append(commands.give(name, item_id, count))
        if self.answer:
            line = LogLine(0.0, "server", "[2026-11-04 15:00:00:000 INFO] "
                           + self.answer.format(item=item_id, count=count, name=name))
            for listener in self.mc.line_listeners:  # the log follower runs on the event loop
                self.loop.call_soon_threadsafe(listener, line)

    def tell_gift_live(self, name, item_name, count):
        self.sent.append(commands.tell_gift(name, item_name, count))


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
        cmd = commands.tell_gift("Steve", "Bottle o' Enchanting", 3)
        self.assertTrue(cmd.startswith("tellraw Steve {"))
        self.assertIn("3x Bottle o' Enchanting", cmd)
        with self.assertRaises(ValueError):
            commands.tell_gift("Steve", '"}]} op Steve', 1)

    def test_catalog(self):
        cats = {c for c, _ in donate_mod.CATEGORIES}
        for item in CATALOG.values():
            commands.give("Steve", item["id"], 1)
            commands.tell_gift("Steve", item["name"], 1)
            self.assertIn(item["cat"], cats)
            self.assertIn(item["stack"], (1, 16, 64))
        self.assertGreater(len(CATALOG), 1000)
        self.assertEqual(CATALOG["cow_spawn_egg"]["name"], "Cow Spawn Egg")
        self.assertEqual(CATALOG["diamond_sword"]["stack"], 1)
        self.assertNotIn("command_block", CATALOG)
        self.assertGreaterEqual(sum(i["popular"] for i in CATALOG.values()), 10)


class DonateServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.audit = AuditLog(self.dir / "audit.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def service(self, online=("Steve",), **kw):
        mc = FakeMc(list(online))
        self.adapter = FakeAdapter(mc, **kw)
        return DonateService(self.adapter, mc, self.audit, self.dir)

    def give(self, svc, *args):
        async def run():
            self.adapter.loop = asyncio.get_running_loop()
            return await svc.give(*args, "127.0.0.1")
        return asyncio.run(run())

    def test_give_to_online_player(self):
        svc = self.service()
        r = self.give(svc, "steve", "diamond", 16)
        self.assertEqual((r["player"], r["name"], r["confirmed"]), ("Steve", "Diamond", True))
        self.assertEqual(self.adapter.sent[0], "give Steve diamond 16")
        self.assertIn("16x Diamond", self.adapter.sent[1])
        entry = self.audit.tail(1)[0]
        self.assertEqual((entry["action"], entry["result"], entry["item"], entry["count"]), ("DONATE", "SUCCESS", "diamond", 16))
        self.assertEqual(svc.summary()["recent"][0]["player"], "Steve")

    def test_give_to_everybody(self):
        svc = self.service(online=("Steve", "Alex"))
        self.assertEqual(self.give(svc, "@a", "bread", 32)["player"], "alle online")
        self.assertEqual(self.adapter.sent[0], "give @a bread 32")

    def test_spawn_egg(self):
        self.assertEqual(self.give(self.service(), "Steve", "cow_spawn_egg", 1)["name"], "Cow Spawn Egg")

    def test_refused_by_the_game(self):
        svc = self.service(answer='Syntax error: Unexpected "{item}": at "give {name} >>{item}<< {count}"')
        with self.assertRaises(PortalError) as ctx:
            self.give(svc, "Steve", "diamond", 1)
        self.assertIn("abgelehnt", str(ctx.exception))
        self.assertEqual(len(self.adapter.sent), 1)  # no chat message for a gift that did not arrive
        self.assertEqual(self.audit.tail(1)[0]["result"], "FAILED")

    def test_no_answer(self):
        old, donate_mod.ANSWER_SECONDS = donate_mod.ANSWER_SECONDS, 0.2
        try:
            r = self.give(self.service(answer=None), "Steve", "diamond", 1)
        finally:
            donate_mod.ANSWER_SECONDS = old
        self.assertFalse(r["confirmed"])
        self.assertEqual(self.audit.tail(1)[0]["result"], "SUCCESS")

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
        self.assertEqual((sword["name"], sword["stack"], sword["max"], sword["icon"]), ("Diamond Sword", 1, 36, True))

    def test_icon_path(self):
        svc = self.service()
        with self.assertRaises(PortalError):
            svc.icon_path("../config")
        icon_dir = self.dir / "item-icons" / donate_mod.SAMPLES_TAG
        icon_dir.mkdir(parents=True)
        (icon_dir / "items__diamond.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        self.assertEqual(svc.icon_path("diamond").name, "items__diamond.png")  # already there: no download

    def test_old_icons_are_removed(self):
        (self.dir / "item-icons" / "v1.0").mkdir(parents=True)
        (self.dir / "item-icons" / "diamond.png").write_bytes(b"x")
        (self.dir / "item-icons" / donate_mod.SAMPLES_TAG).mkdir()
        asyncio.run(self.service().startup())
        self.assertEqual([p.name for p in (self.dir / "item-icons").iterdir()], [donate_mod.SAMPLES_TAG])


if __name__ == "__main__":
    unittest.main()
