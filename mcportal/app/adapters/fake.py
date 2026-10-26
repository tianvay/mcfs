"""In-memory stand-in for a Bedrock server - for local development of the UI only."""
from __future__ import annotations

import asyncio
import json
import os
import queue
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

    def _boot(self, ts: float) -> None:
        self._state, self._started_at = "active", ts
        self._log("Started minecraft-bedrock.service", "systemd", ts)
        self._log("Starting Server", ts=ts)
        self._log(f"Version: {self.VERSION}", ts=ts)
        self._log("Server started.", ts=ts + 4)
        self._log("Player connected: Steve, xuid: 2535400000000001", ts=ts + 60)
        self._online = ["Steve"]

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

    def allowlist_remove_live(self, name: str) -> None:
        entries = [e for e in self.files.read_allowlist() if e.get("name", "").lower() != name.lower()]
        self.files.write_allowlist(entries)
        self._log(f"Player removed from allowlist: {name}")
