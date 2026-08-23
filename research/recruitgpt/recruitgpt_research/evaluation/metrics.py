"""Ranking metrics.

Pairwise accuracy is the headline. It answers the question the project exists
for — given two candidates, does the model put the right one first — and unlike
a mean score it cannot be inflated by getting the easy pairs right, because the
hard-negative pairs are counted individually.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from recruitgpt.schemas import Difficulty, RankingExample


@dataclass
class RankingMetrics:
    pairwise_accuracy: float = 0.0
    #: The same, restricted to pairs involving a hard negative. This is the
    #: number that matters: overall accuracy stays high while the model fails
    #: precisely on the cases the product exists to get right.
    hard_pairwise_accuracy: float = 0.0
    ndcg_at_3: float = 0.0
    ndcg_at_5: float = 0.0
    mrr: float = 0.0
    recall_at_3: float = 0.0
    #: Fraction of examples the model produced a usable ranking for at all.
    parse_rate: float = 0.0
    examples: int = 0

    def to_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def pairwise_accuracy(truth: list[str], predicted: list[str]) -> tuple[int, int]:
    """(correct, total) over every pair the truth orders.

    A pair the prediction omits counts as wrong rather than being skipped — a
    model that ranks two candidates and ignores the rest has not done the task.
    """
    position = {cid: i for i, cid in enumerate(predicted)}
    correct = total = 0
    for i in range(len(truth)):
        for j in range(i + 1, len(truth)):
            total += 1
            better, worse = truth[i], truth[j]
            if better in position and worse in position and position[better] < position[worse]:
                correct += 1
    return correct, total


def ndcg_at_k(truth: list[str], predicted: list[str], k: int) -> float:
    """Graded relevance from the true ordering: first place is worth the most."""
    if not truth:
        return 0.0
    gain = {cid: len(truth) - i for i, cid in enumerate(truth)}
    dcg = sum(
        gain.get(cid, 0) / math.log2(rank + 2) for rank, cid in enumerate(predicted[:k])
    )
    ideal = sum(gain[cid] / math.log2(rank + 2) for rank, cid in enumerate(truth[:k]))
    return dcg / ideal if ideal else 0.0


def mean_reciprocal_rank(truth: list[str], predicted: list[str]) -> float:
    """How far down the prediction the true best candidate landed."""
    if not truth:
        return 0.0
    try:
        return 1.0 / (predicted.index(truth[0]) + 1)
    except ValueError:
        return 0.0


def recall_at_k(truth: list[str], predicted: list[str], k: int) -> float:
    """Of the true top-k, how many the prediction also put in its top-k."""
    if not truth:
        return 0.0
    wanted = set(truth[:k])
    return len(wanted & set(predicted[:k])) / len(wanted)


def score_predictions(
    examples: list[RankingExample],
    predictions: dict[str, list[str]],
) -> RankingMetrics:
    """Aggregate over a benchmark run.

    `predictions` maps example id to the predicted ordering of candidate ids.
    A missing or empty prediction is scored, not dropped: refusing to answer is
    a failure mode, and quietly excluding it would flatter the model.
    """
    if not examples:
        return RankingMetrics()

    correct = total = hard_correct = hard_total = 0
    ndcg3 = ndcg5 = mrr = rec3 = parsed = 0.0

    for ex in examples:
        predicted = predictions.get(ex.example_id) or []
        parsed += 1.0 if predicted else 0.0

        c, t = pairwise_accuracy(ex.ordering, predicted)
        correct += c
        total += t

        position = {cid: i for i, cid in enumerate(predicted)}
        for better, worse in ex.pairs():
            if Difficulty.HARD_NEGATIVE not in (
                ex.difficulty.get(better),
                ex.difficulty.get(worse),
            ):
                continue
            hard_total += 1
            if (
                better in position
                and worse in position
                and position[better] < position[worse]
            ):
                hard_correct += 1

        ndcg3 += ndcg_at_k(ex.ordering, predicted, 3)
        ndcg5 += ndcg_at_k(ex.ordering, predicted, 5)
        mrr += mean_reciprocal_rank(ex.ordering, predicted)
        rec3 += recall_at_k(ex.ordering, predicted, 3)

    n = len(examples)
    return RankingMetrics(
        pairwise_accuracy=correct / total if total else 0.0,
        hard_pairwise_accuracy=hard_correct / hard_total if hard_total else 0.0,
        ndcg_at_3=ndcg3 / n,
        ndcg_at_5=ndcg5 / n,
        mrr=mrr / n,
        recall_at_3=rec3 / n,
        parse_rate=parsed / n,
        examples=n,
    )


__all__ = [
    "RankingMetrics",
    "mean_reciprocal_rank",
    "ndcg_at_k",
    "pairwise_accuracy",
    "recall_at_k",
    "score_predictions",
]
