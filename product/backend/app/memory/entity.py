"""Entity memory — per-candidate / per-job / per-company rolling summary.

Stored in the `entity_memory` table. Updated by the action handlers in agent.py
after each interaction (no LLM call needed for simple bookkeeping; deeper
summarization can be added later as a background agent).
"""

from __future__ import annotations

import re

from app import database as db


# ── Update on action ──────────────────────────────────────────────────────

def update_entity_after_action(
    user_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    *,
    summary_hint: str = "",
    traits: dict | None = None,
    relations: list[str] | None = None,
) -> None:
    """Bump interaction count + optionally update summary/traits/relations.

    Called from action handlers after compose_email, evaluate_candidate,
    match_candidate, recommend_to_employer, etc.
    """
    if not user_id or not entity_id:
        return

    updates: dict = {"bump_interaction": True}
    if summary_hint:
        updates["summary"] = summary_hint
    if traits:
        updates["traits"] = traits
    if relations:
        updates["relations"] = relations

    db.upsert_entity_memory(user_id, entity_type, entity_id, updates)


# ── Resolve entities from the current message ─────────────────────────────

_CANDIDATE_NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")


def get_entities_for_message(user_id: str, message: str, candidates_in_context: list[dict] | None = None) -> list[dict]:
    """Resolve which entities the current user message refers to.

    Strategy:
      1. Find capitalized full names in the message
      2. Cross-reference with the candidates the user actually has
      3. Fetch their entity_memory rows (only those that exist)

    Returns the entity_memory dicts (may be empty list).
    """
    if not message or not candidates_in_context:
        return []

    name_to_id = {c["name"]: c["id"] for c in candidates_in_context if c.get("name") and c.get("id")}
    if not name_to_id:
        return []

    refs: list[tuple[str, str]] = []
    seen = set()
    for match in _CANDIDATE_NAME_RE.findall(message):
        if match in name_to_id and match not in seen:
            refs.append(("candidate", name_to_id[match]))
            seen.add(match)

    return db.get_entity_memories_for(user_id, refs)
