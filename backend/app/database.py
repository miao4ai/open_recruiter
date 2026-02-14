"""SQLite persistence layer with async support."""

from __future__ import annotations

import json
import sqlite3
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
            resume_path TEXT,
            resume_summary TEXT,
            status TEXT DEFAULT 'new',
            match_score REAL DEFAULT 0.0,
            match_reasoning TEXT,
            strengths TEXT,         -- JSON array
            gaps TEXT,              -- JSON array
            notes TEXT,
            job_id TEXT,
            created_at TEXT,
            updated_at TEXT
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

        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            title TEXT,
            start_time TEXT,
            end_time TEXT,
            event_type TEXT DEFAULT 'other',
            candidate_id TEXT,
            candidate_name TEXT,
            job_id TEXT,
            job_title TEXT,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT
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

    # Migration: add reply tracking fields to emails
    for col, default in [
        ("message_id", "''"),
        ("reply_body", "''"),
        ("replied_at", "NULL"),
    ]:
        try:
            conn.execute(f"ALTER TABLE emails ADD COLUMN {col} TEXT DEFAULT {default}")
            conn.commit()
        except sqlite3.OperationalError:
            pass

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
        # Count candidates
        conn2 = get_conn()
        cnt = conn2.execute(
            "SELECT COUNT(*) as c FROM candidates WHERE job_id = ?", (d["id"],)
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
        "SELECT COUNT(*) as c FROM candidates WHERE job_id = ?", (d["id"],)
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
            experience_years, location, resume_path, resume_summary, status,
            match_score, match_reasoning, strengths, gaps, notes, job_id,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            c["id"], c.get("name", ""), c.get("email", ""), c.get("phone", ""),
            c.get("current_title", ""), c.get("current_company", ""),
            json.dumps(c.get("skills", [])), c.get("experience_years"),
            c.get("location", ""), c.get("resume_path", ""),
            c.get("resume_summary", ""), c.get("status", "new"),
            c.get("match_score", 0.0), c.get("match_reasoning", ""),
            json.dumps(c.get("strengths", [])), json.dumps(c.get("gaps", [])),
            c.get("notes", ""), c.get("job_id", ""),
            c["created_at"], c["updated_at"],
        ),
    )
    conn.commit()
    conn.close()


def list_candidates(job_id: str | None = None, status: str | None = None) -> list[dict]:
    conn = get_conn()
    query = "SELECT * FROM candidates WHERE 1=1"
    params: list = []
    if job_id:
        query += " AND job_id = ?"
        params.append(job_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY match_score DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_row_to_candidate(r) for r in rows]


def get_candidate(cid: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (cid,)).fetchone()
    conn.close()
    return _row_to_candidate(row) if row else None


def update_candidate(cid: str, updates: dict) -> bool:
    conn = get_conn()
    sets = []
    params = []
    for k, v in updates.items():
        if k in ("skills", "strengths", "gaps"):
            v = json.dumps(v)
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
    cur = conn.execute("DELETE FROM candidates WHERE id = ?", (cid,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def find_candidate_by_name_email(name: str, email: str) -> dict | None:
    """Return existing candidate if both name and email match (case-insensitive)."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM candidates WHERE LOWER(name) = LOWER(?) AND LOWER(email) = LOWER(?)",
        (name, email),
    ).fetchone()
    conn.close()
    return _row_to_candidate(row) if row else None


def _row_to_candidate(row) -> dict:
    d = dict(row)
    d["skills"] = json.loads(d["skills"] or "[]")
    d["strengths"] = json.loads(d["strengths"] or "[]")
    d["gaps"] = json.loads(d["gaps"] or "[]")
    d["match_score"] = d["match_score"] or 0.0
    return d


# ── Emails ─────────────────────────────────────────────────────────────────

def insert_email(e: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO emails
           (id, candidate_id, candidate_name, to_email, subject, body,
            email_type, approved, sent, sent_at, reply_received, attachment_path,
            message_id, reply_body, replied_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            e["id"], e.get("candidate_id", ""), e.get("candidate_name", ""),
            e.get("to_email", ""), e.get("subject", ""), e.get("body", ""),
            e.get("email_type", "outreach"), int(e.get("approved", False)),
            int(e.get("sent", False)), e.get("sent_at"),
            int(e.get("reply_received", False)), e.get("attachment_path", ""),
            e.get("message_id", ""), e.get("reply_body", ""), e.get("replied_at"),
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


def list_sent_unreplied_emails() -> list[dict]:
    """Return sent emails that haven't received a reply yet."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM emails WHERE sent = 1 AND reply_received = 0 ORDER BY sent_at DESC"
    ).fetchall()
    conn.close()
    return [_row_to_email(r) for r in rows]


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


# ── Calendar Events ───────────────────────────────────────────────────

def insert_event(e: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO events
           (id, title, start_time, end_time, event_type, candidate_id,
            candidate_name, job_id, job_title, notes, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            e["id"], e.get("title", ""), e.get("start_time", ""),
            e.get("end_time", ""), e.get("event_type", "other"),
            e.get("candidate_id", ""), e.get("candidate_name", ""),
            e.get("job_id", ""), e.get("job_title", ""),
            e.get("notes", ""), e["created_at"], e["updated_at"],
        ),
    )
    conn.commit()
    conn.close()


def list_events(month: str | None = None, candidate_id: str | None = None, job_id: str | None = None) -> list[dict]:
    conn = get_conn()
    query = "SELECT * FROM events WHERE 1=1"
    params: list = []
    if month:
        # month format: "2026-02" — match start_time starting with it
        query += " AND start_time LIKE ?"
        params.append(f"{month}%")
    if candidate_id:
        query += " AND candidate_id = ?"
        params.append(candidate_id)
    if job_id:
        query += " AND job_id = ?"
        params.append(job_id)
    query += " ORDER BY start_time ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_event(eid: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM events WHERE id = ?", (eid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_event(eid: str, updates: dict) -> bool:
    conn = get_conn()
    sets = []
    params = []
    for k, v in updates.items():
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        conn.close()
        return False
    params.append(eid)
    conn.execute(f"UPDATE events SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return True


def delete_event(eid: str) -> bool:
    conn = get_conn()
    cur = conn.execute("DELETE FROM events WHERE id = ?", (eid,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0
