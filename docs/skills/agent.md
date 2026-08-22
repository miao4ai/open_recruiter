# Agent — tools, the loop, and approval gates

The chat path runs `openrecruiter.Agent`. The model is given real tool schemas and decides
what to call, in what order, and when it is finished. A single request can rank a job, read
the result, and draft three emails.

> Replaced the LangGraph chat graph in 4.0. The old design asked the model for JSON, parsed
> it with a regex fallback, matched a keyword table when that failed, and dispatched one
> action through a 1030-line if/elif. `docs/guides/v2-langgraph-architecture.md` describes it
> for anyone reading old commits.

## The path

```
routes/agent.py  _prepare_turn()          session, history, tools, system prompt
                        │
sdk_bridge.py    build_recruiter()        SDK client over the app's own database
agent_tools.py   product_tools()          app-specific tools joined to the SDK's
                        │
                 tools_for_role()         a seeker's registry is filtered here,
                        │                 before the model sees a schema
sse_agent.py     stream_agent()           events -> SSE frames
                        │
                 token · tool_call · tool_result · approval_required · done
```

Both chat endpoints go through `_prepare_turn`. `/chat/stream` forwards the frames;
`/chat` drains the same generator and returns the `done` payload. They ran separate
implementations before, and one of them quietly rotted — keep them sharing.

## Adding a tool

Domain capability → `sdk/core/openrecruiter/tools/recruiting.py`.
Anything app-specific (a UI panel, an integration, this user's own profile) →
`product/backend/app/agent_tools.py`.

```python
Tool(
    name="check_calendar",
    description="Look at the recruiter's availability this week",
    parameters={"type": "object", "properties": {"days": {"type": "integer"}}, "required": []},
    fn=check_calendar,
)
```

The description is read by the model, so say *when to reach for it*, not just what it does.
Compare `rank_candidates` ("use this for 'who should I look at for X'") with a bare "ranks
candidates".

Then:

1. If a job seeker may call it, add the name to `SEEKER_TOOLS`.
2. To render its result, map it in `app/blocks.py` — `as_block` for something that can appear
   several times in a turn, `as_action` for the one primary outcome. A message carries a list
   of blocks but at most one action.
3. Add the block type to `product/frontend/src/types/index.ts` and a card in
   `MessageBlocks.tsx`.
4. Test it. `sdk/core/tests/` for a domain tool, `product/tests/harness/test_blocks.py` for
   the shape the UI reads.

A block with the right `type` and the wrong keys renders as an empty card and nobody notices
until a user does — which is why `test_blocks.py` asserts on the exact fields the front end
indexes into.

## Approval gates

Set `requires_approval=True` on anything that reaches outside the system. The agent stops,
emits `ApprovalRequired`, and **holds every call the model queued behind it** — running those
would make the gate cosmetic.

The state is parked in the `workflows` table as a serialised `PendingApproval`, because the
decision arrives on a later request:

```
POST /api/agent/workflow/{id}/resume  {"approved": true}
POST /api/agent/workflow/{id}/cancel
```

The workflow is marked spent *before* the tool runs, so a double-click cannot send twice.
Declining is not an error — the model is told the user refused and gets to respond.

## The system prompt

`AGENT_RECRUITER` and `AGENT_SEEKER` in `prompts.py`. They carry the persona, the tone
boundaries, and the context — not the capabilities. The tool schemas describe those, so the
prompt cannot drift out of sync with the code.

`CHAT_SYSTEM_WITH_ACTIONS` is still in the file for reference. Do not use it with tools: it
ends by demanding JSON-only output, and a model told to answer in JSON will describe an
action instead of calling it.

## Context

`recruiter.pipeline_context(message)` builds a bounded briefing — open jobs, the pipeline
distribution, and the handful of candidates retrieved for this message. It does not grow with
the database. Anyone it does not name is a `search_candidates` call away, and the briefing
says so.

## Debugging

- **The model narrates instead of acting** — the system prompt is probably asking for JSON,
  or the tool description does not say when to use it.
- **A tool never gets called** — check `tools_for_role`; a seeker only sees `SEEKER_TOOLS`.
- **The card is empty** — the block type is right and the keys are wrong. See `blocks.py`.
- **The turn ends early** — `max_steps` is 8. `Finished.stop_reason` says which guard fired.
- **Nothing streams** — the frames are named `token`; anything else and the client ignores them.
