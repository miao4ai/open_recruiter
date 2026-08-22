"""Domain types shared by every layer of the SDK.

These are deliberately plain: a `Job` is what a recruiter posts, a `Candidate`
is who applies, a `Match` is the judgement connecting them. Storage, ranking,
and the agent all speak in these terms, so a backend can be swapped without
anything else noticing.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CandidateStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    REPLIED = "replied"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    HIRED = "hired"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class Job(BaseModel):
    id: str = Field(default_factory=_new_id)
    title: str = ""
    company: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_years: int | None = None
    location: str = ""
    remote: bool = False
    salary_range: str = ""
    summary: str = ""
    raw_text: str = ""
    created_at: str = Field(default_factory=_now)

    def embed_text(self) -> str:
        """The text a retriever should index for this job."""
        parts = [self.summary or "", self.raw_text or ""]
        if self.required_skills:
            parts.insert(0, "Required skills: " + ", ".join(self.required_skills))
        if self.title:
            parts.insert(0, self.title)
        return "\n\n".join(p for p in parts if p).strip()


class Candidate(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str = ""
    email: str = ""
    phone: str = ""
    current_title: str = ""
    current_company: str = ""
    skills: list[str] = Field(default_factory=list)
    experience_years: int | None = None
    location: str = ""
    resume_summary: str = ""
    raw_resume_text: str = ""
    status: CandidateStatus = CandidateStatus.NEW
    created_at: str = Field(default_factory=_now)

    def embed_text(self) -> str:
        """Summary and skills lead — they carry the most signal per token."""
        parts = []
        if self.resume_summary:
            parts.append(self.resume_summary)
        if self.skills:
            parts.append("Skills: " + ", ".join(self.skills))
        if self.current_title:
            parts.append(f"Current role: {self.current_title}")
        return "\n\n".join(parts).strip()

    def profile_text(self) -> str:
        """A compact rendering for prompts that must not spend a whole resume."""
        lines = [f"Name: {self.name}"]
        for label, value in (
            ("Title", self.current_title),
            ("Company", self.current_company),
            ("Location", self.location),
        ):
            if value:
                lines.append(f"{label}: {value}")
        if self.experience_years is not None:
            lines.append(f"Experience: {self.experience_years} years")
        if self.skills:
            lines.append("Skills: " + ", ".join(self.skills))
        if self.resume_summary:
            lines.append(f"Summary: {self.resume_summary}")
        return "\n".join(lines)


class Match(BaseModel):
    """One candidate judged against one job."""

    candidate_id: str
    job_id: str
    score: float = 0.0
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    reasoning: str = ""
    # Which backend produced this, so mixed results stay explainable.
    ranker: str = ""


class EmailDraft(BaseModel):
    candidate_id: str = ""
    job_id: str = ""
    email_type: str = "outreach"
    subject: str = ""
    body: str = ""


__all__ = [
    "Candidate",
    "CandidateStatus",
    "EmailDraft",
    "Job",
    "Match",
]
