"""Tools the desktop app adds to the SDK's set.

These are the capabilities that only make sense inside this application: cards
the chat UI renders, and integrations that read the recruiter's own mailbox. The
SDK knows nothing about any of them — it just calls what is registered.

    recruiter = build_recruiter(cfg, extra_tools=product_tools(cfg, user_id))
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from openrecruiter import Tool

from app.config import Config

log = logging.getLogger(__name__)


_STR = {"type": "string"}
_INT = {"type": "integer"}


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

    def open_job_form() -> dict:
        return {"ui_card": "open_job_form", "note": "A blank job form is now open for the user."}

    def evaluate_candidate(candidate_id: str, job_id: str = "") -> dict:
        """Four specialist agents in parallel, then a synthesis."""
        from app import database as db
        from app.agents.evaluation_swarm import evaluate_candidate_swarm

        result = evaluate_candidate_swarm(cfg, candidate_id, job_id=job_id)
        if result.get("error"):
            return {"error": result["error"]}

        candidate = db.get_candidate(candidate_id) or {}
        job = db.get_job(job_id) if job_id else None
        return {
            "candidate": {
                "id": candidate_id,
                "name": candidate.get("name", ""),
                "current_title": candidate.get("current_title", ""),
            },
            "job_title": (job or {}).get("title", ""),
            "job_company": (job or {}).get("company", ""),
            "dimensions": result.get("dimensions", []),
            "overall_score": result.get("overall_score", 0),
            "hire_recommendation": result.get("hire_recommendation", "maybe"),
            "synthesis": result.get("synthesis", ""),
        }

    def market_analysis(role: str, location: str = "", industry: str = "") -> dict:
        from app.agents.market import analyze_market

        return analyze_market(cfg, role, location=location, industry=industry)

    def recommend_to_employer(candidate_id: str, job_id: str, instructions: str = "") -> dict:
        from app.agents.employer import draft_recommendation

        return draft_recommendation(cfg, candidate_id, job_id, instructions=instructions)

    def mark_candidates_replied(candidate_ids: list[str]) -> dict:
        from app import database as db

        updated = [cid for cid in candidate_ids if db.update_candidate(cid, {"status": "replied"})]
        return {"updated": updated, "count": len(updated)}

    # ── job seeker ───────────────────────────────────────────────────────

    def analyze_job_match(
        job_title: str,
        job_company: str = "",
        job_location: str = "",
        job_url: str = "",
        job_snippet: str = "",
    ) -> dict:
        """Score this user's profile against one posting.

        The old handler had to dig the posting back out of the chat history,
        because a single-action turn could not carry a previous result forward.
        The agent already has its own search results in context, so it simply
        passes them in.
        """
        from app.llm import chat_json
        from app.prompts import MATCHING

        profile = _seeker_profile(user_id)
        if profile is None:
            return {"error": "No resume on file. The user needs to upload one first."}

        job_desc = f"Title: {job_title}\n"
        for label, value in (("Company", job_company), ("Location", job_location)):
            if value:
                job_desc += f"{label}: {value}\n"
        if job_snippet:
            job_desc += f"Description: {job_snippet}\n"

        match = _first_dict(
            chat_json(
                cfg,
                system=MATCHING,
                messages=[
                    {
                        "role": "user",
                        "content": f"## Job Description\n{job_desc}\n\n## Candidate Profile\n{_profile_text(profile)}",
                    }
                ],
            )
        )
        return {
            "job": {
                "title": job_title,
                "company": job_company,
                "location": job_location,
                "url": job_url,
                "snippet": job_snippet,
            },
            "match": {
                "score": match.get("score", 0.0),
                "strengths": match.get("strengths", []),
                "gaps": match.get("gaps", []),
                "reasoning": match.get("reasoning", ""),
            },
        }

    def save_job(
        title: str,
        company: str = "",
        location: str = "",
        url: str = "",
        snippet: str = "",
    ) -> dict:
        from app import database as db

        job = {
            "id": uuid.uuid4().hex[:8],
            "user_id": user_id,
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "snippet": snippet,
            "source": "chat",
            "required_skills": [],
            "created_at": datetime.now().isoformat(),
        }
        db.insert_seeker_job(job)
        return {"saved": True, "job": job}

    def improve_resume(
        job_title: str = "",
        job_company: str = "",
        gaps: list[str] | None = None,
    ) -> dict:
        from app.llm import chat_json
        from app.prompts import RESUME_IMPROVEMENT

        profile = _seeker_profile(user_id)
        if profile is None:
            return {"error": "No resume on file. The user needs to upload one first."}

        gap_text = (
            "\n".join(f"- {g}" for g in gaps)
            if gaps
            else "No specific gaps identified — provide general improvement advice."
        )
        result = _first_dict(
            chat_json(
                cfg,
                system=RESUME_IMPROVEMENT,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"## Candidate Profile\n{_profile_text(profile)}\n\n"
                            f"## Target Job\nTitle: {job_title}\nCompany: {job_company}\n\n"
                            f"## Identified Gaps\n{gap_text}"
                        ),
                    }
                ],
            )
        )
        return {
            "summary": result.get("summary", ""),
            "suggestions": result.get("suggestions", []),
            "job_title": job_title,
            "job_company": job_company,
        }

    def generate_cover_letter(
        job_title: str,
        job_company: str = "",
        job_snippet: str = "",
    ) -> dict:
        from app.llm import chat_json
        from app.prompts import COVER_LETTER

        profile = _seeker_profile(user_id)
        if profile is None:
            return {"error": "No resume on file. The user needs to upload one first."}

        result = _first_dict(
            chat_json(
                cfg,
                system=COVER_LETTER,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"## Candidate Profile\n{_profile_text(profile)}\n\n"
                            f"## Target Job\nTitle: {job_title}\nCompany: {job_company}\n"
                            + (f"Description: {job_snippet}\n" if job_snippet else "")
                        ),
                    }
                ],
            )
        )
        return {
            "job_title": job_title,
            "job_company": job_company,
            "subject": result.get("subject", f"Application for {job_title}"),
            "body": result.get("body", ""),
        }

    return [
        Tool(
            name="request_resume_upload",
            description=(
                "Open the resume upload panel in the app. Use this when the user wants to add "
                "a candidate from a file — never ask them to paste resume text instead."
            ),
            parameters=_obj({"job_id": _STR, "job_title": _STR}),
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
            parameters=_obj({"limit": _INT}),
            fn=check_inbox,
        ),
        Tool(
            name="open_job_form",
            description="Open a blank job form in the app for the user to fill in by hand.",
            parameters=_obj(),
            fn=open_job_form,
        ),
        Tool(
            name="evaluate_candidate",
            description=(
                "Deep multi-agent evaluation of one candidate: skills, culture fit, risk "
                "signals, and market position, synthesised into a hire recommendation. "
                "Slower and more thorough than match_candidate — use it when the user "
                "wants an assessment, not a score."
            ),
            parameters=_obj({"candidate_id": _STR, "job_id": _STR}, ["candidate_id"]),
            fn=evaluate_candidate,
        ),
        Tool(
            name="market_analysis",
            description=(
                "Salary benchmarks and hiring-market conditions for a role, to answer "
                "'what should we be paying' or 'how hard is this to fill'."
            ),
            parameters=_obj(
                {"role": _STR, "location": _STR, "industry": _STR}, ["role"]
            ),
            fn=market_analysis,
        ),
        Tool(
            name="recommend_to_employer",
            description=(
                "Draft a recommendation email presenting a candidate to the hiring "
                "manager. Returns a draft for review — it does not send anything."
            ),
            parameters=_obj(
                {"candidate_id": _STR, "job_id": _STR, "instructions": _STR},
                ["candidate_id", "job_id"],
            ),
            fn=recommend_to_employer,
        ),
        Tool(
            name="mark_candidates_replied",
            description="Mark candidates as having replied, after the recruiter confirms it.",
            parameters=_obj(
                {"candidate_ids": {"type": "array", "items": _STR}}, ["candidate_ids"]
            ),
            fn=mark_candidates_replied,
        ),
        Tool(
            name="analyze_job_match",
            description=(
                "Score this user's own profile against one job posting, with strengths "
                "and gaps. Pass the posting's details from a previous search."
            ),
            parameters=_obj(
                {
                    "job_title": _STR,
                    "job_company": _STR,
                    "job_location": _STR,
                    "job_url": _STR,
                    "job_snippet": _STR,
                },
                ["job_title"],
            ),
            fn=analyze_job_match,
        ),
        Tool(
            name="save_job",
            description="Save a job posting to this user's saved list.",
            parameters=_obj(
                {"title": _STR, "company": _STR, "location": _STR, "url": _STR, "snippet": _STR},
                ["title"],
            ),
            fn=save_job,
        ),
        Tool(
            name="improve_resume",
            description=(
                "Concrete suggestions for improving this user's resume for a target job. "
                "Pass the gaps from a previous analyze_job_match if you have them."
            ),
            parameters=_obj(
                {
                    "job_title": _STR,
                    "job_company": _STR,
                    "gaps": {"type": "array", "items": _STR},
                }
            ),
            fn=improve_resume,
        ),
        Tool(
            name="generate_cover_letter",
            description="Write a cover letter for this user for a specific job.",
            parameters=_obj(
                {"job_title": _STR, "job_company": _STR, "job_snippet": _STR}, ["job_title"]
            ),
            fn=generate_cover_letter,
        ),
        Tool(
            name="search_web_jobs",
            description=(
                "Search the web for job postings matching a query. This looks outside the "
                "pipeline — use it for job seekers, not for finding candidates."
            ),
            parameters=_obj(
                {"query": _STR, "location": _STR, "limit": _INT},
                ["query"],
            ),
            fn=search_web_jobs,
        ),
    ]


#: Tools a job seeker may reach. Everything else is recruiter-only — the role
#: check happens before the model ever sees a schema, so a seeker's agent simply
#: has no way to touch another user's pipeline.
SEEKER_TOOLS = frozenset(
    {
        "search_web_jobs",
        "analyze_job_match",
        "save_job",
        "improve_resume",
        "generate_cover_letter",
        "request_resume_upload",
    }
)


def tools_for_role(recruiter, role: str):
    """Narrow the registry to what this role is allowed to call."""
    if role != "job_seeker":
        return recruiter.tools

    from openrecruiter import ToolRegistry

    return ToolRegistry([t for t in recruiter.tools if t.name in SEEKER_TOOLS])



# ── shared helpers ───────────────────────────────────────────────────────


def _seeker_profile(user_id: str) -> dict | None:
    from app import database as db

    profile = db.get_job_seeker_profile_by_user(user_id)
    return profile if profile and profile.get("name") else None


def _profile_text(profile: dict) -> str:
    skills = profile.get("skills", [])
    skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)
    return (
        f"Name: {profile['name']}\n"
        f"Title: {profile.get('current_title', '')}\n"
        f"Skills: {skills_str}\n"
        f"Experience: {profile.get('experience_years', 'N/A')} years\n"
        f"Location: {profile.get('location', '')}\n"
        f"Summary: {profile.get('resume_summary', '')}"
    )


def _first_dict(value):
    """LLM helpers occasionally return a single-element list."""
    if isinstance(value, list):
        value = value[0] if value else {}
    return value if isinstance(value, dict) else {}


__all__ = ["SEEKER_TOOLS", "product_tools", "tools_for_role"]
