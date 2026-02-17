"""Orchestrator — coordinates multi-step workflows through SSE."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from typing import Any

from app import database as db
from app.config import Config

log = logging.getLogger(__name__)


# ── Workflow Step Definitions ──────────────────────────────────────────────

WORKFLOW_STEPS: dict[str, list[str]] = {
    "bulk_outreach": [
        "Find candidates",
        "Draft emails",
        "Review batch",
        "Send emails",
    ],
    "candidate_review": [
        "Load candidate",
        "Run match analysis",
        "Suggest action",
        "Execute action",
    ],
    "interview_scheduling": [
        "Load candidate & job",
        "Propose time slots",
        "Create calendar event",
        "Draft invite email",
    ],
    "pipeline_cleanup": [
        "Find stale candidates",
        "Categorize actions",
        "Execute actions",
    ],
    "job_launch": [
        "Load job details",
        "Find matching candidates",
        "Rank candidates",
        "Draft outreach batch",
        "Send outreach",
    ],
}


# ── Lifecycle ──────────────────────────────────────────────────────────────


def create_workflow(
    session_id: str,
    user_id: str,
    workflow_type: str,
    params: dict,
) -> dict:
    """Create and persist a new workflow record."""
    steps = WORKFLOW_STEPS.get(workflow_type, [])
    now = datetime.now().isoformat()
    workflow = {
        "id": uuid.uuid4().hex[:8],
        "session_id": session_id,
        "user_id": user_id,
        "workflow_type": workflow_type,
        "status": "running",
        "current_step": 0,
        "total_steps": len(steps),
        "steps_json": json.dumps([{"label": s, "status": "pending"} for s in steps]),
        "context_json": json.dumps(params),
        "checkpoint_data_json": "{}",
        "created_at": now,
        "updated_at": now,
    }
    db.insert_workflow(workflow)
    return workflow


async def run_workflow(
    cfg: Config,
    workflow: dict,
    user_id: str,
    session_id: str,
) -> AsyncGenerator[dict, None]:
    """Execute a workflow from the current step. Yields SSE-ready dicts."""
    wtype = workflow["workflow_type"]
    runners = {
        "bulk_outreach": _run_bulk_outreach,
        "candidate_review": _run_candidate_review,
        "interview_scheduling": _run_interview_scheduling,
        "pipeline_cleanup": _run_pipeline_cleanup,
        "job_launch": _run_job_launch,
    }
    runner = runners.get(wtype)
    if not runner:
        yield _done(session_id, f"Unknown workflow type: {wtype}")
        return
    try:
        async for event in runner(cfg, workflow, user_id, session_id):
            yield event
    except Exception as exc:
        log.error("Workflow %s error: %s", wtype, exc, exc_info=True)
        db.update_workflow(workflow["id"], {"status": "cancelled", "updated_at": datetime.now().isoformat()})
        yield _done(session_id, f"Sorry, the workflow encountered an error: {exc}")


async def resume_workflow(
    cfg: Config,
    workflow: dict,
    user_message: str,
    user_id: str,
    session_id: str,
) -> AsyncGenerator[dict, None]:
    """Resume a paused workflow after user approval/rejection."""
    lower = user_message.lower().strip()
    approved = any(w in lower for w in [
        "yes", "approve", "confirm", "go ahead", "send", "ok", "sure",
        "send all", "continue", "proceed",
        "好", "确认", "发送", "可以", "没问题", "继续",
    ])
    cancelled = any(w in lower for w in [
        "no", "cancel", "stop", "abort", "skip",
        "不", "取消", "停止",
    ])

    wid = workflow["id"]

    if cancelled or not approved:
        db.update_workflow(wid, {"status": "cancelled", "updated_at": datetime.now().isoformat()})
        yield _done(session_id, "Workflow cancelled. Let me know if you'd like to do something else.",
                     workflow_id=wid, workflow_status="cancelled")
        return

    # Resume: inject approval flag into context and re-run
    ctx = json.loads(workflow.get("context_json", "{}"))
    checkpoint = json.loads(workflow.get("checkpoint_data_json", "{}"))
    ctx["_resumed"] = checkpoint
    db.update_workflow(wid, {
        "status": "running",
        "context_json": json.dumps(ctx),
        "updated_at": datetime.now().isoformat(),
    })
    workflow = db.get_workflow(wid)  # refresh

    async for event in run_workflow(cfg, workflow, user_id, session_id):
        yield event


# ── SSE Event Helpers ──────────────────────────────────────────────────────


def _step(wid: str, idx: int, total: int, label: str, status: str) -> dict:
    """Build a workflow_step SSE event."""
    return {
        "event": "workflow_step",
        "data": json.dumps({
            "workflow_id": wid,
            "step_index": idx,
            "total_steps": total,
            "label": label,
            "status": status,
        }),
    }


def _done(
    session_id: str,
    reply: str,
    blocks: list | None = None,
    suggestions: list | None = None,
    workflow_id: str | None = None,
    workflow_status: str | None = None,
    context_hint: dict | None = None,
) -> dict:
    """Build a final done SSE event."""
    payload: dict[str, Any] = {
        "reply": reply,
        "session_id": session_id,
        "blocks": blocks or [],
        "suggestions": suggestions or [],
        "context_hint": context_hint,
    }
    if workflow_id:
        payload["workflow_id"] = workflow_id
        payload["workflow_status"] = workflow_status or "done"
    return {"event": "done", "data": json.dumps(payload)}


def _approval(
    session_id: str,
    reply: str,
    workflow_id: str,
    title: str,
    description: str,
    preview_items: list | None = None,
    approve_label: str = "Approve & Send",
    cancel_label: str = "Cancel",
) -> dict:
    """Build a done event with an approval_block."""
    return {
        "event": "done",
        "data": json.dumps({
            "reply": reply,
            "session_id": session_id,
            "blocks": [{
                "type": "approval_block",
                "workflow_id": workflow_id,
                "title": title,
                "description": description,
                "approve_label": approve_label,
                "cancel_label": cancel_label,
                "preview_items": preview_items or [],
            }],
            "suggestions": [],
            "context_hint": None,
            "workflow_id": workflow_id,
            "workflow_status": "paused",
        }),
    }


def _update_steps(wid: str, steps: list[dict], step_idx: int, status: str) -> None:
    """Mark a step status and persist."""
    if 0 <= step_idx < len(steps):
        steps[step_idx]["status"] = status
    db.update_workflow(wid, {
        "current_step": step_idx,
        "steps_json": json.dumps(steps),
        "updated_at": datetime.now().isoformat(),
    })


# ── Workflow: Bulk Outreach ────────────────────────────────────────────────


async def _run_bulk_outreach(
    cfg: Config, workflow: dict, user_id: str, session_id: str,
) -> AsyncGenerator[dict, None]:
    wid = workflow["id"]
    ctx = json.loads(workflow["context_json"])
    steps = json.loads(workflow["steps_json"])
    total = workflow["total_steps"]
    loop = asyncio.get_running_loop()
    resumed = ctx.get("_resumed")

    if not resumed:
        # Step 0: Find candidates
        yield _step(wid, 0, total, steps[0]["label"], "running")
        _update_steps(wid, steps, 0, "running")

        job_id = ctx.get("job_id", "")
        candidate_ids = ctx.get("candidate_ids", [])
        if candidate_ids:
            candidates = [db.get_candidate(cid) for cid in candidate_ids]
            candidates = [c for c in candidates if c]
        else:
            all_cands = db.list_candidates(job_id=job_id or None, status="new")
            candidates = all_cands[:10]

        if not candidates:
            _update_steps(wid, steps, 0, "done")
            db.update_workflow(wid, {"status": "done", "updated_at": datetime.now().isoformat()})
            yield _done(session_id, "No candidates found for outreach. Try uploading some resumes first.",
                        workflow_id=wid, workflow_status="done")
            return

        _update_steps(wid, steps, 0, "done")
        yield _step(wid, 0, total, steps[0]["label"], "done")
        await asyncio.sleep(0)

        # Step 1: Draft emails
        yield _step(wid, 1, total, steps[1]["label"], "running")
        _update_steps(wid, steps, 1, "running")

        from app.agents.communication import draft_email
        from app.models import Email

        drafted_emails = []
        for c in candidates:
            draft = await loop.run_in_executor(
                None, draft_email, cfg, c["id"],
                job_id or c.get("job_id", ""), "outreach",
                ctx.get("instructions", ""),
            )
            email = Email(
                candidate_id=c["id"], candidate_name=c["name"],
                to_email=c.get("email", ""), subject=draft.get("subject", "(no subject)"),
                body=draft.get("body", ""), email_type="outreach",
            )
            db.insert_email(email.model_dump())
            drafted_emails.append({
                "id": email.id, "candidate_name": c["name"],
                "to_email": c.get("email", ""), "subject": draft.get("subject", ""),
            })
            await asyncio.sleep(0)

        _update_steps(wid, steps, 1, "done")
        yield _step(wid, 1, total, steps[1]["label"], "done")

        # Pause at approval
        _update_steps(wid, steps, 2, "running")
        db.update_workflow(wid, {
            "status": "paused",
            "checkpoint_data_json": json.dumps({"drafted_emails": drafted_emails}),
            "updated_at": datetime.now().isoformat(),
        })

        preview = [{"label": e["candidate_name"], "detail": e["subject"]} for e in drafted_emails]
        yield _approval(
            session_id=session_id,
            reply=f"I've drafted **{len(drafted_emails)} outreach emails**. Review the batch below and approve to send.",
            workflow_id=wid,
            title=f"Send {len(drafted_emails)} outreach emails?",
            description="These emails will be sent immediately after approval.",
            preview_items=preview,
            approve_label="Send All",
        )
        return

    # ── Resumed after approval ──
    checkpoint = resumed
    drafted_emails = checkpoint.get("drafted_emails", [])

    _update_steps(wid, steps, 2, "done")
    yield _step(wid, 2, total, steps[2]["label"], "done")

    # Step 3: Send emails
    yield _step(wid, 3, total, steps[3]["label"], "running")
    _update_steps(wid, steps, 3, "running")

    from app.tools.email_sender import send_email as send_one
    from app.routes.settings import get_config

    email_cfg = get_config()
    sent_count = 0
    for e in drafted_emails:
        try:
            email_row = db.get_email(e["id"])
            if not email_row:
                continue
            result = send_one(
                backend=email_cfg.email_backend, from_email=email_cfg.email_from,
                to_email=email_row["to_email"], subject=email_row["subject"],
                body=email_row["body"],
                smtp_host=email_cfg.smtp_host, smtp_port=email_cfg.smtp_port,
                smtp_username=email_cfg.smtp_username, smtp_password=email_cfg.smtp_password,
            )
            if result.get("status") == "ok":
                db.update_email(e["id"], {
                    "approved": True, "sent": True,
                    "sent_at": datetime.now().isoformat(),
                    "message_id": result.get("message_id", ""),
                })
                sent_count += 1
            # Update candidate status to contacted
            if email_row.get("candidate_id"):
                db.update_candidate(email_row["candidate_id"], {
                    "status": "contacted", "updated_at": datetime.now().isoformat(),
                })
        except Exception as exc:
            log.error("Failed to send email %s: %s", e["id"], exc)
        await asyncio.sleep(0)

    _update_steps(wid, steps, 3, "done")
    yield _step(wid, 3, total, steps[3]["label"], "done")

    db.update_workflow(wid, {"status": "done", "updated_at": datetime.now().isoformat()})
    yield _done(
        session_id,
        f"Bulk outreach complete! Sent **{sent_count}/{len(drafted_emails)}** emails successfully.",
        workflow_id=wid, workflow_status="done",
    )


# ── Workflow: Candidate Review ─────────────────────────────────────────────


async def _run_candidate_review(
    cfg: Config, workflow: dict, user_id: str, session_id: str,
) -> AsyncGenerator[dict, None]:
    wid = workflow["id"]
    ctx = json.loads(workflow["context_json"])
    steps = json.loads(workflow["steps_json"])
    total = workflow["total_steps"]
    loop = asyncio.get_running_loop()
    resumed = ctx.get("_resumed")

    if not resumed:
        # Step 0: Load candidate
        yield _step(wid, 0, total, steps[0]["label"], "running")
        _update_steps(wid, steps, 0, "running")

        candidate_id = ctx.get("candidate_id", "")
        candidate = db.get_candidate(candidate_id) if candidate_id else None
        if not candidate:
            db.update_workflow(wid, {"status": "done", "updated_at": datetime.now().isoformat()})
            yield _done(session_id, "Candidate not found.", workflow_id=wid, workflow_status="done")
            return

        _update_steps(wid, steps, 0, "done")
        yield _step(wid, 0, total, steps[0]["label"], "done")

        # Step 1: Run match analysis
        yield _step(wid, 1, total, steps[1]["label"], "running")
        _update_steps(wid, steps, 1, "running")

        from app.agents.planning import match_candidate_to_jobs
        result = await loop.run_in_executor(None, match_candidate_to_jobs, cfg, candidate_id)
        rankings = result.get("rankings", [])
        summary = result.get("summary", "")

        _update_steps(wid, steps, 1, "done")
        yield _step(wid, 1, total, steps[1]["label"], "done")

        # Determine suggested action
        current_status = candidate.get("status", "new")
        if rankings and rankings[0].get("score", 0) >= 0.6:
            suggested = "screening" if current_status == "new" else "interview_scheduled"
            reason = f"Strong match ({int(rankings[0]['score'] * 100)}%) for {rankings[0].get('title', 'a role')}"
        else:
            suggested = current_status  # no change
            reason = "No strong matches found — consider gathering more information"

        # Pause for approval
        _update_steps(wid, steps, 2, "running")
        db.update_workflow(wid, {
            "status": "paused",
            "checkpoint_data_json": json.dumps({
                "candidate_id": candidate_id,
                "candidate_name": candidate["name"],
                "current_status": current_status,
                "suggested_status": suggested,
                "rankings": rankings[:5],
                "summary": summary,
            }),
            "updated_at": datetime.now().isoformat(),
        })

        # Build match report block
        blocks = [{
            "type": "match_report",
            "candidate": {
                "id": candidate_id, "name": candidate["name"],
                "current_title": candidate.get("current_title", ""),
                "skills": candidate.get("skills", []),
            },
            "rankings": [
                {"job_id": r.get("job_id", ""), "title": r.get("title", ""),
                 "company": r.get("company", ""), "score": r.get("score", 0),
                 "strengths": r.get("strengths", []), "gaps": r.get("gaps", []),
                 "one_liner": r.get("one_liner", "")}
                for r in rankings[:5]
            ],
            "summary": summary,
        }]

        if suggested != current_status:
            blocks.append({
                "type": "approval_block",
                "workflow_id": wid,
                "title": f"Move {candidate['name']} from '{current_status}' to '{suggested}'?",
                "description": reason,
                "approve_label": f"Move to {suggested}",
                "cancel_label": "Keep current status",
                "preview_items": [],
            })

        reply = f"Here's the match analysis for **{candidate['name']}**."
        if suggested != current_status:
            reply += f"\n\nI recommend moving them to **{suggested}** — {reason}."

        yield {
            "event": "done",
            "data": json.dumps({
                "reply": reply, "session_id": session_id,
                "blocks": blocks, "suggestions": [],
                "context_hint": {"type": "candidate", "id": candidate_id},
                "workflow_id": wid, "workflow_status": "paused",
            }),
        }
        return

    # ── Resumed after approval ──
    checkpoint = resumed
    candidate_id = checkpoint.get("candidate_id", "")
    new_status = checkpoint.get("suggested_status", "")

    if new_status and candidate_id:
        _update_steps(wid, steps, 3, "running")
        yield _step(wid, 3, total, steps[3]["label"], "running")

        db.update_candidate(candidate_id, {
            "status": new_status, "updated_at": datetime.now().isoformat(),
        })

        _update_steps(wid, steps, 3, "done")
        yield _step(wid, 3, total, steps[3]["label"], "done")

    db.update_workflow(wid, {"status": "done", "updated_at": datetime.now().isoformat()})
    name = checkpoint.get("candidate_name", "The candidate")
    yield _done(
        session_id,
        f"Done! **{name}** has been moved to **{new_status}** in the pipeline.",
        workflow_id=wid, workflow_status="done",
        context_hint={"type": "candidate", "id": candidate_id},
    )


# ── Workflow: Interview Scheduling ─────────────────────────────────────────


async def _run_interview_scheduling(
    cfg: Config, workflow: dict, user_id: str, session_id: str,
) -> AsyncGenerator[dict, None]:
    wid = workflow["id"]
    ctx = json.loads(workflow["context_json"])
    steps = json.loads(workflow["steps_json"])
    total = workflow["total_steps"]
    loop = asyncio.get_running_loop()
    resumed = ctx.get("_resumed")

    if not resumed:
        # Step 0: Load candidate & job
        yield _step(wid, 0, total, steps[0]["label"], "running")
        _update_steps(wid, steps, 0, "running")

        candidate_id = ctx.get("candidate_id", "")
        candidate_name = ctx.get("candidate_name", "")
        job_id = ctx.get("job_id", "")
        candidate = db.get_candidate(candidate_id) if candidate_id else None
        job = db.get_job(job_id) if job_id else None

        if not candidate:
            db.update_workflow(wid, {"status": "done", "updated_at": datetime.now().isoformat()})
            yield _done(session_id, "Candidate not found.", workflow_id=wid, workflow_status="done")
            return

        # If no job specified, use candidate's associated job
        if not job and candidate.get("job_id"):
            job = db.get_job(candidate["job_id"])

        _update_steps(wid, steps, 0, "done")
        yield _step(wid, 0, total, steps[0]["label"], "done")

        # Step 1: Propose time slots (generate 3 slots starting tomorrow)
        yield _step(wid, 1, total, steps[1]["label"], "running")
        _update_steps(wid, steps, 1, "running")

        tomorrow = datetime.now() + timedelta(days=1)
        slots = []
        for i in range(3):
            day = tomorrow + timedelta(days=i)
            slot_start = day.replace(hour=10 + i, minute=0, second=0, microsecond=0)
            slot_end = slot_start + timedelta(hours=1)
            slots.append({
                "start": slot_start.isoformat(),
                "end": slot_end.isoformat(),
                "label": slot_start.strftime("%A %b %d, %I:%M %p") + " - " + slot_end.strftime("%I:%M %p"),
            })

        _update_steps(wid, steps, 1, "done")
        yield _step(wid, 1, total, steps[1]["label"], "done")

        # Pause for approval
        _update_steps(wid, steps, 2, "running")
        job_title = job["title"] if job else "the role"
        db.update_workflow(wid, {
            "status": "paused",
            "checkpoint_data_json": json.dumps({
                "candidate_id": candidate_id,
                "candidate_name": candidate.get("name", candidate_name),
                "job_id": job_id,
                "job_title": job_title,
                "selected_slot": slots[0],  # default to first slot
                "all_slots": slots,
            }),
            "updated_at": datetime.now().isoformat(),
        })

        preview = [{"label": s["label"], "detail": ""} for s in slots]
        yield _approval(
            session_id=session_id,
            reply=f"I've proposed **3 interview slots** for **{candidate.get('name', candidate_name)}** ({job_title}). The first available slot will be used.",
            workflow_id=wid,
            title=f"Schedule interview with {candidate.get('name', candidate_name)}?",
            description=f"Create a calendar event and send an invite email for {job_title}.",
            preview_items=preview,
            approve_label="Schedule & Send Invite",
        )
        return

    # ── Resumed after approval ──
    checkpoint = resumed
    candidate_id = checkpoint.get("candidate_id", "")
    candidate_name = checkpoint.get("candidate_name", "")
    job_id = checkpoint.get("job_id", "")
    job_title = checkpoint.get("job_title", "")
    slot = checkpoint.get("selected_slot", {})

    # Step 2: Create calendar event
    _update_steps(wid, steps, 2, "done")
    yield _step(wid, 2, total, steps[2]["label"], "running")

    event_id = uuid.uuid4().hex[:8]
    now = datetime.now().isoformat()
    db.insert_event({
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
    })

    # Update candidate status
    db.update_candidate(candidate_id, {
        "status": "interview_scheduled", "updated_at": now,
    })

    yield _step(wid, 2, total, steps[2]["label"], "done")

    # Step 3: Draft invite email
    yield _step(wid, 3, total, steps[3]["label"], "running")
    _update_steps(wid, steps, 3, "running")

    from app.agents.communication import draft_email
    from app.models import Email

    draft = await loop.run_in_executor(
        None, draft_email, cfg, candidate_id, job_id, "interview_invite", "",
    )
    email = Email(
        candidate_id=candidate_id, candidate_name=candidate_name,
        to_email=db.get_candidate(candidate_id).get("email", "") if db.get_candidate(candidate_id) else "",
        subject=draft.get("subject", f"Interview Invitation — {job_title}"),
        body=draft.get("body", ""), email_type="interview_invite",
    )
    db.insert_email(email.model_dump())

    _update_steps(wid, steps, 3, "done")
    yield _step(wid, 3, total, steps[3]["label"], "done")

    db.update_workflow(wid, {"status": "done", "updated_at": datetime.now().isoformat()})
    yield _done(
        session_id,
        f"Interview scheduled! Created a calendar event for **{candidate_name}** and drafted an invite email. Review it in the email drafts.",
        workflow_id=wid, workflow_status="done",
        context_hint={"type": "candidate", "id": candidate_id},
    )


# ── Workflow: Pipeline Cleanup ─────────────────────────────────────────────


async def _run_pipeline_cleanup(
    cfg: Config, workflow: dict, user_id: str, session_id: str,
) -> AsyncGenerator[dict, None]:
    wid = workflow["id"]
    ctx = json.loads(workflow["context_json"])
    steps = json.loads(workflow["steps_json"])
    total = workflow["total_steps"]
    resumed = ctx.get("_resumed")

    if not resumed:
        # Step 0: Find stale candidates
        yield _step(wid, 0, total, steps[0]["label"], "running")
        _update_steps(wid, steps, 0, "running")

        days_stale = ctx.get("days_stale", 3)
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
            _update_steps(wid, steps, 0, "done")
            db.update_workflow(wid, {"status": "done", "updated_at": datetime.now().isoformat()})
            yield _done(session_id, f"Pipeline is clean! No candidates have been waiting for more than {days_stale} days.",
                        workflow_id=wid, workflow_status="done")
            return

        _update_steps(wid, steps, 0, "done")
        yield _step(wid, 0, total, steps[0]["label"], "done")

        # Step 1: Categorize — simple heuristic based on age
        yield _step(wid, 1, total, steps[1]["label"], "running")
        _update_steps(wid, steps, 1, "running")

        actions = []
        for c in stale:
            updated = c.get("updated_at") or c.get("created_at", "")
            days = (datetime.now() - datetime.fromisoformat(updated)).days if updated else 0
            if days >= 14:
                actions.append({"id": c["id"], "name": c["name"], "action": "reject", "days": days})
            elif days >= 7:
                actions.append({"id": c["id"], "name": c["name"], "action": "archive", "days": days})
            else:
                actions.append({"id": c["id"], "name": c["name"], "action": "follow_up", "days": days})

        _update_steps(wid, steps, 1, "done")
        yield _step(wid, 1, total, steps[1]["label"], "done")

        # Pause for approval
        db.update_workflow(wid, {
            "status": "paused",
            "checkpoint_data_json": json.dumps({"actions": actions}),
            "updated_at": datetime.now().isoformat(),
        })

        preview = [
            {"label": a["name"], "detail": f"{a['action']} ({a['days']}d stale)"}
            for a in actions
        ]
        follow_ups = sum(1 for a in actions if a["action"] == "follow_up")
        rejects = sum(1 for a in actions if a["action"] == "reject")
        archives = sum(1 for a in actions if a["action"] == "archive")

        desc_parts = []
        if follow_ups:
            desc_parts.append(f"{follow_ups} follow-up")
        if rejects:
            desc_parts.append(f"{rejects} reject")
        if archives:
            desc_parts.append(f"{archives} archive")

        yield _approval(
            session_id=session_id,
            reply=f"Found **{len(stale)} stale candidates** in the pipeline. Here's my recommendation:\n\n"
                  + "\n".join(f"- **{a['name']}**: {a['action']} ({a['days']} days stale)" for a in actions),
            workflow_id=wid,
            title=f"Execute pipeline cleanup ({len(actions)} actions)?",
            description=f"Actions: {', '.join(desc_parts)}.",
            preview_items=preview,
            approve_label="Execute All",
        )
        return

    # ── Resumed after approval ──
    checkpoint = resumed
    actions = checkpoint.get("actions", [])

    yield _step(wid, 2, total, steps[2]["label"], "running")
    _update_steps(wid, steps, 2, "running")

    now = datetime.now().isoformat()
    for a in actions:
        cid = a["id"]
        action_type = a["action"]
        if action_type == "reject":
            db.update_candidate(cid, {"status": "rejected", "updated_at": now})
        elif action_type == "archive":
            db.update_candidate(cid, {"status": "withdrawn", "updated_at": now})
        # follow_up: keep status, just note it
        await asyncio.sleep(0)

    _update_steps(wid, steps, 2, "done")
    yield _step(wid, 2, total, steps[2]["label"], "done")

    db.update_workflow(wid, {"status": "done", "updated_at": now})
    yield _done(
        session_id,
        f"Pipeline cleanup complete! Processed **{len(actions)}** candidates.",
        workflow_id=wid, workflow_status="done",
    )


# ── Workflow: Job Launch ───────────────────────────────────────────────────


async def _run_job_launch(
    cfg: Config, workflow: dict, user_id: str, session_id: str,
) -> AsyncGenerator[dict, None]:
    wid = workflow["id"]
    ctx = json.loads(workflow["context_json"])
    steps = json.loads(workflow["steps_json"])
    total = workflow["total_steps"]
    loop = asyncio.get_running_loop()
    resumed = ctx.get("_resumed")

    if not resumed:
        # Step 0: Load job
        yield _step(wid, 0, total, steps[0]["label"], "running")
        _update_steps(wid, steps, 0, "running")

        job_id = ctx.get("job_id", "")
        job = db.get_job(job_id) if job_id else None

        # If no job_id, try the most recent job
        if not job:
            jobs = db.list_jobs()
            if jobs:
                job = jobs[0]
                job_id = job["id"]

        if not job:
            db.update_workflow(wid, {"status": "done", "updated_at": datetime.now().isoformat()})
            yield _done(session_id, "No job found. Please upload a job description first.",
                        workflow_id=wid, workflow_status="done")
            return

        _update_steps(wid, steps, 0, "done")
        yield _step(wid, 0, total, steps[0]["label"], "done")

        # Step 1: Find matching candidates
        yield _step(wid, 1, total, steps[1]["label"], "running")
        _update_steps(wid, steps, 1, "running")

        from app.agents.matching import rank_candidates_for_job
        top_k = ctx.get("top_k", 5)
        ranked = await loop.run_in_executor(None, rank_candidates_for_job, job_id, None, top_k)

        _update_steps(wid, steps, 1, "done")
        yield _step(wid, 1, total, steps[1]["label"], "done")

        if not ranked:
            db.update_workflow(wid, {"status": "done", "updated_at": datetime.now().isoformat()})
            yield _done(session_id, f"No matching candidates found for **{job['title']}**. Upload some resumes first.",
                        workflow_id=wid, workflow_status="done")
            return

        # Step 2: Rank candidates (already done by rank_candidates_for_job)
        yield _step(wid, 2, total, steps[2]["label"], "running")
        _update_steps(wid, steps, 2, "done")
        yield _step(wid, 2, total, steps[2]["label"], "done")

        # Step 3: Draft outreach batch
        yield _step(wid, 3, total, steps[3]["label"], "running")
        _update_steps(wid, steps, 3, "running")

        from app.agents.communication import draft_email
        from app.models import Email

        drafted_emails = []
        for c_data in ranked[:top_k]:
            c = c_data if isinstance(c_data, dict) else {}
            cid = c.get("id", "")
            cname = c.get("name", "")
            if not cid or not cname:
                continue
            draft = await loop.run_in_executor(
                None, draft_email, cfg, cid, job_id, "outreach", "",
            )
            email = Email(
                candidate_id=cid, candidate_name=cname,
                to_email=c.get("email", ""), subject=draft.get("subject", "(no subject)"),
                body=draft.get("body", ""), email_type="outreach",
            )
            db.insert_email(email.model_dump())
            drafted_emails.append({
                "id": email.id, "candidate_name": cname,
                "to_email": c.get("email", ""), "subject": draft.get("subject", ""),
            })
            await asyncio.sleep(0)

        _update_steps(wid, steps, 3, "done")
        yield _step(wid, 3, total, steps[3]["label"], "done")

        # Pause for approval
        db.update_workflow(wid, {
            "status": "paused",
            "checkpoint_data_json": json.dumps({
                "drafted_emails": drafted_emails,
                "job_id": job_id,
                "job_title": job.get("title", ""),
            }),
            "updated_at": datetime.now().isoformat(),
        })

        preview = [{"label": e["candidate_name"], "detail": e["subject"]} for e in drafted_emails]
        yield _approval(
            session_id=session_id,
            reply=f"Job launch ready for **{job['title']}**! Found **{len(ranked)}** candidates and drafted **{len(drafted_emails)}** outreach emails.",
            workflow_id=wid,
            title=f"Send {len(drafted_emails)} outreach emails for {job['title']}?",
            description="Emails will be sent immediately after approval.",
            preview_items=preview,
            approve_label="Launch Outreach",
        )
        return

    # ── Resumed after approval: send emails ──
    checkpoint = resumed
    drafted_emails = checkpoint.get("drafted_emails", [])

    yield _step(wid, 4, total, steps[4]["label"], "running")
    _update_steps(wid, steps, 4, "running")

    from app.tools.email_sender import send_email as send_one
    from app.routes.settings import get_config

    email_cfg = get_config()
    sent_count = 0
    for e in drafted_emails:
        try:
            email_row = db.get_email(e["id"])
            if not email_row:
                continue
            result = send_one(
                backend=email_cfg.email_backend, from_email=email_cfg.email_from,
                to_email=email_row["to_email"], subject=email_row["subject"],
                body=email_row["body"],
                smtp_host=email_cfg.smtp_host, smtp_port=email_cfg.smtp_port,
                smtp_username=email_cfg.smtp_username, smtp_password=email_cfg.smtp_password,
            )
            if result.get("status") == "ok":
                db.update_email(e["id"], {
                    "approved": True, "sent": True,
                    "sent_at": datetime.now().isoformat(),
                    "message_id": result.get("message_id", ""),
                })
                sent_count += 1
            if email_row.get("candidate_id"):
                db.update_candidate(email_row["candidate_id"], {
                    "status": "contacted", "updated_at": datetime.now().isoformat(),
                })
        except Exception as exc:
            log.error("Failed to send email %s: %s", e["id"], exc)
        await asyncio.sleep(0)

    _update_steps(wid, steps, 4, "done")
    yield _step(wid, 4, total, steps[4]["label"], "done")

    db.update_workflow(wid, {"status": "done", "updated_at": datetime.now().isoformat()})
    job_title = checkpoint.get("job_title", "the role")
    yield _done(
        session_id,
        f"Job launch complete for **{job_title}**! Sent **{sent_count}/{len(drafted_emails)}** outreach emails.",
        workflow_id=wid, workflow_status="done",
    )
