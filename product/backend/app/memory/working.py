"""Working memory — current session state (goals, open workflows, focused entities).

Backed by the `session_state` table. Updated whenever an action is dispatched
or a workflow is started/paused/resumed.
"""

from __future__ import annotations

from app import database as db


def get_working_memory(session_id: str) -> dict | None:
    """Return the current working-memory snapshot for a session, or None if empty."""
    if not session_id:
        return None
    return db.get_session_state(session_id)


def update_working_memory(session_id: str, user_id: str, **fields) -> None:
    """Patch the session_state row.

    Supported fields:
      current_goal: str
      open_workflows: list[dict] — each {workflow_id, type, status}
      focused_entities: list[dict] — each {entity_type, entity_id, name}
      scratchpad: str — free-form notes
    """
    if not session_id or not user_id:
        return
    db.upsert_session_state(session_id, user_id, fields)


def add_focused_entity(session_id: str, user_id: str, entity_type: str, entity_id: str, name: str) -> None:
    """Add an entity to the focused list (dedup by id, last-N-keep)."""
    current = get_working_memory(session_id) or {}
    focused = current.get("focused_entities", [])
    focused = [f for f in focused if not (f.get("entity_type") == entity_type and f.get("entity_id") == entity_id)]
    focused.append({"entity_type": entity_type, "entity_id": entity_id, "name": name})
    focused = focused[-5:]
    update_working_memory(session_id, user_id, focused_entities=focused)
