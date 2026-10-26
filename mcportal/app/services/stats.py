"""Block statistics: totals per player and block type, fed by the stats behavior pack.

The pack writes one "[mcportal-stats] {...}" line to the server log every 20 s
with the counts since its last line. These deltas are added up here and kept in
/var/lib/mcportal/stats.json. A cursor (timestamp + hashes of the lines at that
timestamp) makes sure no line is counted twice, also across portal restarts.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from pathlib import Path

from ..adapters.base import MinecraftAdapter
from ..adapters.bedrock.logparse import LogLine, parse_stats
from .minecraft import MinecraftService

log = logging.getLogger("mcportal.stats")
TOP_N = 8


class StatsService:
    def __init__(self, adapter: MinecraftAdapter, mc: MinecraftService, data_dir: Path):
        self.a = adapter
        self.mc = mc
        self.file = data_dir / "stats.json"
        self.data = self._load()
        self._ready = False
        self._buffer: list[LogLine] = []
        mc.line_listeners.append(self._on_live_line)
        mc.extras["stats"] = lambda: {"updated": self.data.get("updated"), "pack_seen": self.data.get("pack_seen")}

    # ---------- persistence ----------

    def _load(self) -> dict:
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            if data.get("version") == 1:
                return data
        except (OSError, ValueError):
            pass
        return {"version": 1, "since": None, "updated": None, "pack_seen": None,
                "cursor": {"ts": 0.0, "hashes": []}, "players": {}}

    def _save(self) -> None:
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.file)  # the portal's own file - atomic rename is fine here

    # ---------- feeding ----------

    async def startup(self) -> None:
        cursor = self.data["cursor"]["ts"]
        if cursor:
            try:
                lines = await asyncio.to_thread(self.a.read_log, cursor - 1)
                self._apply_lines(lines)
            except Exception:
                log.exception("stats catch-up failed")
        self._ready = True
        self._apply_lines(self._buffer)
        self._buffer.clear()

    def _on_live_line(self, line: LogLine) -> None:
        if not self._ready:
            self._buffer.append(line)
            return
        self._apply_lines([line])

    def _apply_lines(self, lines: list[LogLine]) -> None:
        changed = False
        for line in lines:
            payload = parse_stats(line)
            if payload is None:
                continue
            h = hashlib.sha1(f"{line.ts}|{line.text}".encode()).hexdigest()[:16]
            cur = self.data["cursor"]
            if line.ts < cur["ts"] or (line.ts == cur["ts"] and h in cur["hashes"]):
                continue
            if line.ts > cur["ts"]:
                cur["ts"], cur["hashes"] = line.ts, []
            cur["hashes"].append(h)
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
        d["since"] = d["since"] or ts
        for name, counts in (payload.get("players") or {}).items():
            if not isinstance(name, str) or not isinstance(counts, dict):
                continue
            p = d["players"].setdefault(name, {"placed": {}, "broken": {}, "last_active": None})
            for kind in ("placed", "broken"):
                for block, n in (counts.get(kind) or {}).items():
                    if isinstance(block, str) and isinstance(n, int) and 0 < n < 1_000_000:
                        p[kind][block] = p[kind].get(block, 0) + n
            p["last_active"] = ts
        d["updated"] = ts

    # ---------- api ----------

    def summary(self) -> dict:
        players = []
        for name, p in self.data["players"].items():
            players.append({
                "name": name,
                "placed": sum(p["placed"].values()),
                "broken": sum(p["broken"].values()),
                "top_placed": sorted(p["placed"].items(), key=lambda kv: -kv[1])[:TOP_N],
                "top_broken": sorted(p["broken"].items(), key=lambda kv: -kv[1])[:TOP_N],
                "last_active": p["last_active"],
            })
        players.sort(key=lambda p: -(p["placed"] + p["broken"]))
        return {
            "since": self.data["since"],
            "updated": self.data["updated"],
            "pack_seen": self.data["pack_seen"],
            "players": players,
            "now": time.time(),
        }
