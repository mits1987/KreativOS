import pytest
import asyncio
import os, sys

# Repo root → enables 'from backend import main' and 'import backend.main'
_backend_dir = os.path.dirname(os.path.dirname(__file__))
_repo_root   = os.path.dirname(_backend_dir)
sys.path.insert(0, _repo_root)    # KreativOS/ — for package-style imports
sys.path.insert(0, _backend_dir)  # KreativOS/backend/ — for direct 'import memory' etc.
os.environ["AUTH_REQUIRED"] = "false"


@pytest.fixture
def tmp_workspace(tmp_path):
    os.environ["WORKSPACE_DIR"] = str(tmp_path)
    os.environ["TESTING"] = "1"
    import backup
    backup.init(tmp_path)
    yield tmp_path

@pytest.fixture
async def client(tmp_workspace):
    from backend import main
    main.reinit_workspace()
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        yield c
