"""Memory loader — builds a single 4-layer context string for the system prompt.

Layer budget (approximate tokens):
  Sensory     ~200    last 3 events
  Working     ~400    current session goal + open workflows + focused entities
  Long-term   ~400    top-5 high-confidence preferences (existing memories table)
  Entity      ~600    memories of entities referenced in the current message
              ─────
              ~1600  tokens

Call from agent.py's _build_pipeline_context() or chat_graph's build_context node.
"""

from __future__ import annotations

from app import database as db
from app.memory import entity as entity_mod
from app.memory import sensory, working


_LAYER_CAPS = {
    "sensory": 400,        # chars
    "working": 800,
    "long_term": 800,
    "entity": 1200,
}


def build_memory_context(
    user_id: str,
    session_id: str,
    message: str,
    candidates_in_context: list[dict] | None = None,
) -> str:
    """Return a formatted 4-layer memory string ready to splice into the system prompt.

    Empty layers are skipped. Returns "" if everything is empty.
    """
    sections: list[str] = []

    sensory_block = _format_sensory(user_id)
    if sensory_block:
        sections.append(sensory_block)

    working_block = _format_working(session_id)
    if working_block:
        sections.append(working_block)

    long_term_block = _format_long_term(user_id)
    if long_term_block:
        sections.append(long_term_block)

    entity_block = _format_entity(user_id, message, candidates_in_context)
    if entity_block:
        sections.append(entity_block)

    if not sections:
        return ""

    return "\n\n".join(["## Agent Memory", *sections])


# ── Per-layer formatters ──────────────────────────────────────────────────

def _format_sensory(user_id: str) -> str:
    events = sensory.recent_events(user_id, limit=3)
    if not events:
        return ""
    lines = ["### Sensory (last few minutes)"]
    for e in events:
        lines.append(f"- [{e.kind}] {e.summary}")
    return _cap("\n".join(lines), _LAYER_CAPS["sensory"])


def _format_working(session_id: str) -> str:
    state = working.get_working_memory(session_id)
    if not state:
        return ""
    parts = ["### Working (current session)"]
    if state.get("current_goal"):
        parts.append(f"Goal: {state['current_goal']}")
    open_wfs = state.get("open_workflows", [])
    if open_wfs:
        wf_strs = [f"{w.get('type', 'workflow')} ({w.get('status', 'running')})" for w in open_wfs]
        parts.append(f"Open workflows: {', '.join(wf_strs)}")
    focused = state.get("focused_entities", [])
    if focused:
        names = [f.get("name", f.get("entity_id", "?")) for f in focused]
        parts.append(f"Focused: {', '.join(names)}")
    if state.get("scratchpad"):
        parts.append(f"Scratchpad: {state['scratchpad']}")
    if len(parts) == 1:
        return ""
    return _cap("\n".join(parts), _LAYER_CAPS["working"])


def _format_long_term(user_id: str) -> str:
    mems = db.list_memories(user_id, limit=5)
    if not mems:
        return ""
    lines = ["### Long-term (learned preferences)"]
    for m in mems:
        tag = "[preference]" if m.get("memory_type") == "explicit" else "[observed]"
        lines.append(f"- {tag} {m['content']}")
    return _cap("\n".join(lines), _LAYER_CAPS["long_term"])


def _format_entity(user_id: str, message: str, candidates_in_context: list[dict] | None) -> str:
    rows = entity_mod.get_entities_for_message(user_id, message, candidates_in_context)
    if not rows:
        return ""
    lines = ["### Entity (relevant to this message)"]
    for r in rows:
        head = f"- {r['entity_type']}:{r['entity_id']}"
        if r.get("interaction_count"):
            head += f" (×{r['interaction_count']})"
        lines.append(head)
        if r.get("summary"):
            lines.append(f"  summary: {r['summary']}")
        relations = r.get("relations", [])
        if relations:
            lines.append(f"  relations: {', '.join(relations[:3])}")
    return _cap("\n".join(lines), _LAYER_CAPS["entity"])


def _cap(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
