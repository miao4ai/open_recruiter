"""Candidate routes — CRUD, resume upload, matching."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Query

from app import database as db
from app.models import Candidate, CandidateUpdate, MatchRequest

router = APIRouter()


@router.get("")
async def list_candidates_route(
    job_id: str | None = Query(None),
    status: str | None = Query(None),
):
    return db.list_candidates(job_id=job_id, status=status)


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...), job_id: str = ""):
    """Upload a resume file. Phase 2 will parse it with the Resume Agent."""
    content = await file.read()
    # Phase 1: store file metadata, placeholder candidate
    candidate = Candidate(
        name=file.filename or "Unknown",
        resume_path=file.filename or "",
        resume_summary=f"Uploaded file: {file.filename} ({len(content)} bytes)",
        job_id=job_id,
    )
    db.insert_candidate(candidate.model_dump())
    return candidate.model_dump()


@router.get("/{candidate_id}")
async def get_candidate_route(candidate_id: str):
    c = db.get_candidate(candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return c


@router.patch("/{candidate_id}")
async def update_candidate_route(candidate_id: str, update: CandidateUpdate):
    updates = update.model_dump(exclude_none=True)
    updates["updated_at"] = datetime.now().isoformat()
    if not db.update_candidate(candidate_id, updates):
        raise HTTPException(status_code=404, detail="Candidate not found")
    return db.get_candidate(candidate_id)


@router.post("/match")
async def match_candidates(req: MatchRequest):
    """Match selected candidates against a job. Phase 2 will use the Matching Agent."""
    # Phase 1: return mock scores
    results = []
    for cid in req.candidate_ids:
        c = db.get_candidate(cid)
        if c:
            results.append({
                "candidate_id": cid,
                "candidate_name": c["name"],
                "score": 0.0,
                "strengths": [],
                "gaps": [],
                "reasoning": "Matching not yet implemented — coming in Phase 2.",
            })
    return results
