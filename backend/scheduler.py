"""
KreativOS — Task Scheduler (Phase 0 Fixed)

Fixes applied:
  - threading.Lock() on all read-modify-write cycles
"""
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path


class TaskScheduler:
    def __init__(self, workspace_dir: Path):
        self.path = workspace_dir / ".scheduler" / "tasks.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    # ── Thread-safe I/O ────────────────────────────────────────────────────────
    def _load(self) -> list:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text())
        except Exception:
            return []

    def _save(self, tasks: list):
        self.path.write_text(json.dumps(tasks, indent=2))

    # ── Public API ─────────────────────────────────────────────────────────────
    def list_tasks(self) -> list:
        with self._lock:
            return self._load()

    def add_task(
        self,
        name: str,
        task_prompt: str,
        agent: str,
        model: str,
        interval: str = "daily",
        hour: int = 9,
    ) -> dict:
        with self._lock:
            tasks = self._load()
            t = {
                "id":          f"sched_{datetime.now().timestamp():.0f}",
                "name":        name,
                "prompt":      task_prompt,
                "agent":       agent,
                "model":       model,
                "interval":    interval,
                "hour":        hour,
                "enabled":     True,
                "last_run":    None,
                "next_run":    self._calc_next(interval, hour),
                "run_count":   0,
                "last_output": None,
                "created":     datetime.now().isoformat(),
            }
            tasks.append(t)
            self._save(tasks)
            return t

    def _calc_next(self, interval: str, hour: int) -> str:
        now = datetime.now()
        if interval == "hourly":
            return (now + timedelta(hours=1)).isoformat()
        if interval == "weekly":
            return (now + timedelta(days=7)).replace(
                hour=hour, minute=0, second=0, microsecond=0
            ).isoformat()
        # daily
        next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run.isoformat()

    def delete_task(self, task_id: str):
        with self._lock:
            tasks = [t for t in self._load() if t["id"] != task_id]
            self._save(tasks)

    def toggle_task(self, task_id: str) -> bool:
        with self._lock:
            tasks = self._load()
            for t in tasks:
                if t["id"] == task_id:
                    t["enabled"] = not t["enabled"]
                    self._save(tasks)
                    return t["enabled"]
        return False

    def get_due_tasks(self) -> list:
        with self._lock:
            now = datetime.now().isoformat()
            return [t for t in self._load() if t["enabled"] and t.get("next_run", "") <= now]

    def mark_ran(self, task_id: str, output: str):
        with self._lock:
            tasks = self._load()
            for t in tasks:
                if t["id"] == task_id:
                    t["last_run"]    = datetime.now().isoformat()
                    t["next_run"]    = self._calc_next(t["interval"], t["hour"])
                    t["run_count"]  += 1
                    t["last_output"] = output[:500]
                    break
            self._save(tasks)
