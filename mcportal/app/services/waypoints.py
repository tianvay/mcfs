"""Waypoints of the waypoints behavior pack, as seen by the portal (admin view: all, also private ones).

The pack writes after every change (and at startup) the complete list:
  [mcportal-warp] {"v":1,"event":"list","waypoints":[{name, owner, dim, x, y, z, public, physical, created}]}
plus single events; "teleport" and "renamed" are used here to count travels per waypoint.
Stored in /var/lib/mcportal/waypoints.json.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from ..adapters.base import MinecraftAdapter
from ..adapters.bedrock.logparse import LogLine, parse_pack_line
from .logcursor import LogCursor
from .minecraft import MinecraftService

log = logging.getLogger("mcportal.waypoints")


def _key(name: str) -> str:
    return name.strip().lower()


class WaypointsService:
    def __init__(self, adapter: MinecraftAdapter, mc: MinecraftService, data_dir: Path):
        self.a = adapter
        self.mc = mc
        self.file = data_dir / "waypoints.json"
        self.data = self._load()
        self.cursor = LogCursor(self.data["cursor"])
        self._ready = False
        self._buffer: list[LogLine] = []
        mc.line_listeners.append(self._on_live_line)
        mc.extras["waypoints"] = lambda: {"updated": self.data.get("updated")}

    def _load(self) -> dict:
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            if data.get("version") == 1:
                return data
        except (OSError, ValueError):
            pass
        return {"version": 1, "list": [], "list_at": None, "travels": {}, "updated": None, "cursor": {}}

    def _save(self) -> None:
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.file)

    # ---------- feeding (same pattern as StatsService) ----------

    async def startup(self) -> None:
        if self.cursor.ts:
            try:
                lines = await asyncio.to_thread(self.a.read_log, self.cursor.ts - 1)
                self._apply(lines)
            except Exception:
                log.exception("waypoints catch-up failed")
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
            payload = parse_pack_line(line, "mcportal-warp")
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
        if event == "list" and isinstance(p.get("waypoints"), list):
            d["list"] = [w for w in p["waypoints"] if isinstance(w, dict) and isinstance(w.get("name"), str)]
            d["list_at"] = ts
        elif event == "teleport" and isinstance(p.get("name"), str):
            t = d["travels"].setdefault(_key(p["name"]), {"count": 0, "last": None, "by": {}})
            t["count"] += 1
            t["last"] = ts
            who = str(p.get("player", "?"))
            t["by"][who] = t["by"].get(who, 0) + 1
        elif event == "renamed" and isinstance(p.get("from"), str) and isinstance(p.get("name"), str):
            old = d["travels"].pop(_key(p["from"]), None)
            if old:
                d["travels"][_key(p["name"])] = old
        elif event in ("deleted", "destroyed") and isinstance(p.get("name"), str):
            d["travels"].pop(_key(p["name"]), None)
        else:
            return False
        d["updated"] = ts
        return True

    # ---------- api ----------

    def summary(self) -> dict:
        players: dict[str, list] = {}
        for w in self.data["list"]:
            t = self.data["travels"].get(_key(w["name"]), {})
            players.setdefault(w.get("owner", "?"), []).append({
                **w, "travels": t.get("count", 0), "last_travel": t.get("last"), "travelers": t.get("by", {}),
            })
        for items in players.values():
            items.sort(key=lambda w: w["name"].lower())
        return {
            "total": len(self.data["list"]),
            "players": players,
            "list_at": self.data["list_at"],
            "updated": self.data["updated"],
        }
