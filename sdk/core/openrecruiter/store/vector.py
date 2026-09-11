"""Semantic retrieval over ChromaDB with API embeddings.

Embeddings are an API call, never a local model: no PyTorch, no ONNX runtime,
nothing to download at import or at startup. Two shapes of API: Voyage, or any
OpenAI-compatible `/v1/embeddings` endpoint (a self-hosted model behind one).
Without either configured this class reports `available == False` and every
search returns nothing, so a caller can fall back to keyword search instead of
failing.

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


class _ChromaEF:
    """chromadb 1.5 dispatches to ``embed_documents`` (add) and ``embed_query``
    (search); earlier versions call the object. Subclasses implement ``__call__``
    only; these two forward to it so one class works across versions."""

    def embed_documents(self, input):  # noqa: A002 - chroma's name
        return self(input)

    def embed_query(self, input):  # noqa: A002 - chroma's name
        return self(input)


class VoyageEmbeddings(_ChromaEF):
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


class OpenAIEmbeddings(_ChromaEF):
    """A ChromaDB embedding function over an OpenAI-compatible endpoint:
    `POST <url> {"model", "input": [...]}` → `{"data": [{"index", "embedding"}]}`.
    Resolved per call, like Voyage, so a key set at runtime applies."""

    def __init__(self, resolve: Callable[[], tuple[str, str, str]]) -> None:
        self._resolve = resolve  # → (url, api_key, model)

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002 - Chroma's name
        url, api_key, model = self._resolve()
        if not url or not api_key:
            raise RuntimeError("No embeddings endpoint configured — semantic search is unavailable.")
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"input": list(input), "model": model},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        return [item["embedding"] for item in sorted(data, key=lambda d: d.get("index", 0))]

    @staticmethod
    def name() -> str:
        return "openai"

    def get_config(self) -> dict:
        return {"model": self._resolve()[2]}

    @staticmethod
    def build_from_config(config: dict) -> "OpenAIEmbeddings":
        model = config.get("model", "")
        return OpenAIEmbeddings(lambda: ("", "", model))

    def default_space(self) -> str:
        return "cosine"


def embeddings_configured(config: Config) -> bool:
    return bool(config.embedding_api_url and config.embedding_api_key) or bool(config.voyage_api_key)


def embedding_function(resolve: Callable[[], Config]) -> Any:
    """The embedder a config asks for: the OpenAI-compatible endpoint when one
    is set, else Voyage. Decided at collection-open time, per call thereafter."""
    if resolve().embedding_api_url:
        return OpenAIEmbeddings(
            lambda: (resolve().embedding_api_url, resolve().embedding_api_key, resolve().embedding_model)
        )
    return VoyageEmbeddings(lambda: (resolve().voyage_api_key, resolve().voyage_model))


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
        return embeddings_configured(self._config())

    def _collection(self, name: str) -> Any:
        if self._client is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            self.path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self.path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        embed = embedding_function(self._config)
        return self._client.get_or_create_collection(
            name=name, embedding_function=embed, metadata={"hnsw:space": "cosine"}
        )

    # ── indexing ─────────────────────────────────────────────────────────

    def index_job(self, job: Job) -> None:
        self._upsert(
            JOBS_COLLECTION,
            job.id,
            job.embed_text(),
            {"title": job.title, "company": job.company},
        )

    def index_candidate(self, candidate: Candidate) -> None:
        self._upsert(
            CANDIDATES_COLLECTION,
            candidate.id,
            candidate.embed_text(),
            {"name": candidate.name, "title": candidate.current_title},
        )

    def _upsert(self, collection: str, record_id: str, text: str, metadata: dict) -> None:
        """Index one record. A failure costs retrieval, not the record.

        The key is only checked for presence, never for validity, so a typo or
        an expired key reaches the API. Letting that raise would mean a wrong
        embedding key stops the user adding a candidate at all — losing the data
        to protect the index, which is backwards. The record is already stored
        by the time this runs; reindexing can recover the rest.
        """
        if not text or not self.available:
            return
        try:
            self._collection(collection).upsert(
                ids=[record_id], documents=[text], metadatas=[metadata]
            )
        except Exception as exc:  # noqa: BLE001 - network, auth, quota, disk
            log.warning("Could not index %s in %s: %s", record_id, collection, exc)

    def remove_job(self, job_id: str) -> None:
        self._delete(JOBS_COLLECTION, job_id)

    def remove_candidate(self, candidate_id: str) -> None:
        self._delete(CANDIDATES_COLLECTION, candidate_id)

    def _delete(self, collection: str, record_id: str) -> None:
        if not self.available:
            return
        try:
            self._collection(collection).delete(ids=[record_id])
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not remove %s from %s: %s", record_id, collection, exc)

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


__all__ = ["ChromaVectorIndex", "OpenAIEmbeddings", "VoyageEmbeddings", "embeddings_configured"]
