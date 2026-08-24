"""Corpus profiling, against fixtures rather than the real 142k download.

The measurements this module produces decide what a hard negative looks like,
so what is tested is the *logic* — lift separating skills from filler, the
section split, the mention-versus-requirement gap — on data small enough to read.
"""

from __future__ import annotations

import pytest

from recruitgpt_research.sources import djinni


class FakeDataset:
    """The two columns the profiler reads."""

    def __init__(self, rows: list[tuple[str, str, str]]) -> None:
        # (description, category, exp_band)
        self.rows = rows

    def __getitem__(self, column: str) -> list[str]:
        index = {"Long Description": 0, "Primary Keyword": 1, "Exp Years": 2}[column]
        return [row[index] for row in self.rows]


def posting(category: str, intro: str, required: str, preferred: str = "") -> tuple:
    text = f"{intro}\n\nRequirements\n{required}"
    if preferred:
        text += f"\n\nNice to have\n{preferred}"
    return (text, category, "3y")


# ── sections ─────────────────────────────────────────────────────────────


def test_sections_split_on_the_headings():
    required, preferred = djinni.sections(
        "We are a great company.\n\nRequirements\nStrong C++\n\nNice to have\nQt"
    )
    assert "C++" in required
    assert "great company" not in required, "the intro is not a requirement"
    assert "Qt" in preferred
    assert "Qt" not in required


def test_an_unmarked_posting_yields_nothing():
    assert djinni.sections("We want someone great who knows C++.") == ("", "")


def test_a_posting_with_no_nice_to_have_still_gives_requirements():
    required, preferred = djinni.sections("Intro\n\nMust have\nCUDA and NCCL")
    assert "CUDA" in required
    assert preferred == ""


# ── vocabulary ───────────────────────────────────────────────────────────


def test_lift_keeps_skills_and_drops_filler():
    """A skill concentrates in the categories that use it; filler does not."""
    rows = []
    for _ in range(300):
        rows.append(posting("C++", "We are hiring", "Strong C++ and demonstrated ownership"))
        rows.append(posting("Python", "We are hiring", "Strong Django and demonstrated ownership"))

    vocab = djinni.mine_vocabulary(
        FakeDataset(rows)["Long Description"],
        FakeDataset(rows)["Primary Keyword"],
        min_df=100,
        min_lift=1.5,
    )

    assert "c++" in vocab and "django" in vocab
    assert "demonstrated" not in vocab, "appears equally in both categories"
    assert "hiring" not in vocab


def test_rare_terms_are_excluded():
    rows = [posting("C++", "x", "Strong C++")] * 300 + [posting("C++", "x", "Also Fortran")]
    vocab = djinni.mine_vocabulary(
        FakeDataset(rows)["Long Description"], FakeDataset(rows)["Primary Keyword"], min_df=50
    )
    assert "fortran" not in vocab, "one mention is not a rate"


# ── the gap that hard negatives are built from ───────────────────────────


@pytest.fixture
def corpus():
    """A family where CUDA is demanded and 'cloud' is merely mentioned."""
    rows = []
    for _ in range(200):
        rows.append(posting("C++", "We run workloads in the cloud.", "Strong CUDA"))
        rows.append(posting("Python", "We build services.", "Strong Django"))
    return FakeDataset(rows)


def test_a_skill_that_is_mentioned_and_not_demanded_is_adjacent(corpus):
    vocab = djinni.mine_vocabulary(
        corpus["Long Description"], corpus["Primary Keyword"], min_df=50, min_lift=1.5
    )
    profile = djinni.skill_profile(corpus, "C++", vocab)

    assert profile.postings == 200
    assert profile.ratio("cuda") == pytest.approx(1.0), "always in the requirements section"
    assert profile.ratio("cloud") == pytest.approx(0.0), "always in the intro"

    assert "cuda" in profile.required()
    assert "cloud" in profile.adjacent()
    assert "cuda" not in profile.adjacent()


def test_the_profile_is_empty_when_nothing_is_marked():
    rows = [("We want CUDA experience.", "C++", "3y")] * 100
    profile = djinni.skill_profile(FakeDataset(rows), "C++", {"cuda"})
    assert profile.postings == 0
    assert profile.required() == []


def test_thresholds_move_the_boundary(corpus):
    vocab = djinni.mine_vocabulary(
        corpus["Long Description"], corpus["Primary Keyword"], min_df=50, min_lift=1.5
    )
    profile = djinni.skill_profile(corpus, "C++", vocab)

    assert profile.adjacent(threshold=0.99) >= profile.adjacent(threshold=0.1)


# ── distributions ────────────────────────────────────────────────────────


def test_experience_bands_are_a_distribution():
    rows = [posting("C++", "x", "y")] * 3 + [("Requirements\nz", "C++", "5y")]
    bands = djinni.experience_bands(FakeDataset(rows))

    assert sum(bands.values()) == pytest.approx(1.0)
    assert bands["3y"] == pytest.approx(0.75)


def test_category_mix_is_a_distribution():
    rows = [posting("C++", "x", "y")] * 3 + [posting("Python", "x", "y")]
    mix = djinni.category_mix(FakeDataset(rows))

    assert sum(mix.values()) == pytest.approx(1.0)
    assert mix["C++"] == pytest.approx(0.75)
