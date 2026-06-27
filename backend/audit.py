"""
KreativOS — Audit Trail (from agentic-os inspiration)
Logs every significant action to a structured JSONL file.
"""
import json
from datetime import datetime
from pathlib import Path

class AuditLog:
    def __init__(self, workspace_dir: Path):
        self.path = workspace_dir / ".audit" / "audit.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, action: str, detail: str = "", user: str = "admin",
            agent: str = "", model: str = "", extra: dict = None):
        entry = {
            "ts":     datetime.now().isoformat(),
            "action": action,
            "detail": detail[:200],
            "user":   user,
            "agent":  agent,
            "model":  model,
        }
        if extra: entry.update(extra)
        with self.path.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def tail(self, n: int = 100) -> list:
        if not self.path.exists(): return []
        lines = self.path.read_text().strip().split("\n")
        lines = [l for l in lines if l.strip()]
        recent = lines[-n:]
        result = []
        for l in reversed(recent):
            try: result.append(json.loads(l))
            except: pass
        return result

    def search(self, query: str, n: int = 50) -> list:
        all_entries = self.tail(500)
        q = query.lower()
        return [e for e in all_entries
                if q in e.get("action","").lower()
                or q in e.get("detail","").lower()
                or q in e.get("agent","").lower()][:n]

    def stats(self) -> dict:
        entries = self.tail(1000)
        from collections import Counter
        actions = Counter(e["action"] for e in entries)
        agents  = Counter(e["agent"]  for e in entries if e.get("agent"))
        return {
            "total_entries":  len(entries),
            "top_actions":    dict(actions.most_common(10)),
            "top_agents":     dict(agents.most_common(6)),
            "first_entry":    entries[-1]["ts"] if entries else None,
            "last_entry":     entries[0]["ts"]  if entries else None,
        }
