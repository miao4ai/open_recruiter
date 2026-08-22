# CLAUDE.md — Open Recruiter

## Project Overview

**Open Recruiter** is a monorepo: an AI-powered recruitment assistant desktop app (Electron + React + FastAPI) in `product/`, the Python SDKs it is built on in `sdk/`, and the experiments behind them in `research/`. As of **3.0 (slim build)** it is cloud-backed — Claude/OpenAI for chat and the Voyage API for embeddings (bring your own keys); local ML (PyTorch / Whisper / ONNX) was removed. Two modes: **Recruiter** (Erika Chan) and **Job Seeker** (Ai Chan).

See [CONTRIBUTING.md](CONTRIBUTING.md) for the per-layer setup paths.

## Available Skills

Topic-specific guides — read the relevant one before working in that area:

- [docs/skills/backend.md](docs/skills/backend.md) — FastAPI structure, agents, the 6-step recipe for adding a chat action, LLM provider config
- [docs/skills/langgraph.md](docs/skills/langgraph.md) — chat graph pipeline, SSE adapter, Human-in-the-Loop approval cards, multi-agent swarm pattern
- [docs/skills/memory.md](docs/skills/memory.md) — 4-tier agent memory (sensory / working / long-term / entity), loader integration, event emission
- [docs/skills/testing.md](docs/skills/testing.md) — pytest harness (137 cases), how to run subsets, when a failure means a real gap vs a stale fixture
- [docs/skills/deployment.md](docs/skills/deployment.md) — version bump + tag + CI release flow, artifact naming, Gatekeeper / notarization notes
- [docs/skills/mcp.md](docs/skills/mcp.md) — stdio MCP server exposing recruiter matching/evaluation tools to external chat agents

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
- **Never commit `product/frontend/tsconfig.tsbuildinfo` or `uv.lock`** — these appear modified but should not be staged.
- All system prompts must instruct the LLM to **always respond in English** (Ollama/Qwen can drift to Chinese).
- When editing files, always **read first** before editing.
- Releases: macOS `.dmg`, Windows `.exe`, Linux `.AppImage` — exactly 3 artifacts.

---

## Architecture

```
product/               ← the desktop app — builds the 3 installers
  electron/            ← Electron shell (main.ts, preload.ts)
  frontend/            ← React 19 + TypeScript + MUI (Vite)
    src/
      pages/           ← Full-page views (Jobs, Candidates, Chat, JobSeekerHome, …)
      components/      ← Reusable UI (MessageBlocks, SemanticSearchBar, …)
      lib/api.ts       ← All fetch calls to FastAPI backend
      types/index.ts   ← Shared TypeScript interfaces
      i18n/            ← 6 locales
  backend/             ← FastAPI + Python — a consumer of sdk/core
    app/
      routes/          ← HTTP endpoints (agent.py is the main chat endpoint)
      agents/          ← Domain agents (resume, jd, matching, communication, …)
      graphs/          ← LangGraph state machine (chat_graph.py, sse_adapter.py)
      guardrails/      ← Input/output guard (policy.py)
      memory/          ← 4-tier agent memory
      prompts.py       ← All LLM system prompts
      config.py        ← Runtime config (LLM provider, email, IMAP, Slack)
      database.py      ← SQLite init_db()
      vectorstore.py   ← ChromaDB + Voyage embeddings
    open_recruiter.spec ← PyInstaller bundle
  tests/               ← Pytest harness (intent detection, guardrails, memory)
  scripts/             ← setup / start / build, for macOS·Linux (.sh) and Windows (.ps1)
  images/              ← app icons, also used by electron-builder
  electron/electron-builder.json  ← Produces: macOS DMG, Windows EXE, Linux AppImage

sdk/                   ← published Python packages, each `pip install`-able on its own
  core/                ← openrecruiter — the engine: types, stores, ranking, tools, agent
  fairness/            ← openrecruiter-fairness — fairness-aware ranking backend
  recruitgpt/          ← recruitgpt — distilled ranking model backend

research/              ← reproducible experiments behind the SDKs
  fairness/            ← bias evaluation, anonymization, counterfactual testing
  recruitgpt/          ← LLM judge, hard negatives, distillation, benchmarks

docs/
  guides/              ← user manual, release notes, roadmaps
  skills/              ← the topic guides linked above
```

Dependency direction is one-way and enforced in CI by
`.github/scripts/check_architecture.py`:

```
product  ──→  sdk        product/backend consumes sdk/core
research ──→  sdk        experiments build on the same interfaces
product  ──X  research   production code never imports research code
```

Nothing in `sdk/` may import from `product/`. `product/backend` and `sdk/core` must
also stay free of training dependencies (torch, transformers, datasets, …) — those
belong in optional extras or in the research packages. The check runs on every push.

`ranking` as a word is reserved for the `Ranker` capability inside `sdk/core`. The two
research tracks are named by subject — `fairness` and `recruitgpt` — so there is never
an `sdk/ranking` and a `research/ranking` meaning different things.


## Key Files

| File | Purpose |
|------|---------|
| `product/backend/app/routes/agent.py` | Main chat SSE endpoint, action dispatch, intent routing |
| `product/backend/app/sdk_bridge.py` | `ProductStore` — the SDK's `Store` over `database.py`; builds the `Recruiter` |
| `product/backend/app/agent_tools.py` | App-specific tools (upload cards, inbox, web job search) + the role filter |
| `product/backend/app/sse_agent.py` | Agent events → SSE frames the chat UI understands |
| `sdk/core/openrecruiter/agent.py` | The agent loop: tool calls, approval gates, streaming |
| `sdk/core/openrecruiter/ranking/` | `Ranker` and its backends — the main extension point |
| `product/backend/app/graphs/chat_graph.py` | Legacy LangGraph path, still serving `/api/agent/chat` |
| `product/backend/app/prompts.py` | All system prompts — edit here to change AI behavior |
| `product/backend/app/config.py` | LLM + Voyage config (slim build: Anthropic/OpenAI only) |
| `product/frontend/src/components/MessageBlocks.tsx` | Renders all chat message card types |
| `product/frontend/src/types/index.ts` | MessageBlock union type — add new block types here first |
| `product/frontend/src/lib/api.ts` | All API calls — add new endpoints here |

## LLM Providers & Models

Configured in `product/backend/app/config.py`. **Slim build (3.0+): chat is locked to cloud providers — Anthropic (default) or OpenAI. Gemini/Ollama were dropped from the UI, and `_build_config()` forces any other stored provider back to Anthropic. Embeddings run on the Voyage API, not a local model.**

- **anthropic** → `claude-sonnet-5` (default); also `claude-opus-4-8`, `claude-haiku-4-5`
- **openai** → `gpt-5.1`
- **embeddings (Voyage)** → `voyage-4-lite` (requires `VOYAGE_API_KEY`)

> Model IDs move fast — Claude models are retired on a schedule. Verify current IDs with the `claude-api` skill before changing them; a retired ID returns `not_found_error` (not an auth error).

Override via Settings UI or `.env` (`LLM_PROVIDER`, `LLM_MODEL`, `VOYAGE_API_KEY`).

## Chat System

`POST /api/agent/chat/stream` runs the SDK agent. The model is given real tool schemas and
decides what to call, in what order, and when it is finished — so one request can rank a job,
read the result, and draft the emails. Text streams as it is generated.

```
routes/agent.py  →  sdk_bridge.build_recruiter()  →  openrecruiter.Agent
                    agent_tools.product_tools()       │
                                                      ▼
                    sse_agent.stream_agent()  ──▶  token · tool_call · tool_result
                                                   approval_required · done
```

`ProductStore` in `sdk_bridge.py` implements the SDK's `Store` protocol over `database.py`,
so both the agent and the REST endpoints read the same tables. Nothing was migrated.

### Adding a New Tool
1. Add a `Tool` to `agent_tools.py` (app-specific) or `sdk/core/openrecruiter/tools/` (domain)
2. If a job seeker may call it, add the name to `SEEKER_TOOLS` — the role filter runs before
   the model sees a schema
3. To render its result as a card: map it in `sse_agent._as_block()`
4. Add the `MessageBlock` type in `product/frontend/src/types/index.ts`
5. Add the render card in `product/frontend/src/components/MessageBlocks.tsx`
6. Add tests — `sdk/core/tests/` for a domain tool, `product/tests/harness/` for an app one

Set `requires_approval=True` on anything that reaches outside the system. The agent stops and
emits `ApprovalRequired`; calls queued behind it are held too.

> **Legacy path still live.** `POST /api/agent/chat` (non-streaming) and `JobSeekerHome.tsx`
> still use `_process_actions()` in `agent.py` — a 1030-line if/elif over 20 actions — and the
> LangGraph `chat_graph`. It renders ~20 block types the SDK path maps only four of, so
> migrating it means porting those cards first. Do not delete it before then.

### Human-in-the-Loop
Uses LangGraph `interrupt()`. Frontend shows approval cards:
- `SchedulingApprovalCard` — confirm interview scheduling
- `PipelineCleanupCard` — confirm bulk pipeline changes
- `BulkOutreachCard` — confirm mass email campaigns

Resume/cancel via `POST /api/workflow/{thread_id}/resume` and `/cancel`.

## Search

`product/backend/app/routes/search.py` — hybrid search (ChromaDB semantic + SQLite keyword).

Relevance thresholds (to avoid garbage results):
- Keyword-only hit OR semantic score ≥ 0.50 (semantic-only)
- Minimum hybrid score: 0.20

Search feedback stored in `search_feedback` table (👍👎 from UI).

## Test Harness

Pytest tests at `product/tests/harness/`:
- `test_intent_detection.py` — keyword fallback, action whitelist, intent disambiguation
- `test_guardrails.py` — input/output validation, action limits, severity priority
- `test_memory.py` — 4-tier memory layers, loader budget, event emission

Run from `product/backend/`:
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
product/scripts/setup.sh   # install Python deps (uv) + node deps
product/scripts/start.sh   # starts FastAPI on :8000 + Vite on :5173
```

Frontend hot-reloads. Backend requires restart on Python changes.

Electron dev: `npm run electron:dev` from `product/`.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
