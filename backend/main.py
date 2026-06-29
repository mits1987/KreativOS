# KreativOS — Main Application
import asyncio
import json
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from dotenv import load_dotenv
load_dotenv()

import httpx
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request

# ── Internal imports ───────────────────────────────────────────────────────────
from .audit        import AuditLog
from .auth         import AuthManager, get_current_user, set_auth_manager, set_auth_required
from .backup       import init as backup_init
from . import backup as backup_mod
from .config       import (
    AGENT_PERSONAS, AGENT_SYSTEMS, INTERNAL_AGENTS, get_skills_for_agent,
)
from .context_manager import build_full_system_prompt
from .memory       import ProjectMemory
from .model_hub    import router as hub_router
from .office_agents import (
    generate_docx, generate_pptx, generate_xlsx,
    parse_ai_to_slides, parse_ai_to_table,
)
from . import permissions as perms
from .paths        import get_workspace_dir
from .orchestrator import orchestrate as run_orchestration, signal_permission
from .pipeline     import PIPELINE_TEMPLATES, run_pipeline
from .sandbox      import run_code_sandboxed
from .scheduler    import TaskScheduler
from .skill_eval   import SkillEvaluator
from .telegram_bot import bot as telegram_bot
from .web_search   import duckduckgo_search, format_results_for_agent

# ── App + Rate Limiter ─────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="KreativOS", version="1.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Environment ────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
WORKSPACE_DIR   = get_workspace_dir()  # [P1-7] No longer /tmp
AUTH_REQUIRED   = os.getenv("AUTH_REQUIRED", "false").lower() == "true"
set_auth_required(AUTH_REQUIRED)  # sync flag to auth.py for get_current_user()
perms.init(WORKSPACE_DIR)

def reinit_workspace():
    """Re-read WORKSPACE_DIR from env and re-init all services. Used by tests."""
    global WORKSPACE_DIR, memory, scheduler, auth, skill_eval, audit_log
    WORKSPACE_DIR = get_workspace_dir()
    perms.init(WORKSPACE_DIR)
    memory     = ProjectMemory(WORKSPACE_DIR)
    scheduler  = TaskScheduler(WORKSPACE_DIR)
    auth       = AuthManager(WORKSPACE_DIR)
    skill_eval = SkillEvaluator(WORKSPACE_DIR)
    audit_log  = AuditLog(WORKSPACE_DIR)
    backup_init(WORKSPACE_DIR)
    set_auth_manager(auth)

# ── Services ───────────────────────────────────────────────────────────────────
memory     = ProjectMemory(WORKSPACE_DIR)
scheduler  = TaskScheduler(WORKSPACE_DIR)
auth       = AuthManager(WORKSPACE_DIR)
skill_eval = SkillEvaluator(WORKSPACE_DIR)
audit_log  = AuditLog(WORKSPACE_DIR)
backup_init(WORKSPACE_DIR)
set_auth_manager(auth)  # wire singleton for Depends(get_current_user)

# ── Persistent start_time [P1-9] ──────────────────────────────────────────────
_START_TIME_FILE = WORKSPACE_DIR / ".startup_time"

def _get_start_time() -> str:
    if _START_TIME_FILE.exists():
        return _START_TIME_FILE.read_text().strip()
    now = datetime.now().isoformat()
    _START_TIME_FILE.write_text(now)
    return now

START_TIME = _get_start_time()

# ── In-memory stats (non-critical counters) ────────────────────────────────────
from collections import defaultdict
stats = {
    "total_messages":    0,
    "total_tasks":       0,
    "ralph_loops_run":   0,
    "ralph_fixes_applied": 0,
    "files_created":     0,
    "code_executions":   0,
    "pipelines_run":     0,
    "searches_run":      0,
    "start_time":        START_TIME,
    "tasks_by_agent":    defaultdict(int),
    "recent_activity":   [],
}

WORKFLOWS_FILE = WORKSPACE_DIR / ".workflows.json"

def track(event: str, detail: str = ""):
    stats["recent_activity"].insert(0, {
        "event":  event,
        "detail": detail,
        "time":   datetime.now().strftime("%H:%M:%S"),
    })
    stats["recent_activity"] = stats["recent_activity"][:30]

# ── Workflow helpers ───────────────────────────────────────────────────────────
def load_workflows() -> list:
    if not WORKFLOWS_FILE.exists():
        return []
    try:
        return json.loads(WORKFLOWS_FILE.read_text())
    except Exception:
        return []

def save_workflows(wf: list):
    WORKFLOWS_FILE.write_text(json.dumps(wf, indent=2))

# ── Ollama helpers ─────────────────────────────────────────────────────────────
KEEPALIVE_INTERVAL = 25  # seconds between SSE heartbeats [P1-3]

async def stream_ollama(
    model: str, messages: list, system: str
) -> AsyncGenerator[str, None]:
    """Stream Ollama chat response with SSE keepalive heartbeat."""
    payload = {
        "model":    model,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream":   True,
    }
    last_chunk_time = asyncio.get_running_loop().time()

    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream(
            "POST", f"{OLLAMA_BASE_URL}/api/chat", json=payload
        ) as resp:
            async for line in resp.aiter_lines():
                now = asyncio.get_running_loop().time()

                # [P1-3] Keepalive: send SSE comment so client connection stays alive
                if now - last_chunk_time > KEEPALIVE_INTERVAL:
                    yield ""   # empty string → caller yields SSE comment
                    last_chunk_time = now

                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    if "message" in d and "content" in d["message"]:
                        chunk = d["message"]["content"]
                        if chunk:
                            last_chunk_time = now
                            yield chunk
                    if d.get("done"):
                        break
                except Exception:
                    continue


async def call_ollama(model: str, messages: list, system: str) -> str:
    payload = {
        "model":    model,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream":   False,
    }
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Ollama error: {data['error']}")
        return data.get("message", {}).get("content", "")


def _parse_filename_hint(line: str) -> str | None:
    """Extract a filename from a comment like '# filename: foo.py' or '## file: foo.py'."""
    low = line.lower()
    if "filename:" in low or ("file:" in low and "profile" not in low):
        parts = line.split(":", 1)
        if len(parts) == 2:
            name = parts[1].strip().lstrip("/")
            if name and ("/" in name or "." in name):
                return name
    return None

def extract_and_save_files(text: str, project: str = "") -> list[str]:
    saved, in_block, block_lines, filename = [], False, [], None
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("```") and not in_block:
            # Check the line immediately before the fence for a filename hint
            pre_hint = _parse_filename_hint(lines[i - 1]) if i > 0 else None
            in_block, block_lines, filename = True, [], pre_hint
        elif line.startswith("```") and in_block:
            in_block = False
            if filename and block_lines:
                fp = (WORKSPACE_DIR / filename).resolve()
                if not str(fp).startswith(str(WORKSPACE_DIR.resolve())):
                    block_lines, filename = [], None
                    continue
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text("\n".join(block_lines))
                saved.append(str(filename))
                stats["files_created"] += 1
                track("file_saved", filename)
                if project:
                    memory.add_file(project, filename)
            block_lines, filename = [], None
        elif in_block:
            hint = _parse_filename_hint(line) if not filename else None
            if hint:
                filename = hint
            else:
                block_lines.append(line)
    return saved


# ── Ralph Loop ─────────────────────────────────────────────────────────────────
async def ralph_loop(
    model: str, task: str, initial: str, agent_type: str
) -> dict:
    if not initial or not initial.strip():
        return {
            "output": initial, "passed": False, "iterations": 0,
            "log": [], "error": "Empty initial output — skipping Ralph Loop",
        }

    stats["ralph_loops_run"] += 1
    track("ralph_loop", f"{agent_type}: {task[:40]}")

    MAX_CTX = 6000
    current = initial
    log     = []

    for i in range(1, 4):
        try:
            preview = current[:MAX_CTX] + ("\n...[truncated]" if len(current) > MAX_CTX else "")
            msgs    = [{"role": "user", "content": f"Original task: {task[:500]}\n\nOutput to review:\n{preview}"}]

            try:
                critic, qa_r = await asyncio.wait_for(
                    asyncio.gather(
                        call_ollama(model, msgs, AGENT_SYSTEMS["self_critic"]),
                        call_ollama(model, msgs, AGENT_SYSTEMS["qa"]),
                    ),
                    timeout=120.0,
                )
            except asyncio.TimeoutError:
                log.append({"iteration": i, "error": "Review timed out", "critic_passed": False, "qa_passed": False})
                continue
            except Exception as e:
                log.append({"iteration": i, "error": str(e), "critic_passed": False, "qa_passed": False})
                continue

            cp = bool(critic) and "APPROVED" in critic and "NEEDS FIXES" not in critic
            qp = bool(qa_r) and (
                "QA Verdict: PASS" in qa_r or
                ("PASS" in qa_r and "FAIL" not in qa_r.split("Verdict:")[-1][:30])
            )

            log.append({
                "iteration":     i,
                "critic":        critic[:400] if critic else "",
                "qa":            qa_r[:400] if qa_r else "",
                "critic_passed": cp,
                "qa_passed":     qp,
            })

            if cp and qp:
                track("ralph_passed", f"Passed on iteration {i}")
                return {"output": current, "passed": True, "iterations": i, "log": log}

            issues = []
            if not cp and critic:
                issues.append(f"Self-critic issues:\n{critic[:800]}")
            if not qp and qa_r:
                issues.append(f"QA issues:\n{qa_r[:800]}")
            if not issues:
                return {"output": current, "passed": True, "iterations": i, "log": log}

            fix_prompt = (
                f"Fix ALL of the following issues with your output:\n\n"
                f"{chr(10).join(issues)}\n\n"
                f"Original task: {task[:500]}\n\n"
                f"Your previous output (improve this):\n{preview}\n\n"
                "Write the complete corrected output — no placeholders."
            )
            sys_prompt = build_full_system_prompt(
                AGENT_SYSTEMS.get(agent_type, AGENT_SYSTEMS["general"]),
                skills=get_skills_for_agent(agent_type),
            )

            try:
                fixed = await asyncio.wait_for(
                    call_ollama(model, [{"role": "user", "content": fix_prompt}], sys_prompt),
                    timeout=240.0,
                )
                if fixed and fixed.strip():
                    current = fixed
                    stats["ralph_fixes_applied"] += 1
                    track("ralph_fix", f"Iteration {i}")
            except asyncio.TimeoutError:
                track("ralph_fix_timeout", f"Iteration {i}")
            except Exception as e:
                track("ralph_fix_error", str(e)[:60])

        except Exception as outer:
            log.append({
                "iteration":     i,
                "error":         f"Outer error: {str(outer)}",
                "critic_passed": False,
                "qa_passed":     False,
            })

    return {"output": current, "passed": False, "iterations": 3, "log": log}


# ══════════════════════════════════════════════════════════════════════════════
#  Pydantic Models
# ══════════════════════════════════════════════════════════════════════════════
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    agent: Optional[str] = "general"
    project: Optional[str] = ""
    use_web_search: bool = False

class TaskRequest(BaseModel):
    task: str
    model: str
    agent_type: str = "coder"
    use_ralph_loop: bool = True
    project: Optional[str] = ""

class PipelineRequest(BaseModel):
    task: str
    model: str
    template: str = "full_app"
    project: Optional[str] = ""
    skip_ralph: bool = False

class FileWriteRequest(BaseModel):
    filename: str
    content: str = Field(max_length=10_000_000)  # [P1-8] 10MB cap

class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"

class CodeReviewRequest(BaseModel):
    code: str
    language: str
    model: str
    filename: Optional[str] = ""

class WorkflowRequest(BaseModel):
    name: str
    description: str
    nodes: list
    edges: list

class ScheduleRequest(BaseModel):
    name: str
    prompt: str
    agent: str
    model: str
    interval: str = "daily"
    hour: int = 9

class LoginRequest(BaseModel):
    username: str
    password: str

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"

class OfficeRequest(BaseModel):
    prompt: str
    model: str
    format: str = "pptx"
    title: str = ""
    project: str = ""


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH MIDDLEWARE  [P0-1]
#  Only active when AUTH_REQUIRED=true.
#  Individual protected routes ALSO use Depends(get_current_user).
# ══════════════════════════════════════════════════════════════════════════════
OPEN_PATHS = {
    "/api/auth/login",
    "/api/health",
    "/api/health/ready",
    "/",
    "/api/pwa/manifest",
    "/api/hub/featured",
    "/api/agents",
    "/api/models",
}

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if not AUTH_REQUIRED:
        return await call_next(request)
    # Only protect API routes — frontend static assets (JS, CSS, icons) are public
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    if request.url.path in OPEN_PATHS or request.url.path.startswith("/api/hub/"):
        return await call_next(request)
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token or not auth.verify(token):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — Open (no auth)
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/")
async def root():
    return FileResponse(FRONTEND_DIST / "index.html")

@app.get("/api/health")
async def health():
    ok = False
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            ok = (await c.get(f"{OLLAMA_BASE_URL}/api/tags")).status_code == 200
    except Exception:
        pass
    return {
        "status":    "ok",
        "version":   "1.1.0",
        "ollama":    "connected" if ok else "disconnected",
        "workspace": str(WORKSPACE_DIR),
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/api/health/ready")
async def health_ready():
    """Readiness probe — checks Ollama, workspace, disk space."""
    import shutil
    checks: dict[str, dict] = {}

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{OLLAMA_BASE_URL}/api/tags")
            models = r.json().get("models", [])
            checks["ollama"] = {"ok": True, "models": len(models)}
    except Exception as e:
        checks["ollama"] = {"ok": False, "error": str(e)}

    # Disk space
    try:
        usage = shutil.disk_usage(str(WORKSPACE_DIR))
        free_mb = usage.free // (1024 * 1024)
        checks["disk"] = {"ok": free_mb > 100, "free_mb": free_mb}
    except Exception as e:
        checks["disk"] = {"ok": False, "error": str(e)}

    # Workspace
    checks["workspace"] = {"ok": WORKSPACE_DIR.exists(), "path": str(WORKSPACE_DIR)}

    ready = all(v.get("ok", False) for v in checks.values())
    return JSONResponse({"ready": ready, "checks": checks}, status_code=200 if ready else 503)


@app.get("/api/models")
async def list_models():
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{OLLAMA_BASE_URL}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            return {"models": models, "count": len(models)}
    except Exception:
        raise HTTPException(503, "Ollama not reachable")


@app.get("/api/agents")
async def list_agents():
    return {
        "agents": [
            {"id": k, "name": v["name"], "icon": v["icon"], "color": v["color"]}
            for k, v in AGENT_PERSONAS.items()
            if k not in INTERNAL_AGENTS
        ]
    }

@app.post("/api/auth/login")
@limiter.limit("10/minute")
async def login(request: Request, req: LoginRequest):
    token = auth.login(req.username, req.password)
    if not token:
        raise HTTPException(401, "Invalid credentials")
    return {"token": token, "username": req.username}


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — Protected  [P0-1: all use Depends(get_current_user)]
# ══════════════════════════════════════════════════════════════════════════════

# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.get("/api/dashboard")
async def dashboard(current_user: dict = Depends(get_current_user)):
    files = [
        f for f in WORKSPACE_DIR.rglob("*")
        if f.is_file() and not any(
            p in str(f) for p in [".memory", ".auth", ".scheduler", ".workflows", ".backups", ".skill_eval", ".audit"]
        )
    ]
    uptime = int((datetime.now() - datetime.fromisoformat(START_TIME)).total_seconds())
    return {
        "stats": {
            **{k: v for k, v in stats.items() if k != "recent_activity"},
            "workspace_files":  len(files),
            "uptime_seconds":   uptime,
            "tasks_by_agent":   dict(stats["tasks_by_agent"]),
            "scheduled_tasks":  len(scheduler.list_tasks()),
            "projects":         memory.count_projects(),
            "backups":          len(backup_mod.list_backups()),
            "skill_leaders":    skill_eval.leaderboard()[:3],
            "telegram_enabled": telegram_bot.enabled,
            "audit_entries":    audit_log.stats().get("total_entries", 0),
        },
        "recent_activity": stats["recent_activity"],
        "audit_tail":      audit_log.tail(10),
        "start_time":      START_TIME,
    }

# ── Permission routes ────────────────────────────────────────────────
@app.get("/api/permissions/pending")
async def pending_permissions(current_user: dict = Depends(get_current_user)):
    return {"pending": perms.pending_list()}

class PermissionRespondRequest(BaseModel):
    req_id: str
    decision: str

@app.post("/api/permissions/respond")
async def respond_permission(req: PermissionRespondRequest, current_user: dict = Depends(get_current_user)):
    if req.decision not in ("allow_once", "allow_session", "deny"):
        raise HTTPException(400, "Invalid decision")
    ok = perms.respond(req.req_id, req.decision)
    signal_permission(req.req_id, req.decision)  # unblock any waiting orchestrator
    if not ok:
        raise HTTPException(404, "Permission request not found")
    return {"success": True}

@app.get("/api/permissions/workspace")
async def get_workspace(current_user: dict = Depends(get_current_user)):
    return {"workspace": str(WORKSPACE_DIR)}

# ── Permission helper for file routes ────────────────────────────────
def _check_file_permission(path, operation):
    fp = Path(path).expanduser().resolve()
    if perms.is_allowed(str(fp)):
        return None
    result = perms.request_access(str(fp), operation)
    if result is None or result.get("status") == "denied":
        return result
    return result

# ── Files [P0-4: paginated] ────────────────────────────────────────────────────
@app.get("/api/files/list")
async def list_files(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    all_files = []
    for f in WORKSPACE_DIR.rglob("*"):
        if f.is_file() and not any(
            p in str(f) for p in [".memory", ".auth", ".scheduler", ".workflows", ".backups", ".skill_eval", ".audit"]
        ):
            all_files.append({
                "name":     str(f.relative_to(WORKSPACE_DIR)),
                "size":     f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    # Sort newest first
    all_files.sort(key=lambda x: x["modified"], reverse=True)
    total = len(all_files)
    page  = all_files[offset: offset + limit]
    return {
        "files":     page,
        "total":     total,
        "limit":     limit,
        "offset":    offset,
        "workspace": str(WORKSPACE_DIR),
    }

@app.post("/api/files/write")
async def write_file(
    req: FileWriteRequest,
    current_user: dict = Depends(get_current_user),
):
    raw = req.filename
    fp = Path(WORKSPACE_DIR / raw).expanduser().resolve()
    perm = _check_file_permission(str(fp), "write")
    if perm:
        raise HTTPException(403, detail=perm)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(req.content)
    stats["files_created"] += 1
    track("file_saved", raw)
    return {"success": True, "path": str(fp)}

@app.get("/api/files/read/{filename:path}")
async def read_file(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    raw = filename
    fp = Path(WORKSPACE_DIR / raw).expanduser().resolve()
    perm = _check_file_permission(str(fp), "read")
    if perm:
        raise HTTPException(403, detail=perm)
    if not fp.exists():
        raise HTTPException(404, "Not found")
    return {"filename": raw, "content": fp.read_text()}

@app.delete("/api/files/delete/{filename:path}")
async def delete_file(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    raw = filename
    fp = Path(WORKSPACE_DIR / raw).expanduser().resolve()
    perm = _check_file_permission(str(fp), "delete")
    if perm:
        raise HTTPException(403, detail=perm)
    if fp.exists():
        fp.unlink()
    return {"success": True}


# ── Code Execution  [P0-2: sandboxed] ─────────────────────────────────────────
@app.post("/api/execute")
@limiter.limit("20/minute")
async def execute_code(
    request: Request,
    req: ExecuteRequest,
    current_user: dict = Depends(get_current_user),
):
    stats["code_executions"] += 1
    track("code_exec", req.language)
    external_paths = perms.check_code_paths(req.code, WORKSPACE_DIR)
    if external_paths:
        result = perms.request_access(external_paths[0], "execute")
        if result and result.get("status") != "allowed":
            raise HTTPException(403, detail=result)
    result = await asyncio.to_thread(run_code_sandboxed, req.code, req.language, workspace_dir=str(WORKSPACE_DIR))
    return result


# ── Chat  [rate-limited] ───────────────────────────────────────────────────────
@app.post("/api/chat/stream")
@limiter.limit("30/minute")
async def chat_stream(
    request: Request,
    req: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    stats["total_messages"] += 1
    track("chat", f"agent:{req.agent}")

    system = AGENT_SYSTEMS.get(req.agent, AGENT_SYSTEMS["general"])
    skills = get_skills_for_agent(req.agent or "general")

    mem_ctx    = memory.build_context(req.project) if req.project else ""
    search_ctx = ""
    if req.use_web_search or req.agent == "researcher":
        last_user = next(
            (m.content for m in reversed(req.messages) if m.role == "user"), ""
        )
        if last_user:
            results    = await duckduckgo_search(last_user[:200], 4)
            search_ctx = format_results_for_agent(last_user[:200], results)
            stats["searches_run"] += 1

    # [P1-6] Token-aware prompt assembly
    full_system = build_full_system_prompt(system, skills, mem_ctx, search_ctx)
    messages    = [{"role": m.role, "content": m.content} for m in req.messages]

    async def generate():
        async for chunk in stream_ollama(req.model, messages, full_system):
            if chunk:
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            else:
                # Keepalive — SSE comment keeps connection alive
                yield ": keepalive\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Tasks  [rate-limited, auth] ────────────────────────────────────────────────
@app.post("/api/task/run")
@limiter.limit("10/minute")
async def run_task(
    request: Request,
    req: TaskRequest,
    current_user: dict = Depends(get_current_user),
):
    stats["total_tasks"]                    += 1
    stats["tasks_by_agent"][req.agent_type] += 1
    track("task_start", f"{req.agent_type}: {req.task[:50]}")

    sys_prompt = AGENT_SYSTEMS.get(req.agent_type, AGENT_SYSTEMS["general"])
    skills     = get_skills_for_agent(req.agent_type)
    mem        = memory.build_context(req.project) if req.project else ""
    full       = build_full_system_prompt(sys_prompt, skills, mem)

    out   = await call_ollama(req.model, [{"role": "user", "content": req.task}], full)
    saved = extract_and_save_files(out, req.project)

    ralph = None
    if req.use_ralph_loop and req.agent_type in ("coder", "architect", "devops"):
        ralph = await ralph_loop(req.model, req.task, out, req.agent_type)
        out   = ralph["output"]
        saved += extract_and_save_files(out, req.project)

    if req.project:
        memory.add_decision(req.project, f"{req.agent_type}: {req.task[:60]}", req.agent_type)

    audit_log.log("task_done", req.task[:80], agent=req.agent_type)
    track("task_done", req.agent_type)

    return {
        "task":        req.task,
        "agent":       AGENT_PERSONAS.get(req.agent_type, AGENT_PERSONAS["general"])["name"],
        "result":      out,
        "saved_files": list(set(saved)),
        "ralph":       ralph,
        "timestamp":   datetime.now().isoformat(),
    }


# ── Orchestrator ───────────────────────────────────────────────────────────────
@app.post("/api/orchestrate")
@limiter.limit("5/minute")
async def orchestrate_endpoint(
    request: Request,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    task    = body.get("task", "").strip()
    model   = body.get("model", "").strip()
    project = body.get("project", "")
    if not task or not model:
        raise HTTPException(400, "task and model required")

    track("orchestrate", task[:60])
    audit_log.log("orchestrate", f"Task: {task[:80]}", user=current_user.get("username"))

    async def event_stream():
        async for event in run_orchestration(task, model, project, WORKSPACE_DIR, OLLAMA_BASE_URL):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Pipeline  [rate-limited, auth] ────────────────────────────────────────────
@app.get("/api/pipeline/templates")
async def pipeline_templates(current_user: dict = Depends(get_current_user)):
    return {
        "templates": [
            {"id": k, "steps": [s["label"] for s in v]}
            for k, v in PIPELINE_TEMPLATES.items()
        ]
    }

@app.post("/api/pipeline/run")
@limiter.limit("5/minute")
async def run_pipeline_route(
    request: Request,
    req: PipelineRequest,
    current_user: dict = Depends(get_current_user),
):
    stats["pipelines_run"] += 1
    stats["total_tasks"]   += 1
    track("pipeline_start", f"{req.template}: {req.task[:50]}")

    async def generate():
        async for event in run_pipeline(
            task=req.task,
            template=req.template,
            model=req.model,
            call_ollama_fn=call_ollama,
            agent_systems=AGENT_SYSTEMS,
            get_skills_fn=get_skills_for_agent,
            ralph_fn=ralph_loop,
            workspace_dir=WORKSPACE_DIR,
            track_fn=track,
            extract_fn=lambda t: extract_and_save_files(t, req.project),
            skip_ralph=req.skip_ralph,
        ):
            yield f"data: {json.dumps(event)}\n\n"
            if event["type"] == "done":
                if req.project:
                    memory.add_decision(req.project, f"Pipeline '{req.template}' run: {req.task[:60]}", "orchestrator")
                audit_log.log("pipeline_done", req.template)
                track("pipeline_done", req.template)
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Memory  [P0-4: paginated] ─────────────────────────────────────────────────
@app.get("/api/memory/projects")
async def list_projects(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    projects = memory.list_projects(limit=limit, offset=offset)
    return {
        "projects": projects,
        "total":    memory.count_projects(),
        "limit":    limit,
        "offset":   offset,
    }

@app.get("/api/memory/{project}")
async def get_memory(project: str, current_user: dict = Depends(get_current_user)):
    return memory.get(project)

@app.post("/api/memory/{project}/note")
async def add_note(
    project: str,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    memory.add_note(project, body.get("note", ""))
    return {"success": True}

@app.delete("/api/memory/{project}")
async def delete_memory(project: str, current_user: dict = Depends(get_current_user)):
    memory.delete(project)
    return {"success": True}


# ── Web Search ─────────────────────────────────────────────────────────────────
@app.get("/api/search")
async def web_search(
    q: str,
    max_results: int = 5,
    current_user: dict = Depends(get_current_user),
):
    stats["searches_run"] += 1
    track("web_search", q[:60])
    results = await duckduckgo_search(q, max_results)
    return {"query": q, "results": results}


# ── App Builder ────────────────────────────────────────────────────────────────
@app.post("/api/appbuilder/generate")
@limiter.limit("5/minute")
async def generate_app(
    request: Request,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    description = body.get("description", "")
    model       = body.get("model", "")
    app_type    = body.get("app_type", "web")
    project     = body.get("project", "")
    skip_ralph  = bool(body.get("skip_ralph", False))
    stats["total_tasks"] += 1
    track("appbuilder", description[:50])

    system = build_full_system_prompt(
        AGENT_SYSTEMS["coder"],
        skills=get_skills_for_agent("coder"),
        memory_context=memory.build_context(project) if project else "",
    )
    prompt = (
        f"Build a complete, working {app_type} application:\n\n{description}\n\n"
        "Requirements:\n"
        "1. Write ALL files needed — frontend, backend, config\n"
        "2. Each file must start with: # filename: path/to/file\n"
        "3. Include package.json/requirements.txt\n"
        "4. Include a README.md with setup instructions\n"
        "5. The app must be runnable immediately after following the README\n\n"
        "Write every file completely — no placeholders."
    )

    output = await call_ollama(model, [{"role": "user", "content": prompt}], system)
    ralph  = None
    if not skip_ralph:
        ralph = await ralph_loop(model, description, output, "coder")
        output = ralph["output"]
    saved  = extract_and_save_files(output, project)

    if project:
        memory.add_decision(project, f"Built {app_type} app: {description[:60]}", "coder")

    return {
        "description": description,
        "output":      output,
        "saved_files": saved,
        "ralph":       ralph,
        "timestamp":   datetime.now().isoformat(),
    }

@app.get("/api/appbuilder/preview/{filename:path}")
async def preview_file(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    fp = (WORKSPACE_DIR / filename).resolve()
    if not str(fp).startswith(str(WORKSPACE_DIR.resolve())):
        raise HTTPException(400, "Invalid path")
    if not fp.exists():
        raise HTTPException(404, "File not found")
    return {"filename": filename, "content": fp.read_text(), "extension": fp.suffix}


# ── Canvas ─────────────────────────────────────────────────────────────────────
@app.get("/api/canvas/workflows")
async def get_workflows(current_user: dict = Depends(get_current_user)):
    return {"workflows": load_workflows()}

@app.post("/api/canvas/workflows")
async def save_workflow(
    wf: WorkflowRequest,
    current_user: dict = Depends(get_current_user),
):
    workflows = load_workflows()
    new_wf = {
        "id":          f"wf_{uuid.uuid4().hex[:8]}",
        "name":        wf.name,
        "description": wf.description,
        "nodes":       wf.nodes,
        "edges":       wf.edges,
        "created":     datetime.now().isoformat(),
    }
    workflows.append(new_wf)
    save_workflows(workflows)
    return new_wf

@app.delete("/api/canvas/workflows/{wf_id}")
async def delete_workflow(
    wf_id: str,
    current_user: dict = Depends(get_current_user),
):
    wfs = [w for w in load_workflows() if w["id"] != wf_id]
    save_workflows(wfs)
    return {"success": True}

@app.post("/api/canvas/run/{wf_id}")
async def run_workflow(
    wf_id: str,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    wfs = load_workflows()
    wf  = next((w for w in wfs if w["id"] == wf_id), None)
    if not wf:
        raise HTTPException(404, "Workflow not found")

    model   = body.get("model", "")
    task    = body.get("task", "")
    track("canvas_run", wf["name"])

    # Topological sort using saved edges; fall back to x-position if no edges
    raw_nodes = wf["nodes"]
    edges     = wf.get("edges", [])
    if edges:
        from collections import deque
        node_map  = {n["id"]: n for n in raw_nodes}
        in_deg    = {n["id"]: 0 for n in raw_nodes}
        adj       = {n["id"]: [] for n in raw_nodes}
        for e in edges:
            s, t = e.get("source"), e.get("target")
            if s in adj and t in in_deg:
                adj[s].append(t)
                in_deg[t] += 1
        queue = deque(nid for nid, d in in_deg.items() if d == 0)
        nodes = []
        while queue:
            nid = queue.popleft()
            nodes.append(node_map[nid])
            for t in adj[nid]:
                in_deg[t] -= 1
                if in_deg[t] == 0:
                    queue.append(t)
        # Cycle or disconnected graph — fall back
        if len(nodes) != len(raw_nodes):
            nodes = sorted(raw_nodes, key=lambda n: n.get("position", {}).get("x", 0))
    else:
        nodes = sorted(raw_nodes, key=lambda n: n.get("position", {}).get("x", 0))

    results, context = [], task

    for node in nodes:
        agent_id = node.get("data", {}).get("agent", "general")
        label    = node.get("data", {}).get("label", "Step")
        sys_p    = build_full_system_prompt(
            AGENT_SYSTEMS.get(agent_id, AGENT_SYSTEMS["general"]),
            skills=get_skills_for_agent(agent_id),
        )
        out   = await call_ollama(model, [{"role": "user", "content": context}], sys_p)
        saved = extract_and_save_files(out)

        # Agent-to-agent handoff
        next_agent = None
        for line in out.split("\n"):
            if line.strip().startswith("HANDOFF:"):
                next_agent = line.split(":", 1)[1].strip()
                break

        results.append({
            "node":         label,
            "agent":        agent_id,
            "output":       out,
            "saved_files":  saved,
            "handoff_to":   next_agent,
        })
        context += f"\n\n[{label}]: {out}"

        # If handoff requested, route to that agent next
        if next_agent and next_agent in AGENT_SYSTEMS:
            handoff_sys = build_full_system_prompt(
                AGENT_SYSTEMS[next_agent],
                skills=get_skills_for_agent(next_agent),
            )
            h_out = await call_ollama(model, [{"role": "user", "content": context}], handoff_sys)
            results.append({
                "node":        f"Handoff → {next_agent}",
                "agent":       next_agent,
                "output":      h_out,
                "saved_files": extract_and_save_files(h_out),
            })
            context += f"\n\n[Handoff {next_agent}]: {h_out}"

    return {
        "workflow":  wf["name"],
        "task":      task,
        "results":   results,
        "timestamp": datetime.now().isoformat(),
    }


# ── Code Review ────────────────────────────────────────────────────────────────
@app.post("/api/review")
@limiter.limit("20/minute")
async def review_code(
    request: Request,
    req: CodeReviewRequest,
    current_user: dict = Depends(get_current_user),
):
    stats["total_tasks"] += 1
    track("code_review", req.filename or req.language)
    prompt = (
        f"Review this {req.language} code"
        f"{f' from file: {req.filename}' if req.filename else ''}:\n\n"
        f"```{req.language}\n{req.code}\n```\n\n"
        "Provide a thorough code review following the structured format."
    )
    output = await call_ollama(
        req.model, [{"role": "user", "content": prompt}], AGENT_SYSTEMS["code_reviewer"]
    )
    return {
        "review":    output,
        "language":  req.language,
        "filename":  req.filename,
        "timestamp": datetime.now().isoformat(),
    }


# ── Scheduler ──────────────────────────────────────────────────────────────────
@app.get("/api/scheduler/tasks")
async def list_scheduled(current_user: dict = Depends(get_current_user)):
    return {"tasks": scheduler.list_tasks()}

@app.post("/api/scheduler/tasks")
async def create_scheduled(
    req: ScheduleRequest,
    current_user: dict = Depends(get_current_user),
):
    t = scheduler.add_task(req.name, req.prompt, req.agent, req.model, req.interval, req.hour)
    track("scheduler_add", req.name)
    return t

@app.delete("/api/scheduler/tasks/{task_id}")
async def delete_scheduled(
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    scheduler.delete_task(task_id)
    return {"success": True}

@app.post("/api/scheduler/tasks/{task_id}/toggle")
async def toggle_scheduled(
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    enabled = scheduler.toggle_task(task_id)
    return {"enabled": enabled}

@app.post("/api/scheduler/run-due")
async def run_due_tasks(
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    due     = scheduler.get_due_tasks()
    results = []
    for t in due:
        sys_p = AGENT_SYSTEMS.get(t["agent"], AGENT_SYSTEMS["general"])
        out   = await call_ollama(t["model"], [{"role": "user", "content": t["prompt"]}], sys_p)
        scheduler.mark_ran(t["id"], out)
        saved = extract_and_save_files(out)
        results.append({"task": t["name"], "output": out, "saved_files": saved})
        track("scheduler_ran", t["name"])
    return {"ran": len(results), "results": results}


# ── Audit  [P0-4: paginated] ───────────────────────────────────────────────────
@app.get("/api/audit")
async def get_audit_log(
    n: int = 100,
    offset: int = 0,
    q: str = "",
    current_user: dict = Depends(get_current_user),
):
    if q:
        return {"entries": audit_log.search(q, n, offset)}
    return {
        "entries": audit_log.tail(n, offset),
        "stats":   audit_log.stats(),
        "total":   audit_log.count(),
    }


# ── Skills ─────────────────────────────────────────────────────────────────────
@app.get("/api/skills/leaderboard")
async def skill_leaderboard(current_user: dict = Depends(get_current_user)):
    return {"leaderboard": skill_eval.leaderboard(), "timestamp": datetime.now().isoformat()}

@app.get("/api/skills/catalog")
async def skills_catalog(current_user: dict = Depends(get_current_user)):
    from .config import OPENCODE_SKILLS, SKILLS
    catalog = []
    for k, v in OPENCODE_SKILLS.items():
        catalog.append({
            "id": k,
            "name": k.replace("-", " ").title(),
            "description": v["description"],
            "source": "opencode",
            "preview": v["content"][:300],
        })
    for k in SKILLS:
        catalog.append({
            "id": k,
            "name": k.title(),
            "description": f"Built-in skill for {k} best practices",
            "source": "builtin",
            "preview": SKILLS[k][:300],
        })
    return {"catalog": catalog}

@app.get("/api/skills/{agent}")
async def agent_skill_stats(agent: str, current_user: dict = Depends(get_current_user)):
    return skill_eval.get_agent(agent)

@app.post("/api/skills/grade")
async def grade_output(
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    task   = body.get("task", "")
    output = body.get("output", "")
    agent  = body.get("agent", "general")
    model  = body.get("model", "")
    if not output or not model:
        raise HTTPException(400, "output and model required")

    prompt = skill_eval.build_grader_prompt(task, output)
    raw    = await call_ollama(
        model,
        [{"role": "user", "content": prompt}],
        "You are a grader. Respond only in the JSON format specified.",
    )
    try:
        raw_clean = raw.strip()
        if raw_clean.startswith("```"):
            raw_clean = raw_clean[raw_clean.index("\n")+1:] if "\n" in raw_clean else raw_clean[3:]
            raw_clean = raw_clean.rstrip("`").strip()
        data  = json.loads(raw_clean)
        score = max(0, min(10, int(data.get("score", 5))))
        fb    = data.get("feedback", "")
    except Exception:
        score, fb = 5, raw[:200]

    skill_eval.record(agent, task, output, score, fb)
    audit_log.log("skill_graded", f"{agent} scored {score}/10", agent=agent)
    return {"score": score, "feedback": fb, "agent": agent}


# ── Auth management ────────────────────────────────────────────────────────────
@app.get("/api/auth/users")
async def list_users(current_user: dict = Depends(get_current_user)):
    return {"users": auth.list_users()}

@app.post("/api/auth/users")
async def create_user(
    req: CreateUserRequest,
    current_user: dict = Depends(get_current_user),
):
    ok = auth.create_user(req.username, req.password, req.role)
    if not ok:
        raise HTTPException(400, "Username already exists")
    return {"success": True}

@app.delete("/api/auth/users/{username}")
async def delete_user(
    username: str,
    current_user: dict = Depends(get_current_user),
):
    ok = auth.delete_user(username)
    if not ok:
        raise HTTPException(400, "Cannot delete this user")
    return {"success": True}


# ── Backup ─────────────────────────────────────────────────────────────────────
@app.post("/api/backup/create")
async def create_backup(current_user: dict = Depends(get_current_user)):
    audit_log.log("backup_create")
    track("backup", "Creating backup…")
    out_path, size_mb = backup_mod.create_backup(WORKSPACE_DIR)
    audit_log.log("backup_done", out_path.name)
    return {"filename": out_path.name, "size_mb": size_mb, "timestamp": datetime.now().isoformat()}

@app.get("/api/backup/list")
async def list_backups(current_user: dict = Depends(get_current_user)):
    return {"backups": backup_mod.list_backups()}

@app.get("/api/backup/download/{filename}")
async def download_backup(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    if not filename.startswith("kreavitos_backup_") or not filename.endswith(".tar.gz"):
        raise HTTPException(400, "Invalid backup filename")
    fp = WORKSPACE_DIR / ".backups" / filename
    if not fp.exists():
        raise HTTPException(404, "Backup not found")
    return FileResponse(str(fp), media_type="application/gzip", filename=filename)

@app.delete("/api/backup/{filename}")
async def delete_backup(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    ok = backup_mod.delete_backup(filename)
    if not ok:
        raise HTTPException(404, "Backup not found")
    audit_log.log("backup_delete", filename)
    return {"success": True}

@app.post("/api/backup/restore/{filename}")
async def restore_backup(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    audit_log.log("backup_restore", filename)
    ok = backup_mod.restore_backup(filename, WORKSPACE_DIR)
    if not ok:
        raise HTTPException(404, "Backup not found")
    return {"success": True, "message": "Workspace restored. Restart recommended."}


# ── Office ─────────────────────────────────────────────────────────────────────
@app.post("/api/office/generate")
async def generate_office_file(
    req: OfficeRequest,
    current_user: dict = Depends(get_current_user),
):
    from .config import SKILLS
    audit_log.log("office_generate", f"{req.format}: {req.prompt[:60]}")
    track("office_gen", f"{req.format}: {req.title or req.prompt[:40]}")

    title = req.title or req.prompt[:60]
    mem   = memory.build_context(req.project) if req.project else ""

    if req.format == "pptx":
        research_system = (
            AGENT_SYSTEMS["researcher"] + "\n\n"
            "Research the given topic thoroughly. Provide:\n"
            "- Key facts, statistics, and data points\n"
            "- Historical context or background\n"
            "- Current trends and future outlook\n"
            "- Real-world examples and case studies\n"
            "- Expert opinions or industry insights\n"
            + (("\n\n" + mem) if mem else "")
        )
        research = await call_ollama(req.model, [{"role": "user", "content": req.prompt}], research_system)

        SLIDE_FORMAT = (
            "You are a presentation designer. Convert the research below into a polished slide deck.\n\n"
            "CRITICAL: Use EXACTLY this format — each slide starts with '## Slide N: Title' on its own line.\n\n"
            "## Slide 1: Introduction\n"
            "Brief hook and overview (2-3 sentences).\n\n"
            "## Slide 2: Background\n"
            "- Key point 1\n- Key point 2\n- Key point 3\n\n"
            "(Continue for 8-12 slides covering: overview, key facts, data/statistics, "
            "trends, examples, challenges, solutions, conclusion)\n\n"
            "Research to convert:\n"
        )
        ai_output = await call_ollama(req.model,
            [{"role": "user", "content": SLIDE_FORMAT + research}],
            "You are a professional presentation writer. Output ONLY slide content in the ## Slide N: Title format. No preamble.")

        system = ""  # used only for xlsx/docx branch below
    elif req.format == "xlsx":
        system = (AGENT_SYSTEMS["researcher"] +
                  "\nOutput your response as a markdown table with | column | headers |.")
        if mem:
            system += "\n\n" + mem
        ai_output = await call_ollama(req.model, [{"role": "user", "content": req.prompt}], system)
    else:
        system = (AGENT_SYSTEMS["researcher"] + "\n\n" + SKILLS["documentation"] +
                  "\nWrite a well-structured document with # for title, ## for sections.")
        if mem:
            system += "\n\n" + mem
        ai_output = await call_ollama(req.model, [{"role": "user", "content": req.prompt}], system)

    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in title[:40])
    filename  = f"{safe_name}_{ts}.{req.format}"
    out_path  = WORKSPACE_DIR / filename

    if req.format == "pptx":
        slides = parse_ai_to_slides(ai_output, title)
        generate_pptx(title, slides, out_path)
    elif req.format == "xlsx":
        headers, rows = parse_ai_to_table(ai_output)
        generate_xlsx(title, rows, headers, out_path)
    else:
        generate_docx(title, ai_output, out_path)

    stats["files_created"] += 1
    return {
        "filename":  filename,
        "format":    req.format,
        "title":     title,
        "ai_output": ai_output,
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/api/office/download/{filename:path}")
async def download_office_file(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    fp = (WORKSPACE_DIR / filename).resolve()
    if not str(fp).startswith(str(WORKSPACE_DIR.resolve())):
        raise HTTPException(400, "Invalid path")
    if not fp.exists():
        raise HTTPException(404, "File not found")
    media_types = {
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return FileResponse(str(fp), media_type=media_types.get(fp.suffix, "application/octet-stream"), filename=fp.name)


# ── Prompts ────────────────────────────────────────────────────────────────────
PROMPT_LIBRARY_FILE = WORKSPACE_DIR / ".prompt_library.json"

def load_prompt_library() -> list:
    defaults = [
        {"id": "pl_1", "name": "REST API", "category": "coder", "prompt": "Build a complete REST API with FastAPI. Include CRUD endpoints, input validation, error handling, and a README. Use SQLite for storage."},
        {"id": "pl_2", "name": "React Dashboard", "category": "coder", "prompt": "Build a React dashboard with Tailwind CSS. Include a sidebar, stat cards, a data table, and a line chart using recharts."},
        {"id": "pl_3", "name": "Docker Setup", "category": "devops", "prompt": "Create a complete Docker setup for a Python FastAPI app. Include Dockerfile (multi-stage), docker-compose.yml, .env.example, and deployment instructions."},
        {"id": "pl_4", "name": "System Architecture", "category": "architect", "prompt": "Design the full system architecture for a SaaS application with auth, billing, multi-tenancy, and a REST API. Include ASCII diagram and tech stack with reasoning."},
        {"id": "pl_5", "name": "Research Report", "category": "researcher", "prompt": "Research the current state of [TOPIC] in 2024. Include key players, recent developments, pros/cons of main approaches, and recommendations."},
    ]
    if not PROMPT_LIBRARY_FILE.exists():
        PROMPT_LIBRARY_FILE.write_text(json.dumps(defaults, indent=2))
        return defaults
    try:
        return json.loads(PROMPT_LIBRARY_FILE.read_text())
    except Exception:
        return defaults

@app.get("/api/prompts")
async def get_prompts(current_user: dict = Depends(get_current_user)):
    return {"prompts": load_prompt_library()}

@app.post("/api/prompts")
async def save_prompt(body: dict, current_user: dict = Depends(get_current_user)):
    prompts = load_prompt_library()
    new_p   = {
        "id":       f"pl_{datetime.now().timestamp():.0f}",
        "name":     body.get("name", ""),
        "category": body.get("category", "general"),
        "prompt":   body.get("prompt", ""),
    }
    prompts.append(new_p)
    PROMPT_LIBRARY_FILE.write_text(json.dumps(prompts, indent=2))
    audit_log.log("prompt_saved", new_p["name"])
    return new_p

@app.delete("/api/prompts/{prompt_id}")
async def delete_prompt(prompt_id: str, current_user: dict = Depends(get_current_user)):
    prompts = [p for p in load_prompt_library() if p["id"] != prompt_id]
    PROMPT_LIBRARY_FILE.write_text(json.dumps(prompts, indent=2))
    return {"success": True}


# ── Telegram ───────────────────────────────────────────────────────────────────
@app.get("/api/telegram/status")
async def telegram_status(current_user: dict = Depends(get_current_user)):
    return {
        "enabled":       telegram_bot.enabled,
        "configured":    bool(os.getenv("TELEGRAM_BOT_TOKEN", "")),
        "bot_token_set": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "chat_id_set":   bool(os.getenv("TELEGRAM_CHAT_ID")),
    }

@app.post("/api/telegram/test")
async def telegram_test(
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    if not telegram_bot.enabled:
        return {"success": False, "error": "Bot not configured — set TELEGRAM_BOT_TOKEN"}
    telegram_bot.update_model(body.get("model", ""))
    return {"success": True, "message": "Bot is running. Send /start to your bot on Telegram."}


# ── PWA ────────────────────────────────────────────────────────────────────────
@app.get("/api/pwa/manifest")
async def pwa_manifest():
    return {
        "name":             "KreativOS",
        "short_name":       "KreativOS",
        "description":      "Agentic AI Operating System",
        "start_url":        "/",
        "display":          "standalone",
        "background_color": "#0a0a0f",
        "theme_color":      "#8b5cf6",
    }


# ── WebSocket ──────────────────────────────────────────────────────────────────
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, token: str = ""):
    # Auth check before accepting — websocket middleware doesn't run on WS upgrades
    if AUTH_REQUIRED:
        token = websocket.query_params.get("token", "")
        if not token or not auth.verify(token):
            await websocket.close(code=4001)
            return
    await websocket.accept()
    try:
        while True:
            data  = await websocket.receive_json()
            model = data.get("model", "")
            agent = data.get("agent", "general")
            msgs  = data.get("messages", [])
            sys_p = build_full_system_prompt(
                AGENT_SYSTEMS.get(agent, AGENT_SYSTEMS["general"]),
                skills=get_skills_for_agent(agent),
            )
            await websocket.send_json({"type": "start", "agent": agent})
            full = ""
            async for chunk in stream_ollama(model, msgs, sys_p):
                if chunk:
                    full += chunk
                    await websocket.send_json({"type": "chunk", "content": chunk})
            await websocket.send_json({"type": "done", "full": full})
    except WebSocketDisconnect:
        pass


# ── Model Hub ──────────────────────────────────────────────────────────────────
app.include_router(hub_router)

@app.post("/api/hub/pull")
@limiter.limit("5/minute")
async def pull_model(
    request: Request,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    model_name = body.get("model_name", "")
    if not model_name:
        raise HTTPException(400, "model_name required")
    track("model_pull", model_name)

    async def generate():
        async with httpx.AsyncClient(timeout=600) as client:
            async with client.stream(
                "POST", f"{OLLAMA_BASE_URL}/api/pull",
                json={"name": model_name, "stream": True}
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            d   = json.loads(line)
                            t   = d.get("status", "")
                            tot = d.get("total", 0)
                            com = d.get("completed", 0)
                            pct = int(com / tot * 100) if tot > 0 else 0
                            yield f"data: {json.dumps({'status': t, 'pct': pct})}\n\n"
                            if t == "success":
                                break
                        except Exception:
                            continue
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.delete("/api/hub/delete/{model_name:path}")
async def delete_model(
    model_name: str,
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.delete(f"{OLLAMA_BASE_URL}/api/delete", json={"name": model_name})
        return {"success": r.status_code == 200}

# ── Static frontend (built) — SPA fallback LAST so API routes take priority ───────
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")
    # Icons served from dist root (icon-192.png, icon-512.png, etc.)
    app.mount("/icons", StaticFiles(directory=FRONTEND_DIST), name="icons")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve frontend index.html for all non-API routes (SPA fallback)."""
        # Skip API routes
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        # Serve static files if they exist (e.g., favicon.ico, manifest.json)
        static_file = FRONTEND_DIST / full_path
        if static_file.exists() and static_file.is_file():
            return FileResponse(static_file)
        # Fallback to index.html for SPA routing
        return FileResponse(FRONTEND_DIST / "index.html")


# ═══════════════════════════════════════════════════════════════════════════════
#  STARTUP / SHUTDOWN
# ═══════════════════════════════════════════════════════════════════════════════
@app.on_event("startup")
async def startup():
    # Background: scheduler loop
    async def scheduler_loop():
        while True:
            await asyncio.sleep(60)
            due = scheduler.get_due_tasks()
            for t in due:
                try:
                    sys_p = AGENT_SYSTEMS.get(t["agent"], AGENT_SYSTEMS["general"])
                    out   = await call_ollama(t["model"], [{"role": "user", "content": t["prompt"]}], sys_p)
                    scheduler.mark_ran(t["id"], out)
                    extract_and_save_files(out)
                    track("scheduler_auto_ran", t["name"])
                except Exception as e:
                    track("scheduler_error", str(e))

    # [P1-9] Background: expired token cleanup every hour
    async def token_cleanup_loop():
        while True:
            await asyncio.sleep(3600)
            auth.cleanup_expired_tokens()

    # Background: Telegram bot
    async def start_telegram():
        async def task_cb(task, model, agent):
            sys_p = AGENT_SYSTEMS.get(agent, AGENT_SYSTEMS["general"])
            skl   = get_skills_for_agent(agent)
            return await call_ollama(model, [{"role": "user", "content": task}], sys_p + "\n\n" + skl)

        telegram_bot.set_task_callback(task_cb)
        telegram_bot.set_chat_callback(stream_ollama)
        await telegram_bot.start()

    asyncio.create_task(scheduler_loop())
    asyncio.create_task(token_cleanup_loop())
    asyncio.create_task(start_telegram())


@app.on_event("shutdown")
async def shutdown():
    await telegram_bot.stop()
