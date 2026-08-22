"""The REST endpoints run on the same SDK the chat agent does.

Before this, resume parsing, JD parsing, matching, and email drafting each had
two implementations — one behind the API and one behind chat. `agents/jd.py` is
what that costs: it was a syntax error for five releases, and only the REST path
noticed, silently.
"""

from __future__ import annotations

import openrecruiter as orc
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_RECRUITER_DATA_DIR", str(tmp_path))
    import importlib

    from app import database as db

    importlib.reload(db)
    db.init_db()

    from app.auth import get_current_user
    from app.config import Config
    from app.main import app
    from app.routes import settings as settings_route
    from app import sdk_bridge

    sdk_bridge.reset_shared_state()
    monkeypatch.setattr(settings_route, "get_config", lambda: Config(anthropic_api_key="test-key"))
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1",
        "email": "r@example.com",
        "role": "recruiter",
    }
    yield TestClient(app)
    app.dependency_overrides.clear()


def _fake_llm(monkeypatch, payload):
    """Answer every structured call with `payload`, and record the prompts."""
    calls = []

    class FakeLLM:
        def __init__(self, config):
            self.config = config

        def complete_json(self, system, messages):
            calls.append({"system": system, "content": messages[0]["content"]})
            return payload() if callable(payload) else payload

        def stream(self, system, messages, tools=None):
            return iter(())

    import openrecruiter.client as sdk_client

    monkeypatch.setattr(sdk_client, "LLM", FakeLLM)
    return calls


def _upload(client, path, name, body=b"resume text", extra=None):
    return client.post(
        path, files={"file": (name, body, "text/plain")}, data=extra or {}
    )


# ── parsing ──────────────────────────────────────────────────────────────


def test_a_jd_upload_is_parsed_stored_and_indexed(client, monkeypatch):
    """The path that silently produced nothing from v1.0.0 to v3.0.1."""
    _fake_llm(monkeypatch, {
        "title": "Senior CUDA Engineer",
        "company": "Acme",
        "required_skills": ["CUDA", "NCCL"],
        "summary": "Scale distributed training.",
    })

    resp = _upload(client, "/api/jobs/upload", "cuda_jd.txt", b"We need a CUDA engineer.")
    assert resp.status_code == 200, resp.text

    job = resp.json()
    assert job["title"] == "Senior CUDA Engineer"
    assert job["company"] == "Acme"
    assert job["required_skills"] == ["CUDA", "NCCL"], "the fields that drive matching"
    assert job["raw_text"] == "We need a CUDA engineer."


def test_a_jd_that_parses_without_a_title_falls_back_to_the_filename(client, monkeypatch):
    _fake_llm(monkeypatch, {"company": "Acme"})

    job = _upload(client, "/api/jobs/upload", "senior_cuda_engineer_jd.txt").json()

    assert job["title"] == "senior cuda engineer"


def test_a_resume_upload_is_parsed_into_a_candidate(client, monkeypatch):
    _fake_llm(monkeypatch, {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "skills": ["CUDA", "PyTorch"],
        "experience_years": 8,
        "resume_summary": "Scaled training to 512 GPUs.",
    })

    resp = _upload(client, "/api/candidates/upload", "ada.txt")
    assert resp.status_code == 200, resp.text

    candidate = resp.json()
    assert candidate["name"] == "Ada Lovelace"
    assert candidate["email"] == "ada@example.com"
    assert candidate["skills"] == ["CUDA", "PyTorch"]


def test_the_prompt_forbids_protected_characteristics(client, monkeypatch):
    """The SDK's parse prompt is now the only one in the product."""
    calls = _fake_llm(monkeypatch, {"name": "Ada"})
    _upload(client, "/api/candidates/upload", "ada.txt")

    assert "date_of_birth" not in calls[0]["system"]


def test_an_upload_without_a_key_still_stores_the_document(client, monkeypatch):
    from app.config import Config
    from app.routes import settings as settings_route

    monkeypatch.setattr(settings_route, "get_config", lambda: Config())

    job = _upload(client, "/api/jobs/upload", "cuda_jd.txt", b"raw jd").json()

    assert job["raw_text"] == "raw jd", "never lose the document because parsing was unavailable"
    assert job["title"] == "cuda"


def test_a_provider_failure_on_upload_is_reported_not_swallowed(client, monkeypatch):
    """The old path logged and carried on with an empty job."""

    class Broken:
        def __init__(self, config):
            self.config = config

        def complete_json(self, system, messages):
            raise RuntimeError("provider is down")

    import openrecruiter.client as sdk_client

    monkeypatch.setattr(sdk_client, "LLM", Broken)

    assert _upload(client, "/api/jobs/upload", "jd.txt").status_code == 502


# ── matching ─────────────────────────────────────────────────────────────


def test_the_match_endpoint_uses_the_same_scorer_as_chat(client, monkeypatch):
    from app import database as db

    db.insert_job({
        "id": "j1", "title": "CUDA Engineer", "company": "Acme",
        "required_skills": ["CUDA"], "raw_text": "jd", "created_at": "2026-01-01",
    })
    db.insert_candidate({
        "id": "c1", "name": "Ada", "email": "a@x.com", "skills": ["CUDA"],
        "status": "new", "created_at": "2026-01-01", "updated_at": "2026-01-01",
    })
    _fake_llm(monkeypatch, {
        "score": 0.88,
        "strengths": ["CUDA at scale"],
        "gaps": ["No Triton"],
        "reasoning": "Direct match on the hard requirement.",
    })

    resp = client.post("/api/candidates/match", json={"job_id": "j1", "candidate_ids": ["c1"]})
    assert resp.status_code == 200, resp.text

    result = resp.json()[0]
    assert result["score"] == 0.88
    assert result["strengths"] == ["CUDA at scale"]
    assert result["reasoning"] == "Direct match on the hard requirement."

    # and it was written to the join the rest of the app reads
    assert db.get_candidate_job("c1", "j1")["match_score"] == 0.88


def test_matching_without_a_key_still_returns_an_order(client, monkeypatch):
    from app import database as db
    from app.config import Config
    from app.routes import settings as settings_route

    db.insert_job({"id": "j1", "title": "x", "company": "", "required_skills": [],
                   "raw_text": "jd", "created_at": "2026-01-01"})
    db.insert_candidate({"id": "c1", "name": "Ada", "email": "", "skills": [],
                         "status": "new", "created_at": "x", "updated_at": "x"})
    monkeypatch.setattr(settings_route, "get_config", lambda: Config())

    result = client.post(
        "/api/candidates/match", json={"job_id": "j1", "candidate_ids": ["c1"]}
    ).json()[0]

    assert "configure LLM key" in result["reasoning"]


# ── drafting ─────────────────────────────────────────────────────────────


def test_the_draft_endpoint_writes_a_real_email(client, monkeypatch):
    """It used to return the same three sentences for every candidate."""
    from app import database as db

    db.insert_candidate({"id": "c1", "name": "Ada", "email": "ada@x.com", "skills": ["CUDA"],
                         "status": "new", "created_at": "x", "updated_at": "x"})
    _fake_llm(monkeypatch, {"subject": "CUDA work at Acme", "body": "Hi Ada, your NCCL work..."})

    email = client.post(
        "/api/emails/draft", json={"candidate_id": "c1", "job_id": ""}
    ).json()

    assert email["subject"] == "CUDA work at Acme"
    assert "NCCL" in email["body"]


def test_drafting_falls_back_to_a_template_without_a_key(client, monkeypatch):
    from app import database as db
    from app.config import Config
    from app.routes import settings as settings_route

    db.insert_candidate({"id": "c1", "name": "Ada", "email": "ada@x.com", "skills": [],
                         "status": "new", "created_at": "x", "updated_at": "x"})
    monkeypatch.setattr(settings_route, "get_config", lambda: Config())

    email = client.post("/api/emails/draft", json={"candidate_id": "c1", "job_id": ""}).json()

    assert email["subject"] == "Exciting opportunity for Ada"
    assert email["body"].startswith("Hi Ada,")


# ── one engine ───────────────────────────────────────────────────────────


def test_the_app_no_longer_carries_its_own_domain_implementations():
    """Two implementations of "parse a resume" is how they drift apart."""
    import pathlib

    agents = pathlib.Path(__file__).resolve().parent.parent.parent / "backend" / "app" / "agents"
    present = {p.stem for p in agents.glob("*.py")} - {"__init__"}

    assert not ({"resume", "jd", "matching", "communication"} & present)
