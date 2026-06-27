"""
KreativOS — Backup & Restore (from agentic-os inspiration)
One-click tar.gz backup of the entire workspace.
"""
import tarfile, json, shutil
from datetime import datetime
from pathlib import Path

BACKUP_DIR = None   # set at init time

def init(workspace_dir: Path):
    global BACKUP_DIR
    BACKUP_DIR = workspace_dir / ".backups"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def create_backup(workspace_dir: Path) -> Path:
    """Create a timestamped tar.gz of the workspace"""
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"kreavitos_backup_{ts}.tar.gz"
    out_path = BACKUP_DIR / out_name

    # Write manifest
    manifest = {
        "created":   datetime.now().isoformat(),
        "version":   "3.1",
        "workspace": str(workspace_dir),
    }
    manifest_path = workspace_dir / ".backup_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    with tarfile.open(str(out_path), "w:gz") as tar:
        # Exclude node_modules, __pycache__, and old backups
        def exclude(tarinfo):
            for skip in ["node_modules", "__pycache__", ".backups", ".git"]:
                if skip in tarinfo.name:
                    return None
            return tarinfo
        tar.add(str(workspace_dir), arcname="workspace", filter=exclude)

    manifest_path.unlink(missing_ok=True)
    size_mb = round(out_path.stat().st_size / 1024 / 1024, 2)
    return out_path, size_mb

def list_backups() -> list:
    if not BACKUP_DIR or not BACKUP_DIR.exists(): return []
    backups = []
    for f in sorted(BACKUP_DIR.glob("kreavitos_backup_*.tar.gz"), reverse=True):
        backups.append({
            "filename": f.name,
            "size_mb":  round(f.stat().st_size / 1024 / 1024, 2),
            "created":  datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            "path":     str(f),
        })
    return backups

def delete_backup(filename: str) -> bool:
    p = BACKUP_DIR / filename
    if p.exists() and p.name.startswith("kreavitos_backup_"):
        p.unlink(); return True
    return False

def restore_backup(filename: str, workspace_dir: Path) -> bool:
    """Restore workspace from a backup (overwrites current)"""
    p = BACKUP_DIR / filename
    if not p.exists(): return False
    # Clear workspace (except backups dir)
    for item in workspace_dir.iterdir():
        if item.name == ".backups": continue
        if item.is_dir():  shutil.rmtree(item)
        else:              item.unlink()
    # Extract
    with tarfile.open(str(p), "r:gz") as tar:
        tar.extractall(str(workspace_dir.parent))
    return True
