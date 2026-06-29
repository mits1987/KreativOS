"""
KreativOS — Audit Log (Phase 0 Fixed)

Fixes applied:
  - threading.Lock() on all file I/O
  - Pagination on tail() and search()
"""
import json
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path


class AuditLog:
    def __init__(self, workspace_dir: Path):
        self.path = workspace_dir / ".audit" / "audit.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def log(
        self,
        action: str,
        detail: str = "",
        user: str = "admin",
        agent: str = "",
        model: str = "",
        extra: dict | None = None,
    ):
        entry = {
            "ts":     datetime.now().isoformat(),
            "action": action,
            "detail": detail[:200],
            "user":   user,
            "agent":  agent,
            "model":  model,
        }
        if extra:
            entry.update(extra)
        with self._lock:
            with self.path.open("a") as f:
                f.write(json.dumps(entry) + "\n")

    def tail(self, n: int = 100, offset: int = 0) -> list:
        with self._lock:
            if not self.path.exists():
                return []
            lines = [l for l in self.path.read_text().strip().split("\n") if l.strip()]

        result = []
        for line in reversed(lines):
            try:
                result.append(json.loads(line))
            except Exception:
                pass

        # Apply pagination
        return result[offset: offset + n]

    def count(self) -> int:
        with self._lock:
            if not self.path.exists():
                return 0
            return sum(1 for l in self.path.read_text().strip().split("\n") if l.strip())

    def search(self, query: str, n: int = 50, offset: int = 0) -> list:
        all_entries = self.tail(1000)
        q = query.lower()
        matches = [
            e for e in all_entries
            if q in e.get("action", "").lower()
            or q in e.get("detail", "").lower()
            or q in e.get("agent", "").lower()
        ]
        return matches[offset: offset + n]

    def stats(self) -> dict:
        entries = self.tail(1000)
        actions = Counter(e["action"] for e in entries)
        agents  = Counter(e["agent"] for e in entries if e.get("agent"))
        return {
            "total_entries": self.count(),
            "top_actions":   dict(actions.most_common(10)),
            "top_agents":    dict(agents.most_common(6)),
            "first_entry":   entries[-1]["ts"] if entries else None,
            "last_entry":    entries[0]["ts"]  if entries else None,
        }
