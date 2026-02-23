# Release Notes

Detailed release notes for each version of Open Recruiter.

Download installers from the [GitHub Releases](https://github.com/miao4ai/open_recruiter/releases) page.

---

## V1.4.0 (2026-02-23)

### macOS DMG Support
- **Native macOS builds** — electron-builder now produces `.dmg` installers for macOS (Apple Silicon arm64)
- **macOS entitlements** — hardened runtime with entitlements for Electron JIT, network access, and PyInstaller compatibility
- **DMG installer layout** — drag-to-Applications install experience with app icon and Applications folder shortcut
- **Auto-generated .icns icon** — electron-builder converts the existing 1024x1024 PNG to macOS icon format during build
- **Backend binary permissions fix** — `chmodSync` ensures execute permission on macOS after electron-builder packaging

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
