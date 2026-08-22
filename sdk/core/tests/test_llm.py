"""The provider layer.

Reassembling streamed tool calls is the fiddly part: providers send a call's
arguments as JSON fragments spread over many chunks, and a half-parsed argument
object is worse than no event at all.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from openrecruiter.config import Config
from openrecruiter.events import TextDelta, ToolCall
from openrecruiter.providers.llm import LLM, LLMError


def _delta(content=None, tool_calls=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content, tool_calls=tool_calls))]
    )


def _frag(index, id=None, name=None, arguments=None):
    return SimpleNamespace(
        index=index,
        id=id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


@pytest.fixture
def llm():
    return LLM(Config(llm_provider="anthropic", anthropic_api_key="test"))


def _patch(monkeypatch, chunks):
    import litellm

    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return iter(chunks) if kwargs.get("stream") else chunks

    monkeypatch.setattr(litellm, "completion", fake_completion)
    return captured


# -- streaming text --------------------------------------------------------


def test_text_chunks_are_yielded_as_they_arrive(llm, monkeypatch):
    _patch(monkeypatch, [_delta("Hel"), _delta("lo"), _delta(None)])

    events = list(llm.stream("sys", [{"role": "user", "content": "hi"}]))

    assert [e.text for e in events] == ["Hel", "lo"]
    assert all(isinstance(e, TextDelta) for e in events)


def test_chunks_without_choices_are_skipped(llm, monkeypatch):
    _patch(monkeypatch, [SimpleNamespace(choices=[]), _delta("ok")])

    assert [e.text for e in llm.stream("sys", [])] == ["ok"]


# -- tool call reassembly --------------------------------------------------


def test_arguments_split_across_chunks_are_reassembled(llm, monkeypatch):
    _patch(monkeypatch, [
        _delta(None, [_frag(0, id="call_1", name="rank", arguments='{"job_')]),
        _delta(None, [_frag(0, arguments='id": "j1", "top_')]),
        _delta(None, [_frag(0, arguments='k": 5}')]),
    ])

    events = list(llm.stream("sys", [], tools=[{"type": "function"}]))

    assert len(events) == 1
    call = events[0]
    assert isinstance(call, ToolCall)
    assert call.id == "call_1"
    assert call.name == "rank"
    assert call.arguments == {"job_id": "j1", "top_k": 5}


def test_a_tool_call_is_only_emitted_once_complete(llm, monkeypatch):
    """Nothing may be yielded while the argument JSON is still a fragment."""
    _patch(monkeypatch, [
        _delta("thinking "),
        _delta(None, [_frag(0, id="c1", name="rank", arguments='{"job_id":')]),
        _delta(None, [_frag(0, arguments=' "j1"}')]),
    ])

    events = list(llm.stream("sys", [], tools=[]))

    assert isinstance(events[0], TextDelta)
    assert len([e for e in events if isinstance(e, ToolCall)]) == 1


def test_parallel_tool_calls_are_kept_apart_by_index(llm, monkeypatch):
    _patch(monkeypatch, [
        _delta(None, [_frag(0, id="a", name="list_jobs", arguments="{}")]),
        _delta(None, [_frag(1, id="b", name="rank", arguments='{"job_id"')]),
        _delta(None, [_frag(1, arguments=': "j1"}')]),
    ])

    calls = list(llm.stream("sys", [], tools=[]))

    assert [c.name for c in calls] == ["list_jobs", "rank"]
    assert calls[1].arguments == {"job_id": "j1"}


def test_unparseable_arguments_become_an_empty_dict(llm, monkeypatch):
    """The tool then rejects its input, instead of the stream dying."""
    _patch(monkeypatch, [_delta(None, [_frag(0, id="a", name="rank", arguments="{not json")])])

    call = list(llm.stream("sys", [], tools=[]))[0]

    assert call.arguments == {}
    assert call.name == "rank"


def test_a_call_with_no_arguments_is_still_emitted(llm, monkeypatch):
    _patch(monkeypatch, [_delta(None, [_frag(0, id="a", name="list_jobs", arguments="")])])

    assert list(llm.stream("sys", [], tools=[]))[0].arguments == {}


def test_a_fragment_that_never_names_a_tool_is_dropped(llm, monkeypatch):
    _patch(monkeypatch, [_delta(None, [_frag(0, arguments="{}")])])

    assert list(llm.stream("sys", [], tools=[])) == []


# -- request shaping -------------------------------------------------------


def test_tools_and_the_system_prompt_reach_the_provider(llm, monkeypatch):
    captured = _patch(monkeypatch, [_delta("ok")])
    schemas = [{"type": "function", "function": {"name": "rank"}}]

    list(llm.stream("be helpful", [{"role": "user", "content": "hi"}], tools=schemas))

    assert captured["tools"] == schemas
    assert captured["stream"] is True
    assert captured["messages"][0]["role"] == "system"
    assert captured["model"] == "anthropic/claude-sonnet-5"
    assert captured["api_key"] == "test"


def test_long_system_prompts_are_cached_on_anthropic(llm, monkeypatch):
    """A 10K-token system prompt re-billed every turn is the expensive default."""
    captured = _patch(monkeypatch, [_delta("ok")])

    list(llm.stream("x" * 5000, []))

    block = captured["messages"][0]["content"][0]
    assert block["cache_control"] == {"type": "ephemeral"}


def test_short_prompts_are_not_cached(llm, monkeypatch):
    captured = _patch(monkeypatch, [_delta("ok")])
    list(llm.stream("short", []))
    assert isinstance(captured["messages"][0]["content"], str)


def test_openai_never_gets_a_cache_control_block(monkeypatch):
    llm = LLM(Config(llm_provider="openai", openai_api_key="k"))
    captured = _patch(monkeypatch, [_delta("ok")])

    list(llm.stream("x" * 5000, []))

    assert isinstance(captured["messages"][0]["content"], str)
    assert captured["model"] == "openai/gpt-5.1"


# -- errors and json -------------------------------------------------------


def test_provider_failures_are_wrapped_with_the_model_id(llm, monkeypatch):
    import litellm

    monkeypatch.setattr(
        litellm, "completion", lambda **kw: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    with pytest.raises(LLMError, match="anthropic/claude-sonnet-5: boom"):
        list(llm.stream("sys", []))


def test_json_replies_survive_a_markdown_fence(llm, monkeypatch):
    import litellm

    fenced = '```json\n{"score": 0.9}\n```'
    monkeypatch.setattr(
        litellm,
        "completion",
        lambda **kw: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=fenced))]
        ),
    )

    assert llm.complete_json("sys", [{"role": "user", "content": "score it"}]) == {"score": 0.9}


def test_json_mode_nudges_the_last_user_message(llm, monkeypatch):
    """OpenAI rejects json mode unless the word appears in the user turn."""
    import litellm

    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

    monkeypatch.setattr(litellm, "completion", fake)
    llm.complete_json("sys", [{"role": "user", "content": "score it"}])

    assert "json" in captured["messages"][-1]["content"].lower()
    assert captured["response_format"] == {"type": "json_object"}
