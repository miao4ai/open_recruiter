"""Supervisor — LangGraph graph that routes, plans, and dispatches agents.

This is the top-level entry point for all user interactions in v2.0.
It combines the Router and Planner roles:

    ┌──────────────┐     ┌─────────────────┐
    │  User Input  │────▶│  check_paused   │──── paused workflow? ──▶ resume_workflow
    └──────────────┘     └────────┬────────┘
                                  │ no
                         ┌────────▼────────┐
                         │ classify_intent │
                         └────────┬────────┘
                       ┌──────────┼──────────────┐
                       │          │              │
                ┌──────▼──┐ ┌────▼──────┐ ┌─────▼───────┐
                │  Chat   │ │  Plan +   │ │  Direct     │
                │  Graph  │ │  Dispatch │ │  Workflow    │
                └─────────┘ └───────────┘ └─────────────┘

Nodes:
  1. check_paused      — Checks if there's a paused workflow waiting for
                         user input in this session.
  2. classify_intent   — Uses the LLM (or keyword detection) to determine
                         what the user wants: simple chat, a complex multi-step
                         task (needs planning), or a direct workflow trigger.
  3. route_to_chat     — Invokes the Chat Graph as a subgraph.
  4. generate_plan     — For complex tasks, generates a structured plan with
                         agent assignments and step ordering.
  5. present_plan      — Emits the plan via SSE and pauses with interrupt()
                         for user approval.
  6. dispatch_agents   — After plan approval, dispatches specialist agents
                         in the order specified by the plan (sequential,
                         parallel, or handoff).
  7. resume_workflow   — Resumes a paused workflow with the user's response.
  8. finalize          — Aggregates agent results and returns the final response.

This graph uses SqliteSaver for checkpointing, enabling pause/resume across
HTTP requests via thread_id.
"""

from __future__ import annotations

import logging
import re

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from app import database as db
from app.graphs.state import PlannerState
from app.llm import chat_json

log = logging.getLogger(__name__)

# Intent types returned by classify_intent
INTENT_CHAT = "chat"
INTENT_WORKFLOW = "workflow"
INTENT_PLAN = "plan"

# Keyword patterns for direct workflow triggers
_WORKFLOW_PATTERNS = {
    "bulk_outreach": re.compile(
        r"(批量|bulk|mass).*(外联|outreach|发邮件|email|联系|contact)",
        re.IGNORECASE,
    ),
    "candidate_review": re.compile(
        r"(审查|review|分析|analyze|评估|evaluate).*(候选人|candidate)",
        re.IGNORECASE,
    ),
    "interview_scheduling": re.compile(
        r"(安排|schedule|预约|book).*(面试|interview)",
        re.IGNORECASE,
    ),
    "pipeline_cleanup": re.compile(
        r"(清理|cleanup|clean up|整理).*(管道|pipeline|候选人|candidates)",
        re.IGNORECASE,
    ),
    "job_launch": re.compile(
        r"(启动|launch|开始|start|发布|post).*(职位|job|招聘|hiring)",
        re.IGNORECASE,
    ),
}

CLASSIFY_INTENT_PROMPT = """\
You are a routing assistant. Classify the user's message into one of these intents:

1. "chat" — Simple question, greeting, or conversation that doesn't require any workflow.
2. "workflow" — The user wants to trigger a specific workflow. Return the workflow type.
3. "plan" — The user wants a complex, multi-step task that requires planning and multiple agents.

Workflow types: bulk_outreach, candidate_review, interview_scheduling, pipeline_cleanup, job_launch

Return JSON:
{
  "intent": "chat" | "workflow" | "plan",
  "workflow_type": "bulk_outreach" | "candidate_review" | ... | null,
  "reasoning": "one sentence explanation"
}
Only output valid JSON.
"""

PLAN_GENERATION_PROMPT = """\
You are a recruitment workflow planner. Given the user's request, create a structured execution plan.

Available agents:
- jd: Parse job descriptions into structured data
- resume: Parse resumes into structured candidate profiles
- matching: Search and rank candidates for jobs (vector search + LLM scoring)
- communication: Draft personalised emails (outreach, follow-up, interview invite, rejection)
- scheduling: Coordinate interview scheduling with time slot proposals
- pipeline: Pipeline cleanup — find stale candidates, categorise actions, execute
- job_search: Search the web for job postings (job seeker side)
- job_match: Analyze candidate-job fit and score matches (job seeker side)

Create a plan with ordered steps. Each step assigns one agent.
Steps can be "sequential" (wait for previous), "parallel" (run concurrently), or "interrupt" (needs user approval).

Return JSON:
{
  "goal": "what the user wants to achieve",
  "workflow_type": "the primary workflow type or 'multi'",
  "agents_required": ["agent1", "agent2"],
  "steps": [
    {"step": 1, "agent": "agent_name", "action": "what to do", "mode": "sequential|parallel|interrupt"}
  ],
  "requires_approval": true
}
Only output valid JSON.
"""


# ── Node 1: check_paused ─────────────────────────────────────────────────
# Before anything else, check if there's a paused workflow in this session.
# If so, the user's message is a response to an approval prompt — route
# directly to resume_workflow.

def check_paused(state: PlannerState) -> dict:
    """Check for paused workflows in this session."""
    session_id = state.get("session_id", "")

    if session_id:
        active_wf = db.get_active_workflow(session_id)
        if active_wf and active_wf.get("status") == "paused":
            return {
                "plan_status": "resuming",
                "plan": {"_paused_workflow": active_wf},
                "current_step": "check_paused",
                "steps_completed": [*(state.get("steps_completed") or []), "check_paused"],
            }

    return {
        "plan_status": "routing",
        "current_step": "check_paused",
        "steps_completed": [*(state.get("steps_completed") or []), "check_paused"],
    }


# ── Node 2: classify_intent ──────────────────────────────────────────────
# Determines what the user wants. First tries keyword matching for direct
# workflow triggers, then falls back to LLM classification for ambiguous
# messages.

def classify_intent(state: PlannerState) -> dict:
    """Classify user intent: chat, workflow, or plan."""
    cfg = state["cfg"]
    user_message = state.get("user_message", "")

    # Fast path: keyword-based workflow detection
    for wtype, pattern in _WORKFLOW_PATTERNS.items():
        if pattern.search(user_message):
            return {
                "plan_status": wtype,
                "plan": {"workflow_type": wtype, "intent": INTENT_WORKFLOW},
                "current_step": "classify_intent",
                "steps_completed": [*(state.get("steps_completed") or []), "classify_intent"],
            }

    # LLM classification for ambiguous messages
    try:
        result = chat_json(
            cfg,
            system=CLASSIFY_INTENT_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        if isinstance(result, list):
            result = result[0] if result else {}

        intent = result.get("intent", INTENT_CHAT)
        workflow_type = result.get("workflow_type")

        if intent == INTENT_WORKFLOW and workflow_type:
            return {
                "plan_status": workflow_type,
                "plan": {"workflow_type": workflow_type, "intent": INTENT_WORKFLOW},
                "current_step": "classify_intent",
                "steps_completed": [*(state.get("steps_completed") or []), "classify_intent"],
            }
        elif intent == INTENT_PLAN:
            return {
                "plan_status": "needs_plan",
                "plan": {"intent": INTENT_PLAN},
                "current_step": "classify_intent",
                "steps_completed": [*(state.get("steps_completed") or []), "classify_intent"],
            }
    except Exception as e:
        log.warning("Intent classification failed, defaulting to chat: %s", e)

    # Default to chat
    return {
        "plan_status": "chat",
        "plan": {"intent": INTENT_CHAT},
        "current_step": "classify_intent",
        "steps_completed": [*(state.get("steps_completed") or []), "classify_intent"],
    }


# ── Node 3: route_to_chat ────────────────────────────────────────────────
# Invokes the Chat Graph as a subgraph for simple conversations.

def route_to_chat(state: PlannerState) -> dict:
    """Delegate to the Chat Graph for simple conversation."""
    from app.graphs.chat_graph import chat_graph

    result = chat_graph.invoke({
        "cfg": state["cfg"],
        "user_id": state.get("user_id", ""),
        "session_id": state.get("session_id", ""),
        "user_message": state.get("user_message", ""),
    })

    return {
        "response_text": result.get("response_text", ""),
        "agent_results": {"chat": result},
        "current_step": "route_to_chat",
        "steps_completed": [*(state.get("steps_completed") or []), "route_to_chat"],
    }


# ── Node 4: generate_plan ────────────────────────────────────────────────
# For complex multi-step tasks, calls the LLM to generate a structured
# execution plan with agent assignments.

def generate_plan(state: PlannerState) -> dict:
    """Generate a structured execution plan for complex tasks."""
    cfg = state["cfg"]
    user_message = state.get("user_message", "")

    try:
        plan = chat_json(
            cfg,
            system=PLAN_GENERATION_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        if isinstance(plan, list):
            plan = plan[0] if plan else {}
    except Exception as e:
        log.error("Plan generation failed: %s", e)
        return {
            "plan": {"error": str(e)},
            "plan_status": "error",
            "error": f"Plan generation failed: {e}",
        }

    return {
        "plan": plan,
        "plan_status": "pending",
        "agents_required": plan.get("agents_required", []),
        "current_step": "generate_plan",
        "steps_completed": [*(state.get("steps_completed") or []), "generate_plan"],
    }


# ── Node 5: present_plan ─────────────────────────────────────────────────
# Pauses the graph with interrupt() to show the plan to the user.
# The SSE adapter translates this into a plan_preview event.

def present_plan(state: PlannerState) -> dict:
    """Present the plan to the user and wait for approval."""
    plan = state.get("plan", {})

    response = interrupt({
        "type": "plan_preview",
        "plan": plan,
        "options": ["approve", "modify", "cancel"],
    })

    decision = response.get("decision", "cancel")

    if decision == "cancel":
        return {
            "plan_status": "cancelled",
            "response_text": "Plan cancelled.",
        }
    elif decision == "modify":
        return {
            "plan_status": "needs_plan",
            "user_message": response.get("modifications", state.get("user_message", "")),
        }

    return {
        "plan_status": "approved",
        "current_step": "present_plan",
        "steps_completed": [*(state.get("steps_completed") or []), "present_plan"],
    }


# ── Node 6: dispatch_agents ──────────────────────────────────────────────
# Executes the approved plan by invoking specialist agents.
# Steps marked as "parallel" are grouped and executed concurrently
# via ThreadPoolExecutor. Sequential/interrupt steps run one-by-one.

def _get_agent_graphs() -> dict:
    """Lazy import of agent subgraphs to avoid circular imports."""
    from app.graphs.agents.jd_agent import jd_agent_graph
    from app.graphs.agents.resume_agent import resume_agent_graph
    from app.graphs.agents.matching_agent import matching_agent_graph
    from app.graphs.agents.communication_agent import communication_agent_graph
    from app.graphs.agents.scheduling_agent import scheduling_agent_graph
    from app.graphs.agents.pipeline_agent import pipeline_agent_graph
    from app.graphs.agents.job_search_agent import job_search_agent_graph
    from app.graphs.agents.job_match_agent import job_match_agent_graph

    return {
        "jd": jd_agent_graph,
        "resume": resume_agent_graph,
        "matching": matching_agent_graph,
        "communication": communication_agent_graph,
        "scheduling": scheduling_agent_graph,
        "pipeline": pipeline_agent_graph,
        "job_search": job_search_agent_graph,
        "job_match": job_match_agent_graph,
    }


def _invoke_agent(agent_graph, agent_input: dict) -> dict:
    """Invoke a single agent graph, returning its output or error."""
    try:
        result = agent_graph.invoke(agent_input)
        return result.get("agent_output", {})
    except Exception as e:
        return {"error": str(e)}


def _group_steps(steps: list[dict]) -> list[list[dict]]:
    """Group plan steps into execution batches.

    Consecutive steps with mode="parallel" are grouped into the same
    batch and run concurrently.  Sequential/interrupt steps each form
    their own single-item batch.

    Example:
        steps = [
            {mode: "sequential"},  # batch 0 (alone)
            {mode: "parallel"},    # batch 1 (together)
            {mode: "parallel"},    # batch 1 (together)
            {mode: "sequential"},  # batch 2 (alone)
        ]
    """
    batches: list[list[dict]] = []
    current_parallel: list[dict] = []

    for step in steps:
        mode = step.get("mode", "sequential")
        if mode == "parallel":
            current_parallel.append(step)
        else:
            # Flush any accumulated parallel batch
            if current_parallel:
                batches.append(current_parallel)
                current_parallel = []
            batches.append([step])

    if current_parallel:
        batches.append(current_parallel)

    return batches


def dispatch_agents(state: PlannerState) -> dict:
    """Dispatch specialist agents according to the approved plan.

    Parallel steps are run concurrently using a ThreadPoolExecutor.
    Sequential steps run one after another. Each batch can read
    previous_results from earlier batches.
    """
    import concurrent.futures

    cfg = state["cfg"]
    plan = state.get("plan", {})
    steps = plan.get("steps", [])
    agent_graphs = _get_agent_graphs()
    agent_results = state.get("agent_results") or {}

    batches = _group_steps(steps)

    for batch in batches:
        if len(batch) == 1:
            # Single step — run directly (no thread overhead)
            step = batch[0]
            agent_name = step.get("agent", "")
            agent_graph = agent_graphs.get(agent_name)
            if not agent_graph:
                log.warning("Unknown agent: %s, skipping", agent_name)
                continue

            agent_input = {
                "cfg": cfg,
                "agent_input": {**step, "previous_results": agent_results},
                "session_id": state.get("session_id", ""),
                "user_id": state.get("user_id", ""),
            }
            result = _invoke_agent(agent_graph, agent_input)
            agent_results[agent_name] = result
            if isinstance(result, dict) and result.get("error"):
                log.error("Agent %s failed: %s", agent_name, result["error"])
        else:
            # Parallel batch — fan out with ThreadPoolExecutor
            futures: dict[str, concurrent.futures.Future] = {}
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(batch),
                thread_name_prefix="agent",
            ) as executor:
                for step in batch:
                    agent_name = step.get("agent", "")
                    agent_graph = agent_graphs.get(agent_name)
                    if not agent_graph:
                        log.warning("Unknown agent: %s, skipping", agent_name)
                        continue
                    agent_input = {
                        "cfg": cfg,
                        "agent_input": {**step, "previous_results": agent_results},
                        "session_id": state.get("session_id", ""),
                        "user_id": state.get("user_id", ""),
                    }
                    futures[agent_name] = executor.submit(
                        _invoke_agent, agent_graph, agent_input,
                    )

            # Collect results after all futures complete
            for agent_name, future in futures.items():
                result = future.result()
                agent_results[agent_name] = result
                if isinstance(result, dict) and result.get("error"):
                    log.error("Agent %s failed: %s", agent_name, result["error"])

    return {
        "agent_results": agent_results,
        "current_step": "dispatch_agents",
        "steps_completed": [*(state.get("steps_completed") or []), "dispatch_agents"],
    }


# ── Node 7: resume_workflow ──────────────────────────────────────────────
# Resumes a paused v1.x workflow. Bridge for migration period.

def resume_workflow(state: PlannerState) -> dict:
    """Resume a paused workflow with the user's response."""
    plan = state.get("plan", {})
    paused_wf = plan.get("_paused_workflow", {})

    if not paused_wf:
        return {
            "response_text": "No paused workflow to resume.",
            "error": "No paused workflow found",
        }

    return {
        "response_text": f"Resuming workflow: {paused_wf.get('type', 'unknown')}",
        "agent_results": {"resumed_workflow": paused_wf},
        "current_step": "resume_workflow",
        "steps_completed": [*(state.get("steps_completed") or []), "resume_workflow"],
    }


# ── Node 8: finalize ─────────────────────────────────────────────────────
# Aggregates all agent results into a final response.

def finalize(state: PlannerState) -> dict:
    """Aggregate results and return the final response."""
    agent_results = state.get("agent_results", {})

    if state.get("response_text"):
        response = state["response_text"]
    elif agent_results:
        parts = []
        for agent_name, result in agent_results.items():
            if isinstance(result, dict) and result.get("error"):
                parts.append(f"- {agent_name}: Error — {result['error']}")
            elif isinstance(result, dict):
                parts.append(f"- {agent_name}: Done")
            else:
                parts.append(f"- {agent_name}: {result}")
        response = "Plan completed. Results:\n" + "\n".join(parts)
    else:
        response = "Task completed."

    return {
        "response_text": response,
        "current_step": "finalize",
        "steps_completed": [*(state.get("steps_completed") or []), "finalize"],
    }


# ── Routing logic ────────────────────────────────────────────────────────

def _route_after_check_paused(state: PlannerState) -> str:
    if state.get("plan_status") == "resuming":
        return "resume_workflow"
    return "classify_intent"


def _route_after_classify(state: PlannerState) -> str:
    status = state.get("plan_status", "chat")
    if status == "chat":
        return "route_to_chat"
    elif status == "needs_plan":
        return "generate_plan"
    else:
        # Direct workflow trigger or specific workflow type
        return "dispatch_agents"


def _route_after_present_plan(state: PlannerState) -> str:
    status = state.get("plan_status", "")
    if status == "approved":
        return "dispatch_agents"
    elif status == "needs_plan":
        return "generate_plan"
    return "finalize"


# ── Graph assembly ───────────────────────────────────────────────────────

def build_supervisor_graph() -> StateGraph:
    """Construct the Supervisor graph.

    Flow:
        check_paused ──┬──▶ classify_intent ──┬──▶ route_to_chat ──▶ finalize
                       │                      ├──▶ generate_plan ──▶ present_plan ──┬──▶ dispatch_agents ──▶ finalize
                       │                      │                                    └──▶ finalize (cancel)
                       │                      └──▶ dispatch_agents ──▶ finalize (direct workflow)
                       └──▶ resume_workflow ──▶ finalize
    """
    graph = StateGraph(PlannerState)

    graph.add_node("check_paused", check_paused)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("route_to_chat", route_to_chat)
    graph.add_node("generate_plan", generate_plan)
    graph.add_node("present_plan", present_plan)
    graph.add_node("dispatch_agents", dispatch_agents)
    graph.add_node("resume_workflow", resume_workflow)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("check_paused")

    graph.add_conditional_edges("check_paused", _route_after_check_paused)
    graph.add_conditional_edges("classify_intent", _route_after_classify)

    graph.add_edge("route_to_chat", "finalize")
    graph.add_edge("generate_plan", "present_plan")
    graph.add_conditional_edges("present_plan", _route_after_present_plan)
    graph.add_edge("dispatch_agents", "finalize")
    graph.add_edge("resume_workflow", "finalize")
    graph.add_edge("finalize", END)

    return graph


# Pre-built compiled graph
supervisor_graph = build_supervisor_graph().compile()
