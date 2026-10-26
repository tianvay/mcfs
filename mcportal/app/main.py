"""HTTP API + web UI."""
from __future__ import annotations

import asyncio
import hmac
import json
import secrets
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .adapters import create_adapter
from .audit import AuditLog
from .config import Config
from .services.achievements import AchievementsService
from .services.map import MapService
from .services.allowlist import AllowlistService
from .services.events import EventsService
from .services.minecraft import MinecraftService, PortalError
from .services.stats import StatsService
from .services.update import UpdateService
from .services.waypoints import WaypointsService

WEB_DIR = Path(__file__).parent / "web"
SESSION_COOKIE = "mcportal_session"
SSE_PING_SECONDS = 15
# Set by the server on SIGTERM/SIGINT so open live streams end by themselves
SHUTTING_DOWN = threading.Event()


class NameIn(BaseModel):
    name: str


class PinIn(BaseModel):
    pin: str


class OperatorIn(BaseModel):
    operator: bool


class EventControlIn(BaseModel):
    type: str | None = None


class SecurityHeaders:
    """Plain ASGI middleware (BaseHTTPMiddleware does not cope well with SSE streams)."""

    HEADERS = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"no-referrer"),
        (b"content-security-policy", b"default-src 'self'; img-src 'self' data:"),
    ]

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                extra = list(self.HEADERS)
                if scope["path"].startswith("/static/"):
                    # always revalidate (ETag), so a portal update reaches the browser at once
                    extra.append((b"cache-control", b"no-cache"))
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)

        await self.app(scope, receive, send_with_headers)


def create_app(cfg: Config) -> FastAPI:
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    adapter = create_adapter(cfg)
    audit = AuditLog(cfg.audit_file)
    mc = MinecraftService(adapter, audit, cfg.data_dir)
    allow = AllowlistService(adapter, mc, audit, cfg.backup_dir, cfg.allowlist_backups_keep,
                             cfg.data_dir / "pending_operator.json")
    update = UpdateService(adapter, mc, audit, cfg.data_dir, cfg.backup_dir, cfg.update_backups_keep)
    stats = StatsService(adapter, mc, cfg.data_dir)
    achievements = AchievementsService(adapter, mc, cfg.data_dir)
    waypoints = WaypointsService(adapter, mc, cfg.data_dir)
    world_map = MapService(adapter, mc, audit, cfg.data_dir)
    game_events = EventsService(adapter, mc, audit, cfg.data_dir)
    sessions: set[str] = set()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await mc.startup()
        await stats.startup()
        await achievements.startup()
        await waypoints.startup()
        await game_events.startup()
        await update.startup()
        await world_map.startup()
        yield
        await world_map.shutdown()
        await update.shutdown()
        await mc.shutdown()

    app = FastAPI(title="Minecraft Family Portal", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(SecurityHeaders)

    @app.exception_handler(PortalError)
    async def portal_error(_: Request, exc: PortalError):
        return JSONResponse({"error": str(exc)}, status_code=exc.status)

    def client(request: Request) -> str:
        return request.client.host if request.client else "local"

    def authorized(request: Request) -> bool:
        return not cfg.pin or request.cookies.get(SESSION_COOKIE) in sessions

    def require_write(request: Request) -> str:
        if not authorized(request):
            raise PortalError("PIN erforderlich", 401)
        return client(request)

    # ---------- auth ----------

    @app.get("/api/auth")
    async def auth_state(request: Request):
        return {"pin_required": bool(cfg.pin), "authorized": authorized(request)}

    @app.post("/api/login")
    async def login(body: PinIn, request: Request):
        if not cfg.pin:
            return {"authorized": True}
        if not hmac.compare_digest(body.pin.encode(), cfg.pin.encode()):
            await asyncio.sleep(1.5)
            audit.write("LOGIN", "FAILED", client(request))
            raise PortalError("Falsche PIN", 401)
        token = secrets.token_urlsafe(32)
        sessions.add(token)
        resp = JSONResponse({"authorized": True})
        resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="strict", max_age=30 * 24 * 3600)
        return resp

    # ---------- status ----------

    @app.get("/api/status")
    async def status():
        return mc.snapshot()

    @app.get("/api/events")
    async def events(request: Request):
        q = mc.subscribe()

        async def stream():
            try:
                yield f"data: {json.dumps(mc.snapshot())}\n\n"
                idle = 0
                while not SHUTTING_DOWN.is_set() and not await request.is_disconnected():
                    try:
                        snap = await asyncio.wait_for(q.get(), timeout=1)
                        yield f"data: {json.dumps(snap)}\n\n"
                        idle = 0
                    except asyncio.TimeoutError:
                        idle += 1
                        if idle >= SSE_PING_SECONDS:
                            yield ": ping\n\n"
                            idle = 0
            finally:
                mc.unsubscribe(q)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ---------- server control ----------

    @app.post("/api/server/{verb}", status_code=202)
    async def server_control(verb: str, user: str = Depends(require_write)):
        mc.begin_control(verb, user)
        return {"accepted": verb}

    # ---------- allowlist ----------

    @app.get("/api/allowlist")
    async def allowlist_get():
        return await asyncio.to_thread(allow.list)

    @app.post("/api/allowlist", status_code=201)
    async def allowlist_add(body: NameIn, user: str = Depends(require_write)):
        await allow.add(body.name, user)
        return await asyncio.to_thread(allow.list)

    @app.delete("/api/allowlist/{name}")
    async def allowlist_remove(name: str, user: str = Depends(require_write)):
        await allow.remove(name, user)
        return await asyncio.to_thread(allow.list)

    @app.put("/api/allowlist/{name}/operator")
    async def allowlist_operator(name: str, body: OperatorIn, user: str = Depends(require_write)):
        await allow.set_operator(name, body.operator, user)
        return await asyncio.to_thread(allow.list)

    # ---------- update ----------

    @app.post("/api/update/check")
    async def update_check():
        return await update.check()

    @app.post("/api/update/start", status_code=202)
    async def update_start(user: str = Depends(require_write)):
        update.begin(user)
        return {"accepted": True}

    # ---------- statistics ----------

    @app.get("/api/stats")
    async def stats_summary():
        return stats.summary()

    @app.get("/api/achievements")
    async def achievements_summary():
        return achievements.summary()

    @app.get("/api/waypoints")
    async def waypoints_summary():
        return waypoints.summary()

    # ---------- timed events (not /api/events - that is the live stream) ----------

    @app.get("/api/gameevents")
    async def game_events_summary():
        return game_events.summary()

    @app.post("/api/gameevents/{action}", status_code=202)
    async def game_events_control(action: str, body: EventControlIn, user: str = Depends(require_write)):
        await game_events.control(action, body.type, user)
        return {"accepted": action}

    # ---------- map ----------

    @app.get("/api/map")
    async def map_summary():
        return await asyncio.to_thread(world_map.summary)

    @app.post("/api/map/render", status_code=202)
    async def map_render(user: str = Depends(require_write)):
        world_map.begin(user)
        return {"accepted": True}

    @app.get("/api/map/tiles/{build}/{dim}/{level}/{name}")
    async def map_tile(build: str, dim: str, level: str, name: str):
        # a build never changes, so tiles can be cached for good
        return FileResponse(world_map.tile_path(build, dim, level, name), media_type="image/png",
                            headers={"Cache-Control": "public, max-age=31536000, immutable"})

    # ---------- audit ----------

    @app.get("/api/audit")
    async def audit_tail(limit: int = 30):
        return await asyncio.to_thread(audit.tail, max(1, min(limit, 200)))

    # ---------- web ui ----------

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    async def index():
        return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    return app
