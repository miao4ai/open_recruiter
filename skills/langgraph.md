# LangGraph — Chat Graph + Human-in-the-Loop

## Chat graph (backend/app/graphs/chat_graph.py)

Linear pipeline:

```
build_context → input_guard → call_llm → parse_response → output_guard → process_action → finalize
```

Each node is a pure function over the state dict. Failures at `input_guard` / `output_guard` short-circuit to `finalize` with a `guardrail_warning` block.

## SSE adapter (backend/app/graphs/sse_adapter.py)

Wraps the graph for streaming. Yields events:
- `token` — streamed text chunks
- `block` — structured `MessageBlock` (cards)
- `action` — structured action data (e.g. `compose_email`)
- `interrupt` — workflow paused for user approval
- `done` — terminal

## Human-in-the-Loop

Uses LangGraph `interrupt()` inside `process_action`. Three approval card types:

| Card | Used for | Payload returned to resume |
|------|----------|---------------------------|
| `SchedulingApprovalCard` | Interview scheduling | `{selected_slot: {...}}` |
| `PipelineCleanupCard` | Bulk pipeline mutations | `{approved: true, actions: [...]}` |
| `BulkOutreachCard` | Mass email campaigns | `{approved: true, drafts: [...]}` |

Resume/cancel endpoints (see `routes/automations.py` or workflow routes):
- `POST /api/workflow/{thread_id}/resume` — body is the user's response payload
- `POST /api/workflow/{thread_id}/cancel`

State persists via `SqliteSaver` — workflows survive process restart.

## Multi-agent (evaluation swarm)

`backend/app/agents/evaluation_swarm.py` runs 4 agents in parallel via `ThreadPoolExecutor`, then synthesizes:

```
       Resume Agent ─┐
       Culture Agent ─┤
                     ├─► Synthesizer ─► overall_score + recommendation
       Risk Agent ──┤
       Market Agent ─┘
```

Synthesizer weights: resume 40%, culture 25%, risk 20%, market 15%.

Pattern to follow when adding more swarms: separate prompts per agent, parallel execution, deterministic synthesis.

## Adding a new agent

1. Create `backend/app/agents/<name>.py` with a pure function: `(cfg, ...) → dict`
2. Add its system prompt to `prompts.py`
3. Wire it into either the chat graph (via `process_action`) or the swarm (via `evaluation_swarm`)
4. Add tests — mock the LLM call to keep tests fast
