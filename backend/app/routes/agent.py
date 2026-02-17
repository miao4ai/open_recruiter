"""Agent route — SSE streaming for natural language instructions + chat."""

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timedelta

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
    log.info("Chat request from user %s with role '%s'", user_id, user_role)
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

    # Process actions using shared helper
    response: dict = {"reply": reply_text, "session_id": session_id, "blocks": [], "suggestions": [], "context_hint": None}

    # GUARD: job seekers must never trigger recruiter-only actions
    if user_role == "job_seeker":
        action_data = None

    response = _process_actions(response, action_data, cfg, user_id, session_id)

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

    # Build smart suggestions if not already set by action handlers
    if not response.get("suggestions") and user_role == "recruiter":
        response["suggestions"] = _build_smart_suggestions(action_data)

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


# ── Streaming Chat ────────────────────────────────────────────────────────


@router.post("/chat/stream")
async def chat_stream_endpoint(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    """SSE streaming chat. Streams text tokens, then sends a final 'done' event
    with the complete structured response (blocks, actions, suggestions).
    """
    from app.routes.settings import get_config
    from app.llm import chat_stream, chat_json, chat
    from app.prompts import CHAT_SYSTEM_WITH_ACTIONS
    from app.models import Email

    user_id = current_user["id"]
    user_role = current_user.get("role", "recruiter")
    cfg = get_config()

    has_key = (
        (cfg.llm_provider == "anthropic" and cfg.anthropic_api_key)
        or (cfg.llm_provider == "openai" and cfg.openai_api_key)
    )
    if not has_key:
        async def err_gen():
            yield {"event": "done", "data": json.dumps({
                "reply": "Please configure an LLM API key in Settings.",
                "session_id": "", "blocks": [], "suggestions": [],
            })}
        return EventSourceResponse(err_gen())

    # Ensure session
    session_id = req.session_id
    if not session_id:
        session_id = uuid.uuid4().hex[:8]
        now = datetime.now().isoformat()
        db.insert_chat_session({
            "id": session_id, "user_id": user_id,
            "title": req.message[:50] or "New Chat",
            "created_at": now, "updated_at": now,
        })
    else:
        db.update_chat_session(session_id, {"updated_at": datetime.now().isoformat()})

    # Build prompt
    if user_role == "job_seeker":
        from app.prompts import CHAT_SYSTEM_JOB_SEEKER
        context = _build_job_seeker_context(user_id)
        system_prompt = CHAT_SYSTEM_JOB_SEEKER.format(context=context)
    else:
        context = _build_chat_context()
        system_prompt = CHAT_SYSTEM_WITH_ACTIONS.format(context=context)

    history = db.list_chat_messages(user_id, limit=20, session_id=session_id)
    db.insert_chat_message({
        "id": uuid.uuid4().hex[:8], "user_id": user_id,
        "session_id": session_id, "role": "user",
        "content": req.message, "created_at": datetime.now().isoformat(),
    })

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": req.message})

    async def event_generator():
        # ── EARLY CHECK: is there a paused workflow awaiting approval? ──
        active_wf = db.get_active_workflow(session_id)
        if active_wf and active_wf["status"] == "paused":
            # Save user message (already saved above), then resume workflow
            from app.agents.orchestrator import resume_workflow

            async for wf_event in resume_workflow(cfg, active_wf, req.message, user_id, session_id):
                if wf_event["event"] == "workflow_step":
                    yield wf_event
                elif wf_event["event"] == "done":
                    # Save assistant message from workflow
                    wf_data = json.loads(wf_event["data"]) if isinstance(wf_event["data"], str) else wf_event["data"]
                    assistant_msg_id = uuid.uuid4().hex[:8]
                    db.insert_chat_message({
                        "id": assistant_msg_id, "user_id": user_id,
                        "session_id": session_id, "role": "assistant",
                        "content": wf_data.get("reply", ""),
                        "created_at": datetime.now().isoformat(),
                    })
                    wf_data["message_id"] = assistant_msg_id
                    yield {"event": "done", "data": json.dumps(wf_data)}
            return  # skip normal LLM path

        # ── NORMAL PATH: stream LLM tokens ──
        loop = asyncio.get_running_loop()
        q: asyncio.Queue[str | Exception | None] = asyncio.Queue()

        def _produce():
            try:
                for chunk in chat_stream(cfg, system=system_prompt, messages=messages, json_mode=True):
                    loop.call_soon_threadsafe(q.put_nowait, chunk)
            except Exception as exc:
                loop.call_soon_threadsafe(q.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(q.put_nowait, None)

        thread = threading.Thread(target=_produce, daemon=True)
        thread.start()

        full_text = ""
        error_occurred = False
        while True:
            item = await q.get()
            if item is None:
                break
            if isinstance(item, Exception):
                log.error("Streaming LLM error: %s", item)
                error_occurred = True
                break
            full_text += item
            yield {"event": "token", "data": json.dumps({"t": item})}

        # --- Post-streaming processing (wrapped in try/except) ---
        try:
            # Parse accumulated JSON
            reply_text = ""
            action_data = None
            if not error_occurred and full_text.strip():
                try:
                    raw = full_text.strip()
                    if raw.startswith("```"):
                        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                        if raw.endswith("```"):
                            raw = raw[:-3]
                        raw = raw.strip()
                    result = json.loads(raw)
                    reply_text = result.get("message", "") if isinstance(result, dict) else str(result)
                    action_data = result.get("action") if isinstance(result, dict) else None
                except Exception:
                    log.warning("Stream JSON parse failed, using raw text")
                    reply_text = full_text.strip()
            elif error_occurred:
                # Fallback to non-streaming
                try:
                    reply_text = chat(cfg, system=system_prompt, messages=messages)
                except Exception as e:
                    reply_text = f"I encountered an error: {e!s}"

            # Process actions (same as chat_endpoint)
            response: dict = {
                "reply": reply_text, "session_id": session_id,
                "blocks": [], "suggestions": [], "context_hint": None,
            }

            if user_role == "job_seeker":
                action_data = None

            response = _process_actions(response, action_data, cfg, user_id, session_id)

            # ── POST-STREAMING: check if a workflow was started ──
            if response.get("_start_workflow"):
                from app.agents.orchestrator import run_workflow

                # Save the LLM reply as assistant message first
                assistant_msg_id = uuid.uuid4().hex[:8]
                db.insert_chat_message({
                    "id": assistant_msg_id, "user_id": user_id,
                    "session_id": session_id, "role": "assistant",
                    "content": reply_text,
                    "created_at": datetime.now().isoformat(),
                })

                wf = db.get_workflow(response["workflow_id"])
                # Run the workflow — yields workflow_step and done events
                async for wf_event in run_workflow(cfg, wf, user_id, session_id):
                    if wf_event["event"] == "workflow_step":
                        yield wf_event
                    elif wf_event["event"] == "done":
                        wf_data = json.loads(wf_event["data"]) if isinstance(wf_event["data"], str) else wf_event["data"]
                        # Save workflow completion message
                        wf_msg_id = uuid.uuid4().hex[:8]
                        db.insert_chat_message({
                            "id": wf_msg_id, "user_id": user_id,
                            "session_id": session_id, "role": "assistant",
                            "content": wf_data.get("reply", ""),
                            "created_at": datetime.now().isoformat(),
                        })
                        wf_data["message_id"] = wf_msg_id
                        yield {"event": "done", "data": json.dumps(wf_data)}
                return

            # Build suggestions
            if not response.get("suggestions") and user_role == "recruiter":
                response["suggestions"] = _build_smart_suggestions(action_data)

            # Save assistant message
            assistant_msg_id = uuid.uuid4().hex[:8]
            action_json_str = ""
            action_status_str = ""
            if response.get("action"):
                action_json_str = json.dumps(response["action"])
                action_status_str = "pending"
            db.insert_chat_message({
                "id": assistant_msg_id, "user_id": user_id,
                "session_id": session_id, "role": "assistant",
                "content": response["reply"],
                "action_json": action_json_str,
                "action_status": action_status_str,
                "created_at": datetime.now().isoformat(),
            })
            response["message_id"] = assistant_msg_id

            yield {"event": "done", "data": json.dumps(response)}
        except Exception as exc:
            log.error("Stream post-processing error: %s", exc, exc_info=True)
            # Always send a done event so the frontend doesn't hang
            fallback = {
                "reply": reply_text or "Sorry, something went wrong processing the response.",
                "session_id": session_id,
                "blocks": [], "suggestions": [], "context_hint": None,
            }
            yield {"event": "done", "data": json.dumps(fallback)}

    return EventSourceResponse(event_generator())


# ── Notifications ────────────────────────────────────────────────────────


@router.get("/notifications")
async def get_notifications(current_user: dict = Depends(get_current_user)):
    """Get proactive notifications for the recruiter dashboard."""
    user_role = current_user.get("role", "recruiter")
    if user_role != "recruiter":
        return []

    notifications = []
    now = datetime.now()

    # Stale candidates: contacted > 3 days ago
    candidates = db.list_candidates() or []
    for c in candidates:
        if c.get("status") != "contacted":
            continue
        updated = c.get("updated_at") or c.get("created_at", "")
        if not updated:
            continue
        try:
            dt = datetime.fromisoformat(updated)
            days = (now - dt).days
            if days >= 3:
                notifications.append({
                    "id": f"stale-{c['id']}",
                    "type": "stale_candidate",
                    "severity": "warning",
                    "title": f"{c['name']} awaiting reply for {days} days",
                    "description": f"Last contacted {days} days ago. Consider sending a follow-up.",
                    "candidate_id": c["id"],
                    "candidate_name": c["name"],
                    "action_label": "Send follow-up",
                    "action_prompt": f"Draft a follow-up email to {c['name']}",
                    "created_at": updated,
                })
        except (ValueError, TypeError):
            pass

    # Upcoming events in the next 2 hours
    events = db.list_events() or []
    two_hours = now + timedelta(hours=2)
    for e in events:
        if not e.get("start_time"):
            continue
        try:
            start = datetime.fromisoformat(e["start_time"])
            if now <= start <= two_hours:
                mins = int((start - now).total_seconds() / 60)
                notifications.append({
                    "id": f"event-{e['id']}",
                    "type": "upcoming_event",
                    "severity": "info",
                    "title": f"{e['title']} in {mins} minutes",
                    "description": f"{e.get('candidate_name', '')} — {e.get('event_type', 'event')}",
                    "candidate_id": e.get("candidate_id", ""),
                    "candidate_name": e.get("candidate_name", ""),
                    "action_label": "View details",
                    "action_prompt": f"Tell me about the upcoming {e.get('event_type', 'event')} with {e.get('candidate_name', 'the candidate')}",
                    "created_at": e["start_time"],
                })
        except (ValueError, TypeError):
            pass

    # New high-score candidates (added in last 24h with match_score > 0.7)
    yesterday = (now - timedelta(hours=24)).isoformat()
    for c in candidates:
        created = c.get("created_at", "")
        if not created or created < yesterday:
            continue
        score = c.get("match_score", 0)
        if score and score >= 0.7:
            notifications.append({
                "id": f"new-match-{c['id']}",
                "type": "new_match",
                "severity": "success",
                "title": f"New strong match: {c['name']} ({int(score * 100)}%)",
                "description": f"{c.get('current_title', 'Candidate')} — added recently with high match score.",
                "candidate_id": c["id"],
                "candidate_name": c["name"],
                "action_label": "Review",
                "action_prompt": f"Tell me about {c['name']}",
                "created_at": created,
            })

    # Pending email drafts
    emails = db.list_emails() or []
    pending = [e for e in emails if not e["sent"] and not e["approved"]]
    if len(pending) >= 2:
        notifications.append({
            "id": "pending-drafts",
            "type": "pending_drafts",
            "severity": "info",
            "title": f"{len(pending)} email drafts pending review",
            "description": "Review and send your pending email drafts.",
            "action_label": "Review drafts",
            "action_prompt": "Show me pending email drafts",
            "created_at": now.isoformat(),
        })

    # Sort by severity (warning first, then success, then info)
    severity_order = {"warning": 0, "success": 1, "info": 2}
    notifications.sort(key=lambda n: severity_order.get(n.get("severity", "info"), 3))

    return notifications[:10]


# ── Action Processing (shared by chat + streaming) ───────────────────────


def _process_actions(response: dict, action_data, cfg, user_id: str, session_id: str = "") -> dict:
    """Process action intents from the LLM and enrich the response."""
    from app.models import Email

    if not action_data or not isinstance(action_data, dict):
        return response

    action_type = action_data.get("type")

    if action_type == "compose_email":
        try:
            from app.agents.communication import draft_email as agent_draft

            candidate_id = action_data.get("candidate_id", "")
            candidate_name = action_data.get("candidate_name", "")
            to_email = action_data.get("to_email", "")
            email_type = action_data.get("email_type", "outreach")
            job_id = action_data.get("job_id", "")
            instructions = action_data.get("instructions", "")

            draft = agent_draft(cfg, candidate_id=candidate_id, job_id=job_id,
                                email_type=email_type, instructions=instructions)
            if draft.get("error"):
                log.warning("Communication agent error: %s", draft["error"])

            email = Email(
                candidate_id=candidate_id, candidate_name=candidate_name,
                to_email=to_email, subject=draft.get("subject", ""),
                body=draft.get("body", ""), email_type=email_type,
            )
            db.insert_email(email.model_dump())

            db.insert_activity({
                "id": uuid.uuid4().hex[:8], "user_id": user_id,
                "activity_type": "email_drafted",
                "description": f"Drafted {email_type} email to {candidate_name}",
                "metadata_json": json.dumps({
                    "email_id": email.id, "candidate_id": candidate_id,
                    "candidate_name": candidate_name, "email_type": email_type,
                }),
                "created_at": datetime.now().isoformat(),
            })

            response["reply"] = f"I've drafted a personalized {email_type} email for {candidate_name}. Review it below and send when ready!"
            response["action"] = {"type": "compose_email", "email": email.model_dump()}
            response["context_hint"] = {"type": "candidate", "id": candidate_id}
        except Exception as e:
            log.error("Failed to create email draft: %s", e)

    elif action_type == "match_candidate":
        try:
            from app.agents.planning import match_candidate_to_jobs

            candidate_id = action_data.get("candidate_id", "")
            candidate_name = action_data.get("candidate_name", "")
            result = match_candidate_to_jobs(cfg, candidate_id)

            if result.get("error") and not result.get("rankings"):
                response["reply"] = f"Sorry, I couldn't run the matching: {result['error']}"
            else:
                rankings = result.get("rankings", [])
                summary = result.get("summary", "")
                top_count = min(len(rankings), 5)

                if rankings:
                    top = rankings[0]
                    response["reply"] = (
                        f"I found **{top_count} matching jobs** for **{candidate_name}**. "
                        f"Best match: **{top.get('title', '')}** at {top.get('company', '')} "
                        f"({int(top.get('score', 0) * 100)}%)."
                    )
                    if summary:
                        response["reply"] += f"\n\n{summary}"
                    response["reply"] += "\n\nWould you like me to draft an outreach email for the top match?"
                else:
                    response["reply"] = f"No matching jobs found for {candidate_name}."

                candidate_data = db.get_candidate(candidate_id)
                response["blocks"].append({
                    "type": "match_report",
                    "candidate": {
                        "id": candidate_id, "name": candidate_name,
                        "current_title": candidate_data.get("current_title", "") if candidate_data else "",
                        "skills": candidate_data.get("skills", []) if candidate_data else [],
                    },
                    "rankings": [
                        {"job_id": r.get("job_id", ""), "title": r.get("title", ""),
                         "company": r.get("company", ""), "score": r.get("score", 0),
                         "strengths": r.get("strengths", []), "gaps": r.get("gaps", []),
                         "one_liner": r.get("one_liner", "")}
                        for r in rankings[:5]
                    ],
                    "summary": summary,
                })
                response["context_hint"] = {"type": "candidate", "id": candidate_id}
                response["suggestions"] = [
                    {"label": f"Draft email to {candidate_name}", "prompt": f"Draft an outreach email to {candidate_name}"},
                    {"label": "Compare candidates", "prompt": f"Compare top candidates for {rankings[0].get('title', 'this role')}" if rankings else "Show pipeline status"},
                ]

                db.insert_activity({
                    "id": uuid.uuid4().hex[:8], "user_id": user_id,
                    "activity_type": "candidate_matched",
                    "description": f"Matched {candidate_name} against {len(rankings)} jobs",
                    "metadata_json": json.dumps({
                        "candidate_id": candidate_id, "candidate_name": candidate_name,
                        "top_job": rankings[0].get("title", "") if rankings else "",
                        "top_score": rankings[0].get("score", 0) if rankings else 0,
                    }),
                    "created_at": datetime.now().isoformat(),
                })
        except Exception as e:
            log.error("Failed to run candidate matching: %s", e)
            response["reply"] = f"Sorry, I encountered an error while matching: {e}"

    elif action_type == "mark_candidates_replied":
        try:
            candidates_to_update = action_data.get("candidates", [])
            updated_names = []
            now_str = datetime.now().isoformat()

            for c in candidates_to_update:
                cid = c.get("candidate_id", "")
                cname = c.get("candidate_name", "")
                if cid:
                    db.update_candidate(cid, {"status": "replied", "updated_at": now_str})
                    updated_names.append(cname)

            if updated_names:
                names_str = "、".join(updated_names)
                response["reply"] = f"Done! I've updated **{names_str}** to the **replied** stage in the pipeline."
                response["action"] = {"type": "mark_candidates_replied", "updated": updated_names}
                db.insert_activity({
                    "id": uuid.uuid4().hex[:8], "user_id": user_id,
                    "activity_type": "candidates_marked_replied",
                    "description": f"Marked {names_str} as replied",
                    "metadata_json": json.dumps({"candidates": candidates_to_update}),
                    "created_at": now_str,
                })
            else:
                response["reply"] = "I couldn't find the candidates to update."
        except Exception as e:
            log.error("Failed to mark candidates as replied: %s", e)
            response["reply"] = f"Sorry, I encountered an error while updating: {e}"

    elif action_type == "upload_resume":
        response["action"] = {
            "type": "upload_resume",
            "job_id": action_data.get("job_id", ""),
            "job_title": action_data.get("job_title", ""),
        }

    elif action_type == "upload_jd":
        response["action"] = {"type": "upload_jd"}

    elif action_type == "start_workflow":
        try:
            from app.agents.orchestrator import create_workflow
            wf = create_workflow(
                session_id, user_id,
                action_data.get("workflow_type", ""),
                action_data.get("params", {}),
            )
            response["workflow_id"] = wf["id"]
            response["_start_workflow"] = True
        except Exception as e:
            log.error("Failed to create workflow: %s", e)
            response["reply"] = f"Sorry, I couldn't start the workflow: {e}"

    return response


def _build_smart_suggestions(action_data) -> list[dict]:
    """Build contextual suggestions based on pipeline state and last action."""
    suggestions = []
    candidates = db.list_candidates() or []

    contacted = [c for c in candidates if c.get("status") == "contacted"]
    new_ones = [c for c in candidates if c.get("status") == "new"]

    if action_data and isinstance(action_data, dict):
        atype = action_data.get("type", "")
        if atype == "compose_email":
            name = action_data.get("candidate_name", "")
            suggestions.append({"label": "Check pipeline", "prompt": "What's the pipeline status?"})
            if len(contacted) > 1:
                suggestions.append({"label": "More follow-ups", "prompt": "Who else needs a follow-up?"})
            return suggestions[:4]
        if atype == "upload_resume":
            suggestions.append({"label": "Match to jobs", "prompt": "Match the latest candidate to jobs"})
            suggestions.append({"label": "Upload another", "prompt": "Upload another resume"})
            return suggestions[:4]
        if atype == "upload_jd":
            suggestions.append({"label": "Find candidates", "prompt": "Find candidates for the latest job"})
            suggestions.append({"label": "Upload resume", "prompt": "Upload a resume"})
            return suggestions[:4]

    if contacted:
        suggestions.append({"label": "Check for replies", "prompt": "Have any contacted candidates replied?"})
    if new_ones:
        suggestions.append({"label": f"Review {new_ones[0]['name']}", "prompt": f"What jobs match {new_ones[0]['name']}?"})
    if not suggestions:
        suggestions.append({"label": "Pipeline status", "prompt": "What's the pipeline status today?"})
    suggestions.append({"label": "Upload resume", "prompt": "Upload a resume"})

    return suggestions[:4]


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
