# CLAUDE.md — Open Recruiter

## Project Overview

**Open Recruiter** is an AI-powered recruitment assistant desktop app (Electron + React + FastAPI). It runs 100% locally. Two modes: **Recruiter** (Erika Chan) and **Job Seeker** (Ai Chan).

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

## Rules — Don't Forget

- **Never bump version numbers** without explicit user instruction.
- **Never commit `frontend/tsconfig.tsbuildinfo` or `uv.lock`** — these are in `.gitignore` intent but sometimes show as modified. Do not stage them.
- All system prompts must instruct the LLM to **always respond in English** (Ollama/Qwen can drift to Chinese).
- When editing files, always **read first** before editing.
- Releases: macOS `.dmg`, Windows `.exe`, Linux `.AppImage` — exactly 3 artifacts. Configured in `electron/electron-builder.json`.

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
