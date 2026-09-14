"""Open Recruiter as an MCP server.

Publishes the tools a `Recruiter` carries — including any a host registered —
to any MCP client over stdio:

    openrecruiter-mcp

See `server.py` for how the bridge works and README.md for client wiring.
"""

from openrecruiter_mcp.server import WRITE_TOOLS, build_recruiter, build_server, main

__version__ = "0.1.0"

__all__ = [
    "WRITE_TOOLS",
    "__version__",
    "build_recruiter",
    "build_server",
    "main",
]
