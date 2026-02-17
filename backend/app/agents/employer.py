"""Employer Contact Agent — candidate recommendation emails + reply classification."""

from __future__ import annotations

import logging

from app import database as db
from app.config import Config
from app.llm import chat_json
from app.prompts import DRAFT_RECOMMENDATION, CLASSIFY_EMPLOYER_REPLY

log = logging.getLogger(__name__)


def draft_recommendation(
    cfg: Config,
    candidate_id: str,
    job_id: str,
    instructions: str = "",
) -> dict:
    """Draft a candidate recommendation email to the employer/hiring manager.

    Returns ``{"subject": str, "body": str}`` or an error dict.
    """
    candidate = db.get_candidate(candidate_id)
    if not candidate:
        return {"subject": "", "body": "", "error": "Candidate not found"}

    job = db.get_job(job_id) if job_id else None

    # Build rich context
    parts: list[str] = []

    skills = candidate.get("skills", [])
    skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)
    parts.append(
        f"## Candidate Profile\n"
        f"Name: {candidate['name']}\n"
        f"Title: {candidate.get('current_title', '')}\n"
        f"Company: {candidate.get('current_company', '')}\n"
        f"Skills: {skills_str}\n"
        f"Experience: {candidate.get('experience_years', 'N/A')} years\n"
        f"Location: {candidate.get('location', '')}\n"
        f"Summary: {candidate.get('resume_summary', '')}"
    )

    if candidate.get("match_score"):
        parts.append(
            f"\n## Match Analysis\n"
            f"Score: {candidate['match_score']:.0%}\n"
            f"Reasoning: {candidate.get('match_reasoning', '')}\n"
            f"Strengths: {', '.join(candidate.get('strengths', []))}\n"
            f"Gaps: {', '.join(candidate.get('gaps', []))}"
        )

    if job:
        req_skills = ", ".join(job.get("required_skills", []))
        parts.append(
            f"\n## Job Description\n"
            f"Title: {job['title']}\n"
            f"Company: {job['company']}\n"
            f"Required Skills: {req_skills}\n"
            f"Experience: {job.get('experience_years', 'N/A')} years\n"
            f"Location: {job.get('location', '')}\n"
            f"Summary: {job.get('summary', '')}"
        )

        if job.get("contact_name"):
            parts.append(f"\nHiring Manager: {job['contact_name']}")

    context = "\n".join(parts)
    user_msg = (
        f"{context}\n\n"
        f"## Task\n"
        f"Draft a recommendation email introducing this candidate to the hiring manager.\n"
        f"User instructions: {instructions or 'None — use your best judgment'}\n"
    )

    try:
        data = chat_json(
            cfg,
            system=DRAFT_RECOMMENDATION,
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as e:
        log.error("Employer agent draft LLM call failed: %s", e)
        return {"subject": "", "body": "", "error": f"LLM error: {e}"}

    if isinstance(data, list):
        data = data[0] if data else {}

    return {
        "subject": data.get("subject", ""),
        "body": data.get("body", ""),
    }


def classify_employer_reply(
    cfg: Config,
    reply_body: str,
    original_subject: str,
    candidate_name: str,
    job_title: str,
) -> dict:
    """Classify an employer's reply to a recommendation email.

    Returns ``{"intent": str, "new_status": str|None, "summary": str, "action_needed": str}``.
    """
    user_msg = (
        f"Original email subject: {original_subject}\n"
        f"Candidate: {candidate_name}\n"
        f"Job: {job_title}\n\n"
        f"Employer's reply:\n{reply_body}"
    )

    try:
        data = chat_json(
            cfg,
            system=CLASSIFY_EMPLOYER_REPLY,
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as e:
        log.error("Employer reply classification LLM call failed: %s", e)
        return {
            "intent": "other",
            "new_status": None,
            "summary": f"Classification failed: {e}",
            "action_needed": "Manual review required",
        }

    if isinstance(data, list):
        data = data[0] if data else {}

    return {
        "intent": data.get("intent", "other"),
        "new_status": data.get("new_status"),
        "summary": data.get("summary", ""),
        "action_needed": data.get("action_needed", ""),
    }
