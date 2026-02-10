"""FastAPI routes for Slack event subscriptions."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/events")
async def slack_events(request: Request) -> JSONResponse:
    """Handle Slack Events API webhook (URL verification + event dispatch)."""
    from app.slack.bot import get_slack_handler

    handler = get_slack_handler()
    if handler is None:
        return JSONResponse({"error": "Slack bot not configured"}, status_code=503)
    return await handler.handle(request)


@router.post("/interactions")
async def slack_interactions(request: Request) -> JSONResponse:
    """Handle Slack interactive components (buttons, modals)."""
    from app.slack.bot import get_slack_handler

    handler = get_slack_handler()
    if handler is None:
        return JSONResponse({"error": "Slack bot not configured"}, status_code=503)
    return await handler.handle(request)
