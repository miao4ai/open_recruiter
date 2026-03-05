"""Router — thin entry point that delegates to the Supervisor.

In v2.0 the routing logic lives inside the Supervisor graph itself
(check_paused → classify_intent → route). This module re-exports the
supervisor_graph so callers can import from either location.

Usage:
    from app.graphs.router import supervisor_graph

    result = supervisor_graph.invoke({
        "cfg": config,
        "user_id": "u1",
        "session_id": "s1",
        "user_message": "Help me find candidates for the engineer role",
    })
"""

from app.graphs.supervisor import supervisor_graph  # noqa: F401
