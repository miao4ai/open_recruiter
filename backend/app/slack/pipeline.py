"""Three-stage ingestion pipeline: Parse → Normalize → Privacy Filter.

Reuses the existing resume parsing and storage infrastructure, adding
normalization and PII filtering stages before persisting.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from app import database as db
from app import vectorstore
from app.config import Config
from app.models import Candidate, SlackAuditLog
from app.slack.normalizer import normalize_profile
from app.slack.privacy import filter_pii
from app.tools.resume_parser import extract_text

log = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def run_ingestion_pipeline(
    cfg: Config,
    *,
    raw_text: str | None = None,
    file_bytes: bytes | None = None,
    filename: str = "resume.txt",
    source_type: str = "text",
    slack_user_id: str = "",
    channel: str = "",
    thread_ts: str = "",
    job_id: str = "",
) -> dict:
    """Execute the full ingestion pipeline. Returns the candidate dict.

    Stages:
      1. Resume Parser Agent  (extract text + LLM structured parsing)
      2. Profile Normalizer   (title case, skill canonicalization, phone format)
      3. Privacy Filter        (strip SSN, DOB, passport, DL)
    """
    # ── Create audit log entry ────────────────────────────────────────────
    audit = SlackAuditLog(
        slack_user_id=slack_user_id,
        slack_channel=channel,
        slack_thread_ts=thread_ts,
        source_type=source_type,
        original_filename=filename,
    )
    db.insert_audit_log(audit.model_dump())

    try:
        candidate = _run_stages(
            cfg,
            raw_text=raw_text,
            file_bytes=file_bytes,
            filename=filename,
            source_type=source_type,
            job_id=job_id,
        )
        db.update_audit_log(audit.id, {
            "candidate_id": candidate["id"],
            "processing_status": "success",
        })
        return candidate

    except Exception as exc:
        log.error("Ingestion pipeline failed: %s", exc)
        db.update_audit_log(audit.id, {
            "processing_status": "error",
            "error_message": str(exc)[:500],
        })
        raise


def _run_stages(
    cfg: Config,
    *,
    raw_text: str | None,
    file_bytes: bytes | None,
    filename: str,
    source_type: str,
    job_id: str,
) -> dict:
    # ── Stage 1: Resume Parser Agent ──────────────────────────────────────
    if source_type == "file" and file_bytes:
        text = extract_text(file_bytes, filename)
        # Save file to disk
        save_path = UPLOAD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        save_path.write_bytes(file_bytes)
    elif raw_text:
        text = raw_text
        save_path = UPLOAD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_slack_paste.txt"
        save_path.write_text(text, encoding="utf-8")
    else:
        raise ValueError("No resume content provided (file_bytes or raw_text required)")

    # LLM structured parsing (non-fatal if key missing or LLM fails)
    parsed: dict = {}
    has_key = (
        (cfg.llm_provider == "anthropic" and cfg.anthropic_api_key)
        or (cfg.llm_provider == "openai" and cfg.openai_api_key)
    )
    if has_key:
        try:
            from app.agents.resume import parse_resume_text
            parsed = parse_resume_text(cfg, text)
        except Exception as e:
            log.error("LLM resume parsing failed: %s", e)
    else:
        log.warning("No LLM API key configured — skipping structured parsing.")

    # ── Stage 2: Profile Normalizer ───────────────────────────────────────
    try:
        parsed = normalize_profile(parsed)
    except Exception as e:
        log.warning("Profile normalization failed (continuing): %s", e)

    # ── Stage 3: Privacy Filter ───────────────────────────────────────────
    try:
        parsed, text = filter_pii(parsed, text)
    except Exception as e:
        log.warning("Privacy filter failed (continuing): %s", e)

    # ── Dedup check ───────────────────────────────────────────────────────
    email = parsed.get("email", "")
    if email:
        existing = db.list_candidates()
        for c in existing:
            if c.get("email", "").lower() == email.lower():
                # Update existing candidate instead of duplicating
                db.update_candidate(c["id"], {
                    "resume_path": str(save_path),
                    "resume_summary": parsed.get("resume_summary", "") or text[:500],
                    "skills": parsed.get("skills", c.get("skills", [])),
                    "current_title": parsed.get("current_title", "") or c.get("current_title", ""),
                    "current_company": parsed.get("current_company", "") or c.get("current_company", ""),
                    "updated_at": datetime.now().isoformat(),
                })
                log.info("Updated existing candidate %s (dedup by email)", c["id"])
                return db.get_candidate(c["id"])  # type: ignore[return-value]

    # ── Build Candidate and store ─────────────────────────────────────────
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
        resume_summary=parsed.get("resume_summary", "") or text[:500],
        job_id=job_id,
    )
    db.insert_candidate(candidate.model_dump())

    # ── Index in vector store ─────────────────────────────────────────────
    try:
        embed_text = vectorstore.build_candidate_embed_text(candidate)
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

    return candidate.model_dump()


def _guess_name(filename: str) -> str:
    """Best-effort name from filename."""
    stem = Path(filename).stem
    for word in ("resume", "cv", "Resume", "CV"):
        stem = stem.replace(word, "")
    name = stem.replace("_", " ").replace("-", " ").strip()
    return name if name else "Unknown"
