# <img src="images/small_logo.png" height="36" /> Open Recruiter

<p align="center">
  <img src="images/large_logo.png" width="320" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/BUILD-PASSING-brightgreen" />
  <img src="https://img.shields.io/badge/RELEASE-V2.1.0-blue" />
  <img src="https://img.shields.io/badge/LICENSE-MIT-purple" />
</p>

<p align="center">
  <a href="document/USER_MANUAL.md"><img src="https://img.shields.io/badge/USER_MANUAL-green?style=for-the-badge" /></a>
  <a href="document/release.md"><img src="https://img.shields.io/badge/RELEASE_NOTES-orange?style=for-the-badge" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/LICENSE-MIT-purple?style=for-the-badge" /></a>
</p>

---

**AI-powered recruitment assistant for independent recruiters and small teams. Runs 100% locally — no cloud, no subscription.**

---

## The Problem

Small and mid-size recruiting teams often work across industries they don't have deep expertise in. When you're filling a role in, say, compiler engineering or ML infrastructure, it's hard to quickly judge whether a candidate's resume actually fits — and even harder to write a credible outreach email that speaks to their background.

Open Recruiter solves this. Drop in a job description and a stack of resumes. The AI reads them, scores the fit, explains the gaps, and drafts a personalized email for each candidate — ready to send in one click. You don't need to understand the tech stack. The AI does the reading so you can focus on relationships.

**For job seekers**, there's a dedicated mode (Ai Chan) that searches for matching jobs on the web, analyzes your fit, and writes your cover letter.

---

## Demo

> 🎬 *Coming soon*

---

## Key Features

| | Recruiter | Job Seeker |
|--|-----------|------------|
| **Parse** | Upload resumes & JDs (PDF/DOCX/TXT) → auto-extract structured data | Upload resume → instant profile |
| **Match** | Vector + LLM scoring: strengths, gaps, reasoning per candidate | Job match analysis against any listing |
| **Outreach** | One-click personalized email per candidate, bulk campaigns | Cover letter generation |
| **Pipeline** | Kanban board, reply tracking, interview scheduling | Save jobs, track applications |
| **AI Chat** | Erika Chan — ask anything about your pipeline, get actions | Ai Chan — job search, resume tips |
| **Automation** | Auto-match, inbox scan, follow-up, pipeline cleanup | — |

**Runs on:** Anthropic Claude · OpenAI GPT · Google Gemini · Ollama (fully local, offline)

**Desktop app** for macOS, Windows, Linux — or run as a local web server.

---

## Install

**Desktop app** (recommended) — download from [Releases](https://github.com/miao4ai/open_recruiter/releases):
- **macOS** (Apple Silicon): `.dmg` → drag to Applications → run `xattr -cr /Applications/Open\ Recruiter.app` if blocked
- **Windows**: `.exe` installer
- **Linux**: `.AppImage`

**One-line installer** (macOS / Linux):
```bash
curl -fsSL https://raw.githubusercontent.com/miao4ai/open_recruiter/main/scripts/install.sh | bash
```

**Manual setup:**
```bash
git clone https://github.com/miao4ai/open_recruiter.git && cd open_recruiter
scripts/setup.sh && scripts/start.sh   # then open http://localhost:5173
```

---

## Releases

| Version | Date | Highlights |
|---------|------|------------|
| [V2.1.0](https://github.com/miao4ai/open_recruiter/releases/tag/v2.1.0) | 2026-03-13 | Search feedback (👍👎), candidate count auto-refresh on job create |
| [V2.0.0](https://github.com/miao4ai/open_recruiter/releases/tag/v2.0.0) | 2026-03-12 | LangGraph agents, human-in-the-loop approvals, resume improvement, cover letter, Ollama |
| [V1.5.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.5.0) | 2026-03-01 | Desktop app: auto-update, system tray, backup/restore |
| [V1.4.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.4.0) | 2026-02-23 | macOS DMG, cross-platform CI/CD |
| [V1.3.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.3.0) | 2026-02-22 | Encouragement mode, favorite jobs from search |
| [V1.2.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.2.0) | 2026-02-21 | Per-job pipeline, Kanban view toggle, emoji picker |
| [V1.1.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.1.0) | 2026-02-20 | i18n (6 languages), ONNX migration, calendar |
| [V1.0.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.0.0) | 2026-02-20 | Initial release |

Full changelog: [document/release.md](document/release.md)

---

## License

MIT
