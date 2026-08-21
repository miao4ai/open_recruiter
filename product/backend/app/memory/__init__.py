"""4-tier memory system for Open Recruiter.

Layers:
  - sensory:  in-memory ring buffer of recent UI events (30min TTL, not persisted)
  - working:  current session state — goals, in-flight workflows, focused entities
  - long_term: persistent preferences (reuses existing `memories` table)
  - entity:   per-candidate / per-job / per-company history + traits + relations

See skills/backend.md for the design and loader.build_memory_context() for usage.
"""

from app.memory.sensory import SensoryBuffer, emit_event, recent_events
from app.memory.working import get_working_memory, update_working_memory
from app.memory.entity import update_entity_after_action, get_entities_for_message
from app.memory.loader import build_memory_context

__all__ = [
    "SensoryBuffer",
    "emit_event",
    "recent_events",
    "get_working_memory",
    "update_working_memory",
    "update_entity_after_action",
    "get_entities_for_message",
    "build_memory_context",
]
