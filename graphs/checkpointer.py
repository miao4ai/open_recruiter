"""LangGraph checkpoint persistence — SqliteSaver using the same DB file.

The app already uses SQLite with WAL mode. LangGraph's SqliteSaver creates
its own tables (checkpoints, checkpoint_writes, etc.) alongside the app's
tables in the same database, so workflow_id maps directly to thread_id.

Usage:
    from graphs.checkpointer import get_checkpointer

    checkpointer = get_checkpointer()
    graph = workflow.compile(checkpointer=checkpointer)
"""

from __future__ import annotations

from langgraph.checkpoint.sqlite import SqliteSaver

from app.database import DB_PATH

# Module-level singleton — reused across all graph compilations
_checkpointer: SqliteSaver | None = None


def get_checkpointer() -> SqliteSaver:
    """Return a shared SqliteSaver instance backed by the app's SQLite DB."""
    global _checkpointer
    if _checkpointer is None:
        conn = SqliteSaver.from_conn_string(str(DB_PATH))
        conn.setup()  # creates LangGraph checkpoint tables if missing
        _checkpointer = conn
    return _checkpointer
