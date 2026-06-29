"""
KreativOS — Orchestrator v3
- Parallel agent execution (asyncio.Queue fan-out)
- Dynamic agent creation (orchestrator emits system_prompt in plan step)
- Per-agent self-scoring
- ReAct tool loop (works with any Ollama model)
"""
import asyncio
import json
import re
import httpx
from pathlib import Path
from typing import AsyncGenerator

from .config import AGENT_SYSTEMS
from . import permissions as perms
from .sandbox import run_code_sandboxed
from .web_search import duckduckgo_search

# ── Permission signalling ──────────────────────────────────────────────────────
_perm_events: dict[str, tuple] = {}

def signal_permission(req_id: str, decision: str):
    entry = _perm_events.get(req_id)
    if entry:
        event, holder = entry
        holder.append(decision)
        event.set()

# ── In-session custom agents created by the orchestrator ──────────────────────
_custom_agents: dict[str, str] = {}

TOOL_INSTRUCTIONS = """
## Tools — use this EXACT format (two consecutive lines):
TOOL: tool_name
ARGS: {"key": "value"}

Available tools:
- list_files   {"path": "."} — list directory (relative to workspace OR absolute path)
- read_file    {"filename": "path"} — read file (relative or absolute)
- write_file   {"filename": "relative/path", "content": "text"} — write to workspace
- execute_code {"code": "...", "language": "python"} — run code, get stdout/stderr
- web_search   {"query": "..."} — search the web
- request_permission {"path": "/absolute/path", "operation": "read"} — ask user before accessing paths outside workspace

Rules:
- For paths OUTSIDE the workspace, always call request_permission first.
- You may chain tools — one per response turn.
- When all tool work is done, write your final answer with NO TOOL: line.
- Do NOT invent file contents — always use read_file to get real data.
"""

ORCHESTRATOR_SYSTEM = """\
You are the KreativOS Orchestrator. Analyse the task and produce a parallel execution plan.

Existing agents: researcher, architect, coder, devops, general
- researcher: web search, information gathering
- architect: system design, tech stack, folder structure
- coder: write code, create files, execute code
- devops: Docker, CI/CD, deployment
- general: time queries, file exploration, writing, anything else

If a task requires a specialist that does not exist (e.g. seo_expert, data_scientist, security_auditor),
CREATE one by including "system_prompt" in that step.

ALL steps run IN PARALLEL — design them to be independent.
Each agent receives the original task description.

Respond ONLY with valid JSON (no markdown, no explanation):
{
  "plan_summary": "one sentence",
  "steps": [
    {"agent": "researcher", "task": "specific instructions"},
    {"agent": "coder", "task": "specific instructions"},
    {"agent": "seo_expert", "task": "...", "system_prompt": "You are an SEO specialist. Analyse websites for..."}
  ]
}"""

AUDITOR_SYSTEM = """\
You are the KreativOS Auditor. Review ALL agent outputs against the original task.
Respond ONLY with valid JSON:
{
  "passed": true,
  "score": 8,
  "feedback": "revision instructions if score < 7, else empty string",
  "issues": []
}
passed = true when score >= 7."""

SELF_SCORE_SYSTEM = """\
Rate the quality of your own output for the given task.
Respond ONLY with JSON: {"score": 7, "notes": "brief self-assessment"}
Be honest. Score 1-10."""

FINAL_SYSTEM = """\
You are the KreativOS Orchestrator. Present the final result to the user.
Summarise what was done, list files created, explain how to use/run them.
Be concise. Use markdown."""

TOOL_RE = re.compile(r'TOOL:\s*(\w+)\s*\nARGS:\s*(\{[^}]*\}|\{[\s\S]*?\})', re.MULTILINE)


def _parse_json(raw: str) -> dict:
    clean = raw.strip()
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', clean)
    if m:
        clean = m.group(1).strip()
    if not clean.startswith('{'):
        m = re.search(r'\{[\s\S]*\}', clean)
        if m:
            clean = m.group(0)
    return json.loads(clean)


def _resolve(raw: str, workspace_dir: Path) -> tuple[Path, bool]:
    p = Path(raw)
    resolved = p.resolve() if p.is_absolute() else (workspace_dir / raw).resolve()
    in_ws = str(resolved).startswith(str(workspace_dir.resolve()))
    return resolved, in_ws


async def _llm(model: str, messages: list, system: str, ollama_url: str) -> str:
    payload = {
        "model":    model,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream":   False,
    }
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(f"{ollama_url}/api/chat", json=payload)
        r.raise_for_status()
    return r.json().get("message", {}).get("content", "")


async def _exec_tool(name: str, args: dict, workspace_dir: Path) -> str:
    try:
        if name == "list_files":
            fp, in_ws = _resolve(args.get("path", "."), workspace_dir)
            if not in_ws and not perms.is_allowed(str(fp)):
                return f"__NEED_PERMISSION__{fp}__read"
            if not fp.exists():
                return f"Error: path not found: {fp}"
            if fp.is_file():
                return f"(this is a file, not a directory): {fp}"
            items = sorted(fp.iterdir(), key=lambda x: (x.is_file(), x.name))
            return "\n".join(f"{'FILE' if i.is_file() else 'DIR '} {i.name}" for i in items) or "(empty)"

        elif name == "read_file":
            fp, in_ws = _resolve(args.get("filename", ""), workspace_dir)
            if not in_ws and not perms.is_allowed(str(fp)):
                return f"__NEED_PERMISSION__{fp}__read"
            if not fp.exists():
                return f"Error: file not found: {fp}"
            return fp.read_text(errors="replace")[:10000]

        elif name == "write_file":
            fp, in_ws = _resolve(args.get("filename", ""), workspace_dir)
            if not in_ws:
                return "Error: write_file only allowed within workspace"
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(args.get("content", ""))
            return f"Written: {fp.name} ({len(args.get('content', ''))} chars)"

        elif name == "execute_code":
            result = await asyncio.to_thread(
                run_code_sandboxed, args.get("code", ""), args.get("language", "python")
            )
            out = (result.get("stdout") or "").strip()
            err = (result.get("stderr") or "").strip()
            return (out + ("\n[stderr]\n" + err if err else "")).strip()[:5000] or "(no output)"

        elif name == "web_search":
            results = await duckduckgo_search(args.get("query", ""), max_results=5)
            return "\n\n".join(
                f"**{r['title']}**\n{r.get('url','')}\n{r.get('body','')}" for r in results
            ) or "No results"

        elif name == "request_permission":
            import uuid as _uuid
            req_id = _uuid.uuid4().hex[:12]
            return f"__ASK_PERMISSION__{req_id}__{args.get('path','')}__{args.get('operation','read')}"

        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool error ({name}): {e}"


async def _handle_permission(result: str) -> tuple[str, dict | None]:
    """Returns (updated_result, permission_event_to_yield | None)."""
    if not (result.startswith("__NEED_PERMISSION__") or result.startswith("__ASK_PERMISSION__")):
        return result, None

    import uuid as _uuid
    parts   = result.split("__")
    req_id  = parts[2] if result.startswith("__ASK_PERMISSION__") else _uuid.uuid4().hex[:12]
    path    = parts[3] if len(parts) > 3 else ""
    op      = parts[4] if len(parts) > 4 else "read"

    event_obj = asyncio.Event()
    holder: list = []
    _perm_events[req_id] = (event_obj, holder)
    perms.request_access(path, op)

    perm_event = {"type": "permission_request", "req_id": req_id, "path": path, "operation": op}

    try:
        await asyncio.wait_for(event_obj.wait(), timeout=120)
        decision = holder[0] if holder else "deny"
    except asyncio.TimeoutError:
        decision = "deny"
    finally:
        _perm_events.pop(req_id, None)

    result = (
        f"Permission {decision} for {path}. "
        + ("You may now access this path." if "allow" in decision else "Access denied.")
    )
    return result, perm_event


async def _run_agent(agent: str, task: str, context: str,
                     model: str, workspace_dir: Path, ollama_url: str,
                     custom_system: str = ""):
    """ReAct loop for one agent. Yields event dicts."""
    base_system = custom_system or AGENT_SYSTEMS.get(agent, AGENT_SYSTEMS["general"])
    system = base_system + "\n\n" + TOOL_INSTRUCTIONS
    user_content = task if not context else f"{context}\n\nYour task:\n{task}"
    messages = [{"role": "user", "content": user_content}]

    for _ in range(25):
        response = await _llm(model, messages, system, ollama_url)
        matches  = list(TOOL_RE.finditer(response))

        if not matches:
            yield {"type": "agent_output", "content": response}
            return

        m = matches[0]
        fn_name = m.group(1).strip()
        try:    fn_args = json.loads(m.group(2))
        except: fn_args = {}

        yield {"type": "tool_call", "tool": fn_name, "args": fn_args}
        result = await _exec_tool(fn_name, fn_args, workspace_dir)

        result, perm_ev = await _handle_permission(result)
        if perm_ev:
            yield perm_ev

        yield {"type": "tool_result", "tool": fn_name, "result": result[:600]}
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user",      "content": f"Tool result:\n{result}\n\nContinue."})

    yield {"type": "agent_output", "content": response}


async def _self_score(agent: str, task: str, output: str,
                      model: str, ollama_url: str) -> int | None:
    prompt = f"Task: {task}\n\nYour output:\n{output[:1500]}\n\nRate your work."
    try:
        raw  = await _llm(model, [{"role": "user", "content": prompt}], SELF_SCORE_SYSTEM, ollama_url)
        data = _parse_json(raw)
        return max(0, min(10, int(data.get("score", 5))))
    except Exception:
        return None


async def _run_to_queue(step: dict, context: str, model: str,
                        workspace_dir: Path, ollama_url: str,
                        queue: asyncio.Queue, outputs: dict):
    """Run one agent and push all events to the shared queue."""
    agent   = step.get("agent", "general")
    task    = step.get("task", "")
    custom  = step.get("system_prompt", "") or _custom_agents.get(agent, "")

    # Register custom agent for future rounds
    if custom and agent not in AGENT_SYSTEMS:
        _custom_agents[agent] = custom

    output = ""
    async for event in _run_agent(agent, task, context, model, workspace_dir, ollama_url, custom):
        if event["type"] == "agent_output":
            output = event["content"]
        await queue.put(event)

    outputs[agent] = output

    # Self-score
    score = await _self_score(agent, task, output, model, ollama_url)
    await queue.put({
        "type":   "agent_done",
        "agent":  agent,
        "output": output,
        "score":  score,
    })


async def orchestrate(task: str, model: str, project: str,
                      workspace_dir: Path, ollama_url: str) -> AsyncGenerator[dict, None]:

    # 1. Plan
    yield {"type": "planning"}
    try:
        raw_plan = await _llm(model, [{"role": "user", "content": task}], ORCHESTRATOR_SYSTEM, ollama_url)
        plan     = _parse_json(raw_plan)
        steps    = plan.get("steps") or []
        if not steps:
            raise ValueError("empty")
    except Exception:
        steps = [{"agent": "general", "task": task}]
        plan  = {"plan_summary": "Direct execution", "steps": steps}

    yield {"type": "plan", "summary": plan.get("plan_summary", ""), "steps": steps}

    MAX_ROUNDS     = 3
    audit_feedback = ""
    all_outputs: dict[str, str] = {}

    for round_num in range(1, MAX_ROUNDS + 1):
        context = f"Original task: {task}\n"
        if audit_feedback:
            context += f"\nAuditor feedback (fix these):\n{audit_feedback}\n"

        # Emit agent_start for every step upfront so UI shows all running in parallel
        for step in steps:
            agent_task = step.get("task", task)
            if audit_feedback:
                agent_task += f"\n\nFix: {audit_feedback}"
            yield {"type": "agent_start", "agent": step["agent"], "task": agent_task, "round": round_num}

        # 2. Run all agents in PARALLEL
        queue   = asyncio.Queue()
        outputs: dict[str, str] = {}
        worker_tasks = [
            asyncio.create_task(
                _run_to_queue(
                    {**step, "task": (step.get("task", task) + (f"\n\nFix: {audit_feedback}" if audit_feedback else ""))},
                    context, model, workspace_dir, ollama_url, queue, outputs
                )
            )
            for step in steps
        ]

        finished = 0
        while finished < len(steps):
            event = await queue.get()
            if event["type"] == "agent_done":
                finished += 1
                all_outputs[event["agent"]] = event["output"]
            yield event

        # Ensure tasks are done (they should be, but cancel stale ones)
        for t in worker_tasks:
            if not t.done():
                t.cancel()

        # 3. Audit
        yield {"type": "audit_start", "round": round_num}
        combined     = "\n\n".join(f"=== {a.upper()} ===\n{o}" for a, o in all_outputs.items())
        audit_prompt = f"Task: {task}\n\nWork done:\n{combined}"

        try:
            raw_audit = await _llm(model, [{"role": "user", "content": audit_prompt}], AUDITOR_SYSTEM, ollama_url)
            audit     = _parse_json(raw_audit)
        except Exception:
            audit = {"passed": True, "score": 7, "feedback": "", "issues": []}

        score          = max(0, min(10, int(audit.get("score", 7))))
        passed         = bool(audit.get("passed", score >= 7))
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
            final_prompt = f"Task: {task}\n\nCompleted work:\n{combined}\n\nAudit: {score}/10"
            final_text   = await _llm(model, [{"role": "user", "content": final_prompt}], FINAL_SYSTEM, ollama_url)
            yield {"type": "done", "output": final_text, "score": score}
            return
