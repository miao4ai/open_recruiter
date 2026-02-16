"""Agent route — SSE streaming for natural language instructions + chat."""

import asyncio
import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app import database as db
from app.auth import get_current_user, require_recruiter
from app.models import AgentRequest, ChatRequest

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/run")
async def run_agent(req: AgentRequest, _user: dict = Depends(require_recruiter)):
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

    # Build context and system prompt based on user role
    user_role = current_user.get("role", "recruiter")
    if user_role == "job_seeker":
        from app.prompts import CHAT_SYSTEM_JOB_SEEKER
        context = _build_job_seeker_context(user_id)
        system_prompt = CHAT_SYSTEM_JOB_SEEKER.format(context=context)
    else:
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

    # If there's a mark_candidates_replied action, update candidate statuses
    if action_data and isinstance(action_data, dict) and action_data.get("type") == "mark_candidates_replied":
        try:
            candidates_to_update = action_data.get("candidates", [])
            updated_names = []
            now = datetime.now().isoformat()

            for c in candidates_to_update:
                cid = c.get("candidate_id", "")
                cname = c.get("candidate_name", "")
                if cid:
                    db.update_candidate(cid, {
                        "status": "replied",
                        "updated_at": now,
                    })
                    updated_names.append(cname)

            if updated_names:
                names_str = "、".join(updated_names)
                response["reply"] = f"Done! I've updated **{names_str}** to the **replied** stage in the pipeline."
                response["action"] = {
                    "type": "mark_candidates_replied",
                    "updated": updated_names,
                }

                db.insert_activity({
                    "id": uuid.uuid4().hex[:8],
                    "user_id": user_id,
                    "activity_type": "candidates_marked_replied",
                    "description": f"Marked {names_str} as replied",
                    "metadata_json": json.dumps({
                        "candidates": candidates_to_update,
                    }),
                    "created_at": now,
                })
            else:
                response["reply"] = "I couldn't find the candidates to update. Please check the names and try again."
        except Exception as e:
            log.error("Failed to mark candidates as replied: %s", e)
            response["reply"] = f"Sorry, I encountered an error while updating: {e}"

    # If there's an upload_resume action, pass it through to the frontend
    if action_data and isinstance(action_data, dict) and action_data.get("type") == "upload_resume":
        response["action"] = {
            "type": "upload_resume",
            "job_id": action_data.get("job_id", ""),
            "job_title": action_data.get("job_title", ""),
        }

    # If there's an upload_jd action, pass it through to the frontend
    if action_data and isinstance(action_data, dict) and action_data.get("type") == "upload_jd":
        response["action"] = {
            "type": "upload_jd",
        }

    # Save assistant reply with action data for persistence
    assistant_msg_id = uuid.uuid4().hex[:8]
    action_json_str = ""
    action_status_str = ""
    if response.get("action"):
        action_json_str = json.dumps(response["action"])
        action_status_str = "pending"
    db.insert_chat_message({
        "id": assistant_msg_id,
        "user_id": user_id,
        "session_id": session_id,
        "role": "assistant",
        "content": response["reply"],
        "action_json": action_json_str,
        "action_status": action_status_str,
        "created_at": datetime.now().isoformat(),
    })
    response["message_id"] = assistant_msg_id

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


@router.patch("/chat/messages/{message_id}")
async def update_chat_message(message_id: str, req: dict, _user: dict = Depends(get_current_user)):
    """Update a chat message's action_status."""
    updates = {}
    if "action_status" in req:
        updates["action_status"] = req["action_status"]
    if not updates:
        return {"status": "no_changes"}
    db.update_chat_message(message_id, updates)
    return {"status": "updated"}


@router.post("/chat/messages")
async def save_chat_message(req: dict, current_user: dict = Depends(get_current_user)):
    """Save a follow-up message (e.g. congratulatory message after email send)."""
    msg_id = uuid.uuid4().hex[:8]
    db.insert_chat_message({
        "id": msg_id,
        "user_id": current_user["id"],
        "session_id": req.get("session_id", ""),
        "role": req.get("role", "assistant"),
        "content": req.get("content", ""),
        "created_at": datetime.now().isoformat(),
    })
    return {"id": msg_id, "status": "saved"}


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

    # Contacted candidates (awaiting reply)
    contacted = [c for c in (candidates or []) if c.get("status") == "contacted"]
    if contacted:
        parts.append(f"\n## Contacted Candidates Awaiting Reply ({len(contacted)})")
        for c in contacted:
            parts.append(
                f"- {c['name']} (ID: {c['id']}, email: {c.get('email') or 'N/A'})"
            )

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


def _build_job_seeker_context(user_id: str) -> str:
    """Build context from the job seeker's profile and saved jobs."""
    parts = []

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
            # Include first 2000 chars of raw resume for deeper context
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

    return "\n".join(parts)
