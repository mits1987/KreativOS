"""KreativOS — MCP client + server config."""
import json
import httpx
from .paths import get_workspace_dir

_CONFIG = get_workspace_dir() / "mcp_servers.json"

_DEFAULTS = [
    {
        "name": "open-design",
        "url": "http://localhost:7456/mcp",
        "description": "Open Design — prototypes, decks, HyperFrames (start with: od mcp install claude)",
        "enabled": False,
    }
]


def load_servers() -> list:
    if _CONFIG.exists():
        return json.loads(_CONFIG.read_text())
    return list(_DEFAULTS)


def save_servers(servers: list):
    _CONFIG.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG.write_text(json.dumps(servers, indent=2))


def _get_url(name: str) -> str:
    server = next((s for s in load_servers() if s["name"] == name), None)
    if not server:
        raise ValueError(f"MCP server '{name}' not configured")
    return server["url"]


async def _rpc(url: str, method: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", "MCP error"))
    return data.get("result", {})


async def list_tools(server_url: str) -> list:
    result = await _rpc(server_url, "tools/list", {})
    return result.get("tools", [])


async def call_tool(server_name: str, tool_name: str, args: dict) -> dict:
    url = _get_url(server_name)
    return await _rpc(url, "tools/call", {"name": tool_name, "arguments": args})
