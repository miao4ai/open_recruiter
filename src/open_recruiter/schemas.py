"""Data models for the recruitment pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CandidateStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    REPLIED = "replied"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class TaskType(str, Enum):
    PARSE_JD = "parse_jd"
    PARSE_RESUME = "parse_resume"
    MATCH = "match"
    DRAFT_EMAIL = "draft_email"
    SEND_EMAIL = "send_email"
    SCHEDULE_INTERVIEW = "schedule_interview"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------

class JobDescription(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str = ""
    company: str = ""
    raw_text: str = ""
    requirements: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    summary: str = ""
    created_at: datetime = Field(default_factory=datetime.now)


class Candidate(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    email: str = ""
    phone: str = ""
    resume_text: str = ""
    skills: list[str] = Field(default_factory=list)
    experience_years: int = 0
    summary: str = ""
    status: CandidateStatus = CandidateStatus.NEW
    match_score: float = 0.0
    match_reasoning: str = ""
    created_at: datetime = Field(default_factory=datetime.now)


class Email(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    to: str = ""
    subject: str = ""
    body: str = ""
    email_type: str = "outreach"  # outreach / followup / rejection / custom
    candidate_id: str = ""
    sent: bool = False
    sent_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class Task(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    task_type: TaskType
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    created_at: datetime = Field(default_factory=datetime.now)


class MatchResult(BaseModel):
    candidate_id: str
    jd_id: str
    score: float = 0.0  # 0-100
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    reasoning: str = ""


class PlanStep(BaseModel):
    step: int
    task_type: TaskType
    description: str
    depends_on: list[int] = Field(default_factory=list)
