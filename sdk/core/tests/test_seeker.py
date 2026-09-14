"""The job-seeker tools.

The card shape is a contract with the connectors that render it, so most of what
is checked here is shape: the keys, the string-valued `fields`, and the single
JSON string rather than a Python list. The rest is the part a seeker feels — a
role or a city typed in their own language has to find postings written in
English.
"""

from __future__ import annotations

import json

import pytest

from openrecruiter import Config, Recruiter
from openrecruiter.store.base import NullVectorIndex
from openrecruiter.tools.seeker import (
    SEEKER_WRITE_TOOLS,
    build_seeker_tools,
    english_roles,
    job_card,
    normalise_location,
    transient_candidate,
)
from openrecruiter.types import Job

from tests.conftest import FakeIndex


JOBS = [
    Job(
        id="j-ml",
        title="Machine Learning Engineer",
        company="Acme",
        location="Tokyo",
        remote=False,
        salary_range="¥12M–18M",
        required_skills=["CUDA", "NCCL", "PyTorch"],
        summary="Scale distributed training across thousands of GPUs.",
    ),
    Job(
        id="j-be",
        title="Backend Engineer",
        company="Globex",
        location="Singapore",
        remote=True,
        required_skills=["Go", "Postgres"],
        summary="Payments platform.",
    ),
    Job(id="j-des", title="Product Designer", company="Initech", location="Berlin"),
]


@pytest.fixture
def client(tmp_path):
    r = Recruiter(Config(anthropic_api_key="test-key"), index=NullVectorIndex(), data_dir=tmp_path)
    for job in JOBS:
        r.store.add_job(job)
    return r


def tools(client):
    return {t.name: t for t in build_seeker_tools(client)}


# ── the card contract ────────────────────────────────────────────────────────


def test_a_card_has_exactly_the_keys_a_connector_reads():
    card = job_card(JOBS[0], score=0.87)

    assert set(card) == {"id", "title", "subtitle", "price", "detail", "url", "fields"}
    assert card["id"] == "j-ml"
    assert card["subtitle"] == "Acme · Tokyo"
    assert card["price"] == "¥12M–18M"
    assert card["fields"]["skills"] == "CUDA, NCCL, PyTorch"
    assert card["fields"]["score"] == "0.87"


def test_every_field_value_is_a_string():
    """Connectors render `fields` as text; a bool or a float there breaks them."""
    for card in (job_card(JOBS[0], score=0.5), job_card(JOBS[1]), job_card(JOBS[2])):
        assert all(isinstance(v, str) for v in card["fields"].values()), card["fields"]


def test_remote_reaches_the_subtitle_and_the_fields():
    card = job_card(JOBS[1])
    assert card["subtitle"] == "Globex · Singapore · Remote"
    assert card["fields"]["remote"] == "true"


def test_a_search_returns_one_json_string_not_a_list(client):
    """A list would be split into one block per item by the transports that
    carry this, and a reader taking the first block would see one result."""
    out = tools(client)["search_jobs"](query="engineer")

    assert isinstance(out, str)
    assert isinstance(json.loads(out), list)


# ── a seeker's own language ──────────────────────────────────────────────────


def test_a_role_typed_in_chinese_finds_an_english_posting(client):
    """The phrase expands to machine/learning/engineer, so a Backend Engineer
    matches too — on one word instead of three, which is why order is the
    contract here and not exclusion."""
    cards = json.loads(tools(client)["search_jobs"](query="机器学习工程师"))

    assert cards[0]["id"] == "j-ml"
    assert "j-des" not in [c["id"] for c in cards]


def test_a_city_typed_in_japanese_filters_to_it(client):
    cards = json.loads(tools(client)["search_jobs"](query="engineer", location="東京"))
    assert [c["id"] for c in cards] == ["j-ml"]


def test_remote_in_any_of_the_three_languages_matches_remote_jobs(client):
    for word in ("remote", "远程", "リモート"):
        cards = json.loads(tools(client)["search_jobs"](query="engineer", location=word))
        assert [c["id"] for c in cards] == ["j-be"], word


def test_a_location_meaning_anywhere_does_not_filter(client):
    """"任意" is a seeker saying they do not care, not a place called 任意."""
    assert normalise_location("任意") == ""
    cards = json.loads(tools(client)["search_jobs"](query="engineer", location="任意"))
    assert {c["id"] for c in cards} == {"j-ml", "j-be"}


def test_the_longest_role_phrase_wins():
    """机器学习工程师 must not be split into 机器学习 + 工程师 first."""
    assert "machine learning engineer" in english_roles("机器学习工程师")


def test_an_empty_query_lists_what_is_open(client):
    cards = json.loads(tools(client)["search_jobs"]())
    assert len(cards) == 3


# ── retrieval ────────────────────────────────────────────────────────────────


def test_search_goes_through_the_index_when_one_is_available(tmp_path):
    """Meaning first: with embeddings configured the query is a vector search,
    so a phrasing that shares no keyword with the posting still finds it."""
    index = FakeIndex(hits=[("j-ml", 0.91)])
    r = Recruiter(Config(anthropic_api_key="k"), index=index, data_dir=tmp_path)
    for job in JOBS:
        r.store.add_job(job)

    cards = json.loads(tools(r)["search_jobs"](query="someone who scales GPU training"))

    assert [c["id"] for c in cards] == ["j-ml"]
    assert cards[0]["fields"]["score"] == "0.91"


def test_the_location_filter_still_applies_to_semantic_hits(tmp_path):
    index = FakeIndex(hits=[("j-ml", 0.91), ("j-be", 0.80)])
    r = Recruiter(Config(anthropic_api_key="k"), index=index, data_dir=tmp_path)
    for job in JOBS:
        r.store.add_job(job)

    cards = json.loads(tools(r)["search_jobs"](query="engineer", location="singapore"))

    assert [c["id"] for c in cards] == ["j-be"]


def test_recommend_is_empty_without_embeddings_rather_than_wrong(client):
    assert tools(client)["recommend_jobs"](resume_text="CUDA and NCCL at scale") == "[]"


def test_recommend_ranks_by_similarity(tmp_path):
    index = FakeIndex(hits=[("j-be", 0.77), ("j-ml", 0.64)])
    r = Recruiter(Config(anthropic_api_key="k"), index=index, data_dir=tmp_path)
    for job in JOBS:
        r.store.add_job(job)

    cards = json.loads(tools(r)["recommend_jobs"](resume_text="Go and Postgres"))

    assert [c["id"] for c in cards] == ["j-be", "j-ml"]
    assert cards[0]["fields"]["score"] == "0.77"


def test_a_resume_is_embedded_from_its_summary(tmp_path):
    """`embed_text` reads summary/skills/title and ignores raw_resume_text, so
    a résumé parked only in the raw field embeds to nothing."""
    assert transient_candidate("CUDA at scale").embed_text()


# ── applying ─────────────────────────────────────────────────────────────────


def test_applying_puts_the_seeker_in_the_pipeline(client):
    out = json.loads(
        tools(client)["apply_to_job"](
            job_id="j-ml", resume_text="Ada Lovelace — CUDA, NCCL.", name="Ada", source="charbit"
        )
    )

    assert out["ok"] and out["title"] == "Machine Learning Engineer"
    candidate = client.store.get_candidate(out["candidate_id"])
    assert candidate is not None and candidate.name == "Ada"

    # The link the recruiter side reads back.
    matches = client.store.list_matches("j-ml")
    assert [m.candidate_id for m in matches] == [out["candidate_id"]]
    assert "applied via charbit" in matches[0].reasoning


def test_applying_does_not_need_a_model_key(tmp_path):
    """`add_candidate` would parse the résumé with a model first. An application
    must not fail because nobody configured one."""
    r = Recruiter(Config(), index=NullVectorIndex(), data_dir=tmp_path)
    r.store.add_job(JOBS[0])

    out = json.loads(tools(r)["apply_to_job"](job_id="j-ml", resume_text="CUDA."))

    assert out["ok"]


def test_applying_to_a_job_that_is_not_there_says_so(client):
    out = json.loads(tools(client)["apply_to_job"](job_id="nope", resume_text="CUDA."))
    assert out["ok"] is False and "nope" in out["message"]


def test_an_empty_resume_is_refused(client):
    out = json.loads(tools(client)["apply_to_job"](job_id="j-ml", resume_text="   "))
    assert out["ok"] is False


def test_a_failed_index_does_not_lose_the_application(client, monkeypatch):
    """Retrieval is a bonus; the application is the point."""
    monkeypatch.setattr(
        client.index,
        "index_candidate",
        lambda c: (_ for _ in ()).throw(RuntimeError("401")),
    )
    out = json.loads(tools(client)["apply_to_job"](job_id="j-ml", resume_text="CUDA."))
    assert out["ok"]


# ── the two sets stay apart ──────────────────────────────────────────────────


def test_a_seeker_never_sees_the_recruiters_tools(client):
    """The reason this is a separate set: a seeker's assistant has no business
    moving candidates through someone else's pipeline."""
    seeker = set(tools(client))
    recruiter = set(client.tools.names())

    assert seeker & recruiter == set()
    assert "set_candidate_status" not in seeker and "draft_email" not in seeker


def test_applying_is_the_only_write_and_is_marked_as_one(client):
    by_name = tools(client)
    assert SEEKER_WRITE_TOOLS == {"apply_to_job"}
    assert by_name["apply_to_job"].requires_approval
    assert not any(by_name[n].requires_approval for n in by_name if n != "apply_to_job")
