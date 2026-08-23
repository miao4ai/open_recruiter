"""RankingExample -> chat messages. No tokenizer, no torch."""

from __future__ import annotations

import random
from dataclasses import dataclass

from recruitgpt.format import ListwisePrompt, build_prompt, render_target
from recruitgpt.schemas import LabelQuality, RankingExample

_QUALITY_ORDER = {
    LabelQuality.REJECTED: 0,
    LabelQuality.AMBIGUOUS: 1,
    LabelQuality.SILVER: 2,
    LabelQuality.GOLD: 3,
}


@dataclass
class ChatExample:
    example_id: str
    messages: list[dict]
    prompt: ListwisePrompt

    @property
    def target(self) -> str:
        return self.messages[-1]["content"]


def to_chat(
    example: RankingExample,
    *,
    shuffle_candidates: bool = True,
    seed: int = 0,
    max_candidates: int | None = None,
) -> ChatExample:
    """Render one example as a system/user/assistant turn.

    Candidates are shuffled before rendering. Without that, the generator's own
    ordering leaks into the prompt layout and the model can learn "the first one
    listed is best" — which scores well and has learned nothing.
    """
    ids = [c.candidate_id for c in example.candidates]
    if max_candidates is not None and len(ids) > max_candidates:
        # Keep the label's top candidates rather than a random slice, so the
        # example still has something to get right.
        keep = set(example.ordering[:max_candidates])
        ids = [cid for cid in ids if cid in keep]
    if shuffle_candidates:
        random.Random(f"{seed}:{example.example_id}").shuffle(ids)

    trimmed = example
    if len(ids) != len(example.candidates):
        subset = set(ids)
        trimmed = example.model_copy(
            update={
                "candidates": [c for c in example.candidates if c.candidate_id in subset],
                "ordering": [cid for cid in example.ordering if cid in subset],
                "assessments": [a for a in example.assessments if a.candidate_id in subset],
            }
        )

    prompt = build_prompt(trimmed, order=ids)
    return ChatExample(
        example_id=example.example_id,
        messages=[
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
            {"role": "assistant", "content": render_target(trimmed, prompt)},
        ],
        prompt=prompt,
    )


def keep_quality(examples: list[RankingExample], minimum: str) -> list[RankingExample]:
    """Drop examples whose label was not trustworthy enough to train on."""
    floor = _QUALITY_ORDER[LabelQuality(minimum)]
    return [ex for ex in examples if _QUALITY_ORDER[ex.quality] >= floor]


__all__ = ["ChatExample", "keep_quality", "to_chat"]
