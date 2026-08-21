"""Post-ingestion Slack notification — threaded reply with candidate summary."""

from __future__ import annotations

import logging

from slack_sdk.web.async_client import AsyncWebClient

from app import database as db
from app import vectorstore

log = logging.getLogger(__name__)


async def post_candidate_summary(
    client: AsyncWebClient,
    channel: str,
    thread_ts: str,
    candidate: dict,
) -> None:
    """Post a threaded message summarizing the ingested candidate."""
    blocks = _build_summary_blocks(candidate)
    fallback = f"Candidate ingested: {candidate.get('name', 'Unknown')}"

    try:
        await client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            blocks=blocks,
            text=fallback,
        )
    except Exception as e:
        log.error("Failed to post candidate summary to Slack: %s", e)


async def post_error(
    client: AsyncWebClient,
    channel: str,
    thread_ts: str,
    error_msg: str,
) -> None:
    """Post a threaded error message when ingestion fails."""
    try:
        await client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f":warning: Resume ingestion failed: {error_msg}",
        )
    except Exception as e:
        log.error("Failed to post error to Slack: %s", e)


def _build_summary_blocks(candidate: dict) -> list[dict]:
    """Build Slack Block Kit blocks for candidate summary."""
    name = candidate.get("name", "Unknown")
    title = candidate.get("current_title", "N/A")
    company = candidate.get("current_company", "")
    skills = candidate.get("skills", [])
    exp = candidate.get("experience_years")
    summary = candidate.get("resume_summary", "")
    status = candidate.get("status", "new")
    candidate_id = candidate.get("id", "")

    skills_str = ", ".join(skills[:10]) if skills else "None extracted"
    exp_str = f"{exp} years" if exp else "N/A"
    title_line = f"{title} at {company}" if company else title

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"New Candidate: {name}", "emoji": True},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Title:*\n{title_line}"},
                {"type": "mrkdwn", "text": f"*Experience:*\n{exp_str}"},
                {"type": "mrkdwn", "text": f"*Skills:*\n{skills_str}"},
                {"type": "mrkdwn", "text": f"*Status:*\n{status.upper()}"},
            ],
        },
    ]

    if summary:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Summary:*\n{summary[:500]}"},
        })

    # Find matching jobs
    matched = _find_matching_jobs(candidate_id)
    if matched:
        lines = [f"- {m['title']} ({m['score']:.0%} match)" for m in matched[:3]]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Top Matching Jobs:*\n" + "\n".join(lines)},
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"ID: `{candidate_id}` | Processed by Open Recruiter"},
        ],
    })

    return blocks


def _find_matching_jobs(candidate_id: str) -> list[dict]:
    """Find top matching jobs for a candidate using vector similarity."""
    try:
        candidate = db.get_candidate(candidate_id)
        if not candidate:
            return []
        embed_text = vectorstore.build_candidate_embed_text(candidate)
        if not embed_text.strip():
            return []
        results = vectorstore.search_by_text(
            collection_name="jobs",
            query_text=embed_text,
            n_results=3,
        )
        enriched = []
        for r in results:
            job = db.get_job(r["job_id"])
            if job:
                enriched.append({
                    "title": job.get("title", "Untitled"),
                    "company": job.get("company", ""),
                    "score": r["score"],
                })
        return enriched
    except Exception as e:
        log.warning("Failed to find matching jobs: %s", e)
        return []
