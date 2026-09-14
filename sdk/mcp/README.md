# openrecruiter-mcp

Open Recruiter's recruiting tools, in any MCP client — Claude Desktop, Claude Code, Cursor,
or anything else that speaks [MCP](https://modelcontextprotocol.io).

Ask your assistant *"who in my pipeline fits this CUDA role?"* and it ranks your candidates,
reads the scores, and explains the gaps — against a pipeline on your own machine. Nothing is
uploaded anywhere except to the model provider you have already configured.

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

Every tool the SDK's `Recruiter` carries is published, so this list is whatever your
`openrecruiter` version has — not a second list maintained here.

| Tool | Model? | What it does |
|---|---|---|
| `list_jobs(limit=20)` | no | open roles, with their ids |
| `get_job(job_id)` | no | one role in full |
| `list_candidates(limit=30)` | no | the pool, with their ids |
| `get_candidate(candidate_id)` | no | one profile in full |
| `rank_candidates(job_id, top_k=10)` | yes | the pool against a role, best fit first, with strengths and gaps |
| `match_candidate(candidate_id, job_id)` | yes | one pairing, in detail |
| `search_candidates(query, top_k=10)` | no | semantic search by free text |

Withheld unless you pass `--write` (or set `OPENRECRUITER_MCP_WRITE=1`):

| Tool | What it changes |
|---|---|
| `create_job(raw_text)` | parses a JD and stores it |
| `create_candidate(raw_text)` | parses a résumé and stores it |
| `set_candidate_status(candidate_id, status)` | moves someone through the pipeline |
| `draft_email(candidate_id, job_id, ...)` | writes outreach — a draft, never sent |

The default is read-only because wiring a recruiting pipeline into a chat client is usually
about *asking* it things. `rank_candidates` and `match_candidate` do save the scores they
compute, so "read-only" means read-only about your jobs and candidates, not about the match
table.

## Configuration

| Variable | What for |
|---|---|
| `OPENRECRUITER_DATA_DIR` | where `openrecruiter.db` and `chroma_data` live (or pass `--data-dir`) |
| `ANTHROPIC_API_KEY` | the model behind the ranking and matching tools |
| `VOYAGE_API_KEY` | embeddings, which is what makes `search_candidates` work |
| `EMBEDDING_PROVIDER` | a different embedding backend — `cohere`, `gemini`, `ollama`, `local`, … |

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
