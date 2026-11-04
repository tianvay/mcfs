"""Tab "Spenden": the admin gives a player (or everybody online) items.

The catalog (items.json, English names) is built by tools/make_item_catalog.py from Mojang's bedrock-samples.
Only ids from it can be given - the console command is never built from free text. After "give" the portal
watches the server log for the game's answer, so an item the world does not know is reported as an error.

The item pictures are Mojang's own textures from the same repository. They are not in this (public)
repository: the portal fetches each one the first time somebody looks at it and keeps it in
/var/lib/mcportal/item-icons/<release>/. Until then (or without internet) the page shows a placeholder.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import threading
import time
import urllib.request
from pathlib import Path

from ..adapters.base import MinecraftAdapter
from ..adapters.bedrock.commands import valid_player_name
from ..adapters.bedrock.logparse import LogLine
from ..audit import AuditLog
from .minecraft import MinecraftService, PortalError

log = logging.getLogger("mcportal.donate")

SAMPLES_TAG = "v1.26.60.5"  # release of Mojang/bedrock-samples the catalog and pictures come from
ICON_SOURCE = f"https://raw.githubusercontent.com/Mojang/bedrock-samples/{SAMPLES_TAG}/resource_pack/textures/{{}}.png"
CATALOG_FILE = Path(__file__).with_name("items.json")
ALL_ONLINE = "@a"
MAX_AMOUNT = 999
MAX_STACKS = 36  # a full inventory
ICON_MAX_BYTES = 256 * 1024
ICON_RETRY_SECONDS = 3600  # a picture that failed is tried again after an hour
ICON_PARALLEL = 4
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
USER_AGENT = "mcportal (family server portal)"
ANSWER_SECONDS = 4.0  # how long to wait for the server's answer to "give"
_GAVE = re.compile(r"\bGave\b")
_REFUSED = re.compile(r"Syntax error|No targets matched|Unknown (item|command)|Could not|cannot be", re.I)

CATEGORIES = [
    ("popular", "Beliebt"), ("tools", "Werkzeug & Waffen"), ("armor", "Rüstung"), ("food", "Essen"),
    ("blocks", "Blöcke"), ("valuable", "Wertvoll"), ("spawn", "Spawn-Eier"), ("misc", "Sonstiges"),
]
_ITEM_ID = re.compile(r"^[a-z0-9_]{1,40}$")


def _load_catalog() -> dict[str, dict]:
    try:
        data = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:  # only while tools/make_item_catalog.py builds it
        return {}
    return {i["id"]: i for i in data["items"] if _ITEM_ID.match(i["id"])}


CATALOG = _load_catalog()


def max_amount(item: dict) -> int:
    return min(MAX_AMOUNT, item["stack"] * MAX_STACKS)


class DonateService:
    def __init__(self, adapter: MinecraftAdapter, mc: MinecraftService, audit: AuditLog, data_dir: Path):
        self.a = adapter
        self.mc = mc
        self.audit = audit
        self.icon_root = data_dir / "item-icons"
        self.icon_dir = self.icon_root / SAMPLES_TAG
        self._failed: dict[str, float] = {}
        self._fetch_locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._fetch_slots = threading.Semaphore(ICON_PARALLEL)
        self._give_lock = asyncio.Lock()
        self._answer: asyncio.Future | None = None
        mc.line_listeners.append(self._on_line)
        self._items_public = [
            {"id": i["id"], "name": i["name"], "cat": i["cat"], "stack": i["stack"], "popular": i["popular"],
             "max": max_amount(i), "icon": bool(i.get("texture"))}
            for i in CATALOG.values()]

    async def startup(self) -> None:
        await asyncio.to_thread(self._clean_old_icons)

    def _clean_old_icons(self) -> None:
        """Pictures of an older release (or of the first version of this tab) are not needed any more."""
        if not self.icon_root.is_dir():
            return
        for p in self.icon_root.iterdir():
            if p.name == SAMPLES_TAG:
                continue
            try:
                shutil.rmtree(p) if p.is_dir() else p.unlink()
            except OSError:
                log.warning("cannot remove %s", p)

    # ---------- icons ----------

    def icon_path(self, item_id: str) -> Path:
        """Path of the picture, fetched from Mojang's repository on first use (runs in a worker thread)."""
        item = CATALOG.get(item_id)
        if item is None or not item.get("texture"):
            raise PortalError("Kein Bild für dieses Item", 404)
        texture = item["texture"]
        path = self.icon_dir / (texture.replace("/", "__") + ".png")
        if path.exists():
            return path
        if time.time() - self._failed.get(texture, 0) < ICON_RETRY_SECONDS:
            raise PortalError("Bild nicht verfügbar", 404)
        with self._locks_guard:
            lock = self._fetch_locks.setdefault(texture, threading.Lock())
        with lock, self._fetch_slots:
            if path.exists():  # another request fetched it meanwhile
                return path
            try:
                req = urllib.request.Request(ICON_SOURCE.format(texture), headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = r.read(ICON_MAX_BYTES + 1)
                if len(data) > ICON_MAX_BYTES or not data.startswith(PNG_MAGIC):
                    raise ValueError("kein passendes PNG")
                self.icon_dir.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(data)
                tmp.replace(path)
                return path
            except Exception as e:  # no internet, renamed texture ... - the page shows a placeholder
                self._failed[texture] = time.time()
                log.warning("item picture %s not loaded: %s", texture, e)
                raise PortalError("Bild nicht verfügbar", 404) from e

    # ---------- catalog / history ----------

    def summary(self) -> dict:
        online = sorted(self.mc.tracker.players.values(), key=lambda p: p.name.lower())
        online_names = {p.name.lower() for p in online}
        offline = []
        try:
            offline = sorted({e.get("name", "") for e in self.a.files.read_allowlist()
                              if e.get("name") and e["name"].lower() not in online_names}, key=str.lower)
        except (OSError, ValueError):
            pass
        recent = [{"time": e["time"], "player": e.get("player"), "item": e.get("item"), "count": e.get("count")}
                  for e in self.audit.tail(200) if e.get("action") == "DONATE" and e.get("result") == "SUCCESS"][:8]
        return {
            "online": [p.name for p in online],
            "offline": offline,
            "console": self.a.console_available(),
            "categories": [{"id": c, "name": n} for c, n in CATEGORIES],
            "items": self._items_public,
            "recent": recent,
        }

    # ---------- the server's answer ----------

    def _on_line(self, line: LogLine) -> None:
        fut = self._answer
        if fut is None or fut.done() or line.source != "server":
            return
        msg = line.message
        if _GAVE.search(msg):
            fut.set_result(None)
        elif _REFUSED.search(msg):
            fut.set_result(msg.strip()[:200])

    # ---------- give ----------

    async def give(self, player: str, item_id: str, count: int, user: str) -> dict:
        item = CATALOG.get(item_id) if _ITEM_ID.match(item_id or "") else None
        if item is None:
            raise PortalError("Unbekanntes Item")
        if not 1 <= count <= max_amount(item):
            raise PortalError(f"Menge muss zwischen 1 und {max_amount(item)} liegen")
        online = {p.name.lower(): p.name for p in self.mc.tracker.players.values()}
        if player == ALL_ONLINE:
            if not online:
                raise PortalError("Gerade ist niemand online", 409)
            target, shown = ALL_ONLINE, "alle online"
        else:
            if not valid_player_name(player):
                raise PortalError("Ungültiger Spielername")
            if player.lower() not in online:
                raise PortalError(f"{player} ist nicht online – Geschenke gehen nur an Spieler im Spiel", 409)
            target = shown = online[player.lower()]
        if not self.a.console_available():
            raise PortalError("Die Server-Konsole ist nicht erreichbar (Server aus?)", 409)

        async with self._give_lock:  # one at a time, so the answer in the log belongs to this gift
            self._answer = asyncio.get_running_loop().create_future()
            try:
                await asyncio.to_thread(self.a.give_live, target, item["id"], count)
                refused = await asyncio.wait_for(self._answer, ANSWER_SECONDS)
                confirmed = True
            except asyncio.TimeoutError:
                refused, confirmed = None, False  # older servers may not echo console commands
            except Exception as e:
                self.audit.write("DONATE", "FAILED", user, player=shown, item=item["id"], count=count, error=str(e))
                raise PortalError(f"Spenden fehlgeschlagen: {e}", 500) from e
            finally:
                self._answer = None
        if refused:
            self.audit.write("DONATE", "FAILED", user, player=shown, item=item["id"], count=count, error=refused)
            raise PortalError(f"Minecraft hat {item['name']} abgelehnt: {refused}", 422)
        try:
            await asyncio.to_thread(self.a.tell_gift_live, target, item["name"], count)
        except Exception as e:  # the items arrived; only the chat line is missing
            log.warning("gift message not sent: %s", e)
        self.audit.write("DONATE", "SUCCESS", user, player=shown, item=item["id"], count=count,
                         note=None if confirmed else "ohne Rückmeldung des Servers")
        return {"player": shown, "item": item["id"], "name": item["name"], "count": count, "confirmed": confirmed}
