"""Achievements: unlocks reported by the achievements behavior pack.

The pack keeps the progress itself (in the world) and decides what is unlocked;
the portal only records the unlock events from the log and shows them:
  [mcportal-ach] {"v":1,"catalog":[...]}      once per server start (all achievements)
  [mcportal-ach] {"v":1,"unlocked":[{...}]}   whenever someone reaches one
Stored in /var/lib/mcportal/achievements.json.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from ..adapters.base import MinecraftAdapter
from ..adapters.bedrock.logparse import LogLine, parse_achievements
from .logcursor import LogCursor
from .minecraft import MinecraftService

log = logging.getLogger("mcportal.achievements")
RECENT_N = 8


class AchievementsService:
    def __init__(self, adapter: MinecraftAdapter, mc: MinecraftService, data_dir: Path):
        self.a = adapter
        self.mc = mc
        self.file = data_dir / "achievements.json"
        self.data = self._load()
        self.cursor = LogCursor(self.data["cursor"])
        self._ready = False
        self._buffer: list[LogLine] = []
        mc.line_listeners.append(self._on_live_line)
        mc.extras["achievements"] = lambda: {"updated": self.data.get("updated")}

    def _load(self) -> dict:
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            if data.get("version") == 1:
                return data
        except (OSError, ValueError):
            pass
        return {"version": 1, "catalog": [], "pack_seen": None, "updated": None,
                "cursor": {}, "players": {}}

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
                log.exception("achievements catch-up failed")
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
            payload = parse_achievements(line)
            if payload is None or not self.cursor.first_time(line):
                continue
            self._add(payload, line.ts)
            changed = True
        if changed:
            try:
                self._save()
            except OSError:
                log.exception("cannot write %s", self.file)
            self.mc.publish()

    def _add(self, payload: dict, ts: float) -> None:
        d = self.data
        if payload.get("started"):
            d["pack_seen"] = ts
        catalog = payload.get("catalog")
        if isinstance(catalog, list) and catalog:
            d["catalog"] = [e for e in catalog if isinstance(e, dict) and "id" in e and "tier" in e]
        for u in payload.get("unlocked") or []:
            if not isinstance(u, dict) or not isinstance(u.get("player"), str):
                continue
            key = f"{u.get('id')}:{u.get('tier')}"
            player = d["players"].setdefault(u["player"], {})
            player.setdefault(key, {"at": ts, "name": str(u.get("name", ""))})
        d["updated"] = ts

    # ---------- api ----------

    def summary(self) -> dict:
        catalog = self.data["catalog"]
        by_key = {f"{e['id']}:{e['tier']}": e for e in catalog}
        players = {}
        recent = []
        for name, unlocked in self.data["players"].items():
            items = []
            for key, info in unlocked.items():
                e = by_key.get(key, {})
                item = {"key": key, "name": e.get("name") or info["name"], "desc": e.get("desc", ""),
                        "group": e.get("group", ""), "tier": e.get("tier"), "tiers": e.get("tiers"),
                        "at": info["at"]}
                items.append(item)
                recent.append({"player": name, **item})
            items.sort(key=lambda i: -i["at"])
            players[name] = items
        recent.sort(key=lambda i: -i["at"])
        return {
            "total": len(catalog),
            "catalog": catalog,
            "players": players,
            "recent": recent[:RECENT_N],
            "pack_seen": self.data["pack_seen"],
            "updated": self.data["updated"],
        }
