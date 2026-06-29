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



