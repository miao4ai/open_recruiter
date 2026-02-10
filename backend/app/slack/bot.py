"""Slack Bolt async app factory and FastAPI integration."""

from __future__ import annotations

import logging

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from app.config import Config

log = logging.getLogger(__name__)

_slack_app: AsyncApp | None = None
_handler: AsyncSlackRequestHandler | None = None


def init_slack_app(cfg: Config) -> AsyncApp | None:
    """Create and configure the Slack Bolt AsyncApp.

    Returns None if Slack tokens are not configured, allowing the rest of
    the application to run without Slack integration.
    """
    global _slack_app, _handler

    if not cfg.slack_bot_token or not cfg.slack_signing_secret:
        log.info("Slack tokens not configured — Slack bot disabled.")
        return None

    _slack_app = AsyncApp(
        token=cfg.slack_bot_token,
        signing_secret=cfg.slack_signing_secret,
    )

    # Register event handlers
    from app.slack.handlers import register_handlers
    register_handlers(_slack_app, cfg)

    _handler = AsyncSlackRequestHandler(_slack_app)
    log.info(
        "Slack bot initialized (channel: %s)",
        cfg.slack_intake_channel or "all",
    )
    return _slack_app


def get_slack_app() -> AsyncApp | None:
    return _slack_app


def get_slack_handler() -> AsyncSlackRequestHandler | None:
    return _handler
