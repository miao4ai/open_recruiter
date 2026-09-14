"""An MCP server over the Open Recruiter SDK.

Every tool a `Recruiter` carries is published to MCP — including the ones a host
registered itself. That is the whole design: `openrecruiter` already describes
its tools with a name, a description and a JSON schema, and already dispatches
them by name, so this module is a bridge rather than a second list of tools to
keep in sync. Register a tool with the SDK and it appears here.

The bridge exists because the MCP SDK reads a tool's schema off a Python
signature, while `openrecruiter` carries one as JSON. `_as_function` synthesises
the signature the MCP SDK wants: types and descriptions come from the JSON
schema, and defaults from the underlying function, which is where they actually
live (`top_k: int = 10` is in the code, not in the schema).

Writes are off unless asked for. Someone wiring this into a chat client is
usually after "who fits this role", not a model that can create records on their
behalf, so `create_job`, `create_candidate`, `set_candidate_status` and
`draft_email` are withheld until `--write` (or `OPENRECRUITER_MCP_WRITE=1`).
Ranking and matching do persist the scores they compute — they are read-only
about *your* records, not about the match table.
"""

from __future__ import annotations

import argparse
import inspect
import json
import logging
import os
import sys
from pathlib import Path
from typing import Annotated, Any, Callable

from openrecruiter import Config, Recruiter, Tool
from pydantic import Field

# The MCP Python SDK renamed FastMCP to MCPServer in 2.0. Construction, add_tool
# and run() are the same across both, so support whichever is installed rather
# than pinning to one major.
try:
    from mcp.server.mcpserver import MCPServer as _Server  # mcp >= 2.0
except ImportError:  # pragma: no cover - depends on the installed SDK
    from mcp.server.fastmcp import FastMCP as _Server  # mcp 1.x

log = logging.getLogger(__name__)

SERVER_NAME = "open-recruiter"

#: Tools that create or change the caller's records, or spend a model writing
#: outbound text. Withheld unless writes are enabled.
WRITE_TOOLS = frozenset(
    {"create_job", "create_candidate", "set_candidate_status", "draft_email"}
)

_JSON_TYPES: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _as_function(tool: Tool) -> Callable[..., Any]:
    """A callable whose signature says what `tool`'s JSON schema says.

    The MCP SDK builds a tool's input schema by inspecting the function it is
    given, so handing it `tool.fn` directly would publish that function's
    signature — which for a bound SDK tool is often `(**kwargs)`. This wraps the
    call in a function that *declares* the documented parameters instead.
    """
    schema = tool.parameters or {}
    properties: dict[str, dict] = schema.get("properties", {}) or {}
    required = set(schema.get("required", []) or [])
    defaults = _defaults_of(tool.fn)

    parameters: list[inspect.Parameter] = []
    annotations: dict[str, Any] = {}
    for name, spec in properties.items():
        annotation: Any = _JSON_TYPES.get(spec.get("type", "string"), str)
        if description := spec.get("description"):
            annotation = Annotated[annotation, Field(description=description)]
        annotations[name] = annotation
        default = (
            inspect.Parameter.empty
            if name in required
            else defaults.get(name, spec.get("default"))
        )
        parameters.append(
            inspect.Parameter(
                name,
                inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=annotation,
            )
        )

    def call(**kwargs: Any) -> str:
        # Drop the arguments a client left at null rather than omitting, so an
        # unset optional falls back to the SDK's default instead of overriding
        # it with None.
        given = {k: v for k, v in kwargs.items() if v is not None}
        return _as_json(tool.fn(**given))

    call.__name__ = tool.name
    call.__doc__ = tool.description
    call.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
    call.__annotations__ = annotations
    return call


def _as_json(result: Any) -> str:
    """One JSON text block, whatever the tool returned.

    Handing the MCP SDK a Python object lets it decide the shape, and its
    choices are wrong for this: a list becomes one text block per item, and an
    empty list or `None` becomes *no blocks at all* — a model asking an empty
    pipeline for its jobs would see nothing back and could not tell that from a
    broken tool. Serialising here means "no jobs" arrives as `[]`.

    `default=str` is the escape hatch for a date or an enum a tool hands back;
    losing the exact type in the text a model reads costs nothing.
    """
    return json.dumps(result, default=str, ensure_ascii=False)


def _defaults_of(fn: Callable[..., Any]) -> dict[str, Any]:
    """The default values the tool's own function declares, if it has any."""
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):  # builtins and C callables
        return {}
    return {
        name: p.default
        for name, p in signature.parameters.items()
        if p.default is not inspect.Parameter.empty
    }


def build_server(recruiter: Recruiter, *, write: bool = False) -> Any:
    """An MCP server publishing `recruiter`'s tools."""
    server = _Server(SERVER_NAME)
    published = 0
    for tool in recruiter.tools:
        if tool.name in WRITE_TOOLS and not write:
            continue
        server.add_tool(_as_function(tool), name=tool.name, description=tool.description)
        published += 1
    log.info(
        "Publishing %d tools over MCP (writes %s)", published, "on" if write else "off"
    )
    return server


def build_recruiter(data_dir: str | Path | None = None) -> Recruiter:
    """A `Recruiter` over a local data directory, configured from the environment.

    `Config.from_env` reads the provider keys — `ANTHROPIC_API_KEY` for the
    model, and whichever embedding provider is set. Missing keys are not fatal
    here: retrieval degrades to nothing and the tools that need a model fail when
    called, which is a better failure than a server that will not start.
    """
    directory = Path(
        data_dir or os.environ.get("OPENRECRUITER_DATA_DIR") or Path.cwd()
    ).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    return Recruiter(Config.from_env(), data_dir=directory)


def _writes_enabled(flag: bool) -> bool:
    if flag:
        return True
    return os.environ.get("OPENRECRUITER_MCP_WRITE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def main(argv: list[str] | None = None) -> None:
    """Entry point: serve the SDK's tools over stdio."""
    parser = argparse.ArgumentParser(
        prog="openrecruiter-mcp",
        description="Serve the Open Recruiter SDK's tools to an MCP client over stdio.",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="where openrecruiter.db and chroma_data live (default: $OPENRECRUITER_DATA_DIR, else the working directory)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=f"also publish the tools that change records: {', '.join(sorted(WRITE_TOOLS))}",
    )
    args = parser.parse_args(argv)

    # stdout is the MCP transport — anything printed there corrupts the protocol.
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    recruiter = build_recruiter(args.data_dir)
    build_server(recruiter, write=_writes_enabled(args.write)).run()


if __name__ == "__main__":  # pragma: no cover
    main()
