"""Job seeker routes — read-only job browsing and keyword search."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app import database as db
from app.auth import get_current_user

router = APIRouter()
log = logging.getLogger(__name__)


def _require_job_seeker(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "job_seeker":
        raise HTTPException(status_code=403, detail="Job seeker access only")
    return current_user


@router.get("/jobs")
async def list_jobs_for_seeker(
    q: str = Query("", description="Search keyword"),
    _user: dict = Depends(_require_job_seeker),
):
    """List all jobs for job seekers (read-only). Optional keyword filter."""
    jobs = db.list_jobs()
    # Strip candidate_count — seekers shouldn't see recruiter metrics
    for j in jobs:
        j.pop("candidate_count", None)
        j.pop("raw_text", None)

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
async def get_job_for_seeker(
    job_id: str,
    _user: dict = Depends(_require_job_seeker),
):
    """Get a single job detail (read-only)."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.pop("candidate_count", None)
    return job
