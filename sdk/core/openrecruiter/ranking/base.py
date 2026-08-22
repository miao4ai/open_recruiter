"""The ranking extension point.

Everything that decides *which candidates come first* implements this one
method. That is what lets the same application run on a plain vector search, on
an LLM reranker, or on a trained model, without anything upstream changing.

Shipped in this package:

    EmbeddingRanker   vector similarity — the default, no local model, no GPU
    APIRanker         an LLM scores each candidate and explains itself
    TwoStageRanker    retrieve with one, rerank the shortlist with another

Not shipped here:

    LocalSLMRanker    a distilled ranking model, in `recruitgpt`
    FairnessRanker    bias-aware reranking, in `openrecruiter_fairness`

Both live in their own distributions so their dependencies stay out of a normal
install, and both must lazy-load: nothing may be downloaded until a user has
actually selected that backend.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from openrecruiter.types import Candidate, Job, Match


@runtime_checkable
class Ranker(Protocol):
    """Order candidates for a job.

    Implementations return `Match` objects sorted best-first and no longer than
    `top_k`. Returning fewer is normal; raising is not — a ranker that cannot
    answer should return an empty list so a caller can fall back.
    """

    name: str

    def rank(self, job: Job, candidates: list[Candidate], top_k: int = 20) -> list[Match]: ...


__all__ = ["Ranker"]
