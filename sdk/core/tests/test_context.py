"""The briefing the model gets before it starts.

The failure this guards against is the obvious implementation: paste the
pipeline into the prompt and watch it break at scale.
"""

from __future__ import annotations

from openrecruiter.context import build_pipeline_context
from openrecruiter.types import Candidate, CandidateStatus, Job

from conftest import FakeIndex


def _many(n: int) -> list[Candidate]:
    return [Candidate(id=f"c{i}", name=f"Person {i}", skills=["Python"]) for i in range(n)]


class MemoryStore:
    def __init__(self, jobs=None, candidates=None):
        self._jobs = jobs or []
        self._candidates = candidates or []

    def list_jobs(self, limit=100): return self._jobs[:limit]
    def list_candidates(self, limit=100): return self._candidates[:limit]
    def add_job(self, job): ...
    def get_job(self, job_id): ...
    def add_candidate(self, c): ...
    def get_candidate(self, cid): ...
    def set_candidate_status(self, cid, status): ...
    def save_match(self, m): ...
    def list_matches(self, job_id): return []


def test_an_empty_pipeline_says_so(job):
    assert "empty" in build_pipeline_context(MemoryStore()).lower()


def test_jobs_are_listed_with_their_ids_and_skills(job):
    text = build_pipeline_context(MemoryStore(jobs=[job]))

    assert "[job1] Senior CUDA Engineer at Acme" in text
    assert "needs CUDA, PyTorch, NCCL" in text


def test_the_pipeline_distribution_is_included(candidates):
    candidates[0].status = CandidateStatus.INTERVIEWING
    text = build_pipeline_context(MemoryStore(candidates=candidates))

    assert "## Pipeline (2 candidates)" in text
    assert "- interviewing: 1" in text
    assert "- new: 1" in text


def test_the_context_does_not_grow_with_the_candidate_pool():
    """500 candidates must not mean a 500-line prompt."""
    small = build_pipeline_context(MemoryStore(candidates=_many(10)))
    large = build_pipeline_context(MemoryStore(candidates=_many(500)))

    assert large.count("\n- [c") <= 8
    assert abs(len(large) - len(small)) < 400, "the briefing is bounded, not proportional"
    assert "500 candidates" in large, "but the model is still told the real size"


def test_with_retrieval_the_named_candidates_are_the_relevant_ones():
    pool = _many(50)
    index = FakeIndex([("c42", 0.9), ("c7", 0.8)])

    text = build_pipeline_context(MemoryStore(candidates=pool), index, "who has done CUDA work?")

    assert "related to this message" in text
    assert "[c42] Person 42" in text
    assert "[c7] Person 7" in text
    assert "[c0]" not in text, "an arbitrary slice is what this replaces"


def test_without_retrieval_it_falls_back_to_the_most_recent():
    text = build_pipeline_context(MemoryStore(candidates=_many(50)), FakeIndex(available=False), "cuda")

    assert "Most recent candidates" in text
    assert "[c0] Person 0" in text


def test_retrieval_returning_nothing_falls_back_rather_than_showing_none():
    text = build_pipeline_context(MemoryStore(candidates=_many(5)), FakeIndex([]), "cuda")

    assert "Most recent candidates" in text
    assert "[c0]" in text


def test_hits_for_candidates_that_no_longer_exist_are_skipped():
    """A stale index entry must not become a phantom name in the prompt."""
    index = FakeIndex([("deleted", 0.99), ("c1", 0.7)])

    text = build_pipeline_context(MemoryStore(candidates=_many(3)), index, "cuda")

    assert "[c1] Person 1" in text
    assert "deleted" not in text


def test_the_model_is_told_how_to_reach_everyone_else():
    text = build_pipeline_context(MemoryStore(candidates=_many(50)), FakeIndex([("c1", 0.9)]), "x")

    assert "search_candidates" in text and "get_candidate" in text
