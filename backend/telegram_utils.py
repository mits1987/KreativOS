"""KreativOS — Telegram artifact delivery (fire-and-forget)."""
import os
from pathlib import Path

import httpx


async def send_telegram_artifact(file_path: str, caption: str = ""):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return

    path = Path(file_path)
    if not path.exists():
        return

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            data = {"chat_id": chat_id, "caption": caption}
            files = {"document": (path.name, path.read_bytes(), "application/octet-stream")}
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data=data, files=files
            )
            resp.raise_for_status()
    except Exception:
        pass
