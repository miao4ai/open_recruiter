"""Stream the SDK agent to the browser.

Text is forwarded as `token` events — the same name the chat UI has always
listened for, so restoring real streaming needs no change on the front end. Tool
activity gets its own events so the UI can show what the agent is doing rather
than a spinner, and the terminal `done` event keeps the payload shape the client
already parses.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

from openrecruiter import (
    Agent,
    ApprovalRequired,
    Finished,
    TextDelta,
    ToolCall,
    ToolResult,
)

from app import database as db
from app.blocks import as_action, as_block, as_context_hint

log = logging.getLogger(__name__)


def _sse(event: str, payload: dict) -> dict:
    return {"event": event, "data": json.dumps(payload, default=str)}


def _park_for_approval(agent: Agent, session_id: str, user_id: str) -> str:
    """Persist the paused run so a later request can pick it up.

    The decision almost always arrives on a different request — often after the
    user has read the draft — so the agent's state has to outlive this one.
    """
    workflow_id = uuid.uuid4().hex[:8]
    now = datetime.now().isoformat()
    db.insert_workflow(
        {
            "id": workflow_id,
            "session_id": session_id,
            "user_id": user_id,
            "workflow_type": "tool_approval",
            "status": "paused",
            "current_step": 0,
            "total_steps": 1,
            "steps_json": "[]",
            "context_json": "{}",
            "checkpoint_data_json": agent.pending.model_dump_json() if agent.pending else "{}",
            "created_at": now,
            "updated_at": now,
        }
    )
    return workflow_id


async def stream_agent(
    agent: Agent,
    message: str,
    *,
    session_id: str,
    user_id: str,
    history: list[dict] | None = None,
    resume: tuple[object, bool] | None = None,
) -> AsyncGenerator[dict, None]:
    """Run the agent and translate its events into SSE frames."""
    text_parts: list[str] = []
    blocks: list[dict] = []
    action: dict | None = None
    context_hint: dict | None = None
    tools_used: list[str] = []
    #: Arguments by call id, so a result can be mapped with what it was asked.
    call_arguments: dict[str, dict] = {}

    try:
        events = (
            agent.resume(resume[0], resume[1])
            if resume is not None
            else agent.run(message, history=history)
        )
        for event in events:
            if isinstance(event, TextDelta):
                text_parts.append(event.text)
                yield _sse("token", {"t": event.text})

            elif isinstance(event, ToolCall):
                tools_used.append(event.name)
                call_arguments[event.id] = event.arguments
                if context_hint is None:
                    context_hint = as_context_hint(event.name, event.arguments)
                yield _sse("tool_call", {"id": event.id, "name": event.name, "arguments": event.arguments})

            elif isinstance(event, ToolResult):
                yield _sse(
                    "tool_result",
                    {"id": event.id, "name": event.name, "ok": event.ok, "error": event.error},
                )
                if event.ok:
                    card = as_action(event.name, event.result)
                    if card is not None:
                        action = card
                    block = as_block(event.name, event.result)
                    if block is not None:
                        blocks.append(block)

            elif isinstance(event, ApprovalRequired):
                yield _sse(
                    "approval_required",
                    {
                        "id": event.id,
                        "name": event.name,
                        "arguments": event.arguments,
                        "description": event.description,
                        "session_id": session_id,
                        # The client answers on this id — see /agent/workflow/{id}.
                        "workflow_id": _park_for_approval(agent, session_id, user_id),
                    },
                )

            elif isinstance(event, Finished):
                if event.text:
                    text_parts.append(event.text) if not text_parts else None
                if event.stop_reason == "error":
                    log.error("Agent run failed: %s", event.error)

    except Exception as exc:  # noqa: BLE001 - the stream must always terminate
        log.exception("Agent stream failed")
        text_parts.append(f"\n\nSorry, something went wrong: {exc}")

    # Job-seeker follow-ups ("analyse the third one") read the list back off the
    # stored action, so it has to survive in the message record.
    if action is None:
        search = next((b for b in blocks if b["type"] == "job_search_results"), None)
        if search is not None:
            action = search

    reply = "".join(text_parts).strip()
    message_id = _persist(user_id, session_id, reply, action)

    yield _sse(
        "done",
        {
            "reply": reply,
            "session_id": session_id,
            "message_id": message_id,
            "blocks": blocks,
            "suggestions": [],
            "action": action,
            "context_hint": context_hint,
            "tools_used": tools_used,
        },
    )


def _persist(user_id: str, session_id: str, reply: str, action: dict | None) -> str:
    """Save the assistant turn. A storage failure must not break the stream."""
    message_id = uuid.uuid4().hex[:8]
    try:
        db.insert_chat_message(
            {
                "id": message_id,
                "user_id": user_id,
                "session_id": session_id,
                "role": "assistant",
                "content": reply,
                "action_json": json.dumps(action) if action else "",
                "action_status": "pending" if action else "",
                "created_at": datetime.now().isoformat(),
            }
        )
    except Exception:
        log.exception("Could not persist the assistant message")
    return message_id


__all__ = ["stream_agent"]
