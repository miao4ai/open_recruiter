"""Tokenising a chat example, and masking everything the model should not learn.

The mask is the part worth testing. Train on the whole sequence and the model
spends its capacity learning to reproduce job descriptions — the loss falls, the
ranking does not improve, and nothing about the run looks wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Positions with this label contribute nothing to the loss.
IGNORE = -100


def encode(tokenizer: Any, messages: list[dict], max_length: int) -> dict[str, list[int]]:
    """Tokenise a conversation, with only the assistant turn supervised.

    The boundary is found by character offset, not by tokenising the prompt and
    the full text separately and comparing lengths. Those two token sequences
    are *not* prefixes of one another even when the strings are: BPE merges
    across the boundary differently once the next character is known. On Qwen3
    the prompt ends `...assistant\n` while the full text continues
    `...assistant\n<think>`, and the final token differs — so a length-based
    mask is off by one and supervises part of the template.

    Offsets are exact and survive a change of chat format, which a hand-counted
    boundary would not.
    """
    prompt_text = tokenizer.apply_chat_template(
        messages[:-1], tokenize=False, add_generation_prompt=True
    )
    full_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=False
    )

    if not full_text.startswith(prompt_text):
        raise ValueError(
            "The rendered prompt is not a prefix of the rendered conversation under this "
            "chat template, so the assistant turn cannot be located. Training on an unknown "
            "span is worse than failing here."
        )

    encoded = tokenizer(full_text, add_special_tokens=False, return_offsets_mapping=True)
    offsets = encoded.get("offset_mapping")
    if offsets is None:
        raise ValueError(
            "This tokenizer does not return offsets, so the supervised span cannot be "
            "located exactly. Use the fast tokenizer for this model."
        )

    boundary = len(prompt_text)
    input_ids = list(encoded["input_ids"])
    # A token is part of the prompt if it ends at or before the boundary. A token
    # straddling it belongs to the answer — masking it would drop the first
    # character the model has to produce.
    labels = [
        IGNORE if end <= boundary else token
        for token, (_, end) in zip(input_ids, offsets)
    ]

    if all(label == IGNORE for label in labels):
        raise ValueError("Nothing is supervised — the assistant turn rendered empty.")

    # Truncate from the left of the *prompt*, never the target: a clipped answer
    # teaches the model to stop mid-JSON.
    if len(input_ids) > max_length:
        overflow = len(input_ids) - max_length
        supervised_from = next(i for i, label in enumerate(labels) if label != IGNORE)
        if overflow >= supervised_from:
            raise ValueError(
                f"The target alone is {len(input_ids) - supervised_from} tokens, which does "
                f"not fit in max_seq_len={max_length}. Reduce data.max_candidates."
            )
        input_ids = input_ids[overflow:]
        labels = labels[overflow:]

    return {
        "input_ids": input_ids,
        "labels": labels,
        "attention_mask": [1] * len(input_ids),
    }


@dataclass
class Collator:
    """Pad a batch to its longest member."""

    pad_token_id: int

    def __call__(self, features: list[dict]) -> dict:
        import torch

        width = max(len(f["input_ids"]) for f in features)
        batch = {"input_ids": [], "labels": [], "attention_mask": []}
        for f in features:
            gap = width - len(f["input_ids"])
            batch["input_ids"].append(f["input_ids"] + [self.pad_token_id] * gap)
            # Padding is masked out too, or the model learns to emit pad tokens.
            batch["labels"].append(f["labels"] + [IGNORE] * gap)
            batch["attention_mask"].append(f["attention_mask"] + [0] * gap)
        return {k: torch.tensor(v, dtype=torch.long) for k, v in batch.items()}


__all__ = ["Collator", "IGNORE", "encode"]
