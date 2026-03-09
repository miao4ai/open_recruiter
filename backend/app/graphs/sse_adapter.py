"""SSE Adapter — translates LangGraph graph execution into the existing
SSE event format expected by the frontend.

Event types emitted:
  - ``token``          streaming text chunk: ``{"t": "..."}``
  - ``workflow_step``  multi-step progress indicator
  - ``done``           final structured response (reply, blocks, suggestions, action)

Usage in routes/agent.py::

    from app.graphs.sse_adapter import stream_chat_graph, stream_supervisor_graph
    async for event in stream_chat_graph(state):
        yield event  # already in {event, data} dict format
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator

from app import database as db

log = logging.getLogger(__name__)


async def stream_chat_graph(
    state: dict,
    *,
    session_id: str,
    user_id: str,
    user_role: str = "recruiter",
) -> AsyncGenerator[dict, None]:
    """Run the chat graph and emit SSE events.

    Wraps ``chat_graph.invoke()`` (synchronous) so the route can
    ``async for event in stream_chat_graph(...): yield event``.

    The chat graph already saves its assistant message in its own
    ``finalize`` node, so we only need to format the output here.
    """
    from app.graphs.chat_graph import chat_graph

    try:
        result = chat_graph.invoke(state)
    except Exception as exc:
        log.error("Chat graph failed: %s", exc, exc_info=True)
        yield _done_event(
            session_id=session_id,
            reply=f"Sorry, something went wrong: {exc}",
        )
        return

    reply = result.get("response_text", "")
    action = result.get("parsed_action") or None
    context_hint = None

    # Build response payload
    response: dict = {
        "reply": reply,
        "session_id": session_id,
        "blocks": [],
        "suggestions": [],
        "context_hint": context_hint,
    }

    if action:
        response["action"] = action

    # Build smart suggestions based on role
    if not response.get("suggestions"):
        if user_role == "job_seeker":
            response["suggestions"] = _seeker_suggestions(action)
        else:
            response["suggestions"] = _default_suggestions(action)

    yield {"event": "done", "data": json.dumps(response)}


async def stream_supervisor_graph(
    state: dict,
    *,
    session_id: str,
    user_id: str,
) -> AsyncGenerator[dict, None]:
    """Run the supervisor graph and emit SSE events.

    The supervisor graph may execute multiple agents sequentially.
    We emit ``workflow_step`` events as each agent completes, then
    a final ``done`` event with the aggregated result.
    """
    from app.graphs.supervisor import supervisor_graph

    try:
        # Emit a planning step
        plan = state.get("plan", {})
        agents = state.get("agents_required", [])
        total_steps = len(agents) + 1  # agents + finalize

        yield _step_event(
            workflow_id=state.get("workflow_id", ""),
            step_index=0,
            total_steps=total_steps,
            label="Planning",
            status="running",
        )

        result = supervisor_graph.invoke(state)

        # Emit completed steps for each agent that ran
        agent_results = result.get("agent_results", {})
        for i, (agent_name, agent_result) in enumerate(agent_results.items()):
            status = "done"
            if isinstance(agent_result, dict) and agent_result.get("error"):
                status = "error"
            yield _step_event(
                workflow_id=state.get("workflow_id", ""),
                step_index=i + 1,
                total_steps=total_steps,
                label=agent_name,
                status=status,
            )

    except Exception as exc:
        log.error("Supervisor graph failed: %s", exc, exc_info=True)
        yield _done_event(
            session_id=session_id,
            reply=f"Sorry, the workflow encountered an error: {exc}",
        )
        return

    reply = result.get("response_text", "")

    # Build blocks from agent results
    blocks = _build_blocks_from_agent_results(agent_results)

    # Save assistant message
    msg_id = uuid.uuid4().hex[:8]
    db.insert_chat_message({
        "id": msg_id,
        "user_id": user_id,
        "session_id": session_id,
        "role": "assistant",
        "content": reply,
        "created_at": datetime.now().isoformat(),
    })

    response: dict = {
        "reply": reply,
        "session_id": session_id,
        "blocks": blocks,
        "suggestions": [],
        "message_id": msg_id,
    }

    # Workflow status if a workflow_id exists
    wf_id = state.get("workflow_id", "")
    if wf_id:
        response["workflow_id"] = wf_id
        response["workflow_status"] = "completed"

    yield {"event": "done", "data": json.dumps(response)}


# ── Helpers ───────────────────────────────────────────────────────────────


def _done_event(
    *,
    session_id: str = "",
    reply: str = "",
    blocks: list | None = None,
    suggestions: list | None = None,
    **extra,
) -> dict:
    """Build a ``done`` SSE event dict."""
    data: dict = {
        "reply": reply,
        "session_id": session_id,
        "blocks": blocks or [],
        "suggestions": suggestions or [],
    }
    data.update(extra)
    return {"event": "done", "data": json.dumps(data)}


def _step_event(
    *,
    workflow_id: str,
    step_index: int,
    total_steps: int,
    label: str,
    status: str = "running",
) -> dict:
    """Build a ``workflow_step`` SSE event dict."""
    return {
        "event": "workflow_step",
        "data": json.dumps({
            "workflow_id": workflow_id,
            "step_index": step_index,
            "total_steps": total_steps,
            "label": label,
            "status": status,
        }),
    }


def _build_blocks_from_agent_results(agent_results: dict) -> list[dict]:
    """Convert agent_results into frontend-compatible blocks."""
    blocks: list[dict] = []

    for agent_name, result in agent_results.items():
        if not isinstance(result, dict):
            continue

        if agent_name == "matching" and result.get("rankings"):
            blocks.append({
                "type": "match_report",
                "candidate": result.get("candidate", {}),
                "rankings": result.get("rankings", [])[:5],
                "summary": result.get("summary", ""),
            })
        elif agent_name == "communication" and result.get("subject"):
            blocks.append({
                "type": "email_draft",
                "email": {
                    "subject": result.get("subject", ""),
                    "body": result.get("body", ""),
                    "candidate_name": result.get("candidate_name", ""),
                    "email_type": result.get("email_type", "outreach"),
                },
            })
        elif agent_name == "scheduling" and result.get("event"):
            blocks.append({
                "type": "schedule_confirmation",
                "event": result.get("event", {}),
                "email_draft": result.get("email_draft", {}),
            })
        elif agent_name == "pipeline" and result.get("summary"):
            blocks.append({
                "type": "pipeline_report",
                "summary": result.get("summary", ""),
                "actions": result.get("actions", []),
            })
        elif agent_name == "job_search" and result.get("jobs"):
            blocks.append({
                "type": "job_search_results",
                "jobs": result.get("jobs", []),
                "total": result.get("total", 0),
                "query": result.get("query", ""),
                "location": result.get("location", ""),
            })
        elif agent_name == "job_match" and result.get("score") is not None:
            blocks.append({
                "type": "job_match_result",
                "score": result.get("score", 0.0),
                "strengths": result.get("strengths", []),
                "gaps": result.get("gaps", []),
                "reasoning": result.get("reasoning", ""),
                "job": result.get("job", {}),
                "candidate_name": result.get("candidate_name", ""),
            })

    return blocks


def _default_suggestions(action: dict | None) -> list[dict]:
    """Build context-aware follow-up suggestions."""
    if not action:
        return [
            {"label": "Show pipeline", "prompt": "Show me the current pipeline status"},
            {"label": "Upload resume", "prompt": "I want to upload a resume"},
        ]

    action_type = action.get("type", "")
    if action_type == "compose_email":
        return [
            {"label": "Review draft", "prompt": "Show me pending email drafts"},
            {"label": "Match more", "prompt": "Find more candidates for this role"},
        ]
    elif action_type == "match_candidate":
        cname = action.get("candidate_name", "this candidate")
        return [
            {"label": f"Email {cname}", "prompt": f"Draft an outreach email to {cname}"},
            {"label": "Compare candidates", "prompt": "Compare the top candidates"},
        ]
    return []


def _seeker_suggestions(action: dict | None) -> list[dict]:
    """Build follow-up suggestions for job seekers."""
    if not action:
        return [
            {"label": "Search jobs", "prompt": "Search for jobs matching my profile"},
            {"label": "Upload resume", "prompt": "I want to upload my resume"},
        ]

    action_type = action.get("type", "")
    if action_type == "job_search_results":
        return [
            {"label": "Analyze match", "prompt": "How well do I match the first job?"},
            {"label": "Save job", "prompt": "Save the first job to my list"},
        ]
    elif action_type == "analyze_job_match":
        return [
            {"label": "Search more", "prompt": "Search for more similar jobs"},
            {"label": "View saved jobs", "prompt": "Show my saved jobs"},
        ]
    return []
