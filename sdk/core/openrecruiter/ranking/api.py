"""An LLM reads each candidate against the job and scores the fit.

Far more expensive than embedding similarity and far more informative: it
returns the strengths and the gaps, which is what a recruiter actually needs in
order to act. Use it on a shortlist, not on the whole pool — see
`TwoStageRanker`.
"""

from __future__ import annotations

import logging

from openrecruiter.prompts import MATCHING
from openrecruiter.providers.llm import LLM, LLMError
from openrecruiter.types import Candidate, Job, Match

log = logging.getLogger(__name__)


class APIRanker:
    """Score candidates with a hosted LLM, one call per candidate."""

    name = "api"

    def __init__(self, llm: LLM, system: str = MATCHING) -> None:
        self.llm = llm
        self.system = system

    def rank(self, job: Job, candidates: list[Candidate], top_k: int = 20) -> list[Match]:
        matches = [self.score(job, c) for c in candidates]
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:top_k]

    def score(self, job: Job, candidate: Candidate) -> Match:
        """Judge one candidate. A failed call scores 0 and says why."""
        prompt = (
            f"## Job Description\n{job.raw_text or job.summary}\n\n"
            f"## Candidate Profile\n{candidate.profile_text()}"
        )
        try:
            data = self.llm.complete_json(self.system, [{"role": "user", "content": prompt}])
        except (LLMError, ValueError) as exc:
            log.warning("APIRanker could not score %s: %s", candidate.id, exc)
            return Match(
                candidate_id=candidate.id,
                job_id=job.id,
                reasoning=f"Scoring failed: {exc}",
                ranker=self.name,
            )

        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            data = {}

        return Match(
            candidate_id=candidate.id,
            job_id=job.id,
            score=_clamp(data.get("score")),
            strengths=list(data.get("strengths") or []),
            gaps=list(data.get("gaps") or []),
            reasoning=str(data.get("reasoning") or ""),
            ranker=self.name,
        )


def _clamp(value: object) -> float:
    """Coerce whatever the model returned into a 0-1 score.

    One rule, no thresholds: anything above 1 was meant as a percentage, so it
    is divided by 100 and then clamped. That reads 85 as 0.85, which is the
    common case, and reads a stray 1.5 as 0.015 rather than as a perfect fit —
    the safer direction to be wrong in when the output ranks people.
    """
    try:
        score = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if score > 1.0:
        score /= 100.0
    return round(max(0.0, min(1.0, score)), 4)


__all__ = ["APIRanker"]
