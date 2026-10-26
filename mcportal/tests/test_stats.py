import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from app.adapters.bedrock.logparse import parse_journal_line, parse_stats
from app.services.stats import StatsService

# real format of the pack's output in the journal (seen on the test server)
STARTED = '100.0 mcserver bedrock_server[1]: [2026-10-25 21:11:44:572 WARN] [Scripting] [mcportal-stats] {"v":1,"started":true}'


def stats_line(ts, players):
    return parse_journal_line(f"{ts} mcserver bedrock_server[1]: [2026-10-25 21:12:00:000 WARN] "
                              f"[Scripting] [mcportal-stats] {json.dumps({'v': 1, 'players': players})}")


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


class StatsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def service(self, lines):
        mc = FakeMc()
        s = StatsService(FakeAdapter(lines), mc, self.dir)
        asyncio.run(s.startup())
        return s, mc

    def test_parse(self):
        self.assertEqual(parse_stats(parse_journal_line(STARTED)), {"v": 1, "started": True})
        self.assertIsNone(parse_stats(parse_journal_line("1.0 h bedrock_server[1]: [x INFO] Player connected: a, xuid: 1")))
        self.assertIsNone(parse_stats(parse_journal_line("1.0 h bedrock_server[1]: [2026-10-25 21:12:00:000 WARN] [Scripting] [mcportal-stats] {kaputt")))

    def test_sums_and_no_double_counting_across_restart(self):
        l1 = stats_line(101.0, {"Steve": {"placed": {"minecraft:stone": 3}, "broken": {"minecraft:dirt": 2}}})
        l2 = stats_line(121.0, {"Steve": {"placed": {"minecraft:stone": 2}, "broken": {}},
                                "Alex": {"placed": {}, "broken": {"minecraft:dirt": 5}}})
        s, mc = self.service([])
        for l in (parse_journal_line(STARTED), l1, l2):
            for fn in mc.line_listeners:
                fn(l)
        self.assertEqual(s.summary()["players"][0]["name"], "Steve")
        t = {p["name"]: p for p in s.summary()["players"]}
        self.assertEqual((t["Steve"]["placed"], t["Steve"]["broken"]), (5, 2))
        self.assertEqual(t["Alex"]["broken"], 5)

        # portal restart: catch-up reads the same lines again plus one new one -> only the new one counts
        l3 = stats_line(141.0, {"Steve": {"placed": {"minecraft:glass": 1}, "broken": {}}})
        s2, mc2 = self.service([parse_journal_line(STARTED), l1, l2, l3])
        for fn in mc2.line_listeners:
            fn(l3)  # also arrives live - must not count twice
        t = {p["name"]: p for p in s2.summary()["players"]}
        self.assertEqual(t["Steve"]["placed"], 6)
        self.assertEqual(tuple(t["Steve"]["top_placed"][0]), ("minecraft:stone", 5))

    def test_same_timestamp_different_lines(self):
        a = stats_line(200.0, {"a": {"placed": {"minecraft:stone": 1}, "broken": {}}})
        b = stats_line(200.0, {"b": {"placed": {"minecraft:stone": 1}, "broken": {}}})
        s, mc = self.service([])
        for l in (a, b, a):
            for fn in mc.line_listeners:
                fn(l)
        self.assertEqual(sorted(p["name"] for p in s.summary()["players"]), ["a", "b"])
        self.assertEqual(sum(p["placed"] for p in s.summary()["players"]), 2)


if __name__ == "__main__":
    unittest.main()
