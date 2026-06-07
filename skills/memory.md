# Memory System — 4-tier Agent Memory

```
                          Agent Memory
                              │
   ┌───────────────┬──────────┴────────┬───────────────┐
   │               │                   │               │
 Sensory       Working           Long-term         Entity
 (in-mem)    (session_state)    (memories)     (entity_memory)
```

| Layer | Lifetime | Backed by | What it stores |
|-------|----------|-----------|----------------|
| **Sensory** | ~30 min, in-process | Python ring buffer | Last 10 UI events per user (uploads, clicks, sends) |
| **Working** | Per session | `session_state` table | Current goal, open workflows, focused entities, scratchpad |
| **Long-term** | Forever | `memories` table | Explicit preferences ("prefer concise emails") + implicit patterns from activity logs |
| **Entity** | Forever | `entity_memory` table | Per-candidate / per-job rolling summary, traits, relations, interaction count |

## Module layout

```
backend/app/memory/
  sensory.py    — in-process ring buffer + emit_event / recent_events
  working.py    — session_state CRUD + add_focused_entity
  entity.py     — update_entity_after_action + get_entities_for_message
  loader.py     — build_memory_context() — composes all 4 layers
  __init__.py   — public re-exports
```

## How the loader composes context

`build_memory_context(user_id, session_id, message, candidates_in_context)` returns a single markdown block:

```
## Agent Memory

### Sensory (last few minutes)
- [upload_resume] uploaded Alice.pdf

### Working (current session)
Goal: hire Senior Backend in 2 weeks
Focused: Alice Zhang, Bob Smith

### Long-term (learned preferences)
- [preference] prefer concise emails
- [observed] leans toward backend candidates

### Entity (relevant to this message)
- candidate:c1 (×3)
  summary: strong on ML, asked for relocation
```

Empty layers are silently skipped. Total budget ~1600 tokens with per-layer char caps.

## Integration points

- **Loader call site**: `chat_graph._build_pipeline_context()` — runs in the `build_context` node before LLM call
- **Event emission**: `agent._update_memory_for_action()` — single hook at the top of `_process_actions`, dispatches to sensory + entity updates for every action type. No need to touch individual handlers.
- **Failures are silent**: memory bookkeeping must never break a chat turn (`try/except` around every loader and writer call site)

## Adding a new event source

If you want a non-action event (e.g. page navigation, file view) to surface in sensory memory:

```python
from app.memory import emit_event
emit_event(user_id, "view_candidate", f"opened {candidate_name}")
```

Just call from the relevant route handler. The next chat turn will see it under `### Sensory`.

## Adding entity traits

The entity memory schema is intentionally loose — traits is a free-form JSON dict. Common patterns:

```python
update_entity_after_action(
    user_id, "candidate", c_id, "evaluate_candidate",
    summary_hint="strong on ML, weak on cloud",
    traits={"score": 85, "top_match": "Senior ML"},
    relations=["referred_by:bob_smith", "applied_to:job_42"],
)
```

Traits are merged (last-write-wins per key). Relations are deduped (set-append semantics). Summary is overwritten by the latest hint.

## Tests

`tests/harness/test_memory.py` — 22 cases covering all 4 layers:
- Sensory: emit/recent, per-user isolation, ring buffer cap, TTL bypass
- Working: create/read/merge, focused entity dedup
- Entity: first-interaction creation, count bump, relation dedup, trait merge, per-user isolation, message-based resolution
- Loader: empty/single-layer/all-layers combinations, section ordering

Run: `cd backend && uv run python -m pytest ../tests/harness/test_memory.py -v`

## Why this layered model

- **Predictable context budget** — each layer has a fixed char cap; we never overflow the prompt
- **Different decay rates** — sensory clears in 30min, working dies with session, long-term survives forever
- **Cheap to scale** — sensory is RAM-only; working is one row per session; entity is one row per (user, entity); long-term is already token-capped at top-5
- **Failure isolation** — if entity-resolution regex misfires, the other 3 layers still serve correctly
