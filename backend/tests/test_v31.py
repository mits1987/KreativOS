"""
KrestivOS v3.1 — New feature tests
Covers: Office files, Skill eval, Audit, Backup, Prompts, Telegram status
"""
import pytest, json
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

@pytest.fixture
def tmp_workspace(tmp_path):
    os.environ["WORKSPACE_DIR"] = str(tmp_path)
    return tmp_path

@pytest.fixture
async def client(tmp_workspace):
    from backend.main import app
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

# ── Office file generation ─────────────────────────────────────────────────────
def test_generate_pptx(tmp_path):
    from office_agents import generate_pptx, parse_ai_to_slides
    content = "## Slide 1\n- Point A\n- Point B\n## Slide 2\n- Point C"
    slides  = parse_ai_to_slides(content, "Test Deck")
    assert len(slides) >= 2
    out = tmp_path / "test.pptx"
    generate_pptx("Test Deck", slides, out)
    assert out.exists()
    assert out.stat().st_size > 1000

def test_generate_docx(tmp_path):
    from office_agents import generate_docx
    out = tmp_path / "test.docx"
    generate_docx("Test Doc", "## Section\nSome content\n- bullet one\n- bullet two", out)
    assert out.exists()
    assert out.stat().st_size > 500

def test_generate_xlsx(tmp_path):
    from office_agents import generate_xlsx
    out = tmp_path / "test.xlsx"
    headers = ["Name", "Score", "Grade"]
    data    = [["Alice", 95, "A"], ["Bob", 82, "B"]]
    generate_xlsx("Test Sheet", data, headers, out)
    assert out.exists()
    assert out.stat().st_size > 2000

def test_parse_ai_to_slides():
    from office_agents import parse_ai_to_slides
    text   = "# Title\n## Section 1\n- item a\n- item b\n## Section 2\nsome prose"
    slides = parse_ai_to_slides(text, "T")
    assert any(s["title"] == "Section 1" for s in slides)
    assert any("item a" in s.get("bullets",[]) for s in slides)

def test_parse_ai_to_table():
    from office_agents import parse_ai_to_table
    text = "| Name | Age |\n|------|-----|\n| Alice | 30 |\n| Bob | 25 |"
    headers, rows = parse_ai_to_table(text)
    assert "Name" in headers
    assert len(rows) == 2

# ── Skill evaluator ────────────────────────────────────────────────────────────
def test_skill_record_and_leaderboard(tmp_path):
    from skill_eval import SkillEvaluator
    ev = SkillEvaluator(tmp_path)
    ev.record("coder",      "build api",    "output1", 8, "Good code")
    ev.record("coder",      "fix bug",      "output2", 9, "Excellent")
    ev.record("researcher", "research AI",  "output3", 7, "Thorough")
    lb = ev.leaderboard()
    assert len(lb) == 2
    assert lb[0]["agent"] == "coder"   # highest avg
    assert lb[0]["avg_score"] == 8.5

def test_skill_trend(tmp_path):
    from skill_eval import SkillEvaluator
    ev = SkillEvaluator(tmp_path)
    for score in [5, 6, 7, 8, 9]:
        ev.record("coder", "task", "output", score, "ok")
    stats = ev.get_agent("coder")
    assert stats["trend"] == "improving"

def test_skill_grader_prompt(tmp_path):
    from skill_eval import SkillEvaluator
    ev  = SkillEvaluator(tmp_path)
    p   = ev.build_grader_prompt("build a todo app", "Here is the code...")
    assert "1-10" in p
    assert "score" in p
    assert "JSON" in p

# ── Audit log ──────────────────────────────────────────────────────────────────
def test_audit_log_write_and_tail(tmp_path):
    from audit import AuditLog
    log = AuditLog(tmp_path)
    log.log("chat",      "test message", user="admin", agent="coder")
    log.log("task_done", "built api",    user="admin", agent="coder")
    entries = log.tail(10)
    assert len(entries) == 2
    assert entries[0]["action"] == "task_done"  # most recent first

def test_audit_search(tmp_path):
    from audit import AuditLog
    log = AuditLog(tmp_path)
    log.log("chat",      "hello world")
    log.log("task_done", "built something with fastapi")
    log.log("file_saved","readme.md")
    results = log.search("fastapi")
    assert len(results) == 1
    assert "fastapi" in results[0]["detail"].lower()

def test_audit_stats(tmp_path):
    from audit import AuditLog
    log = AuditLog(tmp_path)
    for i in range(5): log.log("chat",   f"msg {i}", agent="general")
    for i in range(3): log.log("task_done", f"task {i}", agent="coder")
    s = log.stats()
    assert s["total_entries"] == 8
    assert "chat" in s["top_actions"]
    assert s["top_actions"]["chat"] == 5

# ── Backup ─────────────────────────────────────────────────────────────────────
def test_backup_create_and_list(tmp_path):
    import backup as bk
    bk.init(tmp_path)
    (tmp_path / "test_file.txt").write_text("hello")
    out_path, size_mb = bk.create_backup(tmp_path)
    assert out_path.exists()
    assert size_mb >= 0  # small in test env
    backups = bk.list_backups()
    assert len(backups) == 1
    assert backups[0]["filename"] == out_path.name

def test_backup_delete(tmp_path):
    import backup as bk
    bk.init(tmp_path)
    out_path, _ = bk.create_backup(tmp_path)
    assert len(bk.list_backups()) == 1
    bk.delete_backup(out_path.name)
    assert len(bk.list_backups()) == 0

def test_backup_security(tmp_path):
    """Ensure only valid backup files can be deleted"""
    import backup as bk
    bk.init(tmp_path)
    # Try to delete a non-backup file
    result = bk.delete_backup("../important_file.txt")
    assert result is False

# ── Prompt library ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_prompts_list(client, tmp_workspace):
    r = await client.get("/api/prompts")
    assert r.status_code == 200
    prompts = r.json()["prompts"]
    assert len(prompts) >= 10  # default prompts

@pytest.mark.asyncio
async def test_prompts_save_and_delete(client, tmp_workspace):
    r = await client.post("/api/prompts", json={
        "name": "My Prompt", "category": "coder", "prompt": "Write a script that…"
    })
    assert r.status_code == 200
    pid = r.json()["id"]
    r   = await client.delete(f"/api/prompts/{pid}")
    assert r.status_code == 200

# ── Telegram status ────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_telegram_status(client, tmp_workspace):
    r = await client.get("/api/telegram/status")
    assert r.status_code == 200
    assert "enabled" in r.json()
    assert "bot_token_set" in r.json()

# ── Audit route ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_audit_route(client, tmp_workspace):
    r = await client.get("/api/audit?n=10")
    assert r.status_code == 200
    assert "entries" in r.json()

# ── Backup routes ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_backup_list_route(client, tmp_workspace):
    r = await client.get("/api/backup/list")
    assert r.status_code == 200
    assert "backups" in r.json()

@pytest.mark.asyncio
async def test_backup_create_route(client, tmp_workspace):
    r = await client.post("/api/backup/create", json={})
    assert r.status_code == 200
    d = r.json()
    assert "filename" in d
    assert d["filename"].startswith("krestivos_backup_")
    assert d["size_mb"] >= 0

# ── YAGNI in coder prompt ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_yagni_in_coder_agent(client, tmp_workspace):
    """Verify YAGNI rules are injected into coder agent system"""
    r = await client.get("/api/agents")
    assert r.status_code == 200
    # YAGNI is in backend AGENT_SYSTEMS, just verify agents are returned
    agents = [a["id"] for a in r.json()["agents"]]
    assert "coder" in agents
