"""Agent route — SSE streaming for natural language instructions + chat."""

import asyncio
import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app import database as db
from app.auth import get_current_user
from app.models import AgentRequest, ChatRequest

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/run")
async def run_agent(req: AgentRequest, _user: dict = Depends(get_current_user)):
    """Execute a natural language instruction via the orchestrator.

    Returns an SSE stream with plan/progress/result events.
    Phase 2 will connect this to the real orchestrator + agents.
    """
    async def event_generator():
        # Phase 1: mock SSE stream
        yield {
            "event": "plan",
            "data": json.dumps({
                "goal": f"Execute: {req.instruction}",
                "tasks": [
                    {"id": 1, "description": "Analyzing your request...", "type": "planning"},
                    {"id": 2, "description": "Executing tasks...", "type": "execution"},
                ],
            }),
        }

        await asyncio.sleep(0.5)

        yield {
            "event": "progress",
            "data": json.dumps({
                "task_id": 1,
                "status": "done",
                "message": "Request analyzed.",
            }),
        }

        await asyncio.sleep(0.5)

        yield {
            "event": "progress",
            "data": json.dumps({
                "task_id": 2,
                "status": "done",
                "message": "Agent execution not yet implemented — coming in Phase 2.",
            }),
        }

        yield {
            "event": "result",
            "data": json.dumps({
                "summary": f"Received your instruction: \"{req.instruction}\". Full agent execution will be available in Phase 2.",
            }),
        }

    return EventSourceResponse(event_generator())


# ── Chat ──────────────────────────────────────────────────────────────────


@router.post("/chat")
async def chat_endpoint(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    """Synchronous chat with the AI recruiting assistant.

    Returns ``{reply, action?, session_id}`` where *action* is present when
    the AI detects an actionable intent (e.g. drafting an email).
    """
    from app.routes.settings import get_config
    from app.llm import chat_json, chat
    from app.prompts import CHAT_SYSTEM_WITH_ACTIONS
    from app.models import Email

    user_id = current_user["id"]
    cfg = get_config()

    has_key = (
        (cfg.llm_provider == "anthropic" and cfg.anthropic_api_key)
        or (cfg.llm_provider == "openai" and cfg.openai_api_key)
    )
    if not has_key:
        return {"reply": "Please configure an LLM API key in Settings before using the chat assistant."}

    # Ensure a session exists
    session_id = req.session_id
    if not session_id:
        # Create a new session automatically
        session_id = uuid.uuid4().hex[:8]
        now = datetime.now().isoformat()
        db.insert_chat_session({
            "id": session_id,
            "user_id": user_id,
            "title": req.message[:50] or "New Chat",
            "created_at": now,
            "updated_at": now,
        })
    else:
        # Update session timestamp
        db.update_chat_session(session_id, {"updated_at": datetime.now().isoformat()})

    # Build context from database
    context = _build_chat_context()
    system_prompt = CHAT_SYSTEM_WITH_ACTIONS.format(context=context)

    # Load conversation history for this session
    history = db.list_chat_messages(user_id, limit=20, session_id=session_id)

    # Save user message
    db.insert_chat_message({
        "id": uuid.uuid4().hex[:8],
        "user_id": user_id,
        "session_id": session_id,
        "role": "user",
        "content": req.message,
        "created_at": datetime.now().isoformat(),
    })

    # Build messages array for LLM
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": req.message})

    # Call LLM with structured JSON output
    reply_text = ""
    action_data = None
    try:
        result = chat_json(cfg, system=system_prompt, messages=messages)
        reply_text = result.get("message", "") if isinstance(result, dict) else str(result)
        action_data = result.get("action") if isinstance(result, dict) else None
    except Exception:
        # Fallback to plain text chat if JSON parsing fails
        log.warning("chat_json failed, falling back to plain text chat")
        try:
            reply_text = chat(cfg, system=system_prompt, messages=messages)
        except Exception as e:
            log.error("Chat LLM call failed: %s", e)
            reply_text = f"I encountered an error: {e!s}. Please check your LLM configuration in Settings."

    # If there's a compose_email action, delegate to communication agent for rich drafting
    response: dict = {"reply": reply_text, "session_id": session_id}
    if action_data and isinstance(action_data, dict) and action_data.get("type") == "compose_email":
        try:
            from app.agents.communication import draft_email as agent_draft

            candidate_id = action_data.get("candidate_id", "")
            candidate_name = action_data.get("candidate_name", "")
            to_email = action_data.get("to_email", "")
            email_type = action_data.get("email_type", "outreach")
            job_id = action_data.get("job_id", "")
            instructions = action_data.get("instructions", "")

            # Phase 2: Communication agent generates the email with rich context
            draft = agent_draft(
                cfg,
                candidate_id=candidate_id,
                job_id=job_id,
                email_type=email_type,
                instructions=instructions,
            )

            if draft.get("error"):
                log.warning("Communication agent error: %s", draft["error"])

            email = Email(
                candidate_id=candidate_id,
                candidate_name=candidate_name,
                to_email=to_email,
                subject=draft.get("subject", ""),
                body=draft.get("body", ""),
                email_type=email_type,
            )
            db.insert_email(email.model_dump())

            # Log activity
            db.insert_activity({
                "id": uuid.uuid4().hex[:8],
                "user_id": user_id,
                "activity_type": "email_drafted",
                "description": f"Drafted {email_type} email to {candidate_name}",
                "metadata_json": json.dumps({
                    "email_id": email.id,
                    "candidate_id": candidate_id,
                    "candidate_name": candidate_name,
                    "email_type": email_type,
                }),
                "created_at": datetime.now().isoformat(),
            })

            response["reply"] = f"I've drafted a personalized {email_type} email for {candidate_name}. Review it below and send when ready!"
            response["action"] = {
                "type": "compose_email",
                "email": email.model_dump(),
            }
        except Exception as e:
            log.error("Failed to create email draft from chat action: %s", e)

    # If there's a match_candidate action, run the planning agent
    if action_data and isinstance(action_data, dict) and action_data.get("type") == "match_candidate":
        try:
            from app.agents.planning import match_candidate_to_jobs

            candidate_id = action_data.get("candidate_id", "")
            candidate_name = action_data.get("candidate_name", "")

            result = match_candidate_to_jobs(cfg, candidate_id)

            if result.get("error") and not result.get("rankings"):
                response["reply"] = f"Sorry, I couldn't run the matching: {result['error']}"
            else:
                # Format results into a readable reply
                rankings = result.get("rankings", [])
                summary = result.get("summary", "")
                parts = [f"Here are the job matching results for **{candidate_name}**:\n"]

                for i, r in enumerate(rankings[:5], 1):
                    score_pct = int(r.get("score", 0) * 100)
                    title = r.get("title", "Unknown")
                    company = r.get("company", "")
                    one_liner = r.get("one_liner", "")
                    strengths = r.get("strengths", [])
                    gaps = r.get("gaps", [])

                    parts.append(f"**{i}. {title} at {company} — {score_pct}% match**")
                    if one_liner:
                        parts.append(f"   {one_liner}")
                    if strengths:
                        parts.append(f"   Strengths: {', '.join(strengths)}")
                    if gaps:
                        parts.append(f"   Gaps: {', '.join(gaps)}")
                    parts.append("")

                if summary:
                    parts.append(f"**Summary:** {summary}")

                if rankings:
                    top = rankings[0]
                    parts.append(f"\nWould you like me to draft an outreach email to {candidate_name} for the **{top.get('title', '')}** role?")

                response["reply"] = "\n".join(parts)

                # Log activity
                db.insert_activity({
                    "id": uuid.uuid4().hex[:8],
                    "user_id": user_id,
                    "activity_type": "candidate_matched",
                    "description": f"Matched {candidate_name} against {len(rankings)} jobs",
                    "metadata_json": json.dumps({
                        "candidate_id": candidate_id,
                        "candidate_name": candidate_name,
                        "top_job": rankings[0].get("title", "") if rankings else "",
                        "top_score": rankings[0].get("score", 0) if rankings else 0,
                    }),
                    "created_at": datetime.now().isoformat(),
                })
        except Exception as e:
            log.error("Failed to run candidate matching: %s", e)
            response["reply"] = f"Sorry, I encountered an error while matching: {e}"

    # If there's an upload_resume action, pass it through to the frontend
    if action_data and isinstance(action_data, dict) and action_data.get("type") == "upload_resume":
        response["action"] = {
            "type": "upload_resume",
            "job_id": action_data.get("job_id", ""),
            "job_title": action_data.get("job_title", ""),
        }

    # Save assistant reply (text only — action is transient)
    db.insert_chat_message({
        "id": uuid.uuid4().hex[:8],
        "user_id": user_id,
        "session_id": session_id,
        "role": "assistant",
        "content": response["reply"],
        "created_at": datetime.now().isoformat(),
    })

    # Auto-title: update session title from first user message
    session = db.get_chat_session(session_id)
    if session and session["title"] == req.message[:50]:
        # Keep it — it's already set from the first message
        pass

    return response


# ── Chat Sessions ─────────────────────────────────────────────────────────


@router.get("/chat/sessions")
async def list_sessions(current_user: dict = Depends(get_current_user)):
    """List all chat sessions for the current user."""
    return db.list_chat_sessions(current_user["id"])


@router.post("/chat/sessions")
async def create_session(current_user: dict = Depends(get_current_user)):
    """Create a new empty chat session."""
    now = datetime.now().isoformat()
    session = {
        "id": uuid.uuid4().hex[:8],
        "user_id": current_user["id"],
        "title": "New Chat",
        "created_at": now,
        "updated_at": now,
    }
    db.insert_chat_session(session)
    return session


@router.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a chat session and its messages."""
    session = db.get_chat_session(session_id)
    if not session:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete_chat_session(session_id)
    return {"status": "deleted"}


@router.put("/chat/sessions/{session_id}")
async def rename_session(session_id: str, req: dict, current_user: dict = Depends(get_current_user)):
    """Rename a chat session."""
    session = db.get_chat_session(session_id)
    if not session:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")
    title = req.get("title", "").strip()
    if title:
        db.update_chat_session(session_id, {"title": title})
    return db.get_chat_session(session_id)


# ── Chat History ──────────────────────────────────────────────────────────


@router.get("/chat/history")
async def chat_history(
    session_id: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    """Retrieve chat history for a session (or all if no session_id)."""
    return db.list_chat_messages(current_user["id"], limit=50, session_id=session_id)


@router.delete("/chat/history")
async def clear_chat_history(current_user: dict = Depends(get_current_user)):
    """Clear all chat history and sessions for the current user."""
    db.clear_chat_messages(current_user["id"])
    return {"status": "cleared"}


def _build_chat_context() -> str:
    """Build a context string from the database for the chat system prompt."""
    parts = []

    # Jobs summary
    jobs = db.list_jobs()
    if jobs:
        parts.append(f"## Active Jobs ({len(jobs)})")
        for j in jobs[:10]:
            parts.append(
                f"- {j['title']} at {j['company']} "
                f"(ID: {j['id']}, candidates: {j.get('candidate_count', 0)})"
            )
    else:
        parts.append("## Jobs: None")

    # Candidates summary
    candidates = db.list_candidates()
    if candidates:
        parts.append(f"\n## Candidates ({len(candidates)})")
        for c in candidates[:20]:
            parts.append(
                f"- {c['name']} — {c.get('current_title', 'N/A')} "
                f"(ID: {c['id']}, status: {c['status']}, score: {c.get('match_score', 0):.0%}, "
                f"email: {c.get('email') or 'N/A'}, skills: {', '.join(c.get('skills', [])[:5])})"
            )
    else:
        parts.append("\n## Candidates: None")

    # Recent emails
    emails = db.list_emails()
    if emails:
        recent = emails[:10]
        parts.append(f"\n## Recent Emails ({len(emails)} total)")
        for e in recent:
            status = "sent" if e["sent"] else ("approved" if e["approved"] else "draft")
            parts.append(
                f"- [{status}] \"{e['subject']}\" to {e['to_email']} "
                f"({e['email_type']}, candidate: {e.get('candidate_name', 'N/A')})"
            )
    else:
        parts.append("\n## Emails: None")

    return "\n".join(parts)
