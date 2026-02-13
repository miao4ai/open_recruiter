# <img src="images/small_logo.png" height="36" /> Open Recruiter — Personal Talent Discovery Assistant

---

<p align="center">
  <img src="images/large_logo.png" width="360" />
</p>

<p align="center"><b>AI-Powered Recruitment Platform</b></p>

<p align="center">
  <img src="https://img.shields.io/badge/BUILD-PASSING-brightgreen" />
  <img src="https://img.shields.io/badge/RELEASE-V2026.2.13-blue" />
  <img src="https://img.shields.io/badge/PYTHON-3.11+-yellow" />
  <img src="https://img.shields.io/badge/LICENSE-MIT-purple" />
</p>

---

## Features

- **Job Management** — Create and manage job postings with full descriptions
- **Resume Parsing** — Upload resumes (PDF/DOCX/TXT), auto-extract structured data via LLM
- **Vector Matching** — Semantic similarity matching between candidates and jobs using ChromaDB + BGE embeddings
- **AI Match Analysis** — One-click LLM-powered deep analysis with score, strengths, gaps, and typewriter effect
- **Email Outreach** — Compose and send emails to companies with candidate resume attachments
- **Duplicate Detection** — Prevents re-uploading candidates with the same name and email
- **Pipeline Kanban** — Visual candidate pipeline tracking across hiring stages
- **Bot Chat** — Conversational AI assistant with full context of your jobs, candidates, and emails
- **Dashboard** — Stats overview, pipeline board, and real-time activity feed

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + TypeScript + TailwindCSS + Vite |
| Backend | FastAPI + SQLite + ChromaDB |
| Embeddings | BAAI/bge-small-en-v1.5 (local) |
| LLM | Anthropic Claude / OpenAI (configurable) |
| Desktop | Electron (optional) |

## Quick Start

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/open_recruiter.git
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

Then open http://localhost:5173 in your browser.

## Project Structure

```
open_recruiter/
├── backend/            # FastAPI server
│   ├── app/
│   │   ├── routes/     # API endpoints (jobs, candidates, emails, agent, settings)
│   │   ├── agents/     # LLM agents (resume parsing, matching, planning, chat)
│   │   ├── tools/      # Email sender, resume parser
│   │   ├── database.py # SQLite persistence
│   │   ├── vectorstore.py # ChromaDB vector search
│   │   ├── models.py   # Pydantic models
│   │   └── prompts.py  # System prompts
│   └── pyproject.toml
├── frontend/           # React SPA
│   └── src/
│       ├── pages/      # Dashboard, Jobs, Candidates, CandidateDetail, Chat, Outreach, Settings
│       ├── components/ # Sidebar, Layout
│       ├── lib/api.ts  # API client
│       └── types/      # TypeScript interfaces
├── electron/           # Desktop wrapper (optional)
├── setup.sh / start.sh # Setup and launch scripts
└── README.md
```

## Configuration

All settings are configurable via the in-app Settings page:

- **LLM Provider** — Anthropic or OpenAI, with model and API key
- **SMTP** — Email sending configuration (host, port, credentials)

## License

MIT
