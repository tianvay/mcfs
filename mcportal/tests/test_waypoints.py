import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from app.adapters.bedrock.logparse import parse_journal_line
from app.services.waypoints import WaypointsService


def warp(ts, payload):
    return parse_journal_line(f"{ts} mcserver bedrock_server[1]: [2026-10-26 09:30:00:000 WARN] "
                              f"[Scripting] [mcportal-warp] {json.dumps({'v': 1, **payload}, ensure_ascii=False)}")


LIST = {"event": "list", "waypoints": [
    {"name": "Zuhause", "owner": "Steve", "dim": "minecraft:overworld", "x": -2, "y": 71, "z": -4,
     "public": False, "physical": True, "created": "2026-10-26T08:00:00Z"},
    {"name": "Dorf", "owner": "Steve", "dim": "minecraft:overworld", "x": -297, "y": 76, "z": -264,
     "public": True, "physical": True, "created": "2026-10-26T08:10:00Z"},
    {"name": "Markt", "owner": "Alex", "dim": "minecraft:nether", "x": 1.5, "y": 64, "z": 2,
     "public": False, "physical": False, "created": "2026-10-26T08:20:00Z"},
]}


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


class WaypointsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def service(self, lines):
        mc = FakeMc()
        s = WaypointsService(FakeAdapter(lines), mc, self.dir)
        asyncio.run(s.startup())
        return s, mc

    @staticmethod
    def feed(mc, *lines):
        for l in lines:
            for fn in mc.line_listeners:
                fn(l)

    def test_list_per_owner_including_private(self):
        s, mc = self.service([])
        self.feed(mc, warp(100.0, LIST))
        sm = s.summary()
        self.assertEqual(sm["total"], 3)
        self.assertEqual([w["name"] for w in sm["players"]["Steve"]], ["Dorf", "Zuhause"])
        self.assertFalse(sm["players"]["Alex"][0]["public"], "admin view shows private waypoints too")

    def test_travels_follow_renames_and_survive_restart(self):
        lines = [
            warp(100.0, LIST),
            warp(110.0, {"event": "teleport", "player": "Steve", "name": "Dorf"}),
            warp(120.0, {"event": "teleport", "player": "Alex", "name": "Dorf"}),
            warp(130.0, {"event": "renamed", "player": "Steve", "from": "Dorf", "name": "Dorfplatz"}),
            warp(131.0, {"event": "list", "waypoints": [{**LIST["waypoints"][1], "name": "Dorfplatz"}]}),
        ]
        s, mc = self.service([])
        self.feed(mc, *lines)
        w = s.summary()["players"]["Steve"][0]
        self.assertEqual((w["name"], w["travels"], w["travelers"]), ("Dorfplatz", 2, {"Steve": 1, "Alex": 1}))

        # portal restart: catch-up sees everything again - nothing counted twice
        s2, mc2 = self.service(lines)
        self.assertEqual(s2.summary()["players"]["Steve"][0]["travels"], 2)

    def test_deleted_waypoint_loses_its_travel_count(self):
        s, mc = self.service([])
        self.feed(mc, warp(100.0, LIST),
                  warp(110.0, {"event": "teleport", "player": "Steve", "name": "Zuhause"}),
                  warp(120.0, {"event": "deleted", "player": "Steve", "name": "Zuhause"}),
                  warp(121.0, {"event": "list", "waypoints": LIST["waypoints"][1:]}))
        names = [w["name"] for w in s.summary()["players"]["Steve"]]
        self.assertEqual(names, ["Dorf"])
        self.assertNotIn("zuhause", s.data["travels"])


if __name__ == "__main__":
    unittest.main()
