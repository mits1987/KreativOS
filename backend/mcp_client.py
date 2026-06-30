"""KreativOS — MCP client + server config."""
import json
from urllib.parse import urlparse
import httpx
from .paths import get_workspace_dir

_CONFIG = get_workspace_dir() / "mcp_servers.json"

# ponytail: shared client to avoid new connection per call
_HTTP = httpx.AsyncClient(timeout=15)

_DEFAULTS = [
    {
        "name": "open-design",
        "url": "http://localhost:7456/mcp",
        "description": "Open Design — prototypes, decks, HyperFrames (start with: od mcp install claude)",
        "enabled": True,
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


def _validate_mcp_url(url: str):
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise ValueError("MCP URL must be http or https")
    host = p.hostname or ""
    blocked = {"169.254.169.254", "metadata.google.internal"}
    if host in blocked or host.startswith("169.254."):
        raise ValueError("Blocked host")


async def _rpc(url: str, method: str, params: dict) -> dict:
    _validate_mcp_url(url)
    try:
        r = await _HTTP.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        r.raise_for_status()
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        raise ConnectionError(f"MCP server unreachable: {e}") from e
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
