"""Open Recruiter as an MCP server.

Publishes a `Recruiter`'s tools — the hiring side, the job seeker's side, or
both — to any MCP client, over stdio or streamable HTTP:

    openrecruiter-mcp                          # recruiter tools, stdio
    openrecruiter-mcp --tools seeker --http    # seeker tools, for a remote caller

See `server.py` for how the bridge works and README.md for client wiring.
"""

from openrecruiter_mcp.server import (
    TOOL_SETS,
    WRITE_TOOLS,
    BearerGate,
    build_recruiter,
    build_server,
    http_app,
    main,
    tools_for,
)

__version__ = "0.2.0"

__all__ = [
    "TOOL_SETS",
    "WRITE_TOOLS",
    "BearerGate",
    "__version__",
    "build_recruiter",
    "build_server",
    "http_app",
    "main",
    "tools_for",
]
