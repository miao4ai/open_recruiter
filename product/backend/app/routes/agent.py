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


# ── Shared setup ──────────────────────────────────────────────────────────
# Both chat endpoints run the same agent over the same tools. Keeping the setup
# in one place is the only thing stopping them drifting apart again — the
# streaming and non-streaming paths were separately maintained before, and one
# of them quietly rotted.


def _has_llm_key(cfg) -> bool:
    return bool(
        (cfg.llm_provider == "anthropic" and cfg.anthropic_api_key)
        or (cfg.llm_provider == "openai" and cfg.openai_api_key)
    )


def _open_session(user_id: str, message: str, session_id: str | None) -> str:
    """Reuse the session, or start one named after the opening message."""
    now = datetime.now().isoformat()
    if session_id:
        db.update_chat_session(session_id, {"updated_at": now})
        return session_id

    session_id = uuid.uuid4().hex[:8]
    db.insert_chat_session(
        {
            "id": session_id,
            "user_id": user_id,
            "title": message[:50] or "New Chat",
            "created_at": now,
            "updated_at": now,
        }
    )
    return session_id


def _prepare_turn(req, current_user: dict):
    """Session, history, agent — everything both endpoints need.

    Returns ``None`` if no API key is configured, so the caller can answer with
    something the user can act on instead of a failure.
    """
    from app.agent_tools import product_tools, tools_for_role
    from app.routes.settings import get_config
    from app.sdk_bridge import build_recruiter

    cfg = get_config()
    if not _has_llm_key(cfg):
        return None

    user_id = current_user["id"]
    user_role = current_user.get("role", "recruiter")
    session_id = _open_session(user_id, req.message, req.session_id)

    _maybe_summarize_previous_session(cfg, user_id, session_id)

    history = [
        {"role": m["role"], "content": m["content"]}
        for m in db.list_chat_messages(user_id, limit=20, session_id=session_id)
    ]
    db.insert_chat_message(
        {
            "id": uuid.uuid4().hex[:8],
            "user_id": user_id,
            "session_id": session_id,
            "role": "user",
            "content": req.message,
            "created_at": datetime.now().isoformat(),
        }
    )

    recruiter = build_recruiter(cfg, extra_tools=product_tools(cfg, user_id))
    recruiter.system = _agent_system_prompt(recruiter, user_id, user_role, req)
    agent = recruiter.agent(max_steps=8)
    agent.tools = tools_for_role(recruiter, user_role)

    return {
        "cfg": cfg,
        "agent": agent,
        "history": history,
        "session_id": session_id,
        "user_id": user_id,
        "user_role": user_role,
    }


_NO_KEY_REPLY = "Please configure an LLM API key in Settings before using the chat assistant."


def _remember_turn(turn: dict, message: str, reply: str) -> None:
    """Memory extraction runs off the request path — it must never block a reply."""
    if turn["user_role"] != "recruiter":
        return
    threading.Thread(
        target=_extract_and_store_memories,
        args=(turn["cfg"], turn["user_id"], message, reply),
        daemon=True,
    ).start()
    count = len(db.list_chat_messages(turn["user_id"], limit=100, session_id=turn["session_id"]))
    if count and count % 20 == 0:
        threading.Thread(
            target=_extract_implicit_memories, args=(turn["cfg"], turn["user_id"]), daemon=True
        ).start()


@router.post("/chat")
async def chat_endpoint(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    """Chat without streaming.

    The same agent as ``/chat/stream``, collected instead of forwarded. It backs
    the client's fallback when the stream fails, and the job-seeker home page —
    so running a second implementation here is how the two get to disagree.
    """
    from app.sse_agent import stream_agent

    turn = _prepare_turn(req, current_user)
    if turn is None:
        return {"reply": _NO_KEY_REPLY, "session_id": "", "blocks": [], "suggestions": []}

    final: dict = {}
    async for frame in stream_agent(
        turn["agent"],
        req.message,
        session_id=turn["session_id"],
        user_id=turn["user_id"],
        history=turn["history"],
    ):
        if frame["event"] == "done":
            final = json.loads(frame["data"])

    _remember_turn(turn, req.message, final.get("reply", ""))
    return final


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
    """Streaming chat.

    Text arrives as ``token`` frames while it is generated, tool activity as
    ``tool_call`` / ``tool_result``, and the turn closes with ``done`` carrying
    the assembled reply, blocks, and action.
    """
    from app.sse_agent import stream_agent

    turn = _prepare_turn(req, current_user)

    if turn is None:
        async def no_key():
            yield {
                "event": "done",
                "data": json.dumps(
                    {"reply": _NO_KEY_REPLY, "session_id": "", "blocks": [], "suggestions": []}
                ),
            }

        return EventSourceResponse(no_key())

    async def event_generator():
        reply = ""
        async for frame in stream_agent(
            turn["agent"],
            req.message,
            session_id=turn["session_id"],
            user_id=turn["user_id"],
            history=turn["history"],
        ):
            if frame["event"] == "done":
                reply = json.loads(frame["data"]).get("reply", "")
            yield frame
        _remember_turn(turn, req.message, reply)

    return EventSourceResponse(event_generator())


def _agent_system_prompt(recruiter, user_id: str, user_role: str, req) -> str:
    """The persona, the boundaries, and a short briefing on the pipeline.

    Two things changed from the legacy prompt. Capabilities are gone — the tool
    schemas describe them, so they cannot drift out of sync with the code. And
    the pipeline is summarised rather than pasted: the briefing is bounded and
    retrieval-backed, so a recruiter with five hundred candidates gets the eight
    relevant ones instead of whichever fifteen the database returned first.
    """
    from app.prompts import AGENT_RECRUITER, AGENT_SEEKER, ENCOURAGEMENT_ADDENDUM

    if user_role == "job_seeker":
        prompt = AGENT_SEEKER.format(context=_build_job_seeker_context(user_id))
        if getattr(req, "encouragement_mode", False):
            prompt += ENCOURAGEMENT_ADDENDUM
        return prompt

    return AGENT_RECRUITER.format(context=recruiter.pipeline_context(req.message))


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


def _build_job_seeker_context(user_id: str, session_id: str | None = None) -> str:
    """Build context from the job seeker's profile, saved jobs, and recent search results."""
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

    # Recent search results — inject so LLM can resolve "第N个" references
    if session_id:
        recent_msgs = db.list_chat_messages(user_id, limit=10, session_id=session_id)
        for msg in reversed(recent_msgs):
            if msg.get("action_json"):
                try:
                    action = json.loads(msg["action_json"]) if isinstance(msg["action_json"], str) else msg["action_json"]
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
                except (json.JSONDecodeError, TypeError):
                    pass

    return "\n".join(parts)


# ── Memory Extraction ─────────────────────────────────────────────────

def _extract_and_store_memories(cfg, user_id: str, user_message: str, assistant_reply: str) -> None:
    """Background task: detect explicit preferences in the recruiter's message."""
    from app.prompts import MEMORY_EXTRACTION
    from app.llm import chat_json

    if len(user_message) < 15:
        return

    # Keyword pre-filter — avoid an LLM call on most messages
    signals = [
        "prefer", "always", "never", "don't", "i like", "i want", "make sure",
        "please use", "tone", "style", "remember", "from now on",
        "偏好", "总是", "不要", "我喜欢", "我想要", "确保", "请用", "记住", "以后",
    ]
    if not any(s in user_message.lower() for s in signals):
        return

    try:
        conversation = f"Recruiter: {user_message}\nAssistant: {assistant_reply}"
        result = chat_json(cfg, system=MEMORY_EXTRACTION,
                           messages=[{"role": "user", "content": conversation}])

        memories_out = result.get("memories", []) if isinstance(result, dict) else []
        now = datetime.now().isoformat()

        for mem in memories_out:
            content = mem.get("content", "").strip()
            if not content:
                continue

            # Dedup: check existing memories for substring overlap
            existing = db.list_memories(user_id, limit=50)
            duplicate = next(
                (m for m in existing
                 if content.lower() in m["content"].lower()
                 or m["content"].lower() in content.lower()),
                None,
            )
            if duplicate:
                db.update_memory(duplicate["id"], {
                    "confidence": min(duplicate["confidence"] + 0.1, 1.0),
                    "updated_at": now,
                })
                continue

            db.insert_memory({
                "id": uuid.uuid4().hex[:8],
                "user_id": user_id,
                "memory_type": "explicit",
                "category": mem.get("category", "general"),
                "content": content,
                "source": "chat",
                "confidence": 1.0,
                "access_count": 0,
                "created_at": now,
                "updated_at": now,
            })
    except Exception as e:
        log.warning("Memory extraction failed (non-fatal): %s", e)


def _extract_implicit_memories(cfg, user_id: str) -> None:
    """Background task: analyze activity logs to find behavioral patterns."""
    from app.prompts import IMPLICIT_MEMORY_EXTRACTION
    from app.llm import chat_json

    activities = db.list_activities(user_id, limit=50)
    if len(activities) < 10:
        return  # Not enough data yet

    activity_lines = []
    for a in activities[:30]:
        activity_lines.append(
            f"- [{a['activity_type']}] {a.get('description', '')} "
            f"(meta: {a.get('metadata_json', '{}')})"
        )

    try:
        result = chat_json(
            cfg, system=IMPLICIT_MEMORY_EXTRACTION,
            messages=[{"role": "user", "content": "Recent activities:\n" + "\n".join(activity_lines)}],
        )

        patterns = result.get("patterns", []) if isinstance(result, dict) else []
        now = datetime.now().isoformat()

        for pat in patterns:
            content = pat.get("content", "").strip()
            if not content:
                continue

            existing = db.list_memories(user_id, memory_type="implicit", limit=50)
            duplicate = next(
                (m for m in existing
                 if content.lower() in m["content"].lower()
                 or m["content"].lower() in content.lower()),
                None,
            )
            if duplicate:
                db.update_memory(duplicate["id"], {
                    "confidence": min(duplicate["confidence"] + 0.05, 0.95),
                    "updated_at": now,
                })
                continue

            db.insert_memory({
                "id": uuid.uuid4().hex[:8],
                "user_id": user_id,
                "memory_type": "implicit",
                "category": pat.get("category", "general"),
                "content": content,
                "source": "action_pattern",
                "confidence": pat.get("confidence", 0.6),
                "access_count": 0,
                "created_at": now,
                "updated_at": now,
            })
    except Exception as e:
        log.warning("Implicit memory extraction failed (non-fatal): %s", e)


# ── Cross-Session Intelligence ───────────────────────────────────────────


def _summarize_session(cfg, session_id: str, user_id: str) -> None:
    """Background task: generate an LLM summary of a chat session and index it for RAG."""
    from app.prompts import SESSION_SUMMARY
    from app.llm import chat_json
    from app import vectorstore

    # Skip if summary already exists
    existing = db.get_session_summary(session_id)
    if existing:
        return

    # Load all messages from the session
    messages = db.list_chat_messages(user_id, limit=100, session_id=session_id)
    if len(messages) < 4:
        return

    # Format conversation for the LLM
    lines = []
    for m in messages:
        role = "Recruiter" if m["role"] == "user" else "Assistant"
        lines.append(f"{role}: {m['content']}")
    conversation = "\n\n".join(lines)

    try:
        result = chat_json(
            cfg, system=SESSION_SUMMARY,
            messages=[{"role": "user", "content": conversation}],
        )

        summary_text = result.get("summary", "") if isinstance(result, dict) else ""
        if not summary_text:
            return

        topics = result.get("topics", []) if isinstance(result, dict) else []
        entities = result.get("entities", {}) if isinstance(result, dict) else {}

        now = datetime.now().isoformat()
        summary_id = uuid.uuid4().hex[:8]

        # Save to SQLite
        db.insert_session_summary({
            "id": summary_id,
            "session_id": session_id,
            "user_id": user_id,
            "summary": summary_text,
            "topics": topics,
            "entity_refs": entities,
            "message_count": len(messages),
            "created_at": now,
        })

        # Index in ChromaDB for semantic retrieval
        session = db.get_chat_session(session_id)
        session_title = session["title"] if session else "Chat"
        embed_text = f"{session_title}\n{summary_text}\nTopics: {', '.join(topics)}"
        vectorstore.index_session_summary(summary_id, embed_text, {
            "user_id": user_id,
            "session_id": session_id,
            "created_at": now,
        })

        log.info("Summarized session %s (%d messages) and indexed for RAG", session_id, len(messages))
    except Exception as e:
        log.warning("Session summarization failed (non-fatal): %s", e)


def _rebuild_agent(user_id: str, user_role: str):
    """The same agent and tool set the paused run had.

    Rebuilt rather than held in memory: the process that asked for approval is
    usually not the one that receives the answer.
    """
    from app.agent_tools import product_tools, tools_for_role
    from app.routes.settings import get_config
    from app.sdk_bridge import build_recruiter

    cfg = get_config()
    recruiter = build_recruiter(cfg, extra_tools=product_tools(cfg, user_id))
    agent = recruiter.agent(max_steps=8)
    agent.tools = tools_for_role(recruiter, user_role)
    return agent


async def _answer_approval(workflow_id: str, user: dict, approved: bool) -> dict:
    """Carry on a run that stopped at an approval gate."""
    from openrecruiter import PendingApproval

    from app.sse_agent import stream_agent

    wf = db.get_workflow(workflow_id)
    if not wf:
        return {"error": "Workflow not found"}
    if wf.get("status") != "paused":
        return {"error": "Workflow is not paused"}
    if wf.get("user_id") != user["id"]:
        return {"error": "Workflow not found"}

    try:
        pending = PendingApproval.model_validate_json(wf.get("checkpoint_data_json") or "{}")
    except Exception as exc:
        log.error("Could not read the parked approval for %s: %s", workflow_id, exc)
        return {"error": "This approval can no longer be resumed."}

    # Mark it spent before running, so a double-click cannot send twice.
    db.update_workflow(
        workflow_id,
        {"status": "approved" if approved else "cancelled", "updated_at": datetime.now().isoformat()},
    )

    agent = _rebuild_agent(user["id"], user.get("role", "recruiter"))
    final: dict = {}
    async for frame in stream_agent(
        agent,
        "",
        session_id=wf["session_id"],
        user_id=user["id"],
        resume=(pending, approved),
    ):
        if frame["event"] == "done":
            final = json.loads(frame["data"])

    return {"status": "completed" if approved else "cancelled", **final}


@router.post("/workflow/{workflow_id}/resume")
async def resume_workflow(workflow_id: str, body: dict, user=Depends(get_current_user)):
    """Approve the action an agent stopped on, and let it finish.

    ``body`` may carry ``{"approved": false}`` to decline without cancelling —
    the agent is told and gets to respond, which is more useful than an
    abandoned turn.
    """
    return await _answer_approval(workflow_id, user, approved=bool(body.get("approved", True)))


@router.post("/workflow/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str, user=Depends(get_current_user)):
    """Decline the action. Nothing is performed and the agent is told why."""
    return await _answer_approval(workflow_id, user, approved=False)


def _maybe_summarize_previous_session(cfg, user_id: str, current_session_id: str) -> None:
    """Check if the user's previous session needs summarization and trigger it in background."""
    sessions = db.list_chat_sessions(user_id)
    for s in sessions:
        if s["id"] == current_session_id:
            continue
        # Found the most recent other session — check if it needs summarization
        existing = db.get_session_summary(s["id"])
        if not existing:
            threading.Thread(
                target=_summarize_session,
                args=(cfg, s["id"], user_id), daemon=True,
            ).start()
        break  # Only check the most recent one
