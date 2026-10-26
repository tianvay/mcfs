import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from app.adapters.bedrock.logparse import parse_achievements, parse_journal_line
from app.services.achievements import AchievementsService


def ach_line(ts, payload):
    return parse_journal_line(f"{ts} mcserver bedrock_server[1]: [2026-10-26 07:00:00:000 WARN] "
                              f"[Scripting] [mcportal-ach] {json.dumps(payload, ensure_ascii=False)}")


CATALOG = [
    {"id": "diamonds", "tier": 1, "tiers": 2, "group": "Bergbau", "name": "Diamant!", "desc": "Den ersten Diamanten gefunden"},
    {"id": "diamonds", "tier": 2, "tiers": 2, "group": "Bergbau", "name": "Diamantenfieber", "desc": "50 Diamanten gefunden"},
    {"id": "deaths", "tier": 1, "tiers": 1, "group": "Missgeschicke", "name": "Anfängerfehler", "desc": "Zum ersten Mal gestorben"},
]


class FakeMc:
    def __init__(self):
        self.line_listeners, self.extras = [], {}

    def publish(self):
        pass


class FakeAdapter:
    def __init__(self, lines):
        self.lines = lines

    def read_log(self, since=None):
        return [l for l in self.lines if since is None or l.ts >= since]


class AchievementsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def service(self, lines):
        mc = FakeMc()
        s = AchievementsService(FakeAdapter(lines), mc, self.dir)
        asyncio.run(s.startup())
        return s, mc

    def test_parse_only_own_tag(self):
        self.assertEqual(parse_achievements(ach_line(1.0, {"v": 1, "started": True})), {"v": 1, "started": True})
        stats = parse_journal_line('1.0 h bedrock_server[1]: [x WARN] [Scripting] [mcportal-stats] {"v":2,"started":true}')
        self.assertIsNone(parse_achievements(stats))

    def test_unlocks_and_no_duplicates_across_restart(self):
        lines = [
            ach_line(100.0, {"v": 1, "catalog": CATALOG}),
            ach_line(110.0, {"v": 1, "unlocked": [{"player": "Steve", "id": "diamonds", "tier": 1, "name": "Diamant!"}]}),
            ach_line(120.0, {"v": 1, "unlocked": [{"player": "Alex", "id": "deaths", "tier": 1, "name": "Anfängerfehler"}]}),
        ]
        s, mc = self.service([])
        for l in lines:
            for fn in mc.line_listeners:
                fn(l)
        summary = s.summary()
        self.assertEqual(summary["total"], 3)
        self.assertEqual([u["name"] for u in summary["players"]["Steve"]], ["Diamant!"])
        self.assertEqual(summary["recent"][0]["player"], "Alex")

        # restart: catch-up sees all lines again plus a new tier
        new = ach_line(130.0, {"v": 1, "unlocked": [{"player": "Steve", "id": "diamonds", "tier": 2, "name": "Diamantenfieber"}]})
        s2, mc2 = self.service(lines + [new])
        for fn in mc2.line_listeners:
            fn(new)
        steve = s2.summary()["players"]["Steve"]
        self.assertEqual([u["name"] for u in steve], ["Diamantenfieber", "Diamant!"])  # newest first
        self.assertEqual(steve[1]["at"], 110.0, "first unlock time is kept")
        self.assertEqual(steve[0]["desc"], "50 Diamanten gefunden", "description comes from the catalog")


if __name__ == "__main__":
    unittest.main()
