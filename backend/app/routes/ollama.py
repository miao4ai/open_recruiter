"""Ollama management routes — status check, model listing, model pulling, start."""

from __future__ import annotations

import asyncio
import platform
import shutil
import subprocess
import sys

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


def _find_ollama() -> str | None:
    """Return the path to the ollama binary, or None."""
    path = shutil.which("ollama")
    if path:
        return path
    # Common install locations
    candidates = []
    if sys.platform == "darwin":
        candidates = ["/usr/local/bin/ollama", "/opt/homebrew/bin/ollama"]
    elif sys.platform == "win32":
        candidates = [
            r"C:\Users\{}\AppData\Local\Programs\Ollama\ollama.exe".format(
                __import__("os").environ.get("USERNAME", "")
            ),
        ]
    else:
        candidates = ["/usr/local/bin/ollama", "/usr/bin/ollama"]
    for c in candidates:
        if __import__("os.path", fromlist=["exists"]).exists(c):
            return c
    return None


@router.post("/start")
async def start_ollama(_user: dict = Depends(get_current_user)):
    """Try to start Ollama server in the background. Returns status."""
    cfg = get_config()
    base_url = cfg.ollama_base_url

    # Already running?
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                return {"started": True, "message": "already_running"}
    except Exception:
        pass

    ollama_bin = _find_ollama()
    if not ollama_bin:
        return {"started": False, "installed": False, "message": "not_installed"}

    # Launch 'ollama serve' detached
    try:
        kwargs: dict = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            [ollama_bin, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            **kwargs,
        )
    except Exception as e:
        return {"started": False, "installed": True, "message": str(e)}

    # Wait up to 8 seconds for it to become responsive
    for _ in range(16):
        await asyncio.sleep(0.5)
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{base_url}/api/tags")
                if resp.status_code == 200:
                    return {"started": True, "message": "started"}
        except Exception:
            continue

    return {"started": False, "installed": True, "message": "timeout"}
