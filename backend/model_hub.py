"""
KreativOS Model Hub - HuggingFace GGUF browser + Ollama downloader
"""
import asyncio, json, re
from typing import Optional
import httpx
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/hub", tags=["model_hub"])

HF_API = "https://huggingface.co/api"

# Curated CPU-friendly GGUF models — verified to work with Ollama on CPU
FEATURED_MODELS = [
    {"id": "bartowski/Qwen2.5-7B-Instruct-GGUF",       "name": "Qwen 2.5 7B",        "size": "4.7GB", "ram": "6GB",  "speed": "Fast",   "tag": "Recommended"},
    {"id": "bartowski/Llama-3.2-3B-Instruct-GGUF",     "name": "Llama 3.2 3B",       "size": "2.0GB", "ram": "4GB",  "speed": "Fastest","tag": "Lightweight"},
    {"id": "bartowski/Mistral-7B-Instruct-v0.3-GGUF",  "name": "Mistral 7B",         "size": "4.1GB", "ram": "6GB",  "speed": "Fast",   "tag": "Popular"},
    {"id": "bartowski/gemma-2-2b-it-GGUF",             "name": "Gemma 2 2B",         "size": "1.6GB", "ram": "3GB",  "speed": "Fastest","tag": "Lightweight"},
    {"id": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF","name": "Llama 3.1 8B",       "size": "4.9GB", "ram": "8GB",  "speed": "Medium", "tag": "Capable"},
    {"id": "bartowski/Phi-3.5-mini-instruct-GGUF",     "name": "Phi 3.5 Mini",       "size": "2.2GB", "ram": "4GB",  "speed": "Fast",   "tag": "Microsoft"},
    {"id": "bartowski/DeepSeek-R1-Distill-Qwen-7B-GGUF","name":"DeepSeek R1 7B",     "size": "4.7GB", "ram": "6GB",  "speed": "Fast",   "tag": "Reasoning"},
    {"id": "bartowski/Qwen2.5-Coder-7B-Instruct-GGUF", "name": "Qwen 2.5 Coder 7B", "size": "4.7GB", "ram": "6GB",  "speed": "Fast",   "tag": "Coding"},
    {"id": "bartowski/SmolLM2-1.7B-Instruct-GGUF",     "name": "SmolLM2 1.7B",       "size": "1.0GB", "ram": "2GB",  "speed": "Fastest","tag": "Tiny"},
    {"id": "bartowski/Codestral-22B-v0.1-GGUF",        "name": "Codestral 22B",      "size": "13GB",  "ram": "16GB", "speed": "Slow",   "tag": "Pro Coding"},
]

class PullRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    model_name: str          # ollama model name e.g. "qwen2.5:7b"
    hf_model_id: Optional[str] = None

@router.get("/featured")
async def featured_models():
    return {"models": FEATURED_MODELS}

@router.get("/search")
async def search_hf(q: str = "", limit: int = 12):
    """Search HuggingFace for GGUF models"""
    try:
        params = {
            "search": q if q else "instruct GGUF",
            "filter": "gguf",
            "sort": "downloads",
            "direction": -1,
            "limit": limit,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{HF_API}/models", params=params)
            models = resp.json()
            results = []
            for m in models:
                mid = m.get("modelId", "")
                if not mid:
                    continue
                results.append({
                    "id": mid,
                    "name": mid.split("/")[-1].replace("-GGUF","").replace("-gguf",""),
                    "downloads": m.get("downloads", 0),
                    "likes": m.get("likes", 0),
                    "tags": m.get("tags", [])[:4],
                    "url": f"https://huggingface.co/{mid}",
                })
            return {"results": results, "query": q}
    except Exception as e:
        return {"results": [], "error": str(e)}

@router.get("/ollama-name")
async def suggest_ollama_name(hf_id: str):
    """Convert HuggingFace model ID to ollama pull name"""
    name_map = {
        "Qwen2.5-7B":  "qwen2.5:7b",
        "Qwen2.5-3B":  "qwen2.5:3b",
        "Llama-3.2-3B": "llama3.2:3b",
        "Llama-3.2-1B": "llama3.2:1b",
        "Llama-3.1-8B": "llama3.1:8b",
        "Mistral-7B":   "mistral:7b",
        "gemma-2-2b":   "gemma2:2b",
        "Phi-3.5-mini": "phi3.5:3.8b",
        "DeepSeek-R1-Distill-Qwen-7B": "deepseek-r1:7b",
        "SmolLM2-1.7B": "smollm2:1.7b",
        "Qwen2.5-Coder-7B": "qwen2.5-coder:7b",
    }
    for key, val in name_map.items():
        if key.lower() in hf_id.lower():
            return {"ollama_name": val, "found": True}
    base = hf_id.split("/")[-1].lower()
    base = re.sub(r"-gguf|-instruct|-it|-v[\d.]+", "", base)
    base = re.sub(r"[-_]+", ":", base).strip(":")
    return {"ollama_name": base, "found": False}
