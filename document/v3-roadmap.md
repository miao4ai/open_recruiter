# Open Recruiter V3.0 Roadmap

> V1.x delivered the core recruiting workflow; V2.x refactored the monolithic orchestrator into a LangGraph multi-agent architecture, and added guardrails, HIL, local LLM, and voice input.
> **The mission of V3.0**: evolve from a "reactive tool" to an "Autonomous Recruiting Partner."
>
> - No longer working only when the user speaks → proactively monitor and push action suggestions
> - No longer just single-turn Q&A → cross-session, multi-day goal-driven execution
> - No longer just a data-entry tool → end-to-end candidate lifecycle loop

---

## V2 Recap — Delivered vs Deferred

| V2 Roadmap Direction | Status | Notes |
|---------------------|--------|-------|
| LangGraph refactor of the AI layer | ✅ Delivered (V2.0) | Full orchestrator replacement; added guardrails / HIL / SqliteSaver |
| 4-Agent candidate evaluation swarm | ✅ Delivered (V2.1) | resume / culture / risk / market parallel scoring + synthesizer |
| Voice input | ✅ Delivered (V2.1.x) | Local faster-whisper, offline transcription |
| Recruiter Chrome Extension | ⏳ Deferred to V3 | LinkedIn DOM selector maintenance cost under evaluation |
| Job Seeker Chrome Extension | ⏳ Deferred to V3 | To be merged with the Recruiter extension into a single plugin |
| Voice reply (TTS) | ⏳ Deferred to V3 | Folded into Direction 2 |

---

## Five Directions

### Direction 1: Autonomous Agents — Proactive Recruiting Assistant

**Goal**: Shift from "waiting for the user to ask" to "proactively discovering moments that need action."

**Core Capabilities**

| Capability | Description |
|-----------|-------------|
| Goal-driven Agents | User gives a goal ("hire a Senior Backend within two weeks"), the Agent autonomously decomposes tasks, drives progress, and reports back at milestones |
| Pipeline Watcher | Continuously monitors stalled pipeline stages, unanswered emails, and silent interview follow-ups, proactively producing action cards |
| Idle-time task scheduling | While the user is away, runs evaluations, organizes inbox, and generates daily briefings in the background |
| Cross-session long-running workflows | LangGraph workflows persist across processes (foundation already in SqliteSaver); resume execution after interrupts |
| Proactive Briefing | Every morning auto-generates a "Today's Recruiting Briefing": urgent actions / candidate status changes / pending replies |

**Technical Approach**
- Reuse `app/scheduler.py` (APScheduler) as the trigger, but swap the execution body for LangGraph workflows
- New `app/agents/autonomous/` module: `pipeline_watcher.py`, `goal_driver.py`, `briefing_agent.py`
- Persistence: new table `agent_goals` (id, user_id, description, status, progress_jsonl, created_at)
- Proactive notifications: reuse the existing `notifications` table + frontend toast

**Critical Constraints**
- All destructive actions (sending emails, modifying pipeline, deleting data) **must** go through HIL approval; no silent execution by Agents
- User can pause / take over any Agent with one click
- Agent behavior is fully auditable (new table `agent_actions`: thread_id, agent, action, params_json, status, created_at)
- **Must be gated by Quota Enforcement** (see Cross-cutting Capabilities below) — autonomous mode is NOT allowed to ship without quota gates

**Success Metrics**
- Reduction in user-initiated actions ≥ 30%
- Reduction in candidates stalled > 3 days at a pipeline stage ≥ 50%
- Daily briefing open rate ≥ 60%

---

### Direction 2: Voice Suite — Full-duplex Voice + Interview Transcription

**Goal**: Extend the V2.1 voice input into a complete voice interaction system.

**Core Capabilities**

| Capability | Status | Description |
|-----------|--------|-------------|
| Voice input (STT) | ✅ Delivered in V2.1 | faster-whisper, local |
| Voice reply (TTS) | 🆕 V3 | Piper (local, ~50MB) as default; ElevenLabs as optional cloud high-quality |
| Continuous conversation mode | 🆕 V3 | VAD (voice activity detection) auto-segments; no need to click the mic each time |
| Interview transcription | 🆕 V3 | Browser/meeting mic capture → real-time transcription → structured notes by competency dimension |
| Multi-language auto-detection | 🆕 V3 | Whisper's built-in language detection; UI shows detected language |
| Voice commands | 🆕 V3 | High-frequency commands like "save this candidate", "email HR" route directly through intent → action |

**Interview Transcription Flow**
```
Browser MediaRecorder ──► Chunked upload (10s/chunk) ──► /api/transcribe/stream
                                                              │
                                                              ▼
                                                     faster-whisper
                                                              │
                                                              ▼
                                              Chunk stitching + speaker diarization
                                                              │
                                                              ▼
                                                  LangGraph note Agent
                                                  (extracts by dimension)
                                                              │
                                                              ▼
                                              CandidateInterviewNote table
```

**New Dependencies**
- TTS: `piper-tts` (local, CPU-friendly)
- Speaker diarization (optional, high complexity): `pyannote-audio` — decision on whether to include in V3 pending evaluation

**Success Metrics**
- Voice transcription accuracy ≥ 92% (English) / ≥ 88% (Chinese)
- Interview note automation rate ≥ 80% (recruiter only accepts or lightly edits)
- End-to-end latency ≤ 3 seconds (speech end → text appears)

---

### Direction 3: Sourcing & Outbound — Proactive Candidate Discovery

**Goal**: Shift from "wait for candidates to come" to "actively find people + auto follow-up."

**Chrome Extension (V2 deferred item lands here)**
- Single plugin, switches panel based on the logged-in account role (Recruiter / Job Seeker)
- One-click save LinkedIn / Indeed / Glassdoor pages to local
- Already-saved candidates / jobs are visually marked
- DOM selectors have multiple fallbacks + errors reported to a local SQLite table `extension_errors`

**Active Sourcing**

| Channel | Approach |
|---------|----------|
| GitHub | Search developers by language / location / repo stars; public API |
| LinkedIn public search | Triggered by extension user navigation, no backend scraping (compliance) |
| Public datasets | Public resume corpora on HuggingFace / Kaggle, indexed offline |
| Candidate activity signals | GitHub commit frequency / LinkedIn updated_at signals |

**Outbound Sequence Engine**
- 3-touch template: initial contact → soft follow-up (3 days) → final touch (7 days)
- Every email personalized by the LLM based on the candidate's profile
- A/B test subject lines (success metric: open rate)
- Conditional branching: replied / opened-but-no-reply / not-opened
- Entire sequence under HIL approval — bulk preview / edit / cancel supported

**New APIs**
- `POST /api/candidates/from-extension`
- `GET /api/candidates/check?linkedin_url=...`
- `POST /api/sourcing/github/search`
- `POST /api/outreach/sequence` — create a 3-touch sequence
- `GET /api/outreach/sequence/{id}/status` — view the status of each touch

**Success Metrics**
- Average reply rate improves ≥ 2x over single-email outreach
- Share of candidates from "active sourcing" ≥ 30%
- Chrome extension monthly active users ≥ 50% of total users

---

### Direction 4: Deep Integrations — ATS / Calendar / Mail

**Goal**: Make Open Recruiter the "intelligence layer" on top of the existing recruiting toolchain, rather than an isolated tool.

**ATS Integration** (by priority)
1. **Greenhouse** — most widely used, complete REST API
2. **Lever** — second-largest, stable API
3. **Ashby** — fast-growing next-generation ATS

**Integration Depth**: bidirectional sync for candidates / jobs / pipeline status. Conflict resolution strategy: last-write-wins by modification time, with an approval card surfaced on conflicts.

**Calendar Upgrade**
- Google Calendar OAuth + bidirectional sync (not just one-way write)
- Outlook / Microsoft 365
- Conflict detection: automatically avoid candidate and interviewer schedule clashes when scheduling
- Timezone intelligence: for cross-timezone candidates, suggest time slots reasonable for both parties

**Email Upgrade**
- Native Gmail API / Microsoft Graph integration (replacing IMAP polling)
- Real-time webhooks: candidate replies hit the inbox immediately, no more 5-minute polling
- Read/unread state, full thread structure, native attachment handling

**Slack Upgrade**
- Full workflow cards (not just resume receiving)
- HIL approvals completable inside Slack (no need to switch back to the desktop app)
- `/recruiter` slash command supports common operations

**Success Metrics**
- At least 1 ATS integration is production-ready (end-to-end sync error rate < 1%)
- Calendar bidirectional sync conflict rate < 5%
- Email reply latency drops from 5 minutes to < 30 seconds

---

### Direction 5: Analytics & Forecasting

**Goal**: Turn the data we already have into actionable insights.

**Pipeline Funnel**
- Visualize stage-to-stage conversion rates (Sankey diagram)
- Group by job / by recruiter / by time period
- Anomaly detection: proactively alert when a stage's conversion rate drops suddenly

**Predictive Models** (local ONNX, avoiding cloud calls)
- Time-to-hire prediction: based on job type, location, salary → expected days
- Candidate response probability: based on profile + email content → reply probability 0-100%
- Pipeline health score: composite signal scoring each job 0-10

**Report Automation**
- Hiring manager weekly digest: auto-generated PDF emailed every Monday morning
- Candidate portfolio analysis: skills / location / salary distribution across the current pipeline

**Technical Approach**
- New `backend/app/analytics/` module
- Predictive models trained with scikit-learn → exported to ONNX → inferred with existing `onnxruntime`
- Report generation: `weasyprint` or `reportlab`

**Success Metrics**
- Predicted time-to-hire average error vs actual ≤ 5 days
- Response probability model ROC-AUC ≥ 0.75
- Weekly digest subscription rate ≥ 70%

---

## Cross-cutting Capability: Quota Enforcement & Safety Net

> This is a **prerequisite** for shipping Direction 1 (Autonomous Agents) and Direction 3 (Outbound sequences).
> No quota gate = leaving the door open to your credit card and the candidates' inboxes.

### Why this is needed

V3 puts "proactive behavior" at the core: autonomous agents, outbound sequences, sourcing API calls, interview transcription. Any logic error or prompt-injection compromise could lead to:
- Cloud LLM bill burned overnight (cloud providers bill per-token)
- Hundreds of emails firing into candidate inboxes (brand damage + Gmail spam-rule triggers)
- Third-party API rate limits being tripped (GitHub / DuckDuckGo / ATS webhook all going down)

### Quota Dimensions

| Scope | Metric | Action on Limit | Default Cap (user-adjustable) |
|-------|--------|-----------------|------------------------------|
| `llm.tokens.daily` | Daily cumulative tokens (counted per provider) | Auto-degrade to local Ollama; notify user | 100k tokens each for Anthropic / OpenAI / Gemini |
| `llm.cost.monthly` | Monthly USD (estimated by provider pricing) | Hard-stop, requires manual user override | $20 / month / provider |
| `email.outbound.hourly` | Emails sent per hour | Queue + show warning bar | 30 |
| `email.outbound.daily` | Daily cumulative emails | Hard-stop | 200 |
| `pipeline.bulk_change.daily` | Pipeline rows modified by autonomous flows per day | Hard-stop | 50 |
| `sourcing.api_calls.daily` | GitHub / external sourcing API calls per day | Queue to next day | 1000 |

### Technical Approach

- New table `usage_log` (id, scope, period_key, count, cost_cents, ts) — append-only, aggregated on demand
- New table `quota_config` (user_id, scope, period, limit, enforce_action) — user-configurable in Settings
- Decorator `@enforce_quota(scope=...)` wraps key call sites:
  - `app/llm.py` — check before LLM call + record after (with token / cost)
  - `app/email_sender.py` — check before sending + record after
  - `app/agents/autonomous/` — check before pipeline mutations
  - Third-party sourcing clients — check before API calls
- Behavior on hitting the cap is configured via `enforce_action`: `block` / `degrade_to_ollama` / `queue` / `warn_only`
- Settings UI adds a "Usage & Quotas" page: realtime progress bars + historical usage charts + quota adjustment + notification preferences when limits are hit

### Integration with Existing Systems

- **Guardrails layer**: the quota check becomes a new line of defense after input guard and before action dispatch
- **Audit log**: `agent_actions` table gains a `quota_consumed_jsonl` field recording each Agent decision's resource consumption
- **Degradation chain**: when cloud LLM hits the cap → automatically switch to local Ollama (infra already exists), keeping the core flow uninterrupted

### Success Metrics

- 0 incidents of "bill events" or "email-spam events" caused by quota failures
- 99% of normal usage does not hit the cap (default quotas should not constantly get in users' way)
- Hit-to-notification latency ≤ 1 second

### Out of Scope

- ❌ Sophisticated token-bucket / leaky-bucket algorithms — a SQLite counter is enough for a single-user desktop app
- ❌ Cross-device / cross-user quota aggregation — V3 remains single-user local-first
- ❌ Billing / paid tiers — this is not SaaS; quotas are purely a safety guardrail

---

## Release Plan

| Stage | Content | Priority | Target Time |
|-------|---------|----------|-------------|
| V3.0-pre-alpha | **Quota Enforcement & Safety Net** (cross-cutting, prerequisite for Direction 1) | P0 | 2026 Q2 |
| V3.0-alpha | Autonomous Agents core (Direction 1) | P0 | 2026 Q2 |
| V3.0-beta | Voice Suite full set (Direction 2) | P0 | 2026 Q3 |
| V3.0-rc1 | Chrome Extension + Sourcing (Direction 3, outbound sequence depends on quotas) | P0 | 2026 Q3 |
| V3.0-rc2 | ATS Integration (Direction 4, start with Greenhouse) | P1 | 2026 Q4 |
| V3.0 | Analytics & Forecasting (Direction 5) + integration release | P1 | 2026 Q4 |

---

## Key Architectural Changes

| Change | Reason |
|--------|--------|
| Long-running agent runtime | Agent workflows persist across sessions; need a robust resume mechanism (SqliteSaver foundation already exists) |
| User preference fine-tuning | Accept/reject signals from the user on Agent suggestions → locally maintained preference vector that weights future recommendations |
| Vector DB upgrade evaluation | ChromaDB slows down at 100k+ candidates; evaluate LanceDB / Qdrant |
| Background worker process isolation | Today's APScheduler shares the FastAPI process; long-running Agents will block it. Evaluate extracting an independent worker |
| Webhook ingress | ATS / Calendar / Mail require receiving webhooks; need to consider a reverse tunnel (ngrok-like) for desktop |
| Quota Enforcement middleware | New `usage_log` / `quota_config` tables + `@enforce_quota` decorator; cross-cuts LLM / email / mutation / sourcing call sites |

---

## Risks and Trade-offs

| Risk | Mitigation |
|------|-----------|
| Autonomous agency vs user sense of control | All destructive operations require HIL; offer a "global pause" switch |
| Chrome extension maintenance cost | LinkedIn DOM changes often → multiple selector fallbacks + auto error reporting + staged version rollout |
| ATS integration explosion | V3 ships only 1 reference implementation (Greenhouse); the rest via community contributions |
| Desktop webhook reachability | Desktop apps have no public IP by default; evaluate Cloudflare Tunnel / local polling as alternatives |
| Privacy compliance (sourcing) | Do not scrape post-login content; first-touch outreach must include data source disclosure |
| Runaway model cost | Quota Enforcement forces daily-token / monthly-USD caps; auto-degrades to Ollama on hit |
| Autonomous agent runaway emails | Outbound email quotas (30/hour / 200/day) + HIL approval — double safeguard |
| Third-party API rate limits | Sourcing API quota rolls daily; on hit, queues to next day without blocking other flows |

---

## Out of Scope for V3 (explicitly drawn line)

- **Mobile App (iOS / Android)** — pushed to V4
- **Marketplace / Plugin store** — defer until community demand is validated
- **New languages** — current 6 languages are sufficient (en / zh / zh-TW / ja / ko / es)
- **Multi-tenant SaaS deployment** — stay local-first; self-hosted mode remains an option
- **Video interview recording** — transcription only, no recording
- **Salary data scraping** — high legal risk; only use public datasets

---

## Design Principles (carried from V1/V2 and reinforced)

1. **Local-first**: default to local inference; cloud APIs are an optional enhancement only
2. **Privacy by default**: candidate PII never leaves the user's device unless explicitly approved
3. **Human-in-the-loop**: more autonomy does not mean loss of control — all destructive actions must be approvable
4. **Graceful degradation**: any external integration (ATS / Calendar / cloud LLM) failing must not break the core flow
5. **Observability first**: every Agent action is traceable, replayable, and debuggable (LangGraph's built-in thread support is the foundation)
