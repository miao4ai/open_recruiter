"""The default ranker: vector similarity, nothing local.

Fast and cheap enough to run over the whole candidate pool, which is exactly
what makes it the right first stage — it optimises recall, and something more
expensive decides the final order.
"""

from __future__ import annotations

from openrecruiter.store.base import VectorIndex
from openrecruiter.types import Candidate, Job, Match


class EmbeddingRanker:
    """Rank by embedding similarity between the job and each candidate."""

    name = "embedding"

    def __init__(self, index: VectorIndex) -> None:
        self.index = index

    def rank(self, job: Job, candidates: list[Candidate], top_k: int = 20) -> list[Match]:
        if not candidates:
            return []

        allowed = {c.id for c in candidates}
        # Over-fetch: the index holds every candidate, but the caller may have
        # narrowed the pool, and filtering after the query would truncate it.
        hits = self.index.search_candidates(job, top_k=max(top_k * 4, top_k))

        matches = [
            Match(candidate_id=cid, job_id=job.id, score=score, ranker=self.name)
            for cid, score in hits
            if cid in allowed
        ]
        return matches[:top_k]


__all__ = ["EmbeddingRanker"]
