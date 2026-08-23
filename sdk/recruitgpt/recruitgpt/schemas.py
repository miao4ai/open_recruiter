"""The shapes that flow through the pipeline.

Richer than the SDK's `Job`, `Candidate` and `Match` — skill levels, coverage
ratios, a recommendation band — because training needs the detail. They are
mapped down at the `Ranker` boundary rather than pushed up into the SDK, so a
model that does not exist yet cannot widen the product's contract.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Seniority(str, Enum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"
    PRINCIPAL = "principal"


class Difficulty(str, Enum):
    """How a candidate is meant to relate to a job.

    `HARD_NEGATIVE` is the one that matters: superficially strong — long tenure,
    heavy keyword overlap — and wrong for the role. A model that ranks those
    correctly has learned something a keyword scorer cannot.
    """

    STRONG = "strong"
    GOOD = "good"
    BORDERLINE = "borderline"
    WEAK = "weak"
    HARD_NEGATIVE = "hard_negative"


class LabelQuality(str, Enum):
    GOLD = "gold"
    SILVER = "silver"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"


class JobSpec(BaseModel):
    """A job, as the pipeline understands it."""

    job_id: str
    title: str
    level: Seniority = Seniority.MID
    domain: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    minimum_experience_years: int = 0
    description: str = ""
    #: Which generator produced this, so a benchmark can prove it came from
    #: somewhere other than the training data.
    source: str = "synthetic"
    template_id: str = ""


class CandidateSpec(BaseModel):
    """A candidate, with the ground truth that produced them.

    `skills` maps a skill to a 1-5 level. That is the structured truth a real
    resume cannot give you, and the reason candidates are generated rather than
    collected.
    """

    candidate_id: str
    experience_years: int = 0
    skills: dict[str, int] = Field(default_factory=dict)
    domains: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    seniority: Seniority = Seniority.MID
    #: The rendered resume. Generated from the fields above, never the source of them.
    resume: str = ""
    source: str = "synthetic"
    template_id: str = ""

    def profile_text(self) -> str:
        """A compact rendering — listwise ranking cannot afford whole resumes."""
        skills = ", ".join(f"{k} ({v}/5)" for k, v in sorted(self.skills.items()))
        lines = [f"Experience: {self.experience_years} years ({self.seniority.value})"]
        if self.roles:
            lines.append(f"Roles: {', '.join(self.roles)}")
        if self.domains:
            lines.append(f"Domains: {', '.join(self.domains)}")
        if skills:
            lines.append(f"Skills: {skills}")
        return "\n".join(lines)


class Assessment(BaseModel):
    """One candidate judged against one job."""

    candidate_id: str
    match_score: float = 0.0
    required_skill_coverage: float = 0.0
    preferred_skill_coverage: float = 0.0
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    recommendation: str = "weak_match"


class RankingExample(BaseModel):
    """The training unit: a job, a shortlist, and the order they belong in.

    Listwise because comparison is the mechanism — a candidate with ten years of
    general ML looks strong until it is placed beside four years of exactly the
    right thing.
    """

    example_id: str
    job: JobSpec
    candidates: list[CandidateSpec]
    #: Candidate ids, best first. The label.
    ordering: list[str]
    assessments: list[Assessment] = Field(default_factory=list)
    difficulty: dict[str, Difficulty] = Field(default_factory=dict)
    quality: LabelQuality = LabelQuality.SILVER
    #: Everything a grouped split needs to keep this example on one side.
    group_keys: list[str] = Field(default_factory=list)

    def pairs(self) -> list[tuple[str, str]]:
        """Every (better, worse) pair implied by the ordering.

        Pairwise accuracy is measured over these, and preference training in
        phase 5 consumes them directly.
        """
        return [
            (self.ordering[i], self.ordering[j])
            for i in range(len(self.ordering))
            for j in range(i + 1, len(self.ordering))
        ]


__all__ = [
    "Assessment",
    "CandidateSpec",
    "Difficulty",
    "JobSpec",
    "LabelQuality",
    "RankingExample",
    "Seniority",
]
