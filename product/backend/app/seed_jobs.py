"""Seed the jobs table from a JSON file when it is empty.

A staging container has a fresh, ephemeral database; nobody is going to sit
in the recruiter UI and post openings into it every time it restarts. So the
container starts by loading a file of jobs — charbit's staging uses
deploy/seed-jobs.staging.json — and the MCP's job-seeker tools have a pool to
search. Idempotent: a database that already has jobs is left alone.

    OPEN_RECRUITER_SEED_JOBS=/path/to/jobs.json python -m app.seed_jobs
"""

from __future__ import annotations

import json
import os
import sys

from app import database as db


def main() -> None:
    path = os.environ.get("OPEN_RECRUITER_SEED_JOBS") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not path:
        print("seed-jobs: no file given (OPEN_RECRUITER_SEED_JOBS)")
        return
    db.init_db()
    existing = db.list_jobs() or []
    if existing:
        print(f"seed-jobs: {len(existing)} jobs already there, nothing to do")
        return

    from openrecruiter.types import Job

    from app import vectorstore

    doc = json.load(open(path, encoding="utf-8"))
    rows = doc["jobs"] if isinstance(doc, dict) else doc
    n, unindexed, first_error = 0, 0, ""
    for j in rows:
        job = Job(
            title=j["title"], company=j.get("company", ""), location=j.get("location", ""),
            remote=bool(j.get("remote", False)), salary_range=j.get("salary_range", ""),
            required_skills=list(j.get("required_skills", [])), preferred_skills=list(j.get("preferred_skills", [])),
            experience_years=j.get("experience_years"), summary=j.get("summary", ""), raw_text=j.get("raw_text", ""),
        )
        row = job.model_dump()
        row["posted_date"] = j.get("posted_date", "")
        db.insert_job(row)
        try:
            vectorstore.index_job(job_id=job.id, text=job.embed_text(),
                                  metadata={"title": job.title, "company": job.company})
        except Exception as exc:  # noqa: BLE001 — no embeddings key: keyword search still works
            unindexed += 1
            if not first_error:
                first_error = f"{type(exc).__name__}: {exc}"
        n += 1
    print(f"seed-jobs: {n} jobs from {path}" +
          (f"; {unindexed} not indexed — {first_error}" if unindexed else "; all indexed"))


if __name__ == "__main__":
    main()
