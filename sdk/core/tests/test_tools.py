"""The registry is what hosts extend, so its contract has to be strict."""

from __future__ import annotations

import pytest

from openrecruiter.tools.base import Tool, ToolError, ToolRegistry, tool


def _echo(value: str = "") -> str:
    return value


def test_schema_is_the_shape_providers_expect():
    t = Tool(
        name="echo",
        description="Say it back",
        parameters={"type": "object", "properties": {"value": {"type": "string"}}},
        fn=_echo,
    )
    schema = t.schema()

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "echo"
    assert schema["function"]["description"] == "Say it back"
    assert schema["function"]["parameters"]["properties"]["value"]["type"] == "string"


def test_registering_the_same_name_twice_is_an_error():
    reg = ToolRegistry([Tool(name="a", description="", fn=_echo)])
    with pytest.raises(ToolError, match="already registered"):
        reg.register(Tool(name="a", description="", fn=_echo))


def test_unknown_tool_names_the_tool():
    with pytest.raises(ToolError, match="Unknown tool 'ghost'"):
        ToolRegistry().call("ghost")


def test_unexpected_arguments_are_dropped_not_fatal():
    """Models invent plausible extra arguments; losing the turn to that is worse."""
    reg = ToolRegistry([Tool(name="echo", description="", fn=_echo)])
    assert reg.call("echo", {"value": "hi", "temperature": 0.7}) == "hi"


def test_missing_required_arguments_still_raise():
    def needs_id(candidate_id: str) -> str:
        return candidate_id

    reg = ToolRegistry([Tool(name="needs_id", description="", fn=needs_id)])
    with pytest.raises(ToolError, match="missing required arguments: candidate_id"):
        reg.call("needs_id", {})


def test_a_tool_taking_kwargs_receives_everything():
    def sink(**kwargs):
        return sorted(kwargs)

    reg = ToolRegistry([Tool(name="sink", description="", fn=sink)])
    assert reg.call("sink", {"b": 1, "a": 2}) == ["a", "b"]


def test_defaults_apply_when_the_model_omits_an_argument():
    reg = ToolRegistry([Tool(name="echo", description="", fn=_echo)])
    assert reg.call("echo", {}) == ""


def test_decorator_builds_an_equivalent_tool():
    @tool("greet", "Greet someone", {"type": "object", "properties": {}}, requires_approval=True)
    def greet(name: str = "world") -> str:
        return f"hello {name}"

    assert isinstance(greet, Tool)
    assert greet.requires_approval is True
    assert greet(name="ada") == "hello ada"


def test_registry_reports_its_contents():
    reg = ToolRegistry([Tool(name="b", description="", fn=_echo), Tool(name="a", description="", fn=_echo)])
    assert reg.names() == ["a", "b"]
    assert len(reg) == 2
    assert "a" in reg
    assert len(reg.schemas()) == 2


def test_hosts_can_extend_the_built_in_set():
    """The desktop app registers its own UI tools this way."""
    reg = ToolRegistry([Tool(name="builtin", description="", fn=_echo)])
    reg.extend([Tool(name="upload_resume", description="", fn=_echo)])
    assert reg.names() == ["builtin", "upload_resume"]
