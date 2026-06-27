"""
KrestivOS v3.1 — Skill Evaluation System (from agentic-os inspiration)
Grades every task output and tracks skill scores over time.
"""
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict

class SkillEvaluator:
    def __init__(self, workspace_dir: Path):
        self.path = workspace_dir / ".skill_eval" / "scores.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text())

    def _save(self, data: dict):
        self.path.write_text(json.dumps(data, indent=2))

    def record(self, agent: str, task: str, output: str, score: int, feedback: str):
        """Record a skill evaluation result (score 1-10)"""
        data = self._load()
        if agent not in data:
            data[agent] = {"runs": [], "avg_score": 0}
        entry = {
            "task":      task[:120],
            "score":     score,
            "feedback":  feedback[:300],
            "timestamp": datetime.now().isoformat(),
            "output_len": len(output),
        }
        data[agent]["runs"].append(entry)
        data[agent]["runs"] = data[agent]["runs"][-50:]   # keep last 50
        scores = [r["score"] for r in data[agent]["runs"]]
        data[agent]["avg_score"] = round(sum(scores) / len(scores), 1)
        data[agent]["total_runs"] = len(data[agent]["runs"])
        data[agent]["best_score"] = max(scores)
        data[agent]["trend"] = self._trend(scores[-5:])
        self._save(data)

    def _trend(self, last5: list) -> str:
        if len(last5) < 2: return "stable"
        diff = last5[-1] - last5[0]
        return "improving" if diff > 0.5 else "declining" if diff < -0.5 else "stable"

    def get_all(self) -> dict:
        return self._load()

    def get_agent(self, agent: str) -> dict:
        return self._load().get(agent, {"runs": [], "avg_score": 0})

    def leaderboard(self) -> list:
        data = self._load()
        lb = []
        for agent, info in data.items():
            lb.append({
                "agent":      agent,
                "avg_score":  info.get("avg_score", 0),
                "total_runs": info.get("total_runs", 0),
                "best_score": info.get("best_score", 0),
                "trend":      info.get("trend", "stable"),
            })
        return sorted(lb, key=lambda x: x["avg_score"], reverse=True)

    def build_grader_prompt(self, task: str, output: str) -> str:
        return f"""Grade the following AI agent output on a scale of 1-10.

Task given: {task[:400]}

Output produced:
{output[:1500]}

Evaluate on:
- Correctness (does it actually solve the task?)
- Completeness (nothing missing?)
- Code quality (if code: runs without errors, good style?)
- Clarity (well explained?)

Respond ONLY in this exact JSON format (no other text):
{{"score": <1-10>, "feedback": "<one sentence reason>"}}"""
