"""Matching Agent — LangGraph subgraph for candidate-job matching.

Wraps the existing agents/matching.py logic as a 4-node LangGraph StateGraph:

    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌────────────┐
    │  load_context │────▶│ vector_rank  │────▶│  llm_score   │────▶│  finalize  │
    │  (DB lookup)  │     │ (ChromaDB)   │     │ (per-cand.)  │     │  (output)  │
    └──────────────┘     └──────────────┘     └──────────────┘     └────────────┘

Nodes:
  1. load_context  — Loads the job record from DB to verify it exists.
  2. vector_rank   — Calls vectorstore.search_candidates_for_job() to get
                     a ranked list of candidates by semantic similarity.
                     This is a fast, cheap pre-filter (no LLM call).
  3. llm_score     — For each candidate in the ranked list, calls
                     matching.match_candidate_to_job() to get a detailed
                     LLM evaluation (score, strengths, gaps, reasoning).
  4. finalize      — Packs the results into agent_output for the Supervisor.

This agent is the most complex specialist because it combines two stages:
  - Stage 1 (vector_rank): Fast vector search via ChromaDB — narrows the
    candidate pool from potentially thousands down to top_k (~20).
  - Stage 2 (llm_score): Detailed LLM evaluation on each shortlisted
    candidate — expensive but gives nuanced analysis.

The Supervisor typically chains this after JD Agent (to ensure the job
is indexed) and before Communication Agent (to draft emails for top matches).

Usage by Supervisor:
    from app.graphs.agents.matching_agent import matching_agent_graph

    result = matching_agent_graph.invoke({
        "cfg": config,
        "agent_input": {"job_id": "job456", "top_k": 10},
    })
    matches = result["agent_output"]  # {"rankings": [...], "detailed_matches": [...]}
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from app import database as db
from app import vectorstore
from app.agents.matching import match_candidate_to_job
from app.graphs.state import MatchingAgentState

log = logging.getLogger(__name__)

DEFAULT_TOP_K = 20


# ── Node 1: load_context ─────────────────────────────────────────────────
# Loads the target job from the database. We need this to:
#   - Verify the job exists before doing expensive searches
#   - Have the job record available for logging/metadata

def load_context(state: MatchingAgentState) -> dict:
    """Load the target job from the database."""
    agent_input = state.get("agent_input", {})
    job_id = state.get("job_id") or agent_input.get("job_id", "")
    candidate_ids = state.get("candidate_ids") or agent_input.get("candidate_ids", [])
    top_k = state.get("top_k") or agent_input.get("top_k", DEFAULT_TOP_K)

    if not job_id:
        return {
            "agent_status": "error",
            "error": "No job_id provided",
        }

    job = db.get_job(job_id)
    if not job:
        return {
            "agent_status": "error",
            "error": f"Job not found: {job_id}",
        }

    return {
        "job_id": job_id,
        "candidate_ids": candidate_ids,
        "top_k": top_k,
        "job_context": job,
        "current_step": "load_context",
        "steps_completed": [*(state.get("steps_completed") or []), "load_context"],
    }


# ── Node 2: vector_rank ──────────────────────────────────────────────────
# Uses ChromaDB vector similarity to find candidates whose resume text
# is semantically close to the job description. This is the fast pre-filter
# that avoids sending every candidate through the expensive LLM scorer.
#
# If specific candidate_ids were provided (e.g. by the Supervisor for a
# targeted match), we still run the vector search but filter to only those IDs.

def vector_rank(state: MatchingAgentState) -> dict:
    """Rank candidates by vector similarity to the job."""
    job_id = state["job_id"]
    candidate_ids = state.get("candidate_ids", [])
    top_k = state.get("top_k", DEFAULT_TOP_K)

    try:
        results = vectorstore.search_candidates_for_job(
            job_id=job_id,
            n_results=top_k,
        )
    except Exception as e:
        log.error("Vector search failed: %s", e)
        return {
            "agent_status": "error",
            "error": f"Vector search failed: {e}",
        }

    # Filter to specific candidates if requested
    if candidate_ids:
        id_set = set(candidate_ids)
        results = [r for r in results if r.get("candidate_id") in id_set]

    if not results:
        return {
            "vector_rankings": [],
            "agent_status": "error",
            "error": "No matching candidates found in vector search",
        }

    return {
        "vector_rankings": results,
        "current_step": "vector_rank",
        "steps_completed": [*(state.get("steps_completed") or []), "vector_rank"],
    }


# ── Node 3: llm_score ────────────────────────────────────────────────────
# For each candidate from the vector search, calls the LLM to produce a
# detailed evaluation: score (0.0-1.0), strengths, gaps, and reasoning.
#
# This reuses the existing match_candidate_to_job() function from
# agents/matching.py — no logic duplication needed.

def llm_score(state: MatchingAgentState) -> dict:
    """Run detailed LLM matching for each candidate in the ranked list."""
    cfg = state["cfg"]
    job_id = state["job_id"]
    rankings = state.get("vector_rankings", [])

    detailed: list[dict] = []
    for rank_entry in rankings:
        cid = rank_entry.get("candidate_id", "")
        if not cid:
            continue

        result = match_candidate_to_job(cfg, job_id, cid)
        detailed.append({
            "candidate_id": cid,
            "candidate_name": rank_entry.get("candidate_name", ""),
            "vector_distance": rank_entry.get("distance"),
            "score": result.get("score", 0.0),
            "strengths": result.get("strengths", []),
            "gaps": result.get("gaps", []),
            "reasoning": result.get("reasoning", ""),
        })

    # Sort by LLM score descending
    detailed.sort(key=lambda x: x.get("score", 0.0), reverse=True)

    return {
        "detailed_matches": detailed,
        "current_step": "llm_score",
        "steps_completed": [*(state.get("steps_completed") or []), "llm_score"],
    }


# ── Node 4: finalize ─────────────────────────────────────────────────────
# Packs both the fast vector rankings and the detailed LLM scores into
# agent_output. The Supervisor can use vector_rankings for a quick overview
# or detailed_matches for the full analysis.

def finalize(state: MatchingAgentState) -> dict:
    """Write the final matching results to agent_output."""
    job = state.get("job_context", {})

    output = {
        "job_id": state.get("job_id", ""),
        "job_title": job.get("title", ""),
        "job_company": job.get("company", ""),
        "rankings": state.get("vector_rankings", []),
        "detailed_matches": state.get("detailed_matches", []),
        "total_candidates": len(state.get("vector_rankings", [])),
    }

    return {
        "agent_output": output,
        "agent_status": state.get("agent_status", "success"),
        "agent_name": "matching",
        "current_step": "finalize",
        "steps_completed": [*(state.get("steps_completed") or []), "finalize"],
    }


# ── Graph assembly ───────────────────────────────────────────────────────

def build_matching_agent_graph() -> StateGraph:
    """Construct the Matching Agent subgraph.

    Flow:
        load_context → vector_rank → llm_score → finalize → END

    On error at load_context or vector_rank, skips to finalize.
    llm_score always flows to finalize (even if some individual
    candidates fail — partial results are still useful).
    """
    graph = StateGraph(MatchingAgentState)

    graph.add_node("load_context", load_context)
    graph.add_node("vector_rank", vector_rank)
    graph.add_node("llm_score", llm_score)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("load_context")

    graph.add_conditional_edges(
        "load_context",
        lambda s: "finalize" if s.get("agent_status") == "error" else "vector_rank",
    )
    graph.add_conditional_edges(
        "vector_rank",
        lambda s: "finalize" if s.get("agent_status") == "error" else "llm_score",
    )
    graph.add_edge("llm_score", "finalize")
    graph.add_edge("finalize", END)

    return graph


# Pre-built compiled graph — import this in the Supervisor
matching_agent_graph = build_matching_agent_graph().compile()
