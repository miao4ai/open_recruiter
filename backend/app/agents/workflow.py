"""Workflow lifecycle helpers — create and persist workflow records."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from app import database as db


WORKFLOW_STEPS: dict[str, list[str]] = {
    "bulk_outreach": [
        "Find candidates",
        "Draft emails",
        "Review batch",
        "Send emails",
    ],
    "candidate_review": [
        "Load candidate",
        "Run match analysis",
        "Suggest action",
        "Execute action",
    ],
    "interview_scheduling": [
        "Load candidate & job",
        "Propose time slots",
        "Create calendar event",
        "Draft invite email",
    ],
    "pipeline_cleanup": [
        "Find stale candidates",
        "Categorize actions",
        "Execute actions",
    ],
    "job_launch": [
        "Load job details",
        "Find matching candidates",
        "Rank candidates",
        "Draft outreach batch",
        "Send outreach",
    ],
    "job_search": [
        "Search for jobs",
        "Enrich results",
        "Present results",
    ],
    "job_match": [
        "Load context",
        "Evaluate match",
        "Present analysis",
    ],
}


def create_workflow(
    session_id: str,
    user_id: str,
    workflow_type: str,
    params: dict,
) -> dict:
    """Create and persist a new workflow record."""
    steps = WORKFLOW_STEPS.get(workflow_type, [])
    now = datetime.now().isoformat()
    workflow = {
        "id": uuid.uuid4().hex[:8],
        "session_id": session_id,
        "user_id": user_id,
        "workflow_type": workflow_type,
        "status": "running",
        "current_step": 0,
        "total_steps": len(steps),
        "steps_json": json.dumps([{"label": s, "status": "pending"} for s in steps]),
        "context_json": json.dumps(params),
        "checkpoint_data_json": "{}",
        "created_at": now,
        "updated_at": now,
    }
    db.insert_workflow(workflow)
    return workflow
