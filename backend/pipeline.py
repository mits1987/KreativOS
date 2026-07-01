"""
Phase 1: Multi-Agent Pipeline Orchestrator
Chains agents automatically: Architect → Coder → DevOps
"""
import asyncio, json
from datetime import datetime
from pathlib import Path

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


def _load_user_templates(workspace_dir: Path = None) -> dict:
    """Load user-defined pipeline templates from workspace/pipelines/*.json"""
    if not workspace_dir:
        return {}
    templates_dir = workspace_dir / "pipelines"
    if not templates_dir.exists():
        return {}
    user_templates = {}
    for f in sorted(templates_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if "phases" in data:
                user_templates[f.stem] = data["phases"]
        except (json.JSONDecodeError, KeyError):
            continue
    return user_templates


def get_all_templates(workspace_dir: Path = None) -> dict:
    """Merge built-in and user-defined templates."""
    templates = dict(PIPELINE_TEMPLATES)
    templates.update(_load_user_templates(workspace_dir))
    return templates


def save_user_template(workspace_dir: Path, name: str, phases: list) -> dict:
    """Save a user-defined pipeline template."""
    templates_dir = workspace_dir / "pipelines"
    templates_dir.mkdir(parents=True, exist_ok=True)
    fp = templates_dir / f"{name}.json"
    data = {"name": name, "phases": phases}
    tmp = fp.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(fp)
    return {"status": "ok", "name": name, "phases": len(phases)}


def delete_user_template(workspace_dir: Path, name: str) -> bool:
    fp = workspace_dir / "pipelines" / f"{name}.json"
    if not fp.exists():
        return False
    fp.unlink()
    return True


async def run_pipeline(task: str, template: str, model: str, call_ollama_fn, agent_systems: dict, get_skills_fn, ralph_fn, workspace_dir, track_fn, extract_fn, skip_ralph: bool = False, cancel_event: asyncio.Event | None = None):
    """Async generator — yields SSE-ready event dicts for each pipeline phase."""
    all_templates = get_all_templates(workspace_dir)
    steps   = all_templates.get(template, all_templates.get("full_app", []))
    results = []
    context = f"Original task: {task}\n\n"

    yield {"type": "start", "template": template, "total": len(steps)}

    for step in steps:
        if cancel_event and cancel_event.is_set():
            yield {"type": "cancelled", "message": "Pipeline cancelled by user"}
            return
        agent_id = step["agent"]
        label    = step["label"]
        track_fn("pipeline_step", f"Phase {step['phase']}: {label}")
        yield {"type": "phase_start", "phase": step["phase"], "agent": agent_id, "label": label}

        try:
            system   = agent_systems.get(agent_id, agent_systems["general"])
            skills   = get_skills_fn(agent_id)
            full_sys = system + ("\n\n" + skills if skills else "")
            prompt   = (
                context
                + f"\nYour job for this phase: {label}"
                + "\nPrevious phases gave you this context above. Now complete YOUR phase only."
            )
            output = await call_ollama_fn(model, [{"role": "user", "content": prompt}], full_sys)

            ralph_result = None
            if not skip_ralph and agent_id in ("coder", "architect", "devops"):
                ralph_result = await ralph_fn(model, task, output, agent_id)
                output = ralph_result["output"]

            saved = extract_fn(output)
            phase_result = {
                "phase":       step["phase"],
                "agent":       agent_id,
                "label":       label,
                "output":      output,
                "saved_files": saved,
                "ralph":       ralph_result,
                "timestamp":   datetime.now().isoformat(),
            }
        except Exception as exc:
            phase_result = {
                "phase":       step["phase"],
                "agent":       agent_id,
                "label":       label,
                "error":       str(exc),
                "output":      "",
                "saved_files": [],
                "ralph":       None,
                "timestamp":   datetime.now().isoformat(),
            }

        results.append(phase_result)
        context += f"\n\n--- Phase {step['phase']} ({label}) output ---\n{phase_result.get('output', '')}\n"
        yield {"type": "phase_done", "phase": phase_result}

    yield {"type": "done", "task": task, "template": template, "phases": results, "timestamp": datetime.now().isoformat()}
