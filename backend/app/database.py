"""SQLite persistence layer with async support."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "open_recruiter.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            posted_date TEXT,
            required_skills TEXT,   -- JSON array
            preferred_skills TEXT,  -- JSON array
            experience_years INTEGER,
            location TEXT,
            remote INTEGER DEFAULT 0,
            salary_range TEXT,
            summary TEXT,
            raw_text TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS candidates (
            id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            phone TEXT,
            current_title TEXT,
            current_company TEXT,
            skills TEXT,            -- JSON array
            experience_years INTEGER,
            location TEXT,
            date_of_birth TEXT DEFAULT '',
            resume_path TEXT,
            resume_summary TEXT,
            status TEXT DEFAULT 'new',
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            -- Legacy columns (kept for SQLite compat, no longer used)
            match_score REAL DEFAULT 0.0,
            match_reasoning TEXT,
            strengths TEXT,
            gaps TEXT,
            job_id TEXT
        );

        CREATE TABLE IF NOT EXISTS candidate_jobs (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            match_score REAL DEFAULT 0.0,
            match_reasoning TEXT DEFAULT '',
            strengths TEXT DEFAULT '[]',   -- JSON array
            gaps TEXT DEFAULT '[]',        -- JSON array
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(candidate_id, job_id)
        );

        CREATE TABLE IF NOT EXISTS slack_audit_log (
            id TEXT PRIMARY KEY,
            slack_user_id TEXT,
            slack_channel TEXT,
            slack_thread_ts TEXT,
            source_type TEXT,
            original_filename TEXT,
            candidate_id TEXT,
            processing_status TEXT DEFAULT 'pending',
            error_message TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS emails (
            id TEXT PRIMARY KEY,
            candidate_id TEXT,
            candidate_name TEXT,
            to_email TEXT,
            subject TEXT,
            body TEXT,
            email_type TEXT DEFAULT 'outreach',
            approved INTEGER DEFAULT 0,
            sent INTEGER DEFAULT 0,
            sent_at TEXT,
            reply_received INTEGER DEFAULT 0,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()

    # Migration: add posted_date column to existing databases
    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN posted_date TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Migration: add attachment_path to emails
    try:
        conn.execute("ALTER TABLE emails ADD COLUMN attachment_path TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Migration: add date_of_birth to candidates
    try:
        conn.execute("ALTER TABLE candidates ADD COLUMN date_of_birth TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Migration: create candidate_jobs table (for existing DBs)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS candidate_jobs (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            match_score REAL DEFAULT 0.0,
            match_reasoning TEXT DEFAULT '',
            strengths TEXT DEFAULT '[]',
            gaps TEXT DEFAULT '[]',
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(candidate_id, job_id)
        )
    """)
    conn.commit()

    # Data migration: move existing candidate.job_id → candidate_jobs
    try:
        rows = conn.execute(
            "SELECT id, job_id, match_score, match_reasoning, strengths, gaps FROM candidates WHERE job_id != '' AND job_id IS NOT NULL"
        ).fetchall()
        now = datetime.now().isoformat()
        for r in rows:
            existing = conn.execute(
                "SELECT id FROM candidate_jobs WHERE candidate_id = ? AND job_id = ?",
                (r["id"], r["job_id"]),
            ).fetchone()
            if not existing:
                conn.execute(
                    """INSERT INTO candidate_jobs (id, candidate_id, job_id, match_score, match_reasoning, strengths, gaps, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        uuid.uuid4().hex[:8], r["id"], r["job_id"],
                        r["match_score"] or 0.0, r["match_reasoning"] or "",
                        r["strengths"] or "[]", r["gaps"] or "[]",
                        now, now,
                    ),
                )
        conn.commit()
    except Exception:
        pass  # Best-effort migration

    conn.close()


# ── Settings helpers ───────────────────────────────────────────────────────

def get_settings() -> dict[str, str]:
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def put_settings(data: dict[str, str]) -> None:
    conn = get_conn()
    for k, v in data.items():
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v)
        )
    conn.commit()
    conn.close()


# ── Users ──────────────────────────────────────────────────────────────────

def insert_user(user: dict) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO users (id, email, password_hash, name, created_at) VALUES (?, ?, ?, ?, ?)",
        (user["id"], user["email"], user["password_hash"], user.get("name", ""), user["created_at"]),
    )
    conn.commit()
    conn.close()


def get_user_by_email(email: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Jobs ───────────────────────────────────────────────────────────────────

def insert_job(job: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO jobs (id, title, company, posted_date, required_skills, preferred_skills,
           experience_years, location, remote, salary_range, summary, raw_text, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job["id"], job["title"], job["company"],
            job.get("posted_date", ""),
            json.dumps(job.get("required_skills", [])),
            json.dumps(job.get("preferred_skills", [])),
            job.get("experience_years"),
            job.get("location", ""), int(job.get("remote", False)),
            job.get("salary_range", ""), job.get("summary", ""),
            job.get("raw_text", ""), job["created_at"],
        ),
    )
    conn.commit()
    conn.close()


def list_jobs() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["required_skills"] = json.loads(d["required_skills"] or "[]")
        d["preferred_skills"] = json.loads(d["preferred_skills"] or "[]")
        d["remote"] = bool(d["remote"])
        d.setdefault("posted_date", "")
        # Count candidates via candidate_jobs
        conn2 = get_conn()
        cnt = conn2.execute(
            "SELECT COUNT(*) as c FROM candidate_jobs WHERE job_id = ?", (d["id"],)
        ).fetchone()["c"]
        conn2.close()
        d["candidate_count"] = cnt
        results.append(d)
    return results


def get_job(job_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["required_skills"] = json.loads(d["required_skills"] or "[]")
    d["preferred_skills"] = json.loads(d["preferred_skills"] or "[]")
    d["remote"] = bool(d["remote"])
    d.setdefault("posted_date", "")
    conn2 = get_conn()
    d["candidate_count"] = conn2.execute(
        "SELECT COUNT(*) as c FROM candidate_jobs WHERE job_id = ?", (d["id"],)
    ).fetchone()["c"]
    conn2.close()
    return d


def update_job(job_id: str, updates: dict) -> bool:
    conn = get_conn()
    sets = []
    params = []
    for k, v in updates.items():
        if k in ("required_skills", "preferred_skills"):
            v = json.dumps(v)
        if isinstance(v, bool):
            v = int(v)
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        conn.close()
        return False
    params.append(job_id)
    conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return True


def delete_job(job_id: str) -> bool:
    conn = get_conn()
    # Clean up candidate_jobs
    conn.execute("DELETE FROM candidate_jobs WHERE job_id = ?", (job_id,))
    cur = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


# ── Candidates ─────────────────────────────────────────────────────────────

def insert_candidate(c: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO candidates
           (id, name, email, phone, current_title, current_company, skills,
            experience_years, location, date_of_birth, resume_path, resume_summary,
            status, notes, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            c["id"], c.get("name", ""), c.get("email", ""), c.get("phone", ""),
            c.get("current_title", ""), c.get("current_company", ""),
            json.dumps(c.get("skills", [])), c.get("experience_years"),
            c.get("location", ""), c.get("date_of_birth", ""),
            c.get("resume_path", ""), c.get("resume_summary", ""),
            c.get("status", "new"), c.get("notes", ""),
            c["created_at"], c["updated_at"],
        ),
    )
    conn.commit()
    conn.close()


def list_candidates(job_id: str | None = None, status: str | None = None) -> list[dict]:
    conn = get_conn()
    if job_id:
        # JOIN with candidate_jobs to get match data for this specific job
        query = """
            SELECT c.*, cj.match_score as _cj_match_score,
                   cj.match_reasoning as _cj_match_reasoning,
                   cj.strengths as _cj_strengths, cj.gaps as _cj_gaps
            FROM candidates c
            INNER JOIN candidate_jobs cj ON c.id = cj.candidate_id
            WHERE cj.job_id = ?
        """
        params: list = [job_id]
        if status:
            query += " AND c.status = ?"
            params.append(status)
        query += " ORDER BY cj.match_score DESC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        results = []
        for r in rows:
            d = _row_to_candidate(r)
            # Overlay match data from candidate_jobs
            d["match_score"] = r["_cj_match_score"] or 0.0
            d["match_reasoning"] = r["_cj_match_reasoning"] or ""
            d["strengths"] = json.loads(r["_cj_strengths"] or "[]")
            d["gaps"] = json.loads(r["_cj_gaps"] or "[]")
            d["job_id"] = job_id
            results.append(d)
        return results
    else:
        query = "SELECT * FROM candidates WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        results = []
        for r in rows:
            d = _row_to_candidate(r)
            # Attach job_matches summary
            d["job_matches"] = list_candidate_jobs(candidate_id=d["id"])
            # For backward compat: pick best match score
            if d["job_matches"]:
                best = max(d["job_matches"], key=lambda m: m["match_score"])
                d["match_score"] = best["match_score"]
                d["match_reasoning"] = best["match_reasoning"]
                d["strengths"] = best["strengths"]
                d["gaps"] = best["gaps"]
            else:
                d["match_score"] = 0.0
                d["match_reasoning"] = ""
                d["strengths"] = []
                d["gaps"] = []
            results.append(d)
        return results


def get_candidate(cid: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (cid,)).fetchone()
    conn.close()
    if not row:
        return None
    d = _row_to_candidate(row)
    d["job_matches"] = list_candidate_jobs(candidate_id=cid)
    # Best match for backward compat
    if d["job_matches"]:
        best = max(d["job_matches"], key=lambda m: m["match_score"])
        d["match_score"] = best["match_score"]
        d["match_reasoning"] = best["match_reasoning"]
        d["strengths"] = best["strengths"]
        d["gaps"] = best["gaps"]
    else:
        d["match_score"] = 0.0
        d["match_reasoning"] = ""
        d["strengths"] = []
        d["gaps"] = []
    return d


def update_candidate(cid: str, updates: dict) -> bool:
    conn = get_conn()
    sets = []
    params = []
    for k, v in updates.items():
        if k in ("skills",):
            v = json.dumps(v)
        # Skip match fields — they belong to candidate_jobs now
        if k in ("match_score", "match_reasoning", "strengths", "gaps", "job_id"):
            continue
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        return False
    params.append(cid)
    conn.execute(f"UPDATE candidates SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return True


def delete_candidate(cid: str) -> bool:
    conn = get_conn()
    # Clean up candidate_jobs
    conn.execute("DELETE FROM candidate_jobs WHERE candidate_id = ?", (cid,))
    cur = conn.execute("DELETE FROM candidates WHERE id = ?", (cid,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def find_candidate_by_identity(name: str, email: str, date_of_birth: str = "") -> dict | None:
    """Return existing candidate matching name + email + date_of_birth (case-insensitive)."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM candidates WHERE LOWER(name) = LOWER(?) AND LOWER(email) = LOWER(?) AND LOWER(COALESCE(date_of_birth, '')) = LOWER(?)",
        (name, email, date_of_birth or ""),
    ).fetchone()
    conn.close()
    return _row_to_candidate(row) if row else None


def _row_to_candidate(row) -> dict:
    d = dict(row)
    d["skills"] = json.loads(d.get("skills") or "[]")
    d.setdefault("date_of_birth", "")
    return d


# ── Candidate Jobs (join table) ───────────────────────────────────────────

def insert_candidate_job(cj: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO candidate_jobs
           (id, candidate_id, job_id, match_score, match_reasoning, strengths, gaps, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            cj.get("id", uuid.uuid4().hex[:8]),
            cj["candidate_id"], cj["job_id"],
            cj.get("match_score", 0.0), cj.get("match_reasoning", ""),
            json.dumps(cj.get("strengths", [])), json.dumps(cj.get("gaps", [])),
            cj.get("created_at", datetime.now().isoformat()),
            cj.get("updated_at", datetime.now().isoformat()),
        ),
    )
    conn.commit()
    conn.close()


def get_candidate_job(candidate_id: str, job_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM candidate_jobs WHERE candidate_id = ? AND job_id = ?",
        (candidate_id, job_id),
    ).fetchone()
    conn.close()
    return _row_to_candidate_job(row) if row else None


def list_candidate_jobs(candidate_id: str | None = None, job_id: str | None = None) -> list[dict]:
    conn = get_conn()
    query = "SELECT cj.*, j.title as job_title, j.company as job_company FROM candidate_jobs cj LEFT JOIN jobs j ON cj.job_id = j.id WHERE 1=1"
    params: list = []
    if candidate_id:
        query += " AND cj.candidate_id = ?"
        params.append(candidate_id)
    if job_id:
        query += " AND cj.job_id = ?"
        params.append(job_id)
    query += " ORDER BY cj.match_score DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_row_to_candidate_job(r) for r in rows]


def update_candidate_job(candidate_id: str, job_id: str, updates: dict) -> bool:
    conn = get_conn()
    sets = []
    params = []
    for k, v in updates.items():
        if k in ("strengths", "gaps"):
            v = json.dumps(v)
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        return False
    params.extend([candidate_id, job_id])
    conn.execute(
        f"UPDATE candidate_jobs SET {', '.join(sets)} WHERE candidate_id = ? AND job_id = ?",
        params,
    )
    conn.commit()
    conn.close()
    return True


def delete_candidate_job(candidate_id: str, job_id: str) -> bool:
    conn = get_conn()
    cur = conn.execute(
        "DELETE FROM candidate_jobs WHERE candidate_id = ? AND job_id = ?",
        (candidate_id, job_id),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def _row_to_candidate_job(row) -> dict:
    d = dict(row)
    d["strengths"] = json.loads(d.get("strengths") or "[]")
    d["gaps"] = json.loads(d.get("gaps") or "[]")
    d["match_score"] = d.get("match_score") or 0.0
    d.setdefault("job_title", "")
    d.setdefault("job_company", "")
    return d


# ── Emails ─────────────────────────────────────────────────────────────────

def insert_email(e: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO emails
           (id, candidate_id, candidate_name, to_email, subject, body,
            email_type, approved, sent, sent_at, reply_received, attachment_path, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            e["id"], e.get("candidate_id", ""), e.get("candidate_name", ""),
            e.get("to_email", ""), e.get("subject", ""), e.get("body", ""),
            e.get("email_type", "outreach"), int(e.get("approved", False)),
            int(e.get("sent", False)), e.get("sent_at"),
            int(e.get("reply_received", False)), e.get("attachment_path", ""),
            e["created_at"],
        ),
    )
    conn.commit()
    conn.close()


def list_emails(candidate_id: str | None = None) -> list[dict]:
    conn = get_conn()
    if candidate_id:
        rows = conn.execute(
            "SELECT * FROM emails WHERE candidate_id = ? ORDER BY created_at DESC",
            (candidate_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM emails ORDER BY created_at DESC").fetchall()
    conn.close()
    return [_row_to_email(r) for r in rows]


def get_email(eid: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM emails WHERE id = ?", (eid,)).fetchone()
    conn.close()
    return _row_to_email(row) if row else None


def update_email(eid: str, updates: dict) -> bool:
    conn = get_conn()
    sets = []
    params = []
    for k, v in updates.items():
        if isinstance(v, bool):
            v = int(v)
        sets.append(f'"{k}" = ?' if k == "to" else f"{k} = ?")
        params.append(v)
    if not sets:
        return False
    params.append(eid)
    conn.execute(f"UPDATE emails SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return True


def _row_to_email(row) -> dict:
    d = dict(row)
    d["approved"] = bool(d["approved"])
    d["sent"] = bool(d["sent"])
    d["reply_received"] = bool(d["reply_received"])
    return d


# ── Slack Audit Log ───────────────────────────────────────────────────────

def insert_audit_log(entry: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO slack_audit_log
           (id, slack_user_id, slack_channel, slack_thread_ts, source_type,
            original_filename, candidate_id, processing_status, error_message, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            entry["id"], entry.get("slack_user_id", ""),
            entry.get("slack_channel", ""), entry.get("slack_thread_ts", ""),
            entry.get("source_type", ""), entry.get("original_filename", ""),
            entry.get("candidate_id", ""), entry.get("processing_status", "pending"),
            entry.get("error_message", ""), entry["created_at"],
        ),
    )
    conn.commit()
    conn.close()


def update_audit_log(log_id: str, updates: dict) -> bool:
    conn = get_conn()
    sets = []
    params = []
    for k, v in updates.items():
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        conn.close()
        return False
    params.append(log_id)
    conn.execute(f"UPDATE slack_audit_log SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return True


def list_audit_logs(
    slack_user_id: str | None = None,
    candidate_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    conn = get_conn()
    query = "SELECT * FROM slack_audit_log WHERE 1=1"
    params: list = []
    if slack_user_id:
        query += " AND slack_user_id = ?"
        params.append(slack_user_id)
    if candidate_id:
        query += " AND candidate_id = ?"
        params.append(candidate_id)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Chat Messages ─────────────────────────────────────────────────────────

def insert_chat_message(msg: dict) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (msg["id"], msg["user_id"], msg["role"], msg["content"], msg["created_at"]),
    )
    conn.commit()
    conn.close()


def list_chat_messages(user_id: str, limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def clear_chat_messages(user_id: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
