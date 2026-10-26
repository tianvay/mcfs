import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from app.adapters.bedrock import commands
from app.adapters.bedrock.logparse import parse_journal_line
from app.services.events import EventsService
from app.services.minecraft import PortalError


def ev(ts, payload):
    return parse_journal_line(f"{ts} mcserver bedrock_server[1]: [2026-10-26 15:00:00:000 WARN] "
                              f"[Scripting] [mcportal-events] {json.dumps({'v': 1, **payload})}")


STATE = {"event": "state", "auto": True, "online": 2, "active": [], "next_in": 120, "last": None,
         "register": 4, "types": ["storm", "mining_rush", "lucky_day"]}

LINES = [
    ev(100.0, STATE),
    ev(110.0, {"event": "started", "type": "storm", "by": "auto", "duration": 2400}),
    ev(110.0, {**STATE, "active": [{"type": "storm", "remaining": 2400, "total": 2400, "by": "auto"}]}),
    ev(120.0, {"event": "started", "type": "mining_rush", "by": "console", "duration": 7200}),
    ev(2510.0, {"event": "ended", "type": "storm", "by": "time", "ran": 2400, "participants": ["Alex", "Steve"]}),
    ev(2510.0, {**STATE, "active": [{"type": "mining_rush", "remaining": 4800, "total": 7200, "by": "console"}]}),
    ev(3000.0, {"event": "ended", "type": "mining_rush", "by": "console", "ran": 3000, "participants": ["Steve"]}),
]


class FakeMc:
    def __init__(self, status="online"):
        self.line_listeners, self.extras, self.status = [], {}, status

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

    def event_control_live(self, action, event_type=None):
        self.sent.append(commands.event_control(action, event_type))


class Audit:
    def __init__(self):
        self.entries = []

    def write(self, *a, **k):
        self.entries.append((a, k))


class EventsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def service(self, lines, mc=None, adapter=None):
        """service that has seen `lines` live (catch-up from the journal only happens after a restart)"""
        mc = mc or FakeMc()
        adapter = adapter or FakeAdapter(lines)
        s = EventsService(adapter, mc, Audit(), self.dir)
        asyncio.run(s.startup())
        self.feed(mc, *lines)
        return s, mc, adapter

    @staticmethod
    def feed(mc, *lines):
        for l in lines:
            for fn in mc.line_listeners:
                fn(l)

    def test_state_history_and_participations(self):
        s, mc, _ = self.service([])
        self.feed(mc, *LINES[:4])
        sm = s.summary()
        self.assertEqual([a["type"] for a in sm["active"]], ["storm"])
        self.assertEqual(sm["active"][0]["started"], 110.0)
        self.assertEqual(mc.extras["events"]()["active"], ["storm"])
        self.feed(mc, *LINES[4:])
        sm = s.summary()
        self.assertEqual(sm["active"], [])
        self.assertEqual([h["type"] for h in sm["history"]], ["mining_rush", "storm"], "newest first")
        storm = sm["history"][1]
        self.assertEqual((storm["started"], storm["by"], storm["stopped_by"]), (110.0, "auto", "time"))
        self.assertEqual(sm["participations"], {"Steve": 2, "Alex": 1})
        self.assertEqual(sm["types"], ["storm", "mining_rush", "lucky_day"])

    def test_portal_restart_counts_nothing_twice(self):
        self.service(LINES)
        mc2 = FakeMc()
        s2 = EventsService(FakeAdapter(LINES), mc2, Audit(), self.dir)  # restart: catch-up reads everything again
        asyncio.run(s2.startup())
        self.assertEqual(len(s2.summary()["history"]), 2)
        self.assertEqual(s2.summary()["participations"], {"Steve": 2, "Alex": 1})

    def test_control_sends_only_fixed_commands(self):
        s, mc, adapter = self.service(LINES)
        asyncio.run(s.control("start", "lucky_day", "admin"))
        asyncio.run(s.control("auto_off", None, "admin"))
        self.assertEqual(adapter.sent, ["scriptevent mcfs:event start lucky_day", "scriptevent mcfs:event auto off"])
        for action, etype in [("start", "meteor"), ("start", "storm; stop"), ("explode", None), ("stop", None)]:
            with self.assertRaises(PortalError):
                asyncio.run(s.control(action, etype, "admin"))
        with self.assertRaises(ValueError):
            commands.event_control("start", "storm\nstop")

    def test_control_needs_a_running_server_and_the_pack(self):
        s, _, _ = self.service([])
        with self.assertRaises(PortalError):
            asyncio.run(s.control("start", "storm", "admin"))  # pack never reported
        s2, _, _ = self.service(LINES, mc=FakeMc("offline"))
        with self.assertRaises(PortalError):
            asyncio.run(s2.control("start", "storm", "admin"))

    def test_weather_and_time_only_fixed_values(self):
        s, mc, adapter = self.service(LINES)
        sent = []
        adapter.world_control_live = lambda kind, value: sent.append(commands.world_control(kind, value))
        asyncio.run(s.world("weather", "thunder", "admin"))
        asyncio.run(s.world("time", "midnight", "admin"))
        self.assertEqual(sent, ["weather thunder", "time set 18000"])
        for kind, value in [("weather", "snow"), ("time", "25000"), ("time", "set 0"), ("gamerule", "x"),
                            ("weather", "clear; op Steve")]:
            with self.assertRaises(PortalError):
                asyncio.run(s.world(kind, value, "admin"))
        mc.status = "offline"
        with self.assertRaises(PortalError):
            asyncio.run(s.world("weather", "clear", "admin"))

    def test_night_and_boss_events_can_be_started(self):
        s, _, adapter = self.service(LINES)
        for t in ("blood_moon", "zombie_invasion", "bounty"):
            asyncio.run(s.control("start", t, "admin"))
        self.assertEqual(adapter.sent[-1], "scriptevent mcfs:event start bounty")

    def test_build_register_sync_sends_only_new_chunks_in_batches(self):
        s, mc, adapter = self.service(LINES)
        sent = []
        adapter.event_register_live = lambda keys: sent.append(commands.event_register(keys))
        f = self.dir / "built_chunks.json"
        f.write_text(json.dumps({"chunks": [f"o{i},0" for i in range(250)]}))
        self.assertEqual(s.sync_register(f), 250)
        self.assertEqual(len(sent), 3, "100 + 100 + 50")
        self.assertTrue(sent[0].startswith("scriptevent mcfs:event register o0,0;o1,0;"))
        f.write_text(json.dumps({"chunks": [f"o{i},0" for i in range(252)]}))
        self.assertEqual(s.sync_register(f), 2, "only the new ones")
        self.assertEqual(sent[-1], "scriptevent mcfs:event register o250,0;o251,0")
        mc.status = "offline"
        f.write_text(json.dumps({"chunks": ["o999,9"]}))
        self.assertEqual(s.sync_register(f), 0, "server offline: next render tries again")
        mc.status = "online"
        self.assertEqual(s.sync_register(f), 1)
        with self.assertRaises(ValueError):
            commands.event_register(["o1,2;start storm"])

    def test_summary_asks_for_fresh_state_at_most_every_30_seconds(self):
        s, _, adapter = self.service(LINES)
        s.summary()
        s.summary()
        self.assertEqual(adapter.sent, ["scriptevent mcfs:event state"])


if __name__ == "__main__":
    unittest.main()
