"""
KreativOS — File Permission Manager

Three states: allow_once, allow_session, deny.
Workspace paths are always implicitly allowed.
"""
import os
import re
import threading
import uuid
from pathlib import Path

WORKSPACE_DIR = None

_lock = threading.Lock()

_allowed_session = set()
_allowed_once = set()
_pending = []
_denied = set()

def init(workspace_dir):
    global WORKSPACE_DIR
    WORKSPACE_DIR = workspace_dir

def _norm(p):
    return str(Path(p).resolve())

def is_allowed(path):
    n = _norm(path)
    if WORKSPACE_DIR and n.startswith(_norm(WORKSPACE_DIR)):
        return True
    if n in _allowed_session:
        return True
    if n in _allowed_once:
        _allowed_once.discard(n)
        return True
    return False

def request_access(path, operation="read"):
    with _lock:
        n = _norm(path)
        if is_allowed(n):
            return None
        if n in _denied:
            return {"status": "denied", "path": n, "operation": operation}
        req_id = uuid.uuid4().hex[:12]
        entry = {"req_id": req_id, "path": n, "operation": operation}
        _pending.append(entry)
        return {"status": "pending", **entry}

def respond(req_id, decision):
    with _lock:
        for i, r in enumerate(_pending):
            if r["req_id"] == req_id:
                if decision == "allow_session":
                    _allowed_session.add(r["path"])
                elif decision == "allow_once":
                    _allowed_once.add(r["path"])
                elif decision == "deny":
                    _denied.add(r["path"])
                _pending.pop(i)
                return True
        return False

def pending_list():
    with _lock:
        return list(_pending)

_CODE_PATH_RE = re.compile(
    r'(?:open|Path|read_text|write_text|unlink|rename|shutil\.\w+|os\.\w+)\s*'
    r'\(?\s*[\'"]([~\'"][^\'"]*(?:\\|/)[^\'"]*|/[^\'"]+|'
    r'[A-Za-z]:\\(?:[^\\\'"]+\\)*[^\\\'"]*)[\'"]'
)

def check_code_paths(code, workspace_dir):
    ws_norm = _norm(workspace_dir)
    found = []
    for match in _CODE_PATH_RE.finditer(code):
        raw = match.group(1).strip("\"'")
        try:
            p = str(Path(raw).expanduser().resolve())
        except Exception:
            continue
        if p.startswith(ws_norm):
            continue
        if any(skip in p for skip in ["/tmp/", "\\Temp\\", "/dev/", "/proc/"]):
            continue
        if p not in found:
            found.append(p)
    return found
