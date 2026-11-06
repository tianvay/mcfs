"""Switch the server's features (= behavior packs of the world, with the resource packs they need) on and off.

Switching only edits world_behavior_packs.json / world_resource_packs.json (in place, backup first); the pack
folders stay in the world. Bedrock reads the lists at start, so a change takes effect with the next restart.
Which packs really run is taken from the "Pack Stack" lines Bedrock logs at every start.

A feature = one behavior pack plus every resource pack it depends on (manifest "dependencies"). Resource packs
nobody depends on are features of their own. Nothing is hard-wired: new packs in the world show up by themselves.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import time
from pathlib import Path

from ..adapters.base import MinecraftAdapter
from ..adapters.bedrock.logparse import LogLine, parse_version
from ..audit import AuditLog
from .minecraft import MinecraftService, PortalError

log = logging.getLogger("mcportal.packs")

PACK_STACK_RE = re.compile(r"Pack Stack - \[\d+\] .*\(id: (?P<uuid>[0-9a-fA-F-]{36}), version: [\d.]+\)")
BACKUPS_KEEP = 20
FEATURE_RE = re.compile(r"[a-z0-9_]{1,64}")
ITEM_ICON_RE = re.compile(r"[a-z0-9_]{1,32}\.[a-z0-9_]{1,64}")


def _label(name: str) -> str:
    for prefix in ("Family Portal ", "mcportal "):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def group_features(packs: list[dict]) -> list[dict]:
    """[{id, name, description, packs: [pack, ...], items, entities}] - behavior packs first, in folder order."""
    by_uuid = {p["uuid"]: p for p in packs}
    used: set[str] = set()
    features = []
    for bp in (p for p in packs if p["kind"] == "behavior"):
        members = [bp] + [by_uuid[u] for u in bp["depends"] if u in by_uuid and by_uuid[u]["kind"] == "resource"]
        used.update(m["uuid"] for m in members)
        features.append(members)
    features += [[rp] for rp in packs if rp["kind"] == "resource" and rp["uuid"] not in used]
    return [{
        "id": m[0]["folder"],
        "name": _label(m[0]["name"]),
        "description": m[0]["description"],
        "packs": m,
        "items": any(p["items"] for p in m),
        "entities": any(p["entities"] for p in m),
    } for m in features]


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def custom_items(packs: list[dict]) -> dict[str, dict]:
    """Own items of these packs: "mcfs:waypoint" -> {name, png} (picture from the resource packs, if any)."""
    textures: dict[str, Path] = {}
    for rp in (p for p in packs if p["kind"] == "resource"):
        try:
            data = _json(rp["path"] / "textures" / "item_texture.json").get("texture_data", {})
        except (OSError, ValueError, AttributeError):
            continue
        root = rp["path"].resolve()
        for key, entry in data.items():
            tex = entry.get("textures") if isinstance(entry, dict) else None
            tex = tex[0] if isinstance(tex, list) and tex else tex
            if isinstance(tex, str):
                png = (rp["path"] / f"{tex}.png").resolve()
                if png.is_relative_to(root) and png.is_file():   # nothing outside the pack folder
                    textures[key] = png
    items: dict[str, dict] = {}
    for bp in (p for p in packs if p["kind"] == "behavior"):
        for f in sorted((bp["path"] / "items").glob("*.json")) if (bp["path"] / "items").is_dir() else []:
            try:
                item = _json(f)["minecraft:item"]
                ident = str(item["description"]["identifier"])
                comp = item.get("components", {})
                name = comp.get("minecraft:display_name", {}).get("value") or ident
                icon = comp.get("minecraft:icon")
                icon = icon.get("texture") if isinstance(icon, dict) else icon
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                continue
            items[ident] = {"name": str(name), "png": textures.get(str(icon)) if icon else None}
    return items


def _item(ident: str, own: dict[str, dict], count: int = 1) -> dict:
    """An ingredient or result as the page shows it: name and picture URL (None = placeholder)."""
    from .donate import CATALOG   # same item names and pictures as the "Spenden" tab
    if ident in own:
        icon = f"/api/features/icons/{ident.replace(':', '.')}.png" if own[ident]["png"] else None
        return {"id": ident, "name": own[ident]["name"], "icon": icon, "count": count, "own": True}
    short = ident.removeprefix("minecraft:")
    known = CATALOG.get(short)
    return {
        "id": ident,
        "name": known["name"] if known else short.replace("_", " ").capitalize(),
        "icon": f"/api/donate/icons/{short}.png" if known and known.get("texture") else None,
        "count": count,
        "own": False,
    }


def _ingredient(entry, own: dict[str, dict]) -> dict | None:
    if isinstance(entry, str):
        return _item(entry, own)
    if isinstance(entry, dict) and isinstance(entry.get("item"), str):
        return _item(entry["item"], own, int(entry.get("count", 1)))
    if isinstance(entry, dict) and isinstance(entry.get("tag"), str):
        return {"id": entry["tag"], "name": entry["tag"], "icon": None, "count": 1, "own": False}
    return None


def recipes(packs: list[dict], own: dict[str, dict]) -> list[dict]:
    """Crafting recipes of these packs: {result, grid (rows of ingredient|None), shapeless}."""
    out = []
    for bp in (p for p in packs if p["kind"] == "behavior"):
        folder = bp["path"] / "recipes"
        for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            try:
                data = _json(f)
                if "minecraft:recipe_shaped" in data:
                    r = data["minecraft:recipe_shaped"]
                    key = {k: _ingredient(v, own) for k, v in r["key"].items()}
                    grid = [[key.get(ch) if ch != " " else None for ch in row] for row in r["pattern"]]
                    shapeless = False
                elif "minecraft:recipe_shapeless" in data:
                    r = data["minecraft:recipe_shapeless"]
                    cells = [_ingredient(v, own) for v in r["ingredients"]]
                    grid = [cells[i:i + 3] for i in range(0, len(cells), 3)]
                    shapeless = True
                else:
                    continue
                res = r["result"]
                res = res[0] if isinstance(res, list) else res
                result = _item(res["item"], own, int(res.get("count", 1))) if isinstance(res, dict) else _item(res, own)
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                continue
            out.append({"result": result, "grid": grid, "shapeless": shapeless})
    return out


class PacksService:
    def __init__(self, adapter: MinecraftAdapter, mc: MinecraftService, audit: AuditLog, data_dir: Path,
                 backup_dir: Path):
        self.a = adapter
        self.mc = mc
        self.audit = audit
        self.backup_dir = backup_dir / "packs"
        self.state_file = data_dir / "packs.json"
        # last change per feature (unix time) - tells "waits for a restart" from "did not start"
        self.changed: dict[str, float] = self._load_state()
        self.lock = asyncio.Lock()
        # uuids of the behavior packs in the "Pack Stack" of the current server run
        self.stack: set[str] = set()
        self.stack_complete = False   # "Server started." seen after the stack
        mc.line_listeners.append(self._on_line)
        mc.extras["packs"] = self.status_extra

    # ---------- log ----------

    async def startup(self) -> None:
        u = self.mc.unit
        if u and u.active_state == "active" and u.started_at:
            lines = await asyncio.to_thread(self.a.read_log, u.started_at - 2)
            for line in lines:
                self._on_line(line)

    def _on_line(self, line: LogLine) -> None:
        if line.source != "server":
            return
        if parse_version(line):   # first line of every server start
            self.stack, self.stack_complete = set(), False
            return
        m = PACK_STACK_RE.search(line.message)
        if m:
            self.stack.add(m.group("uuid").lower())
        elif line.message.startswith("Server started."):
            self.stack_complete = True
            self.mc.publish()

    def _running_known(self) -> bool:
        return self.stack_complete and self.mc.status_word() == "online"

    # ---------- state ----------

    def _load_state(self) -> dict[str, float]:
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return {str(k): float(v) for k, v in data.get("changed", {}).items()}
        except (OSError, ValueError, AttributeError, TypeError):
            return {}

    def _save_state(self) -> None:
        try:
            self.state_file.write_text(json.dumps({"changed": self.changed}), encoding="utf-8")
        except OSError:
            log.warning("cannot write %s", self.state_file)

    def _features(self) -> list[dict]:
        packs = self.a.files.installed_packs()
        enabled = {
            kind: {str(e.get("pack_id", "")).lower() for e in self.a.files.read_world_packs(kind)}
            for kind in ("behavior", "resource")
        }
        known = self._running_known()
        started = self.mc.unit.started_at if self.mc.unit else None
        out = []
        for f in group_features(packs):
            lead = f["packs"][0]
            on = lead["uuid"].lower() in enabled[lead["kind"]]
            complete = all(p["uuid"].lower() in enabled[p["kind"]] for p in f["packs"])
            state = "on" if on else "off"
            if known and lead["kind"] == "behavior":
                running = lead["uuid"].lower() in self.stack
                if on and not running:
                    changed = self.changed.get(f["id"], 0.0)
                    state = "pending_on" if not started or changed > started else "failed"
                elif not on and running:
                    state = "pending_off"
            out.append({
                "id": f["id"],
                "name": f["name"],
                "description": f["description"],
                "enabled": on,
                "complete": complete or not on,
                "state": state,
                "items": f["items"],
                "entities": f["entities"],
                "packs": [{"folder": p["folder"], "kind": p["kind"], "name": p["name"],
                           "version": ".".join(map(str, p["version"]))} for p in f["packs"]],
                "_packs": f["packs"],
            })
        return out

    @staticmethod
    def _with_recipes(f: dict) -> dict:
        own = custom_items(f["_packs"])
        out = {k: v for k, v in f.items() if k != "_packs"}
        out["recipes"] = recipes(f["_packs"], own)
        return out

    def public(self) -> dict:
        """For everyone (tab "Funktionen"): only what runs, with the recipes of its own items."""
        try:
            features = self._features()
        except (OSError, ValueError) as e:
            raise PortalError(f"Pack-Listen der Welt nicht lesbar: {e}", 500)
        keep = ("id", "name", "description", "items", "entities", "recipes")
        return {"features": [{k: v for k, v in self._with_recipes(f).items() if k in keep}
                             for f in features if f["state"] in ("on", "pending_off")]}

    def icon_path(self, name: str) -> Path:
        """Picture of an own item of a running feature ("mcfs.waypoint" = mcfs:waypoint)."""
        if not ITEM_ICON_RE.fullmatch(name):
            raise PortalError("Unbekanntes Item", 404)
        ident = name.replace(".", ":", 1)
        for f in self._features():
            if f["state"] in ("on", "pending_off"):
                item = custom_items(f["_packs"]).get(ident)
                if item and item["png"]:
                    return item["png"]
        raise PortalError("Kein Bild für dieses Item", 404)

    def summary(self) -> dict:
        try:
            features = self._features()
        except (OSError, ValueError) as e:
            raise PortalError(f"Pack-Listen der Welt nicht lesbar: {e}", 500)
        return {
            "features": [self._with_recipes(f) for f in features],
            "writable": self.a.files.world_packs_writable(),
            "running_known": self._running_known(),
            "restart_needed": any(f["state"] in ("pending_on", "pending_off") for f in features),
        }

    def status_extra(self) -> dict:
        """Public part of the status: which features are not active (the UI greys out their tabs)."""
        try:
            features = self._features()
        except (OSError, ValueError):
            return {"off": [], "restart_needed": False}
        return {
            "off": sorted(f["id"] for f in features if f["state"] in ("off", "pending_on", "failed")),
            "restart_needed": any(f["state"] in ("pending_on", "pending_off") for f in features),
        }

    def active(self, feature: str) -> bool:
        """Is the feature running (or, while that is unknown, switched on)?"""
        try:
            for f in self._features():
                if f["id"] == feature:
                    return f["state"] in ("on", "pending_off")
        except (OSError, ValueError):
            return True   # do not block anything because of a read error
        return False

    # ---------- switching ----------

    async def set_enabled(self, feature: str, enabled: bool, user: str) -> dict:
        if not FEATURE_RE.fullmatch(feature):
            raise PortalError("Unbekannte Funktion", 404)
        if self.mc.op_lock.locked():
            raise PortalError(f"Es läuft gerade eine Aktion: {self.mc.busy}", 409)
        async with self.lock:
            await asyncio.to_thread(self._switch, feature, enabled, user)
        self.mc.publish()
        return self.summary()

    def _switch(self, feature: str, enabled: bool, user: str) -> None:
        features = {f["id"]: f for f in group_features(self.a.files.installed_packs())}
        f = features.get(feature)
        if not f:
            raise PortalError("Unbekannte Funktion", 404)
        if not self.a.files.world_packs_writable():
            raise PortalError("Keine Schreibrechte auf die Pack-Listen der Welt (deploy/install.sh ausführen).", 403)
        lists = {kind: self.a.files.read_world_packs(kind) for kind in ("behavior", "resource")}
        backup = self._backup()
        try:
            for kind in ("behavior", "resource"):
                members = [p for p in f["packs"] if p["kind"] == kind]
                if not members:
                    continue
                uuids = {p["uuid"].lower() for p in members}
                entries = [e for e in lists[kind] if str(e.get("pack_id", "")).lower() not in uuids]
                if enabled:
                    # resource packs before the behavior pack that needs them is not required by Bedrock;
                    # appending keeps the order of everything else unchanged
                    entries += [{"pack_id": p["uuid"], "version": p["version"]} for p in members]
                if entries != lists[kind]:
                    self.a.files.write_world_packs(kind, entries)
        except Exception as e:
            self._restore(backup)
            self.audit.write("PACK_ON" if enabled else "PACK_OFF", "FAILED", user, feature=f["name"], error=str(e))
            raise PortalError(f"Pack-Liste konnte nicht geschrieben werden: {e}", 500)
        self.changed[feature] = time.time()
        self._save_state()
        self.audit.write("PACK_ON" if enabled else "PACK_OFF", "SUCCESS", user, feature=f["name"])
        log.info("%s %s by %s (backup %s)", feature, "on" if enabled else "off", user, backup)

    def _backup(self) -> Path:
        target = self.backup_dir / time.strftime("%Y-%m-%d_%H-%M-%S")
        n = 1
        while target.exists():
            n += 1
            target = target.with_name(f"{target.name.split('.')[0]}.{n}")
        target.mkdir(parents=True)
        for kind in ("behavior", "resource"):
            src = self.a.files.world_packs_file(kind)
            if src.exists():
                shutil.copy2(src, target / src.name)
        old = sorted(p for p in self.backup_dir.iterdir() if p.is_dir())
        for p in old[:-BACKUPS_KEEP]:
            shutil.rmtree(p, ignore_errors=True)
        return target

    def _restore(self, backup: Path) -> None:
        for kind in ("behavior", "resource"):
            saved = backup / f"world_{kind}_packs.json"
            if saved.exists():
                try:
                    self.a.files.write_world_packs(kind, json.loads(saved.read_text(encoding="utf-8") or "[]"))
                except Exception:
                    log.exception("restore of %s failed - backup in %s", saved.name, backup)
