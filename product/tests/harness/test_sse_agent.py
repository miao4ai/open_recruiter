"""Agent events become the SSE frames the chat UI already understands.

The most consequential assertion here is that text arrives as `token` events:
that is the name the front end has always listened for, and the reason real
streaming came back without touching the client.
"""

from __future__ import annotations

import asyncio
import json

from openrecruiter import Agent, Tool, ToolRegistry
from openrecruiter.events import TextDelta, ToolCall

from app.sse_agent import stream_agent


class ScriptedLLM:
    def __init__(self, script):
        self.script = list(script)

    def stream(self, system, messages, tools=None):
        turn = self.script.pop(0) if self.script else "done"
        if isinstance(turn, str):
            for word in turn.split(" "):
                yield TextDelta(text=word + " ")
            return
        for i, (name, args) in enumerate(turn):
            yield ToolCall(id=f"c{i}", name=name, arguments=args)


def _tools():
    return ToolRegistry(
        [
            Tool(name="list_jobs", description="", fn=lambda: [{"id": "j1"}]),
            Tool(
                name="request_resume_upload",
                description="",
                fn=lambda job_id="", job_title="": {
                    "ui_card": "upload_resume",
                    "job_id": job_id,
                    "note": "panel open",
                },
            ),
            Tool(
                name="check_inbox",
                description="",
                fn=lambda limit=10: {
                    "configured": True,
                    "messages": [{"from": "ada@example.com", "subject": "Re: role"}],
                },
            ),
            Tool(name="send_email", description="Send it", fn=lambda: {"sent": True}, requires_approval=True),
            Tool(name="explode", description="", fn=lambda: 1 / 0),
        ]
    )


def _drain(stream) -> list[dict]:
    """Run an async generator to completion.

    Done by hand rather than with a pytest async plugin: this is the only async
    surface in the harness, and one helper is cheaper than a new dependency for
    every contributor who just wants to run the tests.
    """

    async def collect():
        return [
            {"event": f["event"], "data": json.loads(f["data"])}
            async for f in stream
        ]

    return asyncio.run(collect())


def _collect(script, monkeypatch):
    monkeypatch.setattr("app.sse_agent._persist", lambda *a, **k: "msg1")
    agent = Agent(ScriptedLLM(script), _tools())
    return _drain(stream_agent(agent, "go", session_id="s1", user_id="u1"))


def test_text_arrives_as_token_events(monkeypatch):
    """The name the existing chat UI listens for — streaming works unchanged."""
    frames = _collect(["hello there"], monkeypatch)

    tokens = [f for f in frames if f["event"] == "token"]
    assert [t["data"]["t"] for t in tokens] == ["hello ", "there "]
    assert frames[-1]["event"] == "done"


def test_the_done_frame_carries_the_assembled_reply(monkeypatch):
    frames = _collect(["all good"], monkeypatch)

    done = frames[-1]["data"]
    assert done["reply"] == "all good"
    assert done["session_id"] == "s1"
    assert done["message_id"] == "msg1"


def test_tool_activity_is_visible_to_the_client(monkeypatch):
    frames = _collect([[("list_jobs", {})], "one role"], monkeypatch)

    names = [f["event"] for f in frames]
    assert "tool_call" in names and "tool_result" in names
    call = next(f for f in frames if f["event"] == "tool_call")["data"]
    assert call["name"] == "list_jobs"
    assert next(f for f in frames if f["event"] == "tool_result")["data"]["ok"] is True
    assert frames[-1]["data"]["tools_used"] == ["list_jobs"]


def test_a_ui_tool_becomes_an_action_the_app_renders(monkeypatch):
    frames = _collect([[("request_resume_upload", {"job_id": "j1"})], "ok"], monkeypatch)

    action = frames[-1]["data"]["action"]
    assert action == {"type": "upload_resume", "job_id": "j1"}


def test_a_tool_with_a_card_becomes_a_block(monkeypatch):
    frames = _collect([[("check_inbox", {})], "one reply"], monkeypatch)

    blocks = frames[-1]["data"]["blocks"]
    assert blocks[0]["type"] == "inbox_preview"
    assert blocks[0]["emails"][0]["from"] == "ada@example.com"


def test_an_approval_gate_reaches_the_client_and_the_stream_still_closes(monkeypatch):
    frames = _collect([[("send_email", {})]], monkeypatch)

    approval = next(f for f in frames if f["event"] == "approval_required")["data"]
    assert approval["name"] == "send_email"
    assert approval["session_id"] == "s1"
    assert frames[-1]["event"] == "done", "the client must never be left hanging"


def test_a_failing_tool_is_reported_and_the_run_continues(monkeypatch):
    frames = _collect([[("explode", {})], "that service is down"], monkeypatch)

    result = next(f for f in frames if f["event"] == "tool_result")["data"]
    assert result["ok"] is False
    assert "ZeroDivisionError" in result["error"]
    assert frames[-1]["data"]["reply"] == "that service is down"


def test_the_stream_always_terminates_with_done(monkeypatch):
    """Even when the agent itself blows up — otherwise the UI spins forever."""

    class Broken(Agent):
        def run(self, message, history=None):
            raise RuntimeError("catastrophe")
            yield  # pragma: no cover

    monkeypatch.setattr("app.sse_agent._persist", lambda *a, **k: "msg1")
    frames = _drain(
        stream_agent(Broken(ScriptedLLM([]), _tools()), "go", session_id="s1", user_id="u1")
    )

    assert frames[-1]["event"] == "done"
    assert "catastrophe" in frames[-1]["data"]["reply"]
