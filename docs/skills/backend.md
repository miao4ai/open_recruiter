# Backend — FastAPI + Agents

## Structure

```
product/backend/app/
  routes/         ← HTTP endpoints
    agent.py      ← Main chat SSE endpoint (action dispatch + intent routing)
    seeker.py     ← Job seeker endpoints
    jobs.py, candidates.py, emails.py, search.py, ...
  agents/         ← Domain logic
    matching.py        ← JD-candidate scoring
    evaluation_swarm.py ← 4-agent parallel evaluation + synthesizer
    communication.py   ← Email drafting
    market.py          ← Salary/market analysis
    employer.py        ← Hiring-manager outreach
    workflow.py, planning.py, jd.py, resume.py, job_search.py, scheduling.py
  graphs/         ← LangGraph state machine (see langgraph.md)
  guardrails/     ← Input/output guard + action limits (see testing.md)
  tools/          ← imap_checker, email_sender, etc.
  prompts.py      ← ALL LLM system prompts (single source of truth)
  llm.py          ← LiteLLM wrapper, prompt caching
  config.py       ← LLM provider + email + Slack config
  database.py     ← SQLite init_db + helpers
  vectorstore.py  ← ChromaDB wrapper
```

## Adding a new chat action

Six files touched, in this order:

1. **agent.py** — whitelist (`_SEEKER_ALLOWED_ACTIONS` if seeker; recruiter default)
2. **agent.py** — handler: `elif action_type == "<new>": ...`
3. **prompts.py** — trigger phrases inside `CHAT_SYSTEM_WITH_ACTIONS` or `CHAT_SYSTEM_JOB_SEEKER`
4. **agent.py** (optional) — keyword fallback in `_detect_action_from_keywords()` for weak local models
5. **frontend/src/types/index.ts** — new block interface + add to `MessageBlock` union
6. **frontend/src/components/MessageBlocks.tsx** — dispatch case + card component

Then add intent test cases — see `testing.md`.

## LLM providers

Configured in `config.py`. **Slim build (3.0+): chat is Anthropic (default) or OpenAI only — Gemini/Ollama were dropped, and embeddings use the Voyage API (`VOYAGE_API_KEY`), not a local model.**
- `anthropic` → `claude-sonnet-5` (default); also `claude-opus-4-8`, `claude-haiku-4-5`
- `openai` → `gpt-5.1`
- embeddings → Voyage `voyage-4-lite`

Model IDs get retired on a schedule — a retired ID returns `not_found_error` (not auth). Check current IDs with the `claude-api` skill before changing them.

`llm.py` enables **Anthropic prompt caching** automatically for system prompts ≥ 4000 chars — 90% input cost reduction on cache hits.

## Hard rules

- All system prompts must instruct the LLM to **respond in English** (Ollama/Qwen drifts to Chinese).
- Always **read first** before editing — Edit tool enforces this.
- Never commit `product/frontend/tsconfig.tsbuildinfo` or `uv.lock`.
