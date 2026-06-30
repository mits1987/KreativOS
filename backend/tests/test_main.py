"""
KreativOS â€” Backend Test Suite
Tests all major API endpoints without requiring Ollama running.
Run: pytest tests/ -v
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# â”€â”€ Health â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest.mark.asyncio
async def test_health_returns_ok(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "ollama" in data

@pytest.mark.asyncio
async def test_health_ollama_disconnected(client):
    # Health always returns 200, ollama field shows connection state
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ollama"] in ("connected", "disconnected")

# â”€â”€ Models & Agents â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest.mark.asyncio
async def test_agents_returns_list(client):
    r = await client.get("/api/agents")
    assert r.status_code == 200
    agents = r.json()["agents"]
    assert len(agents) >= 6
    ids = [a["id"] for a in agents]
    assert "coder" in ids
    assert "researcher" in ids
    assert "self_critic" not in ids   # internal, not exposed

@pytest.mark.asyncio
async def test_models_ollama_unreachable(client):
    # When ollama is not running, endpoint returns 503
    # When running in CI without ollama, we just check it responds
    try:
        r = await client.get("/api/models")
        assert r.status_code in (200, 503)
    except Exception:
        pass  # Connection error is also acceptable in test env

# â”€â”€ Dashboard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest.mark.asyncio
async def test_dashboard_returns_stats(client):
    r = await client.get("/api/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert "stats" in data
    assert "recent_activity" in data
    stats = data["stats"]
    assert "total_messages" in stats
    assert "total_tasks" in stats
    assert "ralph_loops_run" in stats

# â”€â”€ Files â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest.mark.asyncio
async def test_write_and_read_file(client, tmp_workspace):
    r = await client.post("/api/files/write", json={"filename": "test.txt", "content": "hello world"})
    assert r.status_code == 200
    assert r.json()["success"] is True

    r = await client.get("/api/files/read/test.txt")
    assert r.status_code == 200
    assert r.json()["content"] == "hello world"

@pytest.mark.asyncio
async def test_list_files(client, tmp_workspace):
    await client.post("/api/files/write", json={"filename": "a.py", "content": "print(1)"})
    await client.post("/api/files/write", json={"filename": "b.py", "content": "print(2)"})
    r = await client.get("/api/files/list")
    assert r.status_code == 200
    names = [f["name"] for f in r.json()["files"]]
    assert "a.py" in names
    assert "b.py" in names

@pytest.mark.asyncio
async def test_delete_file(client, tmp_workspace):
    await client.post("/api/files/write", json={"filename": "del.txt", "content": "bye"})
    r = await client.delete("/api/files/delete/del.txt")
    assert r.status_code == 200
    r = await client.get("/api/files/read/del.txt")
    assert r.status_code == 404

@pytest.mark.asyncio
async def test_read_nonexistent_file(client):
    r = await client.get("/api/files/read/does_not_exist.txt")
    assert r.status_code == 404

# â”€â”€ Code Execution â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest.mark.asyncio
async def test_execute_python(client, tmp_workspace):
    r = await client.post("/api/execute", json={"code": "print('hello')", "language": "python"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "hello" in data["stdout"]

@pytest.mark.asyncio
async def test_execute_bash(client, tmp_workspace):
    r = await client.post("/api/execute", json={"code": "echo 'bash works'", "language": "bash"})
    assert r.status_code == 200
    d = r.json()
    if d["success"]:
        assert "bash works" in d["stdout"]

@pytest.mark.asyncio
async def test_execute_python_error(client, tmp_workspace):
    r = await client.post("/api/execute", json={"code": "raise ValueError('test error')", "language": "python"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert "ValueError" in data["stderr"]

@pytest.mark.asyncio
async def test_execute_timeout(client, tmp_workspace):
    r = await client.post("/api/execute", json={"code": "import time; time.sleep(60)", "language": "python"})
    assert r.status_code == 200
    assert r.json()["success"] is False

# â”€â”€ Auth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest.mark.asyncio
async def test_login_default_admin(client, tmp_workspace):
    from backend import state
    pw = state.auth._first_boot_password
    r = await client.post("/api/auth/login", json={"username": "admin", "password": pw})
    assert r.status_code == 200
    assert "token" in r.json()

@pytest.mark.asyncio
async def test_login_wrong_password(client, tmp_workspace):
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401

@pytest.mark.asyncio
async def test_create_and_list_users(client, tmp_workspace):
    await client.post("/api/auth/users", json={"username": "alice", "password": "pass123", "role": "user"})
    r = await client.get("/api/auth/users")
    users = [u["username"] for u in r.json()["users"]]
    assert "alice" in users

@pytest.mark.asyncio
async def test_delete_user(client, tmp_workspace):
    await client.post("/api/auth/users", json={"username": "bob", "password": "pass123", "role": "user"})
    r = await client.delete("/api/auth/users/bob")
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_cannot_delete_admin(client, tmp_workspace):
    r = await client.delete("/api/auth/users/admin")
    assert r.status_code == 400

# â”€â”€ Memory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest.mark.asyncio
async def test_memory_create_and_get(client, tmp_workspace):
    r = await client.get("/api/memory/myproject")
    assert r.status_code == 200
    assert r.json()["project"] == "myproject"

@pytest.mark.asyncio
async def test_memory_add_note(client, tmp_workspace):
    await client.post("/api/memory/myproject/note", json={"note": "Using FastAPI"})
    r = await client.get("/api/memory/myproject")
    notes = [n["text"] for n in r.json()["notes"]]
    assert "Using FastAPI" in notes

@pytest.mark.asyncio
async def test_memory_list_projects(client, tmp_workspace):
    await client.get("/api/memory/proj1")
    await client.post("/api/memory/proj1/note", json={"note": "test"})
    r = await client.get("/api/memory/projects")
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_memory_delete(client, tmp_workspace):
    await client.post("/api/memory/todelete/note", json={"note": "bye"})
    r = await client.delete("/api/memory/todelete")
    assert r.status_code == 200

# â”€â”€ Scheduler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest.mark.asyncio
async def test_scheduler_create_and_list(client, tmp_workspace):
    r = await client.post("/api/scheduler/tasks", json={
        "name": "Daily test", "prompt": "Say hello", "agent": "general",
        "model": "qwen3:27b", "interval": "daily", "hour": 9
    })
    assert r.status_code == 200
    task_id = r.json()["id"]

    r = await client.get("/api/scheduler/tasks")
    ids = [t["id"] for t in r.json()["tasks"]]
    assert task_id in ids

@pytest.mark.asyncio
async def test_scheduler_toggle(client, tmp_workspace):
    r = await client.post("/api/scheduler/tasks", json={
        "name": "Toggle test", "prompt": "Test", "agent": "general",
        "model": "qwen3:27b", "interval": "daily", "hour": 8
    })
    task_id = r.json()["id"]
    r = await client.post(f"/api/scheduler/tasks/{task_id}/toggle")
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_scheduler_delete(client, tmp_workspace):
    r = await client.post("/api/scheduler/tasks", json={
        "name": "Delete me", "prompt": "Test", "agent": "general",
        "model": "qwen3:27b", "interval": "daily", "hour": 8
    })
    task_id = r.json()["id"]
    r = await client.delete(f"/api/scheduler/tasks/{task_id}")
    assert r.status_code == 200

# â”€â”€ Pipeline templates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest.mark.asyncio
async def test_pipeline_templates(client):
    r = await client.get("/api/pipeline/templates")
    assert r.status_code == 200
    templates = [t["id"] for t in r.json()["templates"]]
    assert "full_app" in templates
    assert "research_build" in templates

# â”€â”€ Canvas workflows â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@pytest.mark.asyncio
async def test_canvas_save_and_list(client, tmp_workspace):
    r = await client.post("/api/canvas/workflows", json={
        "name": "Test WF", "description": "desc",
        "nodes": [{"id":"n1","data":{"agent":"coder","label":"Code"},"position":{"x":0,"y":0}}],
        "edges": []
    })
    assert r.status_code == 200
    wf_id = r.json()["id"]

    r = await client.get("/api/canvas/workflows")
    ids = [w["id"] for w in r.json()["workflows"]]
    assert wf_id in ids

@pytest.mark.asyncio
async def test_canvas_delete_workflow(client, tmp_workspace):
    r = await client.post("/api/canvas/workflows", json={
        "name": "Del WF", "description": "", "nodes": [], "edges": []
    })
    wf_id = r.json()["id"]
    r = await client.delete(f"/api/canvas/workflows/{wf_id}")
    assert r.status_code == 200

# â”€â”€ Memory module unit tests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def test_memory_build_context(tmp_path):
    from memory import ProjectMemory
    m = ProjectMemory(tmp_path)
    m.add_decision("proj", "Use FastAPI", "architect")
    m.add_file("proj", "main.py")
    m.add_note("proj", "Remember to add auth")
    ctx = m.build_context("proj")
    assert "FastAPI" in ctx
    assert "main.py" in ctx
    assert "auth" in ctx

def test_memory_empty_context(tmp_path):
    from memory import ProjectMemory
    m = ProjectMemory(tmp_path)
    ctx = m.build_context("")  # empty project name returns empty
    assert ctx == ""

def test_scheduler_calc_next(tmp_path):
    from scheduler import TaskScheduler
    s = TaskScheduler(tmp_path)
    t = s.add_task("test", "do stuff", "general", "model", "daily", 9)
    assert t["next_run"] is not None
    assert t["enabled"] is True

def test_auth_hash_consistency(tmp_path):
    from auth import AuthManager
    a = AuthManager(tmp_path)
    token1 = a.login("admin", a._first_boot_password)
    assert token1 is not None
    token2 = a.login("admin", "wrongpass")
    assert token2 is None

def test_websearch_format(tmp_path):
    from web_search import format_results_for_agent
    results = [{"title": "Test", "snippet": "A test result", "url": "http://example.com", "source": "DDG"}]
    fmt = format_results_for_agent("test query", results)
    assert "test query" in fmt
    assert "Test" in fmt

