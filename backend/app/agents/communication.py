"""Communication Agent — personalized email drafting with rich context."""

from __future__ import annotations

import logging

from app import database as db
from app.config import Config
from app.llm import chat_json
from app.prompts import DRAFT_EMAIL_ENHANCED

log = logging.getLogger(__name__)


def draft_email(
    cfg: Config,
    candidate_id: str,
    job_id: str = "",
    email_type: str = "outreach",
    instructions: str = "",
) -> dict:
    """Draft a personalized email using full candidate/job context.

    Returns ``{"subject": str, "body": str}`` or an error dict.
    """
    candidate = db.get_candidate(candidate_id)
    if not candidate:
        return {"subject": "", "body": "", "error": "Candidate not found"}

    # Build rich context
    parts: list[str] = []

    # Candidate profile
    skills = candidate.get("skills", [])
    skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)
    parts.append(
        f"## Candidate Profile\n"
        f"Name: {candidate['name']}\n"
        f"Email: {candidate.get('email', '')}\n"
        f"Title: {candidate.get('current_title', '')}\n"
        f"Company: {candidate.get('current_company', '')}\n"
        f"Skills: {skills_str}\n"
        f"Experience: {candidate.get('experience_years', 'N/A')} years\n"
        f"Location: {candidate.get('location', '')}\n"
        f"Summary: {candidate.get('resume_summary', '')}"
    )

    # Job description (if available)
    job = None
    if job_id:
        job = db.get_job(job_id)
    elif candidate.get("job_id"):
        job = db.get_job(candidate["job_id"])

    if job:
        parts.append(
            f"\n## Job Description\n"
            f"Title: {job['title']}\n"
            f"Company: {job['company']}\n"
            f"Required Skills: {', '.join(job.get('required_skills', []))}\n"
            f"Preferred Skills: {', '.join(job.get('preferred_skills', []))}\n"
            f"Experience: {job.get('experience_years', 'N/A')} years\n"
            f"Location: {job.get('location', '')}\n"
            f"Summary: {job.get('summary', '')}"
        )

    # Prior email history
    prior_emails = db.list_emails(candidate_id=candidate_id)
    if prior_emails:
        parts.append(f"\n## Prior Emails ({len(prior_emails)})")
        for e in prior_emails[:5]:  # Last 5 emails
            status = "sent" if e["sent"] else "draft"
            parts.append(
                f"- [{status}] {e['email_type']}: \"{e['subject']}\"\n"
                f"  Body: {e['body'][:200]}..."
            )

    context = "\n".join(parts)
    user_msg = (
        f"{context}\n\n"
        f"## Task\n"
        f"Email type: {email_type}\n"
        f"User instructions: {instructions or 'None — use your best judgment'}\n"
    )

    try:
        data = chat_json(
            cfg,
            system=DRAFT_EMAIL_ENHANCED,
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as e:
        log.error("Communication agent LLM call failed: %s", e)
        return {"subject": "", "body": "", "error": f"LLM error: {e}"}

    if isinstance(data, list):
        data = data[0] if data else {}

    return {
        "subject": data.get("subject", ""),
        "body": data.get("body", ""),
    }
