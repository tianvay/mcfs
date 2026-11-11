"""Sterntaler: the currency players earn at the timed events and spend in the in-game shop (/shop).

The shop pack (minecraft-pack/mcportal_shop) keeps the accounts in the world and decides every booking; the portal
mirrors them from the log and shows them:
  [mcportal-shop] {"v":1,"event":"catalog","currency":..,"items":[{id,name,price,desc}],"rewards":{..}}   every start
  [mcportal-shop] {"v":1,"event":"balances","players":{name:{balance,earned}}}                             every start
  [mcportal-shop] {"v":1,"event":"booking","player":..,"delta":..,"reason":..,"detail":..,"balance":..,"earned":..}
  [mcportal-shop] {"v":1,"event":"seed_skipped","player":..}      start credit asked twice
The portal only sends two fixed console commands: Sterntaler by hand from the admin (grant) and, once, the start
credit for the events that ran before the shop existed (seed; from the history of the events service).
Stored in /var/lib/mcportal/sterntaler.json.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import Callable
from pathlib import Path

from ..adapters.base import MinecraftAdapter
from ..adapters.bedrock.commands import SHOP_GRANT_MAX, valid_player_name
from ..adapters.bedrock.logparse import LogLine, parse_shop
from ..audit import AuditLog
from .logcursor import LogCursor
from .minecraft import MinecraftService, PortalError

log = logging.getLogger("mcportal.sterntaler")

LEDGER_KEEP = 500
LEDGER_SHOW = 100
SEED_PER_EVENT = 5          # same as REWARDS.participation in the pack
SEED_RETRY_SECONDS = 60


def seed_plan(history: list[dict], before: float, per_event: int = SEED_PER_EVENT) -> dict[str, int]:
    """Start credit per player: `per_event` for every event in the history they took part in before `before`."""
    plan: dict[str, int] = {}
    for h in history:
        ended = h.get("ended")
        if not isinstance(ended, (int, float)) or ended >= before:
            continue   # after the shop started the pack books it itself
        for name in h.get("participants") or []:
            if isinstance(name, str) and valid_player_name(name):
                plan[name] = plan.get(name, 0) + per_event
    return {n: min(a, SHOP_GRANT_MAX) for n, a in plan.items()}


class SterntalerService:
    def __init__(self, adapter: MinecraftAdapter, mc: MinecraftService, audit: AuditLog, data_dir: Path,
                 event_history: Callable[[], list[dict]] = lambda: []):
        self.a = adapter
        self.mc = mc
        self.audit = audit
        self.event_history = event_history
        self.file = data_dir / "sterntaler.json"
        self.data = self._load()
        self.cursor = LogCursor(self.data["cursor"])
        self._ready = False
        self._buffer: list[LogLine] = []
        self._last_seed_try = 0.0
        mc.line_listeners.append(self._on_live_line)
        mc.extras["sterntaler"] = lambda: {"updated": self.data.get("updated")}

    def _load(self) -> dict:
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            if data.get("version") == 1:
                return data
        except (OSError, ValueError):
            pass
        return {"version": 1, "pack_seen": None, "currency": "Sterntaler", "items": [], "rewards": {},
                "players": {}, "ledger": [], "seed": {"plan": None, "done": []}, "updated": None, "cursor": {}}

    def _save(self) -> None:
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.file)

    # ---------- feeding (same pattern as the other pack services) ----------

    async def startup(self) -> None:
        since = self.cursor.ts - 1 if self.cursor.ts else None
        if since is None:
            # first time: the pack's lines of the current server run (catalog, balances) are already in the log
            u = getattr(self.mc, "unit", None)
            if u and u.active_state == "active" and u.started_at:
                since = u.started_at - 2
        if since is not None:
            try:
                lines = await asyncio.to_thread(self.a.read_log, since)
                self._apply(lines)
            except Exception:
                log.exception("sterntaler catch-up failed")
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
            payload = parse_shop(line)
            if payload is None or not self.cursor.first_time(line):
                continue
            changed = self._add(payload, line.ts) or changed
        if changed:
            try:
                self._save()
            except OSError:
                log.exception("cannot write %s", self.file)
            self.mc.publish()

    def _player(self, name: str) -> dict:
        return self.data["players"].setdefault(name, {"balance": 0, "earned": 0, "spent": 0, "bought": {}})

    def _add(self, p: dict, ts: float) -> bool:
        d = self.data
        event = p.get("event")
        if p.get("started"):
            d["pack_seen"] = ts
            if d["seed"]["plan"] is None:
                d["seed"]["plan"] = seed_plan(self.event_history(), ts)
        elif event == "catalog" and isinstance(p.get("items"), list):
            d["items"] = [{"id": i["id"], "name": str(i.get("name", i["id"])), "price": i["price"],
                           "desc": str(i.get("desc", ""))}
                          for i in p["items"]
                          if isinstance(i, dict) and isinstance(i.get("id"), str) and type(i.get("price")) is int]
            if isinstance(p.get("rewards"), dict):
                d["rewards"] = {str(k): v for k, v in p["rewards"].items() if type(v) is int}
            if isinstance(p.get("currency"), str):
                d["currency"] = p["currency"]
        elif event == "balances" and isinstance(p.get("players"), dict):
            # the world is right: whatever the portal missed (it was off, the log was cut) is corrected here
            for name, acc in p["players"].items():
                if isinstance(acc, dict) and type(acc.get("balance")) is int:
                    pl = self._player(str(name))
                    pl["balance"] = acc["balance"]
                    pl["earned"] = acc["earned"] if type(acc.get("earned")) is int else pl["earned"]
        elif event == "booking" and isinstance(p.get("player"), str) and type(p.get("delta")) is int:
            pl = self._player(p["player"])
            delta, reason = p["delta"], str(p.get("reason", ""))
            pl["balance"] = p["balance"] if type(p.get("balance")) is int else max(0, pl["balance"] + delta)
            if type(p.get("earned")) is int:
                pl["earned"] = p["earned"]
            detail = p.get("detail") if isinstance(p.get("detail"), str) else None
            if reason == "buy" and delta < 0:
                pl["spent"] += -delta
                if detail:
                    pl["bought"][detail] = pl["bought"].get(detail, 0) + 1
            if reason == "seed" and p["player"] not in d["seed"]["done"]:
                d["seed"]["done"].append(p["player"])
            d["ledger"].append({"at": ts, "player": p["player"], "delta": delta, "reason": reason,
                                "detail": detail, "balance": pl["balance"]})
            d["ledger"] = d["ledger"][-LEDGER_KEEP:]
        elif event == "seed_skipped" and isinstance(p.get("player"), str):
            if p["player"] not in d["seed"]["done"]:
                d["seed"]["done"].append(p["player"])
        else:
            return False
        d["updated"] = ts
        return True

    # ---------- start credit ----------

    def _seed_pending(self) -> dict[str, int]:
        seed = self.data["seed"]
        return {n: a for n, a in (seed["plan"] or {}).items() if n not in seed["done"]}

    def _console_ready(self) -> bool:
        return self.mc.status_word() == "online" and self.a.console_available()

    def send_seed(self) -> int:
        """Send the start credit that is not confirmed yet (at most once a minute); returns how many were sent.

        The pack books it once per player and answers every command with a line, so asking again is harmless.
        """
        pending = self._seed_pending()
        if not pending or time.time() - self._last_seed_try < SEED_RETRY_SECONDS or not self._console_ready():
            return 0
        self._last_seed_try = time.time()
        sent = 0
        for name, amount in pending.items():
            try:
                self.a.shop_seed_live(name, amount)
                sent += 1
            except Exception:
                log.exception("start credit for %s failed", name)
                break
        if sent:
            log.info("start credit sent for %d players", sent)
        return sent

    # ---------- api ----------

    def summary(self, admin: bool = False) -> dict:
        d = self.data
        if d["pack_seen"] is not None:
            self.send_seed()
        players = sorted(({"name": n, "balance": p["balance"], "earned": p["earned"], "spent": p["spent"],
                           "bought": p["bought"]} for n, p in d["players"].items()),
                         key=lambda p: (-p["balance"], -p["earned"], p["name"].lower()))
        out = {
            "installed": d["pack_seen"] is not None,
            "currency": d["currency"],
            "items": [{**i, "icon": f"/api/features/icons/{i['id'].replace(':', '.')}.png"} for i in d["items"]],
            "rewards": d["rewards"],
            "players": players,
            "updated": d["updated"],
        }
        if admin:
            plan = d["seed"]["plan"] or {}
            out["ledger"] = list(reversed(d["ledger"][-LEDGER_SHOW:]))
            out["seed"] = {"planned": plan, "pending": sorted(self._seed_pending())}
            out["grant_max"] = SHOP_GRANT_MAX
        return out

    async def grant(self, player: str, amount: int, user: str) -> None:
        """Sterntaler by hand: positive gives, negative takes (never below 0 - the pack sees to that)."""
        player = player.strip()
        if not valid_player_name(player):
            raise PortalError("Ungültiger Spielername", 400)
        if type(amount) is not int or amount == 0 or abs(amount) > SHOP_GRANT_MAX:
            raise PortalError(f"Betrag muss zwischen 1 und {SHOP_GRANT_MAX} liegen (mit Minus zum Abziehen).", 400)
        if self.data["pack_seen"] is None:
            raise PortalError("Das Sterntaler-Pack hat sich noch nicht gemeldet.", 409)
        if self.mc.status_word() != "online":
            raise PortalError("Der Server ist nicht online.", 409)
        if not self.a.console_available():
            raise PortalError("Server-Konsole nicht verfügbar.", 409)
        try:
            await asyncio.to_thread(self.a.shop_grant_live, player, amount)
        except Exception as e:
            self.audit.write("STERNTALER", "FAILED", user, player=player, value=amount, error=str(e))
            raise PortalError(f"Befehl fehlgeschlagen: {e}", 500)
        self.audit.write("STERNTALER", "SUCCESS", user, player=player, value=amount)
