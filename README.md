# ðŸ§  KreativOS v3 â€” Agentic Operating System

A self-hosted, browser-based agentic OS powered by your local Ollama models.
**v2 adds: Dashboard Â· Ralph Loop Â· 24 Agent Skills Â· Voice Input**

## âœ¨ What's New in v2

| Feature | Description |
|---|---|
| ðŸ“Š **Dashboard** | Live stats: messages, tasks, Ralph Loop runs, files, agent usage, activity feed |
| ðŸ”„ **Ralph Loop** | Auto self-critic + QA review after every Coder/Architect/DevOps task, up to 3 fix iterations |
| ðŸ“š **24 Agent Skills** | Domain expertise injected into each agent: coding standards, security, testing, DevOps, docs |
| ðŸŽ™ï¸ **Voice Input** | Click mic in chat â€” speak your prompt (Chrome/Edge, no API key needed) |

## ðŸš€ Install on Oracle VM (one command)

```bash
git clone https://github.com/mits1987/KreativOS.git
cd KreativOS
bash install.sh
```

Then open `http://YOUR_VM_IP:3000` from any browser.

## âš¡ Dev mode (no Docker)

```bash
bash start-dev.sh
# Open http://YOUR_VM_IP:5173
```

## ðŸ¤– Agents

| Agent | Ralph Loop | Skills injected |
|---|---|---|
| ðŸ’» Coder | âœ… Yes | coding, testing, debugging, performance |
| ðŸ—ï¸ Architect | âœ… Yes | architecture, devops, documentation |
| âš™ï¸ DevOps | âœ… Yes | devops, security, performance |
| ðŸ” Researcher | âŒ No | documentation |
| ðŸŽ¯ Orchestrator | âŒ No | architecture |
| ðŸ¤– General | âŒ No | â€” |

## ðŸ”„ How Ralph Loop Works

1. You run a task with Coder/Architect/DevOps agent
2. Agent produces initial output
3. **Self-Critic** reviews: correctness, completeness, quality, runnability
4. **QA Tester** reviews: requirement coverage, bugs, readability
5. If either fails â†’ fix prompt sent â†’ agent re-runs
6. Repeat up to 3 times â†’ deliver final output
7. Dashboard shows all loop stats

## ðŸ“Š Dashboard

Live view of:
- System status (Ollama connection, model, uptime)
- Total messages, tasks, files, code executions
- Ralph Loop runs + auto-fixes applied
- Agent usage chart
- Live activity feed (last 20 events)

## ðŸ”’ Open Oracle Cloud Ports

Networking â†’ VCN â†’ Security Lists â†’ Add Ingress Rules:
- Port **3000** (frontend)
- Port **8000** (backend)
- Source CIDR: `0.0.0.0/0`

