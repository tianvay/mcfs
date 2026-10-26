"""Server status, online players, start/stop/restart."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path

from ..adapters.base import MinecraftAdapter
from ..adapters.bedrock.logparse import LogLine, PlayerTracker, parse_version, version_history
from ..adapters.bedrock.systemd import ALLOWED_VERBS, UnitState
from ..audit import AuditLog

log = logging.getLogger("mcportal.minecraft")

POLL_INTERVAL = 5.0
# If the "Server started." line is not in the journal (e.g. rotated away),
# an active unit is considered online after this many seconds.
ASSUME_STARTED_AFTER = 120


class PortalError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class MinecraftService:
    def __init__(self, adapter: MinecraftAdapter, audit: AuditLog, data_dir: Path):
        self.a = adapter
        self.audit = audit
        self.versions_file = data_dir / "versions.json"
        self.tracker = PlayerTracker()
        self.unit: UnitState | None = None
        self.versions: list[tuple[float, str]] = self._load_versions()
        self.allowlist_count: int | None = None
        self.busy: str | None = None
        self.last_error: str | None = None
        self.op_lock = asyncio.Lock()
        self._subs: set[asyncio.Queue] = set()
        self._ready = False
        self._buffer: list[LogLine] = []
        self._scan_until = 0.0
        self._tasks: list[asyncio.Task] = []
        self._last_published: str | None = None
        # other services add their part of the status here (e.g. "update")
        self.extras: dict[str, Callable[[], dict]] = {}
        # other services receive every new server log line (e.g. block statistics)
        self.line_listeners: list[Callable[[LogLine], None]] = []

    # ---------- lifecycle ----------

    async def startup(self) -> None:
        self._tasks.append(asyncio.create_task(self._follow_loop()))
        await asyncio.to_thread(self._initial_scan)
        for line in self._buffer:
            if line.ts > self._scan_until:
                self._on_line(line)
        self._buffer.clear()
        self._ready = True
        self._tasks.append(asyncio.create_task(self._poll_loop()))
        if self._is_active() and self.a.console_available():
            await self._request_list()
        self.publish()

    async def shutdown(self) -> None:
        for t in self._tasks:
            t.cancel()

    def _initial_scan(self) -> None:
        self.unit = self.a.unit_state()
        # Full journal only once (to build the version history); afterwards
        # only since the last known version change / current server start.
        since = None
        if self.versions:
            since = self.versions[-1][0]
            if self.unit.started_at:
                since = min(since, self.unit.started_at)
            since -= 5
        lines = self.a.read_log(since)
        self._scan_until = lines[-1].ts if lines else 0.0
        self._merge_versions(version_history(lines))
        if self.unit.active_state in ("active", "activating", "deactivating") and self.unit.started_at:
            for line in lines:
                if line.ts >= self.unit.started_at - 2:
                    self.tracker.feed(line)
        self.refresh_allowlist_count()

    async def _follow_loop(self) -> None:
        while True:
            try:
                async for line in self.a.follow_log():
                    if self._ready:
                        self._on_line(line)
                    else:
                        self._buffer.append(line)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("journal follow failed")
            await asyncio.sleep(5)

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(POLL_INTERVAL)
            try:
                await asyncio.to_thread(self._refresh)
                self.publish()
            except Exception:
                log.exception("status poll failed")

    def _refresh(self) -> None:
        self.unit = self.a.unit_state()
        if self.unit.active_state in ("inactive", "failed"):
            self.tracker.reset()
        self.refresh_allowlist_count()

    def refresh_allowlist_count(self) -> None:
        try:
            self.allowlist_count = len(self.a.files.read_allowlist())
        except (OSError, ValueError):
            self.allowlist_count = None

    def _on_line(self, line: LogLine) -> None:
        for listener in self.line_listeners:
            try:
                listener(line)
            except Exception:
                log.exception("log line listener failed")
        changed = self.tracker.feed(line)
        v = parse_version(line)
        if v:
            self._merge_versions([(line.ts, v)])
            changed = True
        if line.source == "server" and line.message.startswith("Server started."):
            asyncio.get_running_loop().call_later(2, lambda: asyncio.ensure_future(self._request_list()))
        if changed:
            self.publish()

    async def _request_list(self) -> None:
        try:
            await asyncio.to_thread(self.a.request_player_list)
        except Exception as e:
            log.info("player list not requested: %s", e)

    # ---------- versions ----------

    def _load_versions(self) -> list[tuple[float, str]]:
        try:
            return [(float(t), str(v)) for t, v in json.loads(self.versions_file.read_text())]
        except (OSError, ValueError, TypeError):
            return []

    def _merge_versions(self, found: list[tuple[float, str]]) -> None:
        before = len(self.versions)
        for ts, v in found:
            if not self.versions or (v != self.versions[-1][1] and ts > self.versions[-1][0]):
                self.versions.append((ts, v))
        if len(self.versions) != before:
            try:
                self.versions_file.write_text(json.dumps(self.versions))
            except OSError:
                log.warning("cannot write %s", self.versions_file)

    # ---------- state ----------

    def _is_active(self) -> bool:
        return bool(self.unit and self.unit.active_state == "active")

    def status_word(self) -> str:
        u = self.unit
        if u is None:
            return "unknown"
        if u.active_state == "active":
            if self.tracker.server_started:
                return "online"
            if u.started_at and time.time() - u.started_at > ASSUME_STARTED_AFTER:
                return "online"
            return "starting"
        return {"activating": "starting", "deactivating": "stopping", "failed": "failed"}.get(u.active_state, "offline")

    def snapshot(self) -> dict:
        props = self.a.files.read_properties()
        u = self.unit
        active = self._is_active()
        last_update = self.versions[-1][0] if len(self.versions) > 1 else None
        return {
            "server_name": props.get("server-name", "Minecraft"),
            "status": self.status_word(),
            "active_state": u.active_state if u else "unknown",
            "started_at": u.started_at if u and active else None,
            "last_start": u.started_at if u else None,
            "version": self.versions[-1][1] if self.versions else None,
            "seed": str(seed) if (seed := self.a.files.seed()) is not None else None,
            "last_update": last_update,
            "players": sorted(
                ({"name": p.name, "since": p.since} for p in self.tracker.players.values()),
                key=lambda p: p["name"].lower(),
            ),
            "max_players": int(props["max-players"]) if props.get("max-players", "").isdigit() else None,
            "allowlist_count": self.allowlist_count,
            "console_available": self.a.console_available(),
            "busy": self.busy,
            "last_error": self.last_error,
            **{key: fn() for key, fn in self.extras.items()},
            "now": time.time(),
        }

    # ---------- pub/sub for SSE ----------

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=5)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    def publish(self) -> None:
        snap = self.snapshot()
        key = json.dumps({k: v for k, v in snap.items() if k != "now"}, sort_keys=True)
        if key == self._last_published:
            return
        self._last_published = key
        for q in list(self._subs):
            if q.full():
                q.get_nowait()
            q.put_nowait(snap)

    # ---------- control ----------

    def begin_control(self, verb: str, user: str) -> None:
        """Start start/stop/restart in the background; status follows via SSE."""
        if verb not in ALLOWED_VERBS:
            raise PortalError("Unbekannte Aktion", 404)
        if self.op_lock.locked():
            raise PortalError(f"Es läuft bereits eine Aktion: {self.busy}", 409)
        self._tasks.append(asyncio.create_task(self._control(verb, user)))

    async def _control(self, verb: str, user: str) -> None:
        async with self.op_lock:
            self.busy, self.last_error = verb, None
            self.publish()
            players = [p.name for p in self.tracker.players.values()]
            try:
                ok, msg = await asyncio.to_thread(self.a.control, verb)
            except Exception as e:
                ok, msg = False, str(e)
            await asyncio.to_thread(self._refresh)
            self.busy = None
            if not ok:
                self.last_error = f"{verb} fehlgeschlagen: {msg}"
            self.audit.write(f"SERVER_{verb.upper()}", "SUCCESS" if ok else "FAILED", user,
                             players_online=", ".join(players) or None, error=None if ok else msg)
            self.publish()
