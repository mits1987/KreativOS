import pytest
import asyncio
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
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
