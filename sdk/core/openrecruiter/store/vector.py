"""Semantic retrieval over ChromaDB with Voyage embeddings.

Embeddings are an API call, never a local model: no PyTorch, no ONNX runtime,
nothing to download at import or at startup. Without a Voyage key this class
reports `available == False` and every search returns nothing, so a caller can
fall back to keyword search instead of failing.

ChromaDB is imported lazily so that `import openrecruiter` stays cheap for the
many callers who never touch retrieval.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

import httpx

from openrecruiter.config import Config
from openrecruiter.types import Candidate, Job

log = logging.getLogger(__name__)

VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"
JOBS_COLLECTION = "jobs"
CANDIDATES_COLLECTION = "candidates"


class VoyageEmbeddings:
    """A ChromaDB embedding function backed by the Voyage API.

    The key is resolved through a callable on every call rather than captured at
    construction. Hosts let users paste a key into a settings screen *after* the
    process has started; capturing it once means the index silently never works
    until a restart.
    """

    def __init__(self, resolve: Callable[[], tuple[str, str]]) -> None:
        self._resolve = resolve

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002 - Chroma's name
        api_key, model = self._resolve()
        if not api_key:
            raise RuntimeError(
                "No Voyage API key configured — semantic search is unavailable."
            )
        resp = httpx.post(
            VOYAGE_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"input": list(input), "model": model, "input_type": "document"},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        # Voyage tags each item with its index; sort so order matches the input.
        return [item["embedding"] for item in sorted(data, key=lambda d: d["index"])]

    # ChromaDB persists and rebuilds embedding functions by name.
    @staticmethod
    def name() -> str:
        return "voyage"

    def get_config(self) -> dict:
        return {"model": self._resolve()[1]}

    @staticmethod
    def build_from_config(config: dict) -> "VoyageEmbeddings":
        model = config.get("model", "voyage-4-lite")
        return VoyageEmbeddings(lambda: ("", model))

    def default_space(self) -> str:
        return "cosine"


class ChromaVectorIndex:
    """A `VectorIndex` over a persistent ChromaDB directory."""

    def __init__(
        self,
        config: Config | Callable[[], Config],
        path: str | Path = "chroma_data",
    ) -> None:
        # Accept a callable so a host whose settings change at runtime stays correct.
        self._config = config if callable(config) else (lambda: config)
        self.path = Path(path)
        self._client: Any = None

    @property
    def available(self) -> bool:
        return bool(self._config().voyage_api_key)

    def _collection(self, name: str) -> Any:
        if self._client is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            self.path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self.path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        embed = VoyageEmbeddings(
            lambda: (self._config().voyage_api_key, self._config().voyage_model)
        )
        return self._client.get_or_create_collection(
            name=name, embedding_function=embed, metadata={"hnsw:space": "cosine"}
        )

    # ── indexing ─────────────────────────────────────────────────────────

    def index_job(self, job: Job) -> None:
        text = job.embed_text()
        if not text or not self.available:
            return
        self._collection(JOBS_COLLECTION).upsert(
            ids=[job.id],
            documents=[text],
            metadatas=[{"title": job.title, "company": job.company}],
        )

    def index_candidate(self, candidate: Candidate) -> None:
        text = candidate.embed_text()
        if not text or not self.available:
            return
        self._collection(CANDIDATES_COLLECTION).upsert(
            ids=[candidate.id],
            documents=[text],
            metadatas=[{"name": candidate.name, "title": candidate.current_title}],
        )

    def remove_job(self, job_id: str) -> None:
        if self.available:
            self._collection(JOBS_COLLECTION).delete(ids=[job_id])

    def remove_candidate(self, candidate_id: str) -> None:
        if self.available:
            self._collection(CANDIDATES_COLLECTION).delete(ids=[candidate_id])

    # ── search ───────────────────────────────────────────────────────────

    def search_candidates(self, job: Job, top_k: int = 20) -> list[tuple[str, float]]:
        return self._query(CANDIDATES_COLLECTION, job.embed_text(), top_k)

    def search_jobs(self, candidate: Candidate, top_k: int = 10) -> list[tuple[str, float]]:
        return self._query(JOBS_COLLECTION, candidate.embed_text(), top_k)

    def _query(self, collection: str, text: str, top_k: int) -> list[tuple[str, float]]:
        if not text or not self.available:
            return []
        try:
            res = self._collection(collection).query(
                query_texts=[text], n_results=top_k, include=["distances"]
            )
        except Exception as exc:
            # Retrieval failing should degrade the result set, not the request.
            log.warning("Vector search on %s failed: %s", collection, exc)
            return []
        ids = res.get("ids", [[]])[0]
        distances = res.get("distances", [[]])[0]
        # Cosine distance -> similarity, clamped: an empty index and a bad key
        # both look like "no results", never like a negative score.
        return [
            (rid, round(max(0.0, min(1.0, 1.0 - dist)), 4))
            for rid, dist in zip(ids, distances)
        ]


__all__ = ["ChromaVectorIndex", "VoyageEmbeddings"]
