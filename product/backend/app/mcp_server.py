"""MCP server — exposes Open Recruiter's matching & evaluation capabilities.

Runs as a standalone stdio process so any MCP client (Claude Desktop, Cursor,
another chat agent, …) can call the recruiter's matching and evaluation tools.
It imports the existing agent/db functions directly and operates on the same
local SQLite + ChromaDB data — the FastAPI backend does NOT need to be running.

Run it with::

    uv run recruiter-mcp

See ``skills/mcp.md`` for client wiring.
"""

import logging

# The MCP Python SDK renamed FastMCP to MCPServer in 2.0. The three APIs we use
# — construction, @tool(), and run() over stdio — are identical across both, so
# support whichever is installed rather than pinning to an old major.
try:
    from mcp.server.mcpserver import MCPServer as _Server  # mcp >= 2.0
except ImportError:  # pragma: no cover - depends on the installed SDK
    from mcp.server.fastmcp import FastMCP as _Server  # mcp 1.x

from app import database as db

log = logging.getLogger(__name__)

mcp = _Server("open-recruiter")


def _cfg():
    """Active runtime config (LLM provider, keys). Imported lazily so the
    module loads even before init_db()."""
    from app.routes.settings import get_config
    return get_config()


# ── Lookup helpers (read-only) ──────────────────────────────────────────────
# Matching/evaluation tools need job_id / candidate_id; these let a caller
# resolve names → IDs first.


@mcp.tool()
def list_jobs() -> list[dict]:
    """List all open jobs. Returns id, title, company, location for each —
    use the id as ``job_id`` in the matching/evaluation tools."""
    return [
        {
            "id": j["id"],
            "title": j.get("title", ""),
            "company": j.get("company", ""),
            "location": j.get("location", ""),
        }
        for j in (db.list_jobs() or [])
    ]


@mcp.tool()
def list_candidates(job_id: str = "", status: str = "") -> list[dict]:
    """List candidates, optionally filtered by ``job_id`` or pipeline
    ``status``. Returns id, name, current_title, current_company — use the id
    as ``candidate_id`` in the matching/evaluation tools."""
    rows = db.list_candidates(job_id=job_id or None, status=status or None) or []
    return [
        {
            "id": c["id"],
            "name": c.get("name", ""),
            "current_title": c.get("current_title", ""),
            "current_company": c.get("current_company", ""),
            "status": c.get("status", ""),
        }
        for c in rows
    ]


# ── Matching & evaluation ───────────────────────────────────────────────────


@mcp.tool()
def rank_candidates_for_job(job_id: str, top_k: int = 10) -> list[dict]:
    """Rank candidates for a job by semantic similarity (vector search, no LLM —
    fast). Returns candidates sorted best-first with a 0–1 ``score``."""
    from app.sdk_bridge import build_recruiter

    recruiter = build_recruiter(_cfg())
    job = recruiter.store.get_job(job_id)
    if job is None:
        return []

    out = []
    for cid, score in recruiter.index.search_candidates(job, top_k=top_k):
        cand = recruiter.store.get_candidate(cid)
        if cand is None:
            continue
        out.append({
            "candidate_id": cid,
            "name": cand.name or "Unknown",
            "current_title": cand.current_title,
            "current_company": cand.current_company,
            "experience_years": cand.experience_years,
            "skills": cand.skills[:8],
            "score": round(score, 4),
        })
    return out


@mcp.tool()
def match_candidate_to_job(job_id: str, candidate_id: str) -> dict:
    """Detailed LLM matching of one candidate against one job. Returns
    ``score`` (0–1), ``strengths``, ``gaps``, ``reasoning``."""
    from app.sdk_bridge import build_recruiter

    return build_recruiter(_cfg()).match(candidate_id, job_id).model_dump()


@mcp.tool()
def match_candidate_to_jobs(candidate_id: str) -> dict:
    """Match one candidate against ALL open jobs via LLM. Returns ``rankings``
    (each with job_id, title, company, score, strengths, gaps, one_liner) and a
    ``summary``."""
    from app.agents.planning import match_candidate_to_jobs as _match

    result = _match(_cfg(), candidate_id)
    # Drop the bulky raw candidate dict from the response.
    result.pop("candidate", None)
    return result


@mcp.tool()
def evaluate_candidate(candidate_id: str, job_id: str = "") -> dict:
    """Multi-agent (resume / culture / risk / market) swarm evaluation of a
    candidate, optionally against a specific job. Returns per-dimension scores,
    an ``overall_score`` (0–100), a ``hire_recommendation`` and a ``synthesis``."""
    from app.agents.evaluation_swarm import evaluate_candidate_swarm

    return evaluate_candidate_swarm(_cfg(), candidate_id, job_id=job_id)


def main() -> None:
    """Entry point — init local stores, then serve over stdio."""
    logging.basicConfig(level=logging.WARNING)
    from app.database import init_db
    init_db()
    # The vector index opens lazily on first search, so there is nothing to
    # initialise here — and nothing to fail before the server is listening.
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
