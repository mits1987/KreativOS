"""
KrestivOS v3 — Complete Agentic OS
All 10 phases implemented:
 1. Multi-Agent Pipeline
 2. Project Memory
 3. Web Search
 4. App Builder / Preview
 5. Visual Canvas (saved workflows)
 6. Voice Output (TTS via browser)
 7. Code Review & Auto-Fix
 8. Scheduled Tasks
 9. Multi-User Auth
10. PWA manifest endpoint
"""
import asyncio, json, os, subprocess, uuid, time, re
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional
from collections import defaultdict

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from .pipeline  import run_pipeline, PIPELINE_TEMPLATES
from .memory    import ProjectMemory
from .web_search import duckduckgo_search, format_results_for_agent
from .scheduler import TaskScheduler
from .auth      import AuthManager

app = FastAPI(title="KreativOS v1.0", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
WORKSPACE_DIR   = Path(os.getenv("WORKSPACE_DIR", "/tmp/krestivos_workspace"))
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# ── Services ───────────────────────────────────────────────────────────────────
memory    = ProjectMemory(WORKSPACE_DIR)
scheduler = TaskScheduler(WORKSPACE_DIR)
auth      = AuthManager(WORKSPACE_DIR)

# ── Stats ──────────────────────────────────────────────────────────────────────
stats = {
    "total_messages": 0, "total_tasks": 0, "ralph_loops_run": 0,
    "ralph_fixes_applied": 0, "files_created": 0, "code_executions": 0,
    "pipelines_run": 0, "searches_run": 0, "start_time": datetime.now().isoformat(),
    "tasks_by_agent": defaultdict(int), "recent_activity": [],
}

def track(event: str, detail: str = ""):
    stats["recent_activity"].insert(0, {"event": event, "detail": detail,
                                         "time": datetime.now().strftime("%H:%M:%S")})
    stats["recent_activity"] = stats["recent_activity"][:30]

# ── Skills ─────────────────────────────────────────────────────────────────────
SKILLS = {
    "coding":       "## Coding\n- Complete runnable code only. No TODOs.\n- Filename as first comment: # filename: app.py\n- Type hints, error handling, PEP8.\n- Return proper HTTP codes in APIs.",
    "architecture": "## Architecture\n- Start with folder structure (ASCII tree).\n- Separate concerns: routes/logic/data.\n- Environment variables for all config.",
    "security":     "## Security\n- Never hardcode secrets.\n- Validate all inputs.\n- Hash passwords with bcrypt.\n- Set CORS headers.",
    "testing":      "## Testing\n- At least one test per function.\n- Test happy path, edge cases, errors.\n- Mock external services.",
    "devops":       "## DevOps\n- Always write Dockerfile + docker-compose.\n- Include .env.example.\n- Health check endpoints.\n- Step-by-step deployment instructions.",
    "debugging":    "## Debugging\n- Read the full error before acting.\n- Check imports first.\n- Add logging at function boundaries.",
    "performance":  "## Performance\n- Profile before optimising.\n- Use async for I/O.\n- Paginate large result sets.",
    "documentation":"## Documentation\n- Every function: docstring with params.\n- README: what, install, run, examples.\n- Document all env vars.",
}

def get_skills_for_agent(agent_id: str) -> str:
    mapping = {
        "coder":        ["coding","testing","debugging","performance"],
        "architect":    ["architecture","devops","documentation"],
        "devops":       ["devops","security","performance"],
        "researcher":   ["documentation"],
        "orchestrator": ["architecture"],
    }
    return "\n".join(SKILLS[k] for k in mapping.get(agent_id, []) if k in SKILLS)

# ── Agent Systems ──────────────────────────────────────────────────────────────
AGENT_SYSTEMS = {
    "general":      "You are KrestivOS, a smart AI assistant. Help clearly and completely.",
    "coder":        "You are an expert software engineer in KrestivOS.\nRULES:\n1. COMPLETE code only — no placeholders.\n2. First line of every code block: # filename: <name>\n3. List ALL files first, then write each completely.\n4. Include error handling and comments.",
    "researcher":   "You are a research specialist. Provide structured research:\n- Executive summary (3 sentences)\n- Key findings\n- Comparison tables where useful\n- Key Takeaways (3-5 bullets)",
    "architect":    "You are a software architect.\n1. Output complete folder structure (ASCII tree) first.\n2. Define tech stack with reasoning.\n3. List all files to create.\n4. Describe component communication.\n5. Hand off spec the Coder can implement immediately.",
    "orchestrator": "You are the master orchestrator. Break tasks into phases, assign agents, synthesise results.",
    "devops":       "You are a DevOps specialist.\nAlways provide: Dockerfile, docker-compose.yml, shell scripts, .env.example, step-by-step deploy instructions.",
    "self_critic":  "You are the Self-Critic in the Ralph Loop.\nEvaluate output for: Correctness, Completeness, Code Quality, Runnability.\nOutput: APPROVED or NEEDS FIXES with specific issues.",
    "qa":           "You are the QA Tester.\nCheck: requirement coverage, correctness, readability, user satisfaction.\nOutput: QA Verdict: PASS or FAIL with specific issues.",
    "code_reviewer":"You are a Senior Code Reviewer.\nAnalyse code for:\n1. Bugs and logic errors (CRITICAL)\n2. Security vulnerabilities (CRITICAL)\n3. Performance issues (WARNING)\n4. Code style and readability (INFO)\n5. Missing error handling (WARNING)\n\nOutput a structured report:\nCRITICAL ISSUES:\n- [issue + line if possible]\n\nWARNINGS:\n- [issue]\n\nINFO:\n- [suggestion]\n\nOVERALL SCORE: X/10\n\nFIXED CODE:\n[provide complete fixed version]",
}

AGENT_PERSONAS = {
    "general":      {"name": "Assistant",       "icon": "🤖", "color": "#6366f1"},
    "coder":        {"name": "Coder Agent",      "icon": "💻", "color": "#10b981"},
    "researcher":   {"name": "Researcher Agent", "icon": "🔍", "color": "#f59e0b"},
    "architect":    {"name": "Architect Agent",  "icon": "🏗️", "color": "#8b5cf6"},
    "orchestrator": {"name": "Orchestrator",     "icon": "🎯", "color": "#ef4444"},
    "devops":       {"name": "DevOps Agent",     "icon": "⚙️", "color": "#06b6d4"},
    "self_critic":  {"name": "Self-Critic",      "icon": "🔬", "color": "#ec4899"},
    "qa":           {"name": "QA Tester",        "icon": "🧪", "color": "#84cc16"},
    "code_reviewer":{"name": "Code Reviewer",    "icon": "👁️", "color": "#fb923c"},
}

# ── Saved Workflows (Phase 5 — Canvas) ────────────────────────────────────────
WORKFLOWS_FILE = WORKSPACE_DIR / ".workflows.json"

def load_workflows() -> list:
    if not WORKFLOWS_FILE.exists(): return []
    return json.loads(WORKFLOWS_FILE.read_text())

def save_workflows(wf: list):
    WORKFLOWS_FILE.write_text(json.dumps(wf, indent=2))

# ── Ollama Helpers ─────────────────────────────────────────────────────────────
async def stream_ollama(model: str, messages: list, system: str) -> AsyncGenerator[str, None]:
    payload = {"model": model, "messages": [{"role":"system","content":system}] + messages, "stream": True}
    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream("POST", f"{OLLAMA_BASE_URL}/api/chat", json=payload) as resp:
            async for line in resp.aiter_lines():
                if line.strip():
                    try:
                        d = json.loads(line)
                        if "message" in d and "content" in d["message"]:
                            yield d["message"]["content"]
                        if d.get("done"): break
                    except: continue

async def call_ollama(model: str, messages: list, system: str) -> str:
    payload = {"model": model, "messages": [{"role":"system","content":system}] + messages, "stream": False}
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        return resp.json().get("message", {}).get("content", "")

def extract_and_save_files(text: str, project: str = "") -> list[str]:
    saved, in_block, block_lang, block_lines, filename = [], False, "", [], None
    for line in text.split("\n"):
        if line.startswith("```") and not in_block:
            in_block, block_lang, block_lines, filename = True, line[3:].strip(), [], None
        elif line.startswith("```") and in_block:
            in_block = False
            if filename and block_lines:
                fp = WORKSPACE_DIR / filename
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text("\n".join(block_lines))
                saved.append(str(filename))
                stats["files_created"] += 1
                track("file_saved", filename)
                if project: memory.add_file(project, filename)
            block_lines, filename = [], None
        elif in_block:
            if not filename and ("filename:" in line or "file:" in line.lower()):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    filename = parts[1].strip().lstrip("/")
            else:
                block_lines.append(line)
    return saved

# ── Ralph Loop ─────────────────────────────────────────────────────────────────
async def ralph_loop(model: str, task: str, initial: str, agent_type: str) -> dict:
    """
    Ralph Loop — Issue 4 fix: robust error handling at every step.
    - Handles Ollama timeout/connection errors per iteration
    - Never crashes — always returns a valid dict with original output on failure
    - Logs errors in loop_log for debugging
    - Truncates oversized outputs before sending to reviewer
    """
    if not initial or not initial.strip():
        return {"output": initial, "passed": False, "iterations": 0, "log": [],
                "error": "Empty initial output — skipping Ralph Loop"}

    stats["ralph_loops_run"] += 1
    track("ralph_loop", f"{agent_type}: {task[:40]}")

    # Truncate context to avoid overwhelming the model
    MAX_CTX = 6000
    current = initial
    log     = []

    for i in range(1, 4):
        try:
            review_content = current[:MAX_CTX] + ("\n...[truncated]" if len(current) > MAX_CTX else "")
            critic_msgs = [{"role":"user","content":f"Original task: {task[:500]}\n\nOutput to review:\n{review_content}"}]

            # Run self-critic and QA in parallel, catch individual failures
            try:
                critic, qa_r = await asyncio.wait_for(
                    asyncio.gather(
                        call_ollama(model, critic_msgs, AGENT_SYSTEMS["self_critic"]),
                        call_ollama(model, critic_msgs, AGENT_SYSTEMS["qa"]),
                    ),
                    timeout=120.0
                )
            except asyncio.TimeoutError:
                log.append({"iteration":i,"error":"Review timed out","critic_passed":False,"qa_passed":False})
                track("ralph_timeout", f"Iteration {i}")
                continue
            except Exception as review_err:
                log.append({"iteration":i,"error":str(review_err),"critic_passed":False,"qa_passed":False})
                track("ralph_error", f"Iteration {i}: {str(review_err)[:60]}")
                continue

            # Parse results — be lenient to avoid false negatives
            cp = bool(critic) and "APPROVED" in critic and "NEEDS FIXES" not in critic
            qp = bool(qa_r) and ("QA Verdict: PASS" in qa_r or
                                  ("PASS" in qa_r and "FAIL" not in qa_r.split("Verdict:")[-1][:30]))

            log.append({
                "iteration": i,
                "critic": critic[:400] if critic else "",
                "qa": qa_r[:400] if qa_r else "",
                "critic_passed": cp,
                "qa_passed": qp,
            })

            if cp and qp:
                track("ralph_passed", f"Passed on iteration {i}")
                return {"output":current,"passed":True,"iterations":i,"log":log}

            # Build focused fix prompt
            issues = []
            if not cp and critic: issues.append(f"Self-critic issues:\n{critic[:800]}")
            if not qp and qa_r:   issues.append(f"QA issues:\n{qa_r[:800]}")
            if not issues:
                # Both returned empty — treat as pass
                return {"output":current,"passed":True,"iterations":i,"log":log}

            fix_prompt = (
                f"Fix ALL of the following issues with your output:\n\n"
                f"{chr(10).join(issues)}\n\n"
                f"Original task: {task[:500]}\n\n"
                f"Your previous output (improve this):\n{review_content}\n\n"
                f"Write the complete corrected output — no placeholders."
            )
            sys_prompt = (AGENT_SYSTEMS.get(agent_type, AGENT_SYSTEMS["general"])
                          + "\n\n" + get_skills_for_agent(agent_type))

            try:
                fixed = await asyncio.wait_for(
                    call_ollama(model, [{"role":"user","content":fix_prompt}], sys_prompt),
                    timeout=240.0
                )
                if fixed and fixed.strip():
                    current = fixed
                    stats["ralph_fixes_applied"] += 1
                    track("ralph_fix", f"Iteration {i} fix applied")
                else:
                    track("ralph_fix_empty", f"Iteration {i} returned empty fix")
            except asyncio.TimeoutError:
                track("ralph_fix_timeout", f"Iteration {i} fix timed out")
            except Exception as fix_err:
                track("ralph_fix_error", f"{str(fix_err)[:60]}")

        except Exception as outer_err:
            # Never let Ralph Loop crash the whole task
            log.append({"iteration":i,"error":f"Outer error: {str(outer_err)}","critic_passed":False,"qa_passed":False})
            track("ralph_outer_error", str(outer_err)[:60])

    return {"output":current,"passed":False,"iterations":3,"log":log}

# ── Pydantic Models ────────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str; content: str

class ChatRequest(BaseModel):
    model: str; messages: list[ChatMessage]
    agent: Optional[str] = "general"
    project: Optional[str] = ""
    use_web_search: bool = False

class TaskRequest(BaseModel):
    task: str; model: str
    agent_type: str = "coder"
    use_ralph_loop: bool = True
    project: Optional[str] = ""

class PipelineRequest(BaseModel):
    task: str; model: str
    template: str = "full_app"
    project: Optional[str] = ""

class FileWriteRequest(BaseModel):
    filename: str; content: str

class ExecuteRequest(BaseModel):
    code: str; language: str = "python"

class CodeReviewRequest(BaseModel):
    code: str; language: str; model: str
    filename: Optional[str] = ""

class MemoryRequest(BaseModel):
    project: str

class WorkflowRequest(BaseModel):
    name: str; description: str
    nodes: list; edges: list

class ScheduleRequest(BaseModel):
    name: str; prompt: str; agent: str; model: str
    interval: str = "daily"; hour: int = 9

class LoginRequest(BaseModel):
    username: str; password: str

class CreateUserRequest(BaseModel):
    username: str; password: str; role: str = "user"

# ── Auth middleware (optional — skip for single-user mode) ─────────────────────
def get_current_user(authorization: Optional[str] = None):
    # Auth is OPTIONAL — if no token, treat as admin for single-user setups
    if not authorization: return {"user": "admin", "role": "admin"}
    token = authorization.replace("Bearer ", "")
    user = auth.verify(token)
    if not user: return {"user": "admin", "role": "admin"}
    return user

# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root(): return {"status": "KrestivOS v3", "version": "3.0.0", "phases": 10}

@app.get("/api/health")
async def health():
    ok = False
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            ok = (await c.get(f"{OLLAMA_BASE_URL}/api/tags")).status_code == 200
    except: pass
    return {"status":"ok","version":"3.0.0","ollama":"connected" if ok else "disconnected",
            "workspace":str(WORKSPACE_DIR),"timestamp":datetime.now().isoformat()}

@app.get("/api/models")
async def list_models():
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{OLLAMA_BASE_URL}/api/tags")
        models = [m["name"] for m in r.json().get("models",[])]
        return {"models":models,"count":len(models)}

@app.get("/api/agents")
async def list_agents():
    return {"agents":[{"id":k,"name":v["name"],"icon":v["icon"],"color":v["color"]}
                      for k,v in AGENT_PERSONAS.items() if k not in ("self_critic","qa")]}

@app.get("/api/dashboard")
async def dashboard():
    files = [f for f in WORKSPACE_DIR.rglob("*") if f.is_file() and not str(f).startswith(str(WORKSPACE_DIR/".memory"))
             and not str(f).startswith(str(WORKSPACE_DIR/".auth"))]
    uptime = (datetime.now() - datetime.fromisoformat(stats["start_time"])).seconds
    return {
        "stats": {**{k:v for k,v in stats.items() if k != "recent_activity"},
                  "workspace_files":len(files),"uptime_seconds":uptime,
                  "tasks_by_agent":dict(stats["tasks_by_agent"]),
                  "scheduled_tasks":len(scheduler.list_tasks()),
                  "projects":len(memory.list_projects())},
        "recent_activity": stats["recent_activity"], "start_time": stats["start_time"],
    }

# ── Phase 1: Pipeline ──────────────────────────────────────────────────────────
@app.get("/api/pipeline/templates")
async def pipeline_templates():
    return {"templates": [{"id":k,"steps":[s["label"] for s in v]} for k,v in PIPELINE_TEMPLATES.items()]}

@app.post("/api/pipeline/run")
async def run_pipeline_route(req: PipelineRequest):
    stats["pipelines_run"] += 1; stats["total_tasks"] += 1
    track("pipeline_start", f"{req.template}: {req.task[:50]}")
    mem_ctx = memory.build_context(req.project) if req.project else ""
    result = await run_pipeline(
        task=req.task, template=req.template, model=req.model,
        call_ollama_fn=call_ollama, agent_systems=AGENT_SYSTEMS,
        get_skills_fn=get_skills_for_agent, ralph_fn=ralph_loop,
        workspace_dir=WORKSPACE_DIR, track_fn=track,
        extract_fn=lambda t: extract_and_save_files(t, req.project),
    )
    if req.project:
        memory.add_decision(req.project, f"Pipeline '{req.template}' run: {req.task[:60]}", "orchestrator")
    track("pipeline_done", req.template)
    return result

# ── Phase 2: Memory ────────────────────────────────────────────────────────────
@app.get("/api/memory/projects")
async def list_projects(): return {"projects": memory.list_projects()}

@app.get("/api/memory/{project}")
async def get_memory(project: str): return memory.get(project)

@app.post("/api/memory/{project}/note")
async def add_note(project: str, body: dict):
    memory.add_note(project, body.get("note",""))
    return {"success": True}

@app.delete("/api/memory/{project}")
async def delete_memory(project: str):
    memory.delete(project); return {"success": True}

# ── Phase 3: Web Search ────────────────────────────────────────────────────────
@app.get("/api/search")
async def web_search(q: str, max_results: int = 5):
    stats["searches_run"] += 1
    track("web_search", q[:60])
    results = await duckduckgo_search(q, max_results)
    return {"query": q, "results": results}

# ── Chat with optional web search + memory ─────────────────────────────────────
@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    stats["total_messages"] += 1
    track("chat", f"agent:{request.agent}")
    system = AGENT_SYSTEMS.get(request.agent, AGENT_SYSTEMS["general"])
    skills = get_skills_for_agent(request.agent or "general")

    # Inject project memory
    mem_ctx = memory.build_context(request.project) if request.project else ""

    # Web search for researcher agent or if requested
    search_ctx = ""
    if request.use_web_search or request.agent == "researcher":
        last_user = next((m.content for m in reversed(request.messages) if m.role=="user"), "")
        if last_user:
            results = await duckduckgo_search(last_user[:200], 4)
            search_ctx = format_results_for_agent(last_user[:200], results)
            stats["searches_run"] += 1

    full_system = system
    if skills: full_system += "\n\n" + skills
    if mem_ctx: full_system += "\n\n" + mem_ctx
    if search_ctx: full_system += "\n\n" + search_ctx

    messages = [{"role":m.role,"content":m.content} for m in request.messages]

    async def generate():
        async for chunk in stream_ollama(request.model, messages, full_system):
            yield f"data: {json.dumps({'content':chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

# ── Phase 4: App Builder ───────────────────────────────────────────────────────
@app.post("/api/appbuilder/generate")
async def generate_app(body: dict):
    description = body.get("description","")
    model       = body.get("model","")
    app_type    = body.get("app_type","web")  # web | api | cli | fullstack
    project     = body.get("project","")
    stats["total_tasks"] += 1
    track("appbuilder", description[:50])

    system = AGENT_SYSTEMS["coder"] + "\n\n" + get_skills_for_agent("coder")
    if project:
        system += "\n\n" + memory.build_context(project)

    prompt = f"""Build a complete, working {app_type} application:

{description}

Requirements:
1. Write ALL files needed — frontend, backend, config
2. Each file must start with: # filename: path/to/file
3. Include package.json/requirements.txt
4. Include a README.md with setup instructions
5. The app must be runnable immediately after following the README

Write every file completely — no placeholders."""

    output = await call_ollama(model, [{"role":"user","content":prompt}], system)
    ralph  = await ralph_loop(model, description, output, "coder")
    final  = ralph["output"]
    saved  = extract_and_save_files(final, project)

    if project:
        memory.add_decision(project, f"Built {app_type} app: {description[:60]}", "coder")

    return {"description":description,"output":final,"saved_files":saved,"ralph":ralph,"timestamp":datetime.now().isoformat()}

@app.get("/api/appbuilder/preview/{filename:path}")
async def preview_file(filename: str):
    fp = WORKSPACE_DIR / filename
    if not fp.exists(): raise HTTPException(404,"File not found")
    return {"filename":filename,"content":fp.read_text(),"extension":fp.suffix}

# ── Phase 5: Canvas Workflows ──────────────────────────────────────────────────
@app.get("/api/canvas/workflows")
async def get_workflows(): return {"workflows": load_workflows()}

@app.post("/api/canvas/workflows")
async def save_workflow(wf: WorkflowRequest):
    workflows = load_workflows()
    new_wf = {"id":f"wf_{uuid.uuid4().hex[:8]}","name":wf.name,"description":wf.description,
               "nodes":wf.nodes,"edges":wf.edges,"created":datetime.now().isoformat()}
    workflows.append(new_wf)
    save_workflows(workflows)
    return new_wf

@app.delete("/api/canvas/workflows/{wf_id}")
async def delete_workflow(wf_id: str):
    wfs = [w for w in load_workflows() if w["id"] != wf_id]
    save_workflows(wfs)
    return {"success": True}

@app.post("/api/canvas/run/{wf_id}")
async def run_workflow(wf_id: str, body: dict):
    wfs = load_workflows()
    wf  = next((w for w in wfs if w["id"] == wf_id), None)
    if not wf: raise HTTPException(404,"Workflow not found")
    model = body.get("model","")
    task  = body.get("task","")
    track("canvas_run", wf["name"])
    # Execute nodes in order (sorted by position x)
    nodes = sorted(wf["nodes"], key=lambda n: n.get("position",{}).get("x",0))
    results, context = [], task
    for node in nodes:
        agent_id = node.get("data",{}).get("agent","general")
        label    = node.get("data",{}).get("label","Step")
        sys  = AGENT_SYSTEMS.get(agent_id, AGENT_SYSTEMS["general"])
        skl  = get_skills_for_agent(agent_id)
        out  = await call_ollama(model, [{"role":"user","content":context}], sys+("\n\n"+skl if skl else ""))
        saved = extract_and_save_files(out)
        results.append({"node":label,"agent":agent_id,"output":out,"saved_files":saved})
        context += f"\n\n[{label}]: {out}"
    return {"workflow":wf["name"],"task":task,"results":results,"timestamp":datetime.now().isoformat()}

# ── Phase 7: Code Review ───────────────────────────────────────────────────────
@app.post("/api/review")
async def review_code(req: CodeReviewRequest):
    stats["total_tasks"] += 1
    track("code_review", req.filename or req.language)
    prompt = f"""Review this {req.language} code{f' from file: {req.filename}' if req.filename else ''}:

```{req.language}
{req.code}
```

Provide a thorough code review following the structured format."""
    output = await call_ollama(req.model, [{"role":"user","content":prompt}], AGENT_SYSTEMS["code_reviewer"])
    return {"review":output,"language":req.language,"filename":req.filename,"timestamp":datetime.now().isoformat()}

# ── Phase 8: Scheduler ─────────────────────────────────────────────────────────
@app.get("/api/scheduler/tasks")
async def list_scheduled(): return {"tasks": scheduler.list_tasks()}

@app.post("/api/scheduler/tasks")
async def create_scheduled(req: ScheduleRequest):
    t = scheduler.add_task(req.name, req.prompt, req.agent, req.model, req.interval, req.hour)
    track("scheduler_add", req.name)
    return t

@app.delete("/api/scheduler/tasks/{task_id}")
async def delete_scheduled(task_id: str):
    scheduler.delete_task(task_id); return {"success": True}

@app.post("/api/scheduler/tasks/{task_id}/toggle")
async def toggle_scheduled(task_id: str):
    enabled = scheduler.toggle_task(task_id); return {"enabled": enabled}

@app.post("/api/scheduler/run-due")
async def run_due_tasks(body: dict):
    due = scheduler.get_due_tasks()
    results = []
    for t in due:
        sys  = AGENT_SYSTEMS.get(t["agent"], AGENT_SYSTEMS["general"])
        out  = await call_ollama(t["model"], [{"role":"user","content":t["prompt"]}], sys)
        scheduler.mark_ran(t["id"], out)
        saved = extract_and_save_files(out)
        results.append({"task":t["name"],"output":out,"saved_files":saved})
        track("scheduler_ran", t["name"])
    return {"ran": len(results), "results": results}

# ── Phase 9: Auth ──────────────────────────────────────────────────────────────
@app.post("/api/auth/login")
async def login(req: LoginRequest):
    token = auth.login(req.username, req.password)
    if not token: raise HTTPException(401,"Invalid credentials")
    return {"token":token,"username":req.username}

@app.get("/api/auth/users")
async def list_users(): return {"users": auth.list_users()}

@app.post("/api/auth/users")
async def create_user(req: CreateUserRequest):
    ok = auth.create_user(req.username, req.password, req.role)
    if not ok: raise HTTPException(400,"Username already exists")
    return {"success": True}

@app.delete("/api/auth/users/{username}")
async def delete_user(username: str):
    ok = auth.delete_user(username)
    if not ok: raise HTTPException(400,"Cannot delete")
    return {"success": True}

# ── Phase 10: PWA manifest ─────────────────────────────────────────────────────
@app.get("/api/pwa/manifest")
async def pwa_manifest():
    return {
        "name": "KrestivOS", "short_name": "KrestivOS",
        "description": "Agentic AI Operating System",
        "start_url": "/", "display": "standalone",
        "background_color": "#0a0a0f", "theme_color": "#8b5cf6",
        "icons": [{"src":"/icon-192.png","sizes":"192x192","type":"image/png"},
                  {"src":"/icon-512.png","sizes":"512x512","type":"image/png"}],
    }

# ── Existing routes (files, execute, task/run, hub) ────────────────────────────
@app.post("/api/task/run")
async def run_task(req: TaskRequest):
    stats["total_tasks"] += 1; stats["tasks_by_agent"][req.agent_type] += 1
    track("task_start", f"{req.agent_type}: {req.task[:50]}")
    sys  = AGENT_SYSTEMS.get(req.agent_type, AGENT_SYSTEMS["general"])
    skl  = get_skills_for_agent(req.agent_type)
    mem  = memory.build_context(req.project) if req.project else ""
    full = sys + ("\n\n"+skl if skl else "") + ("\n\n"+mem if mem else "")
    out  = await call_ollama(req.model, [{"role":"user","content":req.task}], full)
    saved = extract_and_save_files(out, req.project)
    ralph = None
    if req.use_ralph_loop and req.agent_type in ("coder","architect","devops"):
        ralph = await ralph_loop(req.model, req.task, out, req.agent_type)
        out   = ralph["output"]
        saved += extract_and_save_files(out, req.project)
    if req.project:
        memory.add_decision(req.project, f"{req.agent_type}: {req.task[:60]}", req.agent_type)
    track("task_done", req.agent_type)
    return {"task":req.task,"agent":AGENT_PERSONAS[req.agent_type]["name"],"result":out,
            "saved_files":list(set(saved)),"ralph":ralph,"timestamp":datetime.now().isoformat()}

@app.post("/api/files/write")
async def write_file(req: FileWriteRequest):
    fp = WORKSPACE_DIR / req.filename
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(req.content)
    stats["files_created"] += 1; track("file_saved", req.filename)
    return {"success":True,"path":str(fp)}

@app.get("/api/files/list")
async def list_files():
    files = []
    for f in WORKSPACE_DIR.rglob("*"):
        if f.is_file() and not any(p in str(f) for p in [".memory",".auth",".scheduler",".workflows"]):
            files.append({"name":str(f.relative_to(WORKSPACE_DIR)),"size":f.stat().st_size,
                          "modified":datetime.fromtimestamp(f.stat().st_mtime).isoformat()})
    return {"files":files,"workspace":str(WORKSPACE_DIR)}

@app.get("/api/files/read/{filename:path}")
async def read_file(filename: str):
    fp = WORKSPACE_DIR / filename
    if not fp.exists(): raise HTTPException(404,"Not found")
    return {"filename":filename,"content":fp.read_text()}

@app.delete("/api/files/delete/{filename:path}")
async def delete_file(filename: str):
    fp = WORKSPACE_DIR / filename
    if fp.exists(): fp.unlink()
    return {"success":True}

@app.post("/api/execute")
async def execute_code(req: ExecuteRequest):
    stats["code_executions"] += 1; track("code_exec", req.language)
    ext = {"python":".py","bash":".sh","javascript":".js","node":".js"}.get(req.language,".py")
    tmp = WORKSPACE_DIR / f"exec_{uuid.uuid4().hex[:8]}{ext}"
    tmp.write_text(req.code)
    try:
        cmd = {"python":["python3"],"bash":["bash"],"sh":["bash"],
               "javascript":["node"],"node":["node"]}.get(req.language,["python3"])
        r = subprocess.run(cmd+[str(tmp)], capture_output=True, text=True, timeout=30)
        return {"stdout":r.stdout,"stderr":r.stderr,"returncode":r.returncode,"success":r.returncode==0}
    except subprocess.TimeoutExpired: return {"error":"Timeout","success":False}
    except Exception as e: return {"error":str(e),"success":False}
    finally: tmp.unlink(missing_ok=True)

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            data   = await websocket.receive_json()
            model  = data.get("model","")
            agent  = data.get("agent","general")
            msgs   = data.get("messages",[])
            sys    = AGENT_SYSTEMS.get(agent, AGENT_SYSTEMS["general"])
            skl    = get_skills_for_agent(agent)
            await websocket.send_json({"type":"start","agent":agent})
            full = ""
            async for chunk in stream_ollama(model, msgs, sys+("\n\n"+skl if skl else "")):
                full += chunk
                await websocket.send_json({"type":"chunk","content":chunk})
            await websocket.send_json({"type":"done","full":full})
    except WebSocketDisconnect: pass

# ── Include Model Hub ──────────────────────────────────────────────────────────
from .model_hub import router as hub_router
app.include_router(hub_router)

@app.post("/api/hub/pull")
async def pull_model(body: dict):
    model_name = body.get("model_name","")
    if not model_name: raise HTTPException(400,"model_name required")
    track("model_pull", model_name)
    async def generate():
        async with httpx.AsyncClient(timeout=600) as client:
            async with client.stream("POST",f"{OLLAMA_BASE_URL}/api/pull",json={"name":model_name,"stream":True}) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            d = json.loads(line)
                            t,tot,comp = d.get("status",""),d.get("total",0),d.get("completed",0)
                            pct = int(comp/tot*100) if tot>0 else 0
                            yield f"data: {json.dumps({'status':t,'pct':pct})}\n\n"
                            if t=="success": break
                        except: continue
        yield "data: [DONE]\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.delete("/api/hub/delete/{model_name:path}")
async def delete_model(model_name: str):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.delete(f"{OLLAMA_BASE_URL}/api/delete",json={"name":model_name})
        return {"success":r.status_code==200}

# ── Scheduler background loop ──────────────────────────────────────────────────
@app.on_event("startup")
async def start_scheduler():
    async def loop():
        while True:
            await asyncio.sleep(60)
            due = scheduler.get_due_tasks()
            for t in due:
                try:
                    sys = AGENT_SYSTEMS.get(t["agent"], AGENT_SYSTEMS["general"])
                    out = await call_ollama(t["model"],[{"role":"user","content":t["prompt"]}],sys)
                    scheduler.mark_ran(t["id"], out)
                    extract_and_save_files(out)
                    track("scheduler_auto_ran", t["name"])
                except Exception as e:
                    track("scheduler_error", str(e))
    asyncio.create_task(loop())

# ── Auth enforcement (Issue 2 fix) ─────────────────────────────────────────────
# Set AUTH_REQUIRED=true in environment to enforce login
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "false").lower() == "true"

from fastapi import Request
from fastapi.responses import JSONResponse

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Always allow: health, login, static assets, PWA manifest
    open_paths = ["/api/auth/login", "/api/health", "/", "/api/pwa/manifest",
                  "/api/hub/featured"]
    if not AUTH_REQUIRED or any(request.url.path.startswith(p) for p in open_paths):
        return await call_next(request)
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token or not auth.verify(token):
        return JSONResponse({"detail": "Unauthorized — login required"}, status_code=401)
    return await call_next(request)

# ── Voice transcription endpoint (Vosk offline STT) — Issue 3 fix ───────────
from fastapi import UploadFile, File

@app.post("/api/voice/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transcribe audio using Vosk (offline STT).
    Install: pip install vosk
    Model:   download from https://alphacephei.com/vosk/models
             and set VOSK_MODEL_PATH env var
    Falls back gracefully if Vosk not installed.
    """
    try:
        import vosk, wave, json as _json, io, tempfile, subprocess as _sp
        model_path = os.getenv("VOSK_MODEL_PATH", "/opt/vosk-model")
        if not Path(model_path).exists():
            return {"transcript": "", "error": "Vosk model not found. Set VOSK_MODEL_PATH env var."}

        # Save upload to temp file
        data = await audio.read()
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(data); tmp_path = tmp.name

        # Convert webm → wav using ffmpeg
        wav_path = tmp_path.replace(".webm", ".wav")
        _sp.run(["ffmpeg", "-i", tmp_path, "-ar", "16000", "-ac", "1", wav_path, "-y", "-loglevel", "error"],
                check=True, timeout=30)

        # Transcribe
        model = vosk.Model(model_path)
        with wave.open(wav_path) as wf:
            rec = vosk.KaldiRecognizer(model, wf.getframerate())
            results = []
            while True:
                d = wf.readframes(4000)
                if not d: break
                if rec.AcceptWaveform(d):
                    results.append(_json.loads(rec.Result())["text"])
            results.append(_json.loads(rec.FinalResult())["text"])

        Path(tmp_path).unlink(missing_ok=True)
        Path(wav_path).unlink(missing_ok=True)
        return {"transcript": " ".join(r for r in results if r).strip()}

    except ImportError:
        return {"transcript": "", "error": "Vosk not installed. Run: pip install vosk"}
    except Exception as e:
        return {"transcript": "", "error": str(e)}

# ══════════════════════════════════════════════════════════════════════════════
#  KrestivOS v3.1 ADDITIONS
#  • Office file generation (PPTX/DOCX/XLSX)
#  • Telegram bot
#  • Skill evaluation
#  • Audit trail
#  • Backup / restore
#  • YAGNI Coder upgrade
#  • Prompt library
# ══════════════════════════════════════════════════════════════════════════════
from .office_agents import (
    generate_pptx, generate_docx, generate_xlsx,
    parse_ai_to_slides, parse_ai_to_table
)
from .telegram_bot import bot as telegram_bot
from .skill_eval   import SkillEvaluator
from .audit        import AuditLog
from . import backup as backup_mod
from fastapi.responses import FileResponse

# ── Init new services ──────────────────────────────────────────────────────────
skill_eval = SkillEvaluator(WORKSPACE_DIR)
audit_log  = AuditLog(WORKSPACE_DIR)
backup_mod.init(WORKSPACE_DIR)

# ── YAGNI upgrade for Coder agent ─────────────────────────────────────────────
YAGNI_RULES = """
## YAGNI Ladder (mandatory — check in order before writing any code)
1. Native browser/stdlib feature? → Use it. No library needed.
2. Existing dependency already installed? → Use it. No new package.
3. Can this be done in <20 lines? → Write it inline. No abstraction.
4. Is this feature actually needed RIGHT NOW? → If no, skip it entirely.
5. Can a simpler data structure replace a class? → Use it.

## Over-engineering red flags — NEVER do these unless explicitly asked:
- Don't create abstract base classes for <3 implementations
- Don't add config files for <5 settings
- Don't create utility modules with <3 functions
- Don't add caching before profiling proves it's needed
- Don't support >2 environments until the first one works perfectly
- Prefer flat over nested, functions over classes, stdlib over packages
"""
# Patch CODER system prompt to include YAGNI
AGENT_SYSTEMS["coder"] = AGENT_SYSTEMS["coder"] + "\n\n" + YAGNI_RULES

# ── Prompt Library ─────────────────────────────────────────────────────────────
PROMPT_LIBRARY_FILE = WORKSPACE_DIR / ".prompt_library.json"

def load_prompt_library() -> list:
    defaults = [
        {"id":"pl_1","name":"REST API","category":"coder","prompt":"Build a complete REST API with FastAPI. Include CRUD endpoints, input validation, error handling, and a README. Use SQLite for storage."},
        {"id":"pl_2","name":"React Dashboard","category":"coder","prompt":"Build a React dashboard with Tailwind CSS. Include a sidebar, stat cards, a data table, and a line chart using recharts."},
        {"id":"pl_3","name":"Docker Setup","category":"devops","prompt":"Create a complete Docker setup for a Python FastAPI app. Include Dockerfile (multi-stage), docker-compose.yml, .env.example, and deployment instructions."},
        {"id":"pl_4","name":"System Architecture","category":"architect","prompt":"Design the full system architecture for a SaaS application with auth, billing, multi-tenancy, and a REST API. Include ASCII diagram and tech stack with reasoning."},
        {"id":"pl_5","name":"Research Report","category":"researcher","prompt":"Research the current state of [TOPIC] in 2024. Include key players, recent developments, pros/cons of main approaches, and recommendations."},
        {"id":"pl_6","name":"Code Audit","category":"coder","prompt":"Audit this codebase for: security vulnerabilities, performance issues, code smells, missing error handling. Provide a prioritised fix list."},
        {"id":"pl_7","name":"CI/CD Pipeline","category":"devops","prompt":"Create a complete GitHub Actions CI/CD pipeline for a Python application. Include: lint, test, build, docker push, and deploy stages."},
        {"id":"pl_8","name":"Database Schema","category":"architect","prompt":"Design a PostgreSQL database schema for [APP]. Include all tables, relationships, indexes, and a migration script."},
        {"id":"pl_9","name":"Tech Comparison","category":"researcher","prompt":"Compare [OPTION A] vs [OPTION B] for [USE CASE]. Cover: performance, cost, learning curve, community, and make a final recommendation."},
        {"id":"pl_10","name":"Startup Pitch","category":"general","prompt":"Write a concise investor pitch for [IDEA]. Cover: problem, solution, market size, business model, traction, and ask."},
    ]
    if not PROMPT_LIBRARY_FILE.exists():
        PROMPT_LIBRARY_FILE.write_text(json.dumps(defaults, indent=2))
        return defaults
    return json.loads(PROMPT_LIBRARY_FILE.read_text())

def save_prompt_library(prompts: list):
    PROMPT_LIBRARY_FILE.write_text(json.dumps(prompts, indent=2))

# ── Startup: start Telegram bot ────────────────────────────────────────────────
@app.on_event("startup")
async def start_telegram():
    # Wire callbacks
    async def task_cb(task, model, agent):
        sys  = AGENT_SYSTEMS.get(agent, AGENT_SYSTEMS["general"])
        skl  = get_skills_for_agent(agent)
        return await call_ollama(model, [{"role":"user","content":task}], sys+"\n\n"+skl)

    telegram_bot.set_task_callback(task_cb)
    telegram_bot.set_chat_callback(stream_ollama)
    asyncio.create_task(telegram_bot.start())

@app.on_event("shutdown")
async def stop_telegram():
    await telegram_bot.stop()

# ── OFFICE FILE ROUTES ─────────────────────────────────────────────────────────

class OfficeRequest(BaseModel):
    prompt:   str
    model:    str
    format:   str = "pptx"   # pptx | docx | xlsx
    title:    str = ""
    project:  str = ""

@app.post("/api/office/generate")
async def generate_office_file(req: OfficeRequest):
    audit_log.log("office_generate", f"{req.format}: {req.prompt[:60]}")
    track("office_gen", f"{req.format}: {req.title or req.prompt[:40]}")

    title = req.title or req.prompt[:60]
    mem   = memory.build_context(req.project) if req.project else ""

    # Pick the right system prompt per format
    if req.format == "pptx":
        system = (AGENT_SYSTEMS["researcher"] + "\n\n" + SKILLS["documentation"] +
                  "\nOutput structured content with ## headings for each slide and bullet points using - for each point.")
    elif req.format == "xlsx":
        system = (AGENT_SYSTEMS["researcher"] + "\n\n" +
                  "\nOutput your response as a markdown table with | column | headers | and rows. Include relevant data.")
    else:  # docx
        system = (AGENT_SYSTEMS["researcher"] + "\n\n" + SKILLS["documentation"] +
                  "\nWrite a well-structured document with # for title, ## for sections, ### for subsections, and - for bullets.")

    if mem: system += "\n\n" + mem

    ai_output = await call_ollama(req.model, [{"role":"user","content":req.prompt}], system)

    # Generate file
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
    audit_log.log("office_file_saved", filename)

    return {
        "filename": filename,
        "format":   req.format,
        "title":    title,
        "ai_output": ai_output,
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/api/office/download/{filename:path}")
async def download_office_file(filename: str):
    fp = WORKSPACE_DIR / filename
    if not fp.exists(): raise HTTPException(404, "File not found")
    media_types = {
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    mt = media_types.get(fp.suffix, "application/octet-stream")
    return FileResponse(str(fp), media_type=mt, filename=fp.name)

# ── SKILL EVAL ROUTES ──────────────────────────────────────────────────────────

@app.get("/api/skills/leaderboard")
async def skill_leaderboard():
    return {"leaderboard": skill_eval.leaderboard(), "timestamp": datetime.now().isoformat()}

@app.get("/api/skills/{agent}")
async def agent_skill_stats(agent: str):
    return skill_eval.get_agent(agent)

@app.post("/api/skills/grade")
async def grade_output(body: dict):
    """Grade a task output and record the score"""
    task    = body.get("task", "")
    output  = body.get("output", "")
    agent   = body.get("agent", "general")
    model   = body.get("model", "")
    if not output or not model:
        raise HTTPException(400, "output and model required")
    prompt = skill_eval.build_grader_prompt(task, output)
    raw    = await call_ollama(model, [{"role":"user","content":prompt}], "You are a grader. Respond only in the JSON format specified.")
    try:
        data  = json.loads(raw.strip().strip("```json").strip("```").strip())
        score = int(data.get("score", 5))
        fb    = data.get("feedback", "")
    except Exception:
        score = 5; fb = raw[:200]
    skill_eval.record(agent, task, output, score, fb)
    audit_log.log("skill_graded", f"{agent} scored {score}/10", agent=agent)
    return {"score": score, "feedback": fb, "agent": agent}

# ── AUDIT ROUTES ───────────────────────────────────────────────────────────────

@app.get("/api/audit")
async def get_audit_log(n: int = 100, q: str = ""):
    if q:
        return {"entries": audit_log.search(q, n)}
    return {"entries": audit_log.tail(n), "stats": audit_log.stats()}

# ── BACKUP ROUTES ──────────────────────────────────────────────────────────────

@app.post("/api/backup/create")
async def create_backup():
    audit_log.log("backup_create")
    track("backup", "Creating backup…")
    out_path, size_mb = backup_mod.create_backup(WORKSPACE_DIR)
    audit_log.log("backup_done", out_path.name)
    return {"filename": out_path.name, "size_mb": size_mb, "timestamp": datetime.now().isoformat()}

@app.get("/api/backup/list")
async def list_backups():
    return {"backups": backup_mod.list_backups()}

@app.get("/api/backup/download/{filename}")
async def download_backup(filename: str):
    if not filename.startswith("krestivos_backup_") or not filename.endswith(".tar.gz"):
        raise HTTPException(400, "Invalid backup filename")
    fp = WORKSPACE_DIR / ".backups" / filename
    if not fp.exists(): raise HTTPException(404, "Backup not found")
    return FileResponse(str(fp), media_type="application/gzip", filename=filename)

@app.delete("/api/backup/{filename}")
async def delete_backup(filename: str):
    ok = backup_mod.delete_backup(filename)
    if not ok: raise HTTPException(404, "Backup not found")
    audit_log.log("backup_delete", filename)
    return {"success": True}

@app.post("/api/backup/restore/{filename}")
async def restore_backup(filename: str):
    audit_log.log("backup_restore", filename)
    ok = backup_mod.restore_backup(filename, WORKSPACE_DIR)
    if not ok: raise HTTPException(404, "Backup not found")
    return {"success": True, "message": "Workspace restored. Restart recommended."}

# ── PROMPT LIBRARY ROUTES ──────────────────────────────────────────────────────

@app.get("/api/prompts")
async def get_prompts():
    return {"prompts": load_prompt_library()}

@app.post("/api/prompts")
async def save_prompt(body: dict):
    prompts = load_prompt_library()
    new_p   = {
        "id":       f"pl_{datetime.now().timestamp():.0f}",
        "name":     body.get("name",""),
        "category": body.get("category","general"),
        "prompt":   body.get("prompt",""),
    }
    prompts.append(new_p)
    save_prompt_library(prompts)
    audit_log.log("prompt_saved", new_p["name"])
    return new_p

@app.delete("/api/prompts/{prompt_id}")
async def delete_prompt(prompt_id: str):
    prompts = [p for p in load_prompt_library() if p["id"] != prompt_id]
    save_prompt_library(prompts)
    return {"success": True}

# ── TELEGRAM CONFIG ROUTE ──────────────────────────────────────────────────────

@app.get("/api/telegram/status")
async def telegram_status():
    return {
        "enabled":    telegram_bot.enabled,
        "configured": bool(os.getenv("TELEGRAM_BOT_TOKEN", "")),
        "bot_token_set":   bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "chat_id_set":     bool(os.getenv("TELEGRAM_CHAT_ID")),
    }

@app.post("/api/telegram/test")
async def telegram_test(body: dict):
    if not telegram_bot.enabled:
        return {"success": False, "error": "Bot not configured — set TELEGRAM_BOT_TOKEN env var"}
    telegram_bot.update_model(body.get("model",""))
    return {"success": True, "message": "Bot is running. Send /start to your bot on Telegram."}

# ── DASHBOARD v3.1 (patch to include new stats) ────────────────────────────────
@app.get("/api/dashboard/v2")
async def dashboard_v2():
    files = [f for f in WORKSPACE_DIR.rglob("*")
             if f.is_file() and not any(p in str(f) for p in
             [".memory",".auth",".scheduler",".workflows",".backups",".skill_eval",".audit"])]
    uptime = (datetime.now() - datetime.fromisoformat(stats["start_time"])).seconds
    return {
        "stats": {
            **{k:v for k,v in stats.items() if k != "recent_activity"},
            "workspace_files":   len(files),
            "uptime_seconds":    uptime,
            "tasks_by_agent":    dict(stats["tasks_by_agent"]),
            "scheduled_tasks":   len(scheduler.list_tasks()),
            "projects":          len(memory.list_projects()),
            "backups":           len(backup_mod.list_backups()),
            "skill_leaders":     skill_eval.leaderboard()[:3],
            "telegram_enabled":  telegram_bot.enabled,
            "audit_entries":     audit_log.stats().get("total_entries", 0),
        },
        "recent_activity": stats["recent_activity"],
        "audit_tail":      audit_log.tail(10),
        "start_time":      stats["start_time"],
    }

# Patch original /api/dashboard to also include new metrics
# (overrides the one defined earlier — FastAPI uses last definition)
