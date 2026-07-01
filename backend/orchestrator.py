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
import uuid
import httpx
from pathlib import Path
from typing import AsyncGenerator

from . import run_history
from .config import AGENT_SYSTEMS
from . import permissions as perms
from . import knowledge
from .sandbox import run_code_sandboxed
from .web_search import duckduckgo_search
from .mcp_client import call_tool as mcp_call_tool, load_servers as mcp_load_servers
from .telegram_utils import send_telegram_artifact
from . import github_client as gh

# ── Permission signalling ──────────────────────────────────────────────────────
_perm_events: dict[str, tuple] = {}

def signal_permission(req_id: str, decision: str):
    entry = _perm_events.get(req_id)
    if entry:
        event, holder = entry
        holder.append(decision)
        event.set()

# ── In-session custom agents created by the orchestrator ──────────────────────
from collections import OrderedDict
_custom_agents: OrderedDict[str, str] = OrderedDict()
MAX_CUSTOM_AGENTS = 100
# ponytail: bounded at 100 to prevent memory leak from unbounded agent creation

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
- search_knowledge {"query": "...", "top_k": 5} — semantic search over uploaded documents
- call_mcp     {"server": "open-design", "tool": "generate_prototype", "args": {...}} — call an external MCP server tool
- request_permission {"path": "/absolute/path", "operation": "read"} — ask user before accessing paths outside workspace
- github_list_repos {} — list GitHub repos (requires GITHUB_TOKEN)
- github_create_issue {"owner": "...", "repo": "...", "title": "..."} — create an issue on a repo
- github_commit_file {"owner": "...", "repo": "...", "path": "...", "content": "...", "message": "..."} — create/update a file in a repo

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


def _mcp_hint() -> str:
    servers = [s for s in mcp_load_servers() if s.get("enabled", True)]
    if not servers:
        return ""
    lines = ["", "## Configured MCP Servers (call via call_mcp tool):"]
    for s in servers:
        lines.append(f"- {s['name']}: {s.get('description', s['url'])}")
    return "\n".join(lines)


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
            # ponytail: fire-and-forget telegram delivery — failures silently ignored
            asyncio.create_task(send_telegram_artifact(str(fp), f"Agent wrote: {fp.name}"))
            return f"Written: {fp.name} ({len(args.get('content', ''))} chars)"

        elif name == "execute_code":
            result = await asyncio.to_thread(
                run_code_sandboxed, args.get("code", ""), args.get("language", "python"), workspace_dir=str(workspace_dir)
            )
            out = (result.get("stdout") or "").strip()
            err = (result.get("stderr") or "").strip()
            return (out + ("\n[stderr]\n" + err if err else "")).strip()[:5000] or "(no output)"

        elif name == "web_search":
            results = await duckduckgo_search(args.get("query", ""), max_results=5)
            return "\n\n".join(
                f"**{r['title']}**\n{r.get('url','')}\n{r.get('body','')}" for r in results
            ) or "No results"

        elif name == "call_mcp":
            server = args.get("server", "")
            tool   = args.get("tool", "")
            margs  = args.get("args", {})
            if not server or not tool:
                return "Error: call_mcp requires 'server' and 'tool'"
            result = await mcp_call_tool(server, tool, margs)
            return json.dumps(result) if isinstance(result, (dict, list)) else str(result)

        elif name == "request_permission":
            import uuid as _uuid
            req_id = _uuid.uuid4().hex[:12]
            return f"__ASK_PERMISSION__{req_id}__{args.get('path','')}__{args.get('operation','read')}"

        elif name == "search_knowledge":
            return json.dumps(knowledge.search_knowledge(
                workspace_dir,
                args.get("query", ""),
                args.get("top_k", 5)
            ))

        elif name == "github_list_repos":
            repos = await gh.list_repos()
            return json.dumps(repos, indent=2) if repos else "No repos or GITHUB_TOKEN not set"

        elif name == "github_create_issue":
            result = await gh.create_issue(args["owner"], args["repo"], args["title"], args.get("body", ""), args.get("labels"))
            return json.dumps(result, indent=2)

        elif name == "github_commit_file":
            result = await gh.commit_file(args["owner"], args["repo"], args["path"], args["content"], args["message"], args.get("branch", "main"))
            return json.dumps(result, indent=2)

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
                     custom_system: str = "",
                     cancel_event: asyncio.Event | None = None):
    """ReAct loop for one agent. Yields event dicts."""
    base_system = custom_system or AGENT_SYSTEMS.get(agent, AGENT_SYSTEMS["general"])
    system = base_system + "\n\n" + TOOL_INSTRUCTIONS + _mcp_hint()
    user_content = task if not context else f"{context}\n\nYour task:\n{task}"
    messages = [{"role": "user", "content": user_content}]

    for _ in range(25):
        if cancel_event and cancel_event.is_set():
            yield {"type": "agent_output", "content": "[cancelled]"}
            return
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
        # ponytail: keep last 10 turns to avoid overflowing model context
        if len(messages) > 10:
            messages = [messages[0]] + messages[-9:]

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
                         queue: asyncio.Queue, outputs: dict,
                         cancel_event: asyncio.Event | None = None):
    """Run one agent and push all events to the shared queue."""
    agent   = step.get("agent", "general")
    task    = step.get("task", "")

    # Per-agent model override
    agent_models = {}
    agent_models_file = workspace_dir / ".agent_models.json"
    if agent_models_file.exists():
        try:
            agent_models = json.loads(agent_models_file.read_text())
        except Exception:
            pass
    model = agent_models.get(agent, model)

    custom  = step.get("system_prompt", "") or _custom_agents.get(agent, "")

    # Register custom agent for future rounds
    if custom and agent not in AGENT_SYSTEMS:
        _custom_agents[agent] = custom
        if len(_custom_agents) > MAX_CUSTOM_AGENTS:
            _custom_agents.popitem(last=False)  # evict oldest

    # Agent prompt override from file (Settings UI)
    if not custom:
        prompts_dir = workspace_dir / ".agent_prompts"
        override_file = prompts_dir / f"{agent}.json"
        if override_file.exists():
            try:
                override = json.loads(override_file.read_text(encoding="utf-8"))
                custom = override.get("system", "")
            except (json.JSONDecodeError, KeyError):
                pass

    try:
        output = ""
        async for event in _run_agent(agent, task, context, model, workspace_dir, ollama_url, custom, cancel_event=cancel_event):
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
    except Exception as e:
        await queue.put({"type": "agent_done", "agent": agent, "output": f"Error: {e}", "score": None})


async def orchestrate(task: str, model: str, project: str,
                       workspace_dir: Path, ollama_url: str,
                       cancel_event: asyncio.Event | None = None,
                       conv_id: str = "") -> AsyncGenerator[dict, None]:

    run_id = str(uuid.uuid4())[:12]
    run_history.record_run_start(run_id, task_id="", conv_id=conv_id, agent_name="orchestrator", workflow_name="")

    try:
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

            for step in steps:
                agent_task = step.get("task", task)
                if audit_feedback:
                    agent_task += f"\n\nFix: {audit_feedback}"
                yield {"type": "agent_start", "agent": step["agent"], "task": agent_task, "round": round_num}

            queue   = asyncio.Queue()
            outputs: dict[str, str] = {}
            worker_tasks = [
                asyncio.create_task(
                    _run_to_queue(
                        {**step, "task": (step.get("task", task) + (f"\n\nFix: {audit_feedback}" if audit_feedback else ""))},
                        context, model, workspace_dir, ollama_url, queue, outputs,
                        cancel_event=cancel_event,
                    )
                )
                for step in steps
            ]

            finished = 0
            try:
                while finished < len(steps):
                    event = await queue.get()
                    if event["type"] == "agent_done":
                        finished += 1
                        all_outputs[event["agent"]] = event["output"]
                    yield event
            finally:
                for t in worker_tasks:
                    if not t.done():
                        t.cancel()

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
                run_history.record_run_end(run_id, "completed")
                return

        run_history.record_run_end(run_id, "completed")
    except asyncio.CancelledError:
        run_history.record_run_end(run_id, "cancelled")
        raise
    except Exception as e:
        run_history.record_run_end(run_id, "failed", error=str(e))
        raise
