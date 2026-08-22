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

log = logging.getLogger(__name__)

#: Tool results carrying this key are UI instructions, not data to summarise.
_UI_CARD_KEY = "ui_card"


def _sse(event: str, payload: dict) -> dict:
    return {"event": event, "data": json.dumps(payload, default=str)}


async def stream_agent(
    agent: Agent,
    message: str,
    *,
    session_id: str,
    user_id: str,
    history: list[dict] | None = None,
) -> AsyncGenerator[dict, None]:
    """Run the agent and translate its events into SSE frames."""
    text_parts: list[str] = []
    blocks: list[dict] = []
    action: dict | None = None
    tools_used: list[str] = []

    try:
        for event in agent.run(message, history=history):
            if isinstance(event, TextDelta):
                text_parts.append(event.text)
                yield _sse("token", {"t": event.text})

            elif isinstance(event, ToolCall):
                tools_used.append(event.name)
                yield _sse("tool_call", {"id": event.id, "name": event.name, "arguments": event.arguments})

            elif isinstance(event, ToolResult):
                yield _sse(
                    "tool_result",
                    {"id": event.id, "name": event.name, "ok": event.ok, "error": event.error},
                )
                card = _as_ui_action(event)
                if card is not None:
                    action = card
                block = _as_block(event)
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
            "tools_used": tools_used,
        },
    )


def _as_ui_action(result: ToolResult) -> dict | None:
    """A tool asking the app to open a panel, rather than returning data."""
    value = result.result
    if isinstance(value, dict) and _UI_CARD_KEY in value:
        card = {k: v for k, v in value.items() if k != "note"}
        card["type"] = card.pop(_UI_CARD_KEY)
        return card
    return None


def _as_block(result: ToolResult) -> dict | None:
    """Turn a tool result the UI has a card for into a renderable block."""
    if not result.ok:
        return None
    value = result.result

    if result.name == "check_inbox" and isinstance(value, dict) and value.get("messages"):
        return {"type": "inbox_preview", "emails": value["messages"]}

    if result.name == "search_web_jobs" and isinstance(value, list) and value:
        return {"type": "job_search_results", "jobs": value}

    if result.name == "rank_candidates" and isinstance(value, list) and value:
        return {"type": "match_results", "matches": value}

    if result.name == "draft_email" and isinstance(value, dict) and value.get("subject"):
        return {"type": "email_draft", "draft": value}

    return None


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
