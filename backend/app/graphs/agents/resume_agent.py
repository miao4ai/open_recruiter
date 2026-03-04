"""Resume Agent — LangGraph subgraph for resume parsing.

Wraps the existing agents/resume.py logic as a 3-node LangGraph StateGraph:

    ┌────────────────┐     ┌───────────┐     ┌────────────┐
    │ extract_resume │────▶│ validate  │────▶│  finalize  │
    │  (LLM call)    │     │ (check)   │     │ (output)   │
    └────────────────┘     └───────────┘     └────────────┘

Nodes:
  1. extract_resume — Calls LLM via llm.chat_json() to parse raw resume text
                      into structured candidate fields (name, skills, etc.)
  2. validate       — Checks required fields (name must be present), normalises
                      types (skills → list, experience_years → int).
  3. finalize       — Packs the result into agent_output for the Supervisor.

This agent is structurally similar to jd_agent — both take raw text in and
produce structured data out. The key difference is the prompt (PARSE_RESUME)
and the output schema (candidate fields vs job fields).

Usage by Supervisor:
    from app.graphs.agents.resume_agent import resume_agent_graph

    result = resume_agent_graph.invoke({
        "cfg": config,
        "agent_input": {"raw_text": "John Doe, Senior Engineer..."},
    })
    parsed_resume = result["agent_output"]
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from app.graphs.state import ResumeAgentState
from app.llm import chat_json
from app.prompts import PARSE_RESUME

log = logging.getLogger(__name__)


# ── Node 1: extract_resume ───────────────────────────────────────────────
# Sends the raw resume text to the LLM with the PARSE_RESUME prompt.
# The LLM extracts: name, email, phone, current_title, current_company,
# skills, experience_years, location, date_of_birth, resume_summary.

def extract_resume(state: ResumeAgentState) -> dict:
    """Call LLM to parse raw resume text into structured candidate fields."""
    cfg = state["cfg"]
    raw_text = state.get("raw_text") or state.get("agent_input", {}).get("raw_text", "")

    if not raw_text:
        return {
            "agent_status": "error",
            "error": "No raw_text provided for resume parsing",
        }

    try:
        data = chat_json(
            cfg,
            system=PARSE_RESUME,
            messages=[{"role": "user", "content": raw_text}],
        )
    except Exception as e:
        log.error("Resume Agent LLM call failed: %s", e)
        return {
            "agent_status": "error",
            "error": f"LLM call failed: {e}",
        }

    # LLM may return a list — unwrap
    if isinstance(data, list):
        data = data[0] if data else {}

    return {
        "parsed_resume": data,
        "current_step": "extract_resume",
        "steps_completed": [*(state.get("steps_completed") or []), "extract_resume"],
    }


# ── Node 2: validate ─────────────────────────────────────────────────────
# Normalises all fields to expected types and checks that at least the
# candidate name was extracted — without a name the record is useless.

def validate(state: ResumeAgentState) -> dict:
    """Validate and normalise the parsed resume fields."""
    data = state.get("parsed_resume", {})

    if not data:
        return {
            "agent_status": "error",
            "error": "LLM returned empty result",
        }

    normalised = {
        "name": str(data.get("name", "")),
        "email": str(data.get("email", "")),
        "phone": str(data.get("phone", "")),
        "current_title": str(data.get("current_title", "")),
        "current_company": str(data.get("current_company", "")),
        "skills": _ensure_list(data.get("skills")),
        "experience_years": _safe_int(data.get("experience_years")),
        "location": str(data.get("location", "")),
        "date_of_birth": str(data.get("date_of_birth", "")),
        "resume_summary": str(data.get("resume_summary", "")),
    }

    # Must have at least a name
    if not normalised["name"]:
        return {
            "parsed_resume": normalised,
            "agent_status": "error",
            "error": "Parsed resume is missing required field: name",
        }

    return {
        "parsed_resume": normalised,
        "current_step": "validate",
        "steps_completed": [*(state.get("steps_completed") or []), "validate"],
    }


# ── Node 3: finalize ─────────────────────────────────────────────────────
# Writes the validated result to agent_output. If a candidate_id was
# provided (update scenario), it's included so the Supervisor knows
# which candidate record to update.

def finalize(state: ResumeAgentState) -> dict:
    """Write the final parsed resume to agent_output."""
    parsed = state.get("parsed_resume", {})
    candidate_id = (
        state.get("candidate_id")
        or state.get("agent_input", {}).get("candidate_id", "")
    )

    output = {**parsed}
    if candidate_id:
        output["candidate_id"] = candidate_id

    return {
        "agent_output": output,
        "agent_status": state.get("agent_status", "success"),
        "agent_name": "resume",
        "current_step": "finalize",
        "steps_completed": [*(state.get("steps_completed") or []), "finalize"],
    }


# ── Graph assembly ───────────────────────────────────────────────────────

def build_resume_agent_graph() -> StateGraph:
    """Construct the Resume Agent subgraph.

    Flow:
        extract_resume → validate → finalize → END

    On error at extract_resume, skips directly to finalize.
    """
    graph = StateGraph(ResumeAgentState)

    graph.add_node("extract_resume", extract_resume)
    graph.add_node("validate", validate)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("extract_resume")

    graph.add_conditional_edges(
        "extract_resume",
        lambda s: "finalize" if s.get("agent_status") == "error" else "validate",
    )
    graph.add_edge("validate", "finalize")
    graph.add_edge("finalize", END)

    return graph


# Pre-built compiled graph — import this in the Supervisor
resume_agent_graph = build_resume_agent_graph().compile()


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
