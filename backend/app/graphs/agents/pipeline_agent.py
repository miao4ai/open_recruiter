"""Pipeline Agent — LangGraph subgraph for pipeline cleanup/maintenance.

Wraps the pipeline_cleanup logic from orchestrator.py as a 5-node
LangGraph StateGraph with interrupt() for human-in-the-loop:

    ┌────────┐   ┌────────────┐   ┌───────────┐   ┌─────────┐   ┌──────────┐
    │  scan  │──▶│ categorize │──▶│ INTERRUPT │──▶│ execute │──▶│ finalize │
    │        │   │            │   │ (approval)│   │         │   │ (output) │
    └────────┘   └────────────┘   └───────────┘   └─────────┘   └──────────┘

Nodes:
  1. scan        — Finds stale candidates: those with status "contacted"
                   whose last update was more than N days ago.
  2. categorize  — Assigns an action to each stale candidate based on
                   how long they've been stale:
                     >= 14 days → reject
                     >= 7 days  → archive
                     < 7 days   → follow_up
  3. INTERRUPT   — Pauses the graph. The Supervisor emits an SSE
                   approval_needed event showing all proposed actions.
                   User approves, modifies, or cancels.
  4. execute     — Applies the approved actions: updates candidate
                   statuses in the database (rejected / withdrawn / no-op).
  5. finalize    — Packs results into agent_output.

Usage by Supervisor:
    from app.graphs.agents.pipeline_agent import pipeline_agent_graph

    # First invocation — pauses at INTERRUPT
    result = pipeline_agent_graph.invoke(
        {"cfg": config, "agent_input": {"days_stale": 3}},
        config={"configurable": {"thread_id": workflow_id}},
    )

    # After user approves — resume
    from langgraph.types import Command
    result = pipeline_agent_graph.invoke(
        Command(resume={"approved": True}),
        config={"configurable": {"thread_id": workflow_id}},
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from app import database as db
from app.graphs.state import PipelineAgentState

log = logging.getLogger(__name__)

DEFAULT_DAYS_STALE = 3


# ── Node 1: scan ─────────────────────────────────────────────────────────
# Scans the entire candidate pool for stale entries. A candidate is
# considered "stale" if:
#   - Their status is "contacted" (we reached out but got no response)
#   - Their last update was more than days_stale days ago
#
# This is a pure DB-read operation — no LLM calls.

def scan(state: PipelineAgentState) -> dict:
    """Find stale candidates in the pipeline."""
    agent_input = state.get("agent_input", {})
    days_stale = state.get("days_stale") or agent_input.get("days_stale", DEFAULT_DAYS_STALE)
    cutoff = (datetime.now() - timedelta(days=days_stale)).isoformat()

    all_candidates = db.list_candidates()
    stale = []
    for c in all_candidates:
        if c.get("status") != "contacted":
            continue
        updated = c.get("updated_at") or c.get("created_at", "")
        if updated and updated < cutoff:
            stale.append(c)

    if not stale:
        return {
            "days_stale": days_stale,
            "stale_candidates": [],
            "actions": [],
            "agent_status": "success",
            "agent_output": {
                "stale_candidates": [],
                "actions": [],
                "summary": f"Pipeline is clean — no candidates stale for more than {days_stale} days.",
            },
            "current_step": "scan",
            "steps_completed": [*(state.get("steps_completed") or []), "scan"],
        }

    return {
        "days_stale": days_stale,
        "stale_candidates": stale,
        "current_step": "scan",
        "steps_completed": [*(state.get("steps_completed") or []), "scan"],
    }


# ── Node 2: categorize ───────────────────────────────────────────────────
# Assigns an action to each stale candidate based on staleness duration:
#   - >= 14 days stale → "reject" (probably not interested)
#   - >= 7 days stale  → "archive" (might circle back later)
#   - < 7 days stale   → "follow_up" (worth one more try)
#
# This is a deterministic heuristic — no LLM needed.
# Future enhancement: use LLM to make smarter decisions based on context.

def categorize(state: PipelineAgentState) -> dict:
    """Categorise stale candidates into actions."""
    stale = state.get("stale_candidates", [])

    actions = []
    for c in stale:
        updated = c.get("updated_at") or c.get("created_at", "")
        days = 0
        if updated:
            try:
                days = (datetime.now() - datetime.fromisoformat(updated)).days
            except ValueError:
                days = 0

        if days >= 14:
            action = "reject"
        elif days >= 7:
            action = "archive"
        else:
            action = "follow_up"

        actions.append({
            "id": c["id"],
            "name": c.get("name", ""),
            "action": action,
            "days": days,
            "current_status": c.get("status", ""),
        })

    return {
        "actions": actions,
        "current_step": "categorize",
        "steps_completed": [*(state.get("steps_completed") or []), "categorize"],
    }


# ── Node 3: wait_for_approval ────────────────────────────────────────────
# Pauses the graph with interrupt(). The Supervisor emits an SSE event
# showing all proposed actions so the user can review and approve.

def wait_for_approval(state: PipelineAgentState) -> dict:
    """Pause execution and wait for user approval of cleanup actions."""
    actions = state.get("actions", [])

    follow_ups = sum(1 for a in actions if a["action"] == "follow_up")
    rejects = sum(1 for a in actions if a["action"] == "reject")
    archives = sum(1 for a in actions if a["action"] == "archive")

    response = interrupt({
        "type": "pipeline_cleanup_approval",
        "title": f"Execute pipeline cleanup ({len(actions)} actions)?",
        "description": (
            f"Follow-up: {follow_ups}, Archive: {archives}, Reject: {rejects}"
        ),
        "actions": actions,
    })

    # User may modify the actions list
    updated_actions = response.get("actions", actions)

    return {
        "actions": updated_actions,
        "current_step": "wait_for_approval",
        "steps_completed": [*(state.get("steps_completed") or []), "wait_for_approval"],
    }


# ── Node 4: execute ──────────────────────────────────────────────────────
# Applies each approved action by updating candidate statuses in the DB:
#   - "reject"    → status = "rejected"
#   - "archive"   → status = "withdrawn"
#   - "follow_up" → no status change (just noted for follow-up workflows)

def execute(state: PipelineAgentState) -> dict:
    """Execute the approved cleanup actions."""
    actions = state.get("actions", [])
    now = datetime.now().isoformat()

    executed = []
    for a in actions:
        cid = a["id"]
        action_type = a["action"]

        if action_type == "reject":
            db.update_candidate(cid, {"status": "rejected", "updated_at": now})
            executed.append({**a, "result": "status → rejected"})
        elif action_type == "archive":
            db.update_candidate(cid, {"status": "withdrawn", "updated_at": now})
            executed.append({**a, "result": "status → withdrawn"})
        else:
            # follow_up — keep current status, just record it
            executed.append({**a, "result": "noted for follow-up"})

    return {
        "executed": executed,
        "current_step": "execute",
        "steps_completed": [*(state.get("steps_completed") or []), "execute"],
    }


# ── Node 5: finalize ─────────────────────────────────────────────────────
# Builds a summary and packs everything into agent_output.

def finalize(state: PipelineAgentState) -> dict:
    """Write the final pipeline cleanup result to agent_output."""
    actions = state.get("actions", [])
    executed = state.get("executed", [])

    output = {
        "stale_candidates": [
            {"id": c["id"], "name": c.get("name", "")}
            for c in state.get("stale_candidates", [])
        ],
        "actions": actions,
        "executed": executed,
        "summary": f"Pipeline cleanup complete — processed {len(executed)} candidates.",
    }

    return {
        "agent_output": output,
        "agent_status": state.get("agent_status", "success"),
        "agent_name": "pipeline",
        "current_step": "finalize",
        "steps_completed": [*(state.get("steps_completed") or []), "finalize"],
    }


# ── Graph assembly ───────────────────────────────────────────────────────

def _route_after_scan(state: PipelineAgentState) -> str:
    """Skip to finalize if no stale candidates found or on error."""
    if state.get("agent_status") == "error":
        return "finalize"
    # If scan already set agent_output (no stale candidates), go to finalize
    if state.get("agent_output"):
        return "finalize"
    return "categorize"


def build_pipeline_agent_graph() -> StateGraph:
    """Construct the Pipeline Agent subgraph.

    Flow:
        scan → categorize → wait_for_approval → execute → finalize → END

    If scan finds no stale candidates, skips directly to finalize.
    wait_for_approval uses interrupt() — the graph pauses here until
    the user approves the proposed cleanup actions.
    """
    graph = StateGraph(PipelineAgentState)

    graph.add_node("scan", scan)
    graph.add_node("categorize", categorize)
    graph.add_node("wait_for_approval", wait_for_approval)
    graph.add_node("execute", execute)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("scan")

    graph.add_conditional_edges("scan", _route_after_scan)
    graph.add_edge("categorize", "wait_for_approval")
    graph.add_edge("wait_for_approval", "execute")
    graph.add_edge("execute", "finalize")
    graph.add_edge("finalize", END)

    return graph


# Pre-built compiled graph — import this in the Supervisor
pipeline_agent_graph = build_pipeline_agent_graph().compile()
