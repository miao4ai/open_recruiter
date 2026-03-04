"""Communication Agent — LangGraph subgraph for email drafting.

Wraps the existing agents/communication.py logic as a 4-node LangGraph StateGraph:

    ┌──────────────┐     ┌───────────────┐     ┌───────────┐     ┌────────────┐
    │ load_context  │────▶│  draft_email  │────▶│ validate  │────▶│  finalize  │
    │ (DB lookups)  │     │  (LLM call)   │     │ (check)   │     │ (output)   │
    └──────────────┘     └───────────────┘     └───────────┘     └────────────┘

Nodes:
  1. load_context  — Loads candidate profile, job description, and prior email
                     history from the database. This gives the LLM rich context
                     for personalisation.
  2. draft_email   — Calls LLM via llm.chat_json() with the DRAFT_EMAIL_ENHANCED
                     prompt to generate a personalised email (subject + body).
  3. validate      — Checks that subject and body are non-empty and within
                     reasonable length limits.
  4. finalize      — Packs the result into agent_output for the Supervisor.

Unlike jd_agent and resume_agent (which are pure text-in → structured-data-out),
this agent has a DB dependency in load_context. This is the pattern for agents
that need to gather context before calling the LLM.

Usage by Supervisor:
    from app.graphs.agents.communication_agent import communication_agent_graph

    result = communication_agent_graph.invoke({
        "cfg": config,
        "agent_input": {
            "candidate_id": "abc123",
            "job_id": "job456",
            "email_type": "outreach",
            "instructions": "Mention their Python experience",
        },
    })
    draft = result["agent_output"]  # {"subject": ..., "body": ..., ...}
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from app import database as db
from app.graphs.state import CommunicationAgentState
from app.llm import chat_json
from app.prompts import DRAFT_EMAIL_ENHANCED

log = logging.getLogger(__name__)


# ── Node 1: load_context ─────────────────────────────────────────────────
# Loads all the context the LLM needs to write a personalised email:
#   - Candidate profile (name, title, skills, resume summary)
#   - Job description (title, required skills, company) — if a job_id is given
#   - Prior email history — so the LLM avoids repeating itself
#
# This is a pure DB-read step with no LLM calls.

def load_context(state: CommunicationAgentState) -> dict:
    """Load candidate, job, and email history from the database."""
    agent_input = state.get("agent_input", {})
    candidate_id = state.get("candidate_id") or agent_input.get("candidate_id", "")
    job_id = state.get("job_id") or agent_input.get("job_id", "")
    email_type = state.get("email_type") or agent_input.get("email_type", "outreach")
    instructions = state.get("instructions") or agent_input.get("instructions", "")

    if not candidate_id:
        return {
            "agent_status": "error",
            "error": "No candidate_id provided",
        }

    candidate = db.get_candidate(candidate_id)
    if not candidate:
        return {
            "agent_status": "error",
            "error": f"Candidate not found: {candidate_id}",
        }

    # Load job if available
    job = None
    if job_id:
        job = db.get_job(job_id)
    elif candidate.get("job_id"):
        job = db.get_job(candidate["job_id"])

    # Load prior emails for context
    prior_emails = db.list_emails(candidate_id=candidate_id)

    return {
        "candidate_id": candidate_id,
        "job_id": job_id,
        "email_type": email_type,
        "instructions": instructions,
        "candidate_context": candidate,
        "job_context": job or {},
        "email_history": prior_emails[:5],  # Last 5 emails
        "current_step": "load_context",
        "steps_completed": [*(state.get("steps_completed") or []), "load_context"],
    }


# ── Node 2: draft_email ──────────────────────────────────────────────────
# Builds a rich prompt from the loaded context and calls the LLM to
# generate the email. The prompt includes candidate profile, job details,
# prior email history, and the user's specific instructions.

def draft_email(state: CommunicationAgentState) -> dict:
    """Call LLM to draft a personalised email."""
    cfg = state["cfg"]
    candidate = state.get("candidate_context", {})
    job = state.get("job_context", {})
    email_history = state.get("email_history", [])
    email_type = state.get("email_type", "outreach")
    instructions = state.get("instructions", "")

    # Build rich context (same format as existing communication.py)
    parts: list[str] = []

    # Candidate profile
    skills = candidate.get("skills", [])
    skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)
    parts.append(
        f"## Candidate Profile\n"
        f"Name: {candidate.get('name', '')}\n"
        f"Email: {candidate.get('email', '')}\n"
        f"Title: {candidate.get('current_title', '')}\n"
        f"Company: {candidate.get('current_company', '')}\n"
        f"Skills: {skills_str}\n"
        f"Experience: {candidate.get('experience_years', 'N/A')} years\n"
        f"Location: {candidate.get('location', '')}\n"
        f"Summary: {candidate.get('resume_summary', '')}"
    )

    # Job description
    if job:
        parts.append(
            f"\n## Job Description\n"
            f"Title: {job.get('title', '')}\n"
            f"Company: {job.get('company', '')}\n"
            f"Required Skills: {', '.join(job.get('required_skills', []))}\n"
            f"Preferred Skills: {', '.join(job.get('preferred_skills', []))}\n"
            f"Experience: {job.get('experience_years', 'N/A')} years\n"
            f"Location: {job.get('location', '')}\n"
            f"Summary: {job.get('summary', '')}"
        )

    # Prior email history
    if email_history:
        parts.append(f"\n## Prior Emails ({len(email_history)})")
        for e in email_history:
            status = "sent" if e.get("sent") else "draft"
            parts.append(
                f"- [{status}] {e.get('email_type', '')}: \"{e.get('subject', '')}\"\n"
                f"  Body: {e.get('body', '')[:200]}..."
            )

    context = "\n".join(parts)
    user_msg = (
        f"{context}\n\n"
        f"## Task\n"
        f"Email type: {email_type}\n"
        f"User instructions: {instructions or 'None — use your best judgment'}\n"
    )

    try:
        data = chat_json(
            cfg,
            system=DRAFT_EMAIL_ENHANCED,
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as e:
        log.error("Communication Agent LLM call failed: %s", e)
        return {
            "agent_status": "error",
            "error": f"LLM call failed: {e}",
        }

    # LLM may return a list — unwrap
    if isinstance(data, list):
        data = data[0] if data else {}

    return {
        "draft": data,
        "current_step": "draft_email",
        "steps_completed": [*(state.get("steps_completed") or []), "draft_email"],
    }


# ── Node 3: validate ─────────────────────────────────────────────────────
# Checks that the LLM produced a usable email draft. A valid draft must
# have both a non-empty subject line and body text.

def validate(state: CommunicationAgentState) -> dict:
    """Validate the drafted email."""
    draft = state.get("draft", {})

    if not draft:
        return {
            "agent_status": "error",
            "error": "LLM returned empty draft",
        }

    subject = str(draft.get("subject", "")).strip()
    body = str(draft.get("body", "")).strip()

    if not subject:
        return {
            "draft": draft,
            "agent_status": "error",
            "error": "Draft is missing subject line",
        }

    if not body:
        return {
            "draft": draft,
            "agent_status": "error",
            "error": "Draft is missing email body",
        }

    # Normalise
    normalised = {"subject": subject, "body": body}

    return {
        "draft": normalised,
        "current_step": "validate",
        "steps_completed": [*(state.get("steps_completed") or []), "validate"],
    }


# ── Node 4: finalize ─────────────────────────────────────────────────────
# Packs the validated draft into agent_output along with metadata
# (candidate info, email type) so the Supervisor or downstream nodes
# can use it for approval UI or sending.

def finalize(state: CommunicationAgentState) -> dict:
    """Write the final email draft to agent_output."""
    draft = state.get("draft", {})
    candidate = state.get("candidate_context", {})

    output = {
        "subject": draft.get("subject", ""),
        "body": draft.get("body", ""),
        "candidate_id": state.get("candidate_id", ""),
        "candidate_name": candidate.get("name", ""),
        "candidate_email": candidate.get("email", ""),
        "job_id": state.get("job_id", ""),
        "email_type": state.get("email_type", "outreach"),
    }

    return {
        "agent_output": output,
        "agent_status": state.get("agent_status", "success"),
        "agent_name": "communication",
        "current_step": "finalize",
        "steps_completed": [*(state.get("steps_completed") or []), "finalize"],
    }


# ── Graph assembly ───────────────────────────────────────────────────────

def build_communication_agent_graph() -> StateGraph:
    """Construct the Communication Agent subgraph.

    Flow:
        load_context → draft_email → validate → finalize → END

    On error at load_context or draft_email, skips to finalize.
    Validate always flows to finalize (even on error) so the Supervisor
    gets a status it can inspect.
    """
    graph = StateGraph(CommunicationAgentState)

    graph.add_node("load_context", load_context)
    graph.add_node("draft_email", draft_email)
    graph.add_node("validate", validate)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("load_context")

    # Skip to finalize on error at any pre-LLM step
    graph.add_conditional_edges(
        "load_context",
        lambda s: "finalize" if s.get("agent_status") == "error" else "draft_email",
    )
    graph.add_conditional_edges(
        "draft_email",
        lambda s: "finalize" if s.get("agent_status") == "error" else "validate",
    )
    graph.add_edge("validate", "finalize")
    graph.add_edge("finalize", END)

    return graph


# Pre-built compiled graph — import this in the Supervisor
communication_agent_graph = build_communication_agent_graph().compile()
