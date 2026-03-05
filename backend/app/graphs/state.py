"""Shared state schemas for all LangGraph graphs.

Each TypedDict defines the shape of data flowing through a graph.
LangGraph reads these annotations to manage state persistence and
node-to-node data passing via SqliteSaver checkpoints.

Hierarchy:
  BaseWorkflowState   — common fields shared by ALL graphs
  ├── ChatState       — single-turn chat graph
  ├── PlannerState    — supervisor / planner graph
  └── AgentState      — individual specialist agent subgraphs
      └── JDAgentState, ResumeAgentState, CommunicationAgentState, ...  (per-agent)
"""

from __future__ import annotations

from typing import Any, TypedDict


# ── Base ──────────────────────────────────────────────────────────────────

class BaseWorkflowState(TypedDict, total=False):
    """Fields present in every graph execution."""

    # Identity
    session_id: str
    user_id: str
    workflow_id: str

    # LLM config (passed through so nodes can call llm.py)
    cfg: Any  # app.config.Config — use Any to avoid import cycles

    # Execution tracking
    current_step: str
    steps_completed: list[str]
    error: str


# ── Chat Graph ────────────────────────────────────────────────────────────

class ChatState(BaseWorkflowState, total=False):
    """State for the single-turn chat graph."""

    # Input
    user_message: str
    conversation_history: list[dict]

    # RAG context injected by build_context node
    rag_context: str

    # LLM output
    llm_response: str
    parsed_action: dict          # {"action": "...", "params": {...}} or {}

    # Final
    response_text: str


# ── Planner / Supervisor Graph ────────────────────────────────────────────

class PlannerState(BaseWorkflowState, total=False):
    """State for the supervisor that plans and dispatches agents."""

    # Input
    user_message: str
    conversation_history: list[dict]

    # Planning
    plan: dict                   # {goal, workflow_type, agents_required, steps[]}
    plan_status: str             # pending | approved | rejected | modified

    # Multi-agent dispatch
    agents_required: list[str]   # ["matching", "communication", ...]
    agent_results: dict          # {agent_name: result_dict, ...}

    # Final
    response_text: str


# ── Specialist Agent State ────────────────────────────────────────────────

class AgentState(BaseWorkflowState, total=False):
    """Base state for specialist agent subgraphs.

    Each agent receives input from the Supervisor, does its work,
    and writes results back. The Supervisor reads agent_output to
    decide the next step.
    """

    # Input from Supervisor
    agent_input: dict            # Task-specific payload
    agent_name: str              # "jd" | "matching" | "communication" | ...

    # Output back to Supervisor
    agent_output: dict           # Agent-specific result
    agent_status: str            # "success" | "error" | "needs_approval"


# ── JD Agent ─────────────────────────────────────────────────────────────

class JDAgentState(AgentState, total=False):
    """State specific to the JD (Job Description) parsing agent.

    Input:  agent_input = {"raw_text": "...", "job_id": "..."}
    Output: agent_output = {"title": ..., "company": ..., "required_skills": [...], ...}
    """

    raw_text: str                # Raw JD text to parse
    job_id: str                  # Optional — existing job to update
    parsed_jd: dict              # Structured fields extracted by LLM


# ── Resume Agent ──────────────────────────────────────────────────────────

class ResumeAgentState(AgentState, total=False):
    """State specific to the Resume parsing agent.

    Input:  agent_input = {"raw_text": "...", "candidate_id": "..."}
    Output: agent_output = {"name": ..., "skills": [...], "resume_summary": ..., ...}
    """

    raw_text: str                # Raw resume text to parse
    candidate_id: str            # Optional — existing candidate to update
    parsed_resume: dict          # Structured fields extracted by LLM


# ── Communication Agent ──────────────────────────────────────────────────

class CommunicationAgentState(AgentState, total=False):
    """State specific to the Communication (email drafting) agent.

    Input:  agent_input = {"candidate_id": ..., "job_id": ..., "email_type": ..., ...}
    Output: agent_output = {"subject": ..., "body": ..., "candidate_name": ...}
    """

    candidate_id: str            # Target candidate
    job_id: str                  # Related job (optional)
    email_type: str              # outreach | followup | interview_invite | rejection
    instructions: str            # User-provided drafting instructions
    candidate_context: dict      # Loaded candidate profile
    job_context: dict            # Loaded job description
    email_history: list[dict]    # Prior emails with this candidate
    draft: dict                  # {"subject": ..., "body": ...}


# ── Matching Agent ────────────────────────────────────────────────────────

class MatchingAgentState(AgentState, total=False):
    """State specific to the Matching (candidate-job scoring) agent.

    Input:  agent_input = {"job_id": ..., "candidate_ids": [...], "top_k": 20}
    Output: agent_output = {"rankings": [...], "detailed_matches": [...]}
    """

    job_id: str                  # Target job
    candidate_ids: list[str]     # Specific candidates (optional — empty means all)
    top_k: int                   # Max candidates for vector search
    job_context: dict            # Loaded job record
    vector_rankings: list[dict]  # Results from vector similarity search
    detailed_matches: list[dict] # LLM-evaluated match results per candidate


# ── Scheduling Agent ─────────────────────────────────────────────────────

class SchedulingAgentState(AgentState, total=False):
    """State specific to the Scheduling (interview coordination) agent.

    Input:  agent_input = {"candidate_id": ..., "job_id": ..., "num_slots": 3}
    Output: agent_output = {"event": {...}, "email_draft": {...}, "slots": [...]}
    """

    candidate_id: str            # Candidate to schedule
    job_id: str                  # Related job
    candidate_context: dict      # Loaded candidate record
    job_context: dict            # Loaded job record
    num_slots: int               # How many time slots to propose (default 3)
    proposed_slots: list[dict]   # Generated time slot options
    selected_slot: dict          # Slot chosen after INTERRUPT
    event: dict                  # Created calendar event
    email_draft: dict            # Drafted invite email


# ── Pipeline Agent ────────────────────────────────────────────────────────

class PipelineAgentState(AgentState, total=False):
    """State specific to the Pipeline (cleanup/maintenance) agent.

    Input:  agent_input = {"days_stale": 3}
    Output: agent_output = {"stale_candidates": [...], "actions": [...], "summary": ...}
    """

    days_stale: int              # Threshold in days for staleness
    stale_candidates: list[dict] # Candidates identified as stale
    actions: list[dict]          # Categorised actions (follow_up / archive / reject)
    executed: list[dict]         # Results of executed actions
