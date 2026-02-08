"""Pydantic models — shared between API routes and agents."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────

class CandidateStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    REPLIED = "replied"
    SCREENING = "screening"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEWED = "interviewed"
    OFFER_SENT = "offer_sent"
    HIRED = "hired"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class EmailType(str, Enum):
    OUTREACH = "outreach"
    FOLLOWUP = "followup"
    REJECTION = "rejection"
    INTERVIEW_INVITE = "interview_invite"


# ── Job ────────────────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    raw_text: str

class Job(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
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
    candidate_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Candidate ──────────────────────────────────────────────────────────────

class CandidateUpdate(BaseModel):
    status: CandidateStatus | None = None
    notes: str | None = None

class MatchRequest(BaseModel):
    job_id: str
    candidate_ids: list[str]

class Candidate(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    email: str = ""
    phone: str = ""
    current_title: str = ""
    current_company: str = ""
    skills: list[str] = Field(default_factory=list)
    experience_years: int | None = None
    location: str = ""
    resume_path: str = ""
    resume_summary: str = ""
    status: CandidateStatus = CandidateStatus.NEW
    match_score: float = 0.0
    match_reasoning: str = ""
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    notes: str = ""
    job_id: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Email ──────────────────────────────────────────────────────────────────

class EmailDraftRequest(BaseModel):
    candidate_id: str
    job_id: str
    email_type: EmailType = EmailType.OUTREACH

class Email(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    candidate_id: str = ""
    candidate_name: str = ""
    to_email: str = ""
    subject: str = ""
    body: str = ""
    email_type: EmailType = EmailType.OUTREACH
    approved: bool = False
    sent: bool = False
    sent_at: str | None = None
    reply_received: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Agent ──────────────────────────────────────────────────────────────────

class AgentRequest(BaseModel):
    instruction: str

class AgentEvent(BaseModel):
    type: str  # plan | progress | approval | result | error
    data: dict[str, Any] = Field(default_factory=dict)


# ── Settings ───────────────────────────────────────────────────────────────

class Settings(BaseModel):
    llm_provider: str = "anthropic"
    llm_model: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    email_backend: str = "console"
    sendgrid_api_key: str = ""
    email_from: str = ""
    recruiter_name: str = ""
    recruiter_email: str = ""
    recruiter_company: str = ""
