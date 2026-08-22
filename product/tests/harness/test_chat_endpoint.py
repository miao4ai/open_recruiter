"""The chat endpoint, over HTTP, with the model faked.

This is the only test that exercises the whole path — route, auth, agent, tools,
store, SSE framing — and it exists because everything below it can pass while
the endpoint still returns nothing usable.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from openrecruiter.events import TextDelta, ToolCall


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

    monkeypatch.setattr(
        settings_route, "get_config", lambda: Config(anthropic_api_key="test-key")
    )
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1",
        "email": "r@example.com",
        "role": "recruiter",
    }
    yield TestClient(app)
    app.dependency_overrides.clear()


def _script(monkeypatch, turns):
    """Replace the provider with a scripted one, leaving everything else real."""

    class ScriptedLLM:
        def __init__(self, config):
            self.config = config

        def stream(self, system, messages, tools=None):
            turn = turns.pop(0) if turns else "done"
            if isinstance(turn, str):
                for word in turn.split(" "):
                    yield TextDelta(text=word + " ")
                return
            for i, (name, args) in enumerate(turn):
                yield ToolCall(id=f"c{i}", name=name, arguments=args)

        def complete_json(self, system, messages):
            return {}

    import openrecruiter.client as sdk_client

    monkeypatch.setattr(sdk_client, "LLM", ScriptedLLM)


def _frames(response) -> list[dict]:
    """Parse an SSE body into (event, data) pairs."""
    frames, event = [], ""
    for line in response.text.splitlines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:") and event:
            frames.append({"event": event, "data": json.loads(line[5:].strip())})
    return frames


def test_streaming_chat_emits_tokens_then_done(client, monkeypatch):
    """Streaming was silently lost in the LangGraph migration. It is back."""
    _script(monkeypatch, ["you have two open roles"])

    resp = client.post("/api/agent/chat/stream", json={"message": "what am I hiring for?"})
    assert resp.status_code == 200

    frames = _frames(resp)
    tokens = [f["data"]["t"] for f in frames if f["event"] == "token"]

    assert tokens, "no token frames — the client would show a spinner and nothing else"
    assert "".join(tokens).strip() == "you have two open roles"
    assert frames[-1]["event"] == "done"
    assert frames[-1]["data"]["reply"] == "you have two open roles"


def test_the_agent_reaches_the_real_store_through_a_tool(client, monkeypatch):
    from app import database as db

    db.insert_job(
        {
            "id": "j1",
            "title": "Senior CUDA Engineer",
            "company": "Acme",
            "required_skills": ["CUDA"],
            "raw_text": "jd",
            "created_at": "2026-01-01",
        }
    )
    _script(monkeypatch, [[("list_jobs", {})], "One role: Senior CUDA Engineer."])

    frames = _frames(client.post("/api/agent/chat/stream", json={"message": "list my jobs"}))

    result = next(f for f in frames if f["event"] == "tool_result")["data"]
    assert result["name"] == "list_jobs"
    assert result["ok"] is True
    assert frames[-1]["data"]["tools_used"] == ["list_jobs"]


def test_a_multi_step_request_runs_every_step(client, monkeypatch):
    """The behaviour the previous single-action dispatcher could not express."""
    from app import database as db

    db.insert_job(
        {
            "id": "j1",
            "title": "CUDA Engineer",
            "company": "Acme",
            "required_skills": [],
            "raw_text": "jd",
            "created_at": "2026-01-01",
        }
    )
    _script(
        monkeypatch,
        [
            [("list_jobs", {})],
            [("rank_candidates", {"job_id": "j1"})],
            "Nobody in the pool fits yet.",
        ],
    )

    frames = _frames(client.post("/api/agent/chat/stream", json={"message": "who fits my CUDA role?"}))

    assert frames[-1]["data"]["tools_used"] == ["list_jobs", "rank_candidates"]
    assert frames[-1]["data"]["reply"] == "Nobody in the pool fits yet."


def test_a_ui_tool_comes_back_as_an_action(client, monkeypatch):
    _script(monkeypatch, [[("request_resume_upload", {})], "Upload it below."])

    frames = _frames(client.post("/api/agent/chat/stream", json={"message": "add a candidate"}))

    assert frames[-1]["data"]["action"] == {"type": "upload_resume", "job_id": "", "job_title": ""}


def test_the_turn_is_persisted_for_the_next_request(client, monkeypatch):
    from app import database as db

    _script(monkeypatch, ["noted"])
    resp = client.post("/api/agent/chat/stream", json={"message": "remember this"})
    session_id = _frames(resp)[-1]["data"]["session_id"]

    roles = [m["role"] for m in db.list_chat_messages("u1", session_id=session_id)]
    assert roles == ["user", "assistant"]


def test_without_an_api_key_the_user_is_told_rather_than_left_waiting(client, monkeypatch):
    from app.config import Config
    from app.routes import settings as settings_route

    monkeypatch.setattr(settings_route, "get_config", lambda: Config())

    frames = _frames(client.post("/api/agent/chat/stream", json={"message": "hello"}))

    assert frames[-1]["event"] == "done"
    assert "API key" in frames[-1]["data"]["reply"]
