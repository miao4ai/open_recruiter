"""The agent loop.

These are the tests that decide whether "AI native" is a real claim: the model
must be able to call a tool, read what came back, and decide what to do next —
repeatedly, within one request — and it must stop dead at an approval gate.
"""

from __future__ import annotations

import json

import pytest

from openrecruiter.agent import Agent, PendingApproval
from openrecruiter.events import ApprovalRequired, Finished, TextDelta, ToolResult
from openrecruiter.tools.base import Tool, ToolRegistry

from conftest import FakeLLM


def _registry(calls: list | None = None) -> ToolRegistry:
    log = calls if calls is not None else []

    def list_jobs(limit: int = 10):
        log.append(("list_jobs", limit))
        return [{"id": "job1", "title": "Senior CUDA Engineer"}]

    def rank(job_id: str, top_k: int = 5):
        log.append(("rank", job_id))
        return [{"candidate_id": "c1", "score": 0.91}]

    def send_email(candidate_id: str, body: str = ""):
        log.append(("send_email", candidate_id))
        return {"sent": True}

    def explode():
        raise ValueError("upstream is down")

    return ToolRegistry(
        [
            Tool(name="list_jobs", description="List jobs", fn=list_jobs),
            Tool(name="rank", description="Rank candidates", fn=rank),
            Tool(
                name="send_email",
                description="Send an email to a candidate",
                fn=send_email,
                requires_approval=True,
            ),
            Tool(name="explode", description="Always fails", fn=explode),
        ]
    )


def _run(script, calls=None):
    agent = Agent(FakeLLM(script), _registry(calls))
    return agent, list(agent.run("go"))


# ── streaming ────────────────────────────────────────────────────────────


def test_text_is_streamed_not_delivered_at_the_end():
    _, events = _run(["hello there friend"])

    deltas = [e for e in events if isinstance(e, TextDelta)]
    assert len(deltas) == 3, "each fragment should surface as it arrives"
    assert "".join(d.text for d in deltas).strip() == "hello there friend"


def test_a_turn_with_no_tool_calls_ends_immediately():
    _, events = _run(["all done"])

    finished = events[-1]
    assert isinstance(finished, Finished)
    assert finished.stop_reason == "end_turn"
    assert finished.steps == 0


# ── tool calling ─────────────────────────────────────────────────────────


def test_a_call_is_announced_before_it_runs():
    """A caller showing progress needs the call, not only the result."""
    from openrecruiter.events import ToolCall as ToolCallEvent

    _, events = _run([[("list_jobs", {"limit": 5})], "done"])

    kinds = [type(e).__name__ for e in events if not isinstance(e, TextDelta)]
    assert kinds[:2] == ["ToolCall", "ToolResult"]
    announced = next(e for e in events if isinstance(e, ToolCallEvent))
    assert announced.name == "list_jobs"
    assert announced.arguments == {"limit": 5}


def test_a_tool_call_runs_and_its_result_is_reported():
    calls = []
    _, events = _run([[("list_jobs", {"limit": 5})], "Found one job."], calls)

    assert calls == [("list_jobs", 5)]
    result = next(e for e in events if isinstance(e, ToolResult))
    assert result.ok
    assert result.result[0]["title"] == "Senior CUDA Engineer"


def test_the_model_chains_tools_across_steps():
    """The single most important behaviour: read a result, then decide again."""
    calls = []
    _, events = _run(
        [
            [("list_jobs", {})],
            [("rank", {"job_id": "job1"})],
            "Ada is the strongest fit.",
        ],
        calls,
    )

    assert calls == [("list_jobs", 10), ("rank", "job1")]
    assert [e for e in events if isinstance(e, ToolResult)][1].result[0]["score"] == 0.91
    assert events[-1].stop_reason == "end_turn"
    assert events[-1].steps == 2


def test_several_tools_in_one_turn_all_run():
    calls = []
    _run([[("list_jobs", {}), ("rank", {"job_id": "job1"})], "done"], calls)
    assert calls == [("list_jobs", 10), ("rank", "job1")]


def test_a_failing_tool_does_not_end_the_run():
    """The model can often recover if it is told what broke."""
    _, events = _run([[("explode", {})], "I could not reach that service."])

    result = next(e for e in events if isinstance(e, ToolResult))
    assert not result.ok
    assert "upstream is down" in result.error
    assert events[-1].stop_reason == "end_turn"


def test_an_unknown_tool_is_reported_back_rather_than_raising():
    _, events = _run([[("nonexistent", {})], "sorry"])

    result = next(e for e in events if isinstance(e, ToolResult))
    assert "Unknown tool" in result.error
    assert events[-1].stop_reason == "end_turn"


# ── approval gate ────────────────────────────────────────────────────────


def test_an_approval_tool_stops_the_run_without_executing():
    calls = []
    agent, events = _run([[("send_email", {"candidate_id": "c1"})]], calls)

    assert calls == [], "the action must not happen before a human agrees"
    approval = next(e for e in events if isinstance(e, ApprovalRequired))
    assert approval.name == "send_email"
    assert approval.arguments == {"candidate_id": "c1"}
    assert approval.description == "Send an email to a candidate"
    assert events[-1].stop_reason == "awaiting_approval"
    assert isinstance(agent.pending, PendingApproval)


def test_approving_runs_the_tool_and_continues():
    calls = []
    agent, _ = _run([[("send_email", {"candidate_id": "c1"})], "Sent."], calls)

    resumed = list(agent.resume(agent.pending, approved=True))

    assert calls == [("send_email", "c1")]
    assert next(e for e in resumed if isinstance(e, ToolResult)).result == {"sent": True}
    assert resumed[-1].stop_reason == "end_turn"


def test_declining_leaves_the_action_undone_and_tells_the_model():
    calls = []
    agent, _ = _run([[("send_email", {"candidate_id": "c1"})], "Understood."], calls)

    resumed = list(agent.resume(agent.pending, approved=False))

    assert calls == []
    result = next(e for e in resumed if isinstance(e, ToolResult))
    assert "declined" in result.error
    assert resumed[-1].stop_reason == "end_turn"


def test_calls_queued_behind_a_gate_are_held_not_run():
    """Otherwise the gate is cosmetic: the rest of the batch escapes it."""
    calls = []
    agent, _ = _run(
        [[("send_email", {"candidate_id": "c1"}), ("rank", {"job_id": "job1"})], "ok"],
        calls,
    )

    assert calls == []
    assert [c["name"] for c in agent.pending.queued] == ["rank"]

    list(agent.resume(agent.pending, approved=True))
    assert calls == [("send_email", "c1"), ("rank", "job1")]


def test_pending_approval_survives_serialisation():
    """The decision usually arrives on a later request, in another process."""
    agent, _ = _run([[("send_email", {"candidate_id": "c1"})], "Sent."])

    revived = PendingApproval.model_validate(json.loads(agent.pending.model_dump_json()))
    assert list(agent.resume(revived, approved=True))[-1].stop_reason == "end_turn"


# ── guards ───────────────────────────────────────────────────────────────


def test_max_steps_stops_a_model_that_never_finishes():
    agent = Agent(
        FakeLLM([[("list_jobs", {})]] * 20),
        _registry(),
        max_steps=3,
    )
    events = list(agent.run("go"))

    assert events[-1].stop_reason == "max_steps"
    assert events[-1].steps == 3


def test_a_provider_failure_finishes_with_an_error():
    from openrecruiter.providers.llm import LLMError

    class Broken(FakeLLM):
        def stream(self, system, messages, tools=None):
            raise LLMError("429 rate limited")
            yield  # pragma: no cover

    events = list(Agent(Broken(), _registry()).run("go"))

    assert events[-1].stop_reason == "error"
    assert "429" in events[-1].error


# ── provider message shapes ──────────────────────────────────────────────


def test_tool_results_are_fed_back_in_the_shape_providers_require():
    llm = FakeLLM([[("list_jobs", {})], "done"])
    list(Agent(llm, _registry()).run("go"))

    second_turn = llm.calls[1]["messages"]
    assistant, tool_msg = second_turn[-2], second_turn[-1]

    assert assistant["role"] == "assistant"
    assert assistant["tool_calls"][0]["function"]["name"] == "list_jobs"
    assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {}

    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == assistant["tool_calls"][0]["id"]
    assert "Senior CUDA Engineer" in tool_msg["content"]


def test_tools_are_offered_to_the_model_on_every_turn():
    llm = FakeLLM([[("list_jobs", {})], "done"])
    list(Agent(llm, _registry()).run("go"))

    for call in llm.calls:
        names = {t["function"]["name"] for t in call["tools"]}
        assert {"list_jobs", "rank", "send_email"} <= names


def test_history_is_carried_into_the_first_turn():
    llm = FakeLLM(["hi"])
    history = [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "sure"}]
    list(Agent(llm, _registry()).run("now", history=history))

    messages = llm.calls[0]["messages"]
    assert messages[0]["content"] == "earlier"
    assert messages[-1] == {"role": "user", "content": "now"}
