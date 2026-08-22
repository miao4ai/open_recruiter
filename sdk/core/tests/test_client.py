"""The facade — what `pip install openrecruiter` actually gives you."""

from __future__ import annotations

import pytest

from openrecruiter import Recruiter
from openrecruiter.config import Config
from openrecruiter.ranking.api import APIRanker
from openrecruiter.ranking.two_stage import TwoStageRanker
from openrecruiter.store.base import NullVectorIndex
from openrecruiter.tools.base import Tool
from openrecruiter.types import CandidateStatus

from conftest import FakeIndex, FakeLLM


def _client(tmp_path, llm=None, index=None, **kw):
    r = Recruiter(Config(anthropic_api_key="test"), data_dir=tmp_path, index=index, **kw)
    if llm is not None:
        r.llm = llm
        for ranker in (r.ranker, getattr(r.ranker, "reranker", None)):
            if isinstance(ranker, APIRanker):
                ranker.llm = llm
    return r


# ── construction ─────────────────────────────────────────────────────────


def test_without_an_embedding_key_retrieval_is_disabled_not_broken(tmp_path):
    r = Recruiter(Config(anthropic_api_key="test"), data_dir=tmp_path)

    assert isinstance(r.index, NullVectorIndex)
    assert isinstance(r.ranker, APIRanker), "falls back to reranking directly"


def test_with_an_embedding_key_ranking_becomes_two_stage(tmp_path):
    r = Recruiter(
        Config(anthropic_api_key="test", voyage_api_key="pa-test"), data_dir=tmp_path
    )
    assert isinstance(r.ranker, TwoStageRanker)


def test_importing_the_package_downloads_nothing(tmp_path):
    """A user without a GPU, or on a plane, must still get a working object."""
    import sys

    Recruiter(Config(anthropic_api_key="test"), data_dir=tmp_path)

    assert "torch" not in sys.modules
    assert "transformers" not in sys.modules


def test_the_built_in_tools_are_registered(tmp_path):
    r = _client(tmp_path)

    for name in ("list_jobs", "rank_candidates", "draft_email", "create_candidate"):
        assert name in r.tools


def test_hosts_can_add_their_own_tools(tmp_path):
    extra = Tool(name="check_inbox", description="Read the recruiter's mail", fn=lambda: [])
    r = _client(tmp_path, extra_tools=[extra])

    assert "check_inbox" in r.tools
    assert "list_jobs" in r.tools


# ── ingest ───────────────────────────────────────────────────────────────


def test_add_job_parses_stores_and_indexes(tmp_path):
    index = FakeIndex()
    llm = FakeLLM(json_response={
        "title": "Senior CUDA Engineer",
        "company": "Acme",
        "required_skills": ["CUDA", "NCCL"],
        "experience_years": "5",
        "remote": True,
        "summary": "Scale training.",
    })
    r = _client(tmp_path, llm=llm, index=index)

    job = r.add_job("We need a CUDA engineer.")

    assert job.title == "Senior CUDA Engineer"
    assert job.required_skills == ["CUDA", "NCCL"]
    assert job.experience_years == 5, "string years are coerced"
    assert job.remote is True
    assert job.raw_text == "We need a CUDA engineer."
    assert r.store.get_job(job.id) is not None
    assert index.indexed_jobs == [job]


def test_add_candidate_parses_stores_and_indexes(tmp_path):
    index = FakeIndex()
    llm = FakeLLM(json_response={
        "name": "Ada",
        "email": "ada@example.com",
        "skills": ["CUDA"],
        "experience_years": 8,
        "resume_summary": "Scaled training.",
    })
    r = _client(tmp_path, llm=llm, index=index)

    c = r.add_candidate("Ada, ML systems.")

    assert c.name == "Ada"
    assert c.email == "ada@example.com"
    assert r.store.get_candidate(c.id).skills == ["CUDA"]
    assert index.indexed_candidates == [c]


def test_a_parse_that_returns_nothing_still_produces_a_record(tmp_path):
    """Never lose the raw text because the model returned junk."""
    r = _client(tmp_path, llm=FakeLLM(json_response="not a dict"), index=FakeIndex())

    job = r.add_job("raw jd text")

    assert job.title == ""
    assert job.raw_text == "raw jd text"


# ── ranking ──────────────────────────────────────────────────────────────


def test_rank_scores_the_pool_and_persists_the_result(tmp_path):
    llm = FakeLLM(json_response={"score": 0.8, "strengths": ["CUDA"], "reasoning": "fits"})
    r = _client(tmp_path, llm=llm, index=FakeIndex(available=False))

    r.llm = FakeLLM(json_response={"name": "Ada", "skills": ["CUDA"]})
    candidate = r.add_candidate("Ada")
    r.llm = FakeLLM(json_response={"title": "CUDA Eng"})
    job = r.add_job("jd")
    r.ranker = APIRanker(llm)

    matches = r.rank(job.id)

    assert matches[0].candidate_id == candidate.id
    assert matches[0].score == 0.8
    assert r.store.list_matches(job.id)[0].score == 0.8, "results are saved, not just returned"


def test_ranking_an_unknown_job_returns_nothing(tmp_path):
    assert _client(tmp_path, llm=FakeLLM()).rank("ghost") == []


def test_match_reports_missing_records_instead_of_guessing(tmp_path):
    result = _client(tmp_path, llm=FakeLLM()).match("nobody", "nowhere")

    assert result.score == 0.0
    assert "not found" in result.reasoning


def test_search_candidates_resolves_hits_to_records(tmp_path):
    r = _client(tmp_path, llm=FakeLLM(json_response={"name": "Ada"}), index=FakeIndex())
    c = r.add_candidate("Ada")
    r.index.hits = [(c.id, 0.83), ("vanished", 0.5)]

    found = r.search_candidates("distributed training")

    assert found == [(c, 0.83)], "an id with no record is skipped, not returned as None"


# ── status and outreach ──────────────────────────────────────────────────


def test_set_status_accepts_a_string_and_rejects_nonsense(tmp_path):
    r = _client(tmp_path, llm=FakeLLM(json_response={"name": "Ada"}), index=FakeIndex())
    c = r.add_candidate("Ada")

    assert r.set_status(c.id, "interviewing") is True
    assert r.store.get_candidate(c.id).status is CandidateStatus.INTERVIEWING
    assert r.set_status(c.id, "promoted-to-cto") is False


def test_draft_email_uses_the_candidate_and_the_job(tmp_path):
    index = FakeIndex()
    r = _client(tmp_path, llm=FakeLLM(json_response={"name": "Ada", "skills": ["CUDA"]}), index=index)
    c = r.add_candidate("Ada")
    r.llm = FakeLLM(json_response={"title": "CUDA Eng", "company": "Acme"})
    job = r.add_job("jd")

    drafting = FakeLLM(json_response={"subject": "CUDA role at Acme", "body": "Hi Ada,"})
    r.llm = drafting
    draft = r.draft_email(c.id, job_id=job.id, instructions="be brief")

    assert draft.subject == "CUDA role at Acme"
    assert draft.candidate_id == c.id
    prompt = drafting.calls[0]["messages"][0]["content"]
    assert "Ada" in prompt and "Acme" in prompt and "be brief" in prompt


def test_drafting_for_an_unknown_candidate_returns_an_empty_draft(tmp_path):
    draft = _client(tmp_path, llm=FakeLLM()).draft_email("ghost")

    assert draft.subject == ""
    assert draft.candidate_id == "ghost"


# ── agent ────────────────────────────────────────────────────────────────


def test_chat_drives_the_tools_the_client_owns(tmp_path):
    r = _client(tmp_path, llm=FakeLLM(json_response={"title": "CUDA Eng"}), index=FakeIndex())
    job = r.add_job("jd")

    from openrecruiter.events import ToolResult

    r.llm = FakeLLM([[("list_jobs", {})], "You have one open role."])
    events = list(r.chat("what am I hiring for?"))

    result = next(e for e in events if isinstance(e, ToolResult))
    assert result.result[0]["id"] == job.id
    assert events[-1].stop_reason == "end_turn"


def test_ask_returns_just_the_text(tmp_path):
    r = _client(tmp_path, llm=FakeLLM(["the answer"]))
    assert r.ask("question").strip() == "the answer"
