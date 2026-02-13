"""Search routes — semantic similarity powered by ChromaDB."""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app import database as db
from app import vectorstore
from app.auth import get_current_user

log = logging.getLogger(__name__)

router = APIRouter()

MATCH_THRESHOLD = 0.30  # same threshold as jobs route


class TextSearchRequest(BaseModel):
    query: str
    collection: str = "candidates"
    n_results: int = 10


@router.get("/candidates-for-job/{job_id}")
async def search_candidates_for_job(
    job_id: str,
    n: int = Query(20, ge=1, le=100, description="Number of results"),
    _user: dict = Depends(get_current_user),
):
    """Find candidates semantically similar to a job description."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    results = vectorstore.search_candidates_for_job(job_id=job_id, n_results=n)

    enriched = []
    for r in results:
        candidate = db.get_candidate(r["candidate_id"])
        if candidate:
            enriched.append({
                "candidate": candidate,
                "similarity_score": r["score"],
            })
    return enriched


@router.get("/similar-candidates/{candidate_id}")
async def search_similar_candidates(
    candidate_id: str,
    n: int = Query(10, ge=1, le=100),
    _user: dict = Depends(get_current_user),
):
    """Find candidates similar to a given candidate."""
    candidate = db.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    results = vectorstore.search_similar_candidates(
        candidate_id=candidate_id, n_results=n,
    )

    enriched = []
    for r in results:
        c = db.get_candidate(r["candidate_id"])
        if c:
            enriched.append({
                "candidate": c,
                "similarity_score": r["score"],
            })
    return enriched


@router.post("/text")
async def search_by_text(req: TextSearchRequest, _user: dict = Depends(get_current_user)):
    """Hybrid search: semantic similarity + keyword title boost for jobs."""
    if req.collection not in ("jobs", "candidates"):
        raise HTTPException(status_code=400, detail="collection must be 'jobs' or 'candidates'")

    if req.collection == "jobs":
        return _hybrid_search_jobs(req.query, req.n_results)

    # Candidates: pure semantic search
    results = vectorstore.search_by_text(
        collection_name="candidates",
        query_text=req.query,
        n_results=req.n_results,
    )
    enriched = []
    for r in results:
        record = db.get_candidate(r["candidate_id"])
        if record:
            enriched.append({"record": record, "similarity_score": r["score"]})
    return enriched


def _hybrid_search_jobs(query: str, n_results: int) -> list[dict]:
    """Combine semantic search with keyword matching on title/company.

    Scoring: hybrid = 0.5 * semantic + 0.5 * keyword_score
    Keyword score uses word-level matching so typos in one word don't
    destroy the whole score, and title matches are weighted heavily.
    """
    # 1) Semantic search — cast a wide net
    semantic_results = vectorstore.search_by_text(
        collection_name="jobs",
        query_text=query,
        n_results=min(n_results * 3, 60),
    )
    semantic_map: dict[str, float] = {}
    for r in semantic_results:
        semantic_map[r["job_id"]] = r["score"]

    # 2) Keyword search in SQLite — find jobs matching any query word in title/company
    query_words = _tokenize(query)
    keyword_hits = _keyword_search_jobs(query_words)

    # 3) Merge: union of both result sets
    all_job_ids = set(semantic_map.keys()) | set(keyword_hits.keys())

    scored: list[tuple[str, float]] = []
    for jid in all_job_ids:
        sem = semantic_map.get(jid, 0.0)
        kw = keyword_hits.get(jid, 0.0)
        # If both signals exist, blend them; otherwise rely on whichever is available
        if sem > 0 and kw > 0:
            hybrid = 0.4 * sem + 0.6 * kw
        elif kw > 0:
            hybrid = kw * 0.8  # keyword-only match (title matches without embedding)
        else:
            hybrid = sem * 0.6  # semantic-only (no title match = lower confidence)
        scored.append((jid, hybrid))

    scored.sort(key=lambda x: x[1], reverse=True)
    scored = scored[:n_results]

    # 4) Enrich with full records + vector-based candidate counts
    enriched = []
    for jid, score in scored:
        record = db.get_job(jid)
        if not record:
            continue
        # Enrich candidate_count with vector-based matching (same as list_jobs)
        try:
            rankings = vectorstore.search_candidates_for_job(jid, n_results=200)
            record["candidate_count"] = sum(
                1 for r in rankings if r["score"] >= MATCH_THRESHOLD
            )
        except Exception:
            pass
        enriched.append({"record": record, "similarity_score": round(score, 4)})
    return enriched


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase words, stripping punctuation."""
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 2]


def _keyword_search_jobs(query_words: list[str]) -> dict[str, float]:
    """Score all jobs by how many query words appear in title + company.

    Returns {job_id: score} where score is in [0, 1].
    Title matches count double compared to company matches.
    """
    if not query_words:
        return {}

    all_jobs = db.list_jobs()
    results: dict[str, float] = {}

    for job in all_jobs:
        title_lower = (job.get("title") or "").lower()
        company_lower = (job.get("company") or "").lower()
        title_tokens = set(_tokenize(title_lower))
        company_tokens = set(_tokenize(company_lower))

        title_hits = 0
        company_hits = 0
        for w in query_words:
            # Substring matching to handle partial/fuzzy: "learn" matches "learning"
            if any(w in t or t in w for t in title_tokens):
                title_hits += 1
            if any(w in t or t in w for t in company_tokens):
                company_hits += 1

        if title_hits == 0 and company_hits == 0:
            continue

        # Title match is worth 2x company match
        max_score = len(query_words) * 2  # all words in title
        raw = title_hits * 2 + company_hits
        results[job["id"]] = min(raw / max_score, 1.0)

    return results


@router.post("/reindex")
async def reindex_all(_user: dict = Depends(get_current_user)):
    """Rebuild all ChromaDB embeddings from SQLite data.

    Useful after first install, data migration, or model change.
    """
    jobs = db.list_jobs()
    candidates = db.list_candidates()

    job_count = vectorstore.reindex_all_jobs(jobs)
    candidate_count = vectorstore.reindex_all_candidates(candidates)

    return {
        "status": "ok",
        "jobs_indexed": job_count,
        "candidates_indexed": candidate_count,
    }


@router.get("/stats")
async def vector_stats(_user: dict = Depends(get_current_user)):
    """Return document counts in each ChromaDB collection."""
    return {
        "jobs_count": vectorstore.get_collection_count(vectorstore.JOBS_COLLECTION),
        "candidates_count": vectorstore.get_collection_count(vectorstore.CANDIDATES_COLLECTION),
    }
