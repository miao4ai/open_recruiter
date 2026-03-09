"""Chat Graph — LangGraph StateGraph for single-turn chat.

Replaces the inline chat logic in routes/agent.py with a composable graph:

    ┌──────────┐   ┌─────────────┐   ┌──────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────┐
    │  build   │──▶│ input_guard │──▶│ call_llm │──▶│parse_response│──▶│ output_guard │──▶│ process  │
    │ context  │   │ (guardrail) │   │(streaming)│  │              │   │ (guardrail)  │   │ action   │
    └──────────┘   └─────────────┘   └──────────┘   └──────────────┘   └──────────────┘   └────┬─────┘
                                                                                               │
                                                                                        ┌──────▼─────┐
                                                                                        │  finalize  │
                                                                                        └────────────┘

Nodes:
  1. build_context    — Loads conversation history from DB, builds RAG context
                        with candidate/job data, assembles the system prompt.
  2. input_guard      — Validates user input: prompt injection detection (BLOCKED),
                        PII scan (WARNING), length limits (BLOCKED).
                        If blocked → short-circuits to finalize (skips LLM).
  3. call_llm         — Calls llm.chat_json() with the system prompt and
                        conversation history. Produces the raw LLM response.
  4. parse_response   — Extracts message, action, and context_hint from the
                        LLM JSON response. Includes regex fallback for
                        malformed JSON and keyword-based action detection.
  5. output_guard     — Validates LLM output: content safety (BLOCKED),
                        output length (WARNING), hallucination check (WARNING).
                        If blocked → replaces response and short-circuits to finalize.
  6. process_action   — If the LLM detected an actionable intent (compose_email,
                        upload_resume, etc.), prepares the action payload.
  7. finalize         — Saves assistant message to DB, returns final response.

Design notes:
  - This graph is synchronous (no interrupt). It completes in a single pass.
  - The streaming variant will be handled at the SSE adapter layer — the
    adapter calls llm.chat_stream() and collects tokens, then feeds the
    accumulated text through parse_response → process_action → finalize.
  - Guardrails use conditional edges to skip downstream nodes when input/output
    is blocked, avoiding unnecessary LLM calls or action processing.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime

from langgraph.graph import END, StateGraph

from app import database as db
from app.graphs.state import ChatState
from app.llm import chat, chat_json
from app.prompts import CHAT_SYSTEM_WITH_ACTIONS

# Job seeker action whitelist — only these actions are allowed for seekers
_SEEKER_ALLOWED_ACTIONS = {"search_jobs", "analyze_job_match", "save_job"}

log = logging.getLogger(__name__)

# Regex to strip trailing ```json {...} ``` blocks the LLM sometimes embeds
_TRAILING_JSON_BLOCK_RE = re.compile(
    r'\s*```(?:json)?\s*\{[^`]*"message"\s*:[^`]*\}\s*```\s*$',
    re.DOTALL,
)


# ── Node 1: build_context ────────────────────────────────────────────────
# Assembles the LLM system prompt with role-appropriate context:
# - Recruiter: pipeline data (candidates, jobs, activity)
# - Job Seeker: profile, saved jobs, recent search results
# Also loads conversation history for multi-turn context.

def build_context(state: ChatState) -> dict:
    """Load conversation history and build the system prompt with RAG context."""
    user_id = state.get("user_id", "")
    session_id = state.get("session_id", "")
    user_message = state.get("user_message", "")
    user_role = state.get("user_role", "recruiter")

    # Load conversation history
    history = db.list_chat_messages(user_id, limit=20, session_id=session_id)
    conversation_history = [
        {"role": m["role"], "content": m["content"]} for m in history
    ]
    conversation_history.append({"role": "user", "content": user_message})

    # Build role-specific system prompt
    if user_role == "job_seeker":
        from app.prompts import CHAT_SYSTEM_JOB_SEEKER, ENCOURAGEMENT_ADDENDUM
        context = _build_job_seeker_context(user_id, session_id=session_id)
        rag_context = CHAT_SYSTEM_JOB_SEEKER.format(context=context)
        if state.get("encouragement_mode"):
            rag_context += ENCOURAGEMENT_ADDENDUM
    else:
        context = _build_pipeline_context(user_id, current_message=user_message)
        rag_context = CHAT_SYSTEM_WITH_ACTIONS.format(context=context)

    return {
        "conversation_history": conversation_history,
        "rag_context": rag_context,
        "current_step": "build_context",
        "steps_completed": [*(state.get("steps_completed") or []), "build_context"],
    }


# ── Node 2: input_guard ──────────────────────────────────────────────────
# Validates user input before it reaches the LLM:
#   - Prompt injection detection (BLOCKED)
#   - PII scan (WARNING — logged but not blocked)
#   - Message length limits (BLOCKED)

def input_guard(state: ChatState) -> dict:
    """Validate user input via InputValidator guardrail."""
    from app.guardrails.input_validator import InputValidator
    from app.guardrails.base import GuardrailSeverity, log_guardrail_result

    user_message = state.get("user_message", "")
    session_id = state.get("session_id", "")
    user_id = state.get("user_id", "")

    validator = InputValidator()
    result = validator.check(text=user_message)

    log_guardrail_result(result, session_id=session_id, user_id=user_id)

    if result.blocked:
        return {
            "response_text": result.message,
            "error": f"input_guard: {result.check_name}",
            "current_step": "input_guard",
            "steps_completed": [*(state.get("steps_completed") or []), "input_guard"],
        }

    if result.severity == GuardrailSeverity.WARNING:
        log.info("Input guard warning: %s — %s", result.check_name, result.message)

    return {
        "current_step": "input_guard",
        "steps_completed": [*(state.get("steps_completed") or []), "input_guard"],
    }


# ── Node 3: call_llm ─────────────────────────────────────────────────────
# Calls the LLM with the assembled system prompt and conversation history.
# Uses chat_json() for structured output; falls back to plain chat() if
# JSON parsing fails.

def call_llm(state: ChatState) -> dict:
    """Call the LLM and get the raw response."""
    cfg = state["cfg"]
    system_prompt = state.get("rag_context", "")
    messages = state.get("conversation_history", [])

    try:
        result = chat_json(cfg, system=system_prompt, messages=messages)
    except Exception:
        log.warning("chat_json failed, falling back to plain text chat")
        try:
            raw_text = chat(cfg, system=system_prompt, messages=messages)
            result = raw_text
        except Exception as e:
            log.error("Chat LLM call failed: %s", e)
            return {
                "llm_response": "",
                "error": f"LLM call failed: {e}",
            }

    # Normalise to string for parse_response
    if isinstance(result, dict):
        llm_response = json.dumps(result)
    elif isinstance(result, str):
        llm_response = result
    else:
        llm_response = str(result)

    return {
        "llm_response": llm_response,
        "current_step": "call_llm",
        "steps_completed": [*(state.get("steps_completed") or []), "call_llm"],
    }


# ── Node 4: parse_response ───────────────────────────────────────────────
# Extracts the structured fields from the LLM's JSON response:
#   - message: the conversational reply
#   - action: optional actionable intent (compose_email, upload_resume, etc.)
#   - context_hint: optional UI hint for the right-side panel
#
# Includes multiple fallback strategies for malformed JSON.

def parse_response(state: ChatState) -> dict:
    """Parse the LLM response into message, action, and context_hint."""
    raw = state.get("llm_response", "")
    user_message = state.get("user_message", "")

    reply_text = ""
    action_data = None

    if not raw:
        reply_text = state.get("error", "I encountered an error processing your message.")
    else:
        # Try JSON parse
        try:
            text = raw.strip()
            # Strip markdown code fences
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            result = json.loads(text)
            if isinstance(result, dict):
                reply_text = result.get("message", "")
                action_data = result.get("action")
            else:
                reply_text = str(result)
        except Exception:
            # Regex fallback — extract "message" field
            m = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
            if m:
                reply_text = (
                    m.group(1)
                    .replace("\\n", "\n")
                    .replace('\\"', '"')
                    .replace("\\\\", "\\")
                )
            else:
                reply_text = raw.strip()

    # Strip trailing embedded JSON blocks
    if reply_text and "```" in reply_text and '"message"' in reply_text:
        reply_text = _TRAILING_JSON_BLOCK_RE.sub("", reply_text).rstrip()

    # Keyword fallback for action detection (weak local models)
    if not action_data:
        action_data = _detect_action_from_keywords(user_message)

    return {
        "response_text": reply_text,
        "parsed_action": action_data or {},
        "current_step": "parse_response",
        "steps_completed": [*(state.get("steps_completed") or []), "parse_response"],
    }


# ── Node 5: output_guard ─────────────────────────────────────────────────
# Validates LLM output before it reaches the user:
#   - Content safety — discriminatory language (BLOCKED)
#   - Output length — runaway generation (WARNING)
#   - Hallucination — fabricated candidate/job references (WARNING)

def output_guard(state: ChatState) -> dict:
    """Validate LLM output via OutputValidator guardrail."""
    from app.guardrails.output_validator import OutputValidator
    from app.guardrails.base import GuardrailSeverity, log_guardrail_result

    response_text = state.get("response_text", "")
    session_id = state.get("session_id", "")
    user_id = state.get("user_id", "")

    # Gather known entities for hallucination check
    known_candidates = []
    known_job_ids = []
    try:
        candidates = db.list_candidates() or []
        known_candidates = [c.get("name", "") for c in candidates if c.get("name")]
        jobs = db.list_jobs() or []
        known_job_ids = [j.get("id", "") for j in jobs if j.get("id")]
    except Exception:
        pass  # Don't let DB errors break the guard

    validator = OutputValidator()
    result = validator.check(
        text=response_text,
        known_candidates=known_candidates,
        known_job_ids=known_job_ids,
    )

    log_guardrail_result(result, session_id=session_id, user_id=user_id)

    if result.blocked:
        return {
            "response_text": "I'm sorry, I can't provide that response. Please rephrase your request.",
            "error": f"output_guard: {result.check_name}",
            "current_step": "output_guard",
            "steps_completed": [*(state.get("steps_completed") or []), "output_guard"],
        }

    if result.severity == GuardrailSeverity.WARNING:
        log.info("Output guard warning: %s — %s", result.check_name, result.message)

    return {
        "current_step": "output_guard",
        "steps_completed": [*(state.get("steps_completed") or []), "output_guard"],
    }


# ── Node 6: process_action ───────────────────────────────────────────────
# If the LLM detected an actionable intent, prepares the action payload
# for the frontend. This is where compose_email triggers the Communication
# Agent, upload_resume triggers a UI card, etc.

def process_action(state: ChatState) -> dict:
    """Process any detected action from the LLM response."""
    action = state.get("parsed_action", {})
    user_role = state.get("user_role", "recruiter")

    # No action — nothing to do
    if not action:
        return {
            "current_step": "process_action",
            "steps_completed": [*(state.get("steps_completed") or []), "process_action"],
        }

    # Job seeker whitelist: block recruiter-only actions
    if user_role == "job_seeker" and action.get("type") not in _SEEKER_ALLOWED_ACTIONS:
        return {
            "parsed_action": {},
            "current_step": "process_action",
            "steps_completed": [*(state.get("steps_completed") or []), "process_action"],
        }

    # Action is present — it will be included in the final output
    # for the SSE adapter / frontend to handle.
    # In v2.0, complex actions (compose_email, schedule_interview) will
    # be dispatched to the Supervisor for multi-agent execution.
    return {
        "parsed_action": action,
        "current_step": "process_action",
        "steps_completed": [*(state.get("steps_completed") or []), "process_action"],
    }


# ── Node 7: finalize ─────────────────────────────────────────────────────
# Saves the assistant message to the database and assembles the final
# response dict that the SSE adapter will emit.

def finalize(state: ChatState) -> dict:
    """Save assistant message to DB and return final response."""
    user_id = state.get("user_id", "")
    session_id = state.get("session_id", "")
    reply_text = state.get("response_text", "")
    action = state.get("parsed_action", {})

    # Save assistant message
    msg_id = uuid.uuid4().hex[:8]
    action_json_str = json.dumps(action) if action else ""
    db.insert_chat_message({
        "id": msg_id,
        "user_id": user_id,
        "session_id": session_id,
        "role": "assistant",
        "content": reply_text,
        "action_json": action_json_str,
        "action_status": "pending" if action else "",
        "created_at": datetime.now().isoformat(),
    })

    return {
        "response_text": reply_text,
        "current_step": "finalize",
        "steps_completed": [*(state.get("steps_completed") or []), "finalize"],
    }


# ── Graph assembly ───────────────────────────────────────────────────────

def _route_after_input_guard(state: ChatState) -> str:
    """Skip LLM call if input was blocked by guardrails."""
    if state.get("error", "").startswith("input_guard:"):
        return "finalize"
    return "call_llm"


def _route_after_output_guard(state: ChatState) -> str:
    """Skip action processing if output was blocked by guardrails."""
    if state.get("error", "").startswith("output_guard:"):
        return "finalize"
    return "process_action"


def build_chat_graph() -> StateGraph:
    """Construct the Chat Graph.

    Flow:
        build_context → input_guard ─┬─▶ call_llm → parse_response → output_guard ─┬─▶ process_action → finalize → END
                                     └─▶ finalize (blocked)                         └─▶ finalize (blocked)
    """
    graph = StateGraph(ChatState)

    graph.add_node("build_context", build_context)
    graph.add_node("input_guard", input_guard)
    graph.add_node("call_llm", call_llm)
    graph.add_node("parse_response", parse_response)
    graph.add_node("output_guard", output_guard)
    graph.add_node("process_action", process_action)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("build_context")

    graph.add_edge("build_context", "input_guard")
    graph.add_conditional_edges("input_guard", _route_after_input_guard)
    graph.add_edge("call_llm", "parse_response")
    graph.add_edge("parse_response", "output_guard")
    graph.add_conditional_edges("output_guard", _route_after_output_guard)
    graph.add_edge("process_action", "finalize")
    graph.add_edge("finalize", END)

    return graph


# Pre-built compiled graph
chat_graph = build_chat_graph().compile()


# ── Helpers ───────────────────────────────────────────────────────────────

def _build_pipeline_context(user_id: str, current_message: str = "") -> str:
    """Build a text summary of the recruiter's pipeline for the system prompt."""
    parts: list[str] = []

    # Jobs summary
    jobs = db.list_jobs()
    if jobs:
        parts.append(f"## Active Jobs ({len(jobs)})")
        for j in jobs[:10]:
            skills = ", ".join(j.get("required_skills", [])[:5])
            parts.append(
                f"- [{j['id']}] {j['title']} at {j['company']}"
                f" (skills: {skills}, candidates: {j.get('candidate_count', 0)})"
            )

    # Candidates summary
    candidates = db.list_candidates()
    if candidates:
        parts.append(f"\n## Candidates ({len(candidates)})")
        for c in candidates[:15]:
            skills = c.get("skills", [])
            skills_str = ", ".join(skills[:5]) if isinstance(skills, list) else str(skills)
            parts.append(
                f"- [{c['id']}] {c['name']} — {c.get('current_title', 'N/A')}"
                f" at {c.get('current_company', 'N/A')}"
                f" | status: {c.get('status', 'new')}"
                f" | skills: {skills_str}"
                f" | email: {c.get('email', '')}"
                + (f" | job_id: {c['job_id']}" if c.get("job_id") else "")
            )

    # Pipeline stats
    if candidates:
        from collections import Counter
        status_counts = Counter(c.get("status", "new") for c in candidates)
        parts.append("\n## Pipeline Status")
        for status, count in sorted(status_counts.items()):
            parts.append(f"- {status}: {count}")

    return "\n".join(parts) if parts else "No data in the system yet."


def _detect_action_from_keywords(message: str) -> dict | None:
    """Detect common user intents via keywords when the LLM fails to
    return a structured action."""
    msg = message.lower().strip()
    if re.search(r"upload.*(resume|cv|简历)|上传.*(简历|cv)|添加候选人|add.*candidate", msg):
        return {"type": "upload_resume", "job_id": "", "job_title": ""}
    if re.search(r"upload.*(jd|job\s*desc)|上传.*(jd|职位|岗位)|添加职位|add.*(job|position)", msg):
        return {"type": "upload_jd"}
    return None


def _build_job_seeker_context(user_id: str, session_id: str | None = None) -> str:
    """Build context from the job seeker's profile, saved jobs, and recent search results."""
    parts: list[str] = []

    # Profile / resume
    profile = db.get_job_seeker_profile_by_user(user_id)
    if profile and profile.get("name"):
        parts.append("## Your Profile")
        parts.append(f"- Name: {profile['name']}")
        if profile.get("email"):
            parts.append(f"- Email: {profile['email']}")
        if profile.get("current_title"):
            parts.append(f"- Current Title: {profile['current_title']}")
        if profile.get("current_company"):
            parts.append(f"- Current Company: {profile['current_company']}")
        if profile.get("experience_years"):
            parts.append(f"- Experience: {profile['experience_years']} years")
        if profile.get("location"):
            parts.append(f"- Location: {profile['location']}")
        skills = profile.get("skills", [])
        if skills:
            parts.append(f"- Skills: {', '.join(skills)}")
        if profile.get("resume_summary"):
            parts.append(f"\n## Resume Summary\n{profile['resume_summary']}")
        if profile.get("raw_resume_text"):
            parts.append(f"\n## Resume Content (excerpt)\n{profile['raw_resume_text'][:2000]}")
    else:
        parts.append("## Profile: Not yet created (user has not uploaded a resume)")

    # Saved jobs
    saved_jobs = db.list_seeker_jobs(user_id)
    if saved_jobs:
        parts.append(f"\n## Saved Jobs ({len(saved_jobs)})")
        for j in saved_jobs[:10]:
            line = f"- {j['title']} at {j['company']}"
            if j.get("location"):
                line += f" ({j['location']})"
            if j.get("required_skills"):
                line += f" — skills: {', '.join(j['required_skills'][:5])}"
            parts.append(line)
    else:
        parts.append("\n## Saved Jobs: None")

    # Recent search results — inject so LLM can resolve "第N个" references
    if session_id:
        import json as _json
        recent_msgs = db.list_chat_messages(user_id, limit=10, session_id=session_id)
        for msg in reversed(recent_msgs):
            if msg.get("action_json"):
                try:
                    action = _json.loads(msg["action_json"]) if isinstance(msg["action_json"], str) else msg["action_json"]
                    if isinstance(action, dict) and action.get("type") == "job_search_results":
                        jobs = action.get("jobs", [])
                        if jobs:
                            parts.append(f"\n## Recent Search Results ({len(jobs)} jobs from web)")
                            for j in jobs:
                                idx = j.get("index", 0)
                                line = f"{idx}. {j.get('title', '')} at {j.get('company', 'Unknown')}"
                                if j.get("location"):
                                    line += f" ({j['location']})"
                                if j.get("source"):
                                    line += f" — {j['source']}"
                                parts.append(line)
                            break
                except (_json.JSONDecodeError, TypeError):
                    pass

    return "\n".join(parts)
