"""RecruitGPT — a recruiting-specialised ranking model, packaged as a `Ranker`.

    from openrecruiter import EmbeddingRanker, TwoStageRanker
    from recruitgpt import RecruitGPTRanker

    r.ranker = TwoStageRanker(EmbeddingRanker(r.index), RecruitGPTRanker(), shortlist=50)

This package holds the pieces that training and serving must agree on — the
schemas and the exact prompt format — so a model cannot be trained against one
rendering and served another. The training pipeline is a separate distribution
(`recruitgpt-research`) that depends on this one.

Model weights are never bundled. `RecruitGPTRanker` loads an adapter from a
model registry the first time it is asked to rank, so importing this package
downloads nothing.
"""

from recruitgpt.format import (
    LABELS,
    SYSTEM,
    ListwisePrompt,
    build_prompt,
    parse_ranking,
    render_target,
)
from recruitgpt.schemas import (
    Assessment,
    CandidateSpec,
    Difficulty,
    JobSpec,
    LabelQuality,
    RankingExample,
    Seniority,
)

__version__ = "0.1.0"

__all__ = [
    "Assessment",
    "CandidateSpec",
    "Difficulty",
    "JobSpec",
    "LABELS",
    "LabelQuality",
    "ListwisePrompt",
    "RankingExample",
    "SYSTEM",
    "Seniority",
    "build_prompt",
    "parse_ranking",
    "render_target",
]
