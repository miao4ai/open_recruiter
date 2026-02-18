"""Job routes — CRUD + JD parsing."""

import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app import database as db
from app import vectorstore
from app.auth import get_current_user
from app.models import Job, JobCreate, JobUpdate

log = logging.getLogger(__name__)

router = APIRouter()

MATCH_THRESHOLD = 0.30  # minimum cosine similarity to count as a match

JD_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "jds"
JD_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("")
async def list_jobs_route(_user: dict = Depends(get_current_user)):
    jobs = db.list_jobs()
    # Enrich with vector-based match counts
    for j in jobs:
        try:
            rankings = vectorstore.search_candidates_for_job(
                job_id=j["id"], n_results=200,
            )
            j["candidate_count"] = sum(
                1 for r in rankings if r["score"] >= MATCH_THRESHOLD
            )
        except Exception:
            pass  # Keep the DB-based count as fallback
    return jobs


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


@router.post("/upload")
async def upload_jd(
    file: UploadFile = File(...),
    _user: dict = Depends(get_current_user),
):
    """Upload a JD file (PDF / DOCX / TXT).

    Pipeline:
      1. Save file to disk
      2. Extract raw text (PyMuPDF / python-docx)
      3. LLM parses text into structured fields
      4. Store Job in SQLite + index in ChromaDB
    """
    from app.tools.resume_parser import extract_text

    file_bytes = await file.read()
    filename = file.filename or "jd"

    # 1. Save file
    save_path = JD_UPLOAD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
    save_path.write_bytes(file_bytes)

    # 2. Extract text
    try:
        raw_text = extract_text(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3. LLM structured parsing
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
        else:
            log.warning("No LLM API key configured — skipping JD parsing.")
    except Exception as e:
        log.error("LLM JD parsing failed: %s", e)

    # 4. Build Job and store
    job = Job(
        title=parsed.get("title", "") or _guess_title(filename),
        company=parsed.get("company", ""),
        posted_date=datetime.now().strftime("%Y-%m-%d"),
        required_skills=parsed.get("required_skills", []),
        preferred_skills=parsed.get("preferred_skills", []),
        experience_years=parsed.get("experience_years"),
        location=parsed.get("location", ""),
        remote=parsed.get("remote", False),
        salary_range=parsed.get("salary_range", ""),
        summary=parsed.get("summary", ""),
        raw_text=raw_text,
    )
    db.insert_job(job.model_dump())

    # 5. Index in ChromaDB
    try:
        vectorstore.index_job(
            job_id=job.id,
            text=job.raw_text,
            metadata={"title": job.title, "company": job.company},
        )
    except Exception as e:
        log.warning("Failed to index job in vector store: %s", e)

    return job.model_dump()


def _guess_title(filename: str) -> str:
    """Best-effort title from filename."""
    stem = Path(filename).stem
    for word in ("jd", "JD", "job_description", "Job_Description"):
        stem = stem.replace(word, "")
    name = stem.replace("_", " ").replace("-", " ").strip()
    return name if name else "Untitled Position"


@router.get("/{job_id}")
async def get_job_route(job_id: str, _user: dict = Depends(get_current_user)):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/ranked-candidates")
async def ranked_candidates_route(job_id: str, _user: dict = Depends(get_current_user)):
    """Return candidates linked to this job, ranked by match score."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get candidates linked to this job (already includes match_score from candidate_jobs)
    candidates = db.list_candidates(job_id=job_id)

    # Also enrich with vector scores for any that haven't been LLM-matched yet
    try:
        rankings = vectorstore.search_candidates_for_job(
            job_id=job_id, n_results=200,
        )
        score_map = {r["candidate_id"]: r["score"] for r in rankings}
        for c in candidates:
            if c.get("match_score", 0.0) == 0.0:
                c["match_score"] = score_map.get(c["id"], 0.0)
    except Exception as e:
        log.warning("Vector search failed for job %s: %s", job_id, e)

    candidates.sort(key=lambda c: c["match_score"], reverse=True)
    return candidates


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
        pass  # Non-fatal

    return {"status": "deleted"}


def _auto_match_candidates_for_job(job_id: str) -> None:
    """Re-run vector-based matching for all candidates linked to a job."""
    candidates = db.list_candidates(job_id=job_id)
    if not candidates:
        return

    rankings = vectorstore.search_candidates_for_job(
        job_id=job_id, n_results=200,
    )
    score_map = {r["candidate_id"]: r["score"] for r in rankings}

    for c in candidates:
        score = score_map.get(c["id"], 0.0)
        db.update_candidate_job(c["id"], job_id, {
            "match_score": score,
            "updated_at": datetime.now().isoformat(),
        })
