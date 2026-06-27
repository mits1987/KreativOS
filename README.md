# KreativOS — Agentic Operating System

A self-hosted, browser-based Agentic OS that runs 100% locally on a CPU-only Oracle VM using Ollama.
**v3 ships all 10 phases: Pipeline · Memory · Web Search · App Builder · Canvas · Voice · Code Review · Scheduler · Auth · PWA**

## What's New in v3

| Feature | Description |
|---|---|
| 🔗 **Multi-Agent Pipeline** | Orchestrator breaks big tasks into phases, auto-assigns Architect → Coder → DevOps |
| 🧠 **Project Memory** | Persistent context file per project — agents never forget earlier decisions |
| 🌐 **Web Search** | Researcher uses DuckDuckGo live search, cites sources in responses |
| 🏗️ **App Builder** | Generate full multi-file apps with preview + zip download |
| 🎨 **Visual Canvas** | Drag-and-drop node editor for custom agent workflows |
| 🔊 **Voice Output** | Browser TTS speaks agent responses; full voice conversation mode |
| 🔍 **Code Review** | Upload any file → structured bug/security/style report + auto-fix |
| ⏰ **Scheduled Tasks** | Cron-style scheduler visible in Dashboard with full output logs |
| 👥 **Multi-User Auth** | Login page, per-user workspaces, admin panel |
| 📱 **PWA** | Installable on mobile, offline history, push notifications |
| 📬 **Telegram Bot** | Control KreativOS from Telegram: run tasks, check status |
| 📄 **Office Suite** | Generate .docx, .xlsx, .pptx directly from agent output |

## Install on Oracle VM (one command)

```bash
git clone https://github.com/mits1987/KreativOS.git
cd KreativOS
bash install.sh
```

Then open `http://YOUR_VM_IP:8000` from any browser.

## Dev Mode (no Docker)

```bash
bash start-dev.sh
# Backend:  http://YOUR_VM_IP:8000
# Frontend: http://YOUR_VM_IP:5173
```

## Windows Dev Mode

```powershell
.\start-dev-windows.ps1
```

## Agents

| Agent | Ralph Loop | Speciality |
|---|---|---|
| 💻 Coder | ✅ Yes | Write & save code, auto-fix with Ralph Loop |
| 🏗️ Architect | ✅ Yes | System design, architecture, structure |
| ⚙️ DevOps | ✅ Yes | Docker, CI/CD, deployment scripts |
| 🔍 Researcher | ❌ No | Deep research + live web search |
| 🎯 Orchestrator | ❌ No | Break tasks into multi-agent pipelines |

## How Ralph Loop Works

1. You run a task with Coder / Architect / DevOps agent
2. Agent produces initial output
3. **Self-Critic** reviews: correctness, completeness, quality, runnability
4. **QA Tester** reviews: requirement coverage, bugs, readability
5. If either fails → fix prompt sent → agent re-runs
6. Repeat up to 3 times → deliver final output

## Open Oracle Cloud Ports

Networking → VCN → Security Lists → Add Ingress Rules:
- Port **8000** (backend + frontend served by FastAPI)
- Source CIDR: `0.0.0.0/0`

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python · FastAPI · Uvicorn |
| AI Engine | Ollama (local LLM) |
| Frontend | React 18 · Vite · Tailwind CSS · Zustand |
| Database | File-based workspace (JSON + files) |
| Deployment | Docker · docker-compose or bare metal |

---
KreativOS v1.0
