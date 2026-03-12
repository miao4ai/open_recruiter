# <img src="images/small_logo.png" height="36" /> Open Recruiter — Personal Talent Discovery Assistant

---

<p align="center">
  <img src="images/large_logo.png" width="360" />
</p>

<p align="center"><b>AI-Powered Recruitment Platform</b></p>

<p align="center">
  <a href="#readme"><img src="https://img.shields.io/badge/README-blue?style=for-the-badge" /></a>
  <a href="document/USER_MANUAL.md"><img src="https://img.shields.io/badge/USER_MANUAL-green?style=for-the-badge" /></a>
  <a href="document/release.md"><img src="https://img.shields.io/badge/RELEASE_NOTES-orange?style=for-the-badge" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/LICENSE-MIT-purple?style=for-the-badge" /></a>
</p>
<p align="center">
  <img src="https://img.shields.io/badge/BUILD-PASSING-brightgreen" />
  <img src="https://img.shields.io/badge/RELEASE-V2.0.0-blue" />
  <img src="https://img.shields.io/badge/PYTHON-3.11+-yellow" />
  <img src="https://img.shields.io/badge/LICENSE-MIT-purple" />
</p>

---

## Introduction

Open Recruiter is a self-hosted, AI-powered recruitment assistant designed for independent recruiters and small hiring teams. It streamlines the entire talent discovery workflow — from uploading and parsing resumes, to semantically matching candidates against job descriptions, to composing outreach emails with one click. Powered by local vector embeddings and configurable LLMs (Claude / GPT / Gemini / Ollama), it delivers intelligent candidate-job matching without sending your data to third-party platforms. Everything runs locally with zero infrastructure: SQLite for data, ChromaDB for semantic search.

**Job seekers** get their own dedicated mode powered by Ai Chan — an AI assistant that searches for matching jobs on the web, analyzes fit with your resume, suggests resume improvements, and writes personalized cover letters.

---

## Features

### Recruiter Mode

#### Job Management
- Create and manage job postings with full descriptions, skills, location, and salary range
- Upload job descriptions from PDF/DOCX files with auto-extraction via LLM
- Each job card shows how many candidates match (vector similarity ≥ 30%)

#### Candidate Management
- Upload resumes (PDF/DOCX/TXT) with auto-extraction of name, email, skills, experience via LLM
- Duplicate detection by name + email prevents re-uploading existing candidates
- Detailed candidate profile with contact info, skills, linked job, notes, and inline editing

#### AI Match Analysis
- **Vector Matching** — Semantic similarity using ChromaDB + BAAI/bge-small-en-v1.5 local embeddings
- **Deep Analysis** — LLM-powered scoring with strengths, gaps, and reasoning
- **Ranked Candidates** — All candidates sorted by match score for a given job
- Auto-match on upload when a job is linked

#### Email Outreach
- Compose personalized outreach emails using LLM with full candidate/job context
- Draft/approve/send workflow with pending queue
- Per-candidate email history timeline; reply tracking via IMAP

#### Pipeline Kanban
- Visual board: New → Contacted → Replied → Screening → Interview → Offer → Hired
- Drag-and-drop candidate cards between stages

#### Bot Chat (Erika Chan)
- Context-aware AI assistant with access to your jobs, candidates, and email history
- Multi-session conversation history with memory extraction
- Actionable responses: draft emails, upload resumes, match candidates, start workflows
- **Human-in-the-loop approval** — Inline cards for interview scheduling, pipeline cleanup, and bulk outreach
- Multi-step workflow execution with SSE streaming

#### Calendar & Automations
- Schedule interviews, follow-ups, and screening events with weekly calendar view
- Background automation rules: Auto-Match, Inbox Scanner, Auto Follow-Up, Pipeline Cleanup

### Job Seeker Mode (Ai Chan)

- Upload resume → auto-extract profile → immediately search for matching jobs
- Chat-based job search powered by DuckDuckGo + LLM enrichment
- Job match analysis: score, strengths, gaps, reasoning
- **Resume improvement suggestions** — gap-based, prioritized, actionable
- **Cover letter generation** — personalized, under 300 words, one-click copy
- Save jobs to personal list with real-time search
- Encouragement mode toggle for extra motivation

### Platform

- **Multi-LLM support** — Anthropic Claude, OpenAI GPT, Google Gemini, Ollama (local)
- **Semantic search** — Hybrid keyword + vector search with relevance filtering
- **Desktop app** — Electron wrapper for macOS, Windows, Linux
- **Slack integration** — Receive resumes directly from channels
- **i18n** — English, Chinese, Japanese, Korean, Traditional Chinese, Spanish

---

## Quick Install (macOS / Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/miao4ai/open_recruiter/main/install.sh | bash
```

The installer will automatically:
1. Check & install dependencies (Python 3.11+, Node.js 18+, uv, git)
2. Let you choose an LLM provider (Anthropic Claude / OpenAI GPT) and enter your API key
3. Clone the repo, install all packages, and generate your `.env`
4. Offer to launch immediately

> You can also set a custom install directory: `OPEN_RECRUITER_DIR=~/my-dir curl -fsSL ... | bash`

## Desktop App (macOS / Windows)

Download the latest installer from the [Releases](https://github.com/miao4ai/open_recruiter/releases) page:
- **Windows**: `.exe` installer — download and run
- **macOS**: `.dmg` (Apple Silicon) — see install steps below

### macOS Install

macOS blocks unsigned apps downloaded from the internet. Use **either** method:

**Method 1 — Install helper** (recommended):
Download both `macos-install.command` and the `.dmg` from [Releases](https://github.com/miao4ai/open_recruiter/releases). Mount the DMG, then double-click `macos-install.command` — it copies the app to `/Applications`, removes the quarantine flag, and launches.

**Method 2 — Terminal**:
After dragging the app to `/Applications` from the DMG:
```bash
xattr -cr /Applications/Open\ Recruiter.app
open /Applications/Open\ Recruiter.app
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + TypeScript + TailwindCSS 4 + Vite |
| Backend | FastAPI + Uvicorn |
| Database | SQLite (WAL mode) |
| Vector Search | ChromaDB + BAAI/bge-small-en-v1.5 (local, CPU) |
| LLM | Anthropic Claude / OpenAI GPT-4o (configurable) |
| Scheduler | APScheduler 3.x (in-process, threaded) |
| Slack | slack-bolt (async) |
| Auth | JWT + bcrypt |
| Desktop | Electron (optional) |

## Quick Start

**Recommended:** Use the [one-line installer](#quick-install-macos--linux) above.

<details>
<summary>Manual setup</summary>

```bash
# Clone
git clone https://github.com/miao4ai/open_recruiter.git
cd open_recruiter

# Setup (installs backend + frontend dependencies)
./setup.sh        # Linux/macOS
# or
./setup.ps1       # Windows

# Start (launches backend + frontend dev servers)
./start.sh        # Linux/macOS
# or
./start.ps1       # Windows
```

</details>

Then open http://localhost:5173 in your browser.

### First-Time Setup

1. Register an account (choose Recruiter role)
2. Go to **Settings** — configure your LLM provider and API key
3. (Optional) Configure email backend (Gmail/SMTP) for outreach
4. (Optional) Configure IMAP for reply detection
5. Go to **Automations** — review the 4 default rules, adjust conditions/schedule, toggle on

## Using Background Automations

Navigate to the **Automations** page (lightning bolt icon in sidebar).

### Viewing Rules
The page shows all automation rules with:
- Rule name, type badge, and schedule description
- Toggle switch to enable/disable
- Run count and error count
- Last execution time

### Configuring a Rule
Click the **pencil icon** to edit a rule. Each rule has:
- **Trigger Type** — `interval` (e.g. every 30 minutes) or `cron` (e.g. 9:00 AM daily)
- **Schedule** — JSON format: `{"minutes": 30}` for interval, `{"hour": 9, "minute": 0}` for cron
- **Conditions** — Rule-specific filters (JSON). Examples:
  - Auto-Match: `{"min_score_threshold": 0.3, "job_id": ""}` (empty = all jobs)
  - Auto Follow-Up: `{"days_since_contact": 3, "max_followups": 2}`
  - Pipeline Cleanup: `{"days_stale": 7, "target_statuses": ["contacted"]}`
- **Actions** — Rule-specific behavior (JSON). Examples:
  - Auto-Match: `{"update_status": false}` (set true to auto-move high-scoring candidates to screening)
  - Auto Follow-Up: `{"auto_send": false}` (set true to send immediately instead of draft-only)
  - Pipeline Cleanup: `{"dry_run": true, "reject_after_days": 14, "archive_after_days": 21}`

### Running Manually
Click the **play button** on any rule to trigger it immediately, regardless of schedule.

### Monitoring Executions
The **Execution History** table at the bottom shows:
- Timestamp, rule name, status (success/error/running)
- Duration, summary text, and error messages

## Project Structure

```
open_recruiter/
├── backend/                # FastAPI server
│   ├── app/
│   │   ├── routes/         # API endpoints
│   │   │   ├── jobs.py
│   │   │   ├── candidates.py
│   │   │   ├── emails.py
│   │   │   ├── agent.py        # Chat + workflow SSE streaming
│   │   │   ├── automations.py  # Automation rules CRUD + manual trigger
│   │   │   ├── calendar.py
│   │   │   ├── settings.py
│   │   │   └── ...
│   │   ├── agents/         # LLM agents
│   │   │   ├── orchestrator.py # Multi-step workflow engine
│   │   │   ├── matching.py     # Vector + LLM candidate-job matching
│   │   │   ├── communication.py # Email drafting
│   │   │   ├── resume.py       # Resume parsing
│   │   │   └── ...
│   │   ├── tools/          # Utilities
│   │   │   ├── email_sender.py # SMTP/Gmail/Console email sending
│   │   │   ├── imap_checker.py # IMAP reply detection
│   │   │   └── resume_parser.py # PDF/DOCX text extraction
│   │   ├── slack/          # Slack integration
│   │   │   ├── bot.py
│   │   │   ├── handlers.py
│   │   │   ├── pipeline.py     # Resume ingestion pipeline
│   │   │   └── ...
│   │   ├── scheduler.py    # APScheduler background automation engine
│   │   ├── automation_tasks.py # Built-in task implementations
│   │   ├── database.py     # SQLite persistence
│   │   ├── vectorstore.py  # ChromaDB vector search
│   │   ├── models.py       # Pydantic models
│   │   ├── prompts.py      # System prompts
│   │   ├── llm.py          # LLM interface (Anthropic/OpenAI)
│   │   ├── config.py       # Configuration
│   │   ├── auth.py         # JWT authentication
│   │   └── main.py         # FastAPI app entry point
│   └── pyproject.toml
├── frontend/               # React SPA
│   └── src/
│       ├── pages/
│       │   ├── Chat.tsx          # AI assistant with workflow support
│       │   ├── Jobs.tsx
│       │   ├── Candidates.tsx
│       │   ├── CandidateDetail.tsx
│       │   ├── Automations.tsx   # Background automation management
│       │   ├── Calendar.tsx
│       │   ├── Settings.tsx
│       │   └── ...
│       ├── components/     # Sidebar, Header, Kanban, etc.
│       ├── lib/api.ts      # API client
│       └── types/          # TypeScript interfaces
├── electron/               # Desktop wrapper (optional)
├── document/               # Documentation
├── setup.sh / start.sh     # Setup and launch scripts
└── README.md
```

## Configuration

All settings are configurable via the in-app **Settings** page:

| Setting | Description |
|---------|-------------|
| LLM Provider | Anthropic or OpenAI, with model name and API key |
| Email Backend | Console (dev), Gmail, or custom SMTP |
| IMAP | Host, port, username, password for reply detection |
| Recruiter Profile | Name, email, company used in outreach emails |

Environment variables (`.env` file) are loaded on first run, then the database settings take precedence:

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
EMAIL_BACKEND=gmail
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
IMAP_HOST=imap.gmail.com
IMAP_PASSWORD=xxxx xxxx xxxx xxxx
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
```

## Architecture

```
Browser (React + TailwindCSS)
    │
    ▼ REST API + SSE Streaming
FastAPI Backend
    ├── SQLite ────── Structured data (jobs, candidates, emails, users, automation rules/logs)
    ├── ChromaDB ──── Vector embeddings (semantic search)
    ├── APScheduler ─ Background automation (auto-match, inbox scan, follow-up, cleanup)
    ├── LLM API ───── Resume parsing, match analysis, email drafting, chat (Anthropic / OpenAI)
    └── IMAP/SMTP ─── Email sending and reply detection
```

## Releases

| Version | Date | Highlights |
|---------|------|------------|
| [V2.0.0](https://github.com/miao4ai/open_recruiter/releases/tag/v2.0.0) | 2026-03-12 | LangGraph migration, human-in-the-loop approvals, resume improvement & cover letter, Ollama support, real-time search |
| [V1.5.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.5.0) | 2026-03-01 | Desktop app (Electron): auto-update, system tray, auto-restart, backup/restore |
| [V1.4.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.4.0) | 2026-02-23 | macOS DMG build, cross-platform CI/CD |
| [V1.3.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.3.0) | 2026-02-22 | Encouragement mode for Ai Chan, favorite jobs from search results, chat tone fix |
| [V1.2.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.2.0) | 2026-02-21 | Per-job pipeline status, Candidate/Jobs toggle, emoji picker |
| [V1.1.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.1.0) | 2026-02-20 | i18n (6 languages), ONNX Runtime migration, CI/CD, calendar overhaul |
| [V1.0.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.0.0) | 2026-02-20 | Initial release |

For detailed release notes, see [document/release.md](document/release.md).

## License

MIT
