"""
KreativOS — Sandboxed Code Execution (Phase 0 Fix)
Replaces bare subprocess.run with a low-privilege, resource-limited wrapper.

VM setup (one-time, run as root):
    sudo useradd -r -s /bin/false -M sandbox_user
    sudo chmod 755 /path/to/workspace  # sandbox_user needs read access

This module is the single sandbox implementation reused by:
  - /api/execute  (this file)
  - Phase 6B Plugin System
  - Phase 6C Test Runner
"""
import asyncio
import logging
import os
import pwd
import resource
import signal
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
SANDBOX_USER      = "sandbox_user"
DEFAULT_TIMEOUT   = 30          # seconds
MAX_OUTPUT_BYTES  = 1_000_000   # 1MB stdout/stderr cap
MAX_MEMORY_BYTES  = 256 * 1024 * 1024  # 256MB virtual memory limit
SAFE_PATH         = "/usr/bin:/bin"

# Language → command mapping
LANG_COMMANDS = {
    "python":     ["python3"],
    "python3":    ["python3"],
    "bash":       ["bash"],
    "sh":         ["bash"],
    "javascript": ["node"],
    "js":         ["node"],
    "node":       ["node"],
}

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
    """Return (uid, gid) of sandbox_user, or (None, None) if not available."""
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
    """Called in the child process (preexec_fn) to apply resource limits."""
    try:
        # CPU time: 25 seconds (slightly less than wall-clock timeout)
        resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
        # Virtual memory
        resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_BYTES, MAX_MEMORY_BYTES))
        # Max file size: 10MB
        resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
        # Max open files
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        # No new processes (prevents forkbombs)
        resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    except Exception as e:
        logger.warning(f"Could not set resource limits: {e}")


def run_sandboxed(
    cmd: list[str],
    cwd: str,
    timeout: int = DEFAULT_TIMEOUT,
    env_extra: Optional[dict] = None,
) -> dict:
    """
    Run a command in a sandboxed subprocess.

    Returns:
        {stdout, stderr, success, returncode, error?}
    """
    uid, gid = _get_sandbox_uid_gid()

    safe_env = {
        "HOME":   "/tmp",
        "PATH":   SAFE_PATH,
        "TMPDIR": "/tmp",
        "LANG":   "en_US.UTF-8",
    }
    if env_extra:
        safe_env.update(env_extra)

    kwargs: dict = {
        "capture_output": True,
        "text":           True,
        "timeout":        timeout,
        "cwd":            cwd,
        "env":            safe_env,
        "start_new_session": True,   # new process group for clean kill
        "preexec_fn":     _set_resource_limits,
    }

    if uid is not None and gid is not None:
        kwargs["user"]  = uid
        kwargs["group"] = gid

    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **{k: v for k, v in kwargs.items()
               if k not in ("capture_output", "timeout")},
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Kill the entire process group, not just the parent
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                proc.kill()
            proc.communicate()
            return {
                "stdout":     "",
                "stderr":     "",
                "success":    False,
                "returncode": -1,
                "error":      f"Execution timed out after {timeout} seconds",
            }

        # Truncate oversized output
        stdout = stdout[:MAX_OUTPUT_BYTES]
        stderr = stderr[:MAX_OUTPUT_BYTES]

        return {
            "stdout":     stdout,
            "stderr":     stderr,
            "success":    proc.returncode == 0,
            "returncode": proc.returncode,
        }

    except Exception as e:
        if proc:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass
        return {
            "stdout":     "",
            "stderr":     "",
            "success":    False,
            "returncode": -1,
            "error":      str(e),
        }


def run_code_sandboxed(code: str, language: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    Write code to a temp file and execute it sandboxed.
    Used by /api/execute.
    """
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

    with tempfile.TemporaryDirectory(prefix="kreavitos_exec_") as tmpdir:
        code_file = os.path.join(tmpdir, f"code{ext}")
        with open(code_file, "w") as f:
            f.write(code)
        # Make readable by sandbox_user
        os.chmod(code_file, 0o644)
        os.chmod(tmpdir, 0o755)

        return run_sandboxed(cmd + [code_file], cwd=tmpdir, timeout=timeout)
