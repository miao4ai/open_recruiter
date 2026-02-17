"""Candidate routes — CRUD, resume upload, matching."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query

from app import database as db
from app import vectorstore
from app.auth import get_current_user
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
    _user: dict = Depends(get_current_user),
):
    return db.list_candidates(job_id=job_id, status=status)


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...), job_id: str = Form(""), _user: dict = Depends(get_current_user)):
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

    # ── Step 3.5: duplicate check ───────────────────────────────────────
    parsed_name = parsed.get("name") or _guess_name(filename)
    parsed_email = parsed.get("email", "")
    if parsed_name and parsed_email:
        existing = db.find_candidate_by_name_email(parsed_name, parsed_email)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Candidate '{parsed_name}' ({parsed_email}) already exists in the database.",
            )

    # ── Step 4: build Candidate and store ──────────────────────────────
    candidate = Candidate(
        name=parsed_name,
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

    embed_text = vectorstore.build_candidate_embed_text(candidate)
    try:
        vectorstore.index_candidate(
            candidate_id=candidate.id,
            text=embed_text,
            metadata={
                "name": candidate.name,
                "job_id": candidate.job_id,
                "current_title": candidate.current_title,
            },
        )
    except Exception as e:
        log.warning("Failed to index candidate in vector store: %s", e)

    # Auto-match against all jobs (pass embed_text directly to avoid ChromaDB round-trip)
    try:
        _auto_match_all_jobs(candidate.id, candidate_text=embed_text)
    except Exception as e:
        log.warning("Auto-match-all failed for new candidate %s: %s", candidate.id, e)

    # Return fresh data (auto-match may have updated fields)
    return db.get_candidate(candidate.id) or candidate.model_dump()


@router.get("/{candidate_id}")
async def get_candidate_route(candidate_id: str, _user: dict = Depends(get_current_user)):
    c = db.get_candidate(candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Enrich with dynamic top matching jobs via vector search
    try:
        top_job_results = vectorstore.search_jobs_for_candidate(candidate_id, n_results=5)
        top_jobs = []
        for r in top_job_results:
            job = db.get_job(r["job_id"])
            if job:
                top_jobs.append({
                    "job_id": r["job_id"],
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "score": r["score"],
                })
        c["top_jobs"] = top_jobs
    except Exception:
        c["top_jobs"] = []

    return c


@router.patch("/{candidate_id}")
async def update_candidate_route(candidate_id: str, update: CandidateUpdate, current_user: dict = Depends(get_current_user)):
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
                "job_id": updated.get("job_id", ""),
                "current_title": updated.get("current_title", ""),
            },
        )
    except Exception as e:
        log.warning("Failed to reindex candidate in vector store: %s", e)

    # Re-run auto-match against all jobs
    try:
        _auto_match_all_jobs(candidate_id, candidate_text=embed_text)
    except Exception as e:
        log.warning("Auto-match-all failed for candidate %s: %s", candidate_id, e)

    # Log activity for implicit memory learning
    db.insert_activity({
        "id": uuid.uuid4().hex[:8],
        "user_id": current_user["id"],
        "activity_type": "candidate_updated",
        "description": f"Updated {updated.get('name', '')} — fields: {', '.join(updates.keys())}",
        "metadata_json": json.dumps({
            "candidate_id": candidate_id,
            "fields_changed": list(updates.keys()),
            "new_status": updates.get("status", ""),
        }),
        "created_at": datetime.now().isoformat(),
    })

    return db.get_candidate(candidate_id) or updated


@router.delete("/{candidate_id}")
async def delete_candidate_route(candidate_id: str, current_user: dict = Depends(get_current_user)):
    candidate = db.get_candidate(candidate_id)
    if not db.delete_candidate(candidate_id):
        raise HTTPException(status_code=404, detail="Candidate not found")

    try:
        vectorstore.remove_candidate(candidate_id)
    except Exception:
        pass  # Non-fatal: embedding cleanup is best-effort

    # Log deletion for implicit memory learning
    if candidate:
        db.insert_activity({
            "id": uuid.uuid4().hex[:8],
            "user_id": current_user["id"],
            "activity_type": "candidate_deleted",
            "description": f"Deleted {candidate.get('name', '')}",
            "metadata_json": json.dumps({
                "candidate_id": candidate_id,
                "candidate_name": candidate.get("name", ""),
                "status": candidate.get("status", ""),
            }),
            "created_at": datetime.now().isoformat(),
        })

    return {"status": "deleted"}


@router.post("/match")
async def match_candidates(req: MatchRequest, _user: dict = Depends(get_current_user)):
    """Re-run multi-job match analysis for candidates."""
    results = []
    for cid in req.candidate_ids:
        c = db.get_candidate(cid)
        if not c:
            continue
        _auto_match_all_jobs(cid)
        updated = db.get_candidate(cid)
        results.append({
            "candidate_id": cid,
            "candidate_name": updated["name"],
            "score": updated["match_score"],
            "strengths": updated["strengths"],
            "gaps": updated["gaps"],
            "reasoning": updated["match_reasoning"],
        })
    return results


def _auto_match_all_jobs(candidate_id: str, candidate_text: str | None = None) -> None:
    """Match a candidate against all jobs: vector scoring + optional LLM analysis.

    Updates the candidate record with:
    - job_id = best matching job
    - match_score = best job's vector score
    - match_reasoning = LLM multi-job analysis (or vector-only summary)
    - strengths / gaps = for best matching job
    """
    top_jobs = vectorstore.search_jobs_for_candidate(
        candidate_id, n_results=5, candidate_text=candidate_text,
    )
    if not top_jobs:
        return

    # Enrich with job details
    enriched_jobs = []
    for r in top_jobs:
        job = db.get_job(r["job_id"])
        if job:
            enriched_jobs.append({**r, "title": job.get("title", ""), "company": job.get("company", ""), "raw_text": job.get("raw_text", "")})

    if not enriched_jobs:
        return

    best = enriched_jobs[0]

    # Try LLM-based multi-job analysis
    from app.routes.settings import get_config
    cfg = get_config()
    has_key = (
        (cfg.llm_provider == "anthropic" and cfg.anthropic_api_key)
        or (cfg.llm_provider == "openai" and cfg.openai_api_key)
    )

    if has_key:
        try:
            analysis = _llm_multi_job_match(cfg, candidate_id, enriched_jobs)
            rankings = analysis.get("rankings", [])
            if rankings:
                # Use LLM's best pick
                best_rank = rankings[0]
                best_job_id = best_rank.get("job_id", best["job_id"])
                db.update_candidate(candidate_id, {
                    "job_id": best_job_id,
                    "match_score": float(best_rank.get("score", best["score"])),
                    "match_reasoning": _format_multi_job_reasoning(analysis),
                    "strengths": best_rank.get("strengths", []),
                    "gaps": best_rank.get("gaps", []),
                    "updated_at": datetime.now().isoformat(),
                })
                return
        except Exception as e:
            log.warning("LLM multi-job match failed, falling back to vector: %s", e)

    # Fallback: vector-only scoring
    reasoning_lines = []
    for i, j in enumerate(enriched_jobs, 1):
        pct = round(j["score"] * 100)
        reasoning_lines.append(f"{i}. {j['title']} at {j['company']} — {pct}% match")
    reasoning = "Top matching jobs (by semantic similarity):\n" + "\n".join(reasoning_lines)

    db.update_candidate(candidate_id, {
        "job_id": best["job_id"],
        "match_score": best["score"],
        "match_reasoning": reasoning,
        "strengths": [],
        "gaps": [],
        "updated_at": datetime.now().isoformat(),
    })


def _llm_multi_job_match(cfg, candidate_id: str, jobs: list[dict]) -> dict:
    """Run LLM multi-job matching for a candidate."""
    from app.llm import chat_json
    from app.prompts import MULTI_JOB_MATCHING

    candidate = db.get_candidate(candidate_id)
    if not candidate:
        return {}

    skills = candidate.get("skills", [])
    skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)

    jobs_text = ""
    for j in jobs:
        jobs_text += (
            f"\n### Job ID: {j['job_id']}\n"
            f"Title: {j['title']}\nCompany: {j['company']}\n"
            f"Description:\n{j['raw_text'][:800]}\n"
        )

    user_msg = (
        f"## Candidate Profile\n"
        f"Name: {candidate['name']}\n"
        f"Title: {candidate.get('current_title', '')}\n"
        f"Skills: {skills_str}\n"
        f"Experience: {candidate.get('experience_years', 'N/A')} years\n"
        f"Summary: {candidate.get('resume_summary', '')}\n\n"
        f"## Jobs to evaluate against\n{jobs_text}"
    )

    return chat_json(cfg, system=MULTI_JOB_MATCHING, messages=[{"role": "user", "content": user_msg}])


def _format_multi_job_reasoning(analysis: dict) -> str:
    """Format LLM multi-job analysis into readable text for storage."""
    lines = []
    summary = analysis.get("summary", "")
    if summary:
        lines.append(summary)
        lines.append("")

    rankings = analysis.get("rankings", [])
    for i, r in enumerate(rankings, 1):
        score_pct = round(float(r.get("score", 0)) * 100)
        title = r.get("title", "Unknown")
        company = r.get("company", "")
        one_liner = r.get("one_liner", "")
        label = f"{title} at {company}" if company else title
        lines.append(f"{i}. {label} — {score_pct}%")
        if one_liner:
            lines.append(f"   {one_liner}")

    return "\n".join(lines)


def _guess_name(filename: str) -> str:
    """Best-effort name from filename (e.g. 'Alice_Wang_Resume.pdf' → 'Alice Wang')."""
    stem = Path(filename).stem
    # Remove common suffixes
    for word in ("resume", "cv", "简历", "Resume", "CV"):
        stem = stem.replace(word, "")
    # Replace separators with spaces
    name = stem.replace("_", " ").replace("-", " ").strip()
    return name if name else "Unknown"
