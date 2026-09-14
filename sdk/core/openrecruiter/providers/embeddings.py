"""Embedding backends — one class per API shape, and a registry that names them.

A host picks a backend by name and gets the endpoint and a default model with it:

    Config(embedding_provider="cohere", embedding_api_key="...")

Four decisions shape this module.

*One class per API shape, not per vendor.* Most of the market speaks OpenAI's
``/v1/embeddings`` — ``{"model", "input"}`` in, ``data[].embedding`` out — so
Jina, Mistral, Ollama, vLLM and Text Embeddings Inference share one backend and
differ only by a row in `PROVIDERS`. Voyage, Cohere and Gemini each have a shape
of their own, and each gets a class. Adding another OpenAI-compatible vendor is
a row; adding a new shape is a class.

*Queries and documents are not embedded the same way.* Voyage and Cohere ask
which one a text is and answer differently for each — a query embedded as a
document retrieves measurably worse. ChromaDB 1.5 says which it wants by calling
``embed_query`` or ``embed_documents``, so the distinction is carried all the way
into the request body. Backends whose API has no such parameter ignore it.

*Keys and models are resolved per call, never captured.* Hosts let a user paste a
key into a settings screen after the process is up; a key captured at
construction means the index silently never works until a restart.

*A key is not always required.* A self-hosted endpoint usually has no auth, and
`local` has no endpoint at all, so "configured" is a per-provider question rather
than "is there a key".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

import httpx

log = logging.getLogger(__name__)

TIMEOUT = 60.0

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
COHERE_URL = "https://api.cohere.com/v2/embed"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

DEFAULT_LOCAL_MODEL = "BAAI/bge-small-en-v1.5"


@dataclass(frozen=True)
class Settings:
    """What a backend needs, after provider defaults have been applied."""

    provider: str
    url: str = ""
    key: str = ""
    model: str = ""


def _post(url: str, headers: dict[str, str], body: dict) -> dict:
    resp = httpx.post(url, headers=headers, json=body, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


class Embedder:
    """The interface ChromaDB expects, over one ``embed`` a subclass writes.

    chromadb 1.5 dispatches to ``embed_documents`` when adding and ``embed_query``
    when searching; earlier versions call the object. Subclasses implement
    ``embed`` once and inherit all three.
    """

    # ChromaDB persists an embedding function by name and rebuilds it later, so
    # these strings are part of the on-disk format. Changing one orphans every
    # collection written under the old name.
    chroma_name = ""

    def __init__(self, resolve: Callable[[], Settings] | None = None) -> None:
        # Optional so a subclass that needs no endpoint, key or model — one of
        # your own, holding whatever it likes — costs no ceremony to write.
        self._resolve = resolve or (lambda: Settings(provider=self.chroma_name))

    def embed(self, texts: list[str], *, query: bool) -> list[list[float]]:
        raise NotImplementedError

    # ── the ChromaDB surface ─────────────────────────────────────────────

    def embed_documents(self, input):  # noqa: A002 - chroma's name
        return self.embed(list(input), query=False)

    def embed_query(self, input):  # noqa: A002 - chroma's name
        return self.embed(list(input), query=True)

    def __call__(self, input):  # noqa: A002 - chroma's name
        # Pre-1.5 chroma calls the object for both, and cannot say which it
        # wants. Documents are the safe reading: indexing is the bulk of it.
        return self.embed(list(input), query=False)

    @classmethod
    def name(cls) -> str:
        return cls.chroma_name

    def get_config(self) -> dict:
        return {"model": self._resolve().model}

    @classmethod
    def build_from_config(cls, config: dict) -> "Embedder":
        model = config.get("model", "")
        return cls(lambda: Settings(provider=cls.chroma_name, model=model))

    def default_space(self) -> str:
        return "cosine"


class OpenAICompatibleEmbeddings(Embedder):
    """Any endpoint speaking OpenAI's ``/v1/embeddings``.

    The workhorse: OpenAI itself, Jina, Mistral, Ollama, vLLM, TEI, and every
    other host that copied the shape. The API has no query/document parameter,
    so both are embedded identically — which is what these models expect.
    """

    chroma_name = "openai"

    def embed(self, texts: list[str], *, query: bool) -> list[list[float]]:
        s = self._resolve()
        if not s.url:
            raise RuntimeError(
                "No embeddings endpoint configured — semantic search is unavailable."
            )
        # A self-hosted endpoint (vLLM, TEI, Ollama) usually has no auth at all.
        headers = _bearer(s.key) if s.key else {}
        data = _post(s.url, headers, {"input": texts, "model": s.model})["data"]
        # Some hosts answer out of order; every one of them tags the index.
        return [d["embedding"] for d in sorted(data, key=lambda d: d.get("index", 0))]


class VoyageEmbeddings(Embedder):
    """Voyage AI. OpenAI's response shape, plus an ``input_type`` that matters."""

    chroma_name = "voyage"

    def embed(self, texts: list[str], *, query: bool) -> list[list[float]]:
        s = self._resolve()
        if not s.key:
            raise RuntimeError(
                "No Voyage API key configured — semantic search is unavailable."
            )
        body = {
            "input": texts,
            "model": s.model,
            "input_type": "query" if query else "document",
        }
        data = _post(s.url or VOYAGE_URL, _bearer(s.key), body)["data"]
        return [d["embedding"] for d in sorted(data, key=lambda d: d["index"])]


class CohereEmbeddings(Embedder):
    """Cohere's v2 ``/embed``: ``texts`` in, ``embeddings.float`` out.

    ``input_type`` is required by the API, not optional as it is on Voyage, and
    ``embedding_types`` has to be asked for or the floats do not come back.
    """

    chroma_name = "cohere"

    def embed(self, texts: list[str], *, query: bool) -> list[list[float]]:
        s = self._resolve()
        if not s.key:
            raise RuntimeError(
                "No Cohere API key configured — semantic search is unavailable."
            )
        body = {
            "model": s.model,
            "texts": texts,
            "input_type": "search_query" if query else "search_document",
            "embedding_types": ["float"],
        }
        out = _post(s.url or COHERE_URL, _bearer(s.key), body)
        return out["embeddings"]["float"]


class GeminiEmbeddings(Embedder):
    """Google's Gemini embeddings, over ``batchEmbedContents``.

    The single-content call (``:embedContent``) answers a list of texts with one
    aggregated vector, which is not what a batch of documents means — so this
    always uses the batch method, whose ``embeddings`` come back one per request
    in order.
    """

    chroma_name = "gemini"

    def embed(self, texts: list[str], *, query: bool) -> list[list[float]]:
        s = self._resolve()
        if not s.key:
            raise RuntimeError(
                "No Gemini API key configured — semantic search is unavailable."
            )
        model = s.model
        base = s.url or GEMINI_BASE
        requests: list[dict[str, Any]] = [
            {"model": f"models/{model}", "content": {"parts": [{"text": t}]}}
            for t in texts
        ]
        # The gemini-embedding-001 family takes a task type and answers queries
        # and documents differently; the -2 family dropped it and rejects it.
        if not model.startswith("gemini-embedding-2"):
            task = "RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT"
            for req in requests:
                req["taskType"] = task
        out = _post(
            f"{base}/models/{model}:batchEmbedContents",
            {"x-goog-api-key": s.key},
            {"requests": requests},
        )
        return [e["values"] for e in out["embeddings"]]


class LocalEmbeddings(Embedder):
    """sentence-transformers, in this process, no API call and no key.

    The import is deferred to the first embed because it pulls torch: a package
    that merely *offers* local embeddings must not make every other install pay
    for them. Needs the extra:

        pip install 'openrecruiter[local-embeddings]'

    The model is loaded once and held. Query and document are embedded
    identically — the prompt-prefix conventions that would distinguish them are
    per-model, and guessing one wrong is worse than not using it.
    """

    chroma_name = "local"

    def __init__(self, resolve: Callable[[], Settings]) -> None:
        super().__init__(resolve)
        self._loaded: Any = None

    def embed(self, texts: list[str], *, query: bool) -> list[list[float]]:
        model = self._model()
        return model.encode(list(texts), normalize_embeddings=True).tolist()

    def _model(self) -> Any:
        if self._loaded is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - depends on the extra
                raise RuntimeError(
                    "Local embeddings need the optional extra: "
                    "pip install 'openrecruiter[local-embeddings]'"
                ) from exc
            name = self._resolve().model or DEFAULT_LOCAL_MODEL
            log.info("Loading local embedding model %s", name)
            self._loaded = SentenceTransformer(name)
        return self._loaded


@dataclass(frozen=True)
class Provider:
    """A named backend with its endpoint and a default model."""

    backend: type[Embedder]
    url: str = ""
    model: str = ""
    needs_key: bool = True
    needs_url: bool = True


# Model ids and endpoints move. Override them through `Config` rather than
# editing here; a row exists to save a caller from looking up a URL, not to pin
# a vendor's catalogue.
PROVIDERS: dict[str, Provider] = {
    "voyage": Provider(VoyageEmbeddings, VOYAGE_URL, "voyage-4-lite"),
    "cohere": Provider(CohereEmbeddings, COHERE_URL, "embed-v4.0"),
    "gemini": Provider(GeminiEmbeddings, GEMINI_BASE, "gemini-embedding-001"),
    "openai": Provider(
        OpenAICompatibleEmbeddings,
        "https://api.openai.com/v1/embeddings",
        "text-embedding-3-small",
    ),
    "jina": Provider(
        OpenAICompatibleEmbeddings,
        "https://api.jina.ai/v1/embeddings",
        "jina-embeddings-v5-text-small",
    ),
    "mistral": Provider(
        OpenAICompatibleEmbeddings,
        "https://api.mistral.ai/v1/embeddings",
        "mistral-embed",
    ),
    # Local servers that copied OpenAI's endpoint: no key, and the default port.
    "ollama": Provider(
        OpenAICompatibleEmbeddings,
        "http://localhost:11434/v1/embeddings",
        "nomic-embed-text",
        needs_key=False,
    ),
    # The escape hatch for everything not named above — Together, SiliconFlow,
    # DeepInfra, a vLLM or TEI server of your own. Bring the URL and the model.
    "openai_compatible": Provider(
        OpenAICompatibleEmbeddings, needs_key=False
    ),
    "local": Provider(
        LocalEmbeddings, model=DEFAULT_LOCAL_MODEL, needs_key=False, needs_url=False
    ),
}

DEFAULT_PROVIDER = "voyage"


def settings_for(config: Any) -> Settings | None:
    """What to embed with, or `None` when the config names no usable provider.

    `embedding_provider` is the answer when it is set. Without it the provider is
    inferred from what else is filled in, which keeps configs written before
    providers had names working: an endpoint means an OpenAI-compatible host, a
    Voyage key means Voyage.
    """
    provider = (getattr(config, "embedding_provider", "") or "").strip().lower()
    if not provider:
        if getattr(config, "embedding_api_url", ""):
            provider = "openai_compatible"
        elif getattr(config, "voyage_api_key", ""):
            provider = DEFAULT_PROVIDER
        else:
            return None
    spec = PROVIDERS.get(provider)
    if spec is None:
        log.warning(
            "Unknown embedding provider %r — known: %s",
            provider,
            ", ".join(sorted(PROVIDERS)),
        )
        return None

    key = getattr(config, "embedding_api_key", "")
    model = getattr(config, "embedding_model", "")
    if provider == DEFAULT_PROVIDER:
        # Voyage had its own pair of fields before providers were named.
        key = key or getattr(config, "voyage_api_key", "")
        model = model or getattr(config, "voyage_model", "")
    return Settings(
        provider=provider,
        url=getattr(config, "embedding_api_url", "") or spec.url,
        key=key,
        model=model or spec.model,
    )


def configured(config: Any) -> bool:
    """Whether embedding calls can be attempted — presence, never validity.

    A key is checked for being there, not for working: see the vector store on
    why a bad key must cost retrieval rather than the record being saved.
    """
    s = settings_for(config)
    if s is None:
        return False
    spec = PROVIDERS[s.provider]
    return (bool(s.key) or not spec.needs_key) and (bool(s.url) or not spec.needs_url)


def embedder_for(config: Callable[[], Any]) -> Embedder:
    """The backend a config asks for, resolving its settings on every call.

    The provider is read once — it decides the class, and a collection on disk is
    tied to it — while the key, model and URL are read per call.
    """
    initial = settings_for(config())
    provider = initial.provider if initial else DEFAULT_PROVIDER

    def resolve() -> Settings:
        return settings_for(config()) or Settings(provider=provider)

    return PROVIDERS[provider].backend(resolve)


def stamp(config: Any) -> str:
    """`provider:model` — what a collection's vectors were written with.

    Vectors from two models are not comparable, so this is recorded alongside a
    collection and compared when it is reopened.
    """
    s = settings_for(config)
    return f"{s.provider}:{s.model}" if s else ""


__all__ = [
    "CohereEmbeddings",
    "Embedder",
    "GeminiEmbeddings",
    "LocalEmbeddings",
    "OpenAICompatibleEmbeddings",
    "PROVIDERS",
    "Provider",
    "Settings",
    "VoyageEmbeddings",
    "configured",
    "embedder_for",
    "settings_for",
    "stamp",
]
