"""SQLite persistence layer for cross-session candidate tracking."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from open_recruiter.schemas import Candidate, CandidateStatus, Email, JobDescription


class Database:
    def __init__(self, db_path: Path | str = "open_recruiter.db") -> None:
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                phone TEXT,
                resume_text TEXT,
                skills TEXT,  -- JSON array
                experience_years INTEGER DEFAULT 0,
                summary TEXT,
                status TEXT DEFAULT 'new',
                match_score REAL DEFAULT 0.0,
                match_reasoning TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS job_descriptions (
                id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                raw_text TEXT,
                requirements TEXT,  -- JSON array
                nice_to_have TEXT,  -- JSON array
                summary TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS emails (
                id TEXT PRIMARY KEY,
                "to" TEXT,
                subject TEXT,
                body TEXT,
                email_type TEXT DEFAULT 'outreach',
                candidate_id TEXT,
                sent INTEGER DEFAULT 0,
                sent_at TEXT,
                created_at TEXT
            );
        """)
        self.conn.commit()

    # -- Candidates -----------------------------------------------------------

    def save_candidate(self, c: Candidate) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO candidates
               (id, name, email, phone, resume_text, skills, experience_years,
                summary, status, match_score, match_reasoning, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                c.id, c.name, c.email, c.phone, c.resume_text,
                json.dumps(c.skills), c.experience_years, c.summary,
                c.status.value, c.match_score, c.match_reasoning,
                c.created_at.isoformat(),
            ),
        )
        self.conn.commit()

    def get_candidate(self, candidate_id: str) -> Candidate | None:
        row = self.conn.execute(
            "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_candidate(row)

    def list_candidates(self, status: CandidateStatus | None = None) -> list[Candidate]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM candidates WHERE status = ? ORDER BY match_score DESC",
                (status.value,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM candidates ORDER BY match_score DESC"
            ).fetchall()
        return [self._row_to_candidate(r) for r in rows]

    def update_candidate_status(self, candidate_id: str, status: CandidateStatus) -> None:
        self.conn.execute(
            "UPDATE candidates SET status = ? WHERE id = ?",
            (status.value, candidate_id),
        )
        self.conn.commit()

    def _row_to_candidate(self, row: sqlite3.Row) -> Candidate:
        return Candidate(
            id=row["id"],
            name=row["name"] or "",
            email=row["email"] or "",
            phone=row["phone"] or "",
            resume_text=row["resume_text"] or "",
            skills=json.loads(row["skills"]) if row["skills"] else [],
            experience_years=row["experience_years"] or 0,
            summary=row["summary"] or "",
            status=CandidateStatus(row["status"]),
            match_score=row["match_score"] or 0.0,
            match_reasoning=row["match_reasoning"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
        )

    # -- Job Descriptions -----------------------------------------------------

    def save_jd(self, jd: JobDescription) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO job_descriptions
               (id, title, company, raw_text, requirements, nice_to_have, summary, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                jd.id, jd.title, jd.company, jd.raw_text,
                json.dumps(jd.requirements), json.dumps(jd.nice_to_have),
                jd.summary, jd.created_at.isoformat(),
            ),
        )
        self.conn.commit()

    def get_jd(self, jd_id: str) -> JobDescription | None:
        row = self.conn.execute(
            "SELECT * FROM job_descriptions WHERE id = ?", (jd_id,)
        ).fetchone()
        if not row:
            return None
        return JobDescription(
            id=row["id"],
            title=row["title"] or "",
            company=row["company"] or "",
            raw_text=row["raw_text"] or "",
            requirements=json.loads(row["requirements"]) if row["requirements"] else [],
            nice_to_have=json.loads(row["nice_to_have"]) if row["nice_to_have"] else [],
            summary=row["summary"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
        )

    def list_jds(self) -> list[JobDescription]:
        rows = self.conn.execute(
            "SELECT * FROM job_descriptions ORDER BY created_at DESC"
        ).fetchall()
        return [
            JobDescription(
                id=r["id"], title=r["title"] or "", company=r["company"] or "",
                raw_text=r["raw_text"] or "",
                requirements=json.loads(r["requirements"]) if r["requirements"] else [],
                nice_to_have=json.loads(r["nice_to_have"]) if r["nice_to_have"] else [],
                summary=r["summary"] or "",
            )
            for r in rows
        ]

    # -- Emails ---------------------------------------------------------------

    def save_email(self, email: Email) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO emails
               (id, "to", subject, body, email_type, candidate_id, sent, sent_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                email.id, email.to, email.subject, email.body,
                email.email_type, email.candidate_id, int(email.sent),
                email.sent_at.isoformat() if email.sent_at else None,
                email.created_at.isoformat(),
            ),
        )
        self.conn.commit()

    def mark_email_sent(self, email_id: str) -> None:
        self.conn.execute(
            'UPDATE emails SET sent = 1, sent_at = ? WHERE id = ?',
            (datetime.now().isoformat(), email_id),
        )
        self.conn.commit()

    def list_emails(self, candidate_id: str | None = None) -> list[Email]:
        if candidate_id:
            rows = self.conn.execute(
                'SELECT * FROM emails WHERE candidate_id = ? ORDER BY created_at DESC',
                (candidate_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                'SELECT * FROM emails ORDER BY created_at DESC'
            ).fetchall()
        return [
            Email(
                id=r["id"], to=r["to"] or "", subject=r["subject"] or "",
                body=r["body"] or "", email_type=r["email_type"] or "outreach",
                candidate_id=r["candidate_id"] or "", sent=bool(r["sent"]),
                sent_at=datetime.fromisoformat(r["sent_at"]) if r["sent_at"] else None,
                created_at=datetime.fromisoformat(r["created_at"]) if r["created_at"] else datetime.now(),
            )
            for r in rows
        ]

    def close(self) -> None:
        self.conn.close()
