"""
KreativOS — Project Memory (Phase 0 Fixed)

Fixes applied:
  - threading.Lock() on all read-modify-write cycles (Phase 0, critical)
  - All paths resolve from workspace_dir, never from CWD (Phase 2 prep)
"""
import json
import threading
from datetime import datetime
from pathlib import Path


class ProjectMemory:
    def __init__(self, workspace_dir: Path):
        self.dir = workspace_dir / ".memory"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, project: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in project)
        return self.dir / f"{safe}.json"

    def _default(self, project: str) -> dict:
        now = datetime.now().isoformat()
        return {
            "project":   project,
            "decisions": [],
            "files":     [],
            "notes":     [],
            "created":   now,
            "updated":   now,
        }

    # ── Thread-safe I/O ────────────────────────────────────────────────────────
    def _load(self, project: str) -> dict:
        p = self._path(project)
        if not p.exists():
            return self._default(project)
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return self._default(project)

    def _save(self, project: str, data: dict):
        data["updated"] = datetime.now().isoformat()
        p = self._path(project)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(p)

    # ── Public API (all operations hold the lock) ──────────────────────────────
    def list_projects(self, limit: int = 50, offset: int = 0) -> list[str]:
        all_projects = sorted(p.stem for p in self.dir.glob("*.json"))
        return all_projects[offset: offset + limit]

    def count_projects(self) -> int:
        return sum(1 for _ in self.dir.glob("*.json"))

    def get(self, project: str) -> dict:
        with self._lock:
            return self._load(project)

    def save(self, project: str, data: dict):
        with self._lock:
            self._save(project, data)

    def add_decision(self, project: str, decision: str, agent: str):
        with self._lock:
            m = self._load(project)
            m["decisions"].append({
                "text":  decision,
                "agent": agent,
                "time":  datetime.now().isoformat(),
            })
            m["decisions"] = m["decisions"][-50:]
            self._save(project, m)

    def add_note(self, project: str, note: str):
        with self._lock:
            m = self._load(project)
            m["notes"].append({"text": note, "time": datetime.now().isoformat()})
            self._save(project, m)

    def add_file(self, project: str, filename: str):
        with self._lock:
            m = self._load(project)
            if filename not in m["files"]:
                m["files"].append(filename)
            self._save(project, m)

    def build_context(self, project: str) -> str:
        if not project:
            return ""
        with self._lock:
            m = self._load(project)
        parts = [f"## Project Memory: {project}"]
        if m["decisions"]:
            parts.append("### Key Decisions Made:")
            for d in m["decisions"][-10:]:
                parts.append(f"- [{d['agent']}] {d['text']}")
        if m["files"]:
            parts.append(f"### Files created so far: {', '.join(m['files'][-20:])}")
        if m["notes"]:
            parts.append("### Notes:")
            for n in m["notes"][-5:]:
                parts.append(f"- {n['text']}")
        return "\n".join(parts)

    def delete(self, project: str):
        with self._lock:
            p = self._path(project)
            if p.exists():
                p.unlink()
