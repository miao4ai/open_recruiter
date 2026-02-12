"""Job routes — CRUD + JD parsing."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app import database as db
from app import vectorstore
from app.auth import get_current_user
from app.models import Job, JobCreate, JobUpdate

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def list_jobs_route(_user: dict = Depends(get_current_user)):
    return db.list_jobs()


@router.post("")
async def create_job(req: JobCreate, _user: dict = Depends(get_current_user)):
    """Create a job from user-provided fields."""
    title = req.title.strip() if req.title else ""
    if not title:
        title = "Untitled Position"

    job = Job(
        title=title,
        company=req.company,
        posted_date=req.posted_date,
        raw_text=req.raw_text,
    )

    db.insert_job(job.model_dump())

    try:
        vectorstore.index_job(
            job_id=job.id,
            text=job.raw_text,
            metadata={"title": job.title, "company": job.company},
        )
    except Exception as e:
        log.warning("Failed to index job in vector store: %s", e)

    return job.model_dump()


@router.get("/{job_id}")
async def get_job_route(job_id: str, _user: dict = Depends(get_current_user)):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.put("/{job_id}")
async def update_job_route(job_id: str, req: JobUpdate, _user: dict = Depends(get_current_user)):
    """Update a job's editable fields."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    updates = req.model_dump(exclude_none=True)
    if not updates:
        return job
    db.update_job(job_id, updates)

    updated_job = db.get_job(job_id)

    # Re-index in vector store
    try:
        vectorstore.index_job(
            job_id=job_id,
            text=updated_job.get("raw_text", ""),
            metadata={"title": updated_job.get("title", ""), "company": updated_job.get("company", "")},
        )
    except Exception as e:
        log.warning("Failed to reindex job in vector store: %s", e)

    # Auto-match: re-run vector scoring for candidates linked to this job
    try:
        _auto_match_candidates_for_job(job_id)
    except Exception as e:
        log.warning("Auto-match failed for job %s: %s", job_id, e)

    return updated_job


@router.delete("/{job_id}")
async def delete_job_route(job_id: str, _user: dict = Depends(get_current_user)):
    if not db.delete_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        vectorstore.remove_job(job_id)
    except Exception:
        pass  # Non-fatal: embedding cleanup is best-effort

    return {"status": "deleted"}


def _auto_match_candidates_for_job(job_id: str) -> None:
    """Re-run vector-based matching for all candidates linked to a job."""
    candidates = db.list_candidates(job_id=job_id)
    if not candidates:
        return

    rankings = vectorstore.search_candidates_for_job(
        job_id=job_id, n_results=100, job_id_filter=job_id,
    )
    score_map = {r["candidate_id"]: r["score"] for r in rankings}

    for c in candidates:
        score = score_map.get(c["id"], 0.0)
        db.update_candidate(c["id"], {
            "match_score": score,
            "updated_at": datetime.now().isoformat(),
        })
