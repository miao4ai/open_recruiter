# Open Recruiter 🤖

An autonomous AI agent for recruitment workflow automation. Think **Claude Code, but built specifically for recruiting**.

Open Recruiter helps recruiters automate candidate outreach, resume screening, interview coordination, and communication between candidates and hiring managers.

## ✨ Features

- **Smart Candidate Outreach** — Generate personalized outreach emails based on JD + candidate profile
- **Resume Analysis** — Match resumes against job descriptions, suggest improvements
- **Automated Follow-ups** — Track email responses, auto-send follow-ups for non-replies
- **Interview Coordination** — Schedule interviews between candidates and hiring managers
- **Pipeline Tracking** — Track every candidate's status through the hiring funnel
- **Multi-Agent Architecture** — Specialized agents for planning, communication, resume analysis, and coordination

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Open Recruiter CLI                 │
│              (Interactive Terminal UI)               │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│               Orchestrator Agent                     │
│         (Task Planning & Coordination)               │
└──┬──────────┬──────────┬──────────┬─────────────────┘
   │          │          │          │
   ▼          ▼          ▼          ▼
┌──────┐ ┌──────────┐ ┌──────┐ ┌──────────┐
│Resume│ │Communi-  │ │Match │ │Scheduling│
│Agent │ │cation    │ │Agent │ │Agent     │
│      │ │Agent     │ │      │ │          │
└──┬───┘ └────┬─────┘ └──┬───┘ └────┬─────┘
   │          │          │          │
   ▼          ▼          ▼          ▼
┌─────────────────────────────────────────────────────┐
│                    Tools Layer                        │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │Email API│ │Calendar  │ │Resume    │ │Database│  │
│  │(Gmail/  │ │(Google   │ │Parser    │ │(SQLite)│  │
│  │SendGrid)│ │Calendar) │ │          │ │        │  │
│  └─────────┘ └──────────┘ └──────────┘ └────────┘  │
└─────────────────────────────────────────────────────┘
```

## 📦 Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- API Keys:
  - **OpenAI** or **Anthropic** (for LLM)
  - **Gmail API** or **SendGrid** (for email)
  - **Google Calendar API** (optional, for scheduling)

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/open_recruiter.git
cd open_recruiter

# Install dependencies
uv sync

# Set up environment variables
cp env.example .env
# Edit .env and add your API keys

# Run Open Recruiter
uv run open-recruiter
```

## 💬 Example Usage

```
🤖 Open Recruiter > What would you like to do?

You: I need to find a Senior Frontend Engineer. Here's the JD: [paste JD]

🤖 Planning...
  ✅ Task 1: Analyze job description and extract key requirements
  ✅ Task 2: Review uploaded candidate resumes for match
  ✅ Task 3: Rank candidates by fit score
  ✅ Task 4: Draft personalized outreach emails for top 5 candidates
  ⏳ Task 5: Awaiting your approval to send emails...

You: Looks good, send emails to the top 3.

🤖 Sending...
  ✅ Email sent to alice@example.com
  ✅ Email sent to bob@example.com
  ✅ Email sent to charlie@example.com
  📅 Follow-up reminders set for 3 days from now.
```

## 📁 Project Structure

```
open_recruiter/
├── src/
│   └── open_recruiter/
│       ├── __init__.py
│       ├── cli.py              # CLI entry point (interactive mode)
│       ├── orchestrator.py     # Main agent orchestration
│       ├── config.py           # Configuration & settings
│       ├── database.py         # SQLite persistence layer
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── planning.py     # Planning Agent - task decomposition
│       │   ├── resume.py       # Resume Agent - parse & analyze resumes
│       │   ├── communication.py# Communication Agent - draft emails
│       │   ├── matching.py     # Matching Agent - JD-candidate matching
│       │   └── scheduling.py   # Scheduling Agent - interview coordination
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── email.py        # Email sending (Gmail/SendGrid)
│       │   ├── calendar.py     # Calendar integration
│       │   ├── resume_parser.py# Resume file parsing (PDF/DOCX)
│       │   └── database.py     # DB read/write tools for agents
│       ├── templates/
│       │   ├── outreach.py     # Outreach email templates
│       │   ├── followup.py     # Follow-up email templates
│       │   └── rejection.py    # Rejection email templates
│       ├── utils/
│       │   ├── __init__.py
│       │   └── logger.py       # Logging utilities
│       └── prompts.py          # System prompts for all agents
├── tests/
│   ├── __init__.py
│   ├── test_orchestrator.py
│   ├── test_agents.py
│   └── test_tools.py
├── docs/
│   └── architecture.md
├── pyproject.toml
├── env.example
├── .gitignore
└── README.md
```

## 🤝 Contributing

Contributions welcome! Please keep PRs small and focused.

## 📄 License

MIT License
