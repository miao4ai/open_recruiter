"""Job Match Agent — LangGraph subgraph for analyzing job-seeker fit (job seeker side).

Evaluates how well a job seeker's profile matches a specific job posting
using LLM scoring.

    load_context ──▶ evaluate ──▶ finalize

Nodes:
  1. load_context  — Loads the seeker's profile from DB and resolves
                     job details from agent_input or session history.
  2. evaluate      — Calls LLM with the MATCHING prompt to score the
                     candidate-job fit.
  3. finalize      — Packages the match result into agent_output.
"""

from __future__ import annotations

import json
import logging

from langgraph.graph import END, StateGraph

from app import database as db
from app.graphs.state import JobMatchAgentState

log = logging.getLogger(__name__)


# ── Node 1: load_context ────────────────────────────────────────────────

def load_context(state: JobMatchAgentState) -> dict:
    """Load the job seeker profile and resolve job details."""
    user_id = state.get("user_id", "")
    session_id = state.get("session_id", "")
    agent_input = state.get("agent_input", {})

    # Load seeker profile
    profile = db.get_job_seeker_profile_by_user(user_id) or {}
    if not profile.get("name"):
        return {
            "agent_output": {"error": "Please upload your resume first so I can analyze your match."},
            "agent_status": "error",
            "error": "No profile found",
            "current_step": "load_context",
            "steps_completed": [*(state.get("steps_completed") or []), "load_context"],
        }

    # Resolve job details from input or session history
    job_title = agent_input.get("job_title", "")
    job_company = agent_input.get("job_company", "")
    job_snippet = agent_input.get("job_snippet", "")
    job_url = agent_input.get("job_url", "")
    job_location = agent_input.get("job_location", "")
    job_index = agent_input.get("job_index")

    # If details are missing, try to find from recent search results in session
    if not job_snippet and session_id:
        recent_msgs = db.list_chat_messages(user_id, limit=10, session_id=session_id)
        for msg in reversed(recent_msgs):
            if msg.get("action_json"):
                try:
                    action = json.loads(msg["action_json"]) if isinstance(msg["action_json"], str) else msg["action_json"]
                    if isinstance(action, dict) and action.get("type") == "job_search_results":
                        jobs = action.get("jobs", [])
                        target = None
                        if job_index and 1 <= job_index <= len(jobs):
                            target = jobs[job_index - 1]
                        elif job_title:
                            for j in jobs:
                                if job_title.lower() in j.get("title", "").lower():
                                    target = j
                                    break
                        if target:
                            job_title = target.get("title", job_title)
                            job_company = target.get("company", job_company)
                            job_snippet = target.get("snippet", job_snippet)
                            job_url = target.get("url", job_url)
                            job_location = target.get("location", job_location)
                        break
                except (json.JSONDecodeError, TypeError):
                    pass

    if not job_title and not job_snippet:
        return {
            "agent_output": {"error": "Couldn't find the job details. Please search for jobs first."},
            "agent_status": "error",
            "error": "No job details found",
            "current_step": "load_context",
            "steps_completed": [*(state.get("steps_completed") or []), "load_context"],
        }

    job_info = {
        "title": job_title,
        "company": job_company,
        "location": job_location,
        "url": job_url,
        "snippet": job_snippet,
    }

    return {
        "profile": profile,
        "job_info": job_info,
        "current_step": "load_context",
        "steps_completed": [*(state.get("steps_completed") or []), "load_context"],
    }


# ── Node 2: evaluate ───────────────────────────────────────────────────

def evaluate(state: JobMatchAgentState) -> dict:
    """Use LLM to evaluate the candidate-job match."""
    from app.llm import chat_json
    from app.prompts import MATCHING

    # Short-circuit if already errored
    if state.get("error"):
        return {
            "current_step": "evaluate",
            "steps_completed": [*(state.get("steps_completed") or []), "evaluate"],
        }

    cfg = state.get("cfg")
    profile = state.get("profile", {})
    job_info = state.get("job_info", {})

    skills = profile.get("skills", [])
    skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)

    job_desc = f"Title: {job_info.get('title', '')}\n"
    if job_info.get("company"):
        job_desc += f"Company: {job_info['company']}\n"
    if job_info.get("location"):
        job_desc += f"Location: {job_info['location']}\n"
    job_desc += f"Description: {job_info.get('snippet', '')}\n"

    user_msg = (
        f"## Job Description\n{job_desc}\n\n"
        f"## Candidate Profile\n"
        f"Name: {profile.get('name', '')}\n"
        f"Title: {profile.get('current_title', '')}\n"
        f"Skills: {skills_str}\n"
        f"Experience: {profile.get('experience_years', 'N/A')} years\n"
        f"Summary: {profile.get('resume_summary', '')}\n"
    )

    try:
        match_data = chat_json(cfg, system=MATCHING, messages=[{"role": "user", "content": user_msg}])
        if isinstance(match_data, list):
            match_data = match_data[0] if match_data else {}

        match_result = {
            "score": float(match_data.get("score", 0.0)),
            "strengths": match_data.get("strengths", []),
            "gaps": match_data.get("gaps", []),
            "reasoning": match_data.get("reasoning", ""),
        }
    except Exception as e:
        log.error("Job match evaluation failed: %s", e)
        match_result = {"score": 0.0, "strengths": [], "gaps": [], "reasoning": f"Error: {e}"}

    return {
        "match_result": match_result,
        "current_step": "evaluate",
        "steps_completed": [*(state.get("steps_completed") or []), "evaluate"],
    }


# ── Node 3: finalize ───────────────────────────────────────────────────

def finalize(state: JobMatchAgentState) -> dict:
    """Package the match result into agent_output."""
    if state.get("error"):
        return {
            "current_step": "finalize",
            "steps_completed": [*(state.get("steps_completed") or []), "finalize"],
        }

    match_result = state.get("match_result", {})
    job_info = state.get("job_info", {})
    profile = state.get("profile", {})

    return {
        "agent_output": {
            "score": match_result.get("score", 0.0),
            "strengths": match_result.get("strengths", []),
            "gaps": match_result.get("gaps", []),
            "reasoning": match_result.get("reasoning", ""),
            "job": job_info,
            "candidate_name": profile.get("name", ""),
        },
        "agent_status": "success",
        "current_step": "finalize",
        "steps_completed": [*(state.get("steps_completed") or []), "finalize"],
    }


# ── Graph assembly ──────────────────────────────────────────────────────

def _route_after_load_context(state: JobMatchAgentState) -> str:
    if state.get("error"):
        return "finalize"
    return "evaluate"


def build_job_match_graph() -> StateGraph:
    graph = StateGraph(JobMatchAgentState)

    graph.add_node("load_context", load_context)
    graph.add_node("evaluate", evaluate)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("load_context")
    graph.add_conditional_edges("load_context", _route_after_load_context)
    graph.add_edge("evaluate", "finalize")
    graph.add_edge("finalize", END)

    return graph


job_match_agent_graph = build_job_match_graph().compile()
