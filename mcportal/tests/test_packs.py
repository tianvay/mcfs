import asyncio
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from app.adapters.bedrock.files import ServerFiles
from app.adapters.bedrock.logparse import LogLine
from app.audit import AuditLog
from app.services.minecraft import PortalError
from app.services.packs import PacksService, custom_items, group_features, recipes

REPO_PACKS = Path(__file__).resolve().parents[1] / "minecraft-pack"
WAYPOINTS = "8c696d43-98da-4c6f-b1d2-1f5d6767d5de"


class Unit:
    def __init__(self, started_at):
        self.active_state = "active"
        self.started_at = started_at


class FakeMc:
    def __init__(self, started_at):
        self.unit = Unit(started_at)
        self.status = "online"
        self.op_lock = asyncio.Lock()
        self.busy = None
        self.line_listeners = []
        self.extras = {}
        self.published = 0

    def status_word(self):
        return self.status

    def publish(self):
        self.published += 1


class Adapter:
    def __init__(self, files, lines=()):
        self.files = files
        self.lines = list(lines)

    def read_log(self, since=None):
        return [l for l in self.lines if since is None or l.ts >= since]


def line(ts, msg):
    return LogLine(ts, "server", f"[2026-11-06 14:59:57:073 INFO] {msg}")


def make_world(root: Path) -> tuple[ServerFiles, dict]:
    """A server folder with the repo's packs in the world, all switched on (like setup.sh --install)."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "server.properties").write_text("level-name=FAF\n", encoding="utf-8")
    world = root / "worlds" / "FAF"
    lists = {"behavior": [], "resource": []}
    packs = {}
    for d in sorted(REPO_PACKS.iterdir()):
        m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        kind = "resource" if any(x["type"] == "resources" for x in m["modules"]) else "behavior"
        dst = world / f"{kind}_packs" / d.name
        shutil.copytree(d, dst, ignore=shutil.ignore_patterns("tests", "tools"))
        lists[kind].append({"pack_id": m["header"]["uuid"], "version": m["header"]["version"]})
        packs[d.name] = m["header"]
    for kind, entries in lists.items():
        (world / f"world_{kind}_packs.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return ServerFiles(str(root)), packs


def start_lines(ts, files):
    """What Bedrock logs at a start for the switched-on behavior packs."""
    out = [line(ts, "Version: 1.26.62.1")]
    by_uuid = {p["uuid"]: p for p in files.installed_packs()}
    for i, e in enumerate(files.read_world_packs("behavior")):
        p = by_uuid[e["pack_id"]]
        out.append(line(ts + 1, f"Pack Stack - [{i:02d}] {p['name']} (id: {p['uuid']}, version: "
                                f"{'.'.join(map(str, p['version']))}) @ worlds/FAF/behavior_packs/{p['folder']}"))
    out.append(line(ts + 2, "Server started."))
    return out


class GroupTest(unittest.TestCase):
    def test_features_from_dependencies(self):
        with tempfile.TemporaryDirectory() as d:
            files, _ = make_world(Path(d))
            features = {f["id"]: f for f in group_features(files.installed_packs())}
        self.assertEqual(set(features), {"mcportal_achievements", "mcportal_blueprint", "mcportal_events",
                                         "mcportal_spawntorch", "mcportal_stats", "mcportal_waypoints"},
                         "six switches - every resource pack belongs to its behavior pack")
        self.assertEqual([p["folder"] for p in features["mcportal_waypoints"]["packs"]],
                         ["mcportal_waypoints", "mcportal_waypoints_rp"])
        self.assertEqual(features["mcportal_waypoints"]["name"], "Wegpunkte")
        self.assertTrue(features["mcportal_blueprint"]["items"])
        self.assertTrue(features["mcportal_spawntorch"]["items"])
        self.assertFalse(features["mcportal_stats"]["items"])
        self.assertTrue(features["mcportal_events"]["entities"])
        self.assertFalse(features["mcportal_achievements"]["items"] or features["mcportal_achievements"]["entities"])

    def test_recipes_with_pictures(self):
        with tempfile.TemporaryDirectory() as d:
            files, _ = make_world(Path(d))
            packs = files.installed_packs()
            features = {f["id"]: f for f in group_features(packs)}
            wp = features["mcportal_waypoints"]["packs"]
            own = custom_items(wp)
            self.assertEqual(own["mcfs:waypoint"]["name"], "Wegpunkt")
            self.assertTrue(own["mcfs:waypoint"]["png"].is_file(), "picture from the resource pack")
            (r,) = recipes(wp, own)
            self.assertEqual(r["result"]["id"], "mcfs:waypoint")
            self.assertEqual(r["result"]["icon"], "/api/features/icons/mcfs.waypoint.png")
            self.assertEqual([[c["id"] for c in row] for row in r["grid"]], [
                ["minecraft:lantern", "minecraft:stone_brick_wall", "minecraft:lantern"],
                ["minecraft:stone_brick_wall", "minecraft:diamond_block", "minecraft:stone_brick_wall"],
                ["minecraft:lantern", "minecraft:stone_brick_wall", "minecraft:lantern"]])
            self.assertEqual(r["grid"][1][1]["name"], "Block of Diamond", "names like the Spenden tab")
            self.assertEqual(r["grid"][1][1]["icon"], "/api/donate/icons/diamond_block.png")
            bp = features["mcportal_blueprint"]["packs"]
            rs = recipes(bp, custom_items(bp))
            self.assertEqual({x["result"]["id"]: x["result"]["count"] for x in rs},
                             {"mcfs:blueprint": 1, "mcfs:blueprint_copy": 2})
            self.assertEqual(recipes(features["mcportal_stats"]["packs"], {}), [], "no own items, no recipes")

    def test_picture_outside_the_pack_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            files, _ = make_world(Path(d))
            rp = files.world_dir() / "resource_packs" / "mcportal_waypoints_rp" / "textures" / "item_texture.json"
            rp.write_text(json.dumps({"texture_data": {"mcfs_waypoint": {"textures": "../../../../../server.properties"}}}))
            wp = {f["id"]: f for f in group_features(files.installed_packs())}["mcportal_waypoints"]["packs"]
            self.assertIsNone(custom_items(wp)["mcfs:waypoint"]["png"])

    def test_resource_pack_without_behavior_pack_is_its_own_feature(self):
        packs = [{"path": Path("rp"), "folder": "rp", "kind": "resource", "uuid": "u1", "version": [1, 0, 0], "name": "Bilder",
                  "description": "", "depends": [], "items": False, "entities": False}]
        self.assertEqual([f["id"] for f in group_features(packs)], ["rp"])


class SwitchTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.files, self.packs = make_world(root / "server")
        self.started = time.time() - 600
        self.mc = FakeMc(self.started)
        self.adapter = Adapter(self.files, start_lines(self.started, self.files))
        self.audit = AuditLog(root / "data" / "audit.jsonl")
        self.svc = PacksService(self.adapter, self.mc, self.audit, root / "data", root / "backups")
        await self.svc.startup()
        self.root = root

    async def asyncTearDown(self):
        self.tmp.cleanup()

    def state(self, feature):
        return {f["id"]: f for f in self.svc.summary()["features"]}[feature]["state"]

    def restart(self):
        ts = time.time()
        self.mc.unit.started_at = ts
        for l in start_lines(ts, self.files):
            self.svc._on_line(l)

    async def test_public_shows_only_running_features_with_recipes(self):
        await self.svc.set_enabled("mcportal_blueprint", False, "admin")
        self.restart()
        pub = {f["id"]: f for f in self.svc.public()["features"]}
        self.assertNotIn("mcportal_blueprint", pub)
        self.assertIn("mcportal_stats", pub)
        self.assertEqual(set(pub["mcportal_spawntorch"]), {"id", "name", "description", "items", "entities", "recipes"},
                         "no versions, states or switches for everyone")
        self.assertEqual(pub["mcportal_spawntorch"]["recipes"][0]["result"]["name"], "Spawnfackel")
        self.assertTrue(self.svc.icon_path("mcfs.spawn_torch").is_file())
        for bad in ("mcfs.blueprint", "mcfs.nope", "../x", "mcfs:waypoint"):
            with self.assertRaises(PortalError, msg=bad):
                self.svc.icon_path(bad)
        json.dumps(self.svc.summary())   # admin view serialises (no paths left in it)

    async def test_all_on_after_install(self):
        s = self.svc.summary()
        self.assertTrue(s["running_known"])
        self.assertFalse(s["restart_needed"])
        self.assertEqual({f["state"] for f in s["features"]}, {"on"})
        self.assertEqual(self.svc.status_extra(), {"off": [], "restart_needed": False})

    async def test_switch_off_removes_both_packs_and_keeps_the_rest(self):
        before_bp = self.files.read_world_packs("behavior")
        await self.svc.set_enabled("mcportal_waypoints", False, "admin")
        bp = self.files.read_world_packs("behavior")
        rp = self.files.read_world_packs("resource")
        self.assertNotIn(WAYPOINTS, [e["pack_id"] for e in bp])
        self.assertNotIn(self.packs["mcportal_waypoints_rp"]["uuid"], [e["pack_id"] for e in rp])
        self.assertEqual(bp, [e for e in before_bp if e["pack_id"] != WAYPOINTS], "order of the others unchanged")
        self.assertTrue((self.files.world_dir() / "behavior_packs" / "mcportal_waypoints").is_dir(),
                        "the pack folder stays in the world")
        self.assertEqual(self.state("mcportal_waypoints"), "pending_off")
        self.assertTrue(self.svc.summary()["restart_needed"])
        self.assertEqual(self.svc.status_extra()["off"], [], "still running until the restart")
        self.restart()
        self.assertEqual(self.state("mcportal_waypoints"), "off")
        self.assertEqual(self.svc.status_extra(), {"off": ["mcportal_waypoints"], "restart_needed": False})
        self.assertFalse(self.svc.active("mcportal_waypoints"))
        entry = self.audit.tail(1)[0]
        self.assertEqual((entry["action"], entry["result"], entry["feature"]), ("PACK_OFF", "SUCCESS", "Wegpunkte"))

    async def test_switch_on_again(self):
        await self.svc.set_enabled("mcportal_events", False, "admin")
        self.restart()
        await self.svc.set_enabled("mcportal_events", True, "admin")
        self.assertEqual(self.state("mcportal_events"), "pending_on")
        bp = self.files.read_world_packs("behavior")
        self.assertIn({"pack_id": self.packs["mcportal_events"]["uuid"],
                       "version": self.packs["mcportal_events"]["version"]}, bp)
        self.restart()
        self.assertEqual(self.state("mcportal_events"), "on")
        self.assertTrue(self.svc.active("mcportal_events"))

    async def test_switching_twice_does_not_duplicate(self):
        await self.svc.set_enabled("mcportal_stats", True, "admin")
        await self.svc.set_enabled("mcportal_stats", True, "admin")
        ids = [e["pack_id"] for e in self.files.read_world_packs("behavior")]
        self.assertEqual(ids.count(self.packs["mcportal_stats"]["uuid"]), 1)

    async def test_vanilla_with_statistics_and_achievements(self):
        for f in ("mcportal_waypoints", "mcportal_events", "mcportal_spawntorch", "mcportal_blueprint"):
            await self.svc.set_enabled(f, False, "admin")
        self.restart()
        self.assertEqual(self.files.read_world_packs("resource"), [], "no resource packs = no extra items/looks")
        self.assertEqual({e["pack_id"] for e in self.files.read_world_packs("behavior")},
                         {self.packs["mcportal_stats"]["uuid"], self.packs["mcportal_achievements"]["uuid"]})
        self.assertFalse(self.svc.summary()["restart_needed"])

    async def test_failed_start_is_reported(self):
        # switched on before the last start, but the server did not load it
        self.svc.changed["mcportal_blueprint"] = self.started - 60
        self.svc.stack.discard(self.packs["mcportal_blueprint"]["uuid"])
        self.assertEqual(self.state("mcportal_blueprint"), "failed")
        self.assertIn("mcportal_blueprint", self.svc.status_extra()["off"])

    async def test_unknown_while_offline(self):
        await self.svc.set_enabled("mcportal_stats", False, "admin")
        self.mc.status = "offline"
        s = self.svc.summary()
        self.assertFalse(s["running_known"])
        self.assertEqual(self.state("mcportal_stats"), "off")
        self.assertFalse(s["restart_needed"])

    async def test_backup_before_every_change(self):
        await self.svc.set_enabled("mcportal_stats", False, "admin")
        backups = sorted((self.root / "backups" / "packs").iterdir())
        self.assertEqual(len(backups), 1)
        saved = json.loads((backups[0] / "world_behavior_packs.json").read_text(encoding="utf-8"))
        self.assertIn(self.packs["mcportal_stats"]["uuid"], [e["pack_id"] for e in saved])

    async def test_refused(self):
        with self.assertRaises(PortalError) as e:
            await self.svc.set_enabled("nope", False, "admin")
        self.assertEqual(e.exception.status, 404)
        with self.assertRaises(PortalError):
            await self.svc.set_enabled("../etc", False, "admin")
        async with self.mc.op_lock:
            self.mc.busy = "update"
            with self.assertRaises(PortalError) as e:
                await self.svc.set_enabled("mcportal_stats", False, "admin")
            self.assertEqual(e.exception.status, 409)

    async def test_write_error_restores_backup(self):
        before = self.files.read_world_packs("behavior")
        original = self.files.write_world_packs
        calls = []

        def flaky(kind, entries):
            calls.append(kind)
            if kind == "resource" and len(calls) == 2:
                raise OSError("Platte voll")
            original(kind, entries)

        self.files.write_world_packs = flaky
        with self.assertRaises(PortalError):
            await self.svc.set_enabled("mcportal_waypoints", False, "admin")
        self.assertEqual(self.files.read_world_packs("behavior"), before, "first file put back")
        self.assertEqual(self.audit.tail(1)[0]["result"], "FAILED")


if __name__ == "__main__":
    unittest.main()
