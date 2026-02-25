"""Ollama management routes — status check, model listing, model pulling."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth import get_current_user
from app.routes.settings import get_config

router = APIRouter()

OLLAMA_MODELS = [
    {"value": "qwen2.5:3b", "label": "Qwen 2.5 3B (2 GB)", "size_gb": 2.0},
    {"value": "qwen2.5:7b", "label": "Qwen 2.5 7B (4.7 GB)", "size_gb": 4.7},
    {"value": "qwen2.5:14b", "label": "Qwen 2.5 14B (9 GB)", "size_gb": 9.0},
]


class PullRequest(BaseModel):
    name: str = "qwen2.5:7b"


@router.get("/status")
async def ollama_status(_user: dict = Depends(get_current_user)):
    """Check if Ollama is running and list installed models."""
    cfg = get_config()
    base_url = cfg.ollama_base_url
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            installed = [m["name"] for m in data.get("models", [])]
            return {
                "running": True,
                "installed_models": installed,
                "available_models": OLLAMA_MODELS,
            }
    except Exception as e:
        return {
            "running": False,
            "installed_models": [],
            "available_models": OLLAMA_MODELS,
            "error": str(e),
        }


@router.post("/pull")
async def pull_model(
    body: PullRequest,
    _user: dict = Depends(get_current_user),
):
    """Pull/download an Ollama model. Streams JSON progress lines."""
    model_name = body.name
    cfg = get_config()
    base_url = cfg.ollama_base_url

    async def stream_progress():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{base_url}/api/pull",
                json={"name": model_name},
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        yield line + "\n"

    return StreamingResponse(
        stream_progress(),
        media_type="application/x-ndjson",
    )
