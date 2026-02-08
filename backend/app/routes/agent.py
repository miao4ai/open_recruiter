"""Agent route — SSE streaming for natural language instructions."""

import asyncio
import json

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.models import AgentRequest

router = APIRouter()


@router.post("/run")
async def run_agent(req: AgentRequest):
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
