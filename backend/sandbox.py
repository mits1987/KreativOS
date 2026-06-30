"""
KreativOS — Sandboxed Code Execution

Cross-platform sandbox that gracefully degrades on platforms without
Unix user switching or resource limits.

Platform-specific behaviour:
  Linux:   Runs as sandbox_user with setrlimit CPU/VM/files/process limits
  Windows: Runs as current user without resource limits (same isolation level
           as the main server — no better, no worse)

VM setup (one-time, Linux only):
    sudo useradd -r -s /bin/false -M sandbox_user
    sudo chmod 755 /path/to/workspace
"""
import asyncio
import logging
import os
import platform
import signal
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Platform detection ─────────────────────────────────────────────────────────
IS_LINUX  = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"

# ── Unix-only imports (graceful fallback) ───────────────────────────────────────
if IS_LINUX:
    import pwd
    import resource
else:
    pwd      = None
    resource = None

# ── Constants ──────────────────────────────────────────────────────────────────
SANDBOX_USER      = "sandbox_user"
DEFAULT_TIMEOUT   = 30          # seconds
MAX_OUTPUT_BYTES  = 1_000_000   # 1MB stdout/stderr cap
MAX_MEMORY_BYTES  = 256 * 1024 * 1024  # 256MB virtual memory limit (Linux only)

# Language → command mapping
_LANG_CMDS = {
    "python":     [sys.executable],
    "python3":    [sys.executable],
    "bash":       ["bash"] if IS_LINUX else None,
    "sh":         ["bash"] if IS_LINUX else None,
    "javascript": ["node"],
    "js":         ["node"],
    "node":       ["node"],
}
LANG_COMMANDS  = {k: v for k, v in _LANG_CMDS.items() if v is not None}
LANG_EXTENSIONS = {
    "python":     ".py",
    "python3":    ".py",
    "bash":       ".sh",
    "sh":         ".sh",
    "javascript": ".js",
    "js":         ".js",
    "node":       ".js",
}


def _get_sandbox_uid_gid() -> tuple[Optional[int], Optional[int]]:
    """Return (uid, gid) of sandbox_user, or (None, None) on Windows / missing user."""
    if not IS_LINUX or pwd is None:
        return None, None
    try:
        pw = pwd.getpwnam(SANDBOX_USER)
        return pw.pw_uid, pw.pw_gid
    except KeyError:
        logger.warning(
            "sandbox_user does not exist — running with server privileges. "
            "Create it with: sudo useradd -r -s /bin/false -M sandbox_user"
        )
        return None, None


def _set_resource_limits():
    """Called in child process (preexec_fn) — no-op on Windows."""
    if resource is None:
        return
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
        resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_BYTES, MAX_MEMORY_BYTES))
        resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    except Exception as e:
        logger.warning(f"Could not set resource limits: {e}")


def _kill_process_group(proc):
    """Kill the entire process group — Windows-safe fallback."""
    if IS_LINUX:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            return
        except ProcessLookupError:
            pass
    proc.kill()


def run_sandboxed(
    cmd: list[str],
    cwd: str,
    timeout: int = DEFAULT_TIMEOUT,
    env_extra: Optional[dict] = None,
) -> dict:
    """Run a command in a sandboxed subprocess.

    Returns {stdout, stderr, success, returncode, error?}
    """
    uid, gid = _get_sandbox_uid_gid()

    safe_env = {
        "PATH":           os.environ.get("PATH", ""),
        "TMP":            tempfile.gettempdir(),
        "PYTHONHASHSEED": "0",  # ponytail: Python 3.10 rc2 subprocess fails without it on Windows
    }
    if IS_LINUX:
        safe_env["HOME"]   = "/tmp"
        safe_env["TMPDIR"] = "/tmp"
        safe_env["LANG"]   = "en_US.UTF-8"
    if env_extra:
        safe_env.update(env_extra)

    popen_kwargs: dict = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text":   True,
        "cwd":    cwd,
        "env":    safe_env,
    }

    if IS_LINUX:
        popen_kwargs["start_new_session"] = True
        popen_kwargs["preexec_fn"] = _set_resource_limits
        if uid is not None and gid is not None:
            popen_kwargs["user"]  = uid
            popen_kwargs["group"] = gid
    elif IS_WINDOWS:
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    proc = None
    try:
        proc = subprocess.Popen(cmd, **popen_kwargs)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_group(proc)
            proc.communicate()
            return {
                "stdout":     "",
                "stderr":     "",
                "success":    False,
                "returncode": -1,
                "error":      f"Execution timed out after {timeout} seconds",
            }

        stdout = (stdout or "")[:MAX_OUTPUT_BYTES]
        stderr = (stderr or "")[:MAX_OUTPUT_BYTES]

        return {
            "stdout":     stdout,
            "stderr":     stderr,
            "success":    proc.returncode == 0,
            "returncode": proc.returncode,
        }

    except Exception as e:
        if proc:
            _kill_process_group(proc)
        return {
            "stdout":     "",
            "stderr":     "",
            "success":    False,
            "returncode": -1,
            "error":      str(e),
        }


def run_code_sandboxed(code: str, language: str, timeout: int = DEFAULT_TIMEOUT, workspace_dir: Optional[str] = None) -> dict:
    """Write code to a temp file and execute it sandboxed."""
    if IS_WINDOWS:
        logger.warning("Code execution on Windows has no sandbox isolation — runs as server process")
    language = language.lower()
    cmd = LANG_COMMANDS.get(language)
    ext = LANG_EXTENSIONS.get(language, ".txt")

    if not cmd:
        return {
            "stdout":  "",
            "stderr":  f"Unsupported language: {language}",
            "success": False,
            "returncode": -1,
        }

    if workspace_dir:
        from . import permissions as perms
        ext_paths = perms.check_code_paths(code, Path(workspace_dir))
        if ext_paths:
            return {
                "stdout": "", "stderr": "",
                "success": False, "returncode": -1,
                "error": f"File permission required for: {ext_paths[0]}",
                "permission_required": True,
                "paths": ext_paths,
            }

    with tempfile.TemporaryDirectory(prefix="kreavitos_exec_") as tmpdir:
        code_file = os.path.join(tmpdir, f"code{ext}")
        with open(code_file, "w") as f:
            f.write(code)

        return run_sandboxed(cmd + [code_file], cwd=tmpdir, timeout=timeout)
