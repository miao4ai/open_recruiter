"""Job routes — CRUD + JD parsing."""

from fastapi import APIRouter, HTTPException

from app import database as db
from app.models import Job, JobCreate

router = APIRouter()


@router.get("")
async def list_jobs_route():
    return db.list_jobs()


@router.post("")
async def create_job(req: JobCreate):
    """Create a job by pasting raw JD text. Agent will parse it later (Phase 2)."""
    job = Job(raw_text=req.raw_text)

    # Phase 1: store raw text, placeholder title
    # Phase 2: call LLM to parse JD and fill fields
    if not job.title:
        # Simple heuristic: first non-empty line as title
        lines = [l.strip() for l in req.raw_text.strip().splitlines() if l.strip()]
        job.title = lines[0][:100] if lines else "Untitled Position"

    db.insert_job(job.model_dump())
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
    return {"status": "deleted"}
