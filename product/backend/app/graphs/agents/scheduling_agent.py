"""Scheduling Agent — LangGraph subgraph for interview coordination.

Wraps the interview_scheduling logic from orchestrator.py as a 5-node
LangGraph StateGraph with a native interrupt() for human-in-the-loop:

    ┌──────────────┐   ┌───────────────┐   ┌───────────┐   ┌──────────────┐   ┌──────────┐
    │ load_context  │──▶│ propose_slots │──▶│ INTERRUPT │──▶│ create_event │──▶│ finalize │
    │ (DB lookup)   │   │ (generate)    │   │ (approval)│   │ + draft_email│   │ (output) │
    └──────────────┘   └───────────────┘   └───────────┘   └──────────────┘   └──────────┘

Nodes:
  1. load_context   — Loads candidate and job records from the database.
  2. propose_slots  — Generates N time slots starting from tomorrow.
                      (Deterministic for now — no LLM needed.)
  3. INTERRUPT      — Pauses the graph. The Supervisor emits an SSE
                      approval_needed event with the proposed slots.
                      User picks a slot, graph resumes with selected_slot.
  4. create_event   — Creates a calendar event in the DB, updates candidate
                      status to "interview_scheduled", and drafts an invite
                      email via Communication Agent / llm.chat_json().
  5. finalize       — Packs event + email draft into agent_output.

This is the first agent that uses LangGraph's interrupt() for
human-in-the-loop. The user must approve the time slot before the
calendar event is created.

Usage by Supervisor:
    from app.graphs.agents.scheduling_agent import scheduling_agent_graph

    # First invocation — pauses at INTERRUPT
    result = scheduling_agent_graph.invoke(
        {"cfg": config, "agent_input": {"candidate_id": "abc", "job_id": "xyz"}},
        config={"configurable": {"thread_id": workflow_id}},
    )

    # After user approves — resume with selected slot
    from langgraph.types import Command
    result = scheduling_agent_graph.invoke(
        Command(resume={"selected_slot": slot}),
        config={"configurable": {"thread_id": workflow_id}},
    )
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from app import database as db
from app.agents.communication import draft_email
from app.graphs.state import SchedulingAgentState

log = logging.getLogger(__name__)

DEFAULT_NUM_SLOTS = 3


# ── Node 1: load_context ─────────────────────────────────────────────────
# Loads the candidate and job from the database. Both must exist for
# scheduling to proceed — you can't schedule an interview without knowing
# who and for what role.

def load_context(state: SchedulingAgentState) -> dict:
    """Load candidate and job records from the database."""
    agent_input = state.get("agent_input", {})
    candidate_id = state.get("candidate_id") or agent_input.get("candidate_id", "")
    job_id = state.get("job_id") or agent_input.get("job_id", "")
    num_slots = state.get("num_slots") or agent_input.get("num_slots", DEFAULT_NUM_SLOTS)

    if not candidate_id:
        return {"agent_status": "error", "error": "No candidate_id provided"}

    candidate = db.get_candidate(candidate_id)
    if not candidate:
        return {"agent_status": "error", "error": f"Candidate not found: {candidate_id}"}

    # Try to find a job if not specified
    job = None
    if job_id:
        job = db.get_job(job_id)
    elif candidate.get("job_id"):
        job = db.get_job(candidate["job_id"])
        job_id = candidate["job_id"]

    return {
        "candidate_id": candidate_id,
        "job_id": job_id,
        "num_slots": num_slots,
        "candidate_context": candidate,
        "job_context": job or {},
        "current_step": "load_context",
        "steps_completed": [*(state.get("steps_completed") or []), "load_context"],
    }


# ── Node 2: propose_slots ────────────────────────────────────────────────
# Generates time slots for the interview. Currently uses a simple
# deterministic strategy: N 1-hour slots on consecutive days starting
# tomorrow at 10:00, 11:00, 14:00, etc.
#
# Future enhancement: call an LLM or check a calendar API for availability.

def propose_slots(state: SchedulingAgentState) -> dict:
    """Generate proposed interview time slots."""
    num_slots = state.get("num_slots", DEFAULT_NUM_SLOTS)

    tomorrow = datetime.now() + timedelta(days=1)
    # Candidate hours for interviews (morning and afternoon)
    hours = [10, 11, 14, 15, 16]

    slots = []
    for i in range(num_slots):
        day = tomorrow + timedelta(days=i)
        hour = hours[i % len(hours)]
        slot_start = day.replace(hour=hour, minute=0, second=0, microsecond=0)
        slot_end = slot_start + timedelta(hours=1)
        slots.append({
            "start": slot_start.isoformat(),
            "end": slot_end.isoformat(),
            "label": (
                slot_start.strftime("%A %b %d, %I:%M %p")
                + " - "
                + slot_end.strftime("%I:%M %p")
            ),
        })

    return {
        "proposed_slots": slots,
        "selected_slot": slots[0],  # Default to first slot
        "current_step": "propose_slots",
        "steps_completed": [*(state.get("steps_completed") or []), "propose_slots"],
    }


# ── Node 3: wait_for_approval ────────────────────────────────────────────
# Uses LangGraph's native interrupt() to pause the graph.
# The Supervisor translates this into an SSE approval_needed event.
# When the user responds, the graph resumes with the selected slot.

def wait_for_approval(state: SchedulingAgentState) -> dict:
    """Pause execution and wait for user to select a time slot."""
    candidate = state.get("candidate_context", {})
    job = state.get("job_context", {})
    slots = state.get("proposed_slots", [])

    # interrupt() pauses the graph and returns the value to the caller.
    # When resumed, the resume value is returned by interrupt().
    response = interrupt({
        "type": "scheduling_approval",
        "title": f"Schedule interview with {candidate.get('name', '')}?",
        "description": f"Create a calendar event for {job.get('title', 'the role')}.",
        "slots": slots,
        "default_slot": slots[0] if slots else {},
    })

    # The resume value should contain the selected slot
    selected = response.get("selected_slot", slots[0] if slots else {})

    return {
        "selected_slot": selected,
        "current_step": "wait_for_approval",
        "steps_completed": [*(state.get("steps_completed") or []), "wait_for_approval"],
    }


# ── Node 4: create_event ─────────────────────────────────────────────────
# After user approval, creates the actual calendar event in the DB,
# updates the candidate's pipeline status to "interview_scheduled",
# and drafts an invite email.

def create_event(state: SchedulingAgentState) -> dict:
    """Create calendar event, update candidate status, and draft invite email."""
    cfg = state["cfg"]
    candidate_id = state["candidate_id"]
    candidate = state.get("candidate_context", {})
    job = state.get("job_context", {})
    job_id = state.get("job_id", "")
    slot = state.get("selected_slot", {})

    candidate_name = candidate.get("name", "")
    job_title = job.get("title", "the role")
    now = datetime.now().isoformat()

    # Create calendar event
    event_id = uuid.uuid4().hex[:8]
    event = {
        "id": event_id,
        "title": f"Interview: {candidate_name} — {job_title}",
        "start_time": slot.get("start", now),
        "end_time": slot.get("end", now),
        "event_type": "interview",
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "job_id": job_id,
        "job_title": job_title,
        "notes": "",
        "created_at": now,
        "updated_at": now,
    }
    db.insert_event(event)

    # Update candidate status
    db.update_candidate(candidate_id, {
        "status": "interview_scheduled",
        "updated_at": now,
    })

    # Draft invite email via existing communication agent logic
    email_draft = draft_email(
        cfg,
        candidate_id=candidate_id,
        job_id=job_id,
        email_type="interview_invite",
    )

    return {
        "event": event,
        "email_draft": email_draft,
        "current_step": "create_event",
        "steps_completed": [*(state.get("steps_completed") or []), "create_event"],
    }


# ── Node 5: finalize ─────────────────────────────────────────────────────
# Packs everything into agent_output so the Supervisor can report back.

def finalize(state: SchedulingAgentState) -> dict:
    """Write the final scheduling result to agent_output."""
    candidate = state.get("candidate_context", {})
    event = state.get("event", {})
    email_draft = state.get("email_draft", {})

    output = {
        "candidate_id": state.get("candidate_id", ""),
        "candidate_name": candidate.get("name", ""),
        "job_id": state.get("job_id", ""),
        "event": event,
        "email_draft": email_draft,
        "proposed_slots": state.get("proposed_slots", []),
        "selected_slot": state.get("selected_slot", {}),
    }

    return {
        "agent_output": output,
        "agent_status": state.get("agent_status", "success"),
        "agent_name": "scheduling",
        "current_step": "finalize",
        "steps_completed": [*(state.get("steps_completed") or []), "finalize"],
    }


# ── Graph assembly ───────────────────────────────────────────────────────

def build_scheduling_agent_graph() -> StateGraph:
    """Construct the Scheduling Agent subgraph.

    Flow:
        load_context → propose_slots → wait_for_approval → create_event → finalize → END

    On error at load_context, skips directly to finalize.
    wait_for_approval uses interrupt() — the graph pauses here until
    the user resumes it with a selected time slot.
    """
    graph = StateGraph(SchedulingAgentState)

    graph.add_node("load_context", load_context)
    graph.add_node("propose_slots", propose_slots)
    graph.add_node("wait_for_approval", wait_for_approval)
    graph.add_node("create_event", create_event)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("load_context")

    graph.add_conditional_edges(
        "load_context",
        lambda s: "finalize" if s.get("agent_status") == "error" else "propose_slots",
    )
    graph.add_edge("propose_slots", "wait_for_approval")
    graph.add_edge("wait_for_approval", "create_event")
    graph.add_edge("create_event", "finalize")
    graph.add_edge("finalize", END)

    return graph


# Pre-built compiled graph — import this in the Supervisor
scheduling_agent_graph = build_scheduling_agent_graph().compile()
