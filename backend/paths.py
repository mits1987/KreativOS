"""
KreativOS — Path Resolution Utility (Phase 1)

All workspace paths must go through here.
Never use relative paths like ./knowledge_base — they break in Docker
where CWD varies.
"""
import os
from pathlib import Path

# ── Single source of truth for WORKSPACE_DIR ──────────────────────────────────
def get_workspace_dir() -> Path:
    """
    Resolve WORKSPACE_DIR from environment.
    Defaults to ~/kreavitos_workspace (not /tmp — survives VM reboot).
    """
    raw = os.getenv("WORKSPACE_DIR", "")
    if raw:
        p = Path(raw).expanduser().resolve()
    else:
        p = Path.home() / "kreavitos_workspace"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_path(subdir: str, workspace_dir: Path | None = None) -> Path:
    """
    Return an absolute path under WORKSPACE_DIR for a named subdirectory.
    Creates the directory if it doesn't exist.
    """
    base = workspace_dir or get_workspace_dir()
    p = base / subdir
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── Named sub-paths ────────────────────────────────────────────────────────────
def knowledge_base_dir(workspace_dir: Path) -> Path:
    return get_path("knowledge_base", workspace_dir)

def plugins_dir(workspace_dir: Path) -> Path:
    return get_path("plugins", workspace_dir)

def logs_dir(workspace_dir: Path) -> Path:
    return get_path("logs", workspace_dir)

def backups_dir(workspace_dir: Path) -> Path:
    return get_path(".backups", workspace_dir)

def tests_dir(workspace_dir: Path) -> Path:
    return get_path("tests", workspace_dir)
