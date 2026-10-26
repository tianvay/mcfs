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
# per-key counters and plain numbers sent by the pack (see minecraft-pack/mcportal_stats)
COUNTERS = ("placed", "broken", "deaths", "kills", "food", "bred", "dist")
SCALARS = ("xp", "time")
DIAMOND_ORES = ("minecraft:diamond_ore", "minecraft:deepslate_diamond_ore")


def _plausible(n) -> bool:
    return isinstance(n, (int, float)) and not isinstance(n, bool) and 0 < n < 1_000_000


def _is_sapling(block: str) -> bool:
    return block.endswith("_sapling") or block in (
        "minecraft:mangrove_propagule", "minecraft:azalea", "minecraft:flowering_azalea")


def _top(counter: dict, n: int | None = None) -> list:
    items = sorted(counter.items(), key=lambda kv: -kv[1])
    return items[:n] if n else items


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
        day = time.strftime("%Y-%m-%d", time.localtime(ts))
        for name, counts in (payload.get("players") or {}).items():
            if not isinstance(name, str) or not isinstance(counts, dict):
                continue
            p = self._player(name)
            for kind in COUNTERS:
                for key, n in (counts.get(kind) or {}).items():
                    if isinstance(key, str) and _plausible(n):
                        p[kind][key] = p[kind].get(key, 0) + n
            for kind in SCALARS:
                n = counts.get(kind)
                if _plausible(n):
                    p[kind] += n
                    if kind == "time":
                        p["time_by_day"][day] = p["time_by_day"].get(day, 0) + n
            p["last_active"] = ts
        d["updated"] = ts

    def _player(self, name: str) -> dict:
        # also upgrades entries written by pack 1.0 (blocks only)
        p = self.data["players"].setdefault(name, {"last_active": None})
        for kind in COUNTERS:
            p.setdefault(kind, {})
        for kind in SCALARS:
            p.setdefault(kind, 0)
        p.setdefault("time_by_day", {})
        return p

    # ---------- api ----------

    def summary(self) -> dict:
        today = time.strftime("%Y-%m-%d")
        players = []
        for name in list(self.data["players"]):
            p = self._player(name)
            saplings = {k: n for k, n in p["placed"].items() if _is_sapling(k)}
            players.append({
                "name": name,
                "last_active": p["last_active"],
                "placed": sum(p["placed"].values()),
                "broken": sum(p["broken"].values()),
                "top_placed": _top(p["placed"], TOP_N),
                "top_broken": _top(p["broken"], TOP_N),
                "deaths": sum(p["deaths"].values()), "deaths_by": _top(p["deaths"]),
                "kills": sum(p["kills"].values()), "kills_by": _top(p["kills"]),
                "diamonds": sum(p["broken"].get(k, 0) for k in DIAMOND_ORES),
                "food": sum(p["food"].values()), "food_by": _top(p["food"]),
                "xp": p["xp"],
                "saplings": sum(saplings.values()), "saplings_by": _top(saplings),
                "bred": sum(p["bred"].values()), "bred_by": _top(p["bred"]),
                "dist": sum(p["dist"].values()), "dist_by": _top(p["dist"]),
                "time_total": p["time"],
                "time_today": p["time_by_day"].get(today, 0),
            })
        players.sort(key=lambda p: (-p["time_total"], -(p["placed"] + p["broken"])))
        return {
            "since": self.data["since"],
            "updated": self.data["updated"],
            "pack_seen": self.data["pack_seen"],
            "players": players,
            "now": time.time(),
        }
