"""World map: snapshot of the world, rendering in a low-priority child process, tiles for the web UI.

A run:
  1. running server: console "save hold", "save query" until the server lists the files to copy,
     copy exactly those files/lengths to <data>/map/snapshot, "save resume" (always, also on errors).
     Stopped server: the world files are consistent, they are copied as they are.
  2. `python -m app.map.render <snapshot> <data>/map` with nice 19 / idle I/O / memory limit.
  3. the snapshot is deleted; <data>/map/current.json points at the new tiles.
Nightly at NIGHTLY_HOUR and on demand (button). The live world is only read, never written.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path

from ..adapters.base import MinecraftAdapter
from ..adapters.bedrock.logparse import SAVE_READY, LogLine, parse_save_files
from ..audit import AuditLog
from .minecraft import MinecraftService, PortalError

log = logging.getLogger("mcportal.map")

NIGHTLY_HOUR = 4
SAVE_QUERY_TIMEOUT = 60
RENDER_TIMEOUT = 30 * 60
RENDER_MEMORY = 1536 * 1024 * 1024
APP_ROOT = Path(__file__).resolve().parents[2]
_BUILD_RE = re.compile(r"^build-\d{8}-\d{6}$")
_TILE_RE = re.compile(r"^-?\d{1,6}_-?\d{1,6}\.png$")
DIMS = ("overworld", "the_end")


def _limit_child() -> None:  # runs in the render child before exec
    os.nice(19)
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (RENDER_MEMORY, RENDER_MEMORY))
    except (ImportError, ValueError, OSError):
        pass


class MapService:
    def __init__(self, adapter: MinecraftAdapter, mc: MinecraftService, audit: AuditLog, data_dir: Path):
        self.a = adapter
        self.mc = mc
        self.audit = audit
        self.dir = data_dir / "map"
        self.snapshot_dir = self.dir / "snapshot"
        self.hold_marker = self.dir / "save-hold.active"
        self.running: str | None = None          # "snapshot" | "render"
        self.progress: int | None = None
        self.last_error: str | None = None
        self._files_waiter: asyncio.Future | None = None
        self._save_ready = False  # "Data saved ..." seen, the file list follows on the next line
        self._task: asyncio.Task | None = None
        self._nightly: asyncio.Task | None = None
        self.after_render: list = []  # called with the built-chunks file after every successful run
        mc.line_listeners.append(self._on_line)
        mc.extras["map"] = self.state

    # ---------- state ----------

    def current(self) -> dict | None:
        try:
            build = json.loads((self.dir / "current.json").read_text(encoding="utf-8"))["build"]
            if not _BUILD_RE.match(build):
                return None
            return json.loads((self.dir / build / "index.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def state(self) -> dict:
        cur = self.current()
        return {
            "running": self.running,
            "progress": self.progress,
            "error": self.last_error,
            "build": cur["build"] if cur else None,
            "rendered_at": cur["rendered_at"] if cur else None,
            "next_run": self.next_nightly(),
        }

    def summary(self) -> dict:
        return {**self.state(), "index": self.current(), "seed": self.mc.snapshot().get("seed")}

    def tile_path(self, build: str, dim: str, level: str, name: str) -> Path:
        if not (_BUILD_RE.match(build) and dim in DIMS and level.isdigit() and len(level) <= 2 and _TILE_RE.match(name)):
            raise PortalError("Unbekannte Kachel", 404)
        path = self.dir / build / dim / level / name
        if not path.is_file():
            raise PortalError("Unbekannte Kachel", 404)
        return path

    @staticmethod
    def next_nightly(now: float | None = None) -> float:
        t = dt.datetime.fromtimestamp(now or time.time())
        nxt = t.replace(hour=NIGHTLY_HOUR, minute=0, second=0, microsecond=0)
        if nxt <= t:
            nxt += dt.timedelta(days=1)
        return nxt.timestamp()

    # ---------- lifecycle ----------

    async def startup(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        if self.hold_marker.exists():
            # portal stopped while the world was on hold: let the server save again
            log.warning("save hold marker found - sending save resume")
            try:
                await asyncio.to_thread(self.a.world_save_live, "resume")
            except Exception:
                log.exception("save resume after restart failed")
            self.hold_marker.unlink(missing_ok=True)
        shutil.rmtree(self.snapshot_dir, ignore_errors=True)
        for tmp in self.dir.glob(".tmp-*"):
            shutil.rmtree(tmp, ignore_errors=True)
        self._nightly = asyncio.create_task(self._nightly_loop())

    async def shutdown(self) -> None:
        for t in (self._nightly, self._task):
            if t:
                t.cancel()

    async def _nightly_loop(self) -> None:
        while True:
            await asyncio.sleep(max(1.0, self.next_nightly() - time.time()))
            try:
                self.begin("nightly")
            except PortalError as e:
                log.info("nightly map skipped: %s", e)

    # ---------- run ----------

    def begin(self, user: str) -> None:
        if self.running:
            raise PortalError("Die Karte wird gerade schon gezeichnet", 409)
        if self.mc.busy:
            raise PortalError(f"Es läuft gerade eine Server-Aktion: {self.mc.busy}", 409)
        self.running, self.progress, self.last_error = "snapshot", None, None
        self.mc.publish()
        self._task = asyncio.create_task(self._run(user))

    async def _run(self, user: str) -> None:
        t0 = time.time()
        try:
            await self._snapshot()
            self.running = "render"
            self.mc.publish()
            result = await self._render()
            self.audit.write("MAP", "SUCCESS", user, build=result.get("build"), seconds=round(time.time() - t0))
            for fn in self.after_render:
                try:
                    await asyncio.to_thread(fn, self.dir / "built_chunks.json")
                except Exception:
                    log.exception("after-render hook failed")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.last_error = str(e) if isinstance(e, PortalError) else f"Karte fehlgeschlagen: {e}"
            log.exception("map run failed")
            self.audit.write("MAP", "FAILED", user, error=self.last_error)
        finally:
            shutil.rmtree(self.snapshot_dir, ignore_errors=True)
            self.running, self.progress = None, None
            self.mc.publish()

    def _on_line(self, line: LogLine) -> None:
        w = self._files_waiter
        if w is None or w.done():
            return
        if line.message == SAVE_READY:
            self._save_ready = True
            return
        if self._save_ready:
            self._save_ready = False
            files = parse_save_files(line)
            if files:
                w.set_result(files)

    async def _snapshot(self) -> None:
        world = self.a.files.world_dir()
        if not (world / "db").is_dir():
            raise PortalError("Weltordner nicht gefunden")
        shutil.rmtree(self.snapshot_dir, ignore_errors=True)
        if not self.mc._is_active():
            await asyncio.to_thread(self._copy_tree, world)
            return
        if not self.a.console_available():
            raise PortalError("Server-Konsole nicht verfügbar - Karte kann nicht sicher kopiert werden")
        loop = asyncio.get_running_loop()
        self.hold_marker.write_text(str(time.time()), encoding="utf-8")
        try:
            await asyncio.to_thread(self.a.world_save_live, "hold")
            deadline = time.time() + SAVE_QUERY_TIMEOUT
            files = None
            while files is None:
                if time.time() > deadline:
                    raise PortalError("Server hat die Welt nicht zum Kopieren freigegeben (Zeitlimit)")
                self._files_waiter, self._save_ready = loop.create_future(), False
                await asyncio.to_thread(self.a.world_save_live, "query")
                try:
                    files = await asyncio.wait_for(asyncio.shield(self._files_waiter), timeout=2)
                except asyncio.TimeoutError:
                    pass  # "A previous save has not been completed." - ask again
            await asyncio.to_thread(self._copy_listed, world, files)
        finally:
            self._files_waiter = None
            try:
                await asyncio.to_thread(self.a.world_save_live, "resume")
            finally:
                self.hold_marker.unlink(missing_ok=True)

    def _copy_listed(self, world: Path, files: list[tuple[str, int]]) -> None:
        """Copy the listed files, each truncated to the listed length (as Mojang documents it)."""
        root = world.parent.resolve()
        prefix = world.name + "/"
        for rel, length in files:
            if not rel.startswith(prefix) or ".." in Path(rel).parts:
                raise PortalError(f"Unerwarteter Pfad in der Dateiliste: {rel}")
            src = (root / rel).resolve()
            if root not in src.parents:
                raise PortalError(f"Unerwarteter Pfad in der Dateiliste: {rel}")
            dst = self.snapshot_dir / rel[len(prefix):]
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(src, "rb") as fi, open(dst, "wb") as fo:
                left = length
                while left > 0:
                    buf = fi.read(min(left, 1 << 20))
                    if not buf:
                        raise PortalError(f"{rel} ist kürzer als vom Server gemeldet")
                    fo.write(buf)
                    left -= len(buf)

    def _copy_tree(self, world: Path) -> None:
        self.snapshot_dir.mkdir(parents=True)
        shutil.copytree(world / "db", self.snapshot_dir / "db")
        if (world / "level.dat").exists():
            shutil.copy2(world / "level.dat", self.snapshot_dir / "level.dat")

    async def _render(self) -> dict:
        cmd = [sys.executable, "-m", "app.map.render", str(self.snapshot_dir), str(self.dir)]
        if ionice := shutil.which("ionice"):
            cmd = [ionice, "-c3", *cmd]
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(APP_ROOT), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            preexec_fn=_limit_child if os.name == "posix" else None,
        )
        result: dict = {}
        error = None

        async def read() -> None:
            nonlocal result, error
            assert proc.stdout
            async for raw in proc.stdout:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                if "progress" in msg:
                    self.progress = int(msg.get("chunks", 0))
                    self.mc.publish()
                elif "done" in msg:
                    result = msg["done"]
                elif "error" in msg:
                    error = str(msg["error"])

        try:
            await asyncio.wait_for(asyncio.gather(read(), proc.wait()), timeout=RENDER_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise PortalError("Zeichnen der Karte dauerte zu lange und wurde abgebrochen")
        except asyncio.CancelledError:
            proc.kill()
            raise
        if proc.returncode != 0 or not result:
            stderr = (await proc.stderr.read()).decode(errors="replace")[-300:] if proc.stderr else ""
            raise PortalError(f"Zeichnen fehlgeschlagen: {error or stderr or proc.returncode}")
        return result
