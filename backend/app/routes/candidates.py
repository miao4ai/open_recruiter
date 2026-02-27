"""Candidate routes — CRUD, resume upload, matching."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query

from app import database as db
from app import vectorstore
from app.auth import get_current_user
from app.models import Candidate, CandidateUpdate, MatchRequest, PipelineStatusUpdate

router = APIRouter()
log = logging.getLogger(__name__)

# Directory to persist uploaded resume files
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("")
async def list_candidates_route(
    job_id: str | None = Query(None),
    status: str | None = Query(None),
    _user: dict = Depends(get_current_user),
):
    return db.list_candidates(job_id=job_id, status=status)


_STATUS_ORDER = [
    "new", "contacted", "replied", "screening",
    "interview_scheduled", "interviewed", "offer_sent", "hired",
    "rejected", "withdrawn",
]


def _sync_candidate_global_status(candidate_id: str) -> None:
    """Set candidate.status to the most advanced pipeline_status across all jobs."""
    cjs = db.list_candidate_jobs(candidate_id=candidate_id)
    if not cjs:
        return
    statuses = [cj.get("pipeline_status", "new") for cj in cjs]
    active = [s for s in statuses if s not in ("rejected", "withdrawn")]
    if not active:
        best = statuses[0]
    else:
        best = max(active, key=lambda s: _STATUS_ORDER.index(s) if s in _STATUS_ORDER else 0)
    db.update_candidate(candidate_id, {"status": best, "updated_at": datetime.now().isoformat()})


@router.get("/pipeline")
async def list_pipeline(
    view: str = Query("candidate"),
    _user: dict = Depends(get_current_user),
):
    """Return pipeline entries (candidate-job pairs) for the pipeline bar."""
    return db.list_pipeline_entries()


@router.patch("/pipeline/{candidate_id}/{job_id}")
async def update_pipeline_status(
    candidate_id: str,
    job_id: str,
    body: PipelineStatusUpdate,
    _user: dict = Depends(get_current_user),
):
    """Update pipeline status for a specific candidate-job pair."""
    if not db.update_candidate_job(candidate_id, job_id, {
        "pipeline_status": body.pipeline_status,
        "updated_at": datetime.now().isoformat(),
    }):
        raise HTTPException(status_code=404, detail="Candidate-job link not found")
    _sync_candidate_global_status(candidate_id)
    return {"status": "updated"}


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...), job_id: str = Form(""), _user: dict = Depends(get_current_user)):
    """Upload a resume file (PDF / DOCX / TXT).

    Pipeline:
      1. Save file to disk
      2. PyMuPDF extracts raw text
      3. LLM parses text into structured fields
      4. Find-or-create Candidate in SQLite
      5. Create candidate_jobs link
    """
    file_bytes = await file.read()
    filename = file.filename or "resume"

    # ── Step 1: save file ──────────────────────────────────────────────
    save_path = UPLOAD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
    save_path.write_bytes(file_bytes)

    # ── Step 2: extract text ───────────────────────────────────────────
    from app.tools.resume_parser import extract_text

    try:
        raw_text = extract_text(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ── Step 3: LLM structured parsing ─────────────────────────────────
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
            log.warning("No LLM API key configured — skipping structured parsing.")
    except Exception as e:
        log.error("LLM resume parsing failed: %s", e)

    # ── Step 4: Find-or-create candidate ───────────────────────────────
    parsed_name = parsed.get("name") or _guess_name(filename)
    parsed_email = parsed.get("email", "")
    parsed_dob = parsed.get("date_of_birth", "")

    existing = None
    if parsed_name and parsed_email:
        existing = db.find_candidate_by_identity(parsed_name, parsed_email, parsed_dob)

    if existing:
        candidate_id = existing["id"]
        # Check if already linked to this job
        if job_id:
            cj = db.get_candidate_job(candidate_id, job_id)
            if cj:
                raise HTTPException(
                    status_code=409,
                    detail=f"Candidate '{parsed_name}' is already linked to this job.",
                )
    else:
        # Create new candidate
        candidate = Candidate(
            name=parsed_name,
            email=parsed.get("email", ""),
            phone=parsed.get("phone", ""),
            current_title=parsed.get("current_title", ""),
            current_company=parsed.get("current_company", ""),
            skills=parsed.get("skills", []),
            experience_years=parsed.get("experience_years"),
            location=parsed.get("location", ""),
            date_of_birth=parsed_dob,
            resume_path=str(save_path),
            resume_summary=parsed.get("resume_summary", "") or raw_text[:500],
        )
        db.insert_candidate(candidate.model_dump())
        candidate_id = candidate.id

        # Index in vector store
        try:
            embed_text = vectorstore.build_candidate_embed_text(candidate)
            vectorstore.index_candidate(
                candidate_id=candidate_id,
                text=embed_text,
                metadata={
                    "name": candidate.name,
                    "current_title": candidate.current_title,
                },
            )
        except Exception as e:
            log.warning("Failed to index candidate in vector store: %s", e)

    # ── Step 5: Create candidate_jobs link ─────────────────────────────
    if job_id:
        now = datetime.now().isoformat()
        db.insert_candidate_job({
            "id": uuid.uuid4().hex[:8],
            "candidate_id": candidate_id,
            "job_id": job_id,
            "match_score": 0.0,
            "created_at": now,
            "updated_at": now,
        })

        # Auto-match: vector similarity score
        try:
            rankings = vectorstore.search_candidates_for_job(
                job_id=job_id, n_results=200,
            )
            score_map = {r["candidate_id"]: r["score"] for r in rankings}
            score = score_map.get(candidate_id, 0.0)
            db.update_candidate_job(candidate_id, job_id, {
                "match_score": score,
                "updated_at": datetime.now().isoformat(),
            })
        except Exception as e:
            log.warning("Auto-match failed for candidate %s: %s", candidate_id, e)

    return db.get_candidate(candidate_id)


@router.get("/{candidate_id}")
async def get_candidate_route(candidate_id: str, _user: dict = Depends(get_current_user)):
    c = db.get_candidate(candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return c


@router.patch("/{candidate_id}")
async def update_candidate_route(candidate_id: str, update: CandidateUpdate, _user: dict = Depends(get_current_user)):
    updates = update.model_dump(exclude_none=True)
    updates["updated_at"] = datetime.now().isoformat()
    if not db.update_candidate(candidate_id, updates):
        raise HTTPException(status_code=404, detail="Candidate not found")

    updated = db.get_candidate(candidate_id)

    # Re-index in vector store
    try:
        embed_text = vectorstore.build_candidate_embed_text(updated)
        vectorstore.index_candidate(
            candidate_id=candidate_id,
            text=embed_text,
            metadata={
                "name": updated.get("name", ""),
                "current_title": updated.get("current_title", ""),
            },
        )
    except Exception as e:
        log.warning("Failed to reindex candidate in vector store: %s", e)

    # Auto-match against all linked jobs
    try:
        _auto_match_candidate(updated)
    except Exception as e:
        log.warning("Auto-match failed for candidate %s: %s", candidate_id, e)

    return updated


@router.post("/{candidate_id}/reparse")
async def reparse_candidate_route(candidate_id: str, _user: dict = Depends(get_current_user)):
    """Re-run LLM parsing on an existing candidate's resume file."""
    c = db.get_candidate(candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")

    resume_path = c.get("resume_path", "")
    if not resume_path or not Path(resume_path).exists():
        raise HTTPException(status_code=400, detail="Resume file not found on disk")

    from app.routes.settings import get_config
    cfg = get_config()

    has_key = (
        cfg.llm_provider == "ollama"
        or (cfg.llm_provider == "anthropic" and cfg.anthropic_api_key)
        or (cfg.llm_provider == "openai" and cfg.openai_api_key)
        or (cfg.llm_provider == "gemini" and cfg.gemini_api_key)
    )
    if not has_key:
        raise HTTPException(status_code=400, detail="No LLM API key configured. Go to Settings first.")

    from app.tools.resume_parser import extract_text
    file_bytes = Path(resume_path).read_bytes()
    filename = Path(resume_path).name
    try:
        raw_text = extract_text(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.agents.resume import parse_resume_text
    parsed = parse_resume_text(cfg, raw_text)

    updates = {
        "name": parsed.get("name") or c.get("name", ""),
        "email": parsed.get("email") or c.get("email", ""),
        "phone": parsed.get("phone") or c.get("phone", ""),
        "current_title": parsed.get("current_title") or c.get("current_title", ""),
        "current_company": parsed.get("current_company") or c.get("current_company", ""),
        "skills": parsed.get("skills") or c.get("skills", []),
        "experience_years": parsed.get("experience_years"),
        "location": parsed.get("location") or c.get("location", ""),
        "date_of_birth": parsed.get("date_of_birth") or c.get("date_of_birth", ""),
        "resume_summary": parsed.get("resume_summary") or c.get("resume_summary", ""),
        "updated_at": datetime.now().isoformat(),
    }
    db.update_candidate(candidate_id, updates)

    updated = db.get_candidate(candidate_id)
    try:
        embed_text = vectorstore.build_candidate_embed_text(updated)
        vectorstore.index_candidate(
            candidate_id=candidate_id,
            text=embed_text,
            metadata={
                "name": updated.get("name", ""),
                "current_title": updated.get("current_title", ""),
            },
        )
    except Exception as e:
        log.warning("Failed to reindex candidate in vector store: %s", e)

    # Auto-match against all linked jobs
    try:
        _auto_match_candidate(updated)
    except Exception as e:
        log.warning("Auto-match failed for candidate %s: %s", candidate_id, e)

    return updated


@router.delete("/{candidate_id}")
async def delete_candidate_route(candidate_id: str, _user: dict = Depends(get_current_user)):
    if not db.delete_candidate(candidate_id):
        raise HTTPException(status_code=404, detail="Candidate not found")

    try:
        vectorstore.remove_candidate(candidate_id)
    except Exception:
        pass  # Non-fatal

    return {"status": "deleted"}


@router.post("/{candidate_id}/link-job")
async def link_candidate_job(candidate_id: str, job_id: str = Form(...), _user: dict = Depends(get_current_user)):
    """Link an existing candidate to a job."""
    c = db.get_candidate(candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    existing = db.get_candidate_job(candidate_id, job_id)
    if existing:
        raise HTTPException(status_code=409, detail="Candidate is already linked to this job.")

    now = datetime.now().isoformat()
    db.insert_candidate_job({
        "id": uuid.uuid4().hex[:8],
        "candidate_id": candidate_id,
        "job_id": job_id,
        "match_score": 0.0,
        "created_at": now,
        "updated_at": now,
    })

    # Auto-match
    try:
        rankings = vectorstore.search_candidates_for_job(job_id=job_id, n_results=200)
        score_map = {r["candidate_id"]: r["score"] for r in rankings}
        score = score_map.get(candidate_id, 0.0)
        db.update_candidate_job(candidate_id, job_id, {
            "match_score": score,
            "updated_at": datetime.now().isoformat(),
        })
    except Exception as e:
        log.warning("Auto-match failed for link %s→%s: %s", candidate_id, job_id, e)

    return db.get_candidate(candidate_id)


@router.delete("/{candidate_id}/jobs/{job_id}")
async def unlink_candidate_job(candidate_id: str, job_id: str, _user: dict = Depends(get_current_user)):
    """Unlink a candidate from a job."""
    if not db.delete_candidate_job(candidate_id, job_id):
        raise HTTPException(status_code=404, detail="Link not found")
    return {"status": "unlinked"}


@router.post("/match")
async def match_candidates(req: MatchRequest, _user: dict = Depends(get_current_user)):
    """Match selected candidates against a job using vector similarity + LLM."""
    from app.agents.matching import match_candidate_to_job, rank_candidates_for_job
    from app.routes.settings import get_config

    job = db.get_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Stage 1: vector similarity ranking
    rankings = rank_candidates_for_job(
        job_id=req.job_id,
        candidate_ids=req.candidate_ids,
    )
    vector_scores = {r["candidate_id"]: r["score"] for r in rankings}

    # Stage 2: LLM evaluation (optional)
    cfg = get_config()
    has_key = (
        cfg.llm_provider == "ollama"
        or (cfg.llm_provider == "anthropic" and cfg.anthropic_api_key)
        or (cfg.llm_provider == "openai" and cfg.openai_api_key)
        or (cfg.llm_provider == "gemini" and cfg.gemini_api_key)
    )

    results = []
    for cid in req.candidate_ids:
        c = db.get_candidate(cid)
        if not c:
            continue

        vscore = vector_scores.get(cid, 0.0)

        if has_key:
            match_data = match_candidate_to_job(cfg, req.job_id, cid)
        else:
            match_data = {
                "score": vscore,
                "strengths": [],
                "gaps": [],
                "reasoning": f"Vector similarity: {vscore:.2f} (configure LLM key for detailed evaluation)",
            }

        # Ensure candidate_jobs link exists, then update
        existing_cj = db.get_candidate_job(cid, req.job_id)
        now = datetime.now().isoformat()
        if not existing_cj:
            db.insert_candidate_job({
                "id": uuid.uuid4().hex[:8],
                "candidate_id": cid,
                "job_id": req.job_id,
                "match_score": match_data["score"],
                "match_reasoning": match_data["reasoning"],
                "strengths": match_data["strengths"],
                "gaps": match_data["gaps"],
                "created_at": now,
                "updated_at": now,
            })
        else:
            db.update_candidate_job(cid, req.job_id, {
                "match_score": match_data["score"],
                "match_reasoning": match_data["reasoning"],
                "strengths": match_data["strengths"],
                "gaps": match_data["gaps"],
                "updated_at": now,
            })

        results.append({
            "candidate_id": cid,
            "candidate_name": c["name"],
            "vector_score": vscore,
            "score": match_data["score"],
            "strengths": match_data["strengths"],
            "gaps": match_data["gaps"],
            "reasoning": match_data["reasoning"],
        })
    return results


def _auto_match_candidate(candidate: dict) -> None:
    """Re-run vector-based matching for a candidate against ALL linked jobs."""
    job_matches = candidate.get("job_matches", [])
    if not job_matches:
        return

    for jm in job_matches:
        job_id = jm["job_id"]
        rankings = vectorstore.search_candidates_for_job(
            job_id=job_id, n_results=200,
        )
        score_map = {r["candidate_id"]: r["score"] for r in rankings}
        score = score_map.get(candidate["id"], 0.0)
        db.update_candidate_job(candidate["id"], job_id, {
            "match_score": score,
            "updated_at": datetime.now().isoformat(),
        })


def _guess_name(filename: str) -> str:
    """Best-effort name from filename (e.g. 'Alice_Wang_Resume.pdf' → 'Alice Wang')."""
    stem = Path(filename).stem
    for word in ("resume", "cv", "简历", "Resume", "CV"):
        stem = stem.replace(word, "")
    name = stem.replace("_", " ").replace("-", " ").strip()
    return name if name else "Unknown"
