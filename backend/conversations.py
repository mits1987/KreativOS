"""
Conversation persistence via SQLite.
Stdlib only — no ORM dependency.
"""
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_NAME = "kreativos.db"

def _get_db(workspace_dir: Path) -> sqlite3.Connection:
    db_path = workspace_dir / DB_NAME
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db(workspace_dir: Path):
    conn = _get_db(workspace_dir)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT 'New Chat',
            model TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conv_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conv_id, id);
        -- Full-text search
        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(content, content='messages', content_rowid='id');
        CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
            INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
        END;
        CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
        END;
    """)
    conn.commit()
    conn.close()

def list_conversations(workspace_dir: Path, limit: int = 50, offset: int = 0) -> list[dict]:
    conn = _get_db(workspace_dir)
    rows = conn.execute(
        "SELECT id, title, model, created_at, updated_at FROM conversations ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_conversation(workspace_dir: Path, conv_id: str) -> Optional[dict]:
    conn = _get_db(workspace_dir)
    row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    if not row:
        conn.close()
        return None
    conv = dict(row)
    msgs = conn.execute(
        "SELECT role, content FROM messages WHERE conv_id = ? ORDER BY id", (conv_id,)
    ).fetchall()
    conn.close()
    conv["messages"] = [dict(m) for m in msgs]
    return conv

def create_conversation(workspace_dir: Path, title: str = "New Chat", model: str = "") -> dict:
    conn = _get_db(workspace_dir)
    cid = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO conversations (id, title, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (cid, title, model, now, now)
    )
    conn.commit()
    conn.close()
    return {"id": cid, "title": title, "model": model, "messages": [], "created_at": now, "updated_at": now}

def add_message(workspace_dir: Path, conv_id: str, role: str, content: str) -> dict:
    conn = _get_db(workspace_dir)
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO messages (conv_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (conv_id, role, content, now)
    )
    conn.execute("UPDATE conversations SET updated_at = ?, title = COALESCE(NULLIF(title, 'New Chat'), ?) WHERE id = ?",
                 (now, content[:80] if role == 'user' else '', conv_id))
    conn.commit()
    conn.close()
    return {"role": role, "content": content, "created_at": now}

def delete_conversation(workspace_dir: Path, conv_id: str) -> bool:
    conn = _get_db(workspace_dir)
    conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    affected = conn.total_changes
    conn.commit()
    conn.close()
    return affected > 0

def search_conversations(workspace_dir: Path, query: str, limit: int = 20) -> list[dict]:
    conn = _get_db(workspace_dir)
    rows = conn.execute(
        """SELECT DISTINCT c.id, c.title, c.updated_at, snippet(messages_fts, 1, '<b>', '</b>', '...', 32) as preview
           FROM messages_fts
           JOIN messages m ON messages_fts.rowid = m.id
           JOIN conversations c ON m.conv_id = c.id
           WHERE messages_fts MATCH ?
           ORDER BY c.updated_at DESC LIMIT ?""",
        (query, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
