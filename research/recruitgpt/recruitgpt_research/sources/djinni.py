"""The Djinni recruitment corpus — 142k real job descriptions, MIT licensed.

    lang-uk/recruitment-dataset-job-descriptions-english

Used for distributions, not for text. Synthetic generation seeded from real
co-occurrence produces jobs that hold together; generation seeded from a model's
idea of a job description produces whatever that model finds plausible, which is
the thing the benchmark is supposed to be independent of.

What the corpus does *not* have is a skills field. `Primary Keyword` is one of 45
job categories, so skills have to come out of the description text. Two things
make that tractable without a model:

**Skills are category-discriminative.** "Rust" concentrates in a few categories;
"demonstrated" is spread evenly across all 45. A lift score separates them.

**Requirements are marked.** 57% of postings label a requirements section and
47% label a nice-to-have section, so 29% carry both and give the
required-versus-preferred distinction for free.

Together those yield the number this whole approach rests on: for a given job
family, which skills are *mentioned often and required rarely*. Those are what a
hard negative should have in depth.
"""

from __future__ import annotations

import collections
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

DATASET = "lang-uk/recruitment-dataset-job-descriptions-english"

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]{1,24}")
_REQUIRED_HEADING = re.compile(
    r"(?im)^[\W]*\b(requirements?|must[- ]have|mandatory|qualifications?|we expect)\b"
)
_PREFERRED_HEADING = re.compile(
    r"(?im)\b(nice[- ]to[- ]have|will be a plus|would be a plus|preferred|bonus|"
    r"as a plus|advantage|desirable)\b"
)

#: Terms below this document frequency are too rare for a stable rate.
MIN_DOCUMENT_FREQUENCY = 200
#: How much more concentrated in its top category a term must be than chance.
MIN_CATEGORY_LIFT = 3.0


def load(split: str = "train") -> Any:
    """The corpus. Downloads on first use and caches."""
    from datasets import load_dataset

    return load_dataset(DATASET, split=split)


def terms(text: str) -> set[str]:
    return {t.lower().strip(".-") for t in _TOKEN.findall(text or "")}


def sections(text: str) -> tuple[str, str]:
    """Split a posting into (required, preferred). Empty when unmarked.

    Deliberately crude. The headings are explicit enough that a parser adds
    nothing, and the 29% of postings carrying both markers is already more than
    this project needs.
    """
    start = _REQUIRED_HEADING.search(text or "")
    if start is None:
        return "", ""
    tail = text[start.end() :]
    boundary = _PREFERRED_HEADING.search(tail)
    if boundary is None:
        return tail, ""
    return tail[: boundary.start()], tail[boundary.end() :]


def mine_vocabulary(
    texts: Iterable[str],
    categories: Iterable[str],
    *,
    min_df: int = MIN_DOCUMENT_FREQUENCY,
    min_lift: float = MIN_CATEGORY_LIFT,
) -> dict[str, float]:
    """Terms that behave like skills, scored by how category-specific they are.

    Lift is P(top category | term) / P(top category). A skill concentrates in
    the categories that use it; a filler word does not. No model is called —
    which matters, because this runs over the whole corpus and a model pass
    would not.
    """
    texts, categories = list(texts), list(categories)
    document_frequency: collections.Counter = collections.Counter()
    per_category: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)

    for text, category in zip(texts, categories):
        found = terms(text)
        document_frequency.update(found)
        for term in found:
            per_category[term][category] += 1

    category_size = collections.Counter(categories)
    total = len(texts)

    vocabulary = {}
    for term, count in document_frequency.items():
        if count < min_df or len(term) < 2 or term.isdigit():
            continue
        top_category, top_count = per_category[term].most_common(1)[0]
        lift = (top_count / count) / (category_size[top_category] / total)
        if lift >= min_lift:
            vocabulary[term] = round(lift, 2)
    return vocabulary


@dataclass
class SkillProfile:
    """How a job family talks about a skill, measured over real postings."""

    category: str
    postings: int
    #: skill -> fraction of postings mentioning it anywhere
    mention_rate: dict[str, float] = field(default_factory=dict)
    #: skill -> fraction naming it in the requirements section
    requirement_rate: dict[str, float] = field(default_factory=dict)

    def required(self, threshold: float = 0.6, min_mentions: float = 0.08) -> list[str]:
        """Skills that, when mentioned, are usually being demanded."""
        return self._ranked(lambda ratio: ratio >= threshold, min_mentions, reverse=True)

    def adjacent(self, threshold: float = 0.45, min_mentions: float = 0.08) -> list[str]:
        """Mentioned often, demanded rarely.

        The trap. A candidate deep in these looks relevant to anything that
        counts terms, and is not what the job asked for. Measured rather than
        guessed is the entire point: hand-written adjacency is a record of the
        author's assumptions, and the model would learn those.
        """
        return self._ranked(lambda ratio: ratio <= threshold, min_mentions, reverse=False)

    def _ranked(self, keep, min_mentions: float, reverse: bool) -> list[str]:
        scored = []
        for skill, mentions in self.mention_rate.items():
            if mentions < min_mentions:
                continue
            ratio = self.requirement_rate.get(skill, 0.0) / mentions
            if keep(ratio):
                scored.append((skill, ratio))
        scored.sort(key=lambda pair: pair[1], reverse=reverse)
        return [skill for skill, _ in scored]

    def ratio(self, skill: str) -> float:
        mentions = self.mention_rate.get(skill, 0.0)
        return self.requirement_rate.get(skill, 0.0) / mentions if mentions else 0.0


def skill_profile(
    dataset: Any,
    category: str,
    vocabulary: dict[str, float] | set[str],
) -> SkillProfile:
    """Measure one job family against the mined vocabulary."""
    vocab = set(vocabulary)
    mentions: collections.Counter = collections.Counter()
    requirements: collections.Counter = collections.Counter()
    postings = 0

    for text, cat in zip(dataset["Long Description"], dataset["Primary Keyword"]):
        if cat != category:
            continue
        required_text, _ = sections(text)
        if not required_text:
            continue  # no marked section: nothing to learn about demand
        postings += 1
        mentions.update(terms(text) & vocab)
        requirements.update(terms(required_text) & vocab)

    if postings == 0:
        return SkillProfile(category=category, postings=0)

    return SkillProfile(
        category=category,
        postings=postings,
        mention_rate={s: n / postings for s, n in mentions.items()},
        requirement_rate={s: n / postings for s, n in requirements.items()},
    )


def experience_bands(dataset: Any) -> dict[str, float]:
    """The corpus's own distribution of demanded experience.

    Five bands rather than a number, which is how the postings themselves put
    it — sampling from this beats inventing a range.
    """
    counts = collections.Counter(dataset["Exp Years"])
    total = sum(counts.values())
    return {band: round(n / total, 4) for band, n in counts.most_common()}


def category_mix(dataset: Any) -> dict[str, float]:
    counts = collections.Counter(dataset["Primary Keyword"])
    total = sum(counts.values())
    return {name: round(n / total, 4) for name, n in counts.most_common()}


__all__ = [
    "DATASET",
    "SkillProfile",
    "category_mix",
    "experience_bands",
    "load",
    "mine_vocabulary",
    "sections",
    "skill_profile",
    "terms",
]
