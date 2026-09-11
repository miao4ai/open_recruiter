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


#: One config object for the whole process, refreshed in place rather than
#: rebuilt. Everything downstream — the LLM client, the ranker, the vector index
#: — holds a reference to it, so a key pasted into Settings takes effect on the
#: next request instead of the next restart. 3.0.1 was a bug of exactly this
#: shape: the Voyage key was captured at launch and never re-read.
_CONFIG = SDKConfig()

#: The vector index is shared because it owns a ChromaDB client. Rebuilding one
#: per request would reopen the database on every upload and every search.
_INDEX: ChromaVectorIndex | None = None


def to_sdk_config(cfg: Config) -> SDKConfig:
    """Refresh the shared SDK config from the app's settings and return it."""
    _CONFIG.llm_provider = cfg.llm_provider
    _CONFIG.llm_model = cfg.llm_model or ""
    _CONFIG.anthropic_api_key = cfg.anthropic_api_key
    _CONFIG.openai_api_key = cfg.openai_api_key
    _CONFIG.voyage_api_key = cfg.voyage_api_key
    _CONFIG.voyage_model = cfg.voyage_model
    _CONFIG.embedding_api_url = cfg.embedding_api_url
    _CONFIG.embedding_api_key = cfg.embedding_api_key
    _CONFIG.embedding_model = cfg.embedding_model
    if not _CONFIG.llm_model:
        _CONFIG.__post_init__()
    return _CONFIG


def vector_index(cfg: Config):
    """The shared index, or the null one when embeddings are not configured.

    Built on first use and kept: `ChromaVectorIndex` opens its client lazily, so
    holding the instance is what makes repeated searches cheap.
    """
    global _INDEX

    # The index reads _CONFIG (the shared SDK config) for its embeddings
    # credentials, and only to_sdk_config populates it. Callers that reach the
    # index WITHOUT going through build_recruiter — the seeder, vectorstore's
    # module helpers — would otherwise leave _CONFIG blank and the embedder
    # would fall back to an empty Voyage key. Refresh it here so every path is
    # correct.
    to_sdk_config(cfg)
    if not (cfg.voyage_api_key or (cfg.embedding_api_url and cfg.embedding_api_key)):
        return NullVectorIndex()
    if _INDEX is None:
        from app.vectorstore import CHROMA_DIR

        _INDEX = ChromaVectorIndex(lambda: _CONFIG, CHROMA_DIR)
    return _INDEX


def build_recruiter(cfg: Config | None = None, extra_tools: list | None = None) -> Recruiter:
    """A `Recruiter` over this installation's database and vector index.

    Cheap enough to call per request: the store is stateless, the index is
    shared, and the config is the same object every time.
    """
    if cfg is None:
        from app.routes.settings import get_config

        cfg = get_config()

    return Recruiter(
        to_sdk_config(cfg),
        store=ProductStore(),
        index=vector_index(cfg),
        extra_tools=extra_tools or [],
    )


# ── one-line entry points for routes that only need the fields ───────────
# Every caller used to repeat the same three steps: check for an API key, import
# an agent module, and swallow whatever it raised. That is how `agents/jd.py`
# managed to be a syntax error through five releases — the failure was caught
# and logged, and the route carried on with an empty dict.


def parse_resume(raw_text: str) -> dict:
    """Structured fields from resume text. Empty when parsing is unavailable."""
    return _parse(lambda r: r.parse_resume(raw_text), "resume")


def parse_job(raw_text: str) -> dict:
    """Structured fields from a job description. Empty when unavailable."""
    return _parse(lambda r: r.parse_job(raw_text), "job description")


def _parse(call, what: str) -> dict:
    recruiter = build_recruiter()
    if not recruiter.config.api_key:
        log.warning("No LLM API key configured — skipping %s parsing.", what)
        return {}
    try:
        return call(recruiter).model_dump()
    except Exception as exc:  # noqa: BLE001 - a provider can fail many ways
        log.error("Could not parse the %s: %s", what, exc)
        return {}


def reset_shared_state() -> None:
    """Drop the cached index. For tests, and for a settings change that moves
    the data directory."""
    global _INDEX
    _INDEX = None


__all__ = [
    "ProductStore",
    "build_recruiter",
    "parse_job",
    "parse_resume",
    "reset_shared_state",
    "to_sdk_config",
    "vector_index",
]
