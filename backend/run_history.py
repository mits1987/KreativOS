"""Run history persistence — lightweight sqlite3 storage for task run records."""

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

_db_lock = threading.Lock()

def _get_db_path():
    from .state import WORKSPACE_DIR
    db_path = Path(WORKSPACE_DIR) / ".kreativ" / "run_history.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path

def _init_db(db):
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            task_id TEXT,
            conv_id TEXT,
            agent_name TEXT,
            workflow_name TEXT,
            status TEXT,
            started_at TEXT,
            finished_at TEXT,
            duration_ms INTEGER,
            files_generated TEXT,
            error TEXT,
            token_usage TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_runs_task_id ON runs(task_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_runs_conv_id ON runs(conv_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at DESC)")

def _get_connection():
    db = sqlite3.connect(str(_get_db_path()))
    db.row_factory = sqlite3.Row
    _init_db(db)
    return db

def record_run_start(run_id: str, task_id: str = "", conv_id: str = "", agent_name: str = "", workflow_name: str = ""):
    with _db_lock:
        db = _get_connection()
        try:
            db.execute(
                "INSERT OR REPLACE INTO runs (id, task_id, conv_id, agent_name, workflow_name, status, started_at) "
                "VALUES (?, ?, ?, ?, ?, 'running', ?)",
                (run_id, task_id, conv_id, agent_name, workflow_name, datetime.utcnow().isoformat())
            )
            db.commit()
        finally:
            db.close()

def record_run_end(run_id: str, status: str, error: str = "", files_generated: list = None, token_usage: dict = None):
    with _db_lock:
        db = _get_connection()
        try:
            started = db.execute("SELECT started_at FROM runs WHERE id=?", (run_id,)).fetchone()
            duration_ms = None
            if started:
                try:
                    start = datetime.fromisoformat(started[0])
                    duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
                except Exception:
                    pass
            db.execute(
                "UPDATE runs SET status=?, finished_at=?, duration_ms=?, error=?, files_generated=?, token_usage=? WHERE id=?",
                (status, datetime.utcnow().isoformat(), duration_ms,
                 error, json.dumps(files_generated or []), json.dumps(token_usage or {}), run_id)
            )
            db.commit()
        finally:
            db.close()

def get_recent_runs(limit: int = 50, conv_id: str = None):
    db = _get_connection()
    try:
        if conv_id:
            rows = db.execute(
                "SELECT * FROM runs WHERE conv_id=? ORDER BY started_at DESC LIMIT ?", (conv_id, limit)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()

def get_run_stats():
    db = _get_connection()
    try:
        total = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        successful = db.execute("SELECT COUNT(*) FROM runs WHERE status='completed'").fetchone()[0]
        failed = db.execute("SELECT COUNT(*) FROM runs WHERE status='failed'").fetchone()[0]
        avg_duration = db.execute("SELECT AVG(duration_ms) FROM runs WHERE duration_ms IS NOT NULL").fetchone()[0]
        return {
            "total_runs": total,
            "successful": successful,
            "failed": failed,
            "avg_duration_ms": round(avg_duration) if avg_duration else 0
        }
    finally:
        db.close()
