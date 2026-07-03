"""ChromaDB vector store with Voyage embeddings — semantic search layer.

SQLite (database.py) handles structured CRUD.
ChromaDB (this module) handles vector storage for semantic search; embeddings
are produced by the Voyage AI API (no local model, no PyTorch/onnxruntime).
Both share record IDs for cross-referencing.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from chromadb.config import Settings as ChromaSettings

log = logging.getLogger(__name__)

# Persist ChromaDB next to the SQLite database
_data_dir = os.environ.get("OPEN_RECRUITER_DATA_DIR")
if _data_dir:
    CHROMA_DIR = Path(_data_dir) / "chroma_data"
else:
    CHROMA_DIR = Path(__file__).resolve().parent.parent / "chroma_data"

# Module-level singletons (populated by init_vectorstore)
_client: chromadb.ClientAPI | None = None
_embedding_fn: Any = None

JOBS_COLLECTION = "jobs"
CANDIDATES_COLLECTION = "candidates"
CHAT_SUMMARIES_COLLECTION = "chat_summaries"

VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = "voyage-4-lite"


# ── Voyage Embedding Function ───────────────────────────────────────────


class _VoyageEmbeddingFunction(EmbeddingFunction):
    """ChromaDB embedding function backed by the Voyage AI API.

    Replaces the local ONNX/BGE model — no PyTorch, no onnxruntime, no bundled
    weights (~170 MB saved).  Requires a Voyage API key and network access.
    """

    def __init__(self, api_key: str, model: str = VOYAGE_MODEL) -> None:
        self._api_key = api_key
        self._model = model or VOYAGE_MODEL

    def __call__(self, input: Documents) -> Embeddings:
        if not input:
            return []
        if not self._api_key:
            raise RuntimeError(
                "Voyage API key not configured — set VOYAGE_API_KEY or add it in Settings."
            )

        import httpx

        resp = httpx.post(
            VOYAGE_API_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"input": list(input), "model": self._model},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        # Voyage tags each item with its `index`; sort to preserve input order.
        data.sort(key=lambda d: d["index"])
        return [d["embedding"] for d in data]

    @staticmethod
    def name() -> str:
        return "voyage"

    def get_config(self) -> dict:
        return {"model": self._model}

    @staticmethod
    def build_from_config(config: dict) -> "_VoyageEmbeddingFunction":
        # The API key is injected at init from app config, never persisted.
        return _VoyageEmbeddingFunction(api_key="", model=config.get("model", VOYAGE_MODEL))

    def default_space(self) -> str:
        return "cosine"


# ── Initialisation ────────────────────────────────────────────────────────


def init_vectorstore() -> None:
    """Load embedding model and create ChromaDB persistent client.

    Called once during FastAPI lifespan startup.
    """
    global _client, _embedding_fn

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    # Lazy import avoids a circular import at module load time.
    from app.routes.settings import get_config

    cfg = get_config()
    _embedding_fn = _VoyageEmbeddingFunction(cfg.voyage_api_key, cfg.voyage_model)
    log.info("Voyage embedding model: %s", cfg.voyage_model or VOYAGE_MODEL)

    _client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    _client.get_or_create_collection(
        name=JOBS_COLLECTION,
        embedding_function=_embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )
    _client.get_or_create_collection(
        name=CANDIDATES_COLLECTION,
        embedding_function=_embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )
    _client.get_or_create_collection(
        name=CHAT_SUMMARIES_COLLECTION,
        embedding_function=_embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )
    log.info("ChromaDB initialized at %s", CHROMA_DIR)


def _get_collection(name: str) -> chromadb.Collection:
    if _client is None or _embedding_fn is None:
        raise RuntimeError("Vectorstore not initialised — call init_vectorstore() first")
    return _client.get_collection(name=name, embedding_function=_embedding_fn)


# ── Index / Remove ────────────────────────────────────────────────────────


def index_job(job_id: str, text: str, metadata: dict) -> None:
    col = _get_collection(JOBS_COLLECTION)
    col.upsert(ids=[job_id], documents=[text], metadatas=[metadata])


def index_candidate(candidate_id: str, text: str, metadata: dict) -> None:
    col = _get_collection(CANDIDATES_COLLECTION)
    col.upsert(ids=[candidate_id], documents=[text], metadatas=[metadata])


def remove_job(job_id: str) -> None:
    col = _get_collection(JOBS_COLLECTION)
    col.delete(ids=[job_id])


def remove_candidate(candidate_id: str) -> None:
    col = _get_collection(CANDIDATES_COLLECTION)
    col.delete(ids=[candidate_id])


# ── Search ────────────────────────────────────────────────────────────────


def search_candidates_for_job(
    job_id: str,
    n_results: int = 20,
    job_id_filter: str | None = None,
) -> list[dict]:
    """Find candidates semantically similar to a job description."""
    jobs_col = _get_collection(JOBS_COLLECTION)
    candidates_col = _get_collection(CANDIDATES_COLLECTION)

    job_result = jobs_col.get(ids=[job_id], include=["documents"])
    if not job_result["documents"]:
        return []
    job_text = job_result["documents"][0]

    where = None
    if job_id_filter:
        where = {"job_id": job_id_filter}

    results = candidates_col.query(
        query_texts=[job_text],
        n_results=n_results,
        where=where,
        include=["distances", "metadatas"],
    )

    output = []
    for i, cid in enumerate(results["ids"][0]):
        dist = results["distances"][0][i]
        output.append({
            "candidate_id": cid,
            "distance": dist,
            "score": round(1.0 - dist, 4),
            "metadata": results["metadatas"][0][i],
        })
    return output


def search_jobs_for_candidate(
    candidate_id: str,
    n_results: int = 5,
    candidate_text: str | None = None,
) -> list[dict]:
    """Find jobs semantically similar to a candidate's profile.

    If *candidate_text* is supplied it is used directly for the query,
    avoiding a round-trip ``get`` to ChromaDB (important right after
    indexing when the document may not yet be readable).
    """
    jobs_col = _get_collection(JOBS_COLLECTION)

    if not candidate_text:
        candidates_col = _get_collection(CANDIDATES_COLLECTION)
        result = candidates_col.get(ids=[candidate_id], include=["documents"])
        if not result["documents"] or not result["documents"][0]:
            log.warning("search_jobs_for_candidate: no document found for %s", candidate_id)
            return []
        candidate_text = result["documents"][0]

    results = jobs_col.query(
        query_texts=[candidate_text],
        n_results=n_results,
        include=["distances", "metadatas"],
    )

    output = []
    for i, jid in enumerate(results["ids"][0]):
        dist = results["distances"][0][i]
        output.append({
            "job_id": jid,
            "distance": dist,
            "score": round(1.0 - dist, 4),
            "metadata": results["metadatas"][0][i],
        })
    return output


def search_similar_candidates(
    candidate_id: str,
    n_results: int = 10,
) -> list[dict]:
    """Find candidates similar to a given candidate."""
    col = _get_collection(CANDIDATES_COLLECTION)

    result = col.get(ids=[candidate_id], include=["documents"])
    if not result["documents"]:
        return []
    text = result["documents"][0]

    results = col.query(
        query_texts=[text],
        n_results=n_results + 1,  # +1 to exclude self
        include=["distances", "metadatas"],
    )

    output = []
    for i, cid in enumerate(results["ids"][0]):
        if cid == candidate_id:
            continue
        dist = results["distances"][0][i]
        output.append({
            "candidate_id": cid,
            "distance": dist,
            "score": round(1.0 - dist, 4),
            "metadata": results["metadatas"][0][i],
        })
    return output[:n_results]


def search_by_text(
    collection_name: str,
    query_text: str,
    n_results: int = 10,
    where: dict | None = None,
) -> list[dict]:
    """Free-text semantic search against any collection."""
    col = _get_collection(collection_name)
    kwargs: dict[str, Any] = {
        "query_texts": [query_text],
        "n_results": n_results,
        "include": ["distances", "metadatas"],
    }
    if where:
        kwargs["where"] = where

    results = col.query(**kwargs)

    id_key = "candidate_id" if collection_name == CANDIDATES_COLLECTION else "job_id"
    output = []
    for i, rid in enumerate(results["ids"][0]):
        dist = results["distances"][0][i]
        output.append({
            id_key: rid,
            "distance": dist,
            "score": round(1.0 - dist, 4),
            "metadata": results["metadatas"][0][i],
        })
    return output


# ── Stats / Reindex ───────────────────────────────────────────────────────


def get_collection_count(name: str) -> int:
    col = _get_collection(name)
    return col.count()


def reindex_all_jobs(jobs: list[dict]) -> int:
    col = _get_collection(JOBS_COLLECTION)
    count = 0
    for j in jobs:
        text = j.get("raw_text", "")
        if not text:
            continue
        col.upsert(
            ids=[j["id"]],
            documents=[text],
            metadatas={"title": j.get("title", ""), "company": j.get("company", "")},
        )
        count += 1
    return count


def reindex_all_candidates(candidates: list[dict]) -> int:
    col = _get_collection(CANDIDATES_COLLECTION)
    count = 0
    for c in candidates:
        text = build_candidate_embed_text(c)
        if not text.strip():
            continue
        col.upsert(
            ids=[c["id"]],
            documents=[text],
            metadatas={
                "name": c.get("name", ""),
                "job_id": c.get("job_id", ""),
                "current_title": c.get("current_title", ""),
            },
        )
        count += 1
    return count


def build_candidate_embed_text(c: dict | object) -> str:
    """Build text to embed for a candidate.

    Prioritises summary and skills (high signal) so the most important content
    leads the embedded text.
    """
    # Support both dicts and Pydantic model instances
    def _get(key: str, default=""):
        if isinstance(c, dict):
            return c.get(key, default)
        return getattr(c, key, default)

    parts = []
    summary = _get("resume_summary")
    if summary:
        parts.append(summary)
    skills = _get("skills", [])
    if skills:
        if isinstance(skills, list):
            parts.append(f"Skills: {', '.join(skills)}")
        else:
            parts.append(f"Skills: {skills}")
    title = _get("current_title")
    if title:
        parts.append(f"Current role: {title}")
    return "\n\n".join(parts)


# ── Session Summary Vectors ──────────────────────────────────────────────


def index_session_summary(summary_id: str, text: str, metadata: dict) -> None:
    col = _get_collection(CHAT_SUMMARIES_COLLECTION)
    col.upsert(ids=[summary_id], documents=[text], metadatas=[metadata])


def search_session_summaries(
    query_text: str,
    user_id: str,
    n_results: int = 3,
) -> list[dict]:
    """Find past session summaries semantically relevant to a query."""
    col = _get_collection(CHAT_SUMMARIES_COLLECTION)
    if col.count() == 0:
        return []
    results = col.query(
        query_texts=[query_text],
        n_results=min(n_results, col.count()),
        where={"user_id": user_id},
        include=["distances", "metadatas", "documents"],
    )
    output = []
    for i, sid in enumerate(results["ids"][0]):
        dist = results["distances"][0][i]
        output.append({
            "id": sid,
            "distance": dist,
            "score": round(1.0 - dist, 4),
            "metadata": results["metadatas"][0][i],
            "document": results["documents"][0][i],
        })
    return output


def remove_session_summary(summary_id: str) -> None:
    col = _get_collection(CHAT_SUMMARIES_COLLECTION)
    col.delete(ids=[summary_id])
