"""Search routes — semantic similarity powered by ChromaDB."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app import database as db
from app import vectorstore

router = APIRouter()


class TextSearchRequest(BaseModel):
    query: str
    collection: str = "candidates"
    n_results: int = 10


@router.get("/candidates-for-job/{job_id}")
async def search_candidates_for_job(
    job_id: str,
    n: int = Query(20, ge=1, le=100, description="Number of results"),
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
async def search_by_text(req: TextSearchRequest):
    """Free-text semantic search against jobs or candidates."""
    if req.collection not in ("jobs", "candidates"):
        raise HTTPException(status_code=400, detail="collection must be 'jobs' or 'candidates'")

    results = vectorstore.search_by_text(
        collection_name=req.collection,
        query_text=req.query,
        n_results=req.n_results,
    )

    enriched = []
    for r in results:
        record_id = r.get("candidate_id") or r.get("job_id")
        if req.collection == "candidates":
            record = db.get_candidate(record_id)
        else:
            record = db.get_job(record_id)
        if record:
            enriched.append({
                "record": record,
                "similarity_score": r["score"],
            })
    return enriched


@router.post("/reindex")
async def reindex_all():
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
async def vector_stats():
    """Return document counts in each ChromaDB collection."""
    return {
        "jobs_count": vectorstore.get_collection_count(vectorstore.JOBS_COLLECTION),
        "candidates_count": vectorstore.get_collection_count(vectorstore.CANDIDATES_COLLECTION),
    }
