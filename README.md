# KreativOS — Agentic Operating System

> Self-hosted · Browser-based · Runs 100% locally on CPU via Ollama · No cloud API keys needed

**v3 ships all 10 phases:** Pipeline · Memory · Web Search · App Builder · Canvas · Voice · Code Review · Scheduler · Auth · PWA

---

## Table of Contents

1. [Project Goal](#1-project-goal)
2. [Research & Comparisons](#2-research--comparisons)
3. [Achievements (v1 to v2 to v3)](#3-achievements-v1-to-v2-to-v3)
4. [Technology Stack](#4-technology-stack)
5. [Project Structure](#5-project-structure)
6. [Enhancement Roadmap — 10 Phases](#6-enhancement-roadmap--10-phases)
7. [Quick Start Guide](#7-quick-start-guide)

---

## 1. Project Goal

KreativOS is a self-hosted, browser-based Agentic Operating System that runs 100% locally on a CPU-only Oracle VM using Ollama.

**Core problem it solves:**

- Ollama chat is a single-conversation app — no agents, no task automation, no file workspace
- Cloud AI tools (Claude, ChatGPT) cost money and send data to external servers
- Developer tools (OpenCode, JARVIS) require technical setup and cloud API keys
- Non-technical users have no way to run autonomous AI locally from a browser

---

## 2. Research & Comparisons

Three existing systems were analysed before building KreativOS:

| System | Strength | Weakness |
|---|---|---|
| Open WebUI | Great browser UI | No agents or task automation |
| OpenCode | Ralph Loop quality system | CLI only, needs API keys |
| JARVIS | Voice input concept | No local model support |

Best-of-all design adopted:
- Browser UI from Open WebUI approach
- Ralph Loop quality system from OpenCode
- Voice input concept from JARVIS
- Ollama-native local engine (original)
- File workspace and code execution (original)

---

## 3. Achievements (v1 to v2 to v3)

### Version 1.0
- FastAPI backend with Ollama streaming (Server-Sent Events)
- React + Tailwind frontend — dark terminal-inspired UI
- 6 specialist agents: General, Coder, Researcher, Architect, Orchestrator, DevOps
- Autonomous task runner — agent works without step-by-step prompting
- File workspace — view, edit, download files agents create
- Code execution — run Python, Bash, JavaScript in the browser
- Docker + docker-compose deployment
- One-command install.sh for Oracle Ubuntu VM

### Version 2.0
- Ralph Loop — automatic self-critic + QA review after every Coder/Architect/DevOps task
- Up to 3 fix iterations before delivering final output
- 24 agent skill files injected as context (coding, security, testing, devops, docs, performance)
- Voice input — microphone button in chat using Web Speech API (Chrome/Edge, no API key)
- Dashboard — live stats: messages, tasks, files, Ralph Loop runs, agent usage chart

### Version 2.1
- Model Hub — HuggingFace GGUF model browser inside KreativOS
- 10 curated CPU-friendly models with size/RAM/speed info
- Live HuggingFace search from the browser
- One-click download into Ollama with live progress bar
- Model management — use, switch, or delete models from the UI

### Version 3.0 (Current)

- All 10 enhancement phases shipped in a single unified codebase
- Multi-Agent Pipeline — Orchestrator auto-routes tasks across Architect, Coder, DevOps agents
- Project Memory — persistent context file per project; agents read memory before responding
- Web Search — Researcher uses DuckDuckGo live search; results injected into context with citations
- App Builder — Coder generates full multi-file apps with preview panel and zip download
- Visual Canvas — drag-and-drop node editor for custom multi-agent workflows
- Voice Output — browser TTS speaks agent responses; full voice conversation mode
- Code Review Agent — upload any file, get structured bug/security/style report with auto-fix
- Scheduled Tasks — cron-style task scheduler with Dashboard visibility and output logs
- Multi-User Auth — login page, per-user workspaces, admin panel
- PWA — installable on mobile, offline chat history, push notifications, mobile-optimised layout
- Telegram Bot — control KreativOS from Telegram: run tasks, get results, check status
- Office Suite — generate .docx, .xlsx, .pptx files directly from agent output
- Audit Log — timestamped log of every agent action with full context
- Pipeline View — real-time multi-agent task pipeline with stage-by-stage progress tracker
- Scheduler View — visual cron manager with next-run countdown and task history
- Skill Evaluator — benchmark agent quality across domain-specific test prompts

---

## 4. Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python · FastAPI · Uvicorn |
| AI Engine | Ollama (local LLM, CPU) |
| Frontend | React 18 · Vite · Tailwind CSS · Zustand |
| Markdown | react-markdown · remark-gfm · react-syntax-highlighter |
| Office | python-pptx · python-docx · openpyxl |
| Messaging | python-telegram-bot |
| Testing | pytest · pytest-asyncio · httpx |
| Deployment | Docker · docker-compose or bare metal |

---

## 5. Project Structure

```
KreativOS/
├── main.py                  # FastAPI backend (all 10 phases)
├── scheduler.py             # Cron-style task scheduler
├── memory.py                # Project memory system
├── pipeline.py              # Multi-agent pipeline
├── audit.py                 # Audit log
├── office_agents.py         # Office file generation
├── web_search.py            # DuckDuckGo search
├── auth.py                  # Multi-user authentication
├── model_hub.py             # HuggingFace model browser
├── telegram_bot.py          # Telegram bot integration
├── backup.py                # Workspace backup
├── skill_eval.py            # Agent skill evaluator
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── install.sh               # Ubuntu one-command installer
├── install-windows.ps1      # Windows installer
├── start-dev.sh             # Dev mode (Linux/Mac)
├── start-dev-windows.ps1    # Dev mode (Windows)
├── index.jsx                # React entry point
├── App.jsx                  # Root component + routing
├── store.js                 # Zustand global state
├── index.css                # Tailwind styles
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── components/
│   ├── Sidebar.jsx
│   └── MessageRenderer.jsx
├── pages/
│   ├── ChatView.jsx         DashboardView.jsx  TasksView.jsx
│   ├── PipelineView.jsx     AppBuilderView.jsx CanvasView.jsx
│   ├── OfficeView.jsx       FilesView.jsx      MemoryView.jsx
│   ├── SchedulerView.jsx    ModelHubView.jsx   CodeReviewView.jsx
│   ├── AuditView.jsx        TelegramView.jsx   BackupView.jsx
│   ├── SettingsView.jsx     SkillsView.jsx     UsersView.jsx
│   ├── PromptsView.jsx      VoiceButton.jsx
└── utils/
    └── api.js
```

---

## 6. Enhancement Roadmap — 10 Phases

All phases are completed in v3.

| # | Phase | Description |
|---|---|---|
| 1 | **Multi-Agent Pipeline** | Orchestrator breaks tasks into phases; Architect, Coder, DevOps run in sequence |
| 2 | **Project Memory** | Persistent project.md; agents read it before every response |
| 3 | **Web Search** | DuckDuckGo, no API key; sources cited in responses |
| 4 | **App Builder** | Full multi-file app generation; built-in preview; zip download |
| 5 | **Visual Canvas** | Node-based drag-and-drop workflow editor; save and reuse |
| 6 | **Voice Output** | Browser TTS; speed/voice controls; hands-free conversation mode |
| 7 | **Code Review** | Structured bug/security/style report; one-click auto-fix with diff |
| 8 | **Scheduled Tasks** | Cron scheduler; task history; output logs |
| 9 | **Multi-User Auth** | Local login; per-user workspace; admin dashboard |
| 10 | **PWA** | Installable on mobile; offline chat; push notifications |

---

## 7. Quick Start Guide

### Install on Oracle Ubuntu VM

```bash
git clone https://github.com/mits1987/KreativOS.git
cd KreativOS
bash install.sh
```

Open `http://YOUR_ORACLE_VM_IP:8000` in any browser.

### Dev Mode (Linux/Mac)

```bash
bash start-dev.sh
# Backend:  http://YOUR_VM_IP:8000
# Frontend: http://YOUR_VM_IP:5173
```

### Dev Mode (Windows)

```powershell
.\start-dev-windows.ps1
```

### Open Oracle Cloud Ports

Networking → VCN → Security Lists → Add Ingress Rules:

| Port | Purpose |
|---|---|
| 8000 | Backend API + Frontend |
| 5173 | Frontend dev server |

Source CIDR: `0.0.0.0/0`

### First Run

1. Open **Model Hub** in the sidebar
2. Install a small model (e.g. `qwen2.5:0.5b` — fastest for testing)
3. Go to **Settings** and select the model
4. Start chatting or run a task

---

## Agents

| Agent | Ralph Loop | Speciality |
|---|---|---|
| Coder | Yes | Write and save code; auto self-critic and QA after task |
| Architect | Yes | System design, architecture, structure |
| DevOps | Yes | Docker, CI/CD, deployment scripts |
| Researcher | No | Deep research and live DuckDuckGo web search |
| Orchestrator | No | Break large tasks into multi-agent pipelines |
| General | No | General-purpose assistant |

---

*KreativOS v3.0 · Built with Claude · June 2026*