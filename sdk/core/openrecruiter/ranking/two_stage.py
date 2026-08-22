"""Retrieve broadly, then rerank the shortlist.

This is the architecture the ranking research is aimed at: the first stage
optimises recall over the whole pool, the second optimises relevance over a few
hundred candidates. Splitting them is what makes an expensive reranker
affordable — and it is why the reranker is a swappable `Ranker` rather than a
hardcoded LLM call.

    all candidates ──▶ retriever ──▶ shortlist ──▶ reranker ──▶ ordered results
                       (cheap)        100–500       (costly)
"""

from __future__ import annotations

from openrecruiter.ranking.base import Ranker
from openrecruiter.types import Candidate, Job, Match


class TwoStageRanker:
    """Compose a cheap retriever with a costly reranker."""

    def __init__(
        self,
        retriever: Ranker,
        reranker: Ranker,
        shortlist: int = 50,
    ) -> None:
        self.retriever = retriever
        self.reranker = reranker
        self.shortlist = shortlist
        self.name = f"two_stage({retriever.name}->{reranker.name})"

    def rank(self, job: Job, candidates: list[Candidate], top_k: int = 20) -> list[Match]:
        if not candidates:
            return []

        retrieved = self.retriever.rank(job, candidates, top_k=self.shortlist)
        if not retrieved:
            # An empty first stage usually means no embeddings are configured.
            # Reranking everything is expensive but correct; the caller chose a
            # two-stage ranker because it wants the reranker's judgement.
            return self.reranker.rank(job, candidates, top_k=top_k)

        by_id = {c.id: c for c in candidates}
        shortlist = [by_id[m.candidate_id] for m in retrieved if m.candidate_id in by_id]
        matches = self.reranker.rank(job, shortlist, top_k=top_k)

        # Keep the retrieval score alongside the rerank score — comparing the two
        # is how you tell whether the reranker is earning its cost.
        retrieval_scores = {m.candidate_id: m.score for m in retrieved}
        for m in matches:
            m.ranker = f"{self.name} retrieval={retrieval_scores.get(m.candidate_id, 0.0)}"
        return matches


__all__ = ["TwoStageRanker"]
