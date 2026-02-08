"""Matching Agent — scores candidates against job descriptions."""

from __future__ import annotations

from open_recruiter.config import Config
from open_recruiter.llm import chat_json
from open_recruiter.prompts import MATCHING_AGENT
from open_recruiter.schemas import Candidate, JobDescription, MatchResult


def match_candidate(config: Config, jd: JobDescription, candidate: Candidate) -> MatchResult:
    """Score a single candidate against a job description."""
    prompt = (
        f"Job Description:\n"
        f"Title: {jd.title}\n"
        f"Company: {jd.company}\n"
        f"Requirements: {', '.join(jd.requirements)}\n"
        f"Nice-to-have: {', '.join(jd.nice_to_have)}\n"
        f"Summary: {jd.summary}\n\n"
        f"Candidate:\n"
        f"Name: {candidate.name}\n"
        f"Skills: {', '.join(candidate.skills)}\n"
        f"Experience: {candidate.experience_years} years\n"
        f"Summary: {candidate.summary}"
    )

    data = chat_json(
        config,
        system=MATCHING_AGENT,
        messages=[{"role": "user", "content": prompt}],
    )

    return MatchResult(
        candidate_id=candidate.id,
        jd_id=jd.id,
        score=float(data.get("score", 0)),
        strengths=data.get("strengths", []),
        gaps=data.get("gaps", []),
        reasoning=data.get("reasoning", ""),
    )


def rank_candidates(
    config: Config, jd: JobDescription, candidates: list[Candidate]
) -> list[MatchResult]:
    """Score and rank all candidates against a JD, highest first."""
    results = [match_candidate(config, jd, c) for c in candidates]
    results.sort(key=lambda r: r.score, reverse=True)
    return results
