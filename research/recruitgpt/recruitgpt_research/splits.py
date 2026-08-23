"""Splitting a synthetic dataset without leaking it.

Random splitting is wrong here. Examples are generated from templates, so two
examples built from the same template are near-duplicates however different
their surface text looks. Split them at random and the test set is measuring
memorisation while reporting generalisation — the classic way synthetic-data
results fail to reproduce.

So the split is by group: every example carrying a given key lands on one side.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from recruitgpt.schemas import RankingExample


@dataclass
class Split:
    train: list[RankingExample]
    validation: list[RankingExample]
    test: list[RankingExample]

    def counts(self) -> dict[str, int]:
        return {
            "train": len(self.train),
            "validation": len(self.validation),
            "test": len(self.test),
        }


def _bucket(key: str, seed: int) -> float:
    """A stable position in [0, 1) for a group key.

    Hashed rather than shuffled so that adding examples later does not move
    existing groups across the split — a frozen test set has to stay frozen.
    """
    digest = hashlib.sha256(f"{seed}:{key}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def grouped_split(
    examples: list[RankingExample],
    *,
    validation_fraction: float = 0.1,
    test_fraction: float = 0.1,
    seed: int = 0,
) -> Split:
    """Split so that no group appears on two sides.

    An example's group is the join of its `group_keys`; anything sharing a key
    with it travels with it. That makes the split coarser than a random one: the
    fractions are targets over *groups*, not examples, so the example counts can
    be far from the requested split. That is a property of the data, and the
    alternative — splitting related examples across sides — would report
    memorisation as generalisation.
    """
    if not examples:
        return Split([], [], [])

    # Union-find over group keys, so transitively related examples stay together.
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for ex in examples:
        keys = ex.group_keys or [ex.example_id]
        for key in keys[1:]:
            union(keys[0], key)

    # Assign whole groups, in a hash order that is stable as data is added.
    #
    # Thresholding each group's hash independently is the obvious approach and
    # it fails here: with a handful of groups, a 10% band is often empty, and an
    # empty validation set is discovered much later than it should be. Walking a
    # sorted order instead guarantees every side gets a group whenever there are
    # enough to go round.
    groups = sorted({find(ex.group_keys[0] if ex.group_keys else ex.example_id) for ex in examples})
    groups.sort(key=lambda g: _bucket(g, seed))

    total = len(groups)
    n_test = max(1, round(total * test_fraction)) if total >= 3 else 0
    n_val = max(1, round(total * validation_fraction)) if total >= 3 else 0
    if n_test + n_val >= total:  # never leave training with nothing
        n_test = n_val = 1 if total >= 3 else 0

    side = {}
    for i, group in enumerate(groups):
        if i < n_test:
            side[group] = "test"
        elif i < n_test + n_val:
            side[group] = "validation"
        else:
            side[group] = "train"

    train, validation, test = [], [], []
    buckets = {"train": train, "validation": validation, "test": test}
    for ex in examples:
        key = find(ex.group_keys[0] if ex.group_keys else ex.example_id)
        buckets[side[key]].append(ex)

    return Split(train=train, validation=validation, test=test)


def leaked_groups(split: Split) -> set[str]:
    """Group keys present on more than one side. Must always be empty."""
    sides = [
        {k for ex in part for k in (ex.group_keys or [ex.example_id])}
        for part in (split.train, split.validation, split.test)
    ]
    leaked: set[str] = set()
    for i, a in enumerate(sides):
        for b in sides[i + 1 :]:
            leaked |= a & b
    return leaked


__all__ = ["Split", "grouped_split", "leaked_groups"]
