"""Agent route — SSE streaming for natural language instructions + chat."""

import asyncio
import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app import database as db
from app.auth import get_current_user
from app.models import AgentRequest, ChatRequest

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/run")
async def run_agent(req: AgentRequest, _user: dict = Depends(get_current_user)):
    """Execute a natural language instruction via the orchestrator.

    Returns an SSE stream with plan/progress/result events.
    Phase 2 will connect this to the real orchestrator + agents.
    """
    async def event_generator():
        # Phase 1: mock SSE stream
        yield {
            "event": "plan",
            "data": json.dumps({
                "goal": f"Execute: {req.instruction}",
                "tasks": [
                    {"id": 1, "description": "Analyzing your request...", "type": "planning"},
                    {"id": 2, "description": "Executing tasks...", "type": "execution"},
                ],
            }),
        }

        await asyncio.sleep(0.5)

        yield {
            "event": "progress",
            "data": json.dumps({
                "task_id": 1,
                "status": "done",
                "message": "Request analyzed.",
            }),
        }

        await asyncio.sleep(0.5)

        yield {
            "event": "progress",
            "data": json.dumps({
                "task_id": 2,
                "status": "done",
                "message": "Agent execution not yet implemented — coming in Phase 2.",
            }),
        }

        yield {
            "event": "result",
            "data": json.dumps({
                "summary": f"Received your instruction: \"{req.instruction}\". Full agent execution will be available in Phase 2.",
            }),
        }

    return EventSourceResponse(event_generator())


# ── Chat ──────────────────────────────────────────────────────────────────


@router.post("/chat")
async def chat_endpoint(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    """Synchronous chat with the AI recruiting assistant."""
    from app.routes.settings import get_config
    from app.llm import chat
    from app.prompts import CHAT_SYSTEM

    user_id = current_user["id"]
    cfg = get_config()

    has_key = (
        (cfg.llm_provider == "anthropic" and cfg.anthropic_api_key)
        or (cfg.llm_provider == "openai" and cfg.openai_api_key)
    )
    if not has_key:
        return {"reply": "Please configure an LLM API key in Settings before using the chat assistant."}

    # Build context from database
    context = _build_chat_context()
    system_prompt = CHAT_SYSTEM.format(context=context)

    # Load conversation history
    history = db.list_chat_messages(user_id, limit=20)

    # Save user message
    db.insert_chat_message({
        "id": uuid.uuid4().hex[:8],
        "user_id": user_id,
        "role": "user",
        "content": req.message,
        "created_at": datetime.now().isoformat(),
    })

    # Build messages array for LLM
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": req.message})

    # Call LLM
    try:
        reply = chat(cfg, system=system_prompt, messages=messages)
    except Exception as e:
        log.error("Chat LLM call failed: %s", e)
        reply = f"I encountered an error: {e!s}. Please check your LLM configuration in Settings."

    # Save assistant reply
    db.insert_chat_message({
        "id": uuid.uuid4().hex[:8],
        "user_id": user_id,
        "role": "assistant",
        "content": reply,
        "created_at": datetime.now().isoformat(),
    })

    return {"reply": reply}


@router.get("/chat/history")
async def chat_history(current_user: dict = Depends(get_current_user)):
    """Retrieve chat history for the current user."""
    return db.list_chat_messages(current_user["id"], limit=50)


@router.delete("/chat/history")
async def clear_chat_history(current_user: dict = Depends(get_current_user)):
    """Clear chat history for the current user."""
    db.clear_chat_messages(current_user["id"])
    return {"status": "cleared"}


def _build_chat_context() -> str:
    """Build a context string from the database for the chat system prompt."""
    parts = []

    # Jobs summary
    jobs = db.list_jobs()
    if jobs:
        parts.append(f"## Active Jobs ({len(jobs)})")
        for j in jobs[:10]:
            parts.append(
                f"- {j['title']} at {j['company']} "
                f"(ID: {j['id']}, candidates: {j.get('candidate_count', 0)})"
            )
    else:
        parts.append("## Jobs: None")

    # Candidates summary
    candidates = db.list_candidates()
    if candidates:
        parts.append(f"\n## Candidates ({len(candidates)})")
        for c in candidates[:20]:
            parts.append(
                f"- {c['name']} — {c.get('current_title', 'N/A')} "
                f"(status: {c['status']}, score: {c.get('match_score', 0):.0%}, "
                f"email: {c.get('email', 'N/A')}, skills: {', '.join(c.get('skills', [])[:5])})"
            )
    else:
        parts.append("\n## Candidates: None")

    # Recent emails
    emails = db.list_emails()
    if emails:
        recent = emails[:10]
        parts.append(f"\n## Recent Emails ({len(emails)} total)")
        for e in recent:
            status = "sent" if e["sent"] else ("approved" if e["approved"] else "draft")
            parts.append(
                f"- [{status}] \"{e['subject']}\" to {e['to_email']} "
                f"({e['email_type']}, candidate: {e.get('candidate_name', 'N/A')})"
            )
    else:
        parts.append("\n## Emails: None")

    return "\n".join(parts)
