"""Timed events of the events pack (minecraft-pack/mcportal_events), as seen by the portal.

The pack writes
  [mcportal-events] {"v":1,"event":"state","auto":..,"online":..,"active":[{type,remaining,total,by}],"next_in":..,
                     "last":..,"register":..,"types":[..]}      (start, every change, every 10 online minutes)
  [mcportal-events] {"v":1,"event":"started","type":..,"by":..,"duration":..}
  [mcportal-events] {"v":1,"event":"ended","type":..,"by":..,"ran":..,"participants":[..]}
The portal keeps the latest state and a history, and controls the pack through fixed console commands
(`scriptevent mcfs:event start <type>` ...). Stored in /var/lib/mcportal/events.json.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path

from ..adapters.base import MinecraftAdapter
from ..adapters.bedrock.commands import DAYTIME, EVENT_TYPES, WEATHER
from ..adapters.bedrock.logparse import LogLine, parse_events
from ..audit import AuditLog
from .logcursor import LogCursor
from .minecraft import MinecraftService, PortalError

log = logging.getLogger("mcportal.events")

HISTORY_KEEP = 100
STATE_REFRESH_SECONDS = 30
ACTIONS = ("start", "stop", "auto_on", "auto_off")


class EventsService:
    def __init__(self, adapter: MinecraftAdapter, mc: MinecraftService, audit: AuditLog, data_dir: Path):
        self.a = adapter
        self.mc = mc
        self.audit = audit
        self.file = data_dir / "events.json"
        self.data = self._load()
        self.cursor = LogCursor(self.data["cursor"])
        self._ready = False
        self._buffer: list[LogLine] = []
        self._last_refresh = 0.0
        mc.line_listeners.append(self._on_live_line)
        mc.extras["events"] = lambda: {
            "updated": self.data.get("updated"),
            "active": [a.get("type") for a in (self.data["state"] or {}).get("active", [])],
        }

    def _load(self) -> dict:
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            if data.get("version") == 1:
                return data
        except (OSError, ValueError):
            pass
        return {"version": 1, "state": None, "state_at": None, "history": [], "started": {}, "updated": None,
                "cursor": {}}

    def _save(self) -> None:
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.file)

    # ---------- feeding (same pattern as the other pack services) ----------

    async def startup(self) -> None:
        if self.cursor.ts:
            try:
                lines = await asyncio.to_thread(self.a.read_log, self.cursor.ts - 1)
                self._apply(lines)
            except Exception:
                log.exception("events catch-up failed")
        self._ready = True
        self._apply(self._buffer)
        self._buffer.clear()

    def _on_live_line(self, line: LogLine) -> None:
        if not self._ready:
            self._buffer.append(line)
            return
        self._apply([line])

    def _apply(self, lines: list[LogLine]) -> None:
        changed = False
        for line in lines:
            payload = parse_events(line)
            if payload is None or not self.cursor.first_time(line):
                continue
            changed = self._add(payload, line.ts) or changed
        if changed:
            try:
                self._save()
            except OSError:
                log.exception("cannot write %s", self.file)
            self.mc.publish()

    def _add(self, p: dict, ts: float) -> bool:
        d = self.data
        event = p.get("event")
        etype = p.get("type")
        if event == "state" and isinstance(p.get("active"), list):
            d["state"] = {k: p.get(k) for k in ("auto", "online", "active", "next_in", "last", "register", "types")}
            d["state_at"] = ts
        elif event == "started" and isinstance(etype, str):
            d["started"][etype] = {"at": ts, "by": p.get("by")}
        elif event == "ended" and isinstance(etype, str):
            began = d["started"].pop(etype, {})
            d["history"].append({
                "type": etype, "started": began.get("at"), "ended": ts, "by": began.get("by"),
                "stopped_by": p.get("by"), "ran": p.get("ran"),
                "participants": [n for n in p.get("participants", []) if isinstance(n, str)],
            })
            d["history"] = d["history"][-HISTORY_KEEP:]
            if d["state"]:  # don't wait for the next state line to show it as finished
                d["state"]["active"] = [x for x in d["state"].get("active", []) if x.get("type") != etype]
        else:
            return False
        d["updated"] = ts
        return True

    # ---------- api ----------

    def summary(self) -> dict:
        d = self.data
        state = d["state"] or {}
        active = [{**a, "started": d["started"].get(a.get("type"), {}).get("at")} for a in state.get("active", [])]
        counts: dict[str, int] = {}
        for h in d["history"]:
            for n in h["participants"]:
                counts[n] = counts.get(n, 0) + 1
        self._maybe_refresh()
        return {
            "installed": d["state"] is not None,
            "auto": state.get("auto"),
            "online": state.get("online"),
            "active": active,
            "next_in": state.get("next_in"),
            "types": state.get("types") or [],
            "register": state.get("register"),
            "state_at": d["state_at"],
            "history": list(reversed(d["history"][-20:])),
            "participations": dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))),
            "updated": d["updated"],
        }

    def _maybe_refresh(self) -> None:
        """Ask the pack for a fresh state (remaining times) - at most every 30 s, only when possible."""
        if time.time() - self._last_refresh < STATE_REFRESH_SECONDS or self.data["state"] is None:
            return
        if self.mc.status_word() != "online" or not self.a.console_available():
            return
        self._last_refresh = time.time()
        try:
            self.a.event_control_live("state")
        except Exception:
            log.debug("state refresh failed", exc_info=True)

    async def world(self, kind: str, value: str, user: str) -> None:
        """Weather / time of day through fixed console commands (commands.world_control)."""
        if kind not in ("weather", "time") or value not in (WEATHER if kind == "weather" else DAYTIME):
            raise PortalError("Unbekannte Einstellung", 400)
        if self.mc.status_word() != "online":
            raise PortalError("Der Server ist nicht online.", 409)
        if not self.a.console_available():
            raise PortalError("Server-Konsole nicht verfügbar.", 409)
        action = "WORLD_WEATHER" if kind == "weather" else "WORLD_TIME"
        try:
            await asyncio.to_thread(self.a.world_control_live, kind, value)
        except Exception as e:
            self.audit.write(action, "FAILED", user, value=value, error=str(e))
            raise PortalError(f"Befehl fehlgeschlagen: {e}", 500)
        self.audit.write(action, "SUCCESS", user, value=value)

    async def control(self, action: str, event_type: str | None, user: str) -> None:
        if action not in ACTIONS:
            raise PortalError("Unbekannte Aktion", 400)
        if action in ("start", "stop") and event_type not in EVENT_TYPES:
            raise PortalError("Unbekanntes Event", 400)
        if self.data["state"] is None:
            raise PortalError("Das Events-Pack hat sich noch nicht gemeldet.", 409)
        if self.mc.status_word() != "online":
            raise PortalError("Der Server ist nicht online.", 409)
        if not self.a.console_available():
            raise PortalError("Server-Konsole nicht verfügbar.", 409)
        try:
            await asyncio.to_thread(self.a.event_control_live, action, event_type)
        except Exception as e:
            self.audit.write("EVENT", "FAILED", user, command=action, type=event_type, error=str(e))
            raise PortalError(f"Befehl fehlgeschlagen: {e}", 500)
        self.audit.write("EVENT", "SUCCESS", user, command=action, type=event_type)
