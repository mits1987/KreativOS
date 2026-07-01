"""
KreativOS — Knowledge / RAG Routes
"""
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import state
from .. import knowledge
from ..auth import get_current_user

router = APIRouter(tags=["knowledge"])


@router.post("/api/knowledge/upload")
async def upload_document(request: Request, current_user: dict = Depends(get_current_user)):
    form = await request.form()
    file = form.get("file")
    if not file:
        raise HTTPException(400, "No file provided")
    content = await file.read()
    suffix = Path(file.filename).suffix or ".txt"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(content)
    tmp.close()
    result = await knowledge.ingest_document(state.WORKSPACE_DIR, Path(tmp.name))
    os.unlink(tmp.name)
    return result


@router.get("/api/knowledge/search")
async def search_knowledge_route(q: str = "", top_k: int = 5, current_user: dict = Depends(get_current_user)):
    return await knowledge.search_knowledge(state.WORKSPACE_DIR, q, top_k)


@router.get("/api/knowledge/documents")
async def list_knowledge_docs(current_user: dict = Depends(get_current_user)):
    return knowledge.list_documents(state.WORKSPACE_DIR)


@router.delete("/api/knowledge/documents/{doc_id}")
async def delete_knowledge_doc(doc_id: str, current_user: dict = Depends(get_current_user)):
    ok = knowledge.delete_document(state.WORKSPACE_DIR, doc_id)
    if not ok:
        raise HTTPException(404, "Document not found")
    return {"ok": True}
