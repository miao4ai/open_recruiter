"""JD Agent — LangGraph subgraph for Job Description parsing.

Wraps the existing agents/jd.py logic as a 3-node LangGraph StateGraph:

    ┌────────────┐     ┌───────────┐     ┌────────────┐
    │ extract_jd │────▶│ validate  │────▶│  finalize  │
    │ (LLM call) │     │ (check)   │     │ (output)   │
    └────────────┘     └───────────┘     └────────────┘

Nodes:
  1. extract_jd  — Calls LLM via llm.chat_json() to parse raw JD text into
                   structured fields (title, company, skills, etc.)
  2. validate    — Checks that required fields are present and types are correct.
                   Sets agent_status to "error" if validation fails.
  3. finalize    — Writes the final result to agent_output so the Supervisor
                   can read it and decide the next step.

Usage by Supervisor:
    from graphs.agents.jd_agent import jd_agent_graph

    # Invoke as a subgraph within the supervisor
    result = jd_agent_graph.invoke({
        "cfg": config,
        "agent_input": {"raw_text": "Senior Engineer at Acme Corp..."},
    })
    parsed_jd = result["agent_output"]
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from graphs.state import JDAgentState
from app.llm import chat_json
from app.prompts import PARSE_JD

log = logging.getLogger(__name__)


# ── Node 1: extract_jd ───────────────────────────────────────────────────
# Sends raw JD text to LLM and parses the structured JSON response.
# This is the core intelligence — the LLM reads a free-form job posting
# and extracts title, company, skills, experience, location, etc.

def extract_jd(state: JDAgentState) -> dict:
    """Call LLM to parse raw JD text into structured fields."""
    cfg = state["cfg"]
    raw_text = state.get("raw_text") or state.get("agent_input", {}).get("raw_text", "")

    if not raw_text:
        return {
            "agent_status": "error",
            "error": "No raw_text provided for JD parsing",
        }

    try:
        data = chat_json(
            cfg,
            system=PARSE_JD,
            messages=[{"role": "user", "content": raw_text}],
        )
    except Exception as e:
        log.error("JD Agent LLM call failed: %s", e)
        return {
            "agent_status": "error",
            "error": f"LLM call failed: {e}",
        }

    # LLM may return a list — unwrap
    if isinstance(data, list):
        data = data[0] if data else {}

    return {
        "parsed_jd": data,
        "current_step": "extract_jd",
        "steps_completed": [*(state.get("steps_completed") or []), "extract_jd"],
    }


# ── Node 2: validate ─────────────────────────────────────────────────────
# Normalises the LLM output and checks required fields.
# If the LLM returned garbage or missed critical fields, we mark it as an
# error so the Supervisor can retry or escalate to the user.

def validate(state: JDAgentState) -> dict:
    """Validate and normalise the parsed JD fields."""
    data = state.get("parsed_jd", {})

    if not data:
        return {
            "agent_status": "error",
            "error": "LLM returned empty result",
        }

    # Normalise types
    normalised = {
        "title": str(data.get("title", "")),
        "company": str(data.get("company", "")),
        "required_skills": _ensure_list(data.get("required_skills")),
        "preferred_skills": _ensure_list(data.get("preferred_skills")),
        "experience_years": _safe_int(data.get("experience_years")),
        "location": str(data.get("location", "")),
        "remote": bool(data.get("remote", False)),
        "salary_range": str(data.get("salary_range", "")),
        "summary": str(data.get("summary", "")),
    }

    # Must have at least a title
    if not normalised["title"]:
        return {
            "parsed_jd": normalised,
            "agent_status": "error",
            "error": "Parsed JD is missing required field: title",
        }

    return {
        "parsed_jd": normalised,
        "current_step": "validate",
        "steps_completed": [*(state.get("steps_completed") or []), "validate"],
    }


# ── Node 3: finalize ─────────────────────────────────────────────────────
# Packs the validated result into agent_output so the Supervisor can read it.
# Also copies job_id through if this was an update operation.

def finalize(state: JDAgentState) -> dict:
    """Write the final parsed JD to agent_output."""
    parsed = state.get("parsed_jd", {})
    job_id = state.get("job_id") or state.get("agent_input", {}).get("job_id", "")

    output = {**parsed}
    if job_id:
        output["job_id"] = job_id

    return {
        "agent_output": output,
        "agent_status": state.get("agent_status", "success"),
        "agent_name": "jd",
        "current_step": "finalize",
        "steps_completed": [*(state.get("steps_completed") or []), "finalize"],
    }


# ── Graph assembly ───────────────────────────────────────────────────────

def build_jd_agent_graph() -> StateGraph:
    """Construct the JD Agent subgraph.

    Flow:
        extract_jd → validate → finalize → END

    On error at any node, the graph skips to finalize with
    agent_status="error" — the Supervisor checks this field.
    """
    graph = StateGraph(JDAgentState)

    graph.add_node("extract_jd", extract_jd)
    graph.add_node("validate", validate)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("extract_jd")

    # Route based on status — skip to finalize on error
    graph.add_conditional_edges(
        "extract_jd",
        lambda s: "finalize" if s.get("agent_status") == "error" else "validate",
    )
    graph.add_edge("validate", "finalize")
    graph.add_edge("finalize", END)

    return graph


# Pre-built compiled graph — import this in the Supervisor
jd_agent_graph = build_jd_agent_graph().compile()


# ── Helpers ───────────────────────────────────────────────────────────────

def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _ensure_list(val) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val:
        return [s.strip() for s in val.split(",")]
    return []
