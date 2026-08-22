"""The default store: a single SQLite file.

Deliberately small — four tables, no migrations framework, no ORM. It exists so
`pip install openrecruiter` gives you something that works in one line, and so
the protocol has a reference implementation to check against. An application
with its own database should implement `Store` over that instead.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from openrecruiter.types import Candidate, CandidateStatus, Job, Match

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id                TEXT PRIMARY KEY,
    title             TEXT NOT NULL DEFAULT '',
    company           TEXT NOT NULL DEFAULT '',
    required_skills   TEXT NOT NULL DEFAULT '[]',
    preferred_skills  TEXT NOT NULL DEFAULT '[]',
    experience_years  INTEGER,
    location          TEXT NOT NULL DEFAULT '',
    remote            INTEGER NOT NULL DEFAULT 0,
    salary_range      TEXT NOT NULL DEFAULT '',
    summary           TEXT NOT NULL DEFAULT '',
    raw_text          TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS candidates (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL DEFAULT '',
    email             TEXT NOT NULL DEFAULT '',
    phone             TEXT NOT NULL DEFAULT '',
    current_title     TEXT NOT NULL DEFAULT '',
    current_company   TEXT NOT NULL DEFAULT '',
    skills            TEXT NOT NULL DEFAULT '[]',
    experience_years  INTEGER,
    location          TEXT NOT NULL DEFAULT '',
    resume_summary    TEXT NOT NULL DEFAULT '',
    raw_resume_text   TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'new',
    created_at        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS matches (
    candidate_id  TEXT NOT NULL,
    job_id        TEXT NOT NULL,
    score         REAL NOT NULL DEFAULT 0,
    strengths     TEXT NOT NULL DEFAULT '[]',
    gaps          TEXT NOT NULL DEFAULT '[]',
    reasoning     TEXT NOT NULL DEFAULT '',
    ranker        TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (candidate_id, job_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_job ON matches(job_id, score DESC);
"""

_JOB_COLUMNS = (
    "id", "title", "company", "required_skills", "preferred_skills",
    "experience_years", "location", "remote", "salary_range", "summary",
    "raw_text", "created_at",
)
_CANDIDATE_COLUMNS = (
    "id", "name", "email", "phone", "current_title", "current_company",
    "skills", "experience_years", "location", "resume_summary",
    "raw_resume_text", "status", "created_at",
)
_JSON_FIELDS = {"required_skills", "preferred_skills", "skills", "strengths", "gaps"}


class SQLiteStore:
    """A `Store` backed by one SQLite file.

    Connections are opened per call rather than held open, so the store is safe
    to share across threads — which a web server will do without asking.
    """

    def __init__(self, path: str | Path = "openrecruiter.db") -> None:
        self.path = Path(path)
        if self.path.parent != Path(""):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── jobs ─────────────────────────────────────────────────────────────

    def add_job(self, job: Job) -> Job:
        row = _to_row(job, _JOB_COLUMNS)
        with self._connect() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO jobs ({','.join(_JOB_COLUMNS)}) "
                f"VALUES ({','.join('?' * len(_JOB_COLUMNS))})",
                row,
            )
        return job

    def get_job(self, job_id: str) -> Job | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _to_job(row) if row else None

    def list_jobs(self, limit: int = 100) -> list[Job]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_to_job(r) for r in rows]

    # ── candidates ───────────────────────────────────────────────────────

    def add_candidate(self, candidate: Candidate) -> Candidate:
        row = _to_row(candidate, _CANDIDATE_COLUMNS)
        with self._connect() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO candidates ({','.join(_CANDIDATE_COLUMNS)}) "
                f"VALUES ({','.join('?' * len(_CANDIDATE_COLUMNS))})",
                row,
            )
        return candidate

    def get_candidate(self, candidate_id: str) -> Candidate | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
        return _to_candidate(row) if row else None

    def list_candidates(self, limit: int = 100) -> list[Candidate]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM candidates ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_to_candidate(r) for r in rows]

    def set_candidate_status(self, candidate_id: str, status: CandidateStatus) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE candidates SET status = ? WHERE id = ?",
                (CandidateStatus(status).value, candidate_id),
            )
        return cur.rowcount > 0

    # ── matches ──────────────────────────────────────────────────────────

    def save_match(self, match: Match) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO matches "
                "(candidate_id, job_id, score, strengths, gaps, reasoning, ranker) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    match.candidate_id,
                    match.job_id,
                    match.score,
                    json.dumps(match.strengths),
                    json.dumps(match.gaps),
                    match.reasoning,
                    match.ranker,
                ),
            )

    def list_matches(self, job_id: str) -> list[Match]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM matches WHERE job_id = ? ORDER BY score DESC", (job_id,)
            ).fetchall()
        return [
            Match(
                candidate_id=r["candidate_id"],
                job_id=r["job_id"],
                score=r["score"],
                strengths=json.loads(r["strengths"]),
                gaps=json.loads(r["gaps"]),
                reasoning=r["reasoning"],
                ranker=r["ranker"],
            )
            for r in rows
        ]


# ── row <-> model ────────────────────────────────────────────────────────


def _to_row(model, columns: tuple[str, ...]) -> tuple:
    data = model.model_dump()
    out = []
    for col in columns:
        value = data.get(col)
        if col in _JSON_FIELDS:
            value = json.dumps(value or [])
        elif isinstance(value, bool):
            value = int(value)
        elif hasattr(value, "value"):  # enum
            value = value.value
        out.append(value)
    return tuple(out)


def _to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        title=row["title"],
        company=row["company"],
        required_skills=json.loads(row["required_skills"]),
        preferred_skills=json.loads(row["preferred_skills"]),
        experience_years=row["experience_years"],
        location=row["location"],
        remote=bool(row["remote"]),
        salary_range=row["salary_range"],
        summary=row["summary"],
        raw_text=row["raw_text"],
        created_at=row["created_at"],
    )


def _to_candidate(row: sqlite3.Row) -> Candidate:
    return Candidate(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        phone=row["phone"],
        current_title=row["current_title"],
        current_company=row["current_company"],
        skills=json.loads(row["skills"]),
        experience_years=row["experience_years"],
        location=row["location"],
        resume_summary=row["resume_summary"],
        raw_resume_text=row["raw_resume_text"],
        status=CandidateStatus(row["status"]),
        created_at=row["created_at"],
    )


__all__ = ["SQLiteStore"]
