"""
KreativOS — Core Routes (health, models, agents, dashboard, auth, permissions)
"""
import httpx
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import state
from ..config import AGENT_PERSONAS, INTERNAL_AGENTS
from ..auth import get_current_user
from .. import permissions as perms
from .. import backup as backup_mod

router = APIRouter(tags=["core"])
limiter = Limiter(key_func=get_remote_address)


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class PermissionRespondRequest(BaseModel):
    req_id: str
    decision: str


# ── Open (no auth) ────────────────────────────────────────────────────────────
@router.get("/api/health")
async def health():
    ok = False
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            ok = (await c.get(f"{state.OLLAMA_BASE_URL}/api/tags")).status_code == 200
    except Exception:
        pass
    return {
        "status": "ok", "version": "1.1.0",
        "ollama": "connected" if ok else "disconnected",
        "workspace": str(state.WORKSPACE_DIR),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/api/health/ready")
async def health_ready():
    import shutil
    checks: dict[str, dict] = {}
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{state.OLLAMA_BASE_URL}/api/tags")
            models = r.json().get("models", [])
            checks["ollama"] = {"ok": True, "models": len(models)}
    except Exception as e:
        checks["ollama"] = {"ok": False, "error": str(e)}
    try:
        usage = shutil.disk_usage(str(state.WORKSPACE_DIR))
        free_mb = usage.free // (1024 * 1024)
        checks["disk"] = {"ok": free_mb > 100, "free_mb": free_mb}
    except Exception as e:
        checks["disk"] = {"ok": False, "error": str(e)}
    checks["workspace"] = {"ok": state.WORKSPACE_DIR.exists(), "path": str(state.WORKSPACE_DIR)}
    ready = all(v.get("ok", False) for v in checks.values())
    return JSONResponse({"ready": ready, "checks": checks}, status_code=200 if ready else 503)


@router.get("/api/models")
async def list_models():
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{state.OLLAMA_BASE_URL}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            return {"models": models, "count": len(models)}
    except Exception:
        raise HTTPException(503, "Ollama not reachable")


@router.get("/api/agents")
async def list_agents():
    return {
        "agents": [
            {"id": k, "name": v["name"], "icon": v["icon"], "color": v["color"]}
            for k, v in AGENT_PERSONAS.items()
            if k not in INTERNAL_AGENTS
        ]
    }


@router.post("/api/auth/login")
@limiter.limit("10/minute")
async def login(request: Request, req: LoginRequest):
    token = state.auth.login(req.username, req.password) if state.auth else None
    if not token:
        raise HTTPException(401, "Invalid credentials")
    return {"token": token, "username": req.username}


# ── Protected routes ──────────────────────────────────────────────────────────
@router.get("/api/dashboard")
async def dashboard(current_user: dict = Depends(get_current_user)):
    files = [
        f for f in state.WORKSPACE_DIR.rglob("*")
        if f.is_file() and not any(
            p in str(f) for p in [".memory", ".auth", ".scheduler", ".workflows", ".backups", ".skill_eval", ".audit"]
        )
    ]
    uptime = int((datetime.now() - datetime.fromisoformat(state.START_TIME)).total_seconds())
    return {
        "stats": {
            **{k: v for k, v in state.stats.items() if k != "recent_activity"},
            "workspace_files": len(files),
            "uptime_seconds": uptime,
            "tasks_by_agent": dict(state.stats.get("tasks_by_agent", {})),
            "scheduled_tasks": len(state.scheduler.list_tasks()) if state.scheduler else 0,
            "projects": state.memory.count_projects() if state.memory else 0,
            "backups": len(backup_mod.list_backups()),
            "telegram_enabled": getattr(state, 'telegram_bot', None) and getattr(state.telegram_bot, 'enabled', False),
        },
        "recent_activity": state.stats.get("recent_activity", []),
        "start_time": state.START_TIME,
    }


@router.get("/api/permissions/pending")
async def pending_permissions(current_user: dict = Depends(get_current_user)):
    return {"pending": perms.pending_list()}


@router.post("/api/permissions/respond")
async def respond_permission(req: PermissionRespondRequest, current_user: dict = Depends(get_current_user)):
    if req.decision not in ("allow_once", "allow_session", "deny"):
        raise HTTPException(400, "Invalid decision")
    ok = perms.respond(req.req_id, req.decision)
    if not ok:
        raise HTTPException(404, "Permission request not found")
    return {"success": True}


@router.get("/api/permissions/workspace")
async def get_workspace(current_user: dict = Depends(get_current_user)):
    return {"workspace": str(state.WORKSPACE_DIR)}


# ── Auth user management ──────────────────────────────────────────────────────
@router.get("/api/auth/users")
async def list_users(current_user: dict = Depends(get_current_user)):
    return {"users": state.auth.list_users()} if state.auth else {"users": []}


@router.post("/api/auth/users")
async def create_user(req: CreateUserRequest, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    ok = state.auth.create_user(req.username, req.password, req.role) if state.auth else False
    if not ok:
        raise HTTPException(400, "Username already exists")
    return {"success": True}


@router.delete("/api/auth/users/{username}")
async def delete_user(username: str, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    ok = state.auth.delete_user(username) if state.auth else False
    if not ok:
        raise HTTPException(400, "Cannot delete this user")
    return {"success": True}
