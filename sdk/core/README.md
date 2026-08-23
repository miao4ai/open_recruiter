# openrecruiter

The recruiting engine behind [Open Recruiter](https://github.com/miao4ai/open_recruiter):
parse resumes and job descriptions, retrieve and rank candidates, draft outreach, and run an
agent that does all of it through tools.

The desktop app is a consumer of this package, so everything shipped here is exercised by a
real application rather than only by its own tests.

## Install

```bash
pip install openrecruiter
```

Or straight from the repository, for an unreleased change:

```bash
pip install "git+https://github.com/miao4ai/open_recruiter.git#subdirectory=sdk/core"
```

Wheels are also attached to each [Release](https://github.com/miao4ai/open_recruiter/releases).
They are not in the repository's Packages panel because GitHub Packages has no Python
registry.

No local model is downloaded, at import or at runtime. Embeddings are an API call and chat is
a hosted provider, so it runs on CPU, on macOS, and in a container with no GPU — 97 packages
installed, none of them a training stack.

## Quick start

```python
from openrecruiter import Recruiter

r = Recruiter(anthropic_api_key="sk-ant-...", voyage_api_key="pa-...")

job = r.add_job(open("jd.txt").read())          # parsed into title, skills, requirements
r.add_candidate(open("resume.txt").read())      # parsed into a structured profile

for match in r.rank(job.id, top_k=10):
    print(f"{match.score:.2f}  {match.candidate_id}  {match.reasoning}")
```

Without a Voyage key, retrieval is disabled and ranking falls back to the LLM — the package
still works, it just reads every candidate instead of shortlisting first.

Everything is a constructor argument with a working default:

```python
r = Recruiter(
    config,
    store=my_store,           # anything satisfying the Store protocol
    index=my_index,           # anything satisfying VectorIndex
    ranker=my_ranker,         # anything with rank(job, candidates, top_k)
    extra_tools=[my_tool],    # joined to the built-in tools
    data_dir="./data",        # where the default SQLite file and index live
)
```

---

## A full pass

Ingest a role and a pool, rank it, and write to the top of the list.

```python
from openrecruiter import Recruiter

r = Recruiter(anthropic_api_key="sk-ant-...")

job = r.add_job("""
    Senior CUDA Engineer, Acme.
    You will scale distributed training across thousands of GPUs.
    Must have: CUDA, NCCL, PyTorch Distributed.
""")

for path in ("ada.txt", "grace.txt", "alan.txt"):
    r.add_candidate(open(path).read())

for match in r.rank(job.id, top_k=3):
    candidate = r.store.get_candidate(match.candidate_id)
    print(f"{match.score:.0%}  {candidate.name} — {candidate.current_title}")
    for strength in match.strengths:
        print(f"      + {strength}")
    for gap in match.gaps:
        print(f"      - {gap}")

    draft = r.draft_email(match.candidate_id, job_id=job.id)
    print(f"      → {draft.subject}")
```

`rank` persists what it finds, so the scores are readable later without paying for them again:

```python
for match in r.store.list_matches(job.id):
    print(match.candidate_id, match.score, match.ranker)
```

Free-text search does not need a job at all:

```python
for candidate, score in r.search_candidates("has actually shipped NCCL at scale"):
    print(f"{score:.2f}  {candidate.name}")
```

---

## The agent

The model is given the tools and decides what to call, in what order, and when it is done —
so one request can span several steps.

```python
for event in r.chat("who are the three strongest fits for the CUDA role?"):
    print(event)
```

For anything user-facing you want the events individually. Text arrives as it is generated;
a tool call is only emitted once its arguments are complete:

```python
from openrecruiter import TextDelta, ToolCall, ToolResult, ApprovalRequired, Finished

for event in r.chat("rank the CUDA role, then draft an intro to the top candidate"):
    if isinstance(event, TextDelta):
        print(event.text, end="", flush=True)
    elif isinstance(event, ToolCall):
        print(f"\n  [{event.name} {event.arguments}]")
    elif isinstance(event, ToolResult):
        if not event.ok:
            print(f"\n  [{event.name} failed: {event.error}]")
    elif isinstance(event, Finished):
        print(f"\n({event.stop_reason}, {event.steps} steps)")
```

A conversation is a list of messages you keep and pass back:

```python
history = []
reply = r.ask("how many candidates do I have?", history=history)
history += [
    {"role": "user", "content": "how many candidates do I have?"},
    {"role": "assistant", "content": reply},
]
reply = r.ask("which of them know CUDA?", history=history)
```

`ask` returns only the final text. Use it in scripts and tests; use `chat` when something is
watching.

### Approval gates

A tool marked `requires_approval` stops the run instead of acting, and **holds every call the
model queued behind it** — otherwise the gate is cosmetic.

```python
from openrecruiter import Tool

send = Tool(
    name="send_email",
    description="Send an email to a candidate",
    parameters={"type": "object", "properties": {"to": {"type": "string"}},
                "required": ["to"]},
    fn=lambda to: mail.send(to),
    requires_approval=True,
)

r = Recruiter(config, extra_tools=[send])
agent = r.agent()

for event in agent.run("email the top candidate"):
    if isinstance(event, ApprovalRequired):
        print(f"{event.name}({event.arguments}) — {event.description}")

if agent.pending:
    approved = input("send it? [y/N] ").lower() == "y"
    for event in agent.resume(agent.pending, approved=approved):
        ...
```

`resume` consumes the pending state, so hold onto it if you need it twice.

Usually the answer arrives somewhere else entirely — a later HTTP request, a different
process. `PendingApproval` is a pydantic model for exactly that: park it, and resume with an
agent that never saw the original turn.

```python
agent = r.agent()
for event in agent.run("email the second candidate too"):
    pass

parked = agent.pending.model_dump_json()      # into a queue, a row, a file
```

```python
from openrecruiter import PendingApproval

agent = r.agent()                             # a fresh one, in another process
for event in agent.resume(PendingApproval.model_validate_json(parked), approved=True):
    print(event)
```

Declining is not an error: the model is told the user refused and gets to respond, which is
usually more useful than an abandoned turn.

### Your own tools

A tool is a function plus a JSON schema. The description is read by the model, so say *when*
to reach for it, not just what it does.

```python
from openrecruiter import Tool

check_calendar = Tool(
    name="check_calendar",
    description=(
        "The recruiter's free slots this week. Use this before proposing interview "
        "times, rather than asking the user when they are free."
    ),
    parameters={
        "type": "object",
        "properties": {"days": {"type": "integer", "description": "How far ahead to look"}},
        "required": [],
    },
    fn=lambda days=7: calendar.free_slots(days),
)

r = Recruiter(config, extra_tools=[check_calendar])
```

Unexpected arguments are dropped rather than raising — models invent a plausible extra one
often enough that losing the turn to it is worse. Missing *required* arguments still raise,
because those change what the call means.

To narrow what a particular caller can reach, build a registry from the subset:

```python
from openrecruiter import ToolRegistry

read_only = ToolRegistry([t for t in r.tools if t.name.startswith(("list_", "get_", "search_"))])
agent = r.agent()
agent.tools = read_only
```

---

## Ranking

Ranking is the main extension point. One method, several backends:

```
Ranker
├── EmbeddingRanker   vector similarity — the default, cheap enough for the whole pool
├── APIRanker         an LLM scores each candidate and explains itself
├── TwoStageRanker    retrieve with one, rerank the shortlist with the other
└── your own          implement rank(job, candidates, top_k) and pass it in
```

`TwoStageRanker` is the shape the ranking research targets — the first stage optimises recall
over everyone, the second optimises relevance over a few hundred:

```python
from openrecruiter import APIRanker, EmbeddingRanker, TwoStageRanker

r.ranker = TwoStageRanker(
    EmbeddingRanker(r.index),
    APIRanker(r.llm),
    shortlist=200,
)
```

The retrieval score is kept alongside the rerank score, because comparing the two is how you
tell whether the reranker is earning its cost:

```python
for match in r.rank(job.id):
    print(match.score, match.ranker)   # 0.87  two_stage(embedding->api) retrieval=0.62
```

A ranker for one call only, without changing the default:

```python
matches = r.rank(job.id, ranker=EmbeddingRanker(r.index))
```

### Writing one

Anything with a `name` and a `rank` method qualifies — there is no base class to inherit.

```python
from openrecruiter import Match

class SeniorityRanker:
    """Rerank by how well years of experience match what the job asked for."""

    name = "seniority"

    def rank(self, job, candidates, top_k=20):
        wanted = job.experience_years or 0
        scored = []
        for c in candidates:
            gap = abs((c.experience_years or 0) - wanted)
            scored.append(Match(
                candidate_id=c.id,
                job_id=job.id,
                score=round(max(0.0, 1.0 - gap / 10), 4),
                reasoning=f"{c.experience_years} years against {wanted} asked for",
                ranker=self.name,
            ))
        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:top_k]

r.ranker = TwoStageRanker(EmbeddingRanker(r.index), SeniorityRanker())
```

Return `Match` objects sorted best-first and no longer than `top_k`. Returning fewer is
normal; raising is not — a ranker that cannot answer should return an empty list so the
caller can fall back.

Backends that need a local model live in their own distributions — `recruitgpt` for the
distilled ranker, `openrecruiter-fairness` for bias-aware reranking — so nothing heavy reaches
this install. Both must lazy-load: no download until a user selects that backend.

---

## Bringing your own storage

`Store` and `VectorIndex` are protocols, not base classes. Implement them over a database you
already have and nothing above the storage layer changes — that is how the Open Recruiter
desktop app runs on this package while keeping its own schema.

```python
from openrecruiter import Candidate, Job, Match, Store

class MyStore:
    def add_job(self, job: Job) -> Job: ...
    def get_job(self, job_id: str) -> Job | None: ...
    def list_jobs(self, limit: int = 100) -> list[Job]: ...

    def add_candidate(self, candidate: Candidate) -> Candidate: ...
    def get_candidate(self, candidate_id: str) -> Candidate | None: ...
    def list_candidates(self, limit: int = 100) -> list[Candidate]: ...
    def set_candidate_status(self, candidate_id: str, status) -> bool: ...

    def save_match(self, match: Match) -> None: ...
    def list_matches(self, job_id: str) -> list[Match]: ...

assert isinstance(MyStore(), Store)      # runtime-checkable

r = Recruiter(config, store=MyStore())
```

The default `SQLiteStore` is a working reference in four tables:

```python
from openrecruiter import SQLiteStore

r = Recruiter(config, store=SQLiteStore("./hiring.db"))
```

`NullVectorIndex` is what you get with no embedding key: indexing is a no-op and searches
return nothing. Implementations should degrade that way rather than raising — retrieval
falling back to keyword search is a usable product, a crash is not.

---

## Context without a context window problem

The obvious way to brief an agent is to paste the pipeline into the system prompt. That stops
working around the first few hundred candidates.

`pipeline_context` builds a bounded briefing instead — the open jobs, the pipeline
distribution, and the handful of candidates actually related to the question, retrieved
through the index:

```python
print(r.pipeline_context("who has done distributed training?"))
```

```
## Open jobs (1)
- [a1b2c3d4] Senior CUDA Engineer at Acme — needs CUDA, NCCL, PyTorch Distributed

## Pipeline (312 candidates)
- new: 280
- contacted: 24
- interviewing: 8

## Candidates related to this message (8)
Use search_candidates or get_candidate for anyone not listed here.
- [e5f6a7b8] Ada Lovelace — ML Systems Engineer at Acme | new | CUDA, NCCL
...
```

It does not grow with the database, and it tells the model its real size and how to reach
everyone else — so "someone not in the context" becomes a `search_candidates` call rather
than "I have no data on them".

---

## Development

```bash
cd sdk/core
uv sync
uv run pytest              # no network calls: the LLM is faked end to end
uv build --out-dir dist
```

Releasing: bump `version` in `pyproject.toml`, then push a matching tag.

```bash
git tag sdk-core-v0.1.1 && git push origin sdk-core-v0.1.1
```

CI checks the tag against the version, runs the tests, builds, installs the wheel in a clean
environment and imports it, verifies no training stack came along, and attaches the artifacts
to a Release.

## License

MIT
