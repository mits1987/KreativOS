"""
KreativOS — GitHub Routes
"""
from fastapi import APIRouter, Depends

from .. import github_client as gh
from ..auth import get_current_user

router = APIRouter(tags=["github"])


@router.get("/api/github/repos")
async def github_list_repos(current_user: dict = Depends(get_current_user)):
    repos = await gh.list_repos()
    return repos


@router.post("/api/github/issues")
async def github_create_issue(data: dict, current_user: dict = Depends(get_current_user)):
    result = await gh.create_issue(data["owner"], data["repo"], data["title"], data.get("body", ""), data.get("labels"))
    return result


@router.post("/api/github/commit")
async def github_commit_file(data: dict, current_user: dict = Depends(get_current_user)):
    result = await gh.commit_file(data["owner"], data["repo"], data["path"], data["content"], data["message"], data.get("branch", "main"))
    return result
