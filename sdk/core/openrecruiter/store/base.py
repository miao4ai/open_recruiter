"""Storage protocols.

The SDK ships working implementations, but it depends only on these protocols.
That is what lets an existing application keep its own database: implement the
handful of methods below over whatever schema you already have, pass it in, and
nothing above the store layer changes. It also keeps the SDK's own schema small
enough to read in one sitting.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from openrecruiter.types import Candidate, CandidateStatus, Job, Match


@runtime_checkable
class Store(Protocol):
    """Where jobs, candidates, and match results live."""

    def add_job(self, job: Job) -> Job: ...

    def get_job(self, job_id: str) -> Job | None: ...

    def list_jobs(self, limit: int = 100) -> list[Job]: ...

    def add_candidate(self, candidate: Candidate) -> Candidate: ...

    def get_candidate(self, candidate_id: str) -> Candidate | None: ...

    def list_candidates(self, limit: int = 100) -> list[Candidate]: ...

    def set_candidate_status(self, candidate_id: str, status: CandidateStatus) -> bool: ...

    def save_match(self, match: Match) -> None: ...

    def list_matches(self, job_id: str) -> list[Match]: ...


@runtime_checkable
class VectorIndex(Protocol):
    """Semantic retrieval over jobs and candidates.

    Implementations return `(id, score)` with score in [0, 1], higher is better,
    already sorted. Anything that cannot produce embeddings should behave like
    `NullVectorIndex` rather than raising — retrieval degrading to keyword
    search is a usable product; a crash is not.
    """

    @property
    def available(self) -> bool: ...

    def index_job(self, job: Job) -> None: ...

    def index_candidate(self, candidate: Candidate) -> None: ...

    def remove_job(self, job_id: str) -> None: ...

    def remove_candidate(self, candidate_id: str) -> None: ...

    def search_candidates(self, job: Job, top_k: int = 20) -> list[tuple[str, float]]: ...

    def search_jobs(self, candidate: Candidate, top_k: int = 10) -> list[tuple[str, float]]: ...


class NullVectorIndex:
    """The no-embeddings fallback.

    Used when no embedding key is configured. Indexing is a no-op and searches
    return nothing, which callers must already handle — a fresh install has an
    empty index anyway.
    """

    @property
    def available(self) -> bool:
        return False

    def index_job(self, job: Job) -> None:  # noqa: D102
        return None

    def index_candidate(self, candidate: Candidate) -> None:  # noqa: D102
        return None

    def remove_job(self, job_id: str) -> None:  # noqa: D102
        return None

    def remove_candidate(self, candidate_id: str) -> None:  # noqa: D102
        return None

    def search_candidates(self, job: Job, top_k: int = 20) -> list[tuple[str, float]]:  # noqa: D102
        return []

    def search_jobs(self, candidate: Candidate, top_k: int = 10) -> list[tuple[str, float]]:  # noqa: D102
        return []


__all__ = ["NullVectorIndex", "Store", "VectorIndex"]
