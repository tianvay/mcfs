import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from app.adapters.bedrock import commands
from app.adapters.bedrock.logparse import parse_journal_line, parse_shop
from app.services.minecraft import PortalError
from app.services.sterntaler import SterntalerService, seed_plan


def shop(ts, payload):
    return parse_journal_line(f"{ts} mcserver bedrock_server[1]: [2026-11-11 15:00:00:000 WARN] "
                              f"[Scripting] [mcportal-shop] {json.dumps({'v': 1, **payload}, ensure_ascii=False)}")


ITEMS = [{"id": "mcfs:bergbrecher", "name": "Bergbrecher", "price": 20, "desc": "3 × 3 × 3"},
         {"id": "mcfs:holzfaeller", "name": "Holzfäller-Axt", "price": 15, "desc": "ganzer Baum"}]
CATALOG = {"event": "catalog", "currency": "Sterntaler", "items": ITEMS, "rewards": {"participation": 5, "star": 1}}
HISTORY = [
    {"type": "storm", "ended": 50.0, "participants": ["Steve", "Alex"]},
    {"type": "bounty", "ended": 80.0, "participants": ["Steve", "bad;name"]},
    {"type": "meteor", "ended": 500.0, "participants": ["Steve", "Sunny"]},   # after the shop started
]


def booking(ts, player, delta, reason, balance, earned, detail=None):
    return shop(ts, {"event": "booking", "player": player, "delta": delta, "reason": reason,
                     **({"detail": detail} if detail else {}), "balance": balance, "earned": earned})


class FakeMc:
    def __init__(self, status="online"):
        self.line_listeners, self.extras, self.status, self.unit = [], {}, status, None

    def publish(self):
        pass

    def status_word(self):
        return self.status


class FakeAdapter:
    def __init__(self, lines, console=True):
        self.lines, self.console, self.sent = lines, console, []

    def read_log(self, since=None):
        return [l for l in self.lines if since is None or l.ts >= since]

    def console_available(self):
        return self.console

    def shop_grant_live(self, name, amount):
        self.sent.append(commands.shop_grant(name, amount))

    def shop_seed_live(self, name, amount):
        self.sent.append(commands.shop_seed(name, amount))


class Audit:
    def __init__(self):
        self.entries = []

    def write(self, action, result, user, **kw):
        self.entries.append((action, result, kw))


class SterntalerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def service(self, lines=(), status="online", console=True, history=HISTORY):
        mc, adapter, audit = FakeMc(status), FakeAdapter(list(lines), console), Audit()
        s = SterntalerService(adapter, mc, audit, self.dir, lambda: history)
        asyncio.run(s.startup())
        return s, mc, adapter, audit

    def feed(self, mc, lines):
        for l in lines:
            for fn in mc.line_listeners:
                fn(l)

    def test_parse_only_own_tag(self):
        self.assertEqual(parse_shop(shop(1.0, {"started": True})), {"v": 1, "started": True})
        other = parse_journal_line('1.0 h bedrock_server[1]: [x WARN] [Scripting] [mcportal-events] {"v":1,"event":"state"}')
        self.assertIsNone(parse_shop(other))

    def test_not_installed(self):
        s, _, adapter, _ = self.service()
        out = s.summary(admin=True)
        self.assertFalse(out["installed"])
        self.assertEqual(out["players"], [])
        self.assertEqual(adapter.sent, [], "no start credit before the pack is there")

    def test_bookings_balances_and_purchases(self):
        s, mc, _, _ = self.service()
        self.feed(mc, [
            shop(100.0, CATALOG), shop(100.0, {"event": "balances", "players": {}}), shop(100.0, {"started": True}),
            booking(110.0, "Steve", 5, "participation", 5, 5, "storm"),
            booking(110.0, "Alex", 5, "participation", 5, 5, "storm"),
            booking(120.0, "Steve", 20, "admin", 25, 5),
            booking(130.0, "Steve", -20, "buy", 5, 5, "mcfs:bergbrecher"),
            booking(140.0, "Steve", 1, "star", 6, 6),
        ])
        out = s.summary()
        self.assertTrue(out["installed"])
        self.assertEqual([p["name"] for p in out["players"]], ["Steve", "Alex"], "richest first")
        steve = out["players"][0]
        self.assertEqual((steve["balance"], steve["earned"], steve["spent"]), (6, 6, 20))
        self.assertEqual(steve["bought"], {"mcfs:bergbrecher": 1})
        self.assertEqual(out["items"][0]["icon"], "/api/features/icons/mcfs.bergbrecher.png")
        self.assertEqual(out["rewards"]["participation"], 5)
        self.assertNotIn("ledger", out, "the ledger is for the admin only")
        ledger = s.summary(admin=True)["ledger"]
        self.assertEqual(len(ledger), 5)
        self.assertEqual((ledger[0]["player"], ledger[0]["reason"], ledger[0]["delta"]), ("Steve", "star", 1))
        self.assertEqual(ledger[1]["detail"], "mcfs:bergbrecher")

    def test_no_double_counting_across_a_portal_restart(self):
        lines = [shop(100.0, CATALOG), shop(100.0, {"started": True}),
                 booking(110.0, "Steve", 5, "participation", 5, 5, "storm"),
                 booking(130.0, "Steve", -5, "buy", 0, 5, "mcfs:x")]
        s, mc, _, _ = self.service()
        self.feed(mc, lines)
        new = booking(150.0, "Steve", -5, "buy", 0, 10, "mcfs:x")
        s2, mc2, _, _ = self.service(lines + [new])     # catch-up sees everything again
        self.feed(mc2, [new])                           # ... and the live stream the newest line once more
        steve = s2.summary()["players"][0]
        self.assertEqual(steve["spent"], 10)
        self.assertEqual(len(s2.summary(admin=True)["ledger"]), 3)

    def test_first_start_reads_the_current_server_run(self):
        class Unit:
            active_state, started_at = "active", 90.0

        mc, adapter = FakeMc(), FakeAdapter([shop(100.0, CATALOG), shop(100.0, {"started": True}),
                                             shop(100.0, {"event": "balances", "players": {"Alex": {"balance": 7, "earned": 9}}})])
        mc.unit = Unit()
        s = SterntalerService(adapter, mc, Audit(), self.dir, lambda: [])
        asyncio.run(s.startup())
        out = s.summary()
        self.assertTrue(out["installed"])
        self.assertEqual(out["players"][0], {"name": "Alex", "balance": 7, "earned": 9, "spent": 0, "bought": {}})

    def test_balances_line_corrects_what_the_portal_missed(self):
        s, mc, _, _ = self.service()
        self.feed(mc, [shop(100.0, {"started": True}), booking(110.0, "Steve", 5, "participation", 5, 5),
                       shop(900.0, {"event": "balances", "players": {"Steve": {"balance": 12, "earned": 17}}})])
        steve = s.summary()["players"][0]
        self.assertEqual((steve["balance"], steve["earned"]), (12, 17))

    def test_seed_plan(self):
        self.assertEqual(seed_plan(HISTORY, 100.0), {"Steve": 10, "Alex": 5})
        self.assertEqual(seed_plan(HISTORY, 1000.0), {"Steve": 15, "Alex": 5, "Sunny": 5})
        self.assertEqual(seed_plan([], 100.0), {})
        many = [{"ended": 1.0, "participants": ["Steve"]}] * 300
        self.assertEqual(seed_plan(many, 2.0), {"Steve": commands.SHOP_GRANT_MAX})

    def test_start_credit_is_sent_once_and_confirmed(self):
        s, mc, adapter, _ = self.service()
        self.feed(mc, [shop(100.0, CATALOG), shop(100.0, {"started": True})])
        out = s.summary(admin=True)   # asking for the page sends what is open
        self.assertEqual(sorted(adapter.sent), ["scriptevent mcfs:shop seed 10 Steve", "scriptevent mcfs:shop seed 5 Alex"])
        self.assertEqual(out["seed"]["planned"], {"Steve": 10, "Alex": 5})
        s.summary()
        self.assertEqual(len(adapter.sent), 2, "not again within a minute")
        self.feed(mc, [booking(101.0, "Steve", 10, "seed", 10, 10), shop(101.0, {"event": "seed_skipped", "player": "Alex"})])
        s._last_seed_try = 0
        s.summary()
        self.assertEqual(len(adapter.sent), 2, "confirmed - nothing left to send")
        self.assertEqual(s.summary(admin=True)["seed"]["pending"], [])
        # a later start of the pack does not plan again
        self.feed(mc, [shop(5000.0, {"started": True})])
        self.assertEqual(s.summary(admin=True)["seed"]["planned"], {"Steve": 10, "Alex": 5})

    def test_start_credit_waits_for_the_server(self):
        s, mc, adapter, _ = self.service(status="offline")
        self.feed(mc, [shop(100.0, {"started": True})])
        s.summary()
        self.assertEqual(adapter.sent, [])
        mc.status = "online"
        s.summary()
        self.assertEqual(len(adapter.sent), 2)
        s._last_seed_try = 0
        s.summary()
        self.assertEqual(len(adapter.sent), 4, "unconfirmed ones are asked again - the pack books only once")

    def test_grant(self):
        s, mc, adapter, audit = self.service()
        self.feed(mc, [shop(100.0, {"started": True})])
        s.data["seed"]["plan"] = {}
        asyncio.run(s.grant("Sunny Day", -5, "admin"))
        asyncio.run(s.grant("Steve", 25, "admin"))
        self.assertEqual(adapter.sent, ["scriptevent mcfs:shop grant -5 Sunny Day", "scriptevent mcfs:shop grant 25 Steve"])
        self.assertEqual(audit.entries[-1], ("STERNTALER", "SUCCESS", {"player": "Steve", "value": 25}))

    def test_grant_refuses(self):
        s, mc, adapter, _ = self.service()
        for player, amount in [("Steve", 0), ("Steve", 1000), ("Steve", -1000), ("Steve", 1.5), ("Steve", True),
                               ("@a", 5), ("Steve; op Steve", 5), ("", 5)]:
            with self.assertRaises(PortalError, msg=f"{player} {amount}"):
                asyncio.run(s.grant(player, amount, "admin"))
        with self.assertRaises(PortalError) as cm:
            asyncio.run(s.grant("Steve", 5, "admin"))
        self.assertEqual(cm.exception.status, 409, "pack not seen yet")
        self.feed(mc, [shop(100.0, {"started": True})])
        mc.status = "offline"
        with self.assertRaises(PortalError):
            asyncio.run(s.grant("Steve", 5, "admin"))
        mc.status, adapter.console = "online", False
        with self.assertRaises(PortalError):
            asyncio.run(s.grant("Steve", 5, "admin"))
        self.assertEqual([c for c in adapter.sent if " grant " in c], [])

    def test_commands_are_fixed(self):
        self.assertEqual(commands.shop_grant("Steve", -3), "scriptevent mcfs:shop grant -3 Steve")
        self.assertEqual(commands.shop_seed("Sunny Day#12", 40), "scriptevent mcfs:shop seed 40 Sunny Day#12")
        for bad in [("Steve", 0), ("Steve", 1000), ("Steve\nop Steve", 5), ("@a", 5), ("Steve", "5")]:
            with self.assertRaises(ValueError):
                commands.shop_grant(*bad)
        for bad in [("Steve", 0), ("Steve", -5), ("x y;z", 5)]:
            with self.assertRaises(ValueError):
                commands.shop_seed(*bad)


if __name__ == "__main__":
    unittest.main()
