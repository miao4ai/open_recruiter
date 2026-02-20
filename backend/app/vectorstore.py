"""ChromaDB vector store with local BGE embeddings — semantic search layer.

SQLite (database.py) handles structured CRUD.
ChromaDB (this module) handles vector embeddings for semantic search.
Both share record IDs for cross-referencing.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import chromadb
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
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


# ── ONNX Embedding Function ─────────────────────────────────────────────


def _find_model_dir() -> str | None:
    """Locate the ONNX embedding model directory."""
    # PyInstaller bundle
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        d = os.path.join(meipass, "models")
        if os.path.isdir(d):
            return d
    # Development: backend/models/
    d = str(Path(__file__).resolve().parent.parent / "models")
    if os.path.isdir(d):
        return d
    return None


class _OnnxEmbeddingFunction:
    """ChromaDB-compatible embedding function using ONNX Runtime.

    Replaces SentenceTransformerEmbeddingFunction to avoid bundling PyTorch
    (~800 MB).  Only requires onnxruntime (~30 MB) + tokenizers (~5 MB).
    """

    def __init__(self, model_dir: str) -> None:
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer as HFTokenizer

        self._np = np

        tok_path = os.path.join(model_dir, "tokenizer.json")
        model_path = os.path.join(model_dir, "model.onnx")

        self._tokenizer = HFTokenizer.from_file(tok_path)
        self._tokenizer.enable_padding()
        self._tokenizer.enable_truncation(max_length=512)

        self._session = ort.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"],
        )
        self._input_names = {inp.name for inp in self._session.get_inputs()}

    def __call__(self, input: list[str]) -> list[list[float]]:
        if not input:
            return []

        np = self._np
        encoded = self._tokenizer.encode_batch(input)

        input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
        attention_mask = np.array(
            [e.attention_mask for e in encoded], dtype=np.int64
        )

        feed: dict[str, Any] = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        if "token_type_ids" in self._input_names:
            feed["token_type_ids"] = np.zeros_like(input_ids)

        outputs = self._session.run(None, feed)

        # outputs[0] shape: (batch, seq_len, hidden_size)
        embeddings = outputs[0]

        # Mean pooling with attention mask
        mask = attention_mask[:, :, np.newaxis].astype(np.float32)
        pooled = (embeddings * mask).sum(axis=1) / mask.sum(axis=1)

        # L2 normalize
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        normalized = pooled / np.maximum(norms, 1e-12)

        return normalized.tolist()


# ── Initialisation ────────────────────────────────────────────────────────


def init_vectorstore() -> None:
    """Load embedding model and create ChromaDB persistent client.

    Called once during FastAPI lifespan startup.
    """
    global _client, _embedding_fn

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    model_dir = _find_model_dir()
    onnx_path = os.path.join(model_dir, "model.onnx") if model_dir else None

    if onnx_path and os.path.isfile(onnx_path):
        log.info("Loading ONNX embedding model from %s", model_dir)
        _embedding_fn = _OnnxEmbeddingFunction(model_dir)
    else:
        # Fallback: sentence-transformers (for dev without ONNX export)
        from chromadb.utils.embedding_functions import (
            SentenceTransformerEmbeddingFunction,
        )

        log.info("Loading sentence-transformers model: %s", EMBEDDING_MODEL)
        _embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL,
        )

    log.info("Embedding model loaded.")

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

    Prioritises summary and skills (high signal) since BGE has a 512-token
    window and we want the most important content first.
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
