"""
KreativOS — Orchestrator (ReAct pattern)
Works with any Ollama model — no native tool-calling support required.
Agents emit TOOL: / ARGS: lines; we parse, execute, and continue until done.
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

# ── Tool docs injected into every agent's system prompt ───────────────────────
TOOL_INSTRUCTIONS = """
## Tools
To use a tool write these two lines EXACTLY (no extra text between them):
TOOL: tool_name
ARGS: {"key": "value"}

Available tools:
- list_files   {"path": "."} — list a directory (relative to workspace OR absolute)
- read_file    {"filename": "path/to/file"} — read file contents (relative or absolute)
- write_file   {"filename": "relative/path", "content": "text"} — write to workspace
- execute_code {"code": "...", "language": "python"} — run code, returns stdout/stderr
- web_search   {"query": "search terms"} — search the web
- request_permission {"path": "/absolute/path", "operation": "read"} — ask user before accessing paths outside workspace

Rules:
- For any path outside the workspace, call request_permission FIRST.
- Use list_files to explore before reading files.
- You may call multiple tools sequentially — one per response turn.
- When finished with all tool work, write your final answer normally (no TOOL: line).
"""

ORCHESTRATOR_SYSTEM = """\
You are the KreativOS Orchestrator. Analyse the task and output a JSON execution plan.

Available agents: researcher, architect, coder, devops, general
- researcher : web search, information gathering, analysis
- architect  : system design, tech stack, folder structure
- coder      : write code, create files, run code
- devops     : Docker, CI/CD, deployment scripts
- general    : time, file exploration, writing, any other task

Respond ONLY with valid JSON (no markdown fences, no explanation):
{
  "plan_summary": "one sentence",
  "steps": [
    {"agent": "general", "task": "specific instructions for this agent"}
  ]
}

For simple tasks (check time, read files, quick questions) use a single general agent.
Order agents logically — each sees the previous agents' output."""

AUDITOR_SYSTEM = """\
You are the KreativOS Auditor. Review the agent work against the original task.
Respond ONLY with valid JSON:
{
  "passed": true,
  "score": 8,
  "feedback": "revision instructions if not passed, else empty string",
  "issues": []
}
passed = true when score >= 7."""

FINAL_SYSTEM = """\
You are the KreativOS Orchestrator. Present results to the user.
Summarise what was done, list any files created, explain how to use/run them.
Be concise. Use markdown."""

TOOL_RE = re.compile(r'TOOL:\s*(\w+)\s*\nARGS:\s*(\{[^}]*\}|\{[\s\S]*?\})', re.MULTILINE)


def _parse_json(raw: str) -> dict:
    """Parse JSON that may be wrapped in markdown fences or mixed with text."""
    clean = raw.strip()
    # Try markdown fence first
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', clean)
    if m:
        clean = m.group(1).strip()
    # Try bare JSON object anywhere in the text
    if not clean.startswith('{'):
        m = re.search(r'\{[\s\S]*\}', clean)
        if m:
            clean = m.group(0)
    return json.loads(clean)


def _resolve(raw: str, workspace_dir: Path) -> tuple[Path, bool]:
    """Return (resolved_path, is_within_workspace)."""
    p = Path(raw)
    resolved = p.resolve() if p.is_absolute() else (workspace_dir / raw).resolve()
    in_ws = str(resolved).startswith(str(workspace_dir.resolve()))
    return resolved, in_ws


# ── LLM call (non-streaming, text only) ───────────────────────────────────────
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


# ── Tool executor ──────────────────────────────────────────────────────────────
async def _exec_tool(name: str, args: dict, workspace_dir: Path) -> str:
    """Execute a parsed tool call. Returns result string."""
    try:
        if name == "list_files":
            fp, in_ws = _resolve(args.get("path", "."), workspace_dir)
            if not in_ws and not perms.is_allowed(str(fp)):
                return f"__NEED_PERMISSION__{fp}__read"
            if not fp.exists():
                return f"Error: path not found: {fp}"
            if fp.is_file():
                return f"(file, not directory): {fp}"
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
            return f"Written: {fp.name} ({len(args.get('content',''))} chars)"

        elif name == "execute_code":
            result = await asyncio.to_thread(
                run_code_sandboxed, args.get("code", ""), args.get("language", "python")
            )
            out = (result.get("stdout") or "").strip()
            err = (result.get("stderr") or "").strip()
            combined = out + ("\n[stderr]\n" + err if err else "")
            return combined.strip()[:5000] or "(no output)"

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


# ── Agent loop (ReAct) ─────────────────────────────────────────────────────────
async def _run_agent(agent: str, task: str, context: str,
                     model: str, workspace_dir: Path, ollama_url: str):
    system = AGENT_SYSTEMS.get(agent, AGENT_SYSTEMS["general"]) + "\n\n" + TOOL_INSTRUCTIONS
    user_content = task if not context else f"{context}\n\nYour task:\n{task}"
    messages = [{"role": "user", "content": user_content}]

    for _ in range(25):
        response = await _llm(model, messages, system, ollama_url)
        matches = list(TOOL_RE.finditer(response))

        if not matches:
            # No tool calls — final answer
            yield {"type": "agent_output", "content": response}
            return

        # Take first tool call only (one per turn keeps conversation coherent)
        m = matches[0]
        fn_name = m.group(1).strip()
        try:
            fn_args = json.loads(m.group(2))
        except Exception:
            fn_args = {}

        yield {"type": "tool_call", "tool": fn_name, "args": fn_args}
        result = await _exec_tool(fn_name, fn_args, workspace_dir)

        # Handle permission requests
        if result.startswith("__NEED_PERMISSION__") or result.startswith("__ASK_PERMISSION__"):
            parts   = result.split("__")
            req_id  = parts[2] if result.startswith("__ASK_PERMISSION__") else None
            path    = parts[3] if len(parts) > 3 else fn_args.get("path", "")
            op      = parts[4] if len(parts) > 4 else "read"

            import uuid as _uuid
            if not req_id:
                req_id = _uuid.uuid4().hex[:12]

            event_obj = asyncio.Event()
            holder: list = []
            _perm_events[req_id] = (event_obj, holder)

            # Register with the permissions module so the dialog appears
            perms.request_access(path, op)

            yield {"type": "permission_request", "req_id": req_id, "path": path, "operation": op}
            try:
                await asyncio.wait_for(event_obj.wait(), timeout=120)
                decision = holder[0] if holder else "deny"
            except asyncio.TimeoutError:
                decision = "deny"
            finally:
                _perm_events.pop(req_id, None)

            result = f"Permission {decision} for {path}. " + (
                "You may now access this path." if "allow" in decision else "Access denied — do not attempt to access this path."
            )

        yield {"type": "tool_result", "tool": fn_name, "result": result[:600]}

        # Continue conversation with the tool result
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": f"Tool result:\n{result}\n\nContinue."})

    yield {"type": "agent_output", "content": response}


# ── Main orchestration generator ───────────────────────────────────────────────
async def orchestrate(task: str, model: str, project: str,
                      workspace_dir: Path, ollama_url: str) -> AsyncGenerator[dict, None]:

    # 1. Plan
    yield {"type": "planning"}
    try:
        raw_plan = await _llm(model, [{"role": "user", "content": task}], ORCHESTRATOR_SYSTEM, ollama_url)
        plan     = _parse_json(raw_plan)
        steps    = plan.get("steps") or []
        if not steps:
            raise ValueError("empty steps")
    except Exception as e:
        # Fallback: single general agent
        steps = [{"agent": "general", "task": task}]
        plan  = {"plan_summary": "Direct execution", "steps": steps}

    yield {"type": "plan", "summary": plan.get("plan_summary", ""), "steps": steps}

    # 2. Execute → Audit → Revise (max 3 rounds)
    MAX_ROUNDS     = 3
    audit_feedback = ""
    all_outputs: dict[str, str] = {}

    for round_num in range(1, MAX_ROUNDS + 1):
        context = f"Original task: {task}\n"
        if audit_feedback:
            context += f"\nAuditor feedback (fix these):\n{audit_feedback}\n"

        for step in steps:
            agent      = step.get("agent", "general")
            agent_task = step.get("task", task)
            if audit_feedback:
                agent_task += f"\n\nFix: {audit_feedback}"

            yield {"type": "agent_start", "agent": agent, "task": agent_task, "round": round_num}

            output = ""
            async for event in _run_agent(agent, agent_task, context, model, workspace_dir, ollama_url):
                if event["type"] == "agent_output":
                    output = event["content"]
                else:
                    yield event

            all_outputs[agent] = output
            context += f"\n--- {agent.upper()} ---\n{output}\n"
            yield {"type": "agent_done", "agent": agent, "output": output}

        # 3. Audit
        yield {"type": "audit_start", "round": round_num}
        combined     = "\n\n".join(f"=== {a.upper()} ===\n{o}" for a, o in all_outputs.items())
        audit_prompt = f"Task: {task}\n\nWork done:\n{combined}"

        try:
            raw_audit    = await _llm(model, [{"role": "user", "content": audit_prompt}], AUDITOR_SYSTEM, ollama_url)
            audit        = _parse_json(raw_audit)
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
