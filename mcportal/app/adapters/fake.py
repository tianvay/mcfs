"""In-memory stand-in for a Bedrock server - for local development of the UI only."""
from __future__ import annotations

import asyncio
import json
import os
import queue
import shutil
import threading
import time
from collections.abc import AsyncIterator
from pathlib import Path

from .bedrock.commands import valid_player_name
from .bedrock.files import ServerFiles
from .bedrock.logparse import LogLine
from .bedrock.release import Release
from .bedrock.systemd import ALLOWED_VERBS, UnitState


class FakeUpdater:
    """Simulates download/backup/apply; MCPORTAL_FAKE_UPDATE_FAIL=1 makes the new version fail to start."""

    LATEST = "1.26.52.3"

    def __init__(self, adapter: "FakeAdapter"):
        self.a = adapter
        self._previous = adapter.VERSION

    def latest(self) -> Release:
        return Release(self.LATEST, f"https://www.minecraft.net/bedrockdedicatedserver/bin-linux/bedrock-server-{self.LATEST}.zip")

    def download(self, rel: Release, dest: Path) -> str:
        time.sleep(2)
        dest.write_bytes(b"fake")
        return "0" * 64

    def stage(self, zip_path: Path, target: Path) -> None:
        time.sleep(1)
        target.mkdir(parents=True, exist_ok=True)

    def preflight(self) -> None:
        pass

    def checksums(self) -> dict[str, str]:
        return {"allowlist.json": self.a.files.allowlist.read_text(), "permissions.json": self.a.files.permissions.read_text()}

    def backup(self, target_dir: Path) -> Path:
        time.sleep(2)
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "server.tar.gz").write_bytes(b"fake")
        return target_dir / "server.tar.gz"

    def apply(self) -> tuple[bool, str]:
        time.sleep(2)
        self._previous = self.a.VERSION
        self.a.VERSION = self.LATEST
        self.a.broken = os.environ.get("MCPORTAL_FAKE_UPDATE_FAIL") == "1"
        return True, "apply: fertig"

    def rollback(self) -> tuple[bool, str]:
        time.sleep(1)
        self.a.VERSION = self._previous
        self.a.broken = False
        return True, "rollback: fertig"


class FakeAdapter:
    VERSION = "1.26.51.1"
    broken = False

    def announce_update(self) -> None:
        self._log("[Server] Der Server wird gleich für ein Update neu gestartet (ca. 1 Minute).")

    def __init__(self, server_dir: str):
        d = Path(server_dir)
        d.mkdir(parents=True, exist_ok=True)
        if not (d / "allowlist.json").exists():
            (d / "allowlist.json").write_text(json.dumps([
                {"ignoresPlayerLimit": False, "name": "Steve", "xuid": "2535400000000001"},
                {"ignoresPlayerLimit": False, "name": "Alex", "xuid": "2535400000000002"},
                {"ignoresPlayerLimit": False, "name": "Sunny"},
            ], separators=(",", ":")))
            (d / "permissions.json").write_text('[{"permission":"operator","xuid":"2535400000000001"}]')
            (d / "server.properties").write_text("server-name=Dedicated Server\nmax-players=10\n")
        self.files = ServerFiles(server_dir)
        self._fake_packs()
        self.updater = FakeUpdater(self)
        self._q: queue.Queue[LogLine] = queue.Queue()
        self._history: list[LogLine] = []
        self._lock = threading.Lock()
        self._state = "inactive"
        self._started_at: float | None = None
        self._online: list[str] = []
        self._boot(time.time() - 3 * 3600 - 42 * 60)

    def _log(self, msg: str, source: str = "server", ts: float | None = None, bare: bool = False) -> None:
        ts_ = ts or time.time()
        text = msg if source == "systemd" or bare else             f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts_))}:000 INFO] {msg}"
        line = LogLine(ts=ts_, source=source, text=text)
        with self._lock:
            self._history.append(line)
        if ts is None:
            self._q.put(line)

    def _fake_packs(self) -> None:
        """The repo's packs in the fake world, all switched on."""
        world = self.files.world_dir()
        if (world / "world_behavior_packs.json").exists():
            return
        src = Path(__file__).resolve().parents[2] / "minecraft-pack"
        lists: dict[str, list] = {"behavior": [], "resource": []}
        for d in sorted(p for p in src.iterdir() if (p / "manifest.json").is_file()):
            m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
            kind = "resource" if any(x.get("type") == "resources" for x in m.get("modules", [])) else "behavior"
            dst = world / f"{kind}_packs" / d.name
            # like setup.sh: the whole pack without tests/ and tools/
            shutil.copytree(d, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("tests", "tools"))
            lists[kind].append({"pack_id": m["header"]["uuid"], "version": m["header"]["version"]})
        for kind, entries in lists.items():
            (world / f"world_{kind}_packs.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")

    def _pack_stack(self, ts: float | None = None) -> None:
        """Like Bedrock at every start: one "Pack Stack" line per switched-on behavior pack."""
        names = {p["uuid"]: p for p in self.files.installed_packs()}
        for i, e in enumerate(self.files.read_world_packs("behavior")):
            p = names.get(e["pack_id"])
            if p:
                v = ".".join(map(str, p["version"]))
                self._log(f"Pack Stack - [{i:02d}] {p['name']} (id: {p['uuid']}, version: {v}) "
                          f"@ worlds/Bedrock level/behavior_packs/{p['folder']}", ts=ts)

    def _boot(self, ts: float) -> None:
        self._state, self._started_at = "active", ts
        self._log("Started minecraft-bedrock.service", "systemd", ts)
        self._log("Starting Server", ts=ts)
        self._log(f"Version: {self.VERSION}", ts=ts)
        self._pack_stack(ts=ts + 3)
        self._log("Server started.", ts=ts + 4)
        self._log("Player connected: Steve, xuid: 2535400000000001", ts=ts + 60)
        self._online = ["Steve"]
        # events pack: one finished storm in the past, nothing running
        self._ev_auto, self._ev_active, self._ev_every = True, {}, 90
        # sent a few seconds after the portal started (follow_log): a fresh dev data dir has no
        # catch-up position, and lines from before the portal start would only arrive through it
        self._ev_boot_due = time.time() + 3

    def unit_state(self) -> UnitState:
        return UnitState(self._state, "running" if self._state == "active" else "dead", 4711, self._started_at)

    def control(self, verb: str) -> tuple[bool, str]:
        if verb not in ALLOWED_VERBS:
            raise ValueError(verb)
        if verb in ("stop", "restart") and self._state == "active":
            self._state = "deactivating"
            self._log("Stopping minecraft-bedrock.service", "systemd")
            time.sleep(2)
            for n in self._online:
                self._log(f"Player disconnected: {n}, xuid: ")
            self._online = []
            self._state, self._started_at = "inactive", None
            self._log("Stopped minecraft-bedrock.service", "systemd")
        if verb in ("start", "restart") and self._state != "active":
            self._state = "activating"
            self._log("Started minecraft-bedrock.service", "systemd")
            self._started_at = time.time()
            self._log("Starting Server")
            self._log(f"Version: {self.VERSION}")
            time.sleep(2)
            self._state = "active"
            self._pack_stack()
            if not self.broken:
                self._log("Server started.")
                self._log("[Scripting] [mcportal-stats] {\"v\":2,\"started\":true}")
                self._log("Player connected: Steve, xuid: 2535400000000001")
                self._online = ["Steve"]
        return True, ""

    def read_log(self, since: float | None = None) -> list[LogLine]:
        with self._lock:
            return [l for l in self._history if since is None or l.ts >= since]

    async def follow_log(self) -> AsyncIterator[LogLine]:
        last_stats = time.time()
        while True:
            try:
                yield self._q.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.2)
            if getattr(self, "_ev_boot_due", None) and time.time() > self._ev_boot_due:
                self._ev_boot_due = None
                self._ev_log({"event": "started", "type": "storm", "by": "auto", "duration": 2400})
                self._ev_log({"event": "ended", "type": "storm", "by": "time", "ran": 2400, "participants": ["Steve"]})
                self._ev_state()
                self._shop_boot_due = time.time() + 2   # the shop pack came later than this storm: start credit
            if getattr(self, "_shop_boot_due", None) and time.time() > self._shop_boot_due:
                self._shop_boot_due = None
                self._shop_boot()
            if self._state == "active" and time.time() - last_stats > 8:
                last_stats = time.time()
                self._emit_stats()

    def _emit_stats(self) -> None:
        """Like the stats behavior pack 2.0: one line with the deltas of the last interval."""
        import random
        r = random.randint
        blocks = ["minecraft:cobblestone", "minecraft:oak_planks", "minecraft:dirt", "minecraft:glass", "minecraft:torch",
                  "minecraft:oak_sapling", "minecraft:birch_sapling", "minecraft:deepslate_diamond_ore"]
        players = {}
        for n in self._online:
            e = {"placed": {random.choice(blocks): r(1, 20)}, "broken": {random.choice(blocks): r(1, 30)},
                 "xp": r(0, 40), "time": 8,
                 "dist": {random.choice(["walk", "swim", "boat", "elytra", "horse"]): r(5, 400)}}
            if r(0, 2) == 0:
                e["kills"] = {random.choice(["minecraft:zombie", "minecraft:creeper", "minecraft:skeleton", "minecraft:spider"]): r(1, 3)}
            if r(0, 4) == 0:
                e["deaths"] = {random.choice(["minecraft:creeper", "cause:lava", "cause:fall", "cause:drowning"]): 1}
            if r(0, 2) == 0:
                e["food"] = {random.choice(["minecraft:bread", "minecraft:cooked_beef", "minecraft:apple"]): r(1, 2)}
            if r(0, 3) == 0:
                e["bred"] = {random.choice(["minecraft:cow", "minecraft:sheep", "minecraft:chicken"]): 1}
            players[n] = e
        if players:
            self._log("[Scripting] [mcportal-stats] " + json.dumps({"v": 2, "players": players}))
        self._emit_achievement()
        self._emit_waypoints()

    def _emit_waypoints(self) -> None:
        """Like the waypoints pack 1.3.0: the full list once, then now and then a teleport."""
        import random
        if not self._online:
            return
        owner = self._online[0]
        if not getattr(self, "_wp_list_sent", False):
            self._wp_list_sent = True
            wps = [
                {"name": "Zuhause", "owner": owner, "dim": "minecraft:overworld", "x": -2, "y": 71, "z": -4,
                 "public": False, "physical": True, "created": "2026-10-26T08:00:00Z"},
                {"name": "Dorf", "owner": owner, "dim": "minecraft:overworld", "x": -297, "y": 76, "z": -264,
                 "public": True, "physical": True, "created": "2026-10-26T08:10:00Z"},
                {"name": "Netherfestung", "owner": owner, "dim": "minecraft:nether", "x": 120.5, "y": 64, "z": -33.2,
                 "public": False, "physical": False, "created": "2026-10-26T08:20:00Z"},
            ]
            self._log("[Scripting] [mcportal-warp] " + json.dumps({"v": 1, "event": "list", "waypoints": wps}))
        elif random.randint(0, 1) == 0:
            name = random.choice(["Zuhause", "Dorf"])
            self._log("[Scripting] [mcportal-warp] " + json.dumps({"v": 1, "event": "teleport", "player": owner, "name": name}))

    FAKE_CATALOG = [
        {"id": "diamonds", "tier": 1, "tiers": 3, "group": "Bergbau", "name": "Diamant!", "desc": "Den ersten Diamanten gefunden"},
        {"id": "diamonds", "tier": 2, "tiers": 3, "group": "Bergbau", "name": "Diamantenfieber", "desc": "50 Diamanten gefunden"},
        {"id": "deaths", "tier": 1, "tiers": 3, "group": "Missgeschicke", "name": "Anfängerfehler", "desc": "Zum ersten Mal gestorben"},
        {"id": "death_creeper", "tier": 1, "tiers": 1, "group": "Missgeschicke", "name": "Sssssurprise!", "desc": "Von einem Creeper erwischt worden"},
        {"id": "kill_wither", "tier": 1, "tiers": 1, "group": "Kampf", "name": "Wither-sprochen!", "desc": "Den Wither besiegt"},
        {"id": "saplings", "tier": 2, "tiers": 3, "group": "Natur", "name": "Förster", "desc": "100 Bäume gepflanzt"},
    ]

    def _emit_achievement(self) -> None:
        """Like the achievements pack: catalog once, then now and then an unlock."""
        import random
        if not getattr(self, "_ach_catalog_sent", False):
            self._ach_catalog_sent = True
            self._ach_done = set()
            self._log("[Scripting] [mcportal-ach] " + json.dumps({"v": 1, "catalog": self.FAKE_CATALOG}))
        todo = [e for e in self.FAKE_CATALOG if (e["id"], e["tier"]) not in self._ach_done]
        if self._online and todo and random.randint(0, 1) == 0:
            e = todo[0]
            self._ach_done.add((e["id"], e["tier"]))
            self._log("[Scripting] [mcportal-ach] " + json.dumps({"v": 1, "unlocked": [
                {"player": self._online[0], "id": e["id"], "tier": e["tier"], "name": e["name"]}]}))

    def console_available(self) -> bool:
        return self._state == "active"

    def request_player_list(self) -> None:
        self._log(f"There are {len(self._online)}/10 players online:")
        self._log(", ".join(self._online), bare=True)

    def allowlist_add_live(self, name: str) -> None:
        assert valid_player_name(name)
        entries = self.files.read_allowlist()
        entries.append({"ignoresPlayerLimit": False, "name": name})
        self.files.write_allowlist(entries)
        self._log(f"Player added to allowlist: {name}")

    def permissions_reload_live(self) -> None:
        self._log("Permissions reloaded")

    def set_survival_live(self, name: str) -> None:
        self._log(f"Set {name}'s game mode to Survival")

    def tell_operator_status_live(self, name: str, granted: bool) -> None:
        self._log(f"[tellraw {name}] {'Du bist jetzt Operator.' if granted else 'Du bist nicht mehr Operator.'}")

    def give_live(self, name: str, item_id: str, count: int) -> None:
        """Like the real server's answer; MCPORTAL_FAKE_GIVE_FAIL=<item id> makes it refuse that item."""
        from .bedrock.commands import give
        give(name, item_id, count)  # same validation as the real console
        if os.environ.get("MCPORTAL_FAKE_GIVE_FAIL") == item_id:
            self._log(f'Syntax error: Unexpected "{item_id}": at "give {name} >>{item_id}<< {count}"')
            return
        who = ", ".join(self._online) if name == "@a" else name
        self._log(f"Gave {item_id} * {count} to {who}")

    def tell_gift_live(self, name: str, item_name: str, count: int) -> None:
        from .bedrock.commands import tell_gift
        tell_gift(name, item_name, count)

    def _ev_log(self, payload: dict, ts: float | None = None) -> None:
        self._log("[Scripting] [mcportal-events] " + json.dumps({"v": 1, **payload}), ts=ts)

    def _ev_state(self, ts: float | None = None) -> None:
        night = {"blood_moon", "zombie_invasion", "shooting_stars", "haunted", "creeper_chaos", "witch_coven"}
        active = [{"type": t, "remaining": r, "total": 500 if t in night else {"storm": 2400, "bounty": 1200, "meteor": 1800, "treasure": 1800}.get(t, 7200),
                   "by": "console", "phase": ("waiting" if r > 500 else "running") if t in night else None,
                   "boss": {"name": "Bernd der Zombiekönig", "x": -120, "y": 71, "z": 48} if t == "bounty" else None,
                   "meteor": {"x": 210, "y": 70, "z": -95, "impacted": r < 1700, "undo": "meteor-4"} if t == "meteor" else None,
                   "treasure": {"buried": r < 1700, "found": False, "undo": "treasure-5"} if t == "treasure" else None,
                   "haunt": {"x": -297, "z": -264, "village": True, "kills": 6} if t == "haunted" else None,
                   "coven": {"x": 140, "y": 68, "z": 33, "left": 2, "total": 4} if t == "witch_coven" else None}
                  for t, r in self._ev_active.items()]
        self._ev_log({"event": "state", "auto": self._ev_auto, "online": len(self._online), "active": active,
                      "every": self._ev_every,
                      "next_in": min(95, self._ev_every) if self._ev_auto else None, "last": "storm", "register": getattr(self, "_ev_register", 12),
                      "types": ["storm", "mining_rush", "lucky_day", "blood_moon", "zombie_invasion", "bounty",
                                "meteor", "shooting_stars", "treasure", "haunted", "creeper_chaos", "witch_coven"],
                      "undo": getattr(self, "_ev_undo", ["meteor-3"])}, ts)

    def event_control_live(self, action: str, event_type: str | None = None) -> None:
        """Like the events pack: start/stop/auto/state; running events lose 5 minutes per state request."""
        from .bedrock.commands import event_control
        event_control(action, event_type)  # same validation as the real console command
        if action == "start" and event_type not in self._ev_active:
            self._ev_active[event_type] = {"storm": 2400, "bounty": 1200, "blood_moon": 640, "zombie_invasion": 400,
                                           "meteor": 1800, "treasure": 1800, "shooting_stars": 640,
                                           "haunted": 400, "creeper_chaos": 400, "witch_coven": 400}.get(event_type, 7200)
            self._ev_log({"event": "started", "type": event_type, "by": "console", "duration": self._ev_active[event_type]})
        elif action == "stop" and event_type in self._ev_active:
            ran = {"storm": 2400}.get(event_type, 7200) - self._ev_active.pop(event_type)
            self._ev_log({"event": "ended", "type": event_type, "by": "console", "ran": ran, "participants": list(self._online)})
            for n in self._online:   # like the shop pack: taking part is worth 5 Sterntaler
                self._shop_book(n, 5, "participation", event_type)
        elif action in ("auto_on", "auto_off"):
            self._ev_auto = action == "auto_on"
        elif action == "state":
            for t in self._ev_active:
                self._ev_active[t] = max(60, self._ev_active[t] - 300)
        self._ev_state()

    # ---------- Sterntaler shop pack ----------

    FAKE_SHOP = [
        {"id": "mcfs:bergbrecher", "name": "Bergbrecher", "price": 20,
         "desc": "Spitzhacke, die 3 × 3 × 3 Blöcke Gestein und Erz auf einmal abbaut. Schleichen: nur ein Block."},
        {"id": "mcfs:holzfaeller", "name": "Holzfäller-Axt", "price": 15,
         "desc": "Fällt einen ganzen Baum mit einem Schlag. Schleichen: nur ein Block."},
        {"id": "mcfs:magnet", "name": "Magnet-Amulett", "price": 20,
         "desc": "Zieht herumliegende Gegenstände aus 8 Blöcken an, solange es in der Schnellleiste oder Zweithand liegt."},
        {"id": "mcfs:erntesichel", "name": "Ernte-Sichel", "price": 15,
         "desc": "Erntet reife Feldfrüchte in 3 × 3 und pflanzt gleich neu."},
    ]

    def _shop_log(self, payload: dict) -> None:
        self._log("[Scripting] [mcportal-shop] " + json.dumps({"v": 1, **payload}, ensure_ascii=False))

    def _shop_boot(self) -> None:
        """Like the shop pack at every start: catalog, all balances, startup line - plus a little history."""
        self._shop = getattr(self, "_shop", {"Alex": {"b": 22, "e": 42}})
        self._shop_log({"event": "catalog", "currency": "Sterntaler", "items": self.FAKE_SHOP,
                        "rewards": {"participation": 5, "bounty": 5, "treasure_found": 5, "coven_defeated": 3,
                                    "curse_broken": 3, "meteor_hit": 2, "lightning_survived": 2, "star": 1}})
        self._shop_log({"event": "balances",
                        "players": {n: {"balance": a["b"], "earned": a["e"]} for n, a in self._shop.items()}})
        self._shop_log({"started": True})
        if self._shop["Alex"]["b"] >= 15:
            self._shop_book("Alex", -15, "buy", "mcfs:holzfaeller")
        self._shop_book("Steve", 1, "star")

    def _shop_book(self, name: str, amount: int, reason: str, detail: str | None = None) -> None:
        shop = getattr(self, "_shop", None)
        if shop is None:
            return   # the pack has not started yet
        a = shop.setdefault(name, {"b": 0, "e": 0})
        if reason == "seed" and a.get("s"):
            return self._shop_log({"event": "seed_skipped", "player": name})
        delta = max(amount, -a["b"])
        a["b"] += delta
        if delta > 0 and reason != "admin":
            a["e"] += delta
        if reason == "seed":
            a["s"] = 1
        self._shop_log({"event": "booking", "player": name, "delta": delta, "reason": reason,
                        **({"detail": detail} if detail else {}), "balance": a["b"], "earned": a["e"]})

    def shop_grant_live(self, name: str, amount: int) -> None:
        from .bedrock.commands import shop_grant
        shop_grant(name, amount)  # same validation as the real console command
        self._shop_book(name, amount, "admin")

    def shop_seed_live(self, name: str, amount: int) -> None:
        from .bedrock.commands import shop_seed
        shop_seed(name, amount)  # same validation as the real console command
        self._shop_book(name, amount, "seed")

    def event_every_live(self, minutes: int) -> None:
        from .bedrock.commands import event_every
        event_every(minutes)  # same validation as the real console command
        self._ev_every = minutes
        self._ev_state()

    def event_undo_live(self, undo_id: str) -> None:
        from .bedrock.commands import event_undo
        event_undo(undo_id)  # same validation as the real console command
        self._ev_undo = [u for u in getattr(self, "_ev_undo", ["meteor-3"]) if u != undo_id]
        self._ev_log({"event": "undone", "id": undo_id, "restored": 214, "skipped": 1})
        self._ev_state()

    def event_register_live(self, keys: list[str]) -> None:
        from .bedrock.commands import event_register
        event_register(keys)  # same validation as the real console command
        self._ev_register = getattr(self, "_ev_register", 12) + len(keys)
        self._ev_log({"event": "register", "added": len(keys), "total": self._ev_register})

    def world_control_live(self, kind: str, value: str) -> None:
        from .bedrock.commands import world_control
        cmd = world_control(kind, value)  # same validation as the real console command
        self._log("Changing to clear weather" if cmd == "weather clear" else f"[console] {cmd}")

    def world_save_live(self, step: str) -> None:
        """Like the real server; the "world" is whatever lies in <server_dir>/worlds/<level-name>."""
        if step == "hold":
            self._log("Saving...")
        elif step == "query":
            world = self.files.world_dir()
            files = sorted(p for p in world.rglob("*") if p.is_file()) if world.is_dir() else []
            self._log("Data saved. Files are now ready to be copied.")
            self._log(", ".join(f"{p.relative_to(world.parent).as_posix()}:{p.stat().st_size}" for p in files), bare=True)
        elif step == "resume":
            self._log("Changes to the world are resumed.")

    def allowlist_remove_live(self, name: str) -> None:
        entries = [e for e in self.files.read_allowlist() if e.get("name", "").lower() != name.lower()]
        self.files.write_allowlist(entries)
        self._log(f"Player removed from allowlist: {name}")
