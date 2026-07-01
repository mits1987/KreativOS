"""Lightweight GitHub API client. No PyGithub dependency — uses httpx directly."""

import base64
import httpx
import os

GITHUB_BASE = "https://api.github.com"

def _get_headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"} if token else {}

async def list_repos() -> list:
    if not os.environ.get("GITHUB_TOKEN", ""):
        return []
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{GITHUB_BASE}/user/repos?per_page=50&sort=updated", headers=_get_headers())
        r.raise_for_status()
        return [{"name": repo["name"], "full_name": repo["full_name"], "url": repo["html_url"]} for repo in r.json()]

async def create_issue(owner: str, repo: str, title: str, body: str = "", labels: list = None) -> dict:
    if not os.environ.get("GITHUB_TOKEN", ""):
        return {"error": "GITHUB_TOKEN not set"}
    async with httpx.AsyncClient() as c:
        data = {"title": title, "body": body}
        if labels:
            data["labels"] = labels
        r = await c.post(f"{GITHUB_BASE}/repos/{owner}/{repo}/issues", json=data, headers=_get_headers())
        r.raise_for_status()
        j = r.json()
        return {"number": j["number"], "url": j["html_url"], "title": j["title"]}

async def commit_file(owner: str, repo: str, path: str, content: str, message: str, branch: str = "main") -> dict:
    if not os.environ.get("GITHUB_TOKEN", ""):
        return {"error": "GITHUB_TOKEN not set"}
    async with httpx.AsyncClient() as c:
        existing_sha = None
        get_r = await c.get(f"{GITHUB_BASE}/repos/{owner}/{repo}/contents/{path}?ref={branch}", headers=_get_headers())
        if get_r.status_code == 200:
            existing_sha = get_r.json()["sha"]
        data = {"message": message, "content": base64.b64encode(content.encode()).decode(), "branch": branch}
        if existing_sha:
            data["sha"] = existing_sha
        r = await c.put(f"{GITHUB_BASE}/repos/{owner}/{repo}/contents/{path}", json=data, headers=_get_headers())
        r.raise_for_status()
        j = r.json()
        return {"commit": j["commit"]["sha"], "url": j["content"]["html_url"] if "content" in j else j["commit"]["html_url"]}
