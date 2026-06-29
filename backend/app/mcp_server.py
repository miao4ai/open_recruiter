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

from mcp.server.fastmcp import FastMCP

from app import database as db

log = logging.getLogger(__name__)

mcp = FastMCP("open-recruiter")


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
    from app.agents.matching import rank_candidates_for_job as _rank

    ranked = _rank(job_id, top_k=top_k)
    out = []
    for r in ranked:
        cand = db.get_candidate(r["candidate_id"])
        if not cand:
            continue
        out.append({
            "candidate_id": r["candidate_id"],
            "name": cand.get("name", "Unknown"),
            "current_title": cand.get("current_title", ""),
            "current_company": cand.get("current_company", ""),
            "experience_years": cand.get("experience_years"),
            "skills": (cand.get("skills") or [])[:8],
            "score": round(r.get("score", 0), 4),
        })
    return out


@mcp.tool()
def match_candidate_to_job(job_id: str, candidate_id: str) -> dict:
    """Detailed LLM matching of one candidate against one job. Returns
    ``score`` (0–1), ``strengths``, ``gaps``, ``reasoning``."""
    from app.agents.matching import match_candidate_to_job as _match

    return _match(_cfg(), job_id=job_id, candidate_id=candidate_id)


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
    from app.vectorstore import init_vectorstore

    init_db()
    try:
        init_vectorstore()
    except Exception:
        log.exception("Vector store init failed — rank_candidates_for_job will be unavailable")

    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
