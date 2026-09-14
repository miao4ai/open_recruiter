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

Two audiences, and they must not see each other's tools. `--tools recruiter`
(the default) publishes the hiring side; `--tools seeker` publishes the job
seeker's side — `search_jobs`, `recommend_jobs`, `match_resume_to_job`,
`apply_to_job` — which is what a consumer chat app wants. `all` publishes both,
for a single operator who is genuinely doing both jobs.

Writes are off unless asked for, and the gate is scoped to whatever set is
published: turning on `apply_to_job` for a seeker deployment does not also hand
out `create_job`. A tool the host marked `requires_approval` is gated too, since
that is the SDK's own word for "reaches outside the system". Ranking and
matching do persist the scores they compute — read-only means read-only about
your records, not about the match table.

Two transports. stdio is for a client on the same machine (Claude Desktop,
Cursor). `--http` serves streamable HTTP for a remote caller: stateless, JSON
responses, one JSON-RPC request per POST, which is the shape a server-side
connector speaks. Put a token on it — see `main`.
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

from openrecruiter import Config, Recruiter, Tool, build_seeker_tools
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
HTTP_PATH = "/mcp"

#: Tools that create or change records, or spend a model writing outbound text.
#: Withheld unless writes are enabled. `apply_to_job` is the seeker side's one
#: write: it puts a person into someone else's pipeline.
WRITE_TOOLS = frozenset(
    {
        "create_job",
        "create_candidate",
        "set_candidate_status",
        "draft_email",
        "apply_to_job",
    }
)

#: Which audience a server serves. They are separate because a seeker's
#: assistant has no business calling `set_candidate_status`.
TOOL_SETS = ("recruiter", "seeker", "all")

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

    A tool that already returned a string has done this itself — the seeker
    tools hand back a JSON array of cards that way — so it passes through
    untouched. Serialising it again would wrap it in quotes and escape every
    brace, and a connector parsing the block would get one long string where it
    expected a list.

    `default=str` is the escape hatch for a date or an enum a tool hands back;
    losing the exact type in the text a model reads costs nothing.
    """
    if isinstance(result, str):
        return result
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


def tools_for(recruiter: Recruiter, which: str = "recruiter") -> list[Tool]:
    """The tool set named by `which`, in publication order.

    The recruiter set is the client's own registry, so tools a host registered
    come with it. Under `all` it goes first and the seeker set skips any name it
    already took — a host's own `search_jobs` outranks the built-in one, which is
    the way round that lets an application specialise.
    """
    if which not in TOOL_SETS:
        raise ValueError(f"unknown tool set {which!r} — one of {', '.join(TOOL_SETS)}")
    if which == "seeker":
        return list(build_seeker_tools(recruiter))
    if which == "recruiter":
        return list(recruiter.tools)

    tools = list(recruiter.tools)
    taken = {t.name for t in tools}
    for tool in build_seeker_tools(recruiter):
        if tool.name in taken:
            log.info("Tool %s is already registered; keeping the host's", tool.name)
            continue
        tools.append(tool)
    return tools


def _is_write(tool: Tool) -> bool:
    # `requires_approval` is the SDK's own word for "reaches outside the system",
    # so a host marking their own tool with it is gated without naming it here.
    return tool.name in WRITE_TOOLS or tool.requires_approval


def build_server(
    recruiter: Recruiter, *, write: bool = False, tools: str = "recruiter"
) -> Any:
    """An MCP server publishing one of `recruiter`'s tool sets."""
    server = _Server(SERVER_NAME)
    published = []
    for tool in tools_for(recruiter, tools):
        if _is_write(tool) and not write:
            continue
        server.add_tool(_as_function(tool), name=tool.name, description=tool.description)
        published.append(tool.name)
    log.info(
        "Publishing %d %s tools over MCP (writes %s): %s",
        len(published), tools, "on" if write else "off", ", ".join(published),
    )
    return server


class BearerGate:
    """Refuses any HTTP request without `Authorization: Bearer <token>`.

    Pure ASGI, wrapped around the MCP app, so an unauthenticated request never
    reaches the protocol layer at all.
    """

    def __init__(self, app: Any, token: str) -> None:
        self.app = app
        self.expect = f"Bearer {token}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            if dict(scope.get("headers") or []).get(b"authorization", b"") != self.expect:
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
                return
        await self.app(scope, receive, send)


def http_app(server: Any, token: str = "", path: str = HTTP_PATH) -> Any:
    """The streamable-HTTP ASGI app, gated by `token` when one is given.

    Stateless with JSON responses: a server-side connector POSTs one JSON-RPC
    request and reads one JSON body back — it never sends
    notifications/initialized and never opens an SSE stream.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    app = server.streamable_http_app(
        streamable_http_path=path,
        json_response=True,
        stateless_http=True,
        # DNS-rebinding protection assumes a server on localhost. Behind a proxy
        # or Cloud Run the Host header is the public one and would be refused.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    return BearerGate(app, token) if token else app


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
    """Entry point: serve a tool set over stdio, or over streamable HTTP."""
    parser = argparse.ArgumentParser(
        prog="openrecruiter-mcp",
        description="Serve the Open Recruiter SDK's tools to an MCP client.",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="where openrecruiter.db and chroma_data live (default: $OPENRECRUITER_DATA_DIR, else the working directory)",
    )
    parser.add_argument(
        "--tools",
        choices=TOOL_SETS,
        default=os.environ.get("OPENRECRUITER_MCP_TOOLS", "recruiter"),
        help="which audience to serve (default: recruiter)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="also publish the tools that change records, within the chosen set",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        default=os.environ.get("OPENRECRUITER_MCP_TRANSPORT", "").lower() == "http",
        help=f"serve streamable HTTP on {HTTP_PATH} instead of stdio, for a remote caller",
    )
    parser.add_argument("--host", default=os.environ.get("OPENRECRUITER_MCP_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("OPENRECRUITER_MCP_PORT", "8765"))
    )
    args = parser.parse_args(argv)

    # stdout is the stdio transport — anything printed there corrupts the protocol.
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    recruiter = build_recruiter(args.data_dir)
    write = _writes_enabled(args.write)
    server = build_server(recruiter, write=write, tools=args.tools)

    if not args.http:
        server.run()  # stdio
        return

    import uvicorn

    token = os.environ.get("OPENRECRUITER_MCP_TOKEN", "").strip()
    if not token and args.host not in ("127.0.0.1", "localhost", "::1"):
        # Not fatal: a deployment may authenticate at the proxy. But an open
        # tool server on a routable address is worth saying out loud, and more
        # so when it can write into someone's pipeline.
        print(
            f"WARNING: serving on {args.host} with no OPENRECRUITER_MCP_TOKEN — "
            f"anyone who can reach this port can call these tools"
            f"{', including the ones that write' if write else ''}.",
            file=sys.stderr,
        )
    print(
        f"openrecruiter-mcp: http://{args.host}:{args.port}{HTTP_PATH} "
        f"({args.tools} tools, writes {'on' if write else 'off'}, "
        f"{'token-gated' if token else 'UNGATED'})",
        file=sys.stderr,
    )
    uvicorn.run(http_app(server, token), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":  # pragma: no cover
    main()
