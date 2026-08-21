"""Planning Agent — multi-step workflows like candidate-job matching."""

from __future__ import annotations

import logging

from app import database as db
from app.config import Config
from app.llm import chat_json
from app.prompts import MULTI_JOB_MATCHING

log = logging.getLogger(__name__)


def match_candidate_to_jobs(cfg: Config, candidate_id: str) -> dict:
    """Match a candidate against all available jobs using LLM evaluation.

    Returns ``{"candidate": dict, "rankings": list[dict], "summary": str}``
    where each ranking has: job_id, score, title, company, strengths, gaps, one_liner.
    """
    candidate = db.get_candidate(candidate_id)
    if not candidate:
        return {"error": "Candidate not found", "rankings": [], "summary": ""}

    jobs = db.list_jobs()
    if not jobs:
        return {"error": "No jobs available", "candidate": candidate, "rankings": [], "summary": "No jobs in the system to match against."}

    # Build candidate profile
    skills = candidate.get("skills", [])
    skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)

    # Build jobs section
    jobs_text = []
    for j in jobs:
        req_skills = ", ".join(j.get("required_skills", []))
        pref_skills = ", ".join(j.get("preferred_skills", []))
        jobs_text.append(
            f"### Job ID: {j['id']}\n"
            f"Title: {j['title']}\n"
            f"Company: {j['company']}\n"
            f"Required Skills: {req_skills}\n"
            f"Preferred Skills: {pref_skills}\n"
            f"Experience: {j.get('experience_years', 'N/A')} years\n"
            f"Location: {j.get('location', 'N/A')}\n"
            f"Summary: {j.get('summary', '')}\n"
        )

    user_msg = (
        f"## Candidate Profile\n"
        f"Name: {candidate['name']}\n"
        f"Title: {candidate.get('current_title', '')}\n"
        f"Company: {candidate.get('current_company', '')}\n"
        f"Skills: {skills_str}\n"
        f"Experience: {candidate.get('experience_years', 'N/A')} years\n"
        f"Location: {candidate.get('location', '')}\n"
        f"Summary: {candidate.get('resume_summary', '')}\n\n"
        f"## Available Jobs ({len(jobs)})\n\n"
        + "\n".join(jobs_text)
    )

    try:
        data = chat_json(
            cfg,
            system=MULTI_JOB_MATCHING,
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as e:
        log.error("Planning agent LLM call failed: %s", e)
        return {"error": f"LLM error: {e}", "candidate": candidate, "rankings": [], "summary": ""}

    if isinstance(data, list):
        data = data[0] if data else {}

    return {
        "candidate": candidate,
        "rankings": data.get("rankings", []),
        "summary": data.get("summary", ""),
    }
