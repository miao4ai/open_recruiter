# openrecruiter-mcp

Open Recruiter's recruiting tools, in any MCP client — Claude Desktop, Claude Code, Cursor,
or anything else that speaks [MCP](https://modelcontextprotocol.io).

Two audiences, from one package. A recruiter asks *"who in my pipeline fits this CUDA
role?"* and their assistant ranks the candidates, reads the scores and explains the gaps. A
consumer app asks on a job seeker's behalf — *"机器学习工程师, 东京"* — and gets job cards
back, then submits a résumé to one of them.

Two transports, too: **stdio** for a client on the same machine, **streamable HTTP** for a
remote caller such as a chat backend. Nothing is uploaded anywhere except to the model
provider you have already configured.

```bash
pip install openrecruiter-mcp
openrecruiter-mcp --help
```

## Wire it into a client

Add one entry to your client's `mcpServers` config. For Claude Desktop that file is
`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS,
`%APPDATA%\Claude\claude_desktop_config.json` on Windows:

```json
{
  "mcpServers": {
    "open-recruiter": {
      "command": "openrecruiter-mcp",
      "args": ["--data-dir", "/absolute/path/to/your/pipeline"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "VOYAGE_API_KEY": "pa-..."
      }
    }
  }
}
```

Nothing to clone and nothing to keep running — the client starts the process when it needs it.

With [uv](https://docs.astral.sh/uv/) you can skip installing altogether:

```json
{
  "command": "uvx",
  "args": ["openrecruiter-mcp", "--data-dir", "/absolute/path/to/your/pipeline"]
}
```

<!-- readme-test: skip -->
```bash
# Not released to PyPI yet? Install the same thing straight from the repository:
uvx --from "git+https://github.com/miao4ai/open_recruiter.git#subdirectory=sdk/mcp" openrecruiter-mcp
```

## Tools

`--tools` picks the audience. They are separate sets because a job seeker's assistant has no
business calling `set_candidate_status`.

### `--tools recruiter` (the default)

Whatever the SDK's `Recruiter` carries, so this list is your `openrecruiter` version's — not a
second list maintained here. Host-registered tools come with it.

| Tool | Model? | What it does |
|---|---|---|
| `list_jobs(limit=20)` | no | open roles, with their ids |
| `get_job(job_id)` | no | one role in full |
| `list_candidates(limit=30)` | no | the pool, with their ids |
| `get_candidate(candidate_id)` | no | one profile in full |
| `rank_candidates(job_id, top_k=10)` | yes | the pool against a role, best fit first |
| `match_candidate(candidate_id, job_id)` | yes | one pairing, in detail |
| `search_candidates(query, top_k=10)` | no | semantic search by free text |

Behind `--write`: `create_job`, `create_candidate`, `set_candidate_status`, `draft_email`.

### `--tools seeker`

The other side of the table, for a consumer chat app. Stateless: a résumé arrives as text and
is embedded for one call, so a single deployment serves many people.

| Tool | Model? | What it does |
|---|---|---|
| `search_jobs(query, location, top_k=10)` | no | job cards by keyword and place — `东京`, `リモート` and `机器学习工程师` all work |
| `recommend_jobs(resume_text, top_k=5)` | no | job cards best-first by vector similarity, `fields.score` 0–1 |
| `match_resume_to_job(resume_text, job_id)` | yes | score, strengths, gaps, reasoning |

Behind `--write`: `apply_to_job(job_id, resume_text, name, email, source, note)` — the seeker
becomes a candidate in that job's pipeline, visible to the recruiter side at once. Ask the
person first.

`search_jobs` and `recommend_jobs` return a **JSON array of cards** —
`{id, title, subtitle, price, detail, url, fields}` with string values in `fields` — as one
text block, which is the shape connectors render. It is byte-for-byte the shape
`product/backend/app/mcp_server.py` already serves, so a caller pointed at either gets the
same answer.

### `--tools all`

Both, for an operator genuinely doing both jobs. A host's own tool keeps its name over a
built-in of the same name.

### The write gate

`--write` (or `OPENRECRUITER_MCP_WRITE=1`) is scoped to the set you published: turning on
`apply_to_job` for a seeker deployment does not also hand out `create_job`. A tool your host
marked `requires_approval` is gated the same way.

`rank_candidates` and `match_candidate` do save the scores they compute, so "read-only" means
read-only about your jobs and candidates, not about the match table.

## Serving a remote caller

stdio is for a client on the same machine. A chat backend calling over the network wants
`--http`, which serves streamable HTTP at `/mcp`: stateless, JSON responses, one JSON-RPC
request per POST, no SSE stream and no session to keep.

```bash
OPENRECRUITER_MCP_TOKEN=... openrecruiter-mcp --tools seeker --write --http --host 0.0.0.0
```

```
POST http://<host>:8765/mcp
Authorization: Bearer <OPENRECRUITER_MCP_TOKEN>
Content-Type: application/json
Accept: application/json, text/event-stream
```

Without `OPENRECRUITER_MCP_TOKEN` there is no authentication at all — every request is
accepted. Binding a routable address without one prints a warning and keeps going, because a
deployment may authenticate at the proxy; if yours does not, set the token.

## Configuration

| Variable | What for |
|---|---|
| `OPENRECRUITER_DATA_DIR` | where `openrecruiter.db` and `chroma_data` live (or pass `--data-dir`) |
| `ANTHROPIC_API_KEY` | the model behind the ranking and matching tools |
| `VOYAGE_API_KEY` | embeddings, which is what makes `search_candidates` work |
| `EMBEDDING_PROVIDER` | a different embedding backend — `cohere`, `gemini`, `ollama`, `local`, … |
| `OPENRECRUITER_MCP_TOOLS` | `recruiter` (default), `seeker` or `all` — same as `--tools` |
| `OPENRECRUITER_MCP_WRITE` | `1` to publish the chosen set's writes — same as `--write` |
| `OPENRECRUITER_MCP_TRANSPORT` | `http` for streamable HTTP — same as `--http` |
| `OPENRECRUITER_MCP_HOST` / `_PORT` | where to bind in HTTP mode (default `127.0.0.1:8765`) |
| `OPENRECRUITER_MCP_TOKEN` | the bearer token HTTP callers must send |

Missing keys are not fatal. The server starts, the tools that need no model keep working, and
retrieval degrades to nothing rather than refusing to load — a half-configured server you can
talk to beats one that will not start.

The data directory is created if it does not exist, so a fresh install begins with an empty
pipeline rather than an error. Point it at an existing one to pick up work already there.

## Your own tools come too

This package is a bridge, not a second list of tools: it reads whatever the `Recruiter`
carries. Register a tool with the SDK and it shows up in your client alongside the built-ins.

```python
from openrecruiter import Recruiter, Tool
from openrecruiter_mcp import build_server

check_inbox = Tool(
    name="check_inbox",
    description="Read replies from candidates.",
    parameters={"type": "object", "properties": {"since": {"type": "string"}}},
    fn=lambda since="": [{"from": "ada@example.com", "subject": "Re: the CUDA role"}],
)

recruiter = Recruiter(anthropic_api_key="sk-ant-...", extra_tools=[check_inbox])
server = build_server(recruiter)        # `check_inbox` is now an MCP tool
```

The MCP SDK builds a tool's schema by inspecting a Python signature, while `openrecruiter`
carries one as JSON, so the bridge synthesises the signature: types and descriptions from the
schema, defaults from the function itself — `top_k: int = 10` lives in the code, not in the
schema, and publishing `null` for it would break the call.

## Related

- [`openrecruiter`](../core/README.md) — the engine this serves: storage, retrieval, ranking, agent
- `product/backend/app/mcp_server.py` — the desktop app's own MCP server, which serves *its*
  database and adds evaluation tools. This package is the one to install if you do not run
  the app.

MIT.
