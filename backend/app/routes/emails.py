"""Email routes — CRUD, draft, compose, approve, send."""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form

from app import database as db
from app.auth import get_current_user
from app.models import Email, EmailComposeRequest, EmailDraftRequest

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()


@router.get("")
async def list_emails_route(candidate_id: str | None = Query(None), _user: dict = Depends(get_current_user)):
    return db.list_emails(candidate_id=candidate_id)


@router.post("/draft")
async def draft_email(req: EmailDraftRequest, _user: dict = Depends(get_current_user)):
    """Generate an email draft from a candidate."""
    candidate = db.get_candidate(req.candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

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


@router.post("/compose")
async def compose_email(req: EmailComposeRequest, current_user: dict = Depends(get_current_user)):
    """Compose and save a new email directly (from the Outreach page modal)."""
    email = Email(
        candidate_id=req.candidate_id,
        candidate_name=req.candidate_name,
        to_email=req.to_email,
        subject=req.subject,
        body=req.body,
        email_type=req.email_type,
    )
    db.insert_email(email.model_dump())
    return email.model_dump()


@router.post("/compose-with-attachment")
async def compose_email_with_attachment(
    to_email: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    email_type: str = Form("outreach"),
    candidate_id: str = Form(""),
    candidate_name: str = Form(""),
    job_id: str = Form(""),
    use_candidate_resume: str = Form("false"),
    attachment: UploadFile | None = File(None),
    current_user: dict = Depends(get_current_user),
):
    """Compose an email with optional PDF attachment."""
    attachment_path = ""

    # If a file was uploaded, save it
    if attachment and attachment.filename:
        file_bytes = await attachment.read()
        save_path = UPLOAD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{attachment.filename}"
        save_path.write_bytes(file_bytes)
        attachment_path = str(save_path)
    # Otherwise, if use_candidate_resume is true, use the candidate's existing resume
    elif use_candidate_resume == "true" and candidate_id:
        candidate = db.get_candidate(candidate_id)
        if candidate and candidate.get("resume_path"):
            attachment_path = candidate["resume_path"]

    email = Email(
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        to_email=to_email,
        subject=subject,
        body=body,
        email_type=email_type,
        attachment_path=attachment_path,
    )
    db.insert_email(email.model_dump())
    return email.model_dump()


@router.get("/pending")
async def pending_emails(_user: dict = Depends(get_current_user)):
    all_emails = db.list_emails()
    return [e for e in all_emails if not e["sent"] and not e["approved"]]


@router.get("/followups")
async def followup_emails(_user: dict = Depends(get_current_user)):
    all_emails = db.list_emails()
    return [e for e in all_emails if e["sent"] and not e["reply_received"]]


@router.post("/{email_id}/approve")
async def approve_email(email_id: str, _user: dict = Depends(get_current_user)):
    email = db.get_email(email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    db.update_email(email_id, {"approved": True})
    return {"status": "approved"}


@router.post("/{email_id}/send")
async def send_email(email_id: str, current_user: dict = Depends(get_current_user)):
    """Actually send the email via configured backend, then mark as sent."""
    email = db.get_email(email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    # Load email config
    from app.routes.settings import get_config
    cfg = get_config()

    from app.tools.email_sender import send_email as do_send
    result = do_send(
        backend=cfg.email_backend,
        from_email=current_user["email"],
        to_email=email["to_email"],
        subject=email["subject"],
        body=email["body"],
        smtp_host=cfg.smtp_host,
        smtp_port=cfg.smtp_port,
        smtp_username=cfg.smtp_username,
        smtp_password=cfg.smtp_password,
        attachment_path=email.get("attachment_path", ""),
    )

    if result["status"] != "ok":
        raise HTTPException(status_code=500, detail=result.get("message", "Failed to send email"))

    # Mark as sent
    db.update_email(email_id, {"sent": True, "sent_at": datetime.now().isoformat()})
    # Update candidate status if linked
    if email["candidate_id"]:
        db.update_candidate(email["candidate_id"], {
            "status": "contacted",
            "updated_at": datetime.now().isoformat(),
        })
    return {"status": "sent", "message": result.get("message", "")}


@router.put("/{email_id}")
async def update_email_route(email_id: str, req: EmailComposeRequest, _user: dict = Depends(get_current_user)):
    """Update a draft email."""
    email = db.get_email(email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    if email["sent"]:
        raise HTTPException(status_code=400, detail="Cannot edit a sent email")
    db.update_email(email_id, {
        "to_email": req.to_email,
        "subject": req.subject,
        "body": req.body,
        "email_type": req.email_type.value if hasattr(req.email_type, "value") else req.email_type,
        "candidate_id": req.candidate_id,
        "candidate_name": req.candidate_name,
    })
    return db.get_email(email_id)


@router.delete("/{email_id}")
async def delete_email(email_id: str, _user: dict = Depends(get_current_user)):
    email = db.get_email(email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    conn = db.get_conn()
    conn.execute("DELETE FROM emails WHERE id = ?", (email_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}
