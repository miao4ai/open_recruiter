"""Basic tests for Open Recruiter core modules."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from open_recruiter.config import Config, load_config
from open_recruiter.database import Database
from open_recruiter.schemas import (
    Candidate,
    CandidateStatus,
    Email,
    JobDescription,
    MatchResult,
    PlanStep,
    TaskType,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def test_config_defaults():
    cfg = Config()
    assert cfg.llm_provider == "anthropic"
    assert cfg.llm_model == "claude-sonnet-4-20250514"
    assert cfg.email_backend == "console"


def test_config_openai_default_model():
    cfg = Config(llm_provider="openai")
    assert cfg.llm_model == "gpt-4o"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

def test_candidate_creation():
    c = Candidate(name="Alice", email="alice@example.com", skills=["Python", "React"])
    assert c.name == "Alice"
    assert c.status == CandidateStatus.NEW
    assert len(c.id) == 8


def test_jd_creation():
    jd = JobDescription(title="Senior Engineer", company="Acme")
    assert jd.title == "Senior Engineer"
    assert jd.requirements == []


def test_email_creation():
    e = Email(to="bob@example.com", subject="Hello", body="Hi there")
    assert not e.sent
    assert e.email_type == "outreach"


def test_match_result():
    mr = MatchResult(candidate_id="abc", jd_id="xyz", score=85.0, strengths=["Python"])
    assert mr.score == 85.0


def test_plan_step():
    ps = PlanStep(step=1, task_type=TaskType.PARSE_JD, description="Parse the JD")
    assert ps.depends_on == []


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        database = Database(db_path)
        yield database
        database.close()


def test_save_and_get_candidate(db: Database):
    c = Candidate(name="Alice", email="alice@example.com", skills=["Python"])
    db.save_candidate(c)

    loaded = db.get_candidate(c.id)
    assert loaded is not None
    assert loaded.name == "Alice"
    assert loaded.skills == ["Python"]


def test_list_candidates_by_status(db: Database):
    c1 = Candidate(name="Alice", status=CandidateStatus.NEW)
    c2 = Candidate(name="Bob", status=CandidateStatus.CONTACTED)
    db.save_candidate(c1)
    db.save_candidate(c2)

    new_candidates = db.list_candidates(status=CandidateStatus.NEW)
    assert len(new_candidates) == 1
    assert new_candidates[0].name == "Alice"


def test_update_candidate_status(db: Database):
    c = Candidate(name="Alice")
    db.save_candidate(c)
    db.update_candidate_status(c.id, CandidateStatus.CONTACTED)

    loaded = db.get_candidate(c.id)
    assert loaded is not None
    assert loaded.status == CandidateStatus.CONTACTED


def test_save_and_list_jd(db: Database):
    jd = JobDescription(title="Engineer", company="Acme", requirements=["Python"])
    db.save_jd(jd)

    jds = db.list_jds()
    assert len(jds) == 1
    assert jds[0].title == "Engineer"
    assert jds[0].requirements == ["Python"]


def test_save_and_list_emails(db: Database):
    e = Email(to="bob@example.com", subject="Hi", body="Hello", candidate_id="abc123")
    db.save_email(e)

    emails = db.list_emails(candidate_id="abc123")
    assert len(emails) == 1
    assert emails[0].subject == "Hi"


def test_mark_email_sent(db: Database):
    e = Email(to="bob@example.com", subject="Hi", body="Hello")
    db.save_email(e)
    db.mark_email_sent(e.id)

    emails = db.list_emails()
    assert emails[0].sent is True
    assert emails[0].sent_at is not None
