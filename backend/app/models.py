"""Pydantic models — shared between API routes and agents."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── User / Auth ───────────────────────────────────────────────────────────

class UserRole(str, Enum):
    RECRUITER = "recruiter"
    JOB_SEEKER = "job_seeker"

class UserRegister(BaseModel):
    email: str
    password: str
    name: str = ""
    role: UserRole = UserRole.RECRUITER

class UserLogin(BaseModel):
    email: str
    password: str
    role: UserRole = UserRole.RECRUITER

class User(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    email: str
    name: str = ""
    role: str = "recruiter"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


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
    RECOMMENDATION = "recommendation"


# ── Job ────────────────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    title: str = ""
    company: str = ""
    posted_date: str = ""
    raw_text: str
    contact_name: str = ""
    contact_email: str = ""

class Job(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str = ""
    company: str = ""
    posted_date: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_years: int | None = None
    location: str = ""
    remote: bool = False
    salary_range: str = ""
    summary: str = ""
    raw_text: str = ""
    contact_name: str = ""
    contact_email: str = ""
    candidate_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Candidate ──────────────────────────────────────────────────────────────

class CandidateUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    skills: list[str] | None = None
    experience_years: int | None = None
    location: str | None = None
    status: CandidateStatus | None = None
    notes: str | None = None
    job_id: str | None = None

class JobUpdate(BaseModel):
    title: str | None = None
    company: str | None = None
    posted_date: str | None = None
    raw_text: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None

class MatchRequest(BaseModel):
    job_id: str = ""
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


# ── Job Seeker Profile ────────────────────────────────────────────────────

class JobSeekerProfile(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    user_id: str = ""
    name: str = ""
    email: str = ""
    phone: str = ""
    current_title: str = ""
    current_company: str = ""
    skills: list[str] = Field(default_factory=list)
    experience_years: int | None = None
    location: str = ""
    resume_summary: str = ""
    resume_path: str = ""
    raw_resume_text: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class JobSeekerProfileUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    skills: list[str] | None = None
    experience_years: int | None = None
    location: str | None = None
    resume_summary: str | None = None


# ── Email ──────────────────────────────────────────────────────────────────

class EmailDraftRequest(BaseModel):
    candidate_id: str
    job_id: str
    email_type: EmailType = EmailType.OUTREACH

class EmailComposeRequest(BaseModel):
    to_email: str
    subject: str
    body: str
    email_type: EmailType = EmailType.OUTREACH
    candidate_id: str = ""
    candidate_name: str = ""

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
    attachment_path: str = ""
    message_id: str = ""
    reply_body: str = ""
    replied_at: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Agent ──────────────────────────────────────────────────────────────────

class AgentRequest(BaseModel):
    instruction: str

class AgentEvent(BaseModel):
    type: str  # plan | progress | approval | result | error
    data: dict[str, Any] = Field(default_factory=dict)

class ChatRequest(BaseModel):
    message: str
    session_id: str = ""


# ── Activity Log ──────────────────────────────────────────────────────────

class Activity(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    user_id: str = ""
    activity_type: str = ""          # e.g. "email_drafted", "email_sent"
    description: str = ""
    metadata_json: str = ""          # JSON-encoded extra data
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Slack Audit Log ────────────────────────────────────────────────────────

class SlackAuditLog(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    slack_user_id: str = ""
    slack_channel: str = ""
    slack_thread_ts: str = ""
    source_type: str = ""  # "file" | "text"
    original_filename: str = ""
    candidate_id: str = ""
    processing_status: str = "pending"  # "pending" | "success" | "error"
    error_message: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Calendar Event ─────────────────────────────────────────────────────

class EventType(str, Enum):
    INTERVIEW = "interview"
    FOLLOW_UP = "follow_up"
    OFFER = "offer"
    SCREENING = "screening"
    OTHER = "other"

class CalendarEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str = ""
    start_time: str = ""          # ISO datetime
    end_time: str = ""            # ISO datetime
    event_type: EventType = EventType.OTHER
    candidate_id: str = ""
    candidate_name: str = ""
    job_id: str = ""
    job_title: str = ""
    notes: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class CalendarEventCreate(BaseModel):
    title: str
    start_time: str
    end_time: str = ""
    event_type: EventType = EventType.OTHER
    candidate_id: str = ""
    candidate_name: str = ""
    job_id: str = ""
    job_title: str = ""
    notes: str = ""

class CalendarEventUpdate(BaseModel):
    title: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    event_type: EventType | None = None
    candidate_id: str | None = None
    candidate_name: str | None = None
    job_id: str | None = None
    job_title: str | None = None
    notes: str | None = None


# ── Settings ───────────────────────────────────────────────────────────────

class Settings(BaseModel):
    llm_provider: str = "anthropic"
    llm_model: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    email_backend: str = "console"
    sendgrid_api_key: str = ""
    email_from: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    recruiter_name: str = ""
    recruiter_email: str = ""
    recruiter_company: str = ""
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    slack_bot_token: str = ""
    slack_app_token: str = ""
    slack_signing_secret: str = ""
    slack_intake_channel: str = ""


# ── Automation ────────────────────────────────────────────────────────────


class AutomationRuleType(str, Enum):
    AUTO_MATCH = "auto_match"
    INBOX_SCAN = "inbox_scan"
    AUTO_FOLLOWUP = "auto_followup"
    PIPELINE_CLEANUP = "pipeline_cleanup"


class AutomationTriggerType(str, Enum):
    INTERVAL = "interval"
    CRON = "cron"


class AutomationRuleCreate(BaseModel):
    name: str
    description: str = ""
    rule_type: AutomationRuleType
    trigger_type: AutomationTriggerType = AutomationTriggerType.INTERVAL
    schedule_value: str = ""
    conditions_json: str = "{}"
    actions_json: str = "{}"
    enabled: bool = False


class AutomationRuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_type: AutomationTriggerType | None = None
    schedule_value: str | None = None
    conditions_json: str | None = None
    actions_json: str | None = None
    enabled: bool | None = None


class AutomationRule(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    description: str = ""
    rule_type: AutomationRuleType = AutomationRuleType.AUTO_MATCH
    trigger_type: AutomationTriggerType = AutomationTriggerType.INTERVAL
    schedule_value: str = ""
    conditions_json: str = "{}"
    actions_json: str = "{}"
    enabled: bool = False
    last_run_at: str | None = None
    next_run_at: str | None = None
    run_count: int = 0
    error_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class AutomationLog(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    rule_id: str = ""
    rule_name: str = ""
    status: str = "running"
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    finished_at: str | None = None
    duration_ms: int = 0
    summary: str = ""
    details_json: str = "{}"
    error_message: str = ""
    items_processed: int = 0
    items_affected: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
