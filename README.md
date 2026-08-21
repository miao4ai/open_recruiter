# <img src="product/images/small_logo.png" height="36" /> Open Recruiter

<p align="center">
  <img src="product/images/large_logo.png" width="320" />
</p>

<p align="center">
  <a href="https://github.com/miao4ai/open_recruiter/actions/workflows/test.yml"><img src="https://github.com/miao4ai/open_recruiter/actions/workflows/test.yml/badge.svg" /></a>
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

[Quick Start](#quick-start) · [Documentation](docs/guides/USER_MANUAL.md) · [Architecture](#architecture) · [SDK](sdk/core/) · [Research](#open-recruiter-research) · [Contributing](CONTRIBUTING.md)

- **AI recruiting agent** — ask about your pipeline in plain language, get actions, not just answers
- **Semantic candidate search** — vector retrieval over resumes and job descriptions
- **Candidate matching** — fit scores with explained strengths and gaps
- **Automated outreach** — personalised emails, reply tracking, follow-ups
- **Integrations** — email, IMAP, calendar, Slack, and an MCP server for external agents
- **Extensible SDK** — swap in your own ranking backend
- **Open research platform** — ranking and fairness experiments live in the same repository

---

## Quick Start

Download the desktop app from [Releases](https://github.com/miao4ai/open_recruiter/releases)
— `.dmg` (macOS, signed and notarized), `.exe` (Windows), or `.AppImage` (Linux) — then add
an Anthropic or OpenAI key in **Settings**. That is the whole setup.

To run from source:

```bash
git clone https://github.com/miao4ai/open_recruiter.git && cd open_recruiter
product/scripts/setup.sh && product/scripts/start.sh   # then open http://localhost:5173
```

No GPU, no PyTorch, no local model download. See [Install](#install) for details.

---

## The Problem

Small and mid-size recruiting teams often work across industries they don't have deep expertise in. When you're filling a role in, say, compiler engineering or ML infrastructure, it's hard to quickly judge whether a candidate's resume actually fits — and even harder to write a credible outreach email that speaks to their background.

Open Recruiter solves this. Drop in a job description and a stack of resumes. The AI reads them, scores the fit, explains the gaps, and drafts a personalized email for each candidate — ready to send in one click. You don't need to understand the tech stack. The AI does the reading so you can focus on relationships.

**For job seekers**, there's a dedicated mode (Ai Chan) that searches for matching jobs on the web, analyzes your fit, and writes your cover letter.

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

## Architecture

Open Recruiter is one repository with three layers and a single rule about how they depend
on each other:

```
product  ──→  sdk        the desktop app is a consumer of the SDK
research ──→  sdk        experiments build on the same interfaces
product  ──X  research   production code never imports research code
```

That last line is what keeps the app installable. The desktop build has no PyTorch, no
Transformers, and no training dependencies; embeddings are an API call. Research may grow as
heavy as it needs to behind that boundary. The rule is
[enforced in CI](.github/scripts/check_architecture.py), not just documented.

Each part builds and ships on its own.

| Path | What it is | Produces |
|------|-----------|----------|
| [`product/`](product/) | The desktop app — Electron + React + FastAPI | `.dmg` · `.exe` · `.AppImage` |
| [`sdk/core/`](sdk/core/) | `openrecruiter` — the agent toolkit the app runs on | PyPI package |
| [`sdk/fairness/`](sdk/fairness/) | `openrecruiter-fairness` — fairness-aware ranking | PyPI package |
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

## SDK & Extensibility

The engine behind the app is being published as `openrecruiter`, so the same parsing,
matching, and outreach logic can be imported into your own tools rather than reimplemented.

Ranking is the main extension point. One interface, several backends:

```
Ranker
├── EmbeddingRanker   default — vector similarity, no local model, no GPU
├── APIRanker         optional — an LLM reranks the shortlist
├── LocalSLMRanker    optional — a distilled ranking model, lazy-loaded
└── your own          implement rank(job, candidates) and pass it in
```

Every optional backend keeps its heavy dependencies behind extras and loads its model only
when a user explicitly selects it. Installing `openrecruiter` never downloads a model.

> **Status:** `sdk/core` is being populated now — package layout and interfaces first, the
> engine moving over from `product/backend` next. `LocalSLMRanker` is an interface
> reservation; no trained model exists yet.

---

## Open Recruiter Research

Open Recruiter is also an experimental platform for research in AI-native recruiting
systems. Everything below is **early and experimental** — the repository currently contains
the structure and the boundaries, not results. No benchmarks or trained models have been
published yet.

The research layer never affects a normal install.

### Recruiter Ranking

Evolving candidate search from single-stage embedding similarity into two stages, where
retrieval optimises recall and ranking optimises job-candidate relevance:

```
Job Description
      │
      ▼
Semantic Retrieval        ← optimises recall
      │
      ▼
Top 100–500 Candidates
      │
      ▼
Recruiter Ranker          ← optimises relevance
      │
      ▼
Top Candidates ──→ Recruiter Agent ──→ explain · outreach · follow-up
```

The planned training path uses a large model offline as a recruiter judge, then distils it
into something small enough to serve:

```
Large LLM Recruiter Judge  ──→  Soft Labels  ──→  Compact Ranker
        (offline)                                  (production)
```

Topics: semantic candidate retrieval · hard-negative mining · LLM-as-a-judge soft labels ·
knowledge distillation · compact SLM ranking · multi-objective ranking (skill, domain,
experience, seniority fit) · resume compression and cached candidate representations ·
efficient inference.

→ [`research/recruitgpt/`](research/recruitgpt/) · [`sdk/recruitgpt/`](sdk/recruitgpt/)

### Fair Candidate Search

A deliberately independent track asking whether demographic signals affect candidate
ranking, whether anonymization changes results, and what the relevance/fairness trade-off
actually costs. The goal is to **measure and reduce unwanted bias** — never to use protected
characteristics to disadvantage candidates.

Topics: bias evaluation · candidate anonymization · counterfactual testing ·
fairness-aware ranking · relevance/fairness trade-offs.

→ [`research/fairness/`](research/fairness/) · [`sdk/fairness/`](sdk/fairness/)

---

## Contributing

**You do not need ML experience to contribute.** Most of Open Recruiter is an ordinary
desktop application, and the default development setup installs no training stack.

| I want to work on… | Where | ML needed |
|--------------------|-------|-----------|
| Integrations, outreach, agent workflow, API, UI | [`product/`](product/) | No |
| Public interfaces and the recruiting engine | [`sdk/core/`](sdk/core/) | No |
| Candidate retrieval and ranking quality | [`sdk/`](sdk/) | Some |
| Distillation, hard negatives, benchmarks | [`research/recruitgpt/`](research/recruitgpt/) | Yes |
| Bias evaluation and fairness | [`research/fairness/`](research/fairness/) | Yes |
| Documentation | [`docs/`](docs/) | No |

Each path has its own setup instructions in **[CONTRIBUTING.md](CONTRIBUTING.md)** — you
never need to install the layers you are not touching. Issues are labelled by area and
difficulty, so it is obvious at a glance which ones require an ML background.

If Open Recruiter is useful to you, a ⭐ helps other recruiters and researchers find it.

---

## What's New in 4.0

**Split into a monorepo.** The desktop app moved to [`product/`](product/), joined by
[`sdk/`](sdk/) for the Python packages and [`research/`](research/) for the experiments
behind them. Every part builds and versions on its own — see [Architecture](#architecture).

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
