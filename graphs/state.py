"""Shared state schemas for all LangGraph graphs.

Each TypedDict defines the shape of data flowing through a graph.
LangGraph reads these annotations to manage state persistence and
node-to-node data passing via SqliteSaver checkpoints.

Hierarchy:
  BaseWorkflowState   — common fields shared by ALL graphs
  ├── ChatState       — single-turn chat graph
  ├── PlannerState    — supervisor / planner graph
  └── AgentState      — individual specialist agent subgraphs
      └── JDAgentState, MatchingAgentState, ...  (agent-specific extensions)
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
