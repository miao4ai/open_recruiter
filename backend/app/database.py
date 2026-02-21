"""SQLite persistence layer with async support."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

_data_dir = os.environ.get("OPEN_RECRUITER_DATA_DIR")
if _data_dir:
    _base = Path(_data_dir)
    _base.mkdir(parents=True, exist_ok=True)
    DB_PATH = _base / "open_recruiter.db"
else:
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
            pipeline_status TEXT DEFAULT 'new',
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
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT,
            role TEXT DEFAULT 'recruiter',
            created_at TEXT,
            UNIQUE(email, role)
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

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT 'New Chat',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            action_json TEXT DEFAULT '',
            action_status TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS activities (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            description TEXT,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS job_seeker_profiles (
            id TEXT PRIMARY KEY,
            user_id TEXT UNIQUE NOT NULL,
            name TEXT DEFAULT '',
            email TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            current_title TEXT DEFAULT '',
            current_company TEXT DEFAULT '',
            skills TEXT DEFAULT '[]',
            experience_years INTEGER,
            location TEXT DEFAULT '',
            resume_summary TEXT DEFAULT '',
            resume_path TEXT DEFAULT '',
            raw_resume_text TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS seeker_jobs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT DEFAULT '',
            company TEXT DEFAULT '',
            posted_date TEXT DEFAULT '',
            required_skills TEXT DEFAULT '[]',
            preferred_skills TEXT DEFAULT '[]',
            experience_years INTEGER,
            location TEXT DEFAULT '',
            remote INTEGER DEFAULT 0,
            salary_range TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            raw_text TEXT DEFAULT '',
            source_url TEXT DEFAULT '',
            status TEXT DEFAULT 'interested',
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

        CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            workflow_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            current_step INTEGER NOT NULL DEFAULT 0,
            total_steps INTEGER NOT NULL DEFAULT 0,
            steps_json TEXT NOT NULL DEFAULT '[]',
            context_json TEXT NOT NULL DEFAULT '{}',
            checkpoint_data_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            memory_type TEXT NOT NULL DEFAULT 'explicit',
            category TEXT NOT NULL DEFAULT 'general',
            content TEXT NOT NULL,
            source TEXT DEFAULT '',
            confidence REAL DEFAULT 1.0,
            access_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS automation_rules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            rule_type TEXT NOT NULL,
            trigger_type TEXT NOT NULL DEFAULT 'interval',
            schedule_value TEXT DEFAULT '',
            conditions_json TEXT DEFAULT '{}',
            actions_json TEXT DEFAULT '{}',
            enabled INTEGER DEFAULT 0,
            last_run_at TEXT,
            next_run_at TEXT,
            run_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS automation_logs (
            id TEXT PRIMARY KEY,
            rule_id TEXT NOT NULL,
            rule_name TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'running',
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_ms INTEGER DEFAULT 0,
            summary TEXT DEFAULT '',
            details_json TEXT DEFAULT '{}',
            error_message TEXT DEFAULT '',
            items_processed INTEGER DEFAULT 0,
            items_affected INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS session_summaries (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL UNIQUE,
            user_id TEXT NOT NULL,
            summary TEXT NOT NULL,
            topics TEXT DEFAULT '[]',
            entity_refs TEXT DEFAULT '{}',
            message_count INTEGER DEFAULT 0,
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

    # Migration: add session_id to chat_messages
    try:
        conn.execute("ALTER TABLE chat_messages ADD COLUMN session_id TEXT NOT NULL DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Migration: add date_of_birth to candidates
    try:
        conn.execute("ALTER TABLE candidates ADD COLUMN date_of_birth TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Migration: add action_json and action_status to chat_messages
    for col, default in [("action_json", "''"), ("action_status", "''")]:
        try:
            conn.execute(f"ALTER TABLE chat_messages ADD COLUMN {col} TEXT DEFAULT {default}")
            conn.commit()
        except sqlite3.OperationalError:
            pass

    # Migration: add contact fields to jobs
    for col, default in [("contact_name", "''"), ("contact_email", "''")]:
        try:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT DEFAULT {default}")
            conn.commit()
        except sqlite3.OperationalError:
            pass

    # Migration: rebuild users table so unique constraint is (email, role)
    schema = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()
    if schema and "UNIQUE(email, role)" not in schema[0]:
        try:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'recruiter'")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users_new (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT,
                role TEXT DEFAULT 'recruiter',
                created_at TEXT,
                UNIQUE(email, role)
            )
        """)
        conn.execute("""
            INSERT OR IGNORE INTO users_new (id, email, password_hash, name, role, created_at)
            SELECT id, email, password_hash, name, COALESCE(role, 'recruiter'), created_at FROM users
        """)
        conn.execute("DROP TABLE users")
        conn.execute("ALTER TABLE users_new RENAME TO users")
        conn.commit()

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
            pipeline_status TEXT DEFAULT 'new',
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(candidate_id, job_id)
        )
    """)
    conn.commit()

    # Migration: add pipeline_status column to candidate_jobs
    try:
        conn.execute("ALTER TABLE candidate_jobs ADD COLUMN pipeline_status TEXT DEFAULT 'new'")
        conn.commit()
    except Exception:
        pass  # Column already exists

    # Data migration: copy candidates.status → candidate_jobs.pipeline_status
    try:
        conn.execute("""
            UPDATE candidate_jobs SET pipeline_status = (
                SELECT status FROM candidates WHERE candidates.id = candidate_jobs.candidate_id
            ) WHERE pipeline_status = 'new' AND EXISTS (
                SELECT 1 FROM candidates WHERE candidates.id = candidate_jobs.candidate_id AND candidates.status != 'new'
            )
        """)
        conn.commit()
    except Exception:
        pass

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
        "INSERT INTO users (id, email, password_hash, name, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user["id"], user["email"], user["password_hash"], user.get("name", ""), user.get("role", "recruiter"), user["created_at"]),
    )
    conn.commit()
    conn.close()


def get_user_by_email(email: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email_and_role(email: str, role: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ? AND role = ?", (email, role)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_user(user_id: str, delete_records: bool = False) -> bool:
    """Delete a user and associated data.

    If *delete_records* is True, also removes recruiter business data
    (jobs, candidates, emails, events, automation rules/logs).
    Otherwise only user-specific data (chat, memories, etc.) is removed.
    """
    conn = get_conn()
    # Always: remove user-specific data
    conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM chat_sessions WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM activities WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM workflows WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM session_summaries WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM job_seeker_profiles WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM seeker_jobs WHERE user_id = ?", (user_id,))

    if delete_records:
        # Also remove recruiter business data
        conn.execute("DELETE FROM emails", ())
        conn.execute("DELETE FROM candidate_jobs", ())
        conn.execute("DELETE FROM candidates", ())
        conn.execute("DELETE FROM jobs", ())
        conn.execute("DELETE FROM events", ())
        conn.execute("DELETE FROM automation_rules", ())
        conn.execute("DELETE FROM automation_logs", ())

    cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


# ── Jobs ───────────────────────────────────────────────────────────────────

def insert_job(job: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO jobs (id, title, company, posted_date, required_skills, preferred_skills,
           experience_years, location, remote, salary_range, summary, raw_text,
           contact_name, contact_email, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job["id"], job["title"], job["company"],
            job.get("posted_date", ""),
            json.dumps(job.get("required_skills", [])),
            json.dumps(job.get("preferred_skills", [])),
            job.get("experience_years"),
            job.get("location", ""), int(job.get("remote", False)),
            job.get("salary_range", ""), job.get("summary", ""),
            job.get("raw_text", ""),
            job.get("contact_name", ""), job.get("contact_email", ""),
            job["created_at"],
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
        d.setdefault("contact_name", "")
        d.setdefault("contact_email", "")
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
    d.setdefault("contact_name", "")
    d.setdefault("contact_email", "")
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
    new_status = updates.get("status")
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
    # Sync status → all candidate_jobs.pipeline_status
    if new_status:
        conn.execute(
            "UPDATE candidate_jobs SET pipeline_status = ?, updated_at = ? WHERE candidate_id = ?",
            (new_status, updates.get("updated_at", datetime.now().isoformat()), cid),
        )
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
           (id, candidate_id, job_id, match_score, match_reasoning, strengths, gaps, pipeline_status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            cj.get("id", uuid.uuid4().hex[:8]),
            cj["candidate_id"], cj["job_id"],
            cj.get("match_score", 0.0), cj.get("match_reasoning", ""),
            json.dumps(cj.get("strengths", [])), json.dumps(cj.get("gaps", [])),
            cj.get("pipeline_status", "new"),
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


def list_pipeline_entries() -> list[dict]:
    """Return all candidate-job pairs with candidate+job info for pipeline views.

    Tries candidate_jobs first; falls back to the legacy candidates.job_id column
    so the Jobs view works even for databases that haven't fully migrated yet.
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT cj.candidate_id, cj.job_id, cj.match_score, cj.pipeline_status,
               c.name as candidate_name, c.current_title as candidate_title,
               j.title as job_title, j.company as job_company
        FROM candidate_jobs cj
        INNER JOIN candidates c ON cj.candidate_id = c.id
        INNER JOIN jobs j ON cj.job_id = j.id
        ORDER BY cj.match_score DESC
    """).fetchall()

    if not rows:
        # Fallback: build entries from candidates that have a legacy job_id link
        rows = conn.execute("""
            SELECT c.id as candidate_id, c.job_id, c.match_score, c.status as pipeline_status,
                   c.name as candidate_name, c.current_title as candidate_title,
                   j.title as job_title, j.company as job_company
            FROM candidates c
            INNER JOIN jobs j ON c.job_id = j.id
            WHERE c.job_id != '' AND c.job_id IS NOT NULL
            ORDER BY c.match_score DESC
        """).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def _row_to_candidate_job(row) -> dict:
    d = dict(row)
    d["strengths"] = json.loads(d.get("strengths") or "[]")
    d["gaps"] = json.loads(d.get("gaps") or "[]")
    d["match_score"] = d.get("match_score") or 0.0
    d.setdefault("job_title", "")
    d.setdefault("job_company", "")
    d.setdefault("pipeline_status", "new")
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


# ── Chat Sessions ─────────────────────────────────────────────────────────

def insert_chat_session(session: dict) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (session["id"], session["user_id"], session["title"], session["created_at"], session["updated_at"]),
    )
    conn.commit()
    conn.close()


def list_chat_sessions(user_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_chat_session(session_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_chat_session(session_id: str, updates: dict) -> None:
    conn = get_conn()
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [session_id]
    conn.execute(f"UPDATE chat_sessions SET {sets} WHERE id = ?", vals)
    conn.commit()
    conn.close()


def delete_chat_session(session_id: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


# ── Chat Messages ─────────────────────────────────────────────────────────

def insert_chat_message(msg: dict) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO chat_messages (id, user_id, session_id, role, content, action_json, action_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (msg["id"], msg["user_id"], msg.get("session_id", ""), msg["role"], msg["content"],
         msg.get("action_json", ""), msg.get("action_status", ""), msg["created_at"]),
    )
    conn.commit()
    conn.close()


def update_chat_message(msg_id: str, updates: dict) -> bool:
    conn = get_conn()
    sets = []
    params = []
    for k, v in updates.items():
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        conn.close()
        return False
    params.append(msg_id)
    conn.execute(f"UPDATE chat_messages SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return True


def list_chat_messages(user_id: str, limit: int = 50, session_id: str | None = None) -> list[dict]:
    conn = get_conn()
    if session_id:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE user_id = ? AND session_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, session_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    conn.close()
    results = []
    for r in reversed(rows):
        d = dict(r)
        # Parse action_json back to dict if present
        if d.get("action_json"):
            try:
                d["action"] = json.loads(d["action_json"])
            except (json.JSONDecodeError, TypeError):
                d["action"] = None
        else:
            d["action"] = None
        d["actionStatus"] = d.pop("action_status", "") or None
        del d["action_json"]
        results.append(d)
    return results


def clear_chat_messages(user_id: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM chat_sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ── Activities ─────────────────────────────────────────────────────────

def insert_activity(a: dict) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO activities (id, user_id, activity_type, description, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (a["id"], a["user_id"], a["activity_type"], a.get("description", ""), a.get("metadata_json", "{}"), a["created_at"]),
    )
    conn.commit()
    conn.close()


def list_activities(user_id: str, limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM activities WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Memories ──────────────────────────────────────────────────────────

def insert_memory(m: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO memories
           (id, user_id, memory_type, category, content, source, confidence, access_count, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (m["id"], m["user_id"], m.get("memory_type", "explicit"), m.get("category", "general"),
         m["content"], m.get("source", ""), m.get("confidence", 1.0), m.get("access_count", 0),
         m["created_at"], m["updated_at"]),
    )
    conn.commit()
    conn.close()


def list_memories(user_id: str, memory_type: str | None = None, limit: int = 15) -> list[dict]:
    conn = get_conn()
    if memory_type:
        rows = conn.execute(
            "SELECT * FROM memories WHERE user_id = ? AND memory_type = ? ORDER BY confidence DESC, updated_at DESC LIMIT ?",
            (user_id, memory_type, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM memories WHERE user_id = ? ORDER BY confidence DESC, updated_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_memory(memory_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_memory(memory_id: str, updates: dict) -> bool:
    conn = get_conn()
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [memory_id]
    cur = conn.execute(f"UPDATE memories SET {sets} WHERE id = ?", vals)
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def delete_memory(memory_id: str) -> bool:
    conn = get_conn()
    cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


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


# ── Job Seeker Profiles ──────────────────────────────────────────────────

def insert_job_seeker_profile(profile: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO job_seeker_profiles
           (id, user_id, name, email, phone, current_title, current_company,
            skills, experience_years, location, resume_summary, resume_path,
            raw_resume_text, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            profile["id"], profile["user_id"], profile.get("name", ""),
            profile.get("email", ""), profile.get("phone", ""),
            profile.get("current_title", ""), profile.get("current_company", ""),
            json.dumps(profile.get("skills", [])), profile.get("experience_years"),
            profile.get("location", ""), profile.get("resume_summary", ""),
            profile.get("resume_path", ""), profile.get("raw_resume_text", ""),
            profile["created_at"], profile["updated_at"],
        ),
    )
    conn.commit()
    conn.close()


def get_job_seeker_profile_by_user(user_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM job_seeker_profiles WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["skills"] = json.loads(d["skills"] or "[]")
    return d


def upsert_job_seeker_profile(user_id: str, data: dict) -> dict:
    """Create or update a job seeker profile. Returns the profile dict."""
    existing = get_job_seeker_profile_by_user(user_id)
    now = datetime.now().isoformat()
    if existing:
        updates = {k: v for k, v in data.items() if k not in ("id", "user_id", "created_at")}
        updates["updated_at"] = now
        conn = get_conn()
        sets = []
        params = []
        for k, v in updates.items():
            if k == "skills":
                v = json.dumps(v)
            sets.append(f"{k} = ?")
            params.append(v)
        params.append(existing["id"])
        conn.execute(f"UPDATE job_seeker_profiles SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
        conn.close()
        return get_job_seeker_profile_by_user(user_id)
    else:
        profile = {
            "id": uuid.uuid4().hex[:8],
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
            **data,
        }
        insert_job_seeker_profile(profile)
        return get_job_seeker_profile_by_user(user_id)


# ── Seeker Jobs ───────────────────────────────────────────────────────────

def _enrich_seeker_job(d: dict) -> dict:
    d["required_skills"] = json.loads(d["required_skills"] or "[]")
    d["preferred_skills"] = json.loads(d["preferred_skills"] or "[]")
    d["remote"] = bool(d["remote"])
    d.setdefault("posted_date", "")
    return d


def insert_seeker_job(job: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO seeker_jobs
           (id, user_id, title, company, posted_date, required_skills, preferred_skills,
            experience_years, location, remote, salary_range, summary, raw_text,
            source_url, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job["id"], job["user_id"], job.get("title", ""),
            job.get("company", ""), job.get("posted_date", ""),
            json.dumps(job.get("required_skills", [])),
            json.dumps(job.get("preferred_skills", [])),
            job.get("experience_years"),
            job.get("location", ""), int(job.get("remote", False)),
            job.get("salary_range", ""), job.get("summary", ""),
            job.get("raw_text", ""), job.get("source_url", ""),
            job.get("status", "interested"), job["created_at"],
        ),
    )
    conn.commit()
    conn.close()


def list_seeker_jobs(user_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM seeker_jobs WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [_enrich_seeker_job(dict(r)) for r in rows]


def get_seeker_job(job_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM seeker_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _enrich_seeker_job(dict(row))


def delete_seeker_job(job_id: str) -> bool:
    conn = get_conn()
    cur = conn.execute("DELETE FROM seeker_jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


# ── Workflows ────────────────────────────────────────────────────────────


def insert_workflow(w: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO workflows
           (id, session_id, user_id, workflow_type, status,
            current_step, total_steps, steps_json, context_json,
            checkpoint_data_json, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            w["id"], w["session_id"], w["user_id"], w["workflow_type"],
            w.get("status", "running"), w.get("current_step", 0),
            w.get("total_steps", 0), w.get("steps_json", "[]"),
            w.get("context_json", "{}"), w.get("checkpoint_data_json", "{}"),
            w["created_at"], w["updated_at"],
        ),
    )
    conn.commit()
    conn.close()


def get_workflow(workflow_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_workflow(workflow_id: str, updates: dict) -> bool:
    if not updates:
        return False
    conn = get_conn()
    cols = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [workflow_id]
    cur = conn.execute(f"UPDATE workflows SET {cols} WHERE id = ?", vals)
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def get_active_workflow(session_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM workflows WHERE session_id = ? AND status IN ('running', 'paused') "
        "ORDER BY created_at DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_workflows(user_id: str, limit: int = 20) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM workflows WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Automation Rules ──────────────────────────────────────────────────────


def insert_automation_rule(r: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO automation_rules
           (id, name, description, rule_type, trigger_type, schedule_value,
            conditions_json, actions_json, enabled, last_run_at, next_run_at,
            run_count, error_count, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            r["id"], r["name"], r.get("description", ""),
            r["rule_type"], r.get("trigger_type", "interval"),
            r.get("schedule_value", ""),
            r.get("conditions_json", "{}"), r.get("actions_json", "{}"),
            int(r.get("enabled", False)), r.get("last_run_at"),
            r.get("next_run_at"), r.get("run_count", 0),
            r.get("error_count", 0), r["created_at"], r["updated_at"],
        ),
    )
    conn.commit()
    conn.close()


def list_automation_rules(enabled_only: bool = False) -> list[dict]:
    conn = get_conn()
    query = "SELECT * FROM automation_rules"
    if enabled_only:
        query += " WHERE enabled = 1"
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [_row_to_rule(r) for r in rows]


def get_automation_rule(rule_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM automation_rules WHERE id = ?", (rule_id,)
    ).fetchone()
    conn.close()
    return _row_to_rule(row) if row else None


def update_automation_rule(rule_id: str, updates: dict) -> bool:
    conn = get_conn()
    sets, params = [], []
    for k, v in updates.items():
        if isinstance(v, bool):
            v = int(v)
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        conn.close()
        return False
    params.append(rule_id)
    conn.execute(
        f"UPDATE automation_rules SET {', '.join(sets)} WHERE id = ?", params
    )
    conn.commit()
    conn.close()
    return True


def delete_automation_rule(rule_id: str) -> bool:
    conn = get_conn()
    cur = conn.execute("DELETE FROM automation_rules WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def _row_to_rule(row) -> dict:
    d = dict(row)
    d["enabled"] = bool(d["enabled"])
    return d


# ── Automation Logs ───────────────────────────────────────────────────────


def insert_automation_log(entry: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO automation_logs
           (id, rule_id, rule_name, status, started_at, finished_at,
            duration_ms, summary, details_json, error_message,
            items_processed, items_affected, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            entry["id"], entry["rule_id"], entry.get("rule_name", ""),
            entry["status"], entry["started_at"], entry.get("finished_at"),
            entry.get("duration_ms", 0), entry.get("summary", ""),
            entry.get("details_json", "{}"), entry.get("error_message", ""),
            entry.get("items_processed", 0), entry.get("items_affected", 0),
            entry["created_at"],
        ),
    )
    conn.commit()
    conn.close()


def list_automation_logs(
    rule_id: str | None = None, limit: int = 100
) -> list[dict]:
    conn = get_conn()
    query = "SELECT * FROM automation_logs WHERE 1=1"
    params: list = []
    if rule_id:
        query += " AND rule_id = ?"
        params.append(rule_id)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_automation_log(log_id: str, updates: dict) -> bool:
    conn = get_conn()
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [log_id]
    cur = conn.execute(f"UPDATE automation_logs SET {sets} WHERE id = ?", vals)
    conn.commit()
    conn.close()
    return cur.rowcount > 0


# ── Session Summaries ────────────────────────────────────────────────────


def insert_session_summary(s: dict) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO session_summaries (id, session_id, user_id, summary, topics, entity_refs, message_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (s["id"], s["session_id"], s["user_id"], s["summary"],
         json.dumps(s.get("topics", [])), json.dumps(s.get("entity_refs", {})),
         s.get("message_count", 0), s["created_at"]),
    )
    conn.commit()
    conn.close()


def get_session_summary(session_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM session_summaries WHERE session_id = ?", (session_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["topics"] = json.loads(d.get("topics") or "[]")
    d["entity_refs"] = json.loads(d.get("entity_refs") or "{}")
    return d


def list_session_summaries(user_id: str, limit: int = 20) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM session_summaries WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["topics"] = json.loads(d.get("topics") or "[]")
        d["entity_refs"] = json.loads(d.get("entity_refs") or "{}")
        results.append(d)
    return results


def delete_session_summary(session_id: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM session_summaries WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
