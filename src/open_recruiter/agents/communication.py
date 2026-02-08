"""Communication Agent — drafts recruitment emails."""

from __future__ import annotations

from open_recruiter.config import Config
from open_recruiter.llm import chat_json
from open_recruiter.prompts import COMMUNICATION_AGENT
from open_recruiter.schemas import Candidate, Email, JobDescription


def draft_outreach(config: Config, jd: JobDescription, candidate: Candidate) -> Email:
    """Draft a personalized outreach email for a candidate."""
    prompt = (
        f"Draft an outreach email for the following:\n\n"
        f"Job: {jd.title} at {jd.company}\n"
        f"Key requirements: {', '.join(jd.requirements[:5])}\n\n"
        f"Candidate: {candidate.name}\n"
        f"Skills: {', '.join(candidate.skills[:10])}\n"
        f"Experience: {candidate.experience_years} years\n"
        f"Summary: {candidate.summary}\n\n"
        f"Email type: outreach"
    )

    data = chat_json(
        config,
        system=COMMUNICATION_AGENT,
        messages=[{"role": "user", "content": prompt}],
    )

    return Email(
        to=candidate.email,
        subject=data.get("subject", f"Exciting opportunity: {jd.title} at {jd.company}"),
        body=data.get("body", ""),
        email_type="outreach",
        candidate_id=candidate.id,
    )


def draft_followup(config: Config, candidate: Candidate, original_email: Email) -> Email:
    """Draft a follow-up email for a non-responsive candidate."""
    prompt = (
        f"Draft a follow-up email.\n\n"
        f"Candidate: {candidate.name}\n"
        f"Original email subject: {original_email.subject}\n"
        f"Original email sent on: {original_email.sent_at or original_email.created_at}\n\n"
        f"Email type: followup"
    )

    data = chat_json(
        config,
        system=COMMUNICATION_AGENT,
        messages=[{"role": "user", "content": prompt}],
    )

    return Email(
        to=candidate.email,
        subject=data.get("subject", f"Re: {original_email.subject}"),
        body=data.get("body", ""),
        email_type="followup",
        candidate_id=candidate.id,
    )


def draft_rejection(config: Config, candidate: Candidate, jd: JobDescription) -> Email:
    """Draft a respectful rejection email."""
    prompt = (
        f"Draft a rejection email.\n\n"
        f"Candidate: {candidate.name}\n"
        f"Job: {jd.title} at {jd.company}\n\n"
        f"Email type: rejection"
    )

    data = chat_json(
        config,
        system=COMMUNICATION_AGENT,
        messages=[{"role": "user", "content": prompt}],
    )

    return Email(
        to=candidate.email,
        subject=data.get("subject", f"Update on your application — {jd.title}"),
        body=data.get("body", ""),
        email_type="rejection",
        candidate_id=candidate.id,
    )
