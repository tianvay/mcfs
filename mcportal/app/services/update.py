"""Server update at the push of a button - with backup before, verification after and automatic rollback.

Order: download + verify while the server keeps running, then stop -> backup ->
apply -> verify that allowlist/permissions/server.properties are unchanged ->
start -> wait for the new version. Any failure after files were touched rolls
back to the backup taken just before.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from pathlib import Path

from ..adapters.base import MinecraftAdapter
from ..adapters.bedrock.release import Release, version_key
from ..audit import AuditLog
from .minecraft import MinecraftService, PortalError

log = logging.getLogger("mcportal.update")

STEPS = [
    ("prepare", "Vorbereitung"),
    ("download", "Neue Version herunterladen"),
    ("verify", "Download prüfen"),
    ("announce", "Spieler informieren"),
    ("stop", "Server stoppen"),
    ("backup", "Backup erstellen"),
    ("apply", "Dateien aktualisieren"),
    ("preserved", "Whitelist & Operatoren prüfen"),
    ("start", "Server starten"),
    ("check", "Serverstatus prüfen"),
]
ROLLBACK_STEPS = [
    ("rb_stop", "Rollback: Server stoppen"),
    ("rb_restore", "Rollback: Backup zurückspielen"),
    ("rb_start", "Rollback: alte Version starten"),
]
MIN_FREE_BYTES = 1500 * 1024 * 1024
START_TIMEOUT = 180
CHECK_INTERVAL = 6 * 3600
ANNOUNCE_WAIT = 15


class UpdateService:
    def __init__(self, adapter: MinecraftAdapter, mc: MinecraftService, audit: AuditLog,
                 data_dir: Path, backup_dir: Path, keep_backups: int):
        self.a = adapter
        self.mc = mc
        self.audit = audit
        self.staging = data_dir / "staging"
        self.backup_dir = backup_dir
        self.keep = max(1, keep_backups)
        self.latest: Release | None = None
        self.checked_at: float | None = None
        self.check_error: str | None = None
        self.job: dict | None = None
        self._tasks: list[asyncio.Task] = []
        mc.extras["update"] = self.info

    # ---------- lifecycle / version check ----------

    async def startup(self) -> None:
        self._tasks.append(asyncio.create_task(self._check_loop()))

    async def shutdown(self) -> None:
        for t in self._tasks:
            t.cancel()

    async def _check_loop(self) -> None:
        await asyncio.sleep(15)
        while True:
            await self.check()
            await asyncio.sleep(CHECK_INTERVAL)

    async def check(self) -> dict:
        try:
            self.latest = await asyncio.to_thread(self.a.updater.latest)
            self.check_error = None
        except Exception as e:
            log.warning("update check failed: %s", e)
            self.check_error = f"Versionsprüfung fehlgeschlagen: {e}"
        self.checked_at = time.time()
        self.mc.publish()
        return self.info()

    def current(self) -> str | None:
        return self.mc.versions[-1][1] if self.mc.versions else None

    def available(self) -> bool:
        cur = self.current()
        return bool(self.latest and cur and version_key(self.latest.version) > version_key(cur))

    def info(self) -> dict:
        backups = sorted(p for p in self.backup_dir.glob("*_pre_update") if p.is_dir())
        last_backup = None
        if backups:
            tar = backups[-1] / "server.tar.gz"
            last_backup = {"name": backups[-1].name, "size": tar.stat().st_size if tar.exists() else None}
        return {
            "current": self.current(),
            "latest": self.latest.version if self.latest else None,
            "available": self.available(),
            "checked_at": self.checked_at,
            "check_error": self.check_error,
            "job": self.job,
            "last_backup": last_backup,
        }

    # ---------- run ----------

    def begin(self, user: str) -> None:
        if not self.available():
            raise PortalError("Kein Update verfügbar (bitte zuerst nach Updates suchen).", 409)
        if self.mc.op_lock.locked():
            raise PortalError(f"Es läuft bereits eine Aktion: {self.mc.busy}", 409)
        self._tasks.append(asyncio.create_task(self._run(user)))

    def _set(self, key: str, status: str, message: str | None = None) -> None:
        for s in self.job["steps"]:
            if s["key"] == key:
                s["status"] = status
        if message is not None:
            self.job["message"] = message
        self.mc.publish()

    async def _step(self, key: str, coro_fn):
        self._set(key, "running")
        result = await coro_fn()
        self._set(key, "done")
        return result

    async def _control(self, verb: str) -> None:
        ok, msg = await asyncio.to_thread(self.a.control, verb)
        await asyncio.to_thread(self.mc._refresh)
        if not ok:
            raise RuntimeError(f"systemctl {verb}: {msg}")

    async def _wait_started(self, version: str) -> None:
        deadline = time.monotonic() + START_TIMEOUT
        while time.monotonic() < deadline:
            await asyncio.sleep(1)
            await asyncio.to_thread(self.mc._refresh)
            if self.mc.unit and self.mc.unit.active_state == "failed":
                raise RuntimeError("Server ist beim Start abgestürzt")
            cur = self.current()
            if self.mc.tracker.server_started and cur and version_key(cur) == version_key(version):
                return
        raise RuntimeError(f"Server meldet nach {START_TIMEOUT}s nicht 'Server started.' mit Version {version}")

    async def _run(self, user: str) -> None:
        rel = self.latest
        assert rel is not None
        from_v = self.current()
        async with self.mc.op_lock:
            self.mc.busy = "update"
            self.job = {
                "state": "running", "from": from_v, "to": rel.version, "message": None,
                "started": time.time(), "finished": None,
                "steps": [{"key": k, "label": l, "status": "pending"} for k, l in STEPS],
            }
            self.mc.publish()
            phase = "pre"          # pre -> stopped -> applied
            current_step = "prepare"
            zip_path = self.staging / "download.zip"
            target = self.staging / "server"
            try:
                current_step = "prepare"
                await self._step("prepare", lambda: asyncio.to_thread(self._prepare))

                current_step = "download"
                sha = await self._step("download", lambda: asyncio.to_thread(self.a.updater.download, rel, zip_path))

                current_step = "verify"
                await self._step("verify", lambda: asyncio.to_thread(self._stage, zip_path, target))

                current_step = "announce"
                if self.mc.tracker.players and self.a.console_available():
                    async def announce():
                        await asyncio.to_thread(self.a.announce_update)
                        await asyncio.sleep(ANNOUNCE_WAIT)
                    await self._step("announce", announce)
                else:
                    self._set("announce", "skipped")

                current_step = "stop"
                await self._step("stop", lambda: self._control("stop"))
                phase = "stopped"

                current_step = "backup"
                before = await self._step("backup", lambda: asyncio.to_thread(self._backup, from_v, rel.version))

                current_step = "apply"
                phase = "applied"

                async def apply():
                    ok, msg = await asyncio.to_thread(self.a.updater.apply)
                    if not ok:
                        raise RuntimeError(f"Kopieren fehlgeschlagen: {msg}")
                await self._step("apply", apply)

                current_step = "preserved"

                async def preserved():
                    after = await asyncio.to_thread(self.a.updater.checksums)
                    changed = [n for n in before if before[n] != after.get(n)]
                    if changed:
                        raise RuntimeError(f"Geschützte Dateien wurden verändert: {', '.join(changed)}")
                await self._step("preserved", preserved)

                current_step = "start"
                await self._step("start", lambda: self._control("start"))

                current_step = "check"
                await self._step("check", lambda: self._wait_started(rel.version))

                await asyncio.to_thread(self._prune_backups)
                self.job.update(state="success", message=f"Update auf {rel.version} erfolgreich.")
                self.audit.write("UPDATE", "SUCCESS", user, **{"from": from_v, "to": rel.version, "sha256": sha})
            except Exception as e:
                log.exception("update failed in step %s", current_step)
                self._set(current_step, "failed", f"{dict(STEPS).get(current_step, current_step)}: {e}")
                error = str(e)
                for s in self.job["steps"]:
                    if s["status"] == "pending":
                        s["status"] = "skipped"
                if phase == "applied":
                    await self._rollback(from_v, error)
                else:
                    if phase == "stopped" or current_step == "stop":
                        try:
                            await self._control("start")
                        except Exception as e2:
                            error += f" / Neustart fehlgeschlagen: {e2}"
                    self.job.update(state="failed",
                                    message=f"Update abgebrochen, nichts verändert. {self.job['message']}")
                self.audit.write("UPDATE", "FAILED", user, **{"from": from_v, "to": rel.version, "error": error,
                                                               "result_state": self.job["state"]})
            finally:
                await asyncio.to_thread(shutil.rmtree, self.staging, True)
                self.job["finished"] = time.time()
                self.mc.busy = None
                await asyncio.to_thread(self.mc._refresh)
                self.mc.publish()

    async def _rollback(self, from_v: str | None, error: str) -> None:
        self.job["steps"] += [{"key": k, "label": l, "status": "pending"} for k, l in ROLLBACK_STEPS]
        self.mc.publish()
        try:
            await self._step("rb_stop", self._stop_if_running)

            async def restore():
                ok, msg = await asyncio.to_thread(self.a.updater.rollback)
                if not ok:
                    raise RuntimeError(msg)
            await self._step("rb_restore", restore)

            async def start_old():
                await self._control("start")
                if from_v:
                    await self._wait_started(from_v)
            await self._step("rb_start", start_old)
            self.job.update(state="rolled_back",
                            message=f"Update fehlgeschlagen ({error}). Alter Stand {from_v} wurde wiederhergestellt.")
        except Exception as e:
            for s in self.job["steps"]:
                if s["status"] == "running":
                    s["status"] = "failed"
            self.job.update(state="rollback_failed",
                            message=f"Update UND Rollback fehlgeschlagen: {e}. Backup liegt in "
                                    f"{self.backup_dir} (*_pre_update) – bitte manuell prüfen.")

    async def _stop_if_running(self) -> None:
        await asyncio.to_thread(self.mc._refresh)
        if self.mc.unit and self.mc.unit.active_state not in ("inactive", "failed"):
            await self._control("stop")

    # ---------- blocking helpers (run in threads) ----------

    def _prepare(self) -> None:
        if not self.current():
            raise RuntimeError("Aktuelle Version unbekannt")
        self.a.updater.preflight()
        if self.staging.exists():
            shutil.rmtree(self.staging)
        self.staging.mkdir(parents=True)
        free = shutil.disk_usage(self.staging).free
        if free < MIN_FREE_BYTES:
            raise RuntimeError(f"Zu wenig freier Speicher ({free // 2**20} MB, benötigt {MIN_FREE_BYTES // 2**20} MB)")

    def _stage(self, zip_path: Path, target: Path) -> None:
        self.a.updater.stage(zip_path, target)
        zip_path.unlink(missing_ok=True)

    def _backup(self, from_v: str | None, to_v: str) -> dict[str, str]:
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        target = self.backup_dir / f"{stamp}_pre_update"
        self.a.updater.backup(target)
        checksums = self.a.updater.checksums()
        (target / "meta.json").write_text(json.dumps(
            {"from": from_v, "to": to_v, "created": stamp, "checksums": checksums}, indent=2))
        return checksums

    def _prune_backups(self) -> None:
        backups = sorted(p for p in self.backup_dir.glob("*_pre_update") if p.is_dir())
        for p in backups[:-self.keep]:
            shutil.rmtree(p, ignore_errors=True)
