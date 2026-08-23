"""Open Recruiter — the recruiting engine behind the Open Recruiter app.

Parse resumes and job descriptions, retrieve and rank candidates, draft
outreach, and run an agent that does all of it through tools.

    from openrecruiter import Recruiter

    r = Recruiter(anthropic_api_key="sk-ant-...")
    job = r.add_job(jd_text)
    matches = r.rank(job.id, top_k=10)

No local model is downloaded, at import or at runtime. Embeddings are an API
call and chat is a hosted provider, so the package runs on CPU, on macOS, and in
a container without a GPU.
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
from openrecruiter.ranking import APIRanker, EmbeddingRanker, Ranker, TwoStageRanker
from openrecruiter.store import (
    ChromaVectorIndex,
    NullVectorIndex,
    SQLiteStore,
    Store,
    VectorIndex,
)
from openrecruiter.tools import Tool, ToolRegistry, tool
from openrecruiter.types import Candidate, CandidateStatus, EmailDraft, Job, Match

__version__ = "0.1.1"

__all__ = [
    "APIRanker",
    "Agent",
    "ApprovalRequired",
    "build_pipeline_context",
    "Candidate",
    "CandidateStatus",
    "ChromaVectorIndex",
    "Config",
    "EmailDraft",
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
    "TwoStageRanker",
    "VectorIndex",
    "__version__",
    "tool",
]
