# KreativOS — Code Review & Roadmap
_Generated: 2026-06-30_

---

## What This Is

KreativOS is a self-hosted, browser-based Agentic OS. It runs 100 % locally on CPU via Ollama. Users chat with multi-agent pipelines, generate Office files, run sandboxed code, search the web, schedule tasks, and connect external MCP servers — all from a single-page React app backed by a FastAPI server.

**Lines of code:** ~4 300 Python · ~5 500 JSX · built in ~2 days of rapid iteration.

---

## Architecture Snapshot

```
KreativOS/
├── backend/               FastAPI server (Python)
│   ├── main.py            1 687 lines — API surface + WS + routing
│   ├── orchestrator.py    406 lines — parallel ReAct multi-agent engine
│   ├── config.py          382 lines — agent personas + skills
│   ├── office_agents.py   313 lines — DOCX/PPTX/XLSX generation
│   ├── sandbox.py         219 lines — code execution isolation
│   ├── auth.py            185 lines — bcrypt + token auth
│   ├── pipeline.py        85 lines  — named pipeline templates
│   ├── mcp_client.py      56 lines  — JSON-RPC 2.0 MCP bridge
│   └── permissions.py     91 lines  — Allow Once / Session / Deny
├── frontend/              React 18 + Vite + Tailwind + Zustand
│   ├── pages/             22 views
│   ├── components/        5 shared components
│   ├── store.js           184 lines — Zustand global state
│   └── App.jsx            265 lines — routing + auth gate + WS
└── KreativOS.bat          Windows one-click launcher
```

---

## What's Working Well

### 1. Orchestrator design is solid
The ReAct loop (`orchestrator.py`) is the best piece of the codebase. Parallel asyncio fan-out, a shared queue, per-agent self-scoring, and an auditor retry loop (up to 3 rounds) — this is architecturally sound for a local-model setup. The `_run_to_queue` pattern avoids any shared state between agents correctly.

### 2. Permission system is real security, not fake security
`permissions.py` + `PermissionDialog.jsx` + the `__NEED_PERMISSION__` sentinel pattern gives the agent a real sandbox boundary. Allow Once / Session / Deny is the right UX. The `check_code_paths()` regex scan on generated code before execution is a good defence layer.

### 3. Separation of concerns improved
`config.py` was correctly extracted to hold all prompts and personas. `paths.py` externalises the workspace path so tests can inject a temp dir. `context_manager.py` builds system prompts. The ponytail audit pass (22 dead items deleted) made a real difference.

### 4. Test suite exists and runs
59 tests passing without requiring Ollama. The `reinit_workspace()` pattern in `main.py` for test isolation is correct. `conftest.py` is clean.

### 5. Message pruning in Zustand store
Capping at 200 messages and pruning 50 oldest prevents localStorage blowout. The notice message inserted at the trim point is good UX.

---

## Issues — Ranked by Severity

### CRITICAL

**C1 — `main.py` is 1 687 lines and will become unmaintainable**
This file contains model chat, WebSocket handlers, file management, pipeline routes, orchestrator routes, settings, backup, scheduler, MCP, skill eval, code review, Telegram config — all mixed together. A single import error anywhere breaks the whole server.

Fix: extract route groups into `backend/routes/` (chat.py, files.py, pipeline.py, orchestrator.py, admin.py). FastAPI `APIRouter` makes this trivial. Target <300 lines for `main.py`.

**C2 — All conversation history lives in localStorage**
`store.js` persists conversations to `localStorage`. A single long orchestration run with many tool calls can easily exceed the 5–10 MB browser limit, silently failing writes. There's no server-side conversation persistence — if the user clears the browser, history is gone.

Fix: add a `/api/conversations` CRUD endpoint backed by SQLite (one file, stdlib `sqlite3`, no ORM needed). Store message blobs as JSON. Frontend syncs on mount.

**C3 — `_custom_agents` is a process-global dict — memory leak**
In `orchestrator.py`, dynamically created agents are stored in `_custom_agents: dict[str, str]`. This grows forever across all sessions with no eviction. On a long-running server this accumulates stale system prompts indefinitely.

Fix: move it to per-request context or cap with `maxlen` via `collections.OrderedDict(maxlen=100)`.

---

### HIGH

**H1 — No context-window management in `_run_agent`**
The ReAct loop appends every tool call and result to `messages` with no length check. At 25 iterations with verbose tool results (capped at 600 chars each) the context can still grow past many local model limits, causing silent truncation or OOM on the model server.

Fix: add a rolling window — keep the last N messages, always keep the system prompt and first user message. Or summarise the middle when `len(messages) > threshold`.

**H2 — No retry or circuit-breaker in `_llm()`**
A single `httpx` call with a 180 s timeout. If Ollama is slow or returns a malformed response, the call fails hard and the user sees an error mid-orchestration. In a 3-round audit loop this is 9+ sequential LLM calls all with zero retry.

Fix: wrap `_llm()` with `tenacity` (already installable, or 10 lines of manual exponential backoff). Two retries is enough.

**H3 — MCP client has no connection pooling or server-health check**
`mcp_client.py` creates a new `AsyncClient` per call. For high-frequency tool use this creates and destroys HTTP connections every call. There's also no check that the MCP server is reachable before the orchestrator tries to call it.

Fix: move to a module-level `httpx.AsyncClient` instance (singleton, reused). Add a `/api/mcp/status` endpoint that pings each enabled server and returns reachability.

**H4 — `allow_origins=["*"]` on a server that handles auth tokens**
CORS is wide open. Since the app is local-only this isn't an internet risk, but if the user ever exposes it (via ngrok, Tailscale, port-forward), any website can make authenticated requests with the user's stored token.

Fix: default to `allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"]`, make it overridable via `CORS_ORIGINS` env var.

---

### MEDIUM

**M1 — No WebSocket reconnect on the frontend**
`App.jsx` opens one WebSocket for permissions. If the connection drops (server restart, sleep/wake), the frontend is silently stuck. Permission dialogs stop appearing.

Fix: add an exponential-backoff reconnect loop in the `useEffect` that opens the WS. ~15 lines.

**M2 — Pipeline templates are hardcoded in `pipeline.py`**
`PIPELINE_TEMPLATES` is a dict literal. Users can't create, save, or share pipelines — they're stuck with whatever is coded. The `PipelineView.jsx` UI renders them, but there's no write path.

Fix: load templates from `workspace/pipelines/*.json`, fall back to built-ins. Add POST `/api/pipelines` to save user templates.

**M3 — `Kreativ_Agent` repo has an orphaned upstream**
`/c/Users/mpate/Kreativ_Agent` is on `main` but `origin/master` is gone. There are uncommitted changes in `renderer/app.js` and `renderer/index.html`. This is a data-loss risk.

Fix: commit the changes, then `git branch --unset-upstream` or point to the correct remote.

**M4 — No token/cost tracking**
There's no visibility into how many tokens each orchestration run consumes. For local models this is less about cost and more about knowing when to summarise context. Without it, users have no signal that their context window is being exceeded.

Fix: Ollama's `/api/chat` response includes `prompt_eval_count` and `eval_count`. Log these per-call and return them in the `agent_done` event so the UI can show a token counter.

**M5 — Sandbox escape via `execute_code` path traversal**
`sandbox.py` runs user code in a subprocess. The `write_file` tool is workspace-scoped, but `execute_code` can contain `open('/etc/passwd')` or `import shutil; shutil.rmtree('/')`. The `check_code_paths()` regex in `permissions.py` is a best-effort scan, not a hard boundary.

Fix: run sandboxed code in a restricted environment — at minimum set `cwd=workspace_dir` and use `resource` limits (Linux) or a Docker exec fallback. The real fix is a proper sandbox (Pyodide in WASM, or a Docker container per execution).

---

### LOW / POLISH

**L1 — No loading skeleton in ModelHubView**
On slow connections the model list renders blank, then jumps. Add a simple spinner or skeleton row.

**L2 — `scheduler.py` uses in-memory job list**
Scheduled tasks survive only as long as the process. A restart drops all pending schedules. Back with a `workspace/scheduler.json` file (same pattern as memory/backup).

**L3 — `audit.py` log is append-only with no rotation**
`AuditLog` appends to a single JSON file forever. Add a max-size check (e.g. 10 MB) and rotate to `audit.log.1`.

**L4 — Frontend `package.json` lists no dependencies**
All frontend deps are in `frontend/package.json` (not root). The root `package.json` is effectively unused. Either remove it or make it a workspace root pointing at `frontend/`.

---

## Roadmap — Prioritised

### Phase 1 — Stability (next sprint)
1. Split `main.py` into route modules → improves maintainability, makes PRs reviewable
2. SQLite for conversation persistence → eliminates localStorage limit risk
3. WS reconnect in `App.jsx` → stops silent permission failures
4. `_custom_agents` eviction → plugs memory leak
5. Fix `Kreativ_Agent` upstream + commit orphaned changes

### Phase 2 — Reliability
6. Retry wrapper on `_llm()` → handles Ollama hiccups
7. Context-window rolling window in `_run_agent` → prevents silent truncation
8. CORS tightened to localhost origins → safer for future remote access
9. MCP singleton client + health endpoint → faster tool calls + visibility
10. Token counter in orchestration events → user sees context usage

### Phase 3 — Features users will ask for
11. User-defined pipeline templates (save/load from workspace)
12. Scheduler persistence (JSON file, survive restart)
13. Audit log rotation
14. Multi-user workspace isolation (one `workspace/<username>/` dir per user)
15. Docker compose with Ollama sidecar — one command to run the whole stack
16. Export/import conversations (JSON dump endpoint)

### Phase 4 — Scale (only if needed)
17. Replace file-based memory with SQLite FTS5 for search
18. Streaming cost dashboard (tokens per session)
19. Plugin/tool registry — drop new `.py` files into `backend/tools/` and they auto-register
20. Proper WASM sandbox for `execute_code` (Pyodide or Deno)

---

## Architecture Diagram (current)

```
Browser (React PWA)
    │
    ├── HTTP/REST  ──►  FastAPI main.py
    │                       ├── /api/chat          → orchestrator.py or direct Ollama
    │                       ├── /api/pipeline      → pipeline.py
    │                       ├── /api/files         → workspace/ dir
    │                       ├── /api/mcp           → mcp_client.py → external MCP servers
    │                       ├── /api/models        → model_hub.py → Ollama REST
    │                       ├── /api/scheduler     → scheduler.py (in-memory)
    │                       ├── /api/memory        → memory.py (JSON files)
    │                       ├── /api/backup        → backup.py (zip files)
    │                       ├── /api/audit         → audit.py (append-only JSON)
    │                       └── /api/permissions   → permissions.py (in-memory)
    │
    └── WebSocket  ──►  /ws/permissions  (permission dialog bridge)

Ollama (localhost:11434)
    └── /api/chat  ◄── all LLM calls (orchestrator + direct chat + tools)

Workspace (filesystem)
    └── workspace/  ←── files, memory, backup, mcp_servers.json, audit.json
```

---

## Architecture Diagram (target after Phase 1+2)

```
Browser (React PWA)
    │
    ├── HTTP/REST  ──►  FastAPI main.py  (~250 lines, routing only)
    │                       ├── routes/chat.py
    │                       ├── routes/pipeline.py
    │                       ├── routes/files.py
    │                       ├── routes/orchestrator.py
    │                       └── routes/admin.py
    │
    └── WebSocket  ──►  /ws/permissions  (with reconnect)

SQLite db  ←──  conversations, audit, scheduler, memory index
Workspace/  ←── binary files, pipeline templates, mcp config

Ollama  ←── (same, unchanged)
```

---

## Summary

KreativOS is a genuinely impressive local-AI OS built at speed. The orchestration engine, permission system, and test suite set it apart from most hobby projects. The critical risk right now is `main.py` becoming a 2 000-line monolith and localStorage being the only persistence layer. Fix those two first and the project is on a solid foundation for everything else.
