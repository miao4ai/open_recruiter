"""The default store must round-trip everything the domain types carry."""

from __future__ import annotations

import pytest

from openrecruiter.store.base import NullVectorIndex, Store, VectorIndex
from openrecruiter.store.sqlite import SQLiteStore
from openrecruiter.types import Candidate, CandidateStatus, Job, Match


def test_sqlite_store_satisfies_the_protocol(store):
    assert isinstance(store, Store)


def test_null_index_satisfies_the_protocol():
    assert isinstance(NullVectorIndex(), VectorIndex)


def test_job_round_trips_with_lists_and_booleans(store, job):
    job.remote = True
    store.add_job(job)
    loaded = store.get_job(job.id)

    assert loaded is not None
    assert loaded.title == job.title
    assert loaded.required_skills == ["CUDA", "PyTorch", "NCCL"]
    assert loaded.remote is True
    assert loaded.raw_text == job.raw_text


def test_candidate_round_trips_including_status_enum(store, candidates):
    original = candidates[0]
    original.status = CandidateStatus.INTERVIEWING
    store.add_candidate(original)

    loaded = store.get_candidate(original.id)
    assert loaded is not None
    assert loaded.skills == ["CUDA", "NCCL", "PyTorch"]
    assert loaded.status is CandidateStatus.INTERVIEWING
    assert loaded.experience_years == 8


def test_missing_records_return_none(store):
    assert store.get_job("nope") is None
    assert store.get_candidate("nope") is None


def test_add_is_idempotent_on_id(store, job):
    store.add_job(job)
    job.title = "Renamed"
    store.add_job(job)

    assert len(store.list_jobs()) == 1
    assert store.get_job(job.id).title == "Renamed"


def test_set_candidate_status(store, candidates):
    store.add_candidate(candidates[0])

    assert store.set_candidate_status(candidates[0].id, CandidateStatus.HIRED) is True
    assert store.get_candidate(candidates[0].id).status is CandidateStatus.HIRED
    assert store.set_candidate_status("ghost", CandidateStatus.HIRED) is False


def test_matches_come_back_sorted_by_score(store):
    for cid, score in (("c1", 0.4), ("c2", 0.9), ("c3", 0.6)):
        store.save_match(Match(candidate_id=cid, job_id="j1", score=score, ranker="test"))

    scores = [m.score for m in store.list_matches("j1")]
    assert scores == [0.9, 0.6, 0.4]


def test_saving_a_match_twice_updates_it(store):
    store.save_match(Match(candidate_id="c1", job_id="j1", score=0.2))
    store.save_match(Match(candidate_id="c1", job_id="j1", score=0.8, gaps=["no CUDA"]))

    matches = store.list_matches("j1")
    assert len(matches) == 1
    assert matches[0].score == 0.8
    assert matches[0].gaps == ["no CUDA"]


def test_store_survives_being_reopened(tmp_path, job):
    SQLiteStore(tmp_path / "p.db").add_job(job)
    assert SQLiteStore(tmp_path / "p.db").get_job(job.id) is not None


def test_list_respects_limit(store, candidates):
    for c in candidates:
        store.add_candidate(c)
    assert len(store.list_candidates(limit=1)) == 1


@pytest.mark.parametrize("field", ["skills", "required_skills"])
def test_empty_lists_survive_the_json_column(store, job, candidates, field):
    """An empty list must not come back as None and crash a join downstream."""
    if field == "required_skills":
        job.required_skills = []
        store.add_job(job)
        assert store.get_job(job.id).required_skills == []
    else:
        candidates[0].skills = []
        store.add_candidate(candidates[0])
        assert store.get_candidate(candidates[0].id).skills == []


# ── indexing must not be able to lose a record ───────────────────────────


def _index_with(monkeypatch, raises):
    from openrecruiter.config import Config
    from openrecruiter.store.vector import ChromaVectorIndex

    index = ChromaVectorIndex(lambda: Config(voyage_api_key="pa-wrong"), "/tmp/unused")
    monkeypatch.setattr(
        index, "_collection", lambda name: (_ for _ in ()).throw(raises)
    )
    return index


def test_a_bad_embedding_key_does_not_break_indexing(monkeypatch, job, candidates):
    """A wrong key must cost retrieval, not the ability to add a candidate.

    `available` only checks that a key is present, so a typo or an expired key
    reaches the API. Raising here would mean the caller loses the record to
    protect the index, which is backwards.
    """
    index = _index_with(monkeypatch, RuntimeError("401 Unauthorized"))

    index.index_job(job)                 # must not raise
    index.index_candidate(candidates[0])
    index.remove_job(job.id)
    index.remove_candidate(candidates[0].id)


def test_a_failed_index_is_logged(monkeypatch, caplog, job):
    index = _index_with(monkeypatch, RuntimeError("401 Unauthorized"))

    with caplog.at_level("WARNING"):
        index.index_job(job)

    assert "Could not index" in caplog.text
    assert "401" in caplog.text


def test_search_already_degraded_this_way(monkeypatch, job):
    index = _index_with(monkeypatch, RuntimeError("boom"))
    assert index.search_candidates(job) == []


def test_openai_compatible_embeddings_are_a_second_way_in(monkeypatch):
    """A self-hosted /v1/embeddings behind an OpenAI-shaped API makes the index
    available without a Voyage key, and the request is the OpenAI shape."""
    from openrecruiter.config import Config
    from openrecruiter.store import vector
    from openrecruiter.store.vector import ChromaVectorIndex, OpenAIEmbeddings, embedding_function

    cfg = Config(embedding_api_url="https://ai.example/v1/embeddings", embedding_api_key="k", embedding_model="bge-m3")
    assert ChromaVectorIndex(lambda: cfg, "/tmp/unused").available
    assert not ChromaVectorIndex(lambda: Config(), "/tmp/unused").available
    assert isinstance(embedding_function(lambda: cfg), OpenAIEmbeddings)

    seen = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{"index": 1, "embedding": [0.2]}, {"index": 0, "embedding": [0.1]}]}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, auth=headers["Authorization"], body=json)
        return Resp()

    monkeypatch.setattr(vector.httpx, "post", fake_post)
    out = embedding_function(lambda: cfg)(["a", "b"])
    assert out == [[0.1], [0.2]]  # back in input order
    assert seen["url"] == cfg.embedding_api_url and seen["auth"] == "Bearer k"
    assert seen["body"] == {"input": ["a", "b"], "model": "bge-m3"}
