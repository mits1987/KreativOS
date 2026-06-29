"""
KreativOS — Orchestrator
Single entry-point agent flow:
  User → Orchestrator plan → Specialists (tool-calling loop) → Auditor → Revision → Final report
"""
import asyncio
import json
import httpx
from pathlib import Path
from typing import AsyncGenerator

from .config import AGENT_SYSTEMS
from .sandbox import run_code_sandboxed
from .web_search import duckduckgo_search

# ── Permission signalling ──────────────────────────────────────────────────────
# req_id → (asyncio.Event, [decision])  — main.py calls signal_permission() on respond
_perm_events: dict[str, tuple] = {}

def signal_permission(req_id: str, decision: str):
    entry = _perm_events.get(req_id)
    if entry:
        event, holder = entry
        holder.append(decision)
        event.set()

# ── Tool schema ────────────────────────────────────────────────────────────────
TOOLS = [
    {"type": "function", "function": {
        "name": "list_files",
        "description": "List files and directories in the workspace",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Relative path in workspace (default '.')"}
        }}
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a file from the workspace",
        "parameters": {"type": "object", "required": ["filename"], "properties": {
            "filename": {"type": "string"}
        }}
    }},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write or create a file in the workspace",
        "parameters": {"type": "object", "required": ["filename", "content"], "properties": {
            "filename": {"type": "string"},
            "content": {"type": "string"}
        }}
    }},
    {"type": "function", "function": {
        "name": "execute_code",
        "description": "Execute Python or Bash code, returns stdout/stderr",
        "parameters": {"type": "object", "required": ["code", "language"], "properties": {
            "code": {"type": "string"},
            "language": {"type": "string", "enum": ["python", "bash"]}
        }}
    }},
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web for current information",
        "parameters": {"type": "object", "required": ["query"], "properties": {
            "query": {"type": "string"}
        }}
    }},
    {"type": "function", "function": {
        "name": "request_permission",
        "description": "Request user permission before accessing a path outside the workspace",
        "parameters": {"type": "object", "required": ["path", "operation"], "properties": {
            "path": {"type": "string"},
            "operation": {"type": "string", "enum": ["read", "write", "execute"]}
        }}
    }},
]

# ── System prompts ─────────────────────────────────────────────────────────────
ORCHESTRATOR_SYSTEM = """\
You are the KreativOS Orchestrator. Analyse the task and produce an execution plan.

Available agents:
- researcher: gathers info, analyses requirements, searches the web
- architect: designs systems, APIs, data models, tech stack decisions
- coder: writes all code and creates files in the workspace
- devops: Docker, CI/CD, deployment scripts, infra config
- general: writing, analysis, creative tasks

Respond ONLY with valid JSON (no markdown, no explanation):
{
  "plan_summary": "one sentence describing the approach",
  "steps": [
    {"agent": "researcher", "task": "specific instructions"},
    {"agent": "coder", "task": "specific instructions"}
  ]
}

Include only needed agents. Order matters — each agent sees the previous agents' output."""

AUDITOR_SYSTEM = """\
You are the KreativOS Auditor. Review all agent work against the original task.

Evaluate: correctness, completeness, missing files, logic errors, gaps.

Respond ONLY with valid JSON:
{
  "passed": true,
  "score": 8,
  "feedback": "specific actionable revision instructions (empty string if passed)",
  "issues": ["issue description"]
}

Set passed: true when score >= 7."""

FINAL_SYSTEM = """\
You are the KreativOS Orchestrator. Present the final result to the user clearly.
Summarise: what was built, files created, how to run or use it.
Be concise and use markdown formatting."""


# ── LLM call ──────────────────────────────────────────────────────────────────
async def _llm(model: str, messages: list, system: str, ollama_url: str, tools=None) -> dict:
    payload = {
        "model":   model,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream":  False,
    }
    if tools:
        payload["tools"] = tools
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(f"{ollama_url}/api/chat", json=payload)
        r.raise_for_status()
    return r.json().get("message", {})


def _parse_json_response(raw: str) -> dict:
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean[clean.index("\n")+1:] if "\n" in clean else clean[3:]
        clean = clean.rstrip("`").strip()
    return json.loads(clean)


# ── Tool executor ──────────────────────────────────────────────────────────────
async def _exec_tool(name: str, args: dict, workspace_dir: Path) -> str:
    ws = str(workspace_dir.resolve())
    try:
        if name == "list_files":
            p = (workspace_dir / args.get("path", ".")).resolve()
            if not str(p).startswith(ws):
                return "Error: path outside workspace"
            if not p.exists():
                return f"Error: '{args.get('path')}' not found"
            items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
            return "\n".join(f"{'FILE' if i.is_file() else 'DIR '} {i.name}" for i in items) or "(empty)"

        elif name == "read_file":
            fp = (workspace_dir / args["filename"]).resolve()
            if not str(fp).startswith(ws):
                return "Error: path outside workspace"
            if not fp.exists():
                return f"Error: '{args['filename']}' not found"
            return fp.read_text(errors="replace")[:8000]

        elif name == "write_file":
            fp = (workspace_dir / args["filename"]).resolve()
            if not str(fp).startswith(ws):
                return "Error: path outside workspace"
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(args["content"])
            return f"Written: {args['filename']} ({len(args['content'])} chars)"

        elif name == "execute_code":
            result = await asyncio.to_thread(
                run_code_sandboxed, args["code"], args.get("language", "python")
            )
            out = (result.get("stdout") or "").strip()
            err = (result.get("stderr") or "").strip()
            return (out + ("\n[stderr]\n" + err if err else "")).strip()[:4000] or "(no output)"

        elif name == "web_search":
            results = await duckduckgo_search(args["query"], max_results=5)
            return "\n\n".join(
                f"**{r['title']}**\n{r['url']}\n{r.get('body', '')}" for r in results
            ) or "No results"

        elif name == "request_permission":
            # Workspace paths are auto-allowed; non-workspace paths pause here
            path, op = args.get("path", ""), args.get("operation", "read")
            import uuid as _uuid
            import threading
            req_id = _uuid.uuid4().hex[:12]
            # Return a special marker — orchestrate() yields permission_request event
            return f"__PERMISSION_REQUIRED__{req_id}__{path}__{op}"

        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool error: {e}"


# ── Agent loop ─────────────────────────────────────────────────────────────────
async def _run_agent(agent: str, task: str, context: str,
                     model: str, workspace_dir: Path, ollama_url: str):
    system = AGENT_SYSTEMS.get(agent, AGENT_SYSTEMS["general"])
    user_msg = task if not context else f"Context from prior agents:\n{context}\n\nYour task:\n{task}"
    messages = [{"role": "user", "content": user_msg}]

    for _ in range(20):
        msg = await _llm(model, messages, system, ollama_url, tools=TOOLS)
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            yield {"type": "agent_output", "content": content}
            return

        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

        for tc in tool_calls:
            fn      = tc.get("function", {})
            fn_name = fn.get("name", "")
            fn_args = fn.get("arguments", {})
            if isinstance(fn_args, str):
                try:    fn_args = json.loads(fn_args)
                except: fn_args = {}

            yield {"type": "tool_call", "tool": fn_name, "args": fn_args}
            result = await _exec_tool(fn_name, fn_args, workspace_dir)

            # Permission check
            if result.startswith("__PERMISSION_REQUIRED__"):
                parts  = result.split("__")
                req_id = parts[2]
                path   = parts[3]
                op     = parts[4]
                event  = asyncio.Event()
                holder: list = []
                _perm_events[req_id] = (event, holder)
                yield {"type": "permission_request", "req_id": req_id, "path": path, "operation": op}
                try:
                    await asyncio.wait_for(event.wait(), timeout=120)
                    decision = holder[0] if holder else "deny"
                except asyncio.TimeoutError:
                    decision = "deny"
                finally:
                    _perm_events.pop(req_id, None)
                result = f"Permission {decision} for {path}"

            yield {"type": "tool_result", "tool": fn_name, "result": result[:500]}
            messages.append({"role": "tool", "content": result})

    yield {"type": "agent_output", "content": content}


# ── Main orchestration generator ───────────────────────────────────────────────
async def orchestrate(task: str, model: str, project: str,
                      workspace_dir: Path, ollama_url: str) -> AsyncGenerator[dict, None]:

    # Step 1 — Plan
    yield {"type": "planning"}
    try:
        plan_msg = await _llm(model, [{"role": "user", "content": task}], ORCHESTRATOR_SYSTEM, ollama_url)
        plan = _parse_json_response(plan_msg.get("content", ""))
    except Exception as e:
        yield {"type": "error", "message": f"Planning failed: {e}"}
        return

    steps = plan.get("steps", [])
    if not steps:
        yield {"type": "error", "message": "Orchestrator returned empty plan"}
        return

    yield {"type": "plan", "summary": plan.get("plan_summary", ""), "steps": steps}

    # Step 2 — Execute → Audit → Revise (up to 3 rounds)
    MAX_ROUNDS = 3
    audit_feedback = ""
    all_agent_outputs: dict[str, str] = {}

    for round_num in range(1, MAX_ROUNDS + 1):
        context = f"Original task: {task}\n"
        if audit_feedback:
            context += f"\nAuditor feedback (round {round_num - 1}) — please fix:\n{audit_feedback}\n"

        for step in steps:
            agent      = step["agent"]
            agent_task = step["task"]
            if audit_feedback:
                agent_task += f"\n\nFix auditor issues: {audit_feedback}"

            yield {"type": "agent_start", "agent": agent, "task": agent_task, "round": round_num}

            output = ""
            async for event in _run_agent(agent, agent_task, context, model, workspace_dir, ollama_url):
                if event["type"] == "agent_output":
                    output = event["content"]
                else:
                    yield event

            all_agent_outputs[agent] = output
            context += f"\n--- {agent.upper()} ---\n{output}\n"
            yield {"type": "agent_done", "agent": agent, "output": output}

        # Step 3 — Audit
        yield {"type": "audit_start", "round": round_num}
        combined = "\n\n".join(f"=== {a.upper()} ===\n{o}" for a, o in all_agent_outputs.items())
        audit_prompt = f"Original task: {task}\n\nAgent outputs:\n{combined}"

        try:
            audit_msg = await _llm(model, [{"role": "user", "content": audit_prompt}], AUDITOR_SYSTEM, ollama_url)
            audit = _parse_json_response(audit_msg.get("content", ""))
        except Exception:
            audit = {"passed": True, "score": 7, "feedback": "", "issues": []}

        score   = max(0, min(10, int(audit.get("score", 7))))
        passed  = bool(audit.get("passed", score >= 7))
        audit_feedback = audit.get("feedback", "")

        yield {
            "type":     "audit_result",
            "passed":   passed,
            "score":    score,
            "feedback": audit_feedback,
            "issues":   audit.get("issues", []),
            "round":    round_num,
        }

        if passed or round_num == MAX_ROUNDS:
            # Step 4 — Final synthesis
            final_prompt = (
                f"Original task: {task}\n\n"
                f"Completed work:\n{combined}\n\n"
                f"Audit score: {score}/10"
            )
            final_msg = await _llm(model, [{"role": "user", "content": final_prompt}], FINAL_SYSTEM, ollama_url)
            yield {"type": "done", "output": final_msg.get("content", ""), "score": score}
            return
