"""
KreativOS — Core Engine Functions
Ollama helpers, file extraction, Ralph Loop.
Extracted from main.py for route module reuse.
"""
import asyncio
import json
import httpx
from typing import AsyncGenerator

from . import state
from .config import AGENT_SYSTEMS, get_skills_for_agent
from .context_manager import build_full_system_prompt

KEEPALIVE_INTERVAL = 25
_RETRIES = 2


async def _ollama_post(url: str, payload: dict, timeout: int = 300):
    last_err = None
    for attempt in range(_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                return await client.post(url, json=payload)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            last_err = e
            if attempt < _RETRIES:
                await asyncio.sleep((attempt + 1) * 0.5)
    raise last_err  # type: ignore[misc]


async def stream_ollama(
    model: str, messages: list, system: str
) -> AsyncGenerator[str, None]:
    """Stream Ollama chat response with SSE keepalive."""
    payload = {
        "model":    model,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream":   True,
    }
    last_chunk_time = asyncio.get_running_loop().time()
    last_err = None
    for attempt in range(_RETRIES + 1):
        try:
            client = httpx.AsyncClient(timeout=300)
            resp = await client.stream("POST", f"{state.OLLAMA_BASE_URL}/api/chat", json=payload)
            resp.raise_for_status()
            break
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            last_err = e
            await client.aclose()
            if attempt < _RETRIES:
                await asyncio.sleep((attempt + 1) * 0.5)
    if last_err and attempt == _RETRIES:
        raise last_err
    async with resp:
        async for line in resp.aiter_lines():
            now = asyncio.get_running_loop().time()
            if now - last_chunk_time > KEEPALIVE_INTERVAL:
                yield ""
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
    resp = await _ollama_post(f"{state.OLLAMA_BASE_URL}/api/chat", payload)
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"Ollama error: {data['error']}")
    return data.get("message", {}).get("content", "")


def _parse_filename_hint(line: str) -> str | None:
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
            pre_hint = _parse_filename_hint(lines[i - 1]) if i > 0 else None
            in_block, block_lines, filename = True, [], pre_hint
        elif line.startswith("```") and in_block:
            in_block = False
            if filename and block_lines:
                fp = (state.WORKSPACE_DIR / filename).resolve()
                if not str(fp).startswith(str(state.WORKSPACE_DIR.resolve())):
                    block_lines, filename = [], None
                    continue
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text("\n".join(block_lines))
                saved.append(str(filename))
                state.stats["files_created"] += 1
                state.track("file_saved", filename)
                if project and state.memory:
                    state.memory.add_file(project, filename)
            block_lines, filename = [], None
        elif in_block:
            hint = _parse_filename_hint(line) if not filename else None
            if hint:
                filename = hint
            else:
                block_lines.append(line)
    return saved


async def ralph_loop(
    model: str, task: str, initial: str, agent_type: str
) -> dict:
    if not initial or not initial.strip():
        return {
            "output": initial, "passed": False, "iterations": 0,
            "log": [], "error": "Empty initial output — skipping Ralph Loop",
        }
    state.stats["ralph_loops_run"] += 1
    state.track("ralph_loop", f"{agent_type}: {task[:40]}")
    MAX_CTX = 6000
    current = initial
    log = []
    for i in range(1, 4):
        try:
            preview = current[:MAX_CTX] + ("\n...[truncated]" if len(current) > MAX_CTX else "")
            msgs = [{"role": "user", "content": f"Original task: {task[:500]}\n\nOutput to review:\n{preview}"}]
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
                "QA Verdict: PASS" in qa_r
                or ("PASS" in qa_r and "FAIL" not in qa_r.split("Verdict:")[-1][:30])
            )
            log.append({
                "iteration": i, "critic": critic[:400] if critic else "",
                "qa": qa_r[:400] if qa_r else "",
                "critic_passed": cp, "qa_passed": qp,
            })
            if cp and qp:
                state.track("ralph_passed", f"Passed on iteration {i}")
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
                    state.stats["ralph_fixes_applied"] += 1
                    state.track("ralph_fix", f"Iteration {i}")
            except asyncio.TimeoutError:
                state.track("ralph_fix_timeout", f"Iteration {i}")
            except Exception as e:
                state.track("ralph_fix_error", str(e)[:60])
        except Exception as outer:
            log.append({
                "iteration": i, "error": f"Outer error: {str(outer)}",
                "critic_passed": False, "qa_passed": False,
            })
    return {"output": current, "passed": False, "iterations": 3, "log": log}
