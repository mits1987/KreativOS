"""
Phase 2: Project Memory — persistent context per project
"""
import json
from datetime import datetime
from pathlib import Path

class ProjectMemory:
    def __init__(self, workspace_dir: Path):
        self.dir = workspace_dir / ".memory"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, project: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in project)
        return self.dir / f"{safe}.json"

    def list_projects(self):
        return [p.stem for p in self.dir.glob("*.json")]

    def get(self, project: str) -> dict:
        p = self._path(project)
        if not p.exists():
            return {"project": project, "decisions": [], "files": [], "notes": [], "created": datetime.now().isoformat(), "updated": datetime.now().isoformat()}
        return json.loads(p.read_text())

    def save(self, project: str, data: dict):
        data["updated"] = datetime.now().isoformat()
        self._path(project).write_text(json.dumps(data, indent=2))

    def add_decision(self, project: str, decision: str, agent: str):
        m = self.get(project)
        m["decisions"].append({"text": decision, "agent": agent, "time": datetime.now().isoformat()})
        m["decisions"] = m["decisions"][-50:]  # keep last 50
        self.save(project, m)

    def add_note(self, project: str, note: str):
        m = self.get(project)
        m["notes"].append({"text": note, "time": datetime.now().isoformat()})
        self.save(project, m)

    def add_file(self, project: str, filename: str):
        m = self.get(project)
        if filename not in m["files"]:
            m["files"].append(filename)
        self.save(project, m)

    def build_context(self, project: str) -> str:
        if not project:
            return ""
        m = self.get(project)
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
        p = self._path(project)
        if p.exists():
            p.unlink()
