# KreativOS — Analysis (merged, current as of 2026-07-01)

All findings, fixes, and features from the original analysis are complete. This is the living reference.

---

## Current Posture

**Security:** B — Auth required by default, random admin password (logged, not on disk), role-gated user CRUD, SSRF validation (all private IPs blocked), rate-limited backups/deletes/MCP, protected system directories, WebSocket auth respects AUTH_REQUIRED, MCP results wrapped as data in LLM context.

**Architecture:** B+ — Lifespan pattern (no deprecated `on_event`), async httpx clients (no leaks), worker task cancellation on disconnect, exception-safe queues, atomic file writes (tmp+replace), context trim inside ReAct loop, per-call SQLite connections. Routes extracted from monolithic chat.py (was 1245, now 1150) into `routes/conversations.py`, `routes/knowledge.py`, `routes/github.py`.

**Frontend:** B — React.lazy code splitting (5 chunks), React.memo on message rows, AbortController on streams, live streaming display (not batch), buffered localStorage writes, individual Zustand selectors, prism-light syntax highlighting (9 languages, not 200+).

---

## What's Shipped

### Security fixes (10)
| # | Fix | File |
|---|-----|------|
| 1 | `AUTH_REQUIRED=true` default | `main.py` |
| 2 | Random admin password on first boot, in-memory only | `auth.py` |
| 3 | `python-multipart>=0.0.18` (CVE-2024-53498) | `requirements.txt` |
| 4 | `.auth/` blocked in file read/delete | `routes/chat.py` |
| 5 | `workspace_dir` passed to sandbox call | `orchestrator.py` |
| 6 | `OrderedDict` maxlen bug → manual eviction | `orchestrator.py` |
| 7 | WebSocket respects `AUTH_REQUIRED` | `routes/chat.py` |
| 8 | Admin role check on user create/delete | `routes/core.py` |
| 9 | `.resolve()` guard on backup paths | `routes/chat.py` |
| 10 | Windows no-sandbox warning logged | `sandbox.py` |

### Architecture fixes (15)
| # | Fix | File |
|---|-----|------|
| 11 | httpx client leak → async context manager | `engine.py` |
| 12 | Worker tasks cancelled on SSE disconnect | `orchestrator.py` |
| 13 | Worker exception → `agent_done` on failure | `orchestrator.py` |
| 14 | Context trim inside ReAct loop | `orchestrator.py` |
| 15 | Atomic writes (tmp+replace) in memory, scheduler, auth | `memory.py`, `scheduler.py`, `auth.py` |
| 16 | `state.stats` reset in `reinit_workspace()` | `main.py` |
| 17 | Stream buffer ref → one localStorage write on done | `ChatView.jsx`, `store.js` |
| 18 | Stale closure in permission poll → `useStore.getState()` | `App.jsx` |
| 19 | `activeConvId` persisted to localStorage | `store.js` |
| 20 | PermissionDialog X → deny decision | `PermissionDialog.jsx` |
| 21 | AbortController on stream fetch | `api.js`, `ChatView.jsx` |
| 22 | React.memo on MessageRow | `ChatView.jsx` |
| 23 | React.lazy on 4 heavy views | `App.jsx` |
| 24 | SSRF: block all private IP ranges | `mcp_client.py` |
| 25 | Rate limits: backup 3/h, file delete 60/m, mcp/call 60/m | `routes/chat.py` |

### Post-fix verification (7)
| Priority | Fix | File |
|----------|-----|------|
| P0 | Live streaming display (liveContent state) | `ChatView.jsx` |
| P1 | auth.py atomic save + utf-8 | `auth.py` |
| P1 | No plaintext `.first_boot_password` on disk | `auth.py` |
| P1 | MCP SSRF blocks all private IPs via `ipaddress` | `mcp_client.py` |
| P2 | Sidebar individual Zustand selectors | `Sidebar.jsx` |
| P2 | SyntaxHighlighter prism-light (9 languages) | `MessageRenderer.jsx` |
| P2 | FastAPI lifespan migration | `main.py` |

### Phase 1 — Foundation (5)
- **SQLite conversations** — FTS5 full-text search, WAL mode, CRUD via `/api/conversations`
- **Onboarding wizard** — 3-step modal: Ollama check → pull via backend → first task
- **Background scheduler** — 60s asyncio tick in `main.py` lifespan, `get_due_tasks()` loop
- **Task cancel** — `_running_tasks` dict + `asyncio.Event` + `POST /api/tasks/{id}/cancel`
- **User pipeline templates** — `workspace/pipelines/*.json`, save/load/delete via API + UI

### Phase 2 — Power (7)
- **Local RAG** — Upload → chunk (512 overlap) → embed (nomic-embed-text) → cosine search. `search_knowledge` tool
- **Multi-model routing** — `.agent_models.json` config, per-agent model dropdown in Settings
- **App Builder preview** — `<iframe srcdoc>` live preview for web apps
- **Conversation search** — FTS5 search bar in Sidebar with debounce
- **Token usage** — `prompt_eval_count`/`eval_count` counters via Dashboard stat cards
- **File version history** — `.versions/{filename}__{timestamp}` copies, restore modal
- **Voice input** — Web Speech API mic button, no dependencies

### Phase 3 — Ecosystem (7)
- **Agent prompt editor** — `workspace/.agent_prompts/*.json`, override per-agent prompts in Settings
- **Workflow export/import** — JSON download/upload for Canvas workflows
- **MCP discovery UI** — Server list with status dot + tool count + expandable tool details
- **Telegram artifact delivery** — Files sent as Telegram documents on completion
- **Browser notifications** — `Notification` on task complete (tab unfocused)
- **GitHub integration** — `list_repos`/`create_issue`/`commit_file` tools, env token at call time
- **Run history** — SQLite-backed runs, stats cards, table with duration/files/status

---

## Architecture (current)

```
Browser (React PWA)
    │
    ├── HTTP/REST ──► FastAPI main.py (236 lines, orchestrator)
    │                     ├── routes/core.py          → health, auth, settings
    │                     ├── routes/chat.py           → chat, tasks, files, pipeline, canvas, mcp, backup, etc (1150 lines)
    │                     ├── routes/conversations.py  → SQLite conversation CRUD (6 routes)
    │                     ├── routes/knowledge.py      → RAG upload/search/delete (4 routes)
    │                     └── routes/github.py         → repos/issues/commit (3 routes)
    │
    └── WebSocket (first-message auth, reconnect)
         │
         v
    Ollama (localhost:11434, configurable via OLLAMA_BASE_URL)

SQLite databases (workspace/.kreativ/):
    └── run_history.db
    workspace/.kreativ/conversations.db
    workspace/knowledge/index.json  (flat JSON vector store)
    workspace/.auth/users.json
    workspace/.memory/
    workspace/.scheduler/tasks.json
    workspace/.backups/
    workspace/.workflows.json
    workspace/pipelines/*.json
    workspace/.versions/
```

---

## Remaining Items

Nothing from the analysis remains. Future work if desired:

| Item | Effort | Why |
|------|--------|-----|
| Extract canvas + MCP routes from chat.py | ~100 lines | chat.py still 1150 lines with 10+ domains |
| Conditional branching in Canvas workflows | Medium | Canvas is linear only |
| Diff view + re-run for code review | Small | Single-pass review today |
| `workspace/user/` vs `workspace/system/` separation | Medium | All files in one dir, manual exclusions |
| GitHub Gist workflow registry | Medium | Community template sharing |
| Vector DB upgrade (hnswlib) | Medium | JSON scan is O(n), fine under ~1000 chunks |
| Accessibility audit (aria, labels, keyboard nav) | Low | Noted but not addressed |
