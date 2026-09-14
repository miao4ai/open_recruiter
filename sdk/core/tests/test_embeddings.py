"""The embedding backends: what goes on the wire, and when one is usable.

Each backend is checked against the request body its vendor documents, because
that is the part no amount of local testing exercises — a wrong field name fails
only against the live API, in production, as an empty index.
"""

from __future__ import annotations

import pytest

from openrecruiter.config import Config
from openrecruiter.providers import embeddings as backends
from openrecruiter.providers.embeddings import (
    PROVIDERS,
    CohereEmbeddings,
    GeminiEmbeddings,
    LocalEmbeddings,
    OpenAICompatibleEmbeddings,
    Settings,
    VoyageEmbeddings,
    configured,
    embedder_for,
    settings_for,
)


@pytest.fixture
def wire(monkeypatch):
    """Capture the one request a backend makes, and answer it."""
    seen: dict = {}

    def answer(payload):
        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return payload

        def fake_post(url, headers, json, timeout):
            seen.update(url=url, headers=headers, body=json)
            return Resp()

        monkeypatch.setattr(backends.httpx, "post", fake_post)
        return seen

    answer.seen = seen  # type: ignore[attr-defined]
    return answer


# ── picking a backend by name ────────────────────────────────────────────────


def test_a_provider_name_brings_its_endpoint_and_model():
    """The point of the registry: name a vendor, not a URL."""
    s = settings_for(Config(embedding_provider="cohere", embedding_api_key="k"))
    assert s == Settings("cohere", backends.COHERE_URL, "k", "embed-v4.0")
    assert isinstance(embedder_for(lambda: Config(embedding_provider="cohere", embedding_api_key="k")), CohereEmbeddings)


def test_the_url_and_model_are_still_overridable():
    s = settings_for(
        Config(
            embedding_provider="openai",
            embedding_api_key="k",
            embedding_api_url="https://proxy.internal/v1/embeddings",
            embedding_model="text-embedding-3-large",
        )
    )
    assert s.url == "https://proxy.internal/v1/embeddings"
    assert s.model == "text-embedding-3-large"


def test_every_openai_shaped_vendor_shares_one_backend():
    """Adding such a vendor should be a row in the registry, never a class."""
    for name in ("openai", "jina", "mistral", "ollama", "openai_compatible"):
        assert PROVIDERS[name].backend is OpenAICompatibleEmbeddings


def test_configs_written_before_providers_had_names_still_work():
    """Back-compat: an endpoint meant OpenAI-compatible, a Voyage key meant Voyage."""
    assert settings_for(Config(voyage_api_key="pa-x")).provider == "voyage"
    assert settings_for(Config(embedding_api_url="https://x/v1/embeddings", embedding_api_key="k")).provider == "openai_compatible"
    assert settings_for(Config()) is None


def test_voyages_own_key_field_is_still_read():
    s = settings_for(Config(embedding_provider="voyage", voyage_api_key="pa-x"))
    assert s.key == "pa-x" and s.model == "voyage-4-lite"


def test_an_unknown_provider_is_refused_not_guessed(caplog):
    with caplog.at_level("WARNING"):
        assert settings_for(Config(embedding_provider="nope", embedding_api_key="k")) is None
    assert "Unknown embedding provider" in caplog.text


# ── when is a backend usable ─────────────────────────────────────────────────


def test_configured_is_a_per_provider_question():
    """A key is not universally required, so "is there a key" is the wrong test."""
    assert not configured(Config(embedding_provider="voyage"))
    assert configured(Config(embedding_provider="voyage", voyage_api_key="pa-x"))
    # A local server has an endpoint and no auth.
    assert configured(Config(embedding_provider="ollama"))
    # A local model has neither.
    assert configured(Config(embedding_provider="local"))
    # The generic backend needs the one thing it cannot default: the URL.
    assert not configured(Config(embedding_provider="openai_compatible"))
    assert configured(Config(embedding_provider="openai_compatible", embedding_api_url="https://x/v1/embeddings"))


def test_a_self_hosted_endpoint_is_called_without_an_auth_header(wire):
    """vLLM and TEI are normally wide open inside a network; sending
    `Authorization: Bearer ` to one is a way to be refused for no reason."""
    seen = wire({"data": [{"index": 0, "embedding": [0.1]}]})
    cfg = Config(embedding_provider="openai_compatible", embedding_api_url="http://tei.internal/v1/embeddings", embedding_model="bge-m3")
    embedder_for(lambda: cfg).embed_documents(["a"])
    assert seen["headers"] == {}


# ── the query / document distinction ─────────────────────────────────────────


def test_voyage_tells_the_api_whether_it_is_a_query(wire):
    """Voyage embeds a query and a document differently, and retrieval is worse
    when a query is sent as a document. Chroma 1.5 says which it wants."""
    seen = wire({"data": [{"index": 0, "embedding": [0.1]}]})
    ef = VoyageEmbeddings(lambda: Settings("voyage", backends.VOYAGE_URL, "pa-x", "voyage-4-lite"))

    ef.embed_documents(["a job description"])
    assert seen["body"]["input_type"] == "document"

    ef.embed_query(["a search"])
    assert seen["body"]["input_type"] == "query"

    # Pre-1.5 chroma calls the object and cannot say; documents are the default.
    ef(["a"])
    assert seen["body"]["input_type"] == "document"


def test_cohere_asks_for_floats_and_names_the_input_type(wire):
    """Cohere's v2 shape: `texts`, a required input_type, and floats that have to
    be requested — then handed back under `embeddings.float`."""
    seen = wire({"embeddings": {"float": [[0.1], [0.2]]}})
    ef = CohereEmbeddings(lambda: Settings("cohere", backends.COHERE_URL, "k", "embed-v4.0"))

    assert ef.embed_documents(["a", "b"]) == [[0.1], [0.2]]
    assert seen["body"] == {
        "model": "embed-v4.0",
        "texts": ["a", "b"],
        "input_type": "search_document",
        "embedding_types": ["float"],
    }

    ef.embed_query(["q"])
    assert seen["body"]["input_type"] == "search_query"


# ── Gemini's batch method ────────────────────────────────────────────────────


def test_gemini_embeds_each_text_separately(wire):
    """`:embedContent` answers a list of texts with one aggregated vector, which
    would quietly collapse a batch of documents into a single point."""
    seen = wire({"embeddings": [{"values": [0.1]}, {"values": [0.2]}]})
    ef = GeminiEmbeddings(lambda: Settings("gemini", backends.GEMINI_BASE, "k", "gemini-embedding-001"))

    assert ef.embed_documents(["a", "b"]) == [[0.1], [0.2]]
    assert seen["url"].endswith("/models/gemini-embedding-001:batchEmbedContents")
    assert seen["headers"] == {"x-goog-api-key": "k"}
    assert len(seen["body"]["requests"]) == 2
    assert seen["body"]["requests"][0]["content"] == {"parts": [{"text": "a"}]}
    assert seen["body"]["requests"][0]["taskType"] == "RETRIEVAL_DOCUMENT"

    ef.embed_query(["q"])
    assert seen["body"]["requests"][0]["taskType"] == "RETRIEVAL_QUERY"


def test_the_gemini_2_family_is_sent_no_task_type(wire):
    """It dropped the parameter and rejects it; the instruction goes in the text."""
    seen = wire({"embeddings": [{"values": [0.1]}]})
    ef = GeminiEmbeddings(lambda: Settings("gemini", backends.GEMINI_BASE, "k", "gemini-embedding-2"))

    ef.embed_query(["q"])
    assert "taskType" not in seen["body"]["requests"][0]


# ── the local backend ────────────────────────────────────────────────────────


def test_the_local_backend_says_which_extra_it_needs():
    """Without the extra installed the failure has to name the fix, because the
    alternative is an ImportError for a package the caller never mentioned."""
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        pass
    else:
        pytest.skip("sentence-transformers is installed, so there is no error to read")

    ef = LocalEmbeddings(lambda: Settings("local"))
    with pytest.raises(RuntimeError, match="local-embeddings"):
        ef.embed_documents(["a"])


def test_local_needs_no_key_and_no_endpoint():
    spec = PROVIDERS["local"]
    assert spec.backend is LocalEmbeddings
    assert not spec.needs_key and not spec.needs_url
