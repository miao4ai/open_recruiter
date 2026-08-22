"""Rankers, and the two-stage composition the ranking research targets."""

from __future__ import annotations

import pytest

from openrecruiter.ranking.api import APIRanker, _clamp
from openrecruiter.ranking.base import Ranker
from openrecruiter.ranking.embedding import EmbeddingRanker
from openrecruiter.ranking.two_stage import TwoStageRanker

from conftest import FakeIndex, FakeLLM


def test_shipped_rankers_satisfy_the_protocol():
    assert isinstance(EmbeddingRanker(FakeIndex()), Ranker)
    assert isinstance(APIRanker(FakeLLM()), Ranker)


# ── embedding ────────────────────────────────────────────────────────────


def test_embedding_ranker_orders_by_similarity(job, candidates):
    ranker = EmbeddingRanker(FakeIndex([("c2", 0.42), ("c1", 0.88)]))
    matches = ranker.rank(job, candidates)

    assert [m.candidate_id for m in matches] == ["c2", "c1"]
    assert matches[0].ranker == "embedding"


def test_embedding_ranker_ignores_hits_outside_the_given_pool(job, candidates):
    """The index holds everyone; the caller may have narrowed the pool."""
    ranker = EmbeddingRanker(FakeIndex([("stranger", 0.99), ("c1", 0.5)]))
    matches = ranker.rank(job, candidates)

    assert [m.candidate_id for m in matches] == ["c1"]


def test_embedding_ranker_respects_top_k(job, candidates):
    ranker = EmbeddingRanker(FakeIndex([("c1", 0.9), ("c2", 0.8)]))
    assert len(ranker.rank(job, candidates, top_k=1)) == 1


def test_empty_pool_and_empty_index_both_yield_nothing(job, candidates):
    assert EmbeddingRanker(FakeIndex([("c1", 0.9)])).rank(job, []) == []
    assert EmbeddingRanker(FakeIndex([])).rank(job, candidates) == []


# ── api ──────────────────────────────────────────────────────────────────


def test_api_ranker_returns_strengths_and_gaps(job, candidates):
    llm = FakeLLM(json_response={
        "score": 0.9,
        "strengths": ["Has shipped NCCL at scale"],
        "gaps": ["No Triton"],
        "reasoning": "Direct match on the hard requirement.",
    })
    match = APIRanker(llm).score(job, candidates[0])

    assert match.score == 0.9
    assert match.strengths == ["Has shipped NCCL at scale"]
    assert match.gaps == ["No Triton"]
    assert match.ranker == "api"


def test_api_ranker_sorts_best_first(job, candidates):
    llm = FakeLLM(json_response=[{"score": 0.2}, {"score": 0.95}])
    matches = APIRanker(llm).rank(job, candidates)

    assert [m.score for m in matches] == [0.95, 0.2]


def test_a_scoring_failure_scores_zero_and_says_why(job, candidates):
    from openrecruiter.providers.llm import LLMError

    class Broken(FakeLLM):
        def complete_json(self, system, messages):
            raise LLMError("model overloaded")

    match = APIRanker(Broken()).score(job, candidates[0])

    assert match.score == 0.0
    assert "model overloaded" in match.reasoning


def test_the_prompt_carries_the_job_and_the_candidate(job, candidates):
    llm = FakeLLM(json_response={"score": 0.5})
    APIRanker(llm).score(job, candidates[0])

    prompt = llm.calls[0]["messages"][0]["content"]
    assert job.raw_text in prompt
    assert "Ada" in prompt
    assert "CUDA" in prompt


def test_the_matching_prompt_forbids_protected_characteristics():
    from openrecruiter.prompts import MATCHING

    lowered = MATCHING.lower()
    assert "protected characteristic" in lowered
    for attribute in ("age", "gender", "nationality", "ethnicity"):
        assert attribute in lowered


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0.85, 0.85),
        (85, 0.85),          # models answer on a 0-100 scale often enough to matter
        (150, 1.0),          # rescaled, then clamped
        (1.5, 0.015),        # out of range: read as a percentage, not a perfect fit
        (-3, 0.0),
        ("0.7", 0.7),
        ("high", 0.0),
        (None, 0.0),
    ],
)
def test_scores_are_clamped_into_range(raw, expected):
    assert _clamp(raw) == expected


# ── two stage ────────────────────────────────────────────────────────────


def test_two_stage_reranks_only_the_shortlist(job, candidates):
    """The point of the split: the costly stage sees a few, not everyone."""
    from openrecruiter.types import Match

    seen: list[list[str]] = []

    class CountingReranker:
        name = "counting"

        def rank(self, job, candidates, top_k=20):
            seen.append([c.id for c in candidates])
            return [
                Match(candidate_id=c.id, job_id=job.id, score=0.5, ranker=self.name)
                for c in candidates
            ]

    ranker = TwoStageRanker(EmbeddingRanker(FakeIndex([("c1", 0.9)])), CountingReranker())
    ranker.rank(job, candidates)

    assert seen == [["c1"]], "c2 was not retrieved, so it must not be reranked"


def test_two_stage_keeps_the_retrieval_score_for_comparison(job, candidates):
    llm = FakeLLM(json_response={"score": 0.77})
    ranker = TwoStageRanker(EmbeddingRanker(FakeIndex([("c1", 0.62)])), APIRanker(llm))

    match = ranker.rank(job, candidates)[0]

    assert match.score == 0.77
    assert "retrieval=0.62" in match.ranker


def test_two_stage_falls_back_when_retrieval_returns_nothing(job, candidates):
    """No embeddings configured must not mean no results."""
    llm = FakeLLM(json_response=[{"score": 0.3}, {"score": 0.6}])
    ranker = TwoStageRanker(EmbeddingRanker(FakeIndex([])), APIRanker(llm))

    matches = ranker.rank(job, candidates)

    assert [m.score for m in matches] == [0.6, 0.3]


def test_two_stage_names_both_of_its_halves(job):
    ranker = TwoStageRanker(EmbeddingRanker(FakeIndex()), APIRanker(FakeLLM()))
    assert ranker.name == "two_stage(embedding->api)"
