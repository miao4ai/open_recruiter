"""The job-seeker side of the MCP server: stateless tools a chat app calls on a
user's behalf (charbit's recruiter skill), returning search cards.

The card contract is what makes this testable without a model: every tool
returns ONE JSON text block holding an array of {id, title, subtitle, …}
objects — the shape charbit's connector decodes — so the assertions are on
that JSON, not on ranking quality.
"""

from __future__ import annotations

import asyncio
import importlib
import json
from datetime import datetime, timezone

import pytest

from app import database as db


@pytest.fixture
def jobs(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_RECRUITER_DATA_DIR", str(tmp_path))
    importlib.reload(db)
    db.init_db()
    now = datetime.now(timezone.utc).isoformat()
    db.insert_job({
        "id": "job-go", "title": "Backend Engineer (Go)", "company": "Acme",
        "location": "Tokyo", "required_skills": ["Go", "Postgres"],
        "summary": "Own the Go services.", "created_at": now,
    })
    db.insert_job({
        "id": "job-ios", "title": "iOS Engineer", "company": "Beta",
        "location": "Osaka", "remote": True, "required_skills": ["Swift"],
        "summary": "Ship the iPhone app.", "salary_range": "¥8M–¥12M",
        "created_at": now,
    })
    from app import mcp_server
    return mcp_server


def _cards(text: str) -> list[dict]:
    out = json.loads(text)
    assert isinstance(out, list)
    return out


def test_search_jobs_filters_by_keyword_and_location(jobs):
    assert [c["id"] for c in _cards(jobs.search_jobs(query="Go"))] == ["job-go"]
    assert _cards(jobs.search_jobs(location="osaka"))[0]["id"] == "job-ios"
    assert _cards(jobs.search_jobs(location="remote"))[0]["id"] == "job-ios"
    assert _cards(jobs.search_jobs(query="cobol")) == []
    # Postings are in English; the seeker may not be.
    assert _cards(jobs.search_jobs(location="東京"))[0]["id"] == "job-go"
    assert _cards(jobs.search_jobs(location="リモート"))[0]["id"] == "job-ios"
    assert len(_cards(jobs.search_jobs(location="无所谓"))) == 2
    # Roles too: a tapped Chinese / Japanese role button finds the English posting.
    assert _cards(jobs.search_jobs(query="后端工程师"))[0]["id"] == "job-go"  # ranked: "backend" outweighs the shared "engineer"
    assert _cards(jobs.search_jobs(query="iOSエンジニア"))[0]["id"] == "job-ios"
    # And a city the table does not know still works as a plain substring.
    assert _cards(jobs.search_jobs(location="Osa")) and _cards(jobs.search_jobs(location="成都")) == []
    assert len(_cards(jobs.search_jobs())) == 2


def test_search_jobs_card_shape_is_the_connector_contract(jobs):
    card = _cards(jobs.search_jobs(query="ios"))[0]
    assert card["title"] == "iOS Engineer"
    assert card["subtitle"] == "Beta · Osaka · Remote"
    assert card["price"] == "¥8M–¥12M"
    assert card["detail"] == "Ship the iPhone app."
    assert card["fields"]["skills"] == "Swift"
    # The Go side decodes fields as map[string]string.
    assert all(isinstance(v, str) for v in card["fields"].values())


def test_tools_call_returns_one_text_block_holding_the_array(jobs):
    # The SDK splits a list result into one block per item; a JSON string keeps
    # the array whole, which is what the connector reads. Its args are strings.
    res = asyncio.run(jobs.mcp.call_tool("search_jobs", {"query": "engineer", "top_k": "1"}))
    texts = [c.text for c in res.content if c.type == "text"]
    assert len(texts) == 1
    assert len(_cards(texts[0])) == 1


def test_recommend_jobs_without_embeddings_degrades_to_empty(jobs):
    assert _cards(jobs.recommend_jobs(resume_text="Ten years of Go and Postgres.")) == []
    assert _cards(jobs.recommend_jobs(resume_text="   ")) == []


def test_transient_candidate_embeds_the_resume(jobs):
    cand = jobs._transient_candidate("Senior Go engineer, Tokyo.")
    assert "Senior Go engineer" in cand.embed_text()
    assert cand.raw_resume_text == "Senior Go engineer, Tokyo."


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_bearer_gate_refuses_strangers(jobs):
    import httpx

    async def inner(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    gated = jobs.BearerGate(inner, "s3cret")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gated), base_url="http://mcp") as c:
        assert (await c.post("/mcp")).status_code == 401
        assert (await c.post("/mcp", headers={"authorization": "Bearer wrong"})).status_code == 401
        r = await c.post("/mcp", headers={"authorization": "Bearer s3cret"})
        assert r.status_code == 200 and r.text == "ok"


def test_http_options_come_from_env(jobs, monkeypatch):
    monkeypatch.setenv("RECRUITER_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("RECRUITER_MCP_PORT", "9001")
    o = jobs._http_options()
    assert (o["host"], o["port"], o["streamable_http_path"]) == ("0.0.0.0", 9001, "/mcp")
    assert o["json_response"] and o["stateless_http"]


def test_apply_to_job_puts_the_seeker_in_the_pipeline(jobs):
    out = json.loads(jobs.apply_to_job(job_id="job-go", resume_text="Senior Go engineer, Tokyo, 8 years.",
                                       name="Mei", email="mei@example.com", source="charbit"))
    assert out["ok"] and out["title"] == "Backend Engineer (Go)" and out["company"] == "Acme"
    cand = db.get_candidate(out["candidate_id"])
    assert cand["name"] == "Mei" and cand["email"] == "mei@example.com"
    pipeline = [c for c in db.list_candidates_for_job("job-go")] if hasattr(db, "list_candidates_for_job") else None
    if pipeline is not None:
        assert any(c["id"] == out["candidate_id"] or c.get("candidate_id") == out["candidate_id"] for c in pipeline)
    # Unknown job, or nothing to send: says so, changes nothing.
    assert json.loads(jobs.apply_to_job(job_id="nope", resume_text="x"))["ok"] is False
    assert json.loads(jobs.apply_to_job(job_id="job-go", resume_text="  "))["ok"] is False


def test_search_jobs_goes_by_meaning_when_an_index_exists(jobs, monkeypatch):
    """With embeddings configured the query is answered by the vector index —
    any language — and the location filter still applies to the hits."""
    class Index:
        available = True

        def search_jobs(self, candidate, top_k=10):
            assert "護理師" in candidate.embed_text()
            return [("job-ios", 0.9), ("job-go", 0.8)]

    class Recruiter:
        index = Index()

    monkeypatch.setattr("app.sdk_bridge.build_recruiter", lambda cfg: Recruiter())
    hits = _cards(jobs.search_jobs(query="護理師"))
    assert [c["id"] for c in hits] == ["job-ios", "job-go"] and hits[0]["fields"]["score"] == "0.90"
    assert [c["id"] for c in _cards(jobs.search_jobs(query="護理師", location="tokyo"))] == ["job-go"]


def test_settings_config_carries_the_embeddings_endpoint(monkeypatch):
    """The Config the seeder and the MCP build (via get_config) must include
    the env-only embeddings endpoint, or nothing is ever indexed."""
    for k, v in {"EMBEDDING_API_URL": "https://ai.example/v1/embeddings",
                 "EMBEDDING_API_KEY": "k", "EMBEDDING_MODEL": "bge-m3"}.items():
        monkeypatch.setenv(k, v)
    from app.routes.settings import _build_config
    cfg = _build_config()
    assert cfg.embedding_api_url == "https://ai.example/v1/embeddings"
    assert cfg.embedding_api_key == "k" and cfg.embedding_model == "bge-m3"


def test_seed_path_index_uses_the_configured_endpoint(jobs, monkeypatch):
    """vector_index must populate the shared SDK config, or a caller that does
    not go through build_recruiter (the seeder) gets an embedder with no key
    even though the endpoint is configured."""
    from app import config as appcfg
    from app import sdk_bridge
    from app.routes import settings as settings_mod

    monkeypatch.setenv("EMBEDDING_API_URL", "https://ai.example/v1/embeddings")
    monkeypatch.setenv("EMBEDDING_API_KEY", "k")
    monkeypatch.setenv("EMBEDDING_MODEL", "bge-m3")
    cfg = settings_mod._build_config()
    index = sdk_bridge.vector_index(cfg)
    # Real index (not the null one), and the shared config the embedder reads
    # now carries the endpoint.
    assert type(index).__name__ == "ChromaVectorIndex"
    assert sdk_bridge._CONFIG.embedding_api_url == "https://ai.example/v1/embeddings"
    assert sdk_bridge._CONFIG.embedding_api_key == "k" and sdk_bridge._CONFIG.embedding_model == "bge-m3"

