"""Slack event handlers for the #openrecruiter-intake channel."""

from __future__ import annotations

import asyncio
import logging
from functools import partial

import httpx
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from app.config import Config
from app.slack.notifier import post_candidate_summary, post_error
from app.slack.pipeline import run_ingestion_pipeline

log = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".doc", ".txt")


def register_handlers(app: AsyncApp, cfg: Config) -> None:
    """Register all Slack event listeners on the Bolt app."""

    intake_channel = cfg.slack_intake_channel

    @app.event("message")
    async def handle_message(event: dict, client: AsyncWebClient) -> None:
        """Handle plain-text messages and inline file uploads."""
        # Only process messages in the intake channel
        if intake_channel and event.get("channel") != intake_channel:
            return

        # Ignore bot messages and message edits/deletions
        if event.get("bot_id") or event.get("subtype") in (
            "bot_message", "message_changed", "message_deleted",
        ):
            return

        channel = event["channel"]
        thread_ts = event.get("ts", "")
        user_id = event.get("user", "")

        # Check if message has file attachments
        files = event.get("files", [])
        if files:
            for f in files:
                await _process_file(
                    client=client,
                    cfg=cfg,
                    file_info=f,
                    channel=channel,
                    thread_ts=thread_ts,
                    user_id=user_id,
                )
            return

        # Otherwise treat message text as a pasted resume
        text = event.get("text", "").strip()
        if not text or len(text) < 50:
            # Too short to be a resume, ignore
            return

        await _process_text(
            client=client,
            cfg=cfg,
            text=text,
            channel=channel,
            thread_ts=thread_ts,
            user_id=user_id,
        )

    @app.event("file_shared")
    async def handle_file_shared(event: dict, client: AsyncWebClient) -> None:
        """Handle file_shared events (some Slack clients use this instead of message)."""
        file_id = event.get("file_id", "")
        if not file_id:
            return

        channel = event.get("channel_id", "")
        if intake_channel and channel != intake_channel:
            return

        try:
            resp = await client.files_info(file=file_id)
            file_info = resp.get("file", {})
        except Exception as e:
            log.error("Failed to get file info for %s: %s", file_id, e)
            return

        user_id = event.get("user_id", file_info.get("user", ""))
        thread_ts = event.get("event_ts", "")

        await _process_file(
            client=client,
            cfg=cfg,
            file_info=file_info,
            channel=channel,
            thread_ts=thread_ts,
            user_id=user_id,
        )


async def _process_file(
    client: AsyncWebClient,
    cfg: Config,
    file_info: dict,
    channel: str,
    thread_ts: str,
    user_id: str,
) -> None:
    """Download and process a resume file."""
    filename = file_info.get("name", "resume")
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in SUPPORTED_EXTENSIONS:
        await post_error(
            client, channel, thread_ts,
            f"Unsupported file type `{ext}`. Supported: {', '.join(SUPPORTED_EXTENSIONS)}",
        )
        return

    # Download file bytes
    url = file_info.get("url_private_download") or file_info.get("url_private", "")
    if not url:
        await post_error(client, channel, thread_ts, "Could not get file download URL.")
        return

    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                url,
                headers={"Authorization": f"Bearer {cfg.slack_bot_token}"},
                follow_redirects=True,
            )
            resp.raise_for_status()
            file_bytes = resp.content
    except Exception as e:
        await post_error(client, channel, thread_ts, f"File download failed: {e}")
        return

    # Run the ingestion pipeline in a thread (it's synchronous)
    try:
        loop = asyncio.get_running_loop()
        candidate = await loop.run_in_executor(
            None,
            partial(
                run_ingestion_pipeline,
                cfg,
                file_bytes=file_bytes,
                filename=filename,
                source_type="file",
                slack_user_id=user_id,
                channel=channel,
                thread_ts=thread_ts,
            ),
        )
        await post_candidate_summary(client, channel, thread_ts, candidate)
    except Exception as e:
        await post_error(client, channel, thread_ts, str(e))


async def _process_text(
    client: AsyncWebClient,
    cfg: Config,
    text: str,
    channel: str,
    thread_ts: str,
    user_id: str,
) -> None:
    """Process a pasted resume text."""
    try:
        loop = asyncio.get_running_loop()
        candidate = await loop.run_in_executor(
            None,
            partial(
                run_ingestion_pipeline,
                cfg,
                raw_text=text,
                source_type="text",
                slack_user_id=user_id,
                channel=channel,
                thread_ts=thread_ts,
            ),
        )
        await post_candidate_summary(client, channel, thread_ts, candidate)
    except Exception as e:
        await post_error(client, channel, thread_ts, str(e))
