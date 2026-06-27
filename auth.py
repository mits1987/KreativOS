"""
Phase 9: Auth - simple local multi-user support
Stores users in a JSON file, bcrypt passwords
"""
import json, bcrypt, secrets, time
from datetime import datetime
from pathlib import Path
from fastapi import HTTPException, Header
from typing import Optional

class AuthManager:
    def __init__(self, workspace_dir: Path):
        self.path = workspace_dir / ".auth" / "users.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tokens: dict[str, dict] = {}
        self._ensure_admin()

    def _hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def _verify(self, password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text())

    def _save(self, users: dict):
        self.path.write_text(json.dumps(users, indent=2))

    def _ensure_admin(self):
        users = self._load()
        if not users:
            users["admin"] = {
                "password": self._hash("admin123"),
                "role": "admin",
                "created": datetime.now().isoformat(),
            }
            self._save(users)

    def login(self, username: str, password: str) -> Optional[str]:
        users = self._load()
        u = users.get(username)
        if not u or not self._verify(password, u["password"]):
            return None
        token = secrets.token_hex(32)
        self.tokens[token] = {
            "user":    username,
            "role":    u.get("role", "user"),
            "expires": time.time() + 86400 * 7,
        }
        return token

    def verify(self, token: str) -> Optional[dict]:
        t = self.tokens.get(token)
        if not t or t["expires"] < time.time():
            self.tokens.pop(token, None)
            return None
        return t

    def create_user(self, username: str, password: str, role: str = "user") -> bool:
        users = self._load()
        if username in users:
            return False
        users[username] = {
            "password": self._hash(password),
            "role":     role,
            "created":  datetime.now().isoformat(),
        }
        self._save(users)
        return True

    def list_users(self) -> list:
        users = self._load()
        return [{"username": k, "role": v["role"], "created": v["created"]} for k, v in users.items()]

    def delete_user(self, username: str) -> bool:
        if username == "admin":
            return False
        users = self._load()
        if username not in users:
            return False
        del users[username]
        self._save(users)
        return True

    def change_password(self, username: str, new_password: str):
        users = self._load()
        if username in users:
            users[username]["password"] = self._hash(new_password)
            self._save(users)
