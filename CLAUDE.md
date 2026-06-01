# CLAUDE.md — Open Recruiter

## Project Overview

**Open Recruiter** is an AI-powered recruitment assistant desktop app (Electron + React + FastAPI). It runs 100% locally. Two modes: **Recruiter** (Erika Chan) and **Job Seeker** (Ai Chan).

## Available Skills

Topic-specific guides — read the relevant one before working in that area:

- [skills/backend.md](skills/backend.md) — FastAPI structure, agents, the 6-step recipe for adding a chat action, LLM provider config
- [skills/langgraph.md](skills/langgraph.md) — chat graph pipeline, SSE adapter, Human-in-the-Loop approval cards, multi-agent swarm pattern
- [skills/testing.md](skills/testing.md) — pytest harness (136+ cases), how to run subsets, when a failure means a real gap vs a stale fixture
- [skills/deployment.md](skills/deployment.md) — version bump + tag + CI release flow, artifact naming, Gatekeeper / notarization notes

---

## Working Style

> Behavioral guidelines to reduce common LLM coding mistakes. These bias toward caution over speed — for trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that **your** changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

### Project-specific hard rules

- **Never bump version numbers** without explicit user instruction.
- **Never commit `frontend/tsconfig.tsbuildinfo` or `uv.lock`** — these appear modified but should not be staged.
- All system prompts must instruct the LLM to **always respond in English** (Ollama/Qwen can drift to Chinese).
- When editing files, always **read first** before editing.
- Releases: macOS `.dmg`, Windows `.exe`, Linux `.AppImage` — exactly 3 artifacts.

---

## Architecture

```
electron/          ← Electron shell (main.js, preload.js)
frontend/          ← React 19 + TypeScript + TailwindCSS (Vite)
  src/
    pages/         ← Full-page views (Jobs, Candidates, Chat, JobSeekerHome, …)
    components/    ← Reusable UI (MessageBlocks, SemanticSearchBar, …)
    lib/api.ts     ← All fetch calls to FastAPI backend
    types/index.ts ← Shared TypeScript interfaces
backend/           ← FastAPI + Python
  app/
    routes/        ← HTTP endpoints (agent.py is the main chat endpoint)
    agents/        ← Domain agents (resume, jd, matching, communication, …)
    graphs/        ← LangGraph state machine (chat_graph.py, sse_adapter.py)
    guardrails/    ← Input/output guard (policy.py)
    prompts.py     ← All LLM system prompts
    config.py      ← Runtime config (LLM provider, email, IMAP, Slack)
    database.py    ← SQLite init_db()
    vectorstore.py ← ChromaDB wrapper
tests/             ← Pytest harness (intent detection, guardrails)
electron/
  electron-builder.json  ← Produces: macOS DMG, Windows EXE, Linux AppImage
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/routes/agent.py` | Main chat SSE endpoint, action dispatch, intent routing |
| `backend/app/graphs/chat_graph.py` | LangGraph graph: build_context → input_guard → call_llm → parse_response → output_guard → process_action → finalize |
| `backend/app/prompts.py` | All system prompts — edit here to change AI behavior |
| `backend/app/config.py` | LLM provider defaults (Anthropic/OpenAI/Gemini/Ollama) |
| `frontend/src/components/MessageBlocks.tsx` | Renders all chat message card types |
| `frontend/src/types/index.ts` | MessageBlock union type — add new block types here first |
| `frontend/src/lib/api.ts` | All API calls — add new endpoints here |

## LLM Providers & Models

Configured in `backend/app/config.py`:
- **anthropic** → `claude-sonnet-4-20250514`
- **openai** → `gpt-5.1`
- **gemini** → `gemini-2.5-flash`
- **ollama** → `qwen3.5:2b` (local, offline)

Override via Settings UI or `.env` (`LLM_PROVIDER`, `LLM_MODEL`).

## Chat System

### Intent Detection (3-layer fallback)
1. LLM returns structured JSON `{"action": "...", "params": {...}}`
2. Keyword regex fallback (in `agent.py`)
3. Role-based whitelist (`_RECRUITER_ALLOWED_ACTIONS`, `_SEEKER_ALLOWED_ACTIONS`)

### Adding a New Action
1. Add action name to allowed list in `agent.py`
2. Add handler function `_handle_<action>()` in `agent.py`
3. Add trigger phrases to the relevant system prompt in `prompts.py`
4. Add new `MessageBlock` type in `frontend/src/types/index.ts`
5. Add render card in `frontend/src/components/MessageBlocks.tsx`
6. Add intent test cases in `tests/harness/test_intent_detection.py`

### Human-in-the-Loop
Uses LangGraph `interrupt()`. Frontend shows approval cards:
- `SchedulingApprovalCard` — confirm interview scheduling
- `PipelineCleanupCard` — confirm bulk pipeline changes
- `BulkOutreachCard` — confirm mass email campaigns

Resume/cancel via `POST /api/workflow/{thread_id}/resume` and `/cancel`.

## Search

`backend/app/routes/search.py` — hybrid search (ChromaDB semantic + SQLite keyword).

Relevance thresholds (to avoid garbage results):
- Keyword-only hit OR semantic score ≥ 0.50 (semantic-only)
- Minimum hybrid score: 0.20

Search feedback stored in `search_feedback` table (👍👎 from UI).

## Test Harness

Pytest tests at `tests/harness/`:
- `test_intent_detection.py` — keyword fallback, action whitelist, intent disambiguation
- `test_guardrails.py` — input/output validation, action limits, severity priority

Run from `backend/`:
```bash
uv run python -m pytest ../tests/harness/ -v
```

## CI/CD

GitHub Actions at `.github/workflows/`. Triggers on version tag push (`v*.*.*`).
Builds all 3 platforms and creates a GitHub Release with the 3 artifacts.

To release:
```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

Delete a release before re-tagging:
```bash
gh release delete vX.Y.Z --yes
git push origin --delete vX.Y.Z
git tag -d vX.Y.Z
```

## Dev Setup

```bash
scripts/setup.sh        # install Python deps (uv) + node deps
scripts/start.sh        # starts FastAPI on :8000 + Vite on :5173
```

Frontend hot-reloads. Backend requires restart on Python changes.

Electron dev: `npm run electron:dev` from project root.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
