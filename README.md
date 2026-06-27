# KreativOS

Agentic OS — multi-agent chat, autonomous task runner, file workspace, voice I/O, and Telegram bot, all running locally via Ollama.

## Quick start

```bash
pip install -r requirements.txt
npm install && npm run build
uvicorn main:app --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000.

## Dev (hot-reload)

```bash
# Linux/Mac
./start-dev.sh

# Windows
.\start-dev-windows.ps1
```

## Docker

```bash
docker compose up
```
