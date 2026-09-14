"""Semantic retrieval over ChromaDB, with the embedding backend left open.

Which backend is a configuration question, answered in
`openrecruiter.providers.embeddings`: Voyage by default, Cohere, Gemini, any
OpenAI-compatible endpoint, or a local sentence-transformers model behind an
optional extra. Nothing heavy is imported unless that last one is asked for, so
a normal install still has no torch in it.

An embedder can also be handed in whole — ``ChromaVectorIndex(config,
embedder=...)`` — for a backend this package has never heard of.

With nothing configured this class reports ``available == False`` and every
search returns nothing, so a caller can fall back to keyword search instead of
failing. ChromaDB itself is imported lazily so that ``import openrecruiter``
stays cheap for the many callers who never touch retrieval.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from openrecruiter.config import Config
from openrecruiter.providers.embeddings import (
    Embedder,
    OpenAICompatibleEmbeddings,
    VoyageEmbeddings,
    configured,
    embedder_for,
)
from openrecruiter.types import Candidate, Job

log = logging.getLogger(__name__)

JOBS_COLLECTION = "jobs"
CANDIDATES_COLLECTION = "candidates"

# Recorded on each collection so reopening it with a different embedder is
# caught rather than silently answered with incomparable vectors.
EMBEDDER_KEY = "openrecruiter:embedder"

# The old name for the OpenAI-compatible backend, kept so existing imports work.
OpenAIEmbeddings = OpenAICompatibleEmbeddings


class EmbedderMismatch(RuntimeError):
    """A collection was written by a different embedder than the one configured."""


def embeddings_configured(config: Config) -> bool:
    return configured(config)


def embedding_function(resolve: Callable[[], Config]) -> Embedder:
    """The embedder a config asks for, by provider name."""
    return embedder_for(resolve)


class ChromaVectorIndex:
    """A `VectorIndex` over a persistent ChromaDB directory."""

    def __init__(
        self,
        config: Config | Callable[[], Config],
        path: str | Path = "chroma_data",
        *,
        embedder: Any = None,
    ) -> None:
        # Accept a callable so a host whose settings change at runtime stays correct.
        self._config = config if callable(config) else (lambda: config)
        self.path = Path(path)
        self._embedder = embedder
        self._client: Any = None

    @property
    def available(self) -> bool:
        # A hand-built embedder answers for itself; there is no config to inspect.
        return True if self._embedder is not None else embeddings_configured(self._config())

    def _embed(self) -> Any:
        return self._embedder if self._embedder is not None else embedding_function(self._config)

    def _collection(self, name: str) -> Any:
        if self._client is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            self.path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self.path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        embed = self._embed()
        stamp = _stamp(embed)
        collection = self._client.get_or_create_collection(
            name=name,
            embedding_function=embed,
            metadata={"hnsw:space": "cosine", EMBEDDER_KEY: stamp},
        )
        _check_embedder(collection, stamp, name)
        return collection

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
        except EmbedderMismatch as exc:
            log.error("%s", exc)
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
        except EmbedderMismatch as exc:
            log.error("%s", exc)
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
        except EmbedderMismatch as exc:
            # Returning nothing is the point: the alternative is a ranked list
            # of confident nonsense drawn from an incomparable vector space.
            log.error("%s", exc)
            return []
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


def _stamp(embed: Any) -> str:
    """`provider:model` for whatever embedder this is, including a custom one."""
    name = getattr(embed, "name", None)
    provider = name() if callable(name) else type(embed).__name__
    model = ""
    try:
        model = (embed.get_config() or {}).get("model", "")
    except Exception:  # noqa: BLE001 - a custom embedder need not implement it
        pass
    return f"{provider}:{model}"


def _check_embedder(collection: Any, stamp: str, name: str) -> None:
    """Refuse a collection whose vectors were written by a different embedder.

    Two models' vectors are not comparable, so reusing an index across a provider
    or model change produces plausible, wrong neighbours — the worst failure this
    module has, because nothing looks broken. A collection written before the
    stamp existed carries no record of its embedder and is left alone: there is
    nothing to compare, and refusing every older index would be worse.
    """
    written = (getattr(collection, "metadata", None) or {}).get(EMBEDDER_KEY)
    if not written or written == stamp:
        return
    raise EmbedderMismatch(
        f"Collection {name!r} was indexed with {written!r} but {stamp!r} is configured. "
        f"Vectors from two models cannot be compared: reindex after the change, "
        f"or point the index at a different directory."
    )


# The other backends live in `openrecruiter.providers.embeddings`; these two are
# re-exported because they were importable from here before the registry existed.
__all__ = [
    "ChromaVectorIndex",
    "EmbedderMismatch",
    "OpenAICompatibleEmbeddings",
    "OpenAIEmbeddings",
    "VoyageEmbeddings",
    "embedding_function",
    "embeddings_configured",
]
