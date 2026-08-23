"""Dataset construction and serialisation. Imports no deep-learning stack."""

from recruitgpt.format import (
    ListwisePrompt,
    build_prompt,
    parse_ranking,
    render_target,
)

__all__ = ["ListwisePrompt", "build_prompt", "parse_ranking", "render_target"]
