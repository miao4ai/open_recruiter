# Contributing to Open Recruiter

**You do not need machine-learning experience to contribute.** Most of Open Recruiter is a
desktop application — a FastAPI backend, a React UI, and integrations with email, calendar,
and Slack. None of it needs a GPU, and the default install contains no training stack.

Pick the path that matches what you want to work on. Each one tells you exactly what to
install; you never need to set up the layers you are not touching.

---

## Repository layers

```
product  ──→  sdk        the app is a consumer of the SDK
research ──→  sdk        experiments build on the same interfaces
product  ──X  research   production code never imports research code
```

| Layer | What lives there | Needs ML deps? |
|-------|------------------|----------------|
| [`product/`](product/) | Desktop app: Electron shell, React UI, FastAPI backend | No |
| [`sdk/core/`](sdk/core/) | `openrecruiter` — the recruiting engine the app runs on | No |
| [`sdk/fairness/`](sdk/fairness/) | Fairness-aware ranking backend | Some |
| [`sdk/recruitgpt/`](sdk/recruitgpt/) | Distilled ranking model backend | Yes, optional |
| [`research/`](research/) | Experiments, training, evaluation | Yes |
| [`docs/`](docs/) | Manual, release notes, topic guides | No |

That last rule is enforced in CI. You can run the same check locally:

```bash
python .github/scripts/check_architecture.py
```

It fails if anything under `product/` imports a research module, or if a training package
becomes a required dependency of the app or the core SDK.

> **Current status:** `sdk/` and `research/` are scaffolds — package metadata and layout
> only. The engine is being moved into `sdk/core` now; the research tracks are being
> specified. Issues in those areas will say so.

---

## I want to…

### …improve the product

Integrations, outreach, the agent workflow, the API, the UI, bug fixes.

```bash
git clone https://github.com/miao4ai/open_recruiter.git
cd open_recruiter
product/scripts/setup.sh      # Python deps via uv + node deps
product/scripts/start.sh      # FastAPI on :8000, Vite on :5173
```

On Windows use `product/scripts/setup.ps1` and `product/scripts/start.ps1`.

Run the tests before opening a PR:

```bash
cd product/backend && uv run python -m pytest ../tests/ -v
cd product/frontend && npm run build          # tsc + vite
```

You will need an Anthropic or OpenAI key in **Settings** to exercise anything that talks to
a model. A Voyage key enables semantic search; without one, search falls back to keywords.

**Areas:** `area: product` · `area: agent` · `area: integrations` · `area: ui`

### …work on the SDK

The stable interfaces other people build against, and the engine behind the app.

```bash
cd sdk/core
uv build --out-dir dist       # verify it packages
```

Changes here affect the desktop app, so run the product test suite as well. Anything you add
to `openrecruiter`'s required dependencies must work on CPU, on macOS, and without a GPU.

**Areas:** `area: sdk` · `area: search`

### …work on ranking

Candidate retrieval and ranking quality. This is where ML experience helps, but the default
`EmbeddingRanker` is an API call and needs no local model.

The `Ranker` interface in `openrecruiter` is the seam every backend plugs into:

```
Ranker
├── EmbeddingRanker   default — vector similarity, CPU or API, no local model
├── APIRanker         optional — an LLM reranks the shortlist
├── LocalSLMRanker    optional — the distilled model from sdk/recruitgpt
└── your own          implement the interface, pass it in
```

Backends that need a local model must declare their heavy dependencies as optional extras
and **lazy-load the model** — nothing may be downloaded until a user explicitly selects that
backend, and nothing may be loaded at application startup. Users without a GPU, and users on
macOS, must be able to run Open Recruiter normally.

> `LocalSLMRanker` is an interface reservation. No trained model exists yet, so there is no
> implementation to install.

**Areas:** `area: ranker` · `area: search`

### …reproduce or extend research

Distillation, hard-negative mining, evaluation, benchmarks.

```bash
cd research/recruitgpt
uv sync
```

The training stack is not declared yet — this package is still a scaffold, so `uv sync`
currently installs nothing. Research code may depend on whatever it needs. It must never become a dependency of
`product/` or `sdk/core`. Trained weights belong in a model registry, not in this repository:
commit training code, model definitions, configs, evaluation, and reproduction instructions.

**Areas:** `area: research`

### …work on fairness

Bias evaluation, candidate anonymization, counterfactual testing, fairness-aware ranking.

```bash
cd research/fairness
uv sync
```

Also a scaffold today. This track is deliberately independent of the distillation work so the two can move — and
publish — separately. The goal is to **measure and reduce unwanted bias**; do not use
protected characteristics to disadvantage candidates.

**Areas:** `area: fairness`

### …improve documentation

Everything lives in [`docs/`](docs/): [`guides/`](docs/guides/) for humans,
[`skills/`](docs/skills/) for topic-by-topic engineering notes. No setup required.

**Areas:** `area: docs`

---

## Pull requests

- Branch from `main`, keep the change scoped to one layer where you can.
- CI runs only the layers your diff touches, plus the architecture check.
- Match the surrounding style. The project favours small, surgical diffs over rewrites.
- If you change behaviour, add or update a test. If you find a bug, a failing test first is
  the fastest way to get the fix reviewed.
- Never commit `uv.lock` or `product/frontend/tsconfig.tsbuildinfo` — they show as modified
  but should not be staged.

## Labels

Issues are labelled by area and by how much specialist knowledge they need, so it is obvious
at a glance which ones require ML expertise:

```
good first issue      help wanted

area: product         area: agent        area: integrations
area: search          area: sdk          area: ranker
area: research        area: fairness     area: infra
area: ui              area: docs

difficulty: easy      difficulty: medium
difficulty: advanced  difficulty: research
```

`difficulty: easy` and `difficulty: medium` issues never require a GPU or an ML background.

## License

By contributing you agree that your contributions are licensed under the
[MIT License](LICENSE).
