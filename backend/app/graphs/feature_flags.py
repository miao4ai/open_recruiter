"""Feature flags for LangGraph migration.

Controls whether requests are routed through the new LangGraph-based
graphs or the legacy orchestrator pipeline. Flags are stored in the
DB ``settings`` table and can be toggled at runtime via the Settings UI.

DB keys:
  - ``use_langgraph_chat``      — route /agent/chat and /agent/chat/stream
                                   through chat_graph instead of direct LLM call
  - ``use_langgraph_workflow``  — route workflow execution through supervisor_graph
                                   instead of orchestrator.py

Both default to ``"false"`` — opt-in during migration.
"""

from __future__ import annotations

import logging

from app.database import get_settings

log = logging.getLogger(__name__)

# In-process cache (avoids hitting DB on every request).
# Invalidated by calling ``reload()``.
_cache: dict[str, bool] = {}


def _read(key: str, default: bool = False) -> bool:
    """Read a boolean flag from DB settings (cached)."""
    if key in _cache:
        return _cache[key]
    try:
        settings = get_settings()
        val = settings.get(key, str(default)).lower()
        result = val in ("true", "1", "yes", "on")
    except Exception:
        log.debug("Failed to read feature flag %s, using default=%s", key, default)
        result = default
    _cache[key] = result
    return result


def reload() -> None:
    """Clear the in-process cache so flags are re-read from DB."""
    _cache.clear()


# ── Public API ────────────────────────────────────────────────────────────

def use_langgraph_chat() -> bool:
    """True → route chat through ``chat_graph``; False → legacy LLM path."""
    return _read("use_langgraph_chat", default=False)


def use_langgraph_workflow() -> bool:
    """True → route workflows through ``supervisor_graph``; False → legacy orchestrator."""
    return _read("use_langgraph_workflow", default=False)
