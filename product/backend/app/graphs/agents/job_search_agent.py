"""Job Search Agent — LangGraph subgraph for web job searching (job seeker side).

Wraps the existing job_search.py module as a 3-node subgraph:

    search_web ──▶ enrich ──▶ finalize

Nodes:
  1. search_web  — Calls DuckDuckGo via search_jobs_web() to find job postings.
  2. enrich      — Optionally enriches raw results with LLM parsing for
                   structured job data (title, company, salary, etc.).
  3. finalize    — Packages results into agent_output for the supervisor.
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from app import database as db
from app.graphs.state import JobSearchAgentState

log = logging.getLogger(__name__)


# ── Node 1: search_web ──────────────────────────────────────────────────

def search_web(state: JobSearchAgentState) -> dict:
    """Search the web for job postings via DuckDuckGo."""
    from app.agents.job_search import search_jobs_web

    agent_input = state.get("agent_input", {})
    query = agent_input.get("query", "")
    location = agent_input.get("location", "")
    n_results = agent_input.get("n_results", 10)
    user_id = state.get("user_id", "")

    # If no query provided, build one from the seeker's profile
    if not query:
        profile = db.get_job_seeker_profile_by_user(user_id) or {}
        parts = []
        if profile.get("current_title"):
            parts.append(profile["current_title"])
        if profile.get("skills"):
            skills = profile["skills"]
            if isinstance(skills, list):
                parts.append(" ".join(skills[:5]))
        query = " ".join(parts) if parts else "software engineer"

        if not location and profile.get("location"):
            location = profile["location"]

    raw_results = search_jobs_web(query, location, n_results)

    return {
        "query": query,
        "location": location,
        "n_results": n_results,
        "raw_results": raw_results,
        "current_step": "search_web",
        "steps_completed": [*(state.get("steps_completed") or []), "search_web"],
    }


# ── Node 2: enrich ──────────────────────────────────────────────────────

def enrich(state: JobSearchAgentState) -> dict:
    """Enrich raw search results with LLM-parsed structured data."""
    from app.llm import chat_json

    cfg = state.get("cfg")
    raw_results = state.get("raw_results", [])

    if not raw_results:
        return {
            "enriched_results": [],
            "current_step": "enrich",
            "steps_completed": [*(state.get("steps_completed") or []), "enrich"],
        }

    # Try LLM enrichment
    try:
        results_text = "\n\n".join(
            f"### Result {i+1}\n"
            f"Title: {r['title']}\n"
            f"URL: {r.get('url', '')}\n"
            f"Source: {r.get('source', '')}\n"
            f"Snippet: {r.get('snippet', '')}"
            for i, r in enumerate(raw_results)
        )

        system_prompt = (
            "You are a job listing parser. Given web search results for job postings, "
            "extract structured job information from each result.\n\n"
            "Return a JSON array, one object per result, with:\n"
            '- "title": the job title (clean, without company name)\n'
            '- "company": the company name if identifiable\n'
            '- "location": location if mentioned\n'
            '- "url": the original URL (keep as-is)\n'
            '- "source": the source website (keep as-is)\n'
            '- "snippet": a 1-2 sentence summary of the role\n'
            '- "salary_range": salary if mentioned, empty string otherwise\n\n'
            "Only include results that are actual job postings. "
            "Skip generic articles or non-job content. Output valid JSON array only."
        )

        data = chat_json(
            cfg,
            system=system_prompt,
            messages=[{"role": "user", "content": results_text}],
        )

        enriched = []
        if isinstance(data, list):
            enriched = data
        elif isinstance(data, dict) and "jobs" in data:
            enriched = data["jobs"]

        # Assign indices
        for idx, r in enumerate(enriched):
            r["index"] = idx + 1

        return {
            "enriched_results": enriched[:state.get("n_results", 10)],
            "current_step": "enrich",
            "steps_completed": [*(state.get("steps_completed") or []), "enrich"],
        }
    except Exception as e:
        log.warning("LLM enrichment failed, using raw results: %s", e)
        # Fallback: use raw results with indices
        for idx, r in enumerate(raw_results):
            r["index"] = idx + 1
        return {
            "enriched_results": raw_results,
            "current_step": "enrich",
            "steps_completed": [*(state.get("steps_completed") or []), "enrich"],
        }


# ── Node 3: finalize ────────────────────────────────────────────────────

def finalize(state: JobSearchAgentState) -> dict:
    """Package search results into agent_output."""
    results = state.get("enriched_results", [])

    return {
        "agent_output": {
            "jobs": results,
            "total": len(results),
            "query": state.get("query", ""),
            "location": state.get("location", ""),
        },
        "agent_status": "success" if results else "error",
        "current_step": "finalize",
        "steps_completed": [*(state.get("steps_completed") or []), "finalize"],
    }


# ── Graph assembly ──────────────────────────────────────────────────────

def build_job_search_graph() -> StateGraph:
    graph = StateGraph(JobSearchAgentState)

    graph.add_node("search_web", search_web)
    graph.add_node("enrich", enrich)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("search_web")
    graph.add_edge("search_web", "enrich")
    graph.add_edge("enrich", "finalize")
    graph.add_edge("finalize", END)

    return graph


job_search_agent_graph = build_job_search_graph().compile()
