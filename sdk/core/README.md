# openrecruiter

The recruiting engine behind [Open Recruiter](https://github.com/miao4ai/open_recruiter):
parse resumes and job descriptions, retrieve and rank candidates, draft outreach, and run an
agent that does all of it through tools.

The desktop app is a consumer of this package, so everything shipped here is exercised by a
real application rather than only by its own tests.

```bash
pip install openrecruiter
```

No local model is downloaded, at import or at runtime. Embeddings are an API call and chat is
a hosted provider, so it runs on CPU, on macOS, and in a container with no GPU.

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

## The agent

The model is given real tools and decides what to call and when it is done, so one request
can span several steps: rank a job, read the result, then draft the emails.

```python
for event in r.chat("who are the three strongest fits for the CUDA role, and draft an intro to each"):
    match event:
        case TextDelta():        print(event.text, end="", flush=True)
        case ToolCall():         print(f"\n[{event.name}]")
        case ApprovalRequired(): ...   # a gated tool is waiting for a human
```

Events are `TextDelta`, `ToolCall`, `ToolResult`, `ApprovalRequired`, and `Finished`. Text
streams as it is generated; tool calls are only emitted once their arguments are complete.

For a one-liner, `r.ask("...")` returns just the final text.

### Approval gates

A tool marked `requires_approval` stops the run rather than acting. Anything the model
queued behind it is held too, so the gate cannot be stepped around:

```python
events = list(r.chat("email the top candidate"))
if agent.pending:                                   # serialisable — store it, decide later
    list(agent.resume(agent.pending, approved=True))
```

### Your own tools

```python
from openrecruiter import Tool

check_calendar = Tool(
    name="check_calendar",
    description="Look at the recruiter's availability this week",
    parameters={"type": "object", "properties": {"days": {"type": "integer"}}},
    fn=lambda days=7: my_calendar.free_slots(days),
)

r = Recruiter(anthropic_api_key="...", extra_tools=[check_calendar])
```

## Ranking

Ranking is the main extension point. One interface, several backends:

```
Ranker
├── EmbeddingRanker   vector similarity — the default, cheap enough for the whole pool
├── APIRanker         an LLM scores each candidate and explains itself
├── TwoStageRanker    retrieve with one, rerank the shortlist with the other
└── your own          implement rank(job, candidates, top_k) and pass it in
```

`TwoStageRanker` is the shape the ranking research targets — the first stage optimises
recall, the second optimises relevance over a few hundred candidates:

```python
from openrecruiter import APIRanker, EmbeddingRanker, TwoStageRanker

r.ranker = TwoStageRanker(
    EmbeddingRanker(r.index),
    APIRanker(r.llm),
    shortlist=200,
)
```

Backends that need a local model live in their own distributions — `recruitgpt` for the
distilled ranker, `openrecruiter-fairness` for bias-aware reranking — so nothing heavy
reaches this install. Both must lazy-load: no download until a user selects that backend.

## Bringing your own storage

`Store` and `VectorIndex` are protocols. Implement them over a database you already have and
nothing above the storage layer changes — that is how the desktop app keeps its existing
schema while running on this package.

```python
class MyStore:
    def add_job(self, job): ...
    def get_job(self, job_id): ...
    def list_jobs(self, limit=100): ...
    # ... six more, all in openrecruiter.store.base

r = Recruiter(config, store=MyStore())
```

The default `SQLiteStore` is a working reference in four tables.

## Development

```bash
cd sdk/core
uv sync
uv run pytest              # no network calls: the LLM is faked end to end
uv build --out-dir dist
```

## License

MIT
