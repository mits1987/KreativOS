import pytest
import asyncio
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Required for pytest-asyncio
pytest_plugins = ('anyio',)

@pytest.fixture
def tmp_workspace(tmp_path):
    os.environ["WORKSPACE_DIR"] = str(tmp_path)
    # re-init backup module with new path
    import backup
    backup.init(tmp_path)
    yield tmp_path

@pytest.fixture
async def client(tmp_workspace):
    # Force reimport with new WORKSPACE_DIR
    import importlib, main as m
    importlib.reload(m)
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=m.app), base_url="http://test") as c:
        yield c
