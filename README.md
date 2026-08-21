# <img src="product/images/small_logo.png" height="36" /> Open Recruiter

<p align="center">
  <img src="product/images/large_logo.png" width="320" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/BUILD-PASSING-brightgreen" />
  <img src="https://img.shields.io/badge/RELEASE-V4.0.0-blue" />
  <img src="https://img.shields.io/badge/LICENSE-MIT-purple" />
</p>

<p align="center">
  <a href="docs/guides/USER_MANUAL.md"><img src="https://img.shields.io/badge/USER_MANUAL-green?style=for-the-badge" /></a>
  <a href="docs/guides/release.md"><img src="https://img.shields.io/badge/RELEASE_NOTES-orange?style=for-the-badge" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/LICENSE-MIT-purple?style=for-the-badge" /></a>
</p>

---

**AI-powered recruitment assistant for independent recruiters and small teams.**

A lightweight desktop app powered by Claude, with cloud embeddings for semantic matching — bring your own API keys, no subscription. As of **4.0** the recruiting engine underneath it is also shipped as a Python SDK, so the same parsing, matching, and outreach logic can be imported into your own tools.

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
| **Match** | Vector + LLM scoring, **multi-agent swarm evaluation** (skills, culture, risk, market) | Job match analysis against any listing |
| **Outreach** | One-click personalized email per candidate, bulk campaigns | Cover letter generation |
| **Pipeline** | Kanban board, reply tracking, interview scheduling | Save jobs, track applications |
| **AI Chat** | Erika Chan — ask anything about your pipeline, get actions | Ai Chan — job search, resume tips |
| **Automation** | Auto-match, inbox scan, follow-up, pipeline cleanup | — |

**Runs on:** Anthropic Claude (default) · OpenAI GPT — bring your own API key

**Desktop app** for macOS, Windows, Linux — or run as a local web server.

---

## Install

**Desktop app** (recommended) — download from [Releases](https://github.com/miao4ai/open_recruiter/releases):
- **macOS** (Apple Silicon): `.dmg` → drag to Applications → open (signed & notarized — no Gatekeeper warning)
- **Windows**: `.exe` installer
- **Linux**: `.AppImage`

**One-line installer** (macOS / Linux):
```bash
curl -fsSL https://raw.githubusercontent.com/miao4ai/open_recruiter/main/product/scripts/install.sh | bash
```

**Manual setup:**
```bash
git clone https://github.com/miao4ai/open_recruiter.git && cd open_recruiter
product/scripts/setup.sh && product/scripts/start.sh   # then open http://localhost:5173
```

### API keys (3.0+)

Starting with **3.0**, Open Recruiter is a lightweight cloud-backed build — no local models are bundled, so you provide your own keys in **Settings**:

- **Chat** — an **Anthropic** API key (Claude, the default) or an **OpenAI** key. Get one at [console.anthropic.com](https://console.anthropic.com).
- **Semantic search** — a **Voyage AI** key for candidate ↔ job matching. Free to start (200M tokens) at [dashboard.voyageai.com](https://dashboard.voyageai.com); leave it blank to fall back to keyword search.

> Earlier fully-offline releases remain on the [`old-version-2.2`](https://github.com/miao4ai/open_recruiter/tree/old-version-2.2) branch.

---

## Repository Layout

This is a monorepo. Each part builds and ships on its own.

| Path | What it is | Produces |
|------|-----------|----------|
| [`product/`](product/) | The desktop app — Electron + React + FastAPI | `.dmg` · `.exe` · `.AppImage` |
| [`sdk/core/`](sdk/core/) | `openrecruiter` — the agent toolkit the app runs on | PyPI package |
| [`sdk/ranking/`](sdk/ranking/) | `openrecruiter-ranking` — unbiased candidate ranking | PyPI package |
| [`sdk/recruitgpt/`](sdk/recruitgpt/) | `recruitgpt` — recruiting-domain model training | PyPI package |
| [`research/`](research/) | Reproducible experiments behind the SDKs | PyPI packages |
| [`docs/`](docs/) | Manual, release notes, roadmaps, contributor guides | — |

The SDKs are not a side product: the desktop app is a consumer of `openrecruiter`,
so everything shipped in the package is exercised by the app itself.

```bash
# desktop app
cd product && npm run dist

# any Python package
cd sdk/core && uv build --out-dir dist
```

---

## What's New in 4.0

**Split into a monorepo.** The desktop app moved to [`product/`](product/), joined by
[`sdk/`](sdk/) for the Python packages and [`research/`](research/) for the experiments
behind them. Every part builds and versions on its own — see [Repository Layout](#repository-layout).

**Security.** The JWT signing key is now generated per install instead of falling back to a
shared constant that shipped in every build, dev servers bind to loopback rather than every
interface, CORS is scoped to the dev origin, and API keys are masked in the settings API.
Existing sessions need to log in again after upgrading.

**Slimmer.** Removed the unreachable legacy chat path, the unused LangGraph feature flags,
and the last Ollama and Gemini remnants left over from the 3.0 slim build.

**Fixed.** Onboarding offered retired Claude 4.x model ids, so a fresh install's first API
call failed. The `setup` / `start` / `build` scripts resolved their own directory as the
project root and had been broken since they were moved out of it.

Next up: native tool use and a real agent loop in `sdk/core`, plus unbiased candidate
ranking and RecruitGPT. Full notes in [docs/guides/release.md](docs/guides/release.md).

---

## Releases

| Version | Date | Highlights |
|---------|------|------------|
| **V4.0.0** | *unreleased* | Monorepo split (product / sdk / research), per-install JWT key, loopback binding, scoped CORS, masked API keys, dead-code removal |
| [V3.0.1](https://github.com/miao4ai/open_recruiter/releases/tag/v3.0.1) | 2026-07-09 | Fixes: Voyage key now applies without restart (candidate matching / analysis); failed login shows an error instead of silently reloading |
| [V3.0.0](https://github.com/miao4ai/open_recruiter/releases/tag/v3.0.0) | 2026-07-04 | Slim build (~50% smaller install): Voyage cloud embeddings, Claude/OpenAI chat, current Claude models, signed + notarized macOS DMG; dropped local PyTorch/Whisper |
| [V2.2.0](https://github.com/miao4ai/open_recruiter/releases/tag/v2.2.0) | 2026-05-29 | Voice input (Whisper), inbox preview in chat, 114-case test harness |
| [V2.1.0](https://github.com/miao4ai/open_recruiter/releases/tag/v2.1.0) | 2026-03-18 | Multi-agent candidate evaluation swarm, search feedback, CLAUDE.md |
| [V2.0.0](https://github.com/miao4ai/open_recruiter/releases/tag/v2.0.0) | 2026-03-12 | LangGraph agents, human-in-the-loop approvals, resume improvement, cover letter, Ollama |
| [V1.5.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.5.0) | 2026-03-01 | Desktop app: auto-update, system tray, backup/restore |
| [V1.4.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.4.0) | 2026-02-23 | macOS DMG, cross-platform CI/CD |
| [V1.3.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.3.0) | 2026-02-22 | Encouragement mode, favorite jobs from search |
| [V1.2.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.2.0) | 2026-02-21 | Per-job pipeline, Kanban view toggle, emoji picker |
| [V1.1.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.1.0) | 2026-02-20 | i18n (6 languages), ONNX migration, calendar |
| [V1.0.0](https://github.com/miao4ai/open_recruiter/releases/tag/v1.0.0) | 2026-02-20 | Initial release |

Full changelog: [docs/guides/release.md](docs/guides/release.md)

---

## License

MIT
