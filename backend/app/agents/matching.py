"""Matching Agent — JD-candidate scoring via vector similarity + LLM evaluation."""

from __future__ import annotations

import logging

from app import database as db
from app import vectorstore
from app.config import Config
from app.llm import chat_json
from app.prompts import MATCHING

log = logging.getLogger(__name__)


def rank_candidates_for_job(
    job_id: str,
    candidate_ids: list[str] | None = None,
    top_k: int = 20,
) -> list[dict]:
    """Get candidates ranked by semantic similarity to a job.

    If *candidate_ids* is provided, only those candidates are ranked.
    Otherwise all candidates in the vector store are considered.
    """
    results = vectorstore.search_candidates_for_job(
        job_id=job_id, n_results=top_k,
    )

    if candidate_ids:
        id_set = set(candidate_ids)
        results = [r for r in results if r["candidate_id"] in id_set]

    return results


def match_candidate_to_job(cfg: Config, job_id: str, candidate_id: str) -> dict:
    """Detailed LLM-based matching of one candidate against one job.

    Returns ``{"score": float, "strengths": list, "gaps": list, "reasoning": str}``.
    """
    job = db.get_job(job_id)
    candidate = db.get_candidate(candidate_id)
    if not job or not candidate:
        return {"score": 0.0, "strengths": [], "gaps": [], "reasoning": "Record not found"}

    skills = candidate.get("skills", [])
    if isinstance(skills, list):
        skills_str = ", ".join(skills)
    else:
        skills_str = str(skills)

    user_msg = (
        f"## Job Description\n{job['raw_text']}\n\n"
        f"## Candidate Profile\n"
        f"Name: {candidate['name']}\n"
        f"Title: {candidate.get('current_title', '')}\n"
        f"Skills: {skills_str}\n"
        f"Experience: {candidate.get('experience_years', 'N/A')} years\n"
        f"Summary: {candidate.get('resume_summary', '')}\n"
    )

    try:
        data = chat_json(cfg, system=MATCHING, messages=[{"role": "user", "content": user_msg}])
    except Exception as e:
        log.error("LLM matching call failed: %s", e)
        return {"score": 0.0, "strengths": [], "gaps": [], "reasoning": f"LLM error: {e}"}

    if isinstance(data, list):
        data = data[0] if data else {}

    return {
        "score": float(data.get("score", 0.0)),
        "strengths": data.get("strengths", []),
        "gaps": data.get("gaps", []),
        "reasoning": data.get("reasoning", ""),
    }
