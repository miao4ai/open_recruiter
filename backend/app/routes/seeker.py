"""Job seeker routes — manage their own saved jobs (fully isolated from recruiter data)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File

from app import database as db
from app.auth import get_current_user

router = APIRouter()
log = logging.getLogger(__name__)

JD_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "seeker_jds"
JD_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _require_job_seeker(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "job_seeker":
        raise HTTPException(status_code=403, detail="Job seeker access only")
    return current_user


@router.get("/jobs")
async def list_seeker_jobs(
    q: str = Query("", description="Search keyword"),
    current_user: dict = Depends(_require_job_seeker),
):
    """List the job seeker's own saved jobs. Optional keyword filter."""
    jobs = db.list_seeker_jobs(current_user["id"])

    if q.strip():
        kw = q.strip().lower()
        jobs = [
            j for j in jobs
            if kw in (j.get("title") or "").lower()
            or kw in (j.get("company") or "").lower()
            or kw in (j.get("location") or "").lower()
            or kw in (j.get("summary") or "").lower()
            or kw in (j.get("salary_range") or "").lower()
            or any(kw in s.lower() for s in j.get("required_skills", []))
            or any(kw in s.lower() for s in j.get("preferred_skills", []))
        ]

    return jobs


@router.get("/jobs/{job_id}")
async def get_seeker_job(
    job_id: str,
    current_user: dict = Depends(_require_job_seeker),
):
    """Get a single saved job detail."""
    job = db.get_seeker_job(job_id)
    if not job or job["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/upload")
async def upload_jd_for_seeker(
    file: UploadFile = File(...),
    current_user: dict = Depends(_require_job_seeker),
):
    """Upload a JD file, parse it with LLM, and save as a seeker job."""
    from app.tools.resume_parser import extract_text

    file_bytes = await file.read()
    filename = file.filename or "jd"

    save_path = JD_UPLOAD_DIR / f"seeker_{current_user['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
    save_path.write_bytes(file_bytes)

    try:
        raw_text = extract_text(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    parsed: dict = {}
    try:
        from app.routes.settings import get_config
        cfg = get_config()
        has_key = (
            (cfg.llm_provider == "anthropic" and cfg.anthropic_api_key)
            or (cfg.llm_provider == "openai" and cfg.openai_api_key)
        )
        if has_key:
            from app.agents.jd import parse_jd_text
            parsed = parse_jd_text(cfg, raw_text)
    except Exception as e:
        log.error("LLM JD parsing failed: %s", e)

    job = {
        "id": uuid.uuid4().hex[:8],
        "user_id": current_user["id"],
        "title": parsed.get("title", "") or filename,
        "company": parsed.get("company", ""),
        "posted_date": datetime.now().strftime("%Y-%m-%d"),
        "required_skills": parsed.get("required_skills", []),
        "preferred_skills": parsed.get("preferred_skills", []),
        "experience_years": parsed.get("experience_years"),
        "location": parsed.get("location", ""),
        "remote": parsed.get("remote", False),
        "salary_range": parsed.get("salary_range", ""),
        "summary": parsed.get("summary", ""),
        "raw_text": raw_text,
        "created_at": datetime.now().isoformat(),
    }
    db.insert_seeker_job(job)
    return db.get_seeker_job(job["id"])


@router.delete("/jobs/{job_id}")
async def delete_seeker_job(
    job_id: str,
    current_user: dict = Depends(_require_job_seeker),
):
    """Delete a saved job."""
    job = db.get_seeker_job(job_id)
    if not job or job["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete_seeker_job(job_id)
    return {"status": "deleted"}
