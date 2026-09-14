"""The bridge from SDK tools to MCP.

What is worth testing here is the translation, not the MCP SDK: a tool's schema
has to survive the trip, writes have to stay off until asked for, and a tool
someone registered themselves has to come along. Everything else is `openrecruiter`.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from openrecruiter import Config, Recruiter, Tool

from openrecruiter_mcp.server import (
    WRITE_TOOLS,
    _as_function,
    build_recruiter,
    build_server,
    _writes_enabled,
)


@pytest.fixture
def recruiter(tmp_path):
    """A recruiter on an empty directory. No key, so nothing reaches a network."""
    return Recruiter(Config(anthropic_api_key="test-key"), data_dir=tmp_path)


def _tools(server):
    return {t.name: t for t in asyncio.run(server.list_tools())}


def _schema(tool):
    """chromadb-style camelCase moved to snake_case in mcp 2.0."""
    return getattr(tool, "input_schema", None) or tool.inputSchema


# ── what reaches the client ──────────────────────────────────────────────────


def test_every_sdk_tool_is_published(recruiter):
    server = build_server(recruiter, write=True)
    assert set(_tools(server)) == set(recruiter.tools.names())


def test_writes_are_withheld_by_default(recruiter):
    """A chat client asking "who fits this role" should not also be able to
    create records on the caller's behalf."""
    published = set(_tools(build_server(recruiter)))

    assert not (published & WRITE_TOOLS)
    assert "rank_candidates" in published and "search_candidates" in published
    assert published == set(recruiter.tools.names()) - WRITE_TOOLS


def test_writes_can_be_turned_on(recruiter):
    assert WRITE_TOOLS <= set(_tools(build_server(recruiter, write=True)))


def test_a_host_registered_tool_comes_along(recruiter):
    """The reason this is a bridge and not a second list of tools."""
    recruiter.tools.register(
        Tool(
            name="check_inbox",
            description="Read replies from candidates.",
            parameters={"type": "object", "properties": {"since": {"type": "string"}}},
            fn=lambda since="": [{"from": "ada@example.com"}],
        )
    )
    assert "check_inbox" in _tools(build_server(recruiter))


# ── the schema has to survive the trip ───────────────────────────────────────


def test_the_json_schema_becomes_the_mcp_schema(recruiter):
    tool = _tools(build_server(recruiter))["rank_candidates"]
    schema = _schema(tool)

    assert schema["type"] == "object"
    assert set(schema["properties"]) == {"job_id", "top_k"}
    assert schema["properties"]["job_id"]["type"] == "string"
    assert schema["properties"]["top_k"]["type"] == "integer"
    assert schema["required"] == ["job_id"]
    assert tool.description == recruiter.tools.get("rank_candidates").description


def test_a_parameter_description_is_carried_over():
    """MCP clients show these to the calling model, so losing them costs accuracy."""
    tool = Tool(
        name="t",
        description="A tool.",
        parameters={
            "type": "object",
            "properties": {"q": {"type": "string", "description": "what to look for"}},
            "required": ["q"],
        },
        fn=lambda q: q,
    )
    fn = _as_function(tool)
    import inspect

    annotation = inspect.signature(fn).parameters["q"].annotation
    assert "what to look for" in str(annotation)


def test_defaults_come_from_the_function_not_the_schema():
    """The SDK declares `top_k: int = 10` in code and says nothing about it in
    the schema, so reading defaults off the schema alone would publish None."""

    def rank(job_id: str, top_k: int = 10):
        return top_k

    tool = Tool(
        name="rank",
        description="Rank.",
        parameters={
            "type": "object",
            "properties": {"job_id": {"type": "string"}, "top_k": {"type": "integer"}},
            "required": ["job_id"],
        },
        fn=rank,
    )
    import inspect

    assert inspect.signature(_as_function(tool)).parameters["top_k"].default == 10


def test_an_omitted_optional_falls_back_to_the_sdk_default():
    """MCP clients routinely send an unset optional as null; passing that through
    would override the default with None and break the call."""

    def rank(job_id: str, top_k: int = 10):
        return {"job_id": job_id, "top_k": top_k}

    tool = Tool(
        name="rank",
        description="Rank.",
        parameters={
            "type": "object",
            "properties": {"job_id": {"type": "string"}, "top_k": {"type": "integer"}},
            "required": ["job_id"],
        },
        fn=rank,
    )
    assert json.loads(_as_function(tool)(job_id="j1", top_k=None)) == {
        "job_id": "j1",
        "top_k": 10,
    }


# ── wiring ───────────────────────────────────────────────────────────────────


def test_a_call_reaches_the_sdk(recruiter):
    """An empty pipeline answers, rather than failing — a fresh install is empty."""
    server = build_server(recruiter)
    result = asyncio.run(server.call_tool("list_jobs", {}))
    assert getattr(result, "is_error", False) is False


def test_an_empty_result_is_still_a_visible_answer(recruiter):
    """Handing MCP a bare [] or None produces *no content blocks*, which a model
    cannot tell apart from a broken tool. "No jobs" has to arrive as `[]`."""
    server = build_server(recruiter)

    for name, args, expected in [
        ("list_jobs", {}, "[]"),
        ("get_job", {"job_id": "nope"}, "null"),
        ("search_candidates", {"query": "cuda"}, "[]"),
    ]:
        result = asyncio.run(server.call_tool(name, args))
        assert len(result.content) == 1, f"{name} produced {len(result.content)} blocks"
        assert result.content[0].text == expected


def test_a_list_is_one_block_not_one_block_per_item(recruiter):
    """The MCP SDK splits a returned list across blocks; a caller parsing the
    first block would then silently see only the first item."""
    recruiter.tools.register(
        Tool(
            name="three",
            description="Returns three things.",
            parameters={"type": "object", "properties": {}},
            fn=lambda: [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        )
    )
    result = asyncio.run(build_server(recruiter).call_tool("three", {}))

    assert len(result.content) == 1
    assert json.loads(result.content[0].text) == [{"id": "a"}, {"id": "b"}, {"id": "c"}]


def test_writes_can_be_enabled_from_the_environment(monkeypatch):
    monkeypatch.delenv("OPENRECRUITER_MCP_WRITE", raising=False)
    assert not _writes_enabled(False)
    assert _writes_enabled(True)

    monkeypatch.setenv("OPENRECRUITER_MCP_WRITE", "1")
    assert _writes_enabled(False)
    monkeypatch.setenv("OPENRECRUITER_MCP_WRITE", "no")
    assert not _writes_enabled(False)


def test_the_data_directory_is_created_if_missing(tmp_path, monkeypatch):
    """A client's config names a directory; the first run should not need the
    user to have made it by hand."""
    monkeypatch.delenv("OPENRECRUITER_DATA_DIR", raising=False)
    target = tmp_path / "not-yet"

    r = build_recruiter(target)

    assert target.is_dir()
    assert (target / "openrecruiter.db").exists()
    assert r.tools.names()
