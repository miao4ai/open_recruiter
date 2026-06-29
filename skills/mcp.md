# MCP Server — recruiter tools for external agents

`backend/app/mcp_server.py` exposes the recruiter's **matching & evaluation**
capabilities as an [MCP](https://modelcontextprotocol.io) server over **stdio**,
so any MCP client (Claude Desktop, Cursor, another chat agent) can call them.

It imports the existing agent/db functions directly and reads the same local
SQLite + ChromaDB. **The FastAPI backend does NOT need to be running.**

## Run

```bash
cd backend && uv run recruiter-mcp      # serves on stdio
```

## Tools

| Tool | LLM? | Returns |
|------|------|---------|
| `list_jobs()` | no | open jobs (id, title, company, location) — get `job_id` |
| `list_candidates(job_id?, status?)` | no | candidates (id, name, title, company, status) — get `candidate_id` |
| `rank_candidates_for_job(job_id, top_k=10)` | no | candidates ranked by vector similarity (fast) |
| `match_candidate_to_job(job_id, candidate_id)` | yes | one pairing: score, strengths, gaps, reasoning |
| `match_candidate_to_jobs(candidate_id)` | yes | one candidate vs ALL jobs: rankings + summary |
| `evaluate_candidate(candidate_id, job_id?)` | yes | 4-agent swarm: per-dimension scores, overall, recommendation, synthesis |

The two `list_*` tools exist so a caller can resolve names → IDs before calling
the matching/evaluation tools. All tools are **read-only** (no writes, no email
sends). LLM-backed tools use the active provider from Settings (`get_config()`).

## Wire into a client

Claude Desktop / Cursor `mcpServers` config:

```json
{
  "mcpServers": {
    "open-recruiter": {
      "command": "uv",
      "args": ["run", "recruiter-mcp"],
      "cwd": "/absolute/path/to/open_recruiter/backend"
    }
  }
}
```

To point at a specific data dir, set `OPEN_RECRUITER_DATA_DIR` in an `env` block.

## Adding a tool

Add a `@mcp.tool()`-decorated function in `mcp_server.py` that delegates to an
existing agent/db function. Keep the docstring tight — MCP clients show it to
the calling model as the tool description. Verify registration:

```bash
cd backend && uv run python -c "import asyncio; from app.mcp_server import mcp; print([t.name for t in asyncio.run(mcp.list_tools())])"
```
