"""
KreativOS — Auth Manager (Phase 0 Fixed)

Two-part fix applied:
  1. get_current_user() now raises HTTP 401 instead of returning admin by default.
  2. All sensitive routes must inject Depends(get_current_user).
  3. Expired token cleanup background task added.
  4. AUTH_REQUIRED=false still works by skipping the middleware entirely.
"""
import json
import logging
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import bcrypt
from fastapi import Depends, Header, HTTPException

logger = logging.getLogger(__name__)


class AuthManager:
    def __init__(self, workspace_dir: Path):
        self.path = workspace_dir / ".auth" / "users.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # In-memory token store: token -> {user, role, expires}
        self.tokens: dict[str, dict] = {}
        self._ensure_admin()

    # ── Password helpers ───────────────────────────────────────────────────────
    def _hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def _verify(self, password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())

    # ── Persistence ────────────────────────────────────────────────────────────
    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text())
        except Exception:
            return {}

    def _save(self, users: dict):
        self.path.write_text(json.dumps(users, indent=2))

    def _ensure_admin(self):
        users = self._load()
        if not users:
            users["admin"] = {
                "password": self._hash("admin123"),
                "role":     "admin",
                "created":  datetime.now().isoformat(),
            }
            self._save(users)

    # ── Token management ───────────────────────────────────────────────────────
    def login(self, username: str, password: str) -> Optional[str]:
        users = self._load()
        u = users.get(username)
        if not u or not self._verify(password, u["password"]):
            return None
        token = secrets.token_hex(32)
        self.tokens[token] = {
            "user":    username,
            "role":    u.get("role", "user"),
            "expires": time.time() + 86400 * 7,  # 7 days
        }
        return token

    def verify(self, token: str) -> Optional[dict]:
        t = self.tokens.get(token)
        if not t:
            return None
        if t["expires"] < time.time():
            self.tokens.pop(token, None)
            return None
        return t

    def cleanup_expired_tokens(self):
        """Remove expired tokens from memory. Called by background task."""
        expired = [t for t, v in self.tokens.items() if v["expires"] < time.time()]
        for t in expired:
            self.tokens.pop(t, None)
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired auth tokens")

    # ── User management ────────────────────────────────────────────────────────
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
        return [
            {"username": k, "role": v["role"], "created": v["created"]}
            for k, v in users.items()
        ]

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


# ── Module-level singleton (set by main.py after init) ────────────────────────
_auth_manager: Optional[AuthManager] = None


def set_auth_manager(manager: AuthManager):
    global _auth_manager
    _auth_manager = manager


# ── FastAPI dependency ─────────────────────────────────────────────────────────
def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    FastAPI dependency for protected routes.

    FIXED (Phase 0):
    - No longer returns admin by default on missing token.
    - Raises HTTP 401 if token is missing or invalid.
    - Inject with: current_user = Depends(get_current_user)

    For AUTH_REQUIRED=false (single-user mode):
    - Do NOT mount the auth middleware.
    - Protected routes still require a valid token if auth is enabled.
    - For single-user setups, login once and store the token in the frontend.
    """
    if _auth_manager is None:
        # Auth not initialised yet (startup race) — deny by default
        raise HTTPException(status_code=503, detail="Auth service not ready")

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Bearer token missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = _auth_manager.verify(token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """
    Like get_current_user but returns None instead of raising.
    Used for endpoints that work both authenticated and unauthenticated.
    """
    if not authorization or _auth_manager is None:
        return None
    token = authorization.removeprefix("Bearer ").strip()
    return _auth_manager.verify(token) if token else None
