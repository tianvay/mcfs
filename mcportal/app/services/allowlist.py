"""Allowlist (whitelist) management with backup before every change.

While the server runs, changes go through the server console so the server
updates its own file and memory. While it is stopped, the file is edited directly.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from pathlib import Path

from ..adapters.base import MinecraftAdapter
from ..adapters.bedrock.commands import valid_player_name
from ..adapters.bedrock.logparse import LogLine, parse_spawned
from ..audit import AuditLog
from .minecraft import MinecraftService, PortalError

log = logging.getLogger("mcportal.allowlist")
CONFIRM_TIMEOUT = 6.0
SPAWN_SETTLE = 2.0  # seconds after "Player Spawned" before the gamemode command


class AllowlistService:
    def __init__(self, adapter: MinecraftAdapter, mc: MinecraftService, audit: AuditLog,
                 backup_dir: Path, keep: int, pending_file: Path):
        self.a = adapter
        self.mc = mc
        self.audit = audit
        self.backup_dir = backup_dir
        self.keep = keep
        # players whose operator status was revoked while they were offline:
        # they are set to survival as soon as they appear in the world again
        self.pending_file = pending_file
        self.pending_survival: dict[str, str] = self._load_pending()  # lower name -> name
        mc.line_listeners.append(self._on_line)

    def mode(self, file: str = "allowlist.json") -> tuple[str, str | None]:
        """("live" | "file" | "blocked", reason) for changes to `file`."""
        writable = (self.a.files.allowlist_writable() if file == "allowlist.json"
                    else self.a.files.permissions_writable())
        state = self.mc.unit.active_state if self.mc.unit else "unknown"
        if state == "active":
            if not self.a.console_available():
                return "blocked", ("Der Server läuft, aber die Server-Konsole ist noch nicht eingerichtet (M2). "
                                   "Änderungen sind bis dahin nur bei gestopptem Server möglich.")
            # permissions.json is always edited by the portal, then reloaded by the server
            if file != "allowlist.json" and not writable:
                return "blocked", f"Keine Schreibrechte auf {file}."
            return "live", None
        if state in ("inactive", "failed"):
            if writable:
                return "file", None
            return "blocked", f"Keine Schreibrechte auf {file}."
        return "blocked", "Der Server startet oder stoppt gerade."

    def list(self) -> dict:
        try:
            entries = self.a.files.read_allowlist()
        except (OSError, ValueError) as e:
            raise PortalError(f"allowlist.json kann nicht gelesen werden: {e}", 500)
        ops = self.a.files.operator_xuids()
        online = {p.lower() for p in (pl.name for pl in self.mc.tracker.players.values())}
        mode, reason = self.mode()
        op_mode, op_reason = self.mode("permissions.json")
        return {
            "op_mode": op_mode,
            "op_reason": op_reason,
            "entries": [
                {
                    "name": e.get("name", ""),
                    "xuid": e.get("xuid", ""),
                    "operator": bool(e.get("xuid")) and str(e.get("xuid")) in ops,
                    "online": e.get("name", "").lower() in online,
                    "survival_pending": e.get("name", "").lower() in self.pending_survival,
                }
                for e in entries
            ],
            "mode": mode,
            "reason": reason,
        }

    async def add(self, name: str, user: str) -> None:
        name = name.strip()
        if not valid_player_name(name):
            raise PortalError("Ungültiger Spielername (erlaubt: Buchstaben, Ziffern, Leerzeichen, _ und -, max. 32 Zeichen).")
        await self._change("WHITELIST_ADD", name, user, add=True)

    async def remove(self, name: str, user: str) -> None:
        await self._change("WHITELIST_REMOVE", name, user, add=False)

    async def set_operator(self, name: str, operator: bool, user: str) -> None:
        action = "OPERATOR_GRANT" if operator else "OPERATOR_REVOKE"
        await self._locked(action, name, user, lambda: self._do_set_operator(name, operator, user))

    async def _do_set_operator(self, name: str, operator: bool, user: str) -> str:
        files = self.a.files
        entry = next((e for e in files.read_allowlist() if e.get("name", "").lower() == name.lower()), None)
        if entry is None:
            raise PortalError(f"{name} steht nicht auf der Whitelist.", 404)
        name, xuid = entry["name"], str(entry.get("xuid") or "")
        if not xuid:
            raise PortalError(f"{name} war noch nie auf dem Server. Operator-Rechte sind erst nach der "
                              "ersten Verbindung möglich (der Server kennt die Xbox-ID dann).", 409)
        perms = files.read_permissions()
        is_op = any(str(p.get("xuid")) == xuid and p.get("permission") == "operator" for p in perms)
        if is_op == operator:
            raise PortalError(f"{name} ist bereits {'Operator' if operator else 'kein Operator'}.", 409)

        mode, reason = self.mode("permissions.json")
        if mode == "blocked":
            raise PortalError(reason or "Änderung derzeit nicht möglich.", 409)

        backup = await asyncio.to_thread(self._backup, "operator", files.permissions)
        # Revoke = explicit "member" so an in-game /op stored elsewhere cannot win.
        new = [p for p in perms if str(p.get("xuid")) != xuid]
        new.append({"permission": "operator" if operator else "member", "xuid": xuid})
        try:
            await asyncio.to_thread(files.write_permissions, new)
        except Exception as e:
            await asyncio.to_thread(shutil.copyfile, backup / files.permissions.name, files.permissions)
            raise PortalError(f"Schreiben fehlgeschlagen, Sicherung wiederhergestellt: {e}", 500)
        if mode == "live":
            await asyncio.to_thread(self.a.permissions_reload_live)
        if operator:
            self._set_pending(name, False)
        else:
            await self._force_survival(name, user)
        return name

    # ---------- revoked operators go back to survival ----------

    async def _force_survival(self, name: str, user: str) -> None:
        """Set survival now if the player is in the world, otherwise on their next spawn."""
        online = name.lower() in {p.name.lower() for p in self.mc.tracker.players.values()}
        if online and self.a.console_available():
            try:
                await asyncio.to_thread(self.a.set_survival_live, name)
                self._set_pending(name, False)
                self.audit.write("GAMEMODE_SURVIVAL", "SUCCESS", user, player=name)
                return
            except Exception as e:
                log.warning("gamemode survival for %s failed, will retry on spawn: %s", name, e)
        self._set_pending(name, True)
        self.audit.write("GAMEMODE_SURVIVAL", "PENDING", user, player=name)

    def _on_line(self, line: LogLine) -> None:
        name = parse_spawned(line)
        if name and name.lower() in self.pending_survival:
            asyncio.get_running_loop().create_task(self._apply_pending(name))

    async def _apply_pending(self, name: str) -> None:
        await asyncio.sleep(SPAWN_SETTLE)
        try:
            await asyncio.to_thread(self.a.set_survival_live, name)
        except Exception as e:
            log.warning("gamemode survival for %s on spawn failed: %s", name, e)
            self.audit.write("GAMEMODE_SURVIVAL", "FAILED", "portal", player=name, error=str(e))
            return
        self._set_pending(name, False)
        self.audit.write("GAMEMODE_SURVIVAL", "SUCCESS", "portal", player=name, note="beim Betreten")
        self.mc.publish()

    def _load_pending(self) -> dict[str, str]:
        try:
            names = json.loads(self.pending_file.read_text(encoding="utf-8"))
            return {n.lower(): n for n in names if isinstance(n, str)}
        except (OSError, ValueError):
            return {}

    def _set_pending(self, name: str, pending: bool) -> None:
        if pending:
            self.pending_survival[name.lower()] = name
        else:
            self.pending_survival.pop(name.lower(), None)
        try:
            self.pending_file.write_text(json.dumps(sorted(self.pending_survival.values())), encoding="utf-8")
        except OSError:
            log.exception("cannot write %s", self.pending_file)

    async def _change(self, action: str, name: str, user: str, add: bool) -> None:
        await self._locked(action, name, user, lambda: self._do_change(action, name, add))

    async def _locked(self, action: str, name: str, user: str, work) -> None:
        """Run one change under the global operation lock and record it in the audit log."""
        if self.mc.op_lock.locked():
            raise PortalError(f"Es läuft bereits eine Aktion: {self.mc.busy}", 409)
        async with self.mc.op_lock:
            try:
                name = await work()
            except PortalError as e:
                self.audit.write(action, "FAILED", user, player=name, error=str(e))
                raise
            self.audit.write(action, "SUCCESS", user, player=name)
            await asyncio.to_thread(self.mc.refresh_allowlist_count)
            self.mc.publish()

    async def _do_change(self, action: str, name: str, add: bool) -> str:
        """Apply the change; returns the player name as stored in the allowlist."""
        files = self.a.files
        entries = files.read_allowlist()
        present = [e for e in entries if e.get("name", "").lower() == name.lower()]
        if add and present:
            raise PortalError(f"{name} steht bereits auf der Whitelist.", 409)
        if not add and not present:
            raise PortalError(f"{name} steht nicht auf der Whitelist.", 404)
        if not add:
            name = present[0]["name"]  # exact spelling for the server command

        mode, reason = self.mode()
        if mode == "blocked":
            raise PortalError(reason or "Änderung derzeit nicht möglich.", 409)

        backup = await asyncio.to_thread(self._backup, "allowlist_add" if add else "allowlist_remove", files.allowlist)

        if mode == "live":
            if add:
                await asyncio.to_thread(self.a.allowlist_add_live, name)
            else:
                await asyncio.to_thread(self.a.allowlist_remove_live, name)
            if not await self._confirmed(name, add):
                raise PortalError("Der Server hat die Änderung nicht bestätigt. Bitte Whitelist prüfen "
                                  f"(Sicherung: {backup.name}).", 502)
            return name

        new = entries + [{"ignoresPlayerLimit": False, "name": name}] if add else \
            [e for e in entries if e.get("name", "").lower() != name.lower()]
        try:
            await asyncio.to_thread(files.write_allowlist, new)
        except Exception as e:
            await asyncio.to_thread(shutil.copyfile, backup / "allowlist.json", files.allowlist)
            raise PortalError(f"Schreiben fehlgeschlagen, Sicherung wiederhergestellt: {e}", 500)
        return name

    async def _confirmed(self, name: str, add: bool) -> bool:
        deadline = time.monotonic() + CONFIRM_TIMEOUT
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            try:
                names = {e.get("name", "").lower() for e in self.a.files.read_allowlist()}
            except (OSError, ValueError):
                continue
            if (name.lower() in names) == add:
                return True
        return False

    def _backup(self, kind: str, source: Path) -> Path:
        stamp = time.strftime('%Y-%m-%d_%H-%M-%S') + f".{int(time.time() * 1000) % 1000:03d}"
        target = self.backup_dir / f"{stamp}_pre_{kind}"
        target.mkdir(parents=True, exist_ok=False)
        shutil.copy2(source, target / source.name)
        group = kind.split("_")[0]  # "allowlist" or "operator" - each keeps its own last N
        old = sorted(p for p in self.backup_dir.glob(f"*_pre_{group}*") if p.is_dir())
        for p in old[:-self.keep] if self.keep > 0 else []:
            shutil.rmtree(p, ignore_errors=True)
        return target
