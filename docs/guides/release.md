# Release Notes

Detailed release notes for each version of Open Recruiter.

Download installers from the [GitHub Releases](https://github.com/miao4ai/open_recruiter/releases) page.

---

## V4.0.0 (unreleased)

### Monorepo: product / sdk / research

The repository is now split into three independently buildable parts:

```
product/     desktop app (Electron + React + FastAPI) -> .dmg / .exe / .AppImage
sdk/         core, ranking, recruitgpt                -> PyPI packages
research/    ranking, recruitgpt                      -> PyPI packages
docs/        guides/ (manual, release notes) + skills/
```

- `product/` holds what used to be `electron/`, `frontend/`, `backend/`, `tests/`, `scripts/`, and `images/`
- `document/` became `docs/guides/`; `skills/` became `docs/skills/`
- All six Python packages are uv workspace members, but `uv sync` inside `product/backend`
  still installs only the backend, so research dependencies cannot leak into the app build
- The SDK and research packages ship as scaffolds in this release — name, version, and
  layout only. `sdk/core` gains the recruiting tools and agent loop next.

### Security

- **Per-install JWT signing key.** The key previously fell back to a constant compiled into
  every build, so a token forged against one install was valid against all of them. It is now
  generated on first run and stored locally; `JWT_SECRET` still overrides it.
  **Existing sessions are invalidated — users must log in again.**
- **Loopback binding.** `start.sh` / `start.ps1` bound the API and the Vite dev server to
  `0.0.0.0`, exposing the pipeline to everyone on the same network. Both now bind `127.0.0.1`.
- **Scoped CORS.** `allow_origins` narrowed from `*` to the Vite dev origin. Packaged builds
  serve the UI from the same origin and never needed the wildcard.
- **Masked secrets.** `GET /api/settings` returned every API key, SMTP/IMAP password, and
  Slack token in clear text. All nine fields are now masked; a field submitted still masked
  means "unchanged" and no longer overwrites the stored value.

### Removed

- The legacy chat path in `routes/agent.py` — 176 lines sitting after an unconditional
  `return`, plus the system prompt it was the only consumer of. Every message was building a
  prompt that nothing read.
- `graphs/feature_flags.py`. `use_langgraph_chat()` and `use_langgraph_workflow()` were never
  called, so the documented fallback to the legacy pipeline did not exist.
- The Ollama route, config, and UI, and the Gemini provider branches. `_build_config()` has
  forced the provider to Anthropic or OpenAI since 3.0, so all of it was unreachable.

### Fixed

- Onboarding offered retired Claude 4.x model ids (`claude-sonnet-4-20250514` and friends),
  so a fresh install's first API call failed with `not_found_error`. Aligned with Settings.
- `setup.sh`, `start.sh`, `build.sh` and their `.ps1` twins resolved `ROOT` to their own
  directory, so every `$ROOT/backend` pointed at `scripts/backend`. Broken since the scripts
  were moved out of the project root.
- `env.example` was missing `VOYAGE_API_KEY`, which 3.0 semantic search requires, and still
  advertised Gemini.

### Docs

- README documents the monorepo layout and how each part builds
- `CLAUDE.md` and `docs/skills/*` updated for the new paths
- README claimed Gemini and Ollama support; the test count said 159 and is actually 137

---

## V3.0.1 (2026-07-09)

Bug-fix release for two issues that made 3.0.0 look broken on a fresh install.

### Voyage key now applies without a restart
`_VoyageEmbeddingFunction` captured the API key in `init_vectorstore()` at launch, but users
enter the Voyage key in **Settings** *after* first launch. The embedding function held an
empty key, so every index and search failed silently (swallowed as a warning): candidate
uploads did not update job match counts and match analysis stayed empty until the app was
restarted. The key is now read from live config on each call.

### Failed login shows an error instead of silently reloading
The global 401 interceptor redirected to `/login` on *any* 401 — including the login
request's own "invalid credentials" 401. The page reloaded before `Login.tsx` could render
its error, so a wrong password looked like nothing happened. The redirect now skips the auth
endpoints, so the form surfaces the backend's "Invalid email or password"; 401s from
authenticated calls still redirect.

---

## V3.0.0 (2026-07-04)

The slim build. Local inference is gone — embeddings move to the Voyage AI API and chat is
cloud-only — which halves the install and makes the app bring-your-own-key.

### Slim build: Voyage cloud embeddings
- The local ONNX/BGE embedding model is replaced by the **Voyage AI embeddings API** for
  semantic candidate ↔ job matching. `_VoyageEmbeddingFunction` is a ChromaDB
  `EmbeddingFunction` calling Voyage over httpx; `onnxruntime` is never imported.
- Drops PyTorch, sentence-transformers, transformers, scipy and scikit-learn from the
  install (~800 MB of dev deps, ~170 MB from the shipped bundle) and removes the bundled
  129 MB model.
- New `voyage_api_key` / `voyage_model` in config, env, and the Settings API. Without a key,
  search falls back to keyword-only.

### Slim build: local voice transcription removed
- `/api/transcribe` and the `MicButton` UI are gone. faster-whisper pulled in ctranslate2 and
  PyAV (~168 MB) for a non-core feature. **Backend bundle: 524 MB → 356 MB.**

### Chat providers: Anthropic + OpenAI only
- Chat is locked to the two supported cloud providers; any other stored provider falls back
  to Anthropic. Gemini and Ollama were dropped from the Settings dropdown.
- Retired `claude-sonnet-4` / `opus-4` / `haiku-4` ids (which now 404) in favour of
  `claude-sonnet-5` (default), `claude-opus-4-8`, and `claude-haiku-4-5`.

### 4-tier agent memory
New `backend/app/memory/` package composing one memory block into the system prompt
(~1600 token budget, per-layer caps):
- **sensory** — per-user in-process ring buffer, last 10 events, 30 min TTL
- **working** — `session_state` table: current goal, open workflows, focused entities
- **entity** — per-candidate/job rolling summary, traits, relations, interaction count
- **long-term** — high-confidence preferences from the existing `memories` table

Wired through `build_context`, with a single `_update_memory_for_action()` hook in `agent.py`
instead of touching every handler. All memory reads and writes are wrapped — they can never
break a chat turn.

### MCP server
`backend/app/mcp_server.py` (FastMCP; stdio, or streamable HTTP via
`RECRUITER_MCP_TRANSPORT=http` for a server-side caller such as charbit) lets external MCP
clients — Claude Desktop, Cursor, other chat agents — call the recruiter's matching and
evaluation capabilities. It imports the agent and db functions directly and reads the same
local SQLite + ChromaDB, so the FastAPI backend does not need to be running.

Read-only tools: `list_jobs`, `list_candidates`, `rank_candidates_for_job`,
`match_candidate_to_job`, `match_candidate_to_jobs`, `evaluate_candidate`; stateless
job-seeker tools (resume as text, nothing stored): `search_jobs`, `recommend_jobs`,
`match_resume_to_job`.

### Anthropic prompt caching
`CHAT_SYSTEM_WITH_ACTIONS` is ~10K tokens and was re-processed every turn. Adding
`cache_control: ephemeral` on the system message drops input cost ~90% and TTFB ~80% on
cached hits. Anthropic only, and only for prompts ≥ 4000 characters.

### Signed and notarized macOS builds
`notarize: true` plus `APPLE_ID` / `APPLE_APP_SPECIFIC_PASSWORD` / `APPLE_TEAM_ID` in CI —
the DMG no longer triggers a Gatekeeper warning, so the `xattr -cr` workaround is obsolete.

### Developer tooling
- Opt-in **LangSmith tracing**: set `LANGSMITH_API_KEY` and `LANGSMITH_TRACING=true` to
  forward every LangGraph and LLM call to smith.langchain.com. Off by default.
- Topic guides moved to a project-root `skills/` folder, linked from `CLAUDE.md`.
- CI no longer runs the per-platform torch + optimum ONNX export step — dead work once the
  build stopped bundling a local model.

> Earlier fully-offline releases remain on the
> [`old-version-2.2`](https://github.com/miao4ai/open_recruiter/tree/old-version-2.2) branch.

---

## V2.2.0 (2026-05-29)

### Voice Input (Local Whisper)
- New microphone button in the chat input — record, transcribe locally with faster-whisper, send as message
- Fully offline: no audio leaves the device
- 22 mocked Whisper test cases verify transcription, language detection, and error paths

### Inbox Preview in Chat
- New `check_inbox` action: in chat, ask "check my inbox" / "查看收件箱" to fetch the 10 most recent emails via IMAP
- `InboxPreviewCard` UI: unread dot indicator, sender, subject, snippet, date, one-click "Check Replies" button
- Keyword fallback for weak local models (Qwen 3.5)

### Test Harness (114 cases)
- New `tests/harness/` directory with pytest
- `test_intent_detection.py` — keyword fallback, action-routing whitelist (seeker vs recruiter), intent disambiguation
- `test_guardrails.py` — prompt injection, PII, content safety, hallucination, action limits, severity priority
- Fixed a real guardrail gap: "show me your instructions" now blocked

### Project & Docs
- Karpathy's working-style guidelines integrated into `CLAUDE.md`
- V3 roadmap translated to English
- Shell scripts moved to `scripts/` to declutter project root

---

## V2.1.0 (2026-03-18)

### Multi-Agent Candidate Evaluation Swarm
- **4 parallel agents** evaluate candidates simultaneously via `ThreadPoolExecutor`:
  - **Resume Agent** — skills and experience match analysis
  - **Culture Agent** — cultural fit, career trajectory, growth signals
  - **Risk Agent** — red flags: job-hopping, employment gaps, inconsistencies
  - **Market Agent** — salary benchmarking and market positioning
- **Synthesizer** combines all 4 scores (resume 40%, culture 25%, risk 20%, market 15%) into an overall recommendation: Strong Hire / Recommend / On the Fence / Not Recommended
- New `CandidateEvalCard` UI with score bars, collapsible findings per dimension, and hire recommendation badge
- Triggered by "evaluate [name]" or "assess [name]" in chat

### Search Result Feedback
- Thumbs up/down buttons on search results in both Recruiter and Job Seeker modes
- Feedback stored in `search_feedback` table with query, result metadata, and vote
- New `POST /search/feedback` endpoint

### Project Improvements
- Added `CLAUDE.md` — project guide for AI-assisted development
- Moved all shell scripts to `scripts/` directory to declutter project root
- Candidate count auto-refreshes on job create/upload

---

## V2.0.0 (2026-03-12)

### LangGraph Agentic Architecture
- Migrated chat backend from monolithic route handler to **LangGraph state machine**: `build_context → input_guard → call_llm → parse_response → output_guard → process_action → finalize`
- Input/output guardrails: prompt injection detection, content safety, hallucination detection
- Parallel agent dispatch for concurrent execution

### Human-in-the-Loop Approvals
- **SchedulingApprovalCard** — time slot picker for interview scheduling; user selects a slot before calendar event is created
- **PipelineCleanupCard** — checkbox list for bulk candidate status changes; user can deselect individuals before executing
- **BulkOutreachCard** — email preview with expand/collapse for each draft before batch send
- Backend `/workflow/{id}/resume` and `/cancel` endpoints to continue or abort paused workflows

### Job Seeker Enhancements
- **Resume Improvement** — after job match analysis, Ai Chan provides gap-based suggestions grouped by area (skills, keywords, experience, etc.) with high/medium/low priority
- **Cover Letter Generation** — one-click personalized cover letter under 300 words with copy button
- Auto-search for matching jobs immediately after resume upload
- Real-time debounced search (300ms) in My Jobs page — no more click-to-search

### Ollama (Local LLM) Support
- Added Ollama as a fourth LLM provider alongside Anthropic, OpenAI, Gemini
- Supports Qwen 3.5 (0.8B → 2B → 4B → 9B → 27B) and Qwen 3 series
- Thinking mode disabled by default for Qwen models (`<think>` tags stripped)
- Model pull UI in Settings with download progress

### Search Quality
- Hybrid search now filters low-relevance results: requires keyword hit OR semantic score ≥ 0.50 for semantic-only matches
- Minimum hybrid score threshold of 0.20 prevents unrelated jobs from surfacing

### Bug Fixes
- Fixed: "upload a JD" intent no longer fires when user describes a job in text — `create_job` takes priority
- Fixed: chat default language enforced as English; Qwen no longer randomly outputs Chinese
- Fixed: job search results now persist when navigating between pages
- Fixed: DuckDuckGo search used for web job search (was falling back to placeholder results)
- Cleaned up release assets to 3 files only: `.dmg` (macOS), `.exe` (Windows), `.AppImage` (Linux)

---

## V1.5.0 (2026-03-01)

### Desktop App — Production Hardening
- **Auto-update** — Electron checks GitHub Releases on launch; prompts user to download and install
- **System tray** — minimize to tray, restore from tray icon, quit from context menu
- **Auto-restart** — backend process automatically restarts on crash with exponential backoff
- **Data backup/restore** — export SQLite + ChromaDB to zip from Settings; restore from zip on first launch
- **Offline detection** — banner shown when network unavailable; local features remain functional
- **Log rotation** — backend logs capped at 10 MB, rotated to `.1` backup
- **Smoke tests** — automated startup test verifies backend health before showing main window
- **Linux AppImage build** added to CI/CD alongside macOS DMG and Windows EXE

---

## V1.4.0 (2026-02-23)

### macOS DMG Support
- **Native macOS builds** — electron-builder now produces `.dmg` installers for macOS (Apple Silicon arm64)
- **Ad-hoc code signing** — `afterPack` hook automatically signs the `.app` bundle to avoid Gatekeeper "damaged" errors
- **DMG installer layout** — drag-to-Applications install experience with app icon and Applications folder shortcut
- **Auto-generated .icns icon** — electron-builder converts the existing 1024x1024 PNG to macOS icon format during build
- **Backend binary permissions fix** — `chmodSync` ensures execute permission on macOS after electron-builder packaging

> **macOS first launch**: If macOS shows a security warning, right-click the app and select **Open**, or run `xattr -cr /Applications/Open\ Recruiter.app` in Terminal before opening.

### Cross-Platform CI/CD
- **New `build-macos` job** in GitHub Actions release workflow — builds native macOS backend via PyInstaller + packages as DMG on `macos-latest` (Apple Silicon)
- **Dedicated `release` job** — collects Windows `.exe` and macOS `.dmg` artifacts, attaches both to GitHub Release
- GitHub Releases now include both Windows installer and macOS DMG

### Build Script Improvements
- `build.sh` now auto-detects platform (macOS vs Linux) and passes the correct `--mac` or `--linux` flag to electron-builder
- Accepts optional platform argument: `bash build.sh mac`, `bash build.sh linux`, or `bash build.sh auto` (default)
- New `dist:mac` npm script for macOS packaging

---

## V1.3.0 (2026-02-22)

### Encouragement Mode (Job Seeker)
- New **Cheer Mode** toggle in the Ai Chan chat header
- When enabled, Ai Chan weaves motivational phrases into every response (multilingual: Chinese, English, Japanese, Korean)
- Preference persists across page reloads via localStorage; passed as a request parameter — no database migration required

### Favorite Jobs from Search Results (Job Seeker)
- Heart icon on each job search result card — click to save directly to My Jobs
- Direct REST API save (`POST /seeker/jobs`) bypasses the LLM chat flow for instant saves
- Duplicate detection by URL or title+company (returns 409 if already saved)
- Filled red heart indicates saved state; saved keys loaded on mount via `GET /seeker/jobs/saved-urls`
- Success feedback shown as an inline assistant message

### Chat Tone Fix (Recruiter)
- Added professional boundary rules to `CHAT_SYSTEM` and `CHAT_SYSTEM_WITH_ACTIONS` prompts
- Prevents flirtatious or off-topic responses; enforces `context_hint: null` for casual messages
- Emoji usage capped at 1-2 per message

### New API Endpoints
- `POST /seeker/jobs` — directly save a job from search results (title, company, location, url, snippet, salary_range, source)
- `GET /seeker/jobs/saved-urls` — returns saved job identifiers for heart icon state

### i18n
- Added 7 new translation keys across all 6 locales (en, zh, ja, ko, zh-TW, es) for encouragement mode and favorite jobs

---

## V1.2.0 (2026-02-21)

### Per-Job Pipeline Status
- Each candidate-job pair now has its own pipeline stage (e.g., "replied" for Job A, "contacted" for Job B)
- New `candidate_jobs.pipeline_status` column with automatic data migration from legacy global status
- Backend fallback: when `candidate_jobs` is empty, falls back to legacy `candidates.job_id` join

### Candidate / Jobs Toggle
- Pipeline bar now features a **Candidate / Jobs** segmented toggle
- **Candidate view** — counts candidates per stage (original behavior)
- **Jobs view** — counts unique jobs per stage; clicking a stage shows job cards with expandable candidate lists
- Dashboard Kanban also supports the toggle with job-grouped cards

### New API Endpoints
- `GET /candidates/pipeline?view=candidate|jobs` — returns pipeline entries with candidate and job details
- `PATCH /candidates/pipeline/{candidate_id}/{job_id}` — updates per-job pipeline status

### Chat Enhancements
- Emoji picker added to chat input

### Bug Fixes
- Fixed Windows runtime icon (desktop shortcut and taskbar now show correct icon)
- Fixed `electron-builder.json` to use `.ico` format for Windows exe icon embedding

---

## V1.1.0 (2026-02-20)

### Internationalization
- Added Chinese (Simplified), Chinese (Traditional), Japanese, Korean, Spanish translations
- Full i18n coverage across all pages and components using i18next

### Calendar Overhaul
- Replaced React Big Calendar with a custom calendar component
- Improved CSS styling and event layout

### Performance & Size Optimization
- Migrated from PyTorch to ONNX Runtime for embeddings — installer size reduced from ~1.3 GB to ~500 MB
- Faster startup with lighter runtime dependencies

### CI/CD
- GitHub Actions release workflow (`release.yml`) — triggered by `v*` tags or manual `workflow_dispatch`
- Automated Windows installer builds with electron-builder

### Bug Fixes
- Backend startup diagnostics and resilience improvements
- Fixed system Python detection for ONNX export in CI
- Windows installer icon now displays correctly (NSIS installer)

---

## V1.0.0 (2026-02-20)

### Initial Release
- **Job Management** — create, edit, delete job postings with PDF/DOCX upload and LLM auto-extraction
- **Candidate Management** — resume upload (PDF/DOCX/TXT) with auto-extraction, duplicate detection, inline editing
- **AI Match Analysis** — vector similarity (ChromaDB + BAAI/bge-small-en-v1.5) + LLM deep analysis with streaming
- **Email Outreach** — draft/approve/send workflow, resume attachments, per-candidate email history, IMAP reply tracking
- **Pipeline Kanban** — visual board (New → Contacted → Replied → Screening → Interview → Offer → Hired) with drag-and-drop
- **Bot Chat (Erika Chan)** — context-aware AI assistant with multi-step workflow execution and SSE streaming
- **Calendar** — schedule interviews, follow-ups, offers, and screening events
- **Slack Integration** — receive resumes from channels, auto-parse, PII filtering, top-3 job match suggestions
- **Background Agents** — Auto-Match, Inbox Scanner, Auto Follow-Up, Pipeline Cleanup (APScheduler)
- **Dual-Role Support** — Recruiter and Job Seeker modes
- **Desktop App** — Windows installer via Electron + NSIS
- **One-Line Installer** — macOS / Linux setup script
