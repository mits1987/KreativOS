"""
KreativOS — Skill Evaluator (Phase 0 Fixed)

Fixes applied:
  - threading.Lock() on all read-modify-write cycles
"""
import json
import threading
from datetime import datetime
from pathlib import Path


class SkillEvaluator:
    def __init__(self, workspace_dir: Path):
        self.path = workspace_dir / ".skill_eval" / "scores.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text())
        except Exception:
            return {}

    def _save(self, data: dict):
        self.path.write_text(json.dumps(data, indent=2))

    def record(self, agent: str, task: str, output: str, score: int, feedback: str):
        with self._lock:
            data = self._load()
            if agent not in data:
                data[agent] = {"runs": [], "avg_score": 0}
            entry = {
                "task":       task[:120],
                "score":      max(1, min(10, int(score))),
                "feedback":   feedback[:300],
                "timestamp":  datetime.now().isoformat(),
                "output_len": len(output),
            }
            data[agent]["runs"].append(entry)
            data[agent]["runs"] = data[agent]["runs"][-50:]
            scores = [r["score"] for r in data[agent]["runs"]]
            data[agent]["avg_score"]  = round(sum(scores) / len(scores), 1)
            data[agent]["total_runs"] = len(data[agent]["runs"])
            data[agent]["best_score"] = max(scores)
            data[agent]["trend"]      = self._trend(scores[-5:])
            self._save(data)

    def _trend(self, last5: list) -> str:
        if len(last5) < 2:
            return "stable"
        diff = last5[-1] - last5[0]
        return "improving" if diff > 0.5 else "declining" if diff < -0.5 else "stable"

    def get_all(self) -> dict:
        with self._lock:
            return self._load()

    def get_agent(self, agent: str) -> dict:
        with self._lock:
            return self._load().get(agent, {"runs": [], "avg_score": 0})

    def leaderboard(self) -> list:
        with self._lock:
            data = self._load()
        lb = [
            {
                "agent":      agent,
                "avg_score":  info.get("avg_score", 0),
                "total_runs": info.get("total_runs", 0),
                "best_score": info.get("best_score", 0),
                "trend":      info.get("trend", "stable"),
            }
            for agent, info in data.items()
        ]
        return sorted(lb, key=lambda x: x["avg_score"], reverse=True)

    def build_grader_prompt(self, task: str, output: str) -> str:
        return (
            f"Grade the following AI agent output on a scale of 1-10.\n\n"
            f"Task given: {task[:400]}\n\n"
            f"Output produced:\n{output[:1500]}\n\n"
            "Evaluate on:\n"
            "- Correctness (does it actually solve the task?)\n"
            "- Completeness (nothing missing?)\n"
            "- Code quality (if code: runs without errors, good style?)\n"
            "- Clarity (well explained?)\n\n"
            'Respond ONLY in this exact JSON format (no other text):\n'
            '{"score": <1-10>, "feedback": "<one sentence reason>"}'
        )
