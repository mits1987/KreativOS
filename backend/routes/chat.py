"""
KreativOS — Chat & Task Routes (streaming, tasks, pipeline, orchestrate)
"""
import asyncio
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import state
from .. import conversations
from .. import run_history
from .. import backup as backup_mod
from ..config import AGENT_SYSTEMS, AGENT_PERSONAS, get_skills_for_agent
from ..context_manager import build_full_system_prompt
from ..engine import (
    call_ollama, stream_ollama, ralph_loop, extract_and_save_files,
)
from ..auth import get_current_user
from ..orchestrator import orchestrate as run_orchestration
from ..pipeline import get_all_templates, save_user_template, delete_user_template, run_pipeline
from ..sandbox import run_code_sandboxed
from ..web_search import duckduckgo_search, format_results_for_agent
from ..telegram_utils import send_telegram_artifact
from .. import github_client as gh
from .. import knowledge
from .. import permissions as perms
from ..auth import AUTH_REQUIRED

_PROTECTED = {".memory", ".auth", ".scheduler", ".workflows", ".backups", ".skill_eval", ".audit", ".versions"}
_running_tasks: dict[str, tuple[asyncio.Task, asyncio.Event]] = {}

router = APIRouter(tags=["chat"])
limiter = Limiter(key_func=get_remote_address)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    agent: str = "general"
    project: str = ""
    use_web_search: bool = False


class TaskRequest(BaseModel):
    task: str
    model: str
    agent_type: str = "coder"
    use_ralph_loop: bool = True
    project: str = ""


class PipelineRequest(BaseModel):
    task: str
    model: str
    template: str = "full_app"
    project: str = ""
    skip_ralph: bool = False


class FileWriteRequest(BaseModel):
    filename: str
    content: str = Field(max_length=10_000_000)


class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"


class CodeReviewRequest(BaseModel):
    code: str
    language: str
    model: str
    filename: str = ""


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


class OfficeRequest(BaseModel):
    prompt: str
    model: str
    format: str = "pptx"
    title: str = ""
    project: str = ""


class McpServerRequest(BaseModel):
    name: str
    url: str
    description: str = ""
    enabled: bool = True


class McpCallRequest(BaseModel):
    server: str
    tool: str
    args: dict = {}


# ── File helpers ──────────────────────────────────────────────────────────────
def _check_file_permission(path, operation):
    from pathlib import Path as _Path
    fp = _Path(path).expanduser().resolve()
    if perms.is_allowed(str(fp)):
        return None
    return perms.request_access(str(fp), operation)


# ── File routes ───────────────────────────────────────────────────────────────
@router.get("/api/files/list")
async def list_files(limit: int = 50, offset: int = 0, current_user: dict = Depends(get_current_user)):
    all_files = []
    for f in state.WORKSPACE_DIR.rglob("*"):
        if f.is_file() and not any(
            p in str(f) for p in [".memory", ".auth", ".scheduler", ".workflows", ".backups", ".skill_eval", ".audit", ".versions"]
        ):
            all_files.append({
                "name": str(f.relative_to(state.WORKSPACE_DIR)),
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    all_files.sort(key=lambda x: x["modified"], reverse=True)
    total = len(all_files)
    page = all_files[offset: offset + limit]
    return {"files": page, "total": total, "limit": limit, "offset": offset, "workspace": str(state.WORKSPACE_DIR)}


@router.post("/api/files/write")
async def write_file(req: FileWriteRequest, current_user: dict = Depends(get_current_user)):
    from pathlib import Path as _Path
    raw = req.filename
    fp = _Path(state.WORKSPACE_DIR / raw).expanduser().resolve()
    perm = _check_file_permission(str(fp), "write")
    if perm:
        raise HTTPException(403, detail=str(perm))
    if fp.exists():
        versions_dir = Path(state.WORKSPACE_DIR) / ".versions"
        versions_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{raw}__{ts}"
        shutil.copy2(str(fp), str(versions_dir / backup_name))
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(req.content)
    state.stats["files_created"] = state.stats.get("files_created", 0) + 1
    state.track("file_saved", raw)
    return {"success": True, "path": str(fp)}


@router.get("/api/files/{filename:path}/history")
async def file_history(filename: str, current_user: dict = Depends(get_current_user)):
    versions_dir = Path(state.WORKSPACE_DIR) / ".versions"
    if not versions_dir.exists():
        return []
    prefix = f"{filename}__"
    versions = []
    for f in sorted(versions_dir.iterdir(), reverse=True):
        if f.is_file() and f.name.startswith(prefix):
            ts = f.name[len(prefix):]
            versions.append({
                "filename": f.name,
                "timestamp": ts,
                "size": f.stat().st_size,
            })
    return versions


@router.post("/api/files/restore/{backup_name:path}")
async def restore_file_version(backup_name: str, current_user: dict = Depends(get_current_user)):
    versions_dir = Path(state.WORKSPACE_DIR) / ".versions"
    backup_path = versions_dir / backup_name
    if not backup_path.exists():
        raise HTTPException(404, "Version not found")
    original_name = backup_name.rsplit("__", 1)[0]
    target = Path(state.WORKSPACE_DIR) / original_name
    if not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(backup_path), str(target))
    return {"ok": True, "restored": original_name}


@router.get("/api/files/read/{filename:path}")
async def read_file(filename: str, current_user: dict = Depends(get_current_user)):
    if any(p in filename for p in _PROTECTED):
        raise HTTPException(403, "Protected path")
    from pathlib import Path as _Path
    raw = filename
    fp = _Path(state.WORKSPACE_DIR / raw).expanduser().resolve()
    perm = _check_file_permission(str(fp), "read")
    if perm:
        raise HTTPException(403, detail=str(perm))
    if not fp.exists():
        raise HTTPException(404, "Not found")
    return {"filename": raw, "content": fp.read_text()}


@router.delete("/api/files/delete/{filename:path}")
@limiter.limit("60/minute")
async def delete_file(request: Request, filename: str, current_user: dict = Depends(get_current_user)):
    if any(p in filename for p in _PROTECTED):
        raise HTTPException(403, "Protected path")
    from pathlib import Path as _Path
    raw = filename
    fp = _Path(state.WORKSPACE_DIR / raw).expanduser().resolve()
    perm = _check_file_permission(str(fp), "delete")
    if perm:
        raise HTTPException(403, detail=str(perm))
    if fp.exists():
        fp.unlink()
    return {"success": True}


# ── Code Execution ────────────────────────────────────────────────────────────
@router.post("/api/execute")
@limiter.limit("20/minute")
async def execute_code(request: Request, req: ExecuteRequest, current_user: dict = Depends(get_current_user)):
    state.stats["code_executions"] = state.stats.get("code_executions", 0) + 1
    state.track("code_exec", req.language)
    external_paths = perms.check_code_paths(req.code, state.WORKSPACE_DIR)
    if external_paths:
        result = perms.request_access(external_paths[0], "execute")
        if result and result.get("status") != "allowed":
            raise HTTPException(403, detail=str(result))
    result = await asyncio.to_thread(run_code_sandboxed, req.code, req.language, workspace_dir=str(state.WORKSPACE_DIR))
    return result


# ── Chat ──────────────────────────────────────────────────────────────────────
@router.post("/api/chat/stream")
@limiter.limit("30/minute")
async def chat_stream(request: Request, req: ChatRequest, current_user: dict = Depends(get_current_user)):
    state.stats["total_messages"] = state.stats.get("total_messages", 0) + 1
    state.track("chat", f"agent:{req.agent}")
    system = AGENT_SYSTEMS.get(req.agent, AGENT_SYSTEMS["general"])
    skills = get_skills_for_agent(req.agent or "general")
    mem_ctx = state.memory.build_context(req.project) if req.project and state.memory else ""
    search_ctx = ""
    if req.use_web_search or req.agent == "researcher":
        last_user = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
        if last_user:
            results = await duckduckgo_search(last_user[:200], 4)
            search_ctx = format_results_for_agent(last_user[:200], results)
            state.stats["searches_run"] = state.stats.get("searches_run", 0) + 1
    full_system = build_full_system_prompt(system, skills, mem_ctx, search_ctx)
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    async def generate():
        async for chunk in stream_ollama(req.model, messages, full_system):
            if chunk:
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            else:
                yield ": keepalive\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Conversations (SQLite persistence) ────────────────────────────────────────
@router.get("/api/conversations")
async def list_convs(limit: int = 50, offset: int = 0):
    return conversations.list_conversations(state.WORKSPACE_DIR, limit, offset)


@router.get("/api/conversations/search")
async def search_convs(q: str = "", limit: int = 20):
    if not q:
        return []
    return conversations.search_conversations(state.WORKSPACE_DIR, q, limit)


@router.get("/api/conversations/{conv_id}")
async def get_conv(conv_id: str):
    conv = conversations.get_conversation(state.WORKSPACE_DIR, conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.post("/api/conversations")
async def create_conv(data: dict):
    return conversations.create_conversation(
        state.WORKSPACE_DIR,
        title=data.get("title", "New Chat"),
        model=data.get("model", "")
    )


@router.post("/api/conversations/{conv_id}/messages")
async def add_msg(conv_id: str, data: dict):
    return conversations.add_message(
        state.WORKSPACE_DIR, conv_id,
        data.get("role", "user"),
        data.get("content", "")
    )


@router.delete("/api/conversations/{conv_id}")
async def delete_conv(conv_id: str):
    ok = conversations.delete_conversation(state.WORKSPACE_DIR, conv_id)
    if not ok:
        raise HTTPException(404, "Conversation not found")
    return {"ok": True}


# ── Tasks ─────────────────────────────────────────────────────────────────────
@router.post("/api/task/run")
@limiter.limit("10/minute")
async def run_task(request: Request, req: TaskRequest, current_user: dict = Depends(get_current_user)):
    state.stats["total_tasks"] = state.stats.get("total_tasks", 0) + 1
    state.stats["tasks_by_agent"] = state.stats.get("tasks_by_agent", {})
    state.stats["tasks_by_agent"][req.agent_type] = state.stats["tasks_by_agent"].get(req.agent_type, 0) + 1
    state.track("task_start", f"{req.agent_type}: {req.task[:50]}")
    run_id = str(uuid.uuid4())[:12]
    run_history.record_run_start(run_id, task_id="", conv_id="", agent_name=req.agent_type, workflow_name="task")
    try:
        sys_prompt = AGENT_SYSTEMS.get(req.agent_type, AGENT_SYSTEMS["general"])
        skills = get_skills_for_agent(req.agent_type)
        mem = state.memory.build_context(req.project) if req.project and state.memory else ""
        full = build_full_system_prompt(sys_prompt, skills, mem)
        out = await call_ollama(req.model, [{"role": "user", "content": req.task}], full)
        saved = extract_and_save_files(out, req.project)
        for f in saved:
            asyncio.create_task(send_telegram_artifact(str(state.WORKSPACE_DIR / f), f"Task generated: {Path(f).name}"))
        ralph = None
        if req.use_ralph_loop and req.agent_type in ("coder", "architect", "devops"):
            ralph = await ralph_loop(req.model, req.task, out, req.agent_type)
            out = ralph["output"]
            n = len(saved)
            saved += extract_and_save_files(out, req.project)
            for f in saved[n:]:
                asyncio.create_task(send_telegram_artifact(str(state.WORKSPACE_DIR / f), f"Task generated: {Path(f).name}"))
        if req.project and state.memory:
            state.memory.add_decision(req.project, f"{req.agent_type}: {req.task[:60]}", req.agent_type)
        if state.audit_log:
            state.audit_log.log("task_done", req.task[:80], agent=req.agent_type)
        state.track("task_done", req.agent_type)
        run_history.record_run_end(run_id, "completed", files_generated=list(set(saved)))
        return {
            "task": req.task,
            "agent": AGENT_PERSONAS.get(req.agent_type, AGENT_PERSONAS["general"])["name"],
            "result": out,
            "saved_files": list(set(saved)),
            "ralph": ralph,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        run_history.record_run_end(run_id, "failed", error=str(e))
        raise


# ── Orchestrator ──────────────────────────────────────────────────────────────
@router.post("/api/orchestrate")
@limiter.limit("5/minute")
async def orchestrate_endpoint(request: Request, body: dict, current_user: dict = Depends(get_current_user)):
    task = body.get("task", "").strip()
    model = body.get("model", "").strip()
    project = body.get("project", "")
    if not task or not model:
        raise HTTPException(400, "task and model required")
    state.track("orchestrate", task[:60])
    if state.audit_log:
        state.audit_log.log("orchestrate", f"Task: {task[:80]}", user=current_user.get("username"))

    task_id = uuid.uuid4().hex[:8]
    cancel_event = asyncio.Event()

    async def event_stream():
        t = asyncio.current_task()
        _running_tasks[task_id] = (t, cancel_event)
        try:
            async for event in run_orchestration(task, model, project, state.WORKSPACE_DIR, state.OLLAMA_BASE_URL, cancel_event, conv_id=body.get("conv_id", "")):
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            yield f"data: {json.dumps({'type': 'cancelled', 'task_id': task_id})}\n\n"
        finally:
            _running_tasks.pop(task_id, None)
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Task Cancel ───────────────────────────────────────────────────────────────
@router.get("/api/tasks")
async def list_running_tasks(current_user: dict = Depends(get_current_user)):
    tasks = []
    for tid, (t, _) in list(_running_tasks.items()):
        if t.done():
            status = "cancelled" if t.cancelled() else "done"
        else:
            status = "running"
        tasks.append({"id": tid, "status": status})
    return {"tasks": tasks}


@router.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, current_user: dict = Depends(get_current_user)):
    entry = _running_tasks.get(task_id)
    if not entry:
        raise HTTPException(404, "Task not found")
    task, cancel_event = entry
    cancel_event.set()
    task.cancel()
    return {"ok": True}


# ── Run History ────────────────────────────────────────────────────────────────
@router.get("/api/runs")
async def list_runs(limit: int = 50, conv_id: str = None):
    return run_history.get_recent_runs(limit=limit, conv_id=conv_id)

@router.get("/api/runs/stats")
async def run_stats():
    return run_history.get_run_stats()


# ── Pipeline ──────────────────────────────────────────────────────────────────
@router.get("/api/pipeline/templates")
async def pipeline_templates(current_user: dict = Depends(get_current_user)):
    templates = get_all_templates(state.WORKSPACE_DIR)
    return {"templates": [{"id": k, "steps": [s["label"] for s in v]} for k, v in templates.items()]}


@router.get("/api/pipelines")
async def list_pipelines(current_user: dict = Depends(get_current_user)):
    """Return all pipeline templates (built-in + user-defined)."""
    return get_all_templates(state.WORKSPACE_DIR)


@router.post("/api/pipelines")
async def save_pipeline(data: dict, current_user: dict = Depends(get_current_user)):
    name = data.get("name", "")
    phases = data.get("phases", [])
    if not name or not phases:
        raise HTTPException(400, "name and phases required")
    return save_user_template(state.WORKSPACE_DIR, name, phases)


@router.delete("/api/pipelines/{name}")
async def delete_pipeline(name: str, current_user: dict = Depends(get_current_user)):
    ok = delete_user_template(state.WORKSPACE_DIR, name)
    if not ok:
        raise HTTPException(404, "Pipeline not found")
    return {"ok": True}


@router.post("/api/pipeline/run")
@limiter.limit("5/minute")
async def run_pipeline_route(request: Request, req: PipelineRequest, current_user: dict = Depends(get_current_user)):
    state.stats["pipelines_run"] = state.stats.get("pipelines_run", 0) + 1
    state.stats["total_tasks"] = state.stats.get("total_tasks", 0) + 1
    state.track("pipeline_start", f"{req.template}: {req.task[:50]}")

    task_id = uuid.uuid4().hex[:8]
    cancel_event = asyncio.Event()

    async def generate():
        t = asyncio.current_task()
        _running_tasks[task_id] = (t, cancel_event)
        try:
            async for event in run_pipeline(
                task=req.task, template=req.template, model=req.model,
                call_ollama_fn=call_ollama, agent_systems=AGENT_SYSTEMS,
                get_skills_fn=get_skills_for_agent, ralph_fn=ralph_loop,
                workspace_dir=state.WORKSPACE_DIR, track_fn=state.track,
                extract_fn=lambda t: extract_and_save_files(t, req.project),
                skip_ralph=req.skip_ralph,
                cancel_event=cancel_event,
            ):
                yield f"data: {json.dumps(event)}\n\n"
                if event["type"] == "done":
                    if req.project and state.memory:
                        state.memory.add_decision(req.project, f"Pipeline '{req.template}' run: {req.task[:60]}", "orchestrator")
                    if state.audit_log:
                        state.audit_log.log("pipeline_done", req.template)
                    state.track("pipeline_done", req.template)
        except asyncio.CancelledError:
            yield f"data: {json.dumps({'type': 'cancelled', 'task_id': task_id})}\n\n"
        finally:
            _running_tasks.pop(task_id, None)
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Agent Models ──────────────────────────────────────────────────────────────
@router.get("/api/settings/agent-models")
async def get_agent_models(current_user: dict = Depends(get_current_user)):
    fp = state.WORKSPACE_DIR / ".agent_models.json"
    if fp.exists():
        return json.loads(fp.read_text(encoding="utf-8"))
    return {}


@router.post("/api/settings/agent-models")
async def set_agent_models(data: dict, current_user: dict = Depends(get_current_user)):
    fp = state.WORKSPACE_DIR / ".agent_models.json"
    tmp = fp.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(fp)
    return {"ok": True}


# ── Agent Prompts ─────────────────────────────────────────────────────────────
@router.get("/api/settings/agent-prompts")
async def get_agent_prompts(current_user: dict = Depends(get_current_user)):
    prompts_dir = Path(state.WORKSPACE_DIR) / ".agent_prompts"
    overrides = {}
    if prompts_dir.exists():
        for f in prompts_dir.glob("*.json"):
            overrides[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return overrides


@router.post("/api/settings/agent-prompts/{agent_id}")
async def set_agent_prompt(agent_id: str, data: dict, current_user: dict = Depends(get_current_user)):
    prompt = data.get("prompt", "")
    prompts_dir = Path(state.WORKSPACE_DIR) / ".agent_prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    fp = prompts_dir / f"{agent_id}.json"
    tmp = fp.with_suffix(".tmp")
    tmp.write_text(json.dumps({"system": prompt}, indent=2), encoding="utf-8")
    tmp.replace(fp)
    return {"ok": True, "agent": agent_id}


@router.delete("/api/settings/agent-prompts/{agent_id}")
async def delete_agent_prompt(agent_id: str, current_user: dict = Depends(get_current_user)):
    fp = Path(state.WORKSPACE_DIR) / ".agent_prompts" / f"{agent_id}.json"
    if fp.exists():
        fp.unlink()
    return {"ok": True}


# ── Memory ────────────────────────────────────────────────────────────────────
@router.get("/api/memory/projects")
async def list_projects(limit: int = 50, offset: int = 0, current_user: dict = Depends(get_current_user)):
    if not state.memory:
        return {"projects": [], "total": 0, "limit": limit, "offset": offset}
    projects = state.memory.list_projects(limit=limit, offset=offset)
    return {"projects": projects, "total": state.memory.count_projects(), "limit": limit, "offset": offset}


@router.get("/api/memory/{project}")
async def get_memory(project: str, current_user: dict = Depends(get_current_user)):
    return state.memory.get(project) if state.memory else {}


@router.post("/api/memory/{project}/note")
async def add_note(project: str, body: dict, current_user: dict = Depends(get_current_user)):
    if state.memory:
        state.memory.add_note(project, body.get("note", ""))
    return {"success": True}


@router.delete("/api/memory/{project}")
async def delete_memory(project: str, current_user: dict = Depends(get_current_user)):
    if state.memory:
        state.memory.delete(project)
    return {"success": True}


# ── GitHub ────────────────────────────────────────────────────────────────────
@router.get("/api/github/repos")
async def github_list_repos():
    repos = await gh.list_repos()
    return repos

@router.post("/api/github/issues")
async def github_create_issue(data: dict):
    result = await gh.create_issue(data["owner"], data["repo"], data["title"], data.get("body", ""), data.get("labels"))
    return result

@router.post("/api/github/commit")
async def github_commit_file(data: dict):
    result = await gh.commit_file(data["owner"], data["repo"], data["path"], data["content"], data["message"], data.get("branch", "main"))
    return result


# ── Web Search ────────────────────────────────────────────────────────────────
@router.get("/api/search")
async def web_search(q: str, max_results: int = 5, current_user: dict = Depends(get_current_user)):
    state.stats["searches_run"] = state.stats.get("searches_run", 0) + 1
    state.track("web_search", q[:60])
    results = await duckduckgo_search(q, max_results)
    return {"query": q, "results": results}


# ── Knowledge / RAG ──────────────────────────────────────────────────────────
@router.post("/api/knowledge/upload")
async def upload_document(request: Request):
    import tempfile
    form = await request.form()
    file = form.get("file")
    if not file:
        raise HTTPException(400, "No file provided")
    content = await file.read()
    suffix = Path(file.filename).suffix or ".txt"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(content)
    tmp.close()
    result = knowledge.ingest_document(state.WORKSPACE_DIR, Path(tmp.name))
    os.unlink(tmp.name)
    return result


@router.get("/api/knowledge/search")
async def search_knowledge_route(q: str = "", top_k: int = 5):
    return knowledge.search_knowledge(state.WORKSPACE_DIR, q, top_k)


@router.get("/api/knowledge/documents")
async def list_knowledge_docs():
    return knowledge.list_documents(state.WORKSPACE_DIR)


@router.delete("/api/knowledge/documents/{doc_id}")
async def delete_knowledge_doc(doc_id: str):
    ok = knowledge.delete_document(state.WORKSPACE_DIR, doc_id)
    if not ok:
        raise HTTPException(404, "Document not found")
    return {"ok": True}


# ── App Builder ───────────────────────────────────────────────────────────────
@router.post("/api/appbuilder/generate")
@limiter.limit("5/minute")
async def generate_app(request: Request, body: dict, current_user: dict = Depends(get_current_user)):
    description = body.get("description", "")
    model = body.get("model", "")
    app_type = body.get("app_type", "web")
    project = body.get("project", "")
    skip_ralph = bool(body.get("skip_ralph", False))
    state.stats["total_tasks"] = state.stats.get("total_tasks", 0) + 1
    state.track("appbuilder", description[:50])
    system = build_full_system_prompt(
        AGENT_SYSTEMS["coder"],
        skills=get_skills_for_agent("coder"),
        memory_context=state.memory.build_context(project) if project and state.memory else "",
    )
    prompt = (
        f"Build a complete, working {app_type} application:\n\n{description}\n\n"
        "Requirements:\n1. Write ALL files needed — frontend, backend, config\n"
        "2. Each file must start with: # filename: path/to/file\n"
        "3. Include package.json/requirements.txt\n4. Include a README.md with setup instructions\n"
        "5. The app must be runnable immediately after following the README\n\n"
        "Write every file completely — no placeholders."
    )
    output = await call_ollama(model, [{"role": "user", "content": prompt}], system)
    ralph = None
    if not skip_ralph:
        ralph = await ralph_loop(model, description, output, "coder")
        output = ralph["output"]
    saved = extract_and_save_files(output, project)
    for f in saved:
        asyncio.create_task(send_telegram_artifact(str(state.WORKSPACE_DIR / f), f"App generated: {Path(f).name}"))
    if project and state.memory:
        state.memory.add_decision(project, f"Built {app_type} app: {description[:60]}", "coder")
    return {"description": description, "output": output, "saved_files": saved, "ralph": ralph, "timestamp": datetime.now().isoformat()}


@router.get("/api/appbuilder/preview/{filename:path}")
async def preview_file(filename: str, current_user: dict = Depends(get_current_user)):
    from pathlib import Path as _Path
    fp = (_Path(state.WORKSPACE_DIR) / filename).resolve()
    if not str(fp).startswith(str(_Path(state.WORKSPACE_DIR).resolve())):
        raise HTTPException(400, "Invalid path")
    if not fp.exists():
        raise HTTPException(404, "File not found")
    return {"filename": filename, "content": fp.read_text(), "extension": fp.suffix}


# ── Canvas ────────────────────────────────────────────────────────────────────
def _load_workflows() -> list:
    wf_file = state.WORKSPACE_DIR / ".workflows.json"
    if not wf_file.exists():
        return []
    try:
        return json.loads(wf_file.read_text())
    except Exception:
        return []


def _save_workflows(wf: list):
    (state.WORKSPACE_DIR / ".workflows.json").write_text(json.dumps(wf, indent=2))


@router.get("/api/canvas/workflows")
async def get_workflows(current_user: dict = Depends(get_current_user)):
    return {"workflows": _load_workflows()}


@router.get("/api/canvas/workflows/{wf_id}/export")
async def export_workflow(wf_id: str, current_user: dict = Depends(get_current_user)):
    workflows = _load_workflows()
    wf = next((w for w in workflows if w["id"] == wf_id), None)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return JSONResponse(
        content=wf,
        headers={"Content-Disposition": f"attachment; filename=workflow-{wf_id}.json"}
    )


@router.post("/api/canvas/workflows/import")
async def import_workflow(data: dict, current_user: dict = Depends(get_current_user)):
    name = data.get("name") or data.get("id", "imported")
    wf_id = data.get("id", name)
    import uuid
    wf = {
        "id": wf_id, "name": name,
        "description": data.get("description", ""),
        "nodes": data.get("nodes", []),
        "edges": data.get("edges", []),
        "created": data.get("created", datetime.now().isoformat()),
    }
    workflows = _load_workflows()
    # replace if same id, else append
    workflows = [w for w in workflows if w["id"] != wf_id]
    workflows.append(wf)
    _save_workflows(workflows)
    return {"ok": True, "id": wf_id, "name": name}


@router.post("/api/canvas/workflows")
async def save_workflow(wf: WorkflowRequest, current_user: dict = Depends(get_current_user)):
    import uuid
    workflows = _load_workflows()
    new_wf = {
        "id": f"wf_{uuid.uuid4().hex[:8]}", "name": wf.name,
        "description": wf.description, "nodes": wf.nodes, "edges": wf.edges,
        "created": datetime.now().isoformat(),
    }
    workflows.append(new_wf)
    _save_workflows(workflows)
    return new_wf


@router.delete("/api/canvas/workflows/{wf_id}")
async def delete_workflow(wf_id: str, current_user: dict = Depends(get_current_user)):
    _save_workflows([w for w in _load_workflows() if w["id"] != wf_id])
    return {"success": True}


@router.post("/api/canvas/run/{wf_id}")
async def run_workflow(wf_id: str, body: dict, current_user: dict = Depends(get_current_user)):
    from collections import deque
    wfs = _load_workflows()
    wf = next((w for w in wfs if w["id"] == wf_id), None)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    model = body.get("model", "")
    task = body.get("task", "")
    state.track("canvas_run", wf["name"])
    raw_nodes = wf["nodes"]
    edges = wf.get("edges", [])
    if edges:
        node_map = {n["id"]: n for n in raw_nodes}
        in_deg = {n["id"]: 0 for n in raw_nodes}
        adj = {n["id"]: [] for n in raw_nodes}
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
        if len(nodes) != len(raw_nodes):
            nodes = sorted(raw_nodes, key=lambda n: n.get("position", {}).get("x", 0))
    else:
        nodes = sorted(raw_nodes, key=lambda n: n.get("position", {}).get("x", 0))
    results, context = [], task
    for node in nodes:
        agent_id = node.get("data", {}).get("agent", "general")
        label = node.get("data", {}).get("label", "Step")
        sys_p = build_full_system_prompt(
            AGENT_SYSTEMS.get(agent_id, AGENT_SYSTEMS["general"]),
            skills=get_skills_for_agent(agent_id),
        )
        out = await call_ollama(model, [{"role": "user", "content": context}], sys_p)
        saved = extract_and_save_files(out)
        for f in saved:
            asyncio.create_task(send_telegram_artifact(str(state.WORKSPACE_DIR / f), f"Workflow {label}: {Path(f).name}"))
        handoff = None
        for line in out.split("\n"):
            if line.strip().startswith("HANDOFF:"):
                handoff = line.split(":", 1)[1].strip()
                break
        results.append({"node": label, "agent": agent_id, "output": out, "saved_files": saved, "handoff_to": handoff})
        context += f"\n\n[{label}]: {out}"
        if handoff and handoff in AGENT_SYSTEMS:
            h_sys = build_full_system_prompt(AGENT_SYSTEMS[handoff], skills=get_skills_for_agent(handoff))
            h_out = await call_ollama(model, [{"role": "user", "content": context}], h_sys)
            h_saved = extract_and_save_files(h_out)
            for f in h_saved:
                asyncio.create_task(send_telegram_artifact(str(state.WORKSPACE_DIR / f), f"Workflow handoff {handoff}: {Path(f).name}"))
            results.append({"node": f"Handoff → {handoff}", "agent": handoff, "output": h_out, "saved_files": h_saved})
            context += f"\n\n[Handoff {handoff}]: {h_out}"
    return {"workflow": wf["name"], "task": task, "results": results, "timestamp": datetime.now().isoformat()}


# ── Code Review ───────────────────────────────────────────────────────────────
@router.post("/api/review")
@limiter.limit("20/minute")
async def review_code(request: Request, req: CodeReviewRequest, current_user: dict = Depends(get_current_user)):
    state.stats["total_tasks"] = state.stats.get("total_tasks", 0) + 1
    state.track("code_review", req.filename or req.language)
    prompt = f"Review this {req.language} code" + (f" from file: {req.filename}" if req.filename else "") + f":\n\n```{req.language}\n{req.code}\n```\n\nProvide a thorough code review following the structured format."
    output = await call_ollama(req.model, [{"role": "user", "content": prompt}], AGENT_SYSTEMS["code_reviewer"])
    return {"review": output, "language": req.language, "filename": req.filename, "timestamp": datetime.now().isoformat()}


# ── Scheduler ─────────────────────────────────────────────────────────────────
@router.get("/api/scheduler/tasks")
async def list_scheduled(current_user: dict = Depends(get_current_user)):
    return {"tasks": state.scheduler.list_tasks()} if state.scheduler else {"tasks": []}


@router.post("/api/scheduler/tasks")
async def create_scheduled(req: ScheduleRequest, current_user: dict = Depends(get_current_user)):
    if not state.scheduler:
        raise HTTPException(503, "Scheduler not available")
    t = state.scheduler.add_task(req.name, req.prompt, req.agent, req.model, req.interval, req.hour)
    state.track("scheduler_add", req.name)
    return t


@router.delete("/api/scheduler/tasks/{task_id}")
async def delete_scheduled(task_id: str, current_user: dict = Depends(get_current_user)):
    if state.scheduler:
        state.scheduler.delete_task(task_id)
    return {"success": True}


@router.post("/api/scheduler/tasks/{task_id}/toggle")
async def toggle_scheduled(task_id: str, current_user: dict = Depends(get_current_user)):
    enabled = state.scheduler.toggle_task(task_id) if state.scheduler else False
    return {"enabled": enabled}


@router.post("/api/scheduler/run-due")
async def run_due_tasks(body: dict, current_user: dict = Depends(get_current_user)):
    if not state.scheduler:
        return {"ran": 0, "results": []}
    due = state.scheduler.get_due_tasks()
    results = []
    for t in due:
        sys_p = AGENT_SYSTEMS.get(t["agent"], AGENT_SYSTEMS["general"])
        out = await call_ollama(t["model"], [{"role": "user", "content": t["prompt"]}], sys_p)
        state.scheduler.mark_ran(t["id"], out)
        saved = extract_and_save_files(out)
        for f in saved:
            asyncio.create_task(send_telegram_artifact(str(state.WORKSPACE_DIR / f), f"Scheduled {t['name']}: {Path(f).name}"))
        results.append({"task": t["name"], "output": out, "saved_files": saved})
        state.track("scheduler_ran", t["name"])
    return {"ran": len(results), "results": results}


# ── Audit ─────────────────────────────────────────────────────────────────────
@router.get("/api/audit")
async def get_audit_log(n: int = 100, offset: int = 0, q: str = "", current_user: dict = Depends(get_current_user)):
    if not state.audit_log:
        return {"entries": [], "stats": {}, "total": 0}
    if q:
        return {"entries": state.audit_log.search(q, n, offset)}
    return {"entries": state.audit_log.tail(n, offset), "stats": state.audit_log.stats(), "total": state.audit_log.count()}


# ── Skills ────────────────────────────────────────────────────────────────────
@router.get("/api/skills/leaderboard")
async def skill_leaderboard(current_user: dict = Depends(get_current_user)):
    lb = state.skill_eval.leaderboard() if state.skill_eval else []
    return {"leaderboard": lb, "timestamp": datetime.now().isoformat()}


@router.get("/api/skills/catalog")
async def skills_catalog(current_user: dict = Depends(get_current_user)):
    from ..config import get_local_skills, SKILLS
    catalog = []
    local_skills = get_local_skills()
    for k, v in local_skills.items():
        catalog.append({"id": k, "name": v.get("name", k).replace("-", " ").title(), "description": v.get("description", ""), "source": "opencode", "preview": v.get("content", "")[:300]})
    for k in SKILLS:
        catalog.append({"id": k, "name": k.title(), "description": f"Built-in skill for {k} best practices", "source": "builtin", "preview": SKILLS[k][:300]})
    return {"catalog": catalog}


@router.get("/api/skills/{agent}")
async def agent_skill_stats(agent: str, current_user: dict = Depends(get_current_user)):
    return state.skill_eval.get_agent(agent) if state.skill_eval else {"runs": [], "avg_score": 0}


# ── MCP ───────────────────────────────────────────────────────────────────────
@router.get("/api/mcp/servers")
async def mcp_list(current_user: dict = Depends(get_current_user)):
    from ..mcp_client import load_servers as _ls
    return {"servers": _ls()}


@router.post("/api/mcp/servers")
async def mcp_add(req: McpServerRequest, current_user: dict = Depends(get_current_user)):
    from ..mcp_client import load_servers as _ls, save_servers as _ss, _validate_mcp_url
    _validate_mcp_url(req.url)
    servers = _ls()
    if any(s["name"] == req.name for s in servers):
        raise HTTPException(400, "Server name already exists")
    servers.append(req.model_dump())
    _ss(servers)
    return {"ok": True}


@router.delete("/api/mcp/servers/{name}")
async def mcp_delete(name: str, current_user: dict = Depends(get_current_user)):
    from ..mcp_client import load_servers as _ls, save_servers as _ss
    _ss([s for s in _ls() if s["name"] != name])
    return {"ok": True}


@router.get("/api/mcp/servers/{name}/tools")
async def mcp_tools(name: str, current_user: dict = Depends(get_current_user)):
    from ..mcp_client import load_servers as _ls, list_tools as _lt
    server = next((s for s in _ls() if s["name"] == name), None)
    if not server:
        raise HTTPException(404, "Server not found")
    try:
        tools = await _lt(server["url"])
        return {"tools": tools}
    except ConnectionError as e:
        return {"tools": [], "error": str(e)}


@router.post("/api/mcp/call")
@limiter.limit("60/minute")
async def mcp_call(request: Request, req: McpCallRequest, current_user: dict = Depends(get_current_user)):
    from ..mcp_client import call_tool as _ct
    try:
        result = await _ct(req.server, req.tool, req.args)
        return {"result": result}
    except ConnectionError as e:
        return {"result": None, "error": str(e)}


# ── Backup ────────────────────────────────────────────────────────────────────
@router.post("/api/backup/create")
@limiter.limit("3/hour")
async def create_backup(request: Request, current_user: dict = Depends(get_current_user)):
    if state.audit_log:
        state.audit_log.log("backup_create")
    state.track("backup", "Creating backup…")
    out_path, size_mb = backup_mod.create_backup(state.WORKSPACE_DIR)
    if state.audit_log:
        state.audit_log.log("backup_done", out_path.name)
    return {"filename": out_path.name, "size_mb": size_mb, "timestamp": datetime.now().isoformat()}


@router.get("/api/backup/list")
async def list_backups(current_user: dict = Depends(get_current_user)):
    return {"backups": backup_mod.list_backups()}


@router.get("/api/backup/download/{filename}")
async def download_backup(filename: str, current_user: dict = Depends(get_current_user)):
    if not filename.startswith("kreavitos_backup_") or not filename.endswith(".tar.gz"):
        raise HTTPException(400, "Invalid backup filename")
    fp = (Path(state.WORKSPACE_DIR) / ".backups" / filename).resolve()
    if not str(fp).startswith(str((Path(state.WORKSPACE_DIR) / ".backups").resolve())):
        raise HTTPException(400, "Invalid path")
    if not fp.exists():
        raise HTTPException(404, "Backup not found")
    return FileResponse(str(fp), media_type="application/gzip", filename=filename)


@router.delete("/api/backup/{filename}")
async def delete_backup(filename: str, current_user: dict = Depends(get_current_user)):
    fp = (Path(state.WORKSPACE_DIR) / ".backups" / filename).resolve()
    if not str(fp).startswith(str((Path(state.WORKSPACE_DIR) / ".backups").resolve())):
        raise HTTPException(400, "Invalid path")
    ok = backup_mod.delete_backup(filename)
    if not ok:
        raise HTTPException(404, "Backup not found")
    if state.audit_log:
        state.audit_log.log("backup_delete", filename)
    return {"success": True}


@router.post("/api/backup/restore/{filename}")
@limiter.limit("3/hour")
async def restore_backup(request: Request, filename: str, current_user: dict = Depends(get_current_user)):
    fp = (Path(state.WORKSPACE_DIR) / ".backups" / filename).resolve()
    if not str(fp).startswith(str((Path(state.WORKSPACE_DIR) / ".backups").resolve())):
        raise HTTPException(400, "Invalid path")
    if state.audit_log:
        state.audit_log.log("backup_restore", filename)
    ok = backup_mod.restore_backup(filename, state.WORKSPACE_DIR)
    if not ok:
        raise HTTPException(404, "Backup not found")
    return {"success": True, "message": "Workspace restored. Restart recommended."}


# ── Office ────────────────────────────────────────────────────────────────────
@router.post("/api/office/generate")
async def generate_office_file(req: OfficeRequest, current_user: dict = Depends(get_current_user)):
    from ..config import SKILLS
    from ..office_agents import generate_pptx, generate_docx, generate_xlsx, parse_ai_to_slides, parse_ai_to_table
    if state.audit_log:
        state.audit_log.log("office_generate", f"{req.format}: {req.prompt[:60]}")
    state.track("office_gen", f"{req.format}: {req.title or req.prompt[:40]}")
    title = req.title or req.prompt[:60]
    mem = state.memory.build_context(req.project) if req.project and state.memory else ""
    if req.format == "pptx":
        research_system = AGENT_SYSTEMS["researcher"] + "\n\nResearch the given topic thoroughly. Provide:\n- Key facts, statistics, and data points\n- Historical context or background\n- Current trends and future outlook\n- Real-world examples and case studies\n- Expert opinions or industry insights" + (("\n\n" + mem) if mem else "")
        research = await call_ollama(req.model, [{"role": "user", "content": req.prompt}], research_system)
        slide_format = (
            "You are a presentation designer. Convert the research below into a polished slide deck.\n\n"
            "CRITICAL: Use EXACTLY this format — each slide starts with '## Slide N: Title' on its own line.\n\n"
            "## Slide 1: Introduction\nBrief hook and overview (2-3 sentences).\n\n"
            "## Slide 2: Background\n- Key point 1\n- Key point 2\n- Key point 3\n\n"
            "(Continue for 8-12 slides covering: overview, key facts, data/statistics, trends, examples, challenges, solutions, conclusion)\n\nResearch to convert:\n"
        )
        ai_output = await call_ollama(req.model, [{"role": "user", "content": slide_format + research}], "You are a professional presentation writer. Output ONLY slide content in the ## Slide N: Title format. No preamble.")
    elif req.format == "xlsx":
        system = AGENT_SYSTEMS["researcher"] + "\nOutput your response as a markdown table with | column | headers |."
        if mem:
            system += "\n\n" + mem
        ai_output = await call_ollama(req.model, [{"role": "user", "content": req.prompt}], system)
    else:
        system = AGENT_SYSTEMS["researcher"] + "\n\n" + SKILLS["documentation"] + "\nWrite a well-structured document with # for title, ## for sections."
        if mem:
            system += "\n\n" + mem
        ai_output = await call_ollama(req.model, [{"role": "user", "content": req.prompt}], system)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in title[:40])
    filename = f"{safe_name}_{ts}.{req.format}"
    out_path = state.WORKSPACE_DIR / filename
    if req.format == "pptx":
        slides = parse_ai_to_slides(ai_output, title)
        generate_pptx(title, slides, out_path)
    elif req.format == "xlsx":
        headers, rows = parse_ai_to_table(ai_output)
        generate_xlsx(title, rows, headers, out_path)
    else:
        generate_docx(title, ai_output, out_path)
    state.stats["files_created"] = state.stats.get("files_created", 0) + 1
    return {"filename": filename, "format": req.format, "title": title, "ai_output": ai_output, "timestamp": datetime.now().isoformat()}


@router.get("/api/office/download/{filename:path}")
async def download_office_file(filename: str, current_user: dict = Depends(get_current_user)):
    from pathlib import Path as _Path
    fp = (_Path(state.WORKSPACE_DIR) / filename).resolve()
    if not str(fp).startswith(str(_Path(state.WORKSPACE_DIR).resolve())):
        raise HTTPException(400, "Invalid path")
    if not fp.exists():
        raise HTTPException(404, "File not found")
    media_types = {
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return FileResponse(str(fp), media_type=media_types.get(fp.suffix, "application/octet-stream"), filename=fp.name)


# ── Prompts ───────────────────────────────────────────────────────────────────
_PROMPT_LIBRARY_FILE = None  # set below


@router.get("/api/prompts")
async def get_prompts(current_user: dict = Depends(get_current_user)):
    return {"prompts": _load_prompt_library()}


@router.post("/api/prompts")
async def save_prompt(body: dict, current_user: dict = Depends(get_current_user)):
    prompts = _load_prompt_library()
    new_p = {"id": f"pl_{datetime.now().timestamp():.0f}", "name": body.get("name", ""), "category": body.get("category", "general"), "prompt": body.get("prompt", "")}
    prompts.append(new_p)
    _save_prompt_library(prompts)
    if state.audit_log:
        state.audit_log.log("prompt_saved", new_p["name"])
    return new_p


@router.delete("/api/prompts/{prompt_id}")
async def delete_prompt(prompt_id: str, current_user: dict = Depends(get_current_user)):
    _save_prompt_library([p for p in _load_prompt_library() if p["id"] != prompt_id])
    return {"success": True}


def _load_prompt_library() -> list:
    defaults = [
        {"id": "pl_1", "name": "REST API", "category": "coder", "prompt": "Build a complete REST API with FastAPI. Include CRUD endpoints, input validation, error handling, and a README. Use SQLite for storage."},
        {"id": "pl_2", "name": "React Dashboard", "category": "coder", "prompt": "Build a React dashboard with Tailwind CSS. Include a sidebar, stat cards, a data table, and a line chart using recharts."},
        {"id": "pl_3", "name": "Docker Setup", "category": "devops", "prompt": "Create a complete Docker setup for a Python FastAPI app. Include Dockerfile (multi-stage), docker-compose.yml, .env.example, and deployment instructions."},
        {"id": "pl_4", "name": "System Architecture", "category": "architect", "prompt": "Design the full system architecture for a SaaS application with auth, billing, multi-tenancy, and a REST API. Include ASCII diagram and tech stack with reasoning."},
        {"id": "pl_5", "name": "Research Report", "category": "researcher", "prompt": "Research the current state of [TOPIC] in 2024. Include key players, recent developments, pros/cons of main approaches, and recommendations."},
    ]
    f = state.WORKSPACE_DIR / ".prompt_library.json"
    if not f.exists():
        f.write_text(json.dumps(defaults, indent=2))
        return defaults
    try:
        return json.loads(f.read_text())
    except Exception:
        return defaults


def _save_prompt_library(prompts: list):
    (state.WORKSPACE_DIR / ".prompt_library.json").write_text(json.dumps(prompts, indent=2))


# ── Telegram ──────────────────────────────────────────────────────────────────
@router.get("/api/telegram/status")
async def telegram_status(current_user: dict = Depends(get_current_user)):
    import os
    bot = getattr(state, 'telegram_bot', None)
    return {
        "enabled": bot.enabled if bot else False,
        "configured": bool(os.getenv("TELEGRAM_BOT_TOKEN", "")),
        "bot_token_set": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "chat_id_set": bool(os.getenv("TELEGRAM_CHAT_ID")),
    }


@router.post("/api/telegram/test")
async def telegram_test(body: dict, current_user: dict = Depends(get_current_user)):
    bot = getattr(state, 'telegram_bot', None)
    if not bot or not bot.enabled:
        return {"success": False, "error": "Bot not configured — set TELEGRAM_BOT_TOKEN"}
    bot.update_model(body.get("model", ""))
    return {"success": True, "message": "Bot is running. Send /start to your bot on Telegram."}


# ── PWA ───────────────────────────────────────────────────────────────────────
@router.get("/api/pwa/manifest")
async def pwa_manifest():
    return {
        "name": "KreativOS", "short_name": "KreativOS",
        "description": "Agentic AI Operating System",
        "start_url": "/", "display": "standalone",
        "background_color": "#0a0a0f", "theme_color": "#8b5cf6",
    }


# ── WebSocket ─────────────────────────────────────────────────────────────────
from fastapi import WebSocket as _WS, WebSocketDisconnect as _WSDisconnect


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: _WS, session_id: str, token: str = ""):
    token = websocket.query_params.get("token", "")
    if AUTH_REQUIRED and (not token or not state.auth or not state.auth.verify(token)):
        await websocket.close(code=4001)
        return
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            model = data.get("model", "")
            agent = data.get("agent", "general")
            msgs = data.get("messages", [])
            sys_p = build_full_system_prompt(
                AGENT_SYSTEMS.get(agent, AGENT_SYSTEMS["general"]),
                skills=get_skills_for_agent(agent),
            )
            await websocket.send_json({"type": "start", "agent": agent})
            async for chunk in stream_ollama(model, msgs, sys_p):
                if chunk:
                    await websocket.send_json({"type": "chunk", "content": chunk})
            await websocket.send_json({"type": "done"})
    except _WSDisconnect:
        pass


# ── Model Hub ─────────────────────────────────────────────────────────────────
from ..model_hub import router as _hub_router


@router.post("/api/hub/pull")
@limiter.limit("5/minute")
async def pull_model(request: Request, body: dict, current_user: dict = Depends(get_current_user)):
    import httpx as _httpx
    model_name = body.get("model_name", "")
    if not model_name:
        raise HTTPException(400, "model_name required")
    state.track("model_pull", model_name)

    async def generate():
        async with _httpx.AsyncClient(timeout=600) as client:
            async with client.stream("POST", f"{state.OLLAMA_BASE_URL}/api/pull", json={"name": model_name, "stream": True}) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            d = json.loads(line)
                            t = d.get("status", "")
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


@router.delete("/api/hub/delete/{model_name:path}")
async def delete_model(model_name: str, current_user: dict = Depends(get_current_user)):
    import httpx as _httpx
    async with _httpx.AsyncClient(timeout=30) as c:
        r = await c.delete(f"{state.OLLAMA_BASE_URL}/api/delete", json={"name": model_name})
        return {"success": r.status_code == 200}
