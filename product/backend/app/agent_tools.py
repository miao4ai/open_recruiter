"""Tools the desktop app adds to the SDK's set.

These are the capabilities that only make sense inside this application: cards
the chat UI renders, and integrations that read the recruiter's own mailbox. The
SDK knows nothing about any of them — it just calls what is registered.

    recruiter = build_recruiter(cfg, extra_tools=product_tools(cfg, user_id))
"""

from __future__ import annotations

import logging

from openrecruiter import Tool

from app.config import Config

log = logging.getLogger(__name__)


def _obj(properties: dict | None = None, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
    }


def product_tools(cfg: Config, user_id: str = "") -> list[Tool]:
    """Build the app-specific tools, bound to this request's config and user."""

    def request_resume_upload(job_id: str = "", job_title: str = "") -> dict:
        """A card, not an upload: the file has to come from the user's machine."""
        return {
            "ui_card": "upload_resume",
            "job_id": job_id,
            "job_title": job_title,
            "note": "An upload panel is now open for the user. Do not ask them to paste the resume.",
        }

    def request_jd_upload() -> dict:
        return {
            "ui_card": "upload_jd",
            "note": "An upload panel is now open for the user.",
        }

    def check_inbox(limit: int = 10) -> dict:
        from app.tools.imap_checker import fetch_recent_inbox

        if not cfg.imap_host or not cfg.imap_username:
            return {"configured": False, "note": "No IMAP mailbox is configured in Settings."}
        try:
            messages = fetch_recent_inbox(cfg, limit=limit)
        except Exception as exc:  # noqa: BLE001 - a mail server can fail in many ways
            log.warning("Inbox check failed: %s", exc)
            return {"configured": True, "error": str(exc)}
        return {
            "configured": True,
            "count": len(messages),
            "messages": [
                {
                    "from": m.get("from", ""),
                    "subject": m.get("subject", ""),
                    "date": m.get("date", ""),
                    "snippet": (m.get("body", "") or "")[:200],
                }
                for m in messages
            ],
        }

    def search_web_jobs(query: str, location: str = "", limit: int = 10) -> list[dict]:
        """Job-seeker mode: look outward at the web, not inward at the pipeline."""
        from app.agents.job_search import search_jobs_enriched

        profile = None
        if user_id:
            from app import database as db

            profile = db.get_job_seeker_profile_by_user(user_id)
        results = search_jobs_enriched(cfg, query, profile, location, n_results=limit)
        for i, r in enumerate(results, 1):
            r["index"] = i
        return results

    return [
        Tool(
            name="request_resume_upload",
            description=(
                "Open the resume upload panel in the app. Use this when the user wants to add "
                "a candidate from a file — never ask them to paste resume text instead."
            ),
            parameters=_obj({"job_id": {"type": "string"}, "job_title": {"type": "string"}}),
            fn=request_resume_upload,
        ),
        Tool(
            name="request_jd_upload",
            description="Open the job description upload panel in the app.",
            parameters=_obj(),
            fn=request_jd_upload,
        ),
        Tool(
            name="check_inbox",
            description=(
                "Read the most recent messages from the recruiter's configured mailbox, "
                "to see whether candidates have replied."
            ),
            parameters=_obj({"limit": {"type": "integer"}}),
            fn=check_inbox,
        ),
        Tool(
            name="search_web_jobs",
            description=(
                "Search the web for job postings matching a query. This looks outside the "
                "pipeline — use it for job seekers, not for finding candidates."
            ),
            parameters=_obj(
                {
                    "query": {"type": "string"},
                    "location": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                ["query"],
            ),
            fn=search_web_jobs,
        ),
    ]


#: Tools a job seeker may reach. Everything else is recruiter-only — the role
#: check happens before the model ever sees a schema, so a seeker's agent simply
#: has no way to touch another user's pipeline.
SEEKER_TOOLS = frozenset(
    {"search_web_jobs", "get_job", "match_candidate", "request_resume_upload"}
)


def tools_for_role(recruiter, role: str):
    """Narrow the registry to what this role is allowed to call."""
    if role != "job_seeker":
        return recruiter.tools

    from openrecruiter import ToolRegistry

    return ToolRegistry([t for t in recruiter.tools if t.name in SEEKER_TOOLS])


__all__ = ["SEEKER_TOOLS", "product_tools", "tools_for_role"]
