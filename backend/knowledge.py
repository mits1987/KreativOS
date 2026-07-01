"""
Local RAG over user documents.
- Upload -> chunk -> embed (Ollama nomic-embed-text) -> store
- search_knowledge tool for orchestrator
- Stdlib + httpx only
"""
import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional

import httpx

OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64

def _get_embeddings(texts: list[str]) -> list[list[float]]:
    try:
        resp = httpx.post(OLLAMA_EMBED_URL, json={"model": EMBED_MODEL, "input": texts}, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data.get("embeddings", [])
    except Exception as e:
        print(f"Embedding error: {e}")
        return []

def _chunk_text(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        if end >= len(text):
            chunks.append(text[start:])
            break
        split_at = text.rfind(". ", start, end)
        if split_at == -1 or split_at < start + CHUNK_SIZE // 2:
            split_at = text.rfind("\n", start, end)
        if split_at == -1 or split_at < start + CHUNK_SIZE // 2:
            split_at = end
        else:
            split_at += 1
        chunks.append(text[start:split_at])
        start = split_at - CHUNK_OVERLAP
    return chunks

def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def _load_index(workspace_dir: Path) -> dict:
    idx_path = workspace_dir / "knowledge" / "index.json"
    if idx_path.exists():
        return json.loads(idx_path.read_text(encoding="utf-8"))
    return {"chunks": [], "documents": {}}

def _save_index(workspace_dir: Path, index: dict):
    idx_path = workspace_dir / "knowledge" / "index.json"
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = idx_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(index, indent=2), encoding="utf-8")
    tmp.replace(idx_path)

def ingest_document(workspace_dir: Path, filepath: Path) -> dict:
    text = filepath.read_text(encoding="utf-8", errors="replace")
    docs_dir = workspace_dir / "knowledge" / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    dest = docs_dir / filepath.name
    shutil.copy2(str(filepath), str(dest))
    chunks = _chunk_text(text)
    if not chunks:
        return {"status": "error", "error": "No text content found", "chunks": 0}
    embeddings = _get_embeddings(chunks)
    if not embeddings:
        return {"status": "error", "error": "Failed to get embeddings from Ollama. Is nomic-embed-text pulled?", "chunks": len(chunks)}
    index = _load_index(workspace_dir)
    doc_id = filepath.name
    index["documents"][doc_id] = {
        "filename": doc_id,
        "path": str(dest),
        "size": len(text),
        "chunks": len(chunks),
        "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%S")
    }
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        index["chunks"].append({
            "id": f"{doc_id}:{i}",
            "doc_id": doc_id,
            "text": chunk,
            "embedding": emb,
            "chunk_index": i
        })
    _save_index(workspace_dir, index)
    return {"status": "ok", "filename": doc_id, "chunks": len(chunks)}

def search_knowledge(workspace_dir: Path, query: str, top_k: int = 5) -> list[dict]:
    index = _load_index(workspace_dir)
    if not index["chunks"]:
        return []
    query_emb = _get_embeddings([query])
    if not query_emb:
        return []
    qv = query_emb[0]

    def cosine_sim(a, b):
        dot = sum(x*y for x, y in zip(a, b))
        na = sum(x*x for x in a) ** 0.5
        nb = sum(x*x for x in b) ** 0.5
        return dot / (na * nb) if na and nb else 0

    scored = [(cosine_sim(qv, c["embedding"]), c) for c in index["chunks"]]
    scored.sort(key=lambda x: -x[0])
    results = []
    for score, chunk in scored[:top_k]:
        results.append({
            "text": chunk["text"],
            "score": round(score, 4),
            "document": chunk["doc_id"],
            "chunk": chunk["chunk_index"]
        })
    return results

def list_documents(workspace_dir: Path) -> list[dict]:
    index = _load_index(workspace_dir)
    return list(index["documents"].values())

def delete_document(workspace_dir: Path, doc_id: str) -> bool:
    index = _load_index(workspace_dir)
    if doc_id not in index["documents"]:
        return False
    del index["documents"][doc_id]
    index["chunks"] = [c for c in index["chunks"] if c["doc_id"] != doc_id]
    _save_index(workspace_dir, index)
    return True
