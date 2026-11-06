"""HTTP API + web UI."""
from __future__ import annotations

import asyncio
import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .adapters import create_adapter
from .audit import AuditLog
from .auth import SESSION_DAYS, Lockout, Sessions, verify_password
from .config import Config
from .services.achievements import AchievementsService
from .services.map import MapService
from .services.allowlist import AllowlistService
from .services.donate import DonateService
from .services.events import EventsService
from .services.minecraft import MinecraftService, PortalError
from .services.packs import PacksService
from .services.stats import StatsService
from .services.update import UpdateService
from .services.waypoints import WaypointsService

WEB_DIR = Path(__file__).parent / "web"
SESSION_COOKIE = "mcportal_session"
EVENTS_PACK = "mcportal_events"
SSE_PING_SECONDS = 15
# Status fields everyone may see; everything else (seed, whitelist, update, events, errors ...) is admin only.
# A list of what is allowed, so a new field stays hidden until it is added here.
PUBLIC_STATUS = {"server_name", "status", "active_state", "started_at", "last_start", "version", "last_update",
                 "players", "max_players", "busy", "map", "stats", "achievements", "waypoints", "packs", "now"}
# Set by the server on SIGTERM/SIGINT so open live streams end by themselves
SHUTTING_DOWN = threading.Event()


class NameIn(BaseModel):
    name: str


class PasswordIn(BaseModel):
    password: str


class OperatorIn(BaseModel):
    operator: bool


class EventControlIn(BaseModel):
    type: str | None = None


class GiftIn(BaseModel):
    player: str
    item: str
    count: int


class WorldIn(BaseModel):
    value: str


class PackIn(BaseModel):
    enabled: bool


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
    donate = DonateService(adapter, mc, audit, cfg.data_dir)
    packs = PacksService(adapter, mc, audit, cfg.data_dir, cfg.backup_dir)
    world_map.after_render.append(game_events.sync_register)  # builds found on the map -> build register
    sessions = Sessions(cfg.data_dir / "sessions.json", cfg.password_hash)
    lockout = Lockout()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await mc.startup()
        await packs.startup()
        await stats.startup()
        await achievements.startup()
        await waypoints.startup()
        await game_events.startup()
        await update.startup()
        await world_map.startup()
        await donate.startup()
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

    def is_admin(request: Request) -> bool:
        return bool(cfg.password_hash) and sessions.valid(request.cookies.get(SESSION_COOKIE))

    def require_admin(request: Request) -> str:
        if not is_admin(request):
            raise PortalError("Anmeldung erforderlich", 401)
        return client(request)

    def visible(snap: dict, admin: bool) -> dict:
        return snap if admin else {k: v for k, v in snap.items() if k in PUBLIC_STATUS}

    # ---------- auth ----------

    @app.get("/api/auth")
    async def auth_state(request: Request):
        return {"password_set": bool(cfg.password_hash), "admin": is_admin(request)}

    @app.post("/api/login")
    async def login(body: PasswordIn, request: Request):
        ip = client(request)
        if not cfg.password_hash:
            raise PortalError("Es ist noch kein Admin-Passwort eingerichtet (deploy/set-password.sh).", 403)
        wait = lockout.wait_seconds(ip)
        if wait:
            raise PortalError(f"Zu viele Fehlversuche – bitte in {-(-wait // 60)} Minuten erneut versuchen.", 429)
        if not await asyncio.to_thread(verify_password, body.password, cfg.password_hash):
            lockout.failed(ip)
            await asyncio.sleep(1.5)
            audit.write("LOGIN", "FAILED", ip)
            raise PortalError("Falsches Passwort", 401)
        lockout.reset(ip)
        audit.write("LOGIN", "SUCCESS", ip)
        resp = JSONResponse({"admin": True})
        resp.set_cookie(SESSION_COOKIE, await asyncio.to_thread(sessions.create), httponly=True,
                        samesite="strict", max_age=SESSION_DAYS * 86400)
        return resp

    @app.post("/api/logout")
    async def logout(request: Request):
        await asyncio.to_thread(sessions.remove, request.cookies.get(SESSION_COOKIE))
        resp = JSONResponse({"admin": False})
        resp.delete_cookie(SESSION_COOKIE)
        return resp

    # ---------- status ----------

    @app.get("/api/status")
    async def status(request: Request):
        return visible(mc.snapshot(), is_admin(request))

    @app.get("/api/events")
    async def events(request: Request):
        q = mc.subscribe()
        # decided once per connection; the page reconnects after logging in or out
        admin = is_admin(request)

        async def stream():
            try:
                yield f"data: {json.dumps(visible(mc.snapshot(), admin))}\n\n"
                idle = 0
                while not SHUTTING_DOWN.is_set() and not await request.is_disconnected():
                    try:
                        snap = await asyncio.wait_for(q.get(), timeout=1)
                        yield f"data: {json.dumps(visible(snap, admin))}\n\n"
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
    async def server_control(verb: str, user: str = Depends(require_admin)):
        mc.begin_control(verb, user)
        return {"accepted": verb}

    # ---------- allowlist ----------

    @app.get("/api/allowlist")
    async def allowlist_get(_: str = Depends(require_admin)):
        return await asyncio.to_thread(allow.list)

    @app.post("/api/allowlist", status_code=201)
    async def allowlist_add(body: NameIn, user: str = Depends(require_admin)):
        await allow.add(body.name, user)
        return await asyncio.to_thread(allow.list)

    @app.delete("/api/allowlist/{name}")
    async def allowlist_remove(name: str, user: str = Depends(require_admin)):
        await allow.remove(name, user)
        return await asyncio.to_thread(allow.list)

    @app.put("/api/allowlist/{name}/operator")
    async def allowlist_operator(name: str, body: OperatorIn, user: str = Depends(require_admin)):
        await allow.set_operator(name, body.operator, user)
        return await asyncio.to_thread(allow.list)

    # ---------- update ----------

    @app.post("/api/update/check")
    async def update_check(_: str = Depends(require_admin)):
        return await update.check()

    @app.post("/api/update/start", status_code=202)
    async def update_start(user: str = Depends(require_admin)):
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

    def require_events_pack() -> None:
        # without the events pack the "scriptevent mcfs:event ..." commands would go nowhere
        if not packs.active(EVENTS_PACK):
            raise PortalError("Die Events sind ausgeschaltet (Tab Funktionen).", 409)

    @app.get("/api/gameevents")
    async def game_events_summary(_: str = Depends(require_admin)):
        return game_events.summary()

    # before /api/gameevents/{action}, which would take "undo" as an action
    @app.post("/api/gameevents/undo", status_code=202)
    async def game_events_undo(body: WorldIn, user: str = Depends(require_admin)):
        require_events_pack()
        await game_events.undo(body.value, user)
        return {"accepted": body.value}

    @app.post("/api/gameevents/{action}", status_code=202)
    async def game_events_control(action: str, body: EventControlIn, user: str = Depends(require_admin)):
        require_events_pack()
        await game_events.control(action, body.type, user)
        return {"accepted": action}

    @app.post("/api/world/{kind}", status_code=202)
    async def world_control(kind: str, body: WorldIn, user: str = Depends(require_admin)):
        await game_events.world(kind, body.value, user)
        return {"accepted": kind}

    # ---------- features = packs of the world (tab "Server") ----------

    @app.get("/api/features")
    async def features_public():
        # for everyone: what runs, with the recipes of its own items (tab "Funktionen")
        return await asyncio.to_thread(packs.public)

    @app.get("/api/features/icons/{name}.png")
    async def features_icon(name: str):
        return FileResponse(await asyncio.to_thread(packs.icon_path, name), media_type="image/png",
                            headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/api/packs")
    async def packs_summary(_: str = Depends(require_admin)):
        return await asyncio.to_thread(packs.summary)

    @app.put("/api/packs/{feature}")
    async def packs_switch(feature: str, body: PackIn, user: str = Depends(require_admin)):
        return await packs.set_enabled(feature, body.enabled, user)

    # ---------- donations (tab "Spenden") ----------

    @app.get("/api/donate")
    async def donate_summary(_: str = Depends(require_admin)):
        return await asyncio.to_thread(donate.summary)

    @app.post("/api/donate")
    async def donate_give(body: GiftIn, user: str = Depends(require_admin)):
        return await donate.give(body.player, body.item, body.count, user)

    @app.get("/api/donate/icons/{item_id}.png")
    async def donate_icon(item_id: str):
        # Mojang's item pictures; the same for every viewer, so the browser may keep them
        return FileResponse(await asyncio.to_thread(donate.icon_path, item_id), media_type="image/png",
                            headers={"Cache-Control": "public, max-age=604800"})

    # ---------- map ----------

    @app.get("/api/map")
    async def map_summary(request: Request):
        summary = await asyncio.to_thread(world_map.summary)
        if not is_admin(request):
            summary.pop("seed", None)
        return summary

    @app.post("/api/map/render", status_code=202)
    async def map_render(user: str = Depends(require_admin)):
        world_map.begin(user)
        return {"accepted": True}

    @app.get("/api/map/tiles/{build}/{dim}/{level}/{name}")
    async def map_tile(build: str, dim: str, level: str, name: str):
        # a build never changes, so tiles can be cached for good
        return FileResponse(world_map.tile_path(build, dim, level, name), media_type="image/png",
                            headers={"Cache-Control": "public, max-age=31536000, immutable"})

    # ---------- audit ----------

    @app.get("/api/audit")
    async def audit_tail(limit: int = 30, _: str = Depends(require_admin)):
        return await asyncio.to_thread(audit.tail, max(1, min(limit, 200)))

    # ---------- web ui ----------

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    async def index():
        return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    return app
