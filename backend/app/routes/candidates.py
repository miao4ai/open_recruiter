"""Candidate routes — CRUD, resume upload, matching."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query

from app import database as db
from app.models import Candidate, CandidateUpdate, MatchRequest

router = APIRouter()
log = logging.getLogger(__name__)

# Directory to persist uploaded resume files
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("")
async def list_candidates_route(
    job_id: str | None = Query(None),
    status: str | None = Query(None),
):
    return db.list_candidates(job_id=job_id, status=status)


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...), job_id: str = Form("")):
    """Upload a resume file (PDF / DOCX / TXT).

    Pipeline:
      1. Save file to disk
      2. PyMuPDF extracts raw text
      3. LLM parses text into structured fields
      4. Store Candidate in SQLite
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

        # Only call LLM if an API key is configured
        has_key = (
            (cfg.llm_provider == "anthropic" and cfg.anthropic_api_key)
            or (cfg.llm_provider == "openai" and cfg.openai_api_key)
        )
        if has_key:
            from app.agents.resume import parse_resume_text
            parsed = parse_resume_text(cfg, raw_text)
        else:
            log.warning("No LLM API key configured — skipping structured parsing.")
    except Exception as e:
        # LLM failure is non-fatal; we still have the raw text
        log.error("LLM resume parsing failed: %s", e)

    # ── Step 4: build Candidate and store ──────────────────────────────
    candidate = Candidate(
        name=parsed.get("name") or _guess_name(filename),
        email=parsed.get("email", ""),
        phone=parsed.get("phone", ""),
        current_title=parsed.get("current_title", ""),
        current_company=parsed.get("current_company", ""),
        skills=parsed.get("skills", []),
        experience_years=parsed.get("experience_years"),
        location=parsed.get("location", ""),
        resume_path=str(save_path),
        resume_summary=parsed.get("resume_summary", "") or raw_text[:500],
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


def _guess_name(filename: str) -> str:
    """Best-effort name from filename (e.g. 'Alice_Wang_Resume.pdf' → 'Alice Wang')."""
    stem = Path(filename).stem
    # Remove common suffixes
    for word in ("resume", "cv", "简历", "Resume", "CV"):
        stem = stem.replace(word, "")
    # Replace separators with spaces
    name = stem.replace("_", " ").replace("-", " ").strip()
    return name if name else "Unknown"
