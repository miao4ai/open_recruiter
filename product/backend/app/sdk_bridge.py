"""Wire the app onto the `openrecruiter` SDK.

The SDK owns the recruiting domain — parsing, retrieval, ranking, outreach, and
the agent that drives them. The app keeps everything the SDK has no business
knowing about: users, authentication, chat sessions, automations, Slack, and the
calendar.

Nothing is migrated. `ProductStore` implements the SDK's `Store` protocol over
the existing `database.py`, so the same SQLite file backs both and the REST
endpoints keep working exactly as they did.
"""

from __future__ import annotations

import logging
from datetime import datetime

from openrecruiter import Config as SDKConfig
from openrecruiter import (
    Candidate,
    CandidateStatus,
    ChromaVectorIndex,
    Job,
    Match,
    NullVectorIndex,
    Recruiter,
)

from app import database as db
from app.config import Config

log = logging.getLogger(__name__)


class ProductStore:
    """The SDK's `Store`, backed by the application's own database."""

    # ── jobs ─────────────────────────────────────────────────────────────

    def add_job(self, job: Job) -> Job:
        db.insert_job(
            {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "posted_date": datetime.now().strftime("%Y-%m-%d"),
                "required_skills": job.required_skills,
                "preferred_skills": job.preferred_skills,
                "experience_years": job.experience_years,
                "location": job.location,
                "remote": job.remote,
                "salary_range": job.salary_range,
                "summary": job.summary,
                "raw_text": job.raw_text,
                "created_at": job.created_at,
            }
        )
        return job

    def get_job(self, job_id: str) -> Job | None:
        row = db.get_job(job_id)
        return _to_job(row) if row else None

    def list_jobs(self, limit: int = 100) -> list[Job]:
        return [_to_job(r) for r in (db.list_jobs() or [])[:limit]]

    # ── candidates ───────────────────────────────────────────────────────

    def add_candidate(self, candidate: Candidate) -> Candidate:
        db.insert_candidate(
            {
                "id": candidate.id,
                "name": candidate.name,
                "email": candidate.email,
                "phone": candidate.phone,
                "current_title": candidate.current_title,
                "current_company": candidate.current_company,
                "skills": candidate.skills,
                "experience_years": candidate.experience_years,
                "location": candidate.location,
                "resume_summary": candidate.resume_summary,
                "status": candidate.status.value,
                "created_at": candidate.created_at,
                "updated_at": candidate.created_at,
            }
        )
        return candidate

    def get_candidate(self, candidate_id: str) -> Candidate | None:
        row = db.get_candidate(candidate_id)
        return _to_candidate(row) if row else None

    def list_candidates(self, limit: int = 100) -> list[Candidate]:
        return [_to_candidate(r) for r in (db.list_candidates() or [])[:limit]]

    def set_candidate_status(self, candidate_id: str, status: CandidateStatus) -> bool:
        return bool(
            db.update_candidate(candidate_id, {"status": CandidateStatus(status).value})
        )

    # ── matches ──────────────────────────────────────────────────────────

    def save_match(self, match: Match) -> None:
        """Match results live on the candidate_jobs join, as they always have."""
        payload = {
            "match_score": match.score,
            "match_reasoning": match.reasoning,
            "strengths": match.strengths,
            "gaps": match.gaps,
        }
        if db.get_candidate_job(match.candidate_id, match.job_id):
            db.update_candidate_job(match.candidate_id, match.job_id, payload)
        else:
            db.insert_candidate_job(
                {
                    "candidate_id": match.candidate_id,
                    "job_id": match.job_id,
                    "status": CandidateStatus.NEW.value,
                    **payload,
                }
            )

    def list_matches(self, job_id: str) -> list[Match]:
        rows = db.list_candidates(job_id=job_id) or []
        matches = [
            Match(
                candidate_id=r["id"],
                job_id=job_id,
                score=float(r.get("match_score") or 0.0),
                strengths=list(r.get("strengths") or []),
                gaps=list(r.get("gaps") or []),
                reasoning=str(r.get("match_reasoning") or ""),
            )
            for r in rows
        ]
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches


# ── row -> model ─────────────────────────────────────────────────────────


def _to_job(row: dict) -> Job:
    return Job(
        id=row["id"],
        title=row.get("title") or "",
        company=row.get("company") or "",
        required_skills=list(row.get("required_skills") or []),
        preferred_skills=list(row.get("preferred_skills") or []),
        experience_years=row.get("experience_years"),
        location=row.get("location") or "",
        remote=bool(row.get("remote")),
        salary_range=row.get("salary_range") or "",
        summary=row.get("summary") or "",
        raw_text=row.get("raw_text") or "",
        created_at=row.get("created_at") or "",
    )


def _to_candidate(row: dict) -> Candidate:
    skills = row.get("skills") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    try:
        status = CandidateStatus(row.get("status") or "new")
    except ValueError:
        status = CandidateStatus.NEW
    return Candidate(
        id=row["id"],
        name=row.get("name") or "",
        email=row.get("email") or "",
        phone=row.get("phone") or "",
        current_title=row.get("current_title") or "",
        current_company=row.get("current_company") or "",
        skills=list(skills),
        experience_years=row.get("experience_years"),
        location=row.get("location") or "",
        resume_summary=row.get("resume_summary") or "",
        status=status,
        created_at=row.get("created_at") or "",
    )


# ── construction ─────────────────────────────────────────────────────────


def to_sdk_config(cfg: Config) -> SDKConfig:
    """Translate the app's settings into the SDK's."""
    return SDKConfig(
        llm_provider=cfg.llm_provider,
        llm_model=cfg.llm_model,
        anthropic_api_key=cfg.anthropic_api_key,
        openai_api_key=cfg.openai_api_key,
        voyage_api_key=cfg.voyage_api_key,
        voyage_model=cfg.voyage_model,
    )


def build_recruiter(cfg: Config, extra_tools: list | None = None) -> Recruiter:
    """A `Recruiter` sharing this installation's database and vector index.

    The config is resolved through a callable rather than captured, because a
    user can paste an API key into Settings after the process has started.
    """
    from app.vectorstore import CHROMA_DIR

    sdk_config = to_sdk_config(cfg)

    if sdk_config.voyage_api_key:
        index = ChromaVectorIndex(lambda: to_sdk_config(_live_config()), CHROMA_DIR)
    else:
        index = NullVectorIndex()

    return Recruiter(
        sdk_config,
        store=ProductStore(),
        index=index,
        extra_tools=extra_tools or [],
    )


def _live_config() -> Config:
    from app.routes.settings import get_config

    return get_config()


__all__ = ["ProductStore", "build_recruiter", "to_sdk_config"]
