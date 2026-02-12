"""Job routes — CRUD + JD parsing."""

import logging

from fastapi import APIRouter, HTTPException

from app import database as db
from app import vectorstore
from app.models import Job, JobCreate

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def list_jobs_route():
    return db.list_jobs()


@router.post("")
async def create_job(req: JobCreate):
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
async def get_job_route(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}")
async def delete_job_route(job_id: str):
    if not db.delete_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        vectorstore.remove_job(job_id)
    except Exception:
        pass  # Non-fatal: embedding cleanup is best-effort

    return {"status": "deleted"}
