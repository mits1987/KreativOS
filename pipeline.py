"""
Phase 1: Multi-Agent Pipeline Orchestrator
Chains agents automatically: Architect → Coder → DevOps
"""
import asyncio, json
from datetime import datetime
from typing import AsyncGenerator

PIPELINE_TEMPLATES = {
    "full_app": [
        {"phase": 1, "agent": "architect",    "label": "Design Architecture"},
        {"phase": 2, "agent": "coder",        "label": "Write Code"},
        {"phase": 3, "agent": "devops",       "label": "Write Deployment"},
    ],
    "research_build": [
        {"phase": 1, "agent": "researcher",   "label": "Research Topic"},
        {"phase": 2, "agent": "architect",    "label": "Design Solution"},
        {"phase": 3, "agent": "coder",        "label": "Implement"},
    ],
    "code_only": [
        {"phase": 1, "agent": "coder",        "label": "Write Code"},
        {"phase": 2, "agent": "devops",       "label": "Package & Deploy"},
    ],
    "research_only": [
        {"phase": 1, "agent": "researcher",   "label": "Research"},
        {"phase": 2, "agent": "orchestrator", "label": "Summarise & Plan"},
    ],
}

async def run_pipeline(task: str, template: str, model: str, call_ollama_fn, agent_systems: dict, get_skills_fn, ralph_fn, workspace_dir, track_fn, extract_fn):
    steps  = PIPELINE_TEMPLATES.get(template, PIPELINE_TEMPLATES["full_app"])
    results = []
    context = f"Original task: {task}\n\n"

    for step in steps:
        agent_id = step["agent"]
        label    = step["label"]
        track_fn("pipeline_step", f"Phase {step['phase']}: {label}")

        system = agent_systems.get(agent_id, agent_systems["general"])
        skills = get_skills_fn(agent_id)
        full_sys = system + ("\n\n" + skills if skills else "")

        prompt = context + f"\nYour job for this phase: {label}\nPrevious phases gave you this context above. Now complete YOUR phase only."
        messages = [{"role": "user", "content": prompt}]

        output = await call_ollama_fn(model, messages, full_sys)

        # Ralph loop for code-producing agents
        ralph_result = None
        if agent_id in ("coder", "architect", "devops"):
            ralph_result = await ralph_fn(model, task, output, agent_id)
            output = ralph_result["output"]

        saved = extract_fn(output)
        results.append({
            "phase":       step["phase"],
            "agent":       agent_id,
            "label":       label,
            "output":      output,
            "saved_files": saved,
            "ralph":       ralph_result,
            "timestamp":   datetime.now().isoformat(),
        })
        context += f"\n\n--- Phase {step['phase']} ({label}) output ---\n{output}\n"

    return {"task": task, "template": template, "phases": results, "timestamp": datetime.now().isoformat()}
