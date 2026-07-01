"""
KreativOS — Conversation Routes (SQLite-backed CRUD + FTS5 search)
"""
from fastapi import APIRouter, Depends, HTTPException

from .. import state
from .. import conversations
from ..auth import get_current_user

router = APIRouter(tags=["conversations"])


@router.get("/api/conversations")
async def list_convs(limit: int = 50, offset: int = 0, current_user: dict = Depends(get_current_user)):
    return conversations.list_conversations(state.WORKSPACE_DIR, limit, offset)


@router.get("/api/conversations/search")
async def search_convs(q: str = "", limit: int = 20, current_user: dict = Depends(get_current_user)):
    if not q:
        return []
    return conversations.search_conversations(state.WORKSPACE_DIR, q, limit)


@router.get("/api/conversations/{conv_id}")
async def get_conv(conv_id: str, current_user: dict = Depends(get_current_user)):
    conv = conversations.get_conversation(state.WORKSPACE_DIR, conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.post("/api/conversations")
async def create_conv(data: dict, current_user: dict = Depends(get_current_user)):
    return conversations.create_conversation(
        state.WORKSPACE_DIR,
        title=data.get("title", "New Chat"),
        model=data.get("model", "")
    )


@router.post("/api/conversations/{conv_id}/messages")
async def add_msg(conv_id: str, data: dict, current_user: dict = Depends(get_current_user)):
    return conversations.add_message(
        state.WORKSPACE_DIR, conv_id,
        data.get("role", "user"),
        data.get("content", "")
    )


@router.delete("/api/conversations/{conv_id}")
async def delete_conv(conv_id: str, current_user: dict = Depends(get_current_user)):
    ok = conversations.delete_conversation(state.WORKSPACE_DIR, conv_id)
    if not ok:
        raise HTTPException(404, "Conversation not found")
    return {"ok": True}
