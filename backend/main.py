"""
KreativOS — Main Application
App creation, service initialization, startup/shutdown, static serving.
Routes are in backend/routes/.
"""
import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request as StarRequest

# ── Internal ────────────────────────────────────────────────────────────────────
from . import state
from . import engine  # noqa: F401 — registers call_ollama, stream_ollama, ralph_loop, extract_and_save_files
from . import conversations
from .auth import AuthManager, get_current_user, set_auth_manager, set_auth_required
from .backup import init as backup_init
from . import backup as backup_mod
from .config import AGENT_PERSONAS, AGENT_SYSTEMS, INTERNAL_AGENTS, get_skills_for_agent
from .memory import ProjectMemory
from .paths import get_workspace_dir
from .scheduler import TaskScheduler
from .skill_eval import SkillEvaluator
from .audit import AuditLog
from . import permissions as perms
from .telegram_bot import bot as telegram_bot
from .model_hub import router as hub_router

# ── Re-export for tests ─────────────────────────────────────────────────────────
from .engine import call_ollama, stream_ollama, ralph_loop, extract_and_save_files

# ── Lifespan ────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    async def scheduler_loop():
        while True:
            await asyncio.sleep(60)
            if not state.scheduler:
                continue
            due = state.scheduler.get_due_tasks()
            for t in due:
                try:
                    sys_p = AGENT_SYSTEMS.get(t["agent"], AGENT_SYSTEMS["general"])
                    out = await call_ollama(t["model"], [{"role": "user", "content": t["prompt"]}], sys_p)
                    state.scheduler.mark_ran(t["id"], out)
                    extract_and_save_files(out)
                    track("scheduler_auto_ran", t["name"])
                except Exception as e:
                    track("scheduler_error", str(e))

    async def token_cleanup_loop():
        while True:
            await asyncio.sleep(3600)
            if state.auth:
                state.auth.cleanup_expired_tokens()

    async def start_telegram():
        async def task_cb(task, model, agent):
            sys_p = AGENT_SYSTEMS.get(agent, AGENT_SYSTEMS["general"])
            skl = get_skills_for_agent(agent)
            return await call_ollama(model, [{"role": "user", "content": task}], sys_p + "\n\n" + skl)

        telegram_bot.set_task_callback(task_cb)
        telegram_bot.set_chat_callback(stream_ollama)
        await telegram_bot.start()

    bg_tasks = [
        asyncio.create_task(scheduler_loop()),
        asyncio.create_task(token_cleanup_loop()),
        asyncio.create_task(start_telegram()),
    ]

    yield

    for t in bg_tasks:
        t.cancel()
    await telegram_bot.stop()


# ── App + Rate Limiter ─────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="KreativOS", version="1.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000", "http://127.0.0.1:5173", "http://127.0.0.1:8000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Environment ────────────────────────────────────────────────────────────────
state.OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
state.WORKSPACE_DIR = get_workspace_dir()
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() == "true"
set_auth_required(AUTH_REQUIRED)
perms.init(state.WORKSPACE_DIR)


def _get_start_time() -> str:
    f = state.WORKSPACE_DIR / ".startup_time"
    if f.exists():
        return f.read_text().strip()
    now = datetime.now().isoformat()
    f.write_text(now)
    return now


state.START_TIME = _get_start_time()

# ponytail: flat dict counters, not a class — YAGNI on stats abstraction
from collections import defaultdict
state.stats = {
    "total_messages": 0, "total_tasks": 0, "ralph_loops_run": 0,
    "ralph_fixes_applied": 0, "files_created": 0, "code_executions": 0,
    "pipelines_run": 0, "searches_run": 0, "start_time": state.START_TIME,
    "tasks_by_agent": defaultdict(int), "recent_activity": [],
}
state.total_tokens_prompt = 0
state.total_tokens_completion = 0


def track(event: str, detail: str = ""):
    state.stats["recent_activity"].insert(0, {
        "event": event, "detail": detail, "time": datetime.now().strftime("%H:%M:%S"),
    })
    state.stats["recent_activity"] = state.stats["recent_activity"][:30]


state.track = track


# ── Services ───────────────────────────────────────────────────────────────────
def init_services():
    conversations.init_db(state.WORKSPACE_DIR)
    state.memory = ProjectMemory(state.WORKSPACE_DIR)
    state.scheduler = TaskScheduler(state.WORKSPACE_DIR)
    state.auth = AuthManager(state.WORKSPACE_DIR)
    state.skill_eval = SkillEvaluator(state.WORKSPACE_DIR)
    state.audit_log = AuditLog(state.WORKSPACE_DIR)
    state.telegram_bot = telegram_bot
    backup_init(state.WORKSPACE_DIR)
    set_auth_manager(state.auth)


init_services()


# ── Auth middleware ────────────────────────────────────────────────────────────
OPEN_PATHS = {
    "/api/auth/login", "/api/health", "/api/health/ready", "/",
    "/api/pwa/manifest", "/api/hub/featured", "/api/agents", "/api/models",
}


@app.middleware("http")
async def auth_middleware(request: StarRequest, call_next):
    if not AUTH_REQUIRED:
        return await call_next(request)
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    if request.url.path in OPEN_PATHS or request.url.path.startswith("/api/hub/"):
        return await call_next(request)
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token or not state.auth.verify(token):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


# ── Routes ─────────────────────────────────────────────────────────────────────
app.include_router(hub_router)

# Lazy import routes after services are initialized (avoids circular dependency
# on state before it's set up)
from .routes import core_router, chat_router
app.include_router(core_router)
app.include_router(chat_router)


# ── Test helper ────────────────────────────────────────────────────────────────
def reinit_workspace():
    """Re-read WORKSPACE_DIR from env and re-init all services. Used by tests."""
    state.WORKSPACE_DIR = get_workspace_dir()
    perms.init(state.WORKSPACE_DIR)
    init_services()
    state.START_TIME = _get_start_time()
    from collections import defaultdict
    state.stats = {
        "total_messages": 0, "total_tasks": 0, "ralph_loops_run": 0,
        "ralph_fixes_applied": 0, "files_created": 0, "code_executions": 0,
        "pipelines_run": 0, "searches_run": 0, "start_time": state.START_TIME,
        "tasks_by_agent": defaultdict(int), "recent_activity": [],
    }


# ── SPA static serving (API routes take priority — this is last) ──────────────
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")
    app.mount("/icons", StaticFiles(directory=FRONTEND_DIST), name="icons")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        static_file = FRONTEND_DIST / full_path
        if static_file.exists() and static_file.is_file():
            media_type = None
            if full_path.endswith(".json") or full_path.endswith(".webmanifest"):
                media_type = "application/manifest+json"
            elif full_path.endswith(".svg"):
                media_type = "image/svg+xml"
            return FileResponse(static_file, media_type=media_type)
        return FileResponse(FRONTEND_DIST / "index.html")



