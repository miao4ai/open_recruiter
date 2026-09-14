"""Open Recruiter — the recruiting engine behind the Open Recruiter app.

Parse resumes and job descriptions, retrieve and rank candidates, draft
outreach, and run an agent that does all of it through tools.

    from openrecruiter import Recruiter

    r = Recruiter(anthropic_api_key="sk-ant-...")
    job = r.add_job(jd_text)
    matches = r.rank(job.id, top_k=10)

No local model is downloaded unless you ask for one. Chat is a hosted provider
and embeddings default to an API call, so the package runs on CPU, on macOS, and
in a container without a GPU; `embedding_provider="local"` opts into a
sentence-transformers model and the `local-embeddings` extra that carries it.

Which embedding backend is yours to choose — Voyage, Cohere, Gemini, any
OpenAI-compatible endpoint, Ollama, a local model, or your own `Embedder`:

    r = Recruiter(embedding_provider="cohere", embedding_api_key="...")
"""

from openrecruiter.agent import Agent, PendingApproval
from openrecruiter.client import Recruiter
from openrecruiter.config import Config
from openrecruiter.context import build_pipeline_context
from openrecruiter.events import (
    ApprovalRequired,
    Event,
    Finished,
    TextDelta,
    ToolCall,
    ToolResult,
)
from openrecruiter.providers.embeddings import PROVIDERS as EMBEDDING_PROVIDERS
from openrecruiter.providers.embeddings import Embedder
from openrecruiter.ranking import APIRanker, EmbeddingRanker, Ranker, TwoStageRanker
from openrecruiter.store import (
    ChromaVectorIndex,
    NullVectorIndex,
    SQLiteStore,
    Store,
    VectorIndex,
)
from openrecruiter.tools import Tool, ToolRegistry, build_seeker_tools, tool
from openrecruiter.types import Candidate, CandidateStatus, EmailDraft, Job, Match

__version__ = "0.1.3"

__all__ = [
    "APIRanker",
    "Agent",
    "ApprovalRequired",
    "build_pipeline_context",
    "Candidate",
    "CandidateStatus",
    "ChromaVectorIndex",
    "Config",
    "EMBEDDING_PROVIDERS",
    "EmailDraft",
    "Embedder",
    "EmbeddingRanker",
    "Event",
    "Finished",
    "Job",
    "Match",
    "NullVectorIndex",
    "PendingApproval",
    "Ranker",
    "Recruiter",
    "SQLiteStore",
    "Store",
    "TextDelta",
    "Tool",
    "ToolCall",
    "ToolRegistry",
    "ToolResult",
    "build_seeker_tools",
    "TwoStageRanker",
    "VectorIndex",
    "__version__",
    "tool",
]
