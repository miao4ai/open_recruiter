"""Email routes — CRUD, draft, approve, send."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app import database as db
from app.models import Email, EmailDraftRequest

router = APIRouter()


@router.get("")
async def list_emails_route(candidate_id: str | None = Query(None)):
    return db.list_emails(candidate_id=candidate_id)


@router.post("/draft")
async def draft_email(req: EmailDraftRequest):
    """Generate an email draft. Phase 2 will use the Communication Agent."""
    candidate = db.get_candidate(req.candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Phase 1: placeholder draft
    email = Email(
        candidate_id=req.candidate_id,
        candidate_name=candidate["name"],
        to_email=candidate.get("email", ""),
        subject=f"Exciting opportunity for {candidate['name']}",
        body=f"Hi {candidate['name']},\n\nI came across your profile and thought you'd be a great fit for a role we're hiring for.\n\nWould you be open to a quick chat?\n\nBest regards",
        email_type=req.email_type,
    )
    db.insert_email(email.model_dump())
    return email.model_dump()


@router.get("/pending")
async def pending_emails():
    all_emails = db.list_emails()
    return [e for e in all_emails if not e["sent"] and not e["approved"]]


@router.get("/followups")
async def followup_emails():
    all_emails = db.list_emails()
    return [e for e in all_emails if e["sent"] and not e["reply_received"]]


@router.post("/{email_id}/approve")
async def approve_email(email_id: str):
    email = db.get_email(email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    db.update_email(email_id, {"approved": True})
    return {"status": "approved"}


@router.post("/{email_id}/send")
async def send_email(email_id: str):
    email = db.get_email(email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    # Phase 1: just mark as sent
    db.update_email(email_id, {"sent": True, "sent_at": datetime.now().isoformat()})
    # Update candidate status
    if email["candidate_id"]:
        db.update_candidate(email["candidate_id"], {
            "status": "contacted",
            "updated_at": datetime.now().isoformat(),
        })
    return {"status": "sent"}
