"""Job seeker profile routes — get, update, and upload resume."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app import database as db
from app.auth import get_current_user
from app.models import JobSeekerProfileUpdate

router = APIRouter()
log = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("")
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Get the current job seeker's profile."""
    if current_user.get("role") != "job_seeker":
        raise HTTPException(status_code=403, detail="Only job seekers can access profiles")
    profile = db.get_job_seeker_profile_by_user(current_user["id"])
    if not profile:
        return {
            "id": "",
            "user_id": current_user["id"],
            "name": current_user.get("name", ""),
            "email": current_user.get("email", ""),
            "phone": "",
            "current_title": "",
            "current_company": "",
            "skills": [],
            "experience_years": None,
            "location": "",
            "resume_summary": "",
            "resume_path": "",
            "created_at": "",
            "updated_at": "",
        }
    return profile


@router.put("")
async def update_profile(
    update: JobSeekerProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update the current job seeker's profile fields."""
    if current_user.get("role") != "job_seeker":
        raise HTTPException(status_code=403, detail="Only job seekers can access profiles")
    updates = update.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    profile = db.upsert_job_seeker_profile(current_user["id"], updates)
    return profile


@router.post("/upload-resume")
async def upload_resume_for_profile(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload a resume, parse it, and create/update the job seeker's profile."""
    if current_user.get("role") != "job_seeker":
        raise HTTPException(status_code=403, detail="Only job seekers can access profiles")

    file_bytes = await file.read()
    filename = file.filename or "resume"

    # Save file
    save_path = UPLOAD_DIR / f"seeker_{current_user['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
    save_path.write_bytes(file_bytes)

    # Extract text
    from app.tools.resume_parser import extract_text

    try:
        raw_text = extract_text(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # LLM parsing
    parsed: dict = {}
    try:
        from app.routes.settings import get_config

        cfg = get_config()
        has_key = (
            cfg.llm_provider == "ollama"
            or (cfg.llm_provider == "anthropic" and cfg.anthropic_api_key)
            or (cfg.llm_provider == "openai" and cfg.openai_api_key)
            or (cfg.llm_provider == "gemini" and cfg.gemini_api_key)
        )
        if has_key:
            from app.agents.resume import parse_resume_text

            parsed = parse_resume_text(cfg, raw_text)
        else:
            log.warning("No LLM API key — skipping structured parsing.")
    except Exception as e:
        log.error("LLM resume parsing failed: %s", e)

    # Upsert profile
    profile_data = {
        "name": parsed.get("name") or current_user.get("name", ""),
        "email": parsed.get("email") or current_user.get("email", ""),
        "phone": parsed.get("phone", ""),
        "current_title": parsed.get("current_title", ""),
        "current_company": parsed.get("current_company", ""),
        "skills": parsed.get("skills", []),
        "experience_years": parsed.get("experience_years"),
        "location": parsed.get("location", ""),
        "resume_summary": parsed.get("resume_summary", "") or raw_text[:500],
        "resume_path": str(save_path),
        "raw_resume_text": raw_text[:5000],
    }
    profile = db.upsert_job_seeker_profile(current_user["id"], profile_data)

    return profile
