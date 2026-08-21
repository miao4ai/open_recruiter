"""Background scheduler — APScheduler-based automation engine."""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app import database as db

log = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 60,
            },
        )
    return _scheduler


def init_scheduler() -> None:
    """Start the scheduler and load enabled rules from DB."""
    scheduler = get_scheduler()
    if scheduler.running:
        return

    scheduler.start()
    log.info("Background scheduler started.")

    # Seed default rules on first run
    _seed_default_rules()

    # Load and schedule all enabled rules
    rules = db.list_automation_rules(enabled_only=True)
    for rule in rules:
        _schedule_rule(rule)
    log.info("Loaded %d enabled automation rules.", len(rules))


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("Background scheduler stopped.")
    _scheduler = None


def schedule_rule(rule_id: str) -> bool:
    """Schedule (or reschedule) a rule by ID."""
    rule = db.get_automation_rule(rule_id)
    if not rule:
        return False
    return _schedule_rule(rule)


def unschedule_rule(rule_id: str) -> None:
    """Remove a rule's job from the scheduler."""
    scheduler = get_scheduler()
    job_id = f"automation_{rule_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        log.info("Unscheduled rule %s", rule_id)


def _schedule_rule(rule: dict) -> bool:
    """Internal: add or replace a job for the given rule dict."""
    scheduler = get_scheduler()
    job_id = f"automation_{rule['id']}"

    # Remove existing job if any
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    if not rule.get("enabled"):
        return False

    trigger = _build_trigger(rule)
    if not trigger:
        log.warning("Could not build trigger for rule %s", rule["id"])
        return False

    scheduler.add_job(
        _run_task_wrapper,
        trigger=trigger,
        id=job_id,
        args=[rule["id"]],
        name=rule.get("name", rule["id"]),
    )
    log.info("Scheduled rule '%s' (%s)", rule["name"], rule["id"])
    return True


def _build_trigger(rule: dict):
    """Build an APScheduler trigger from the rule's trigger_type + schedule_value."""
    trigger_type = rule.get("trigger_type", "interval")
    try:
        schedule = json.loads(rule.get("schedule_value", "{}") or "{}")
    except json.JSONDecodeError:
        schedule = {}

    if trigger_type == "interval":
        return IntervalTrigger(
            weeks=schedule.get("weeks", 0),
            days=schedule.get("days", 0),
            hours=schedule.get("hours", 0),
            minutes=schedule.get("minutes", 30),
            seconds=schedule.get("seconds", 0),
        )
    elif trigger_type == "cron":
        return CronTrigger(
            year=schedule.get("year"),
            month=schedule.get("month"),
            day=schedule.get("day"),
            week=schedule.get("week"),
            day_of_week=schedule.get("day_of_week"),
            hour=schedule.get("hour", 9),
            minute=schedule.get("minute", 0),
        )
    return None


def _run_task_wrapper(rule_id: str) -> None:
    """Wrapper that handles logging, error handling, and stats for any task."""
    rule = db.get_automation_rule(rule_id)
    if not rule or not rule.get("enabled"):
        return

    log_id = uuid.uuid4().hex[:8]
    now = datetime.now().isoformat()
    start_time = time.monotonic()

    db.insert_automation_log({
        "id": log_id,
        "rule_id": rule_id,
        "rule_name": rule.get("name", ""),
        "status": "running",
        "started_at": now,
        "created_at": now,
    })

    try:
        result = _dispatch_task(rule)

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        finished_at = datetime.now().isoformat()

        db.update_automation_log(log_id, {
            "status": "success",
            "finished_at": finished_at,
            "duration_ms": elapsed_ms,
            "summary": result.get("summary", ""),
            "details_json": json.dumps(result.get("details", {})),
            "items_processed": result.get("items_processed", 0),
            "items_affected": result.get("items_affected", 0),
        })

        db.update_automation_rule(rule_id, {
            "last_run_at": finished_at,
            "run_count": rule.get("run_count", 0) + 1,
            "updated_at": finished_at,
        })

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        finished_at = datetime.now().isoformat()
        log.error(
            "Automation rule '%s' failed: %s",
            rule.get("name", rule_id),
            exc,
            exc_info=True,
        )

        db.update_automation_log(log_id, {
            "status": "error",
            "finished_at": finished_at,
            "duration_ms": elapsed_ms,
            "error_message": str(exc),
        })

        db.update_automation_rule(rule_id, {
            "last_run_at": finished_at,
            "run_count": rule.get("run_count", 0) + 1,
            "error_count": rule.get("error_count", 0) + 1,
            "updated_at": finished_at,
        })


def _dispatch_task(rule: dict) -> dict:
    """Route to the correct task handler based on rule_type."""
    from app.automation_tasks import (
        run_auto_followup,
        run_auto_match,
        run_inbox_scan,
        run_pipeline_cleanup,
    )

    rule_type = rule.get("rule_type", "")
    conditions = json.loads(rule.get("conditions_json", "{}") or "{}")
    actions = json.loads(rule.get("actions_json", "{}") or "{}")

    runners = {
        "auto_match": run_auto_match,
        "inbox_scan": run_inbox_scan,
        "auto_followup": run_auto_followup,
        "pipeline_cleanup": run_pipeline_cleanup,
    }

    runner = runners.get(rule_type)
    if not runner:
        return {
            "summary": f"Unknown rule type: {rule_type}",
            "details": {},
            "items_processed": 0,
            "items_affected": 0,
        }

    return runner(conditions=conditions, actions=actions)


def run_rule_now(rule_id: str) -> dict:
    """Manually trigger a rule immediately (for the 'Run Now' button)."""
    rule = db.get_automation_rule(rule_id)
    if not rule:
        return {"error": "Rule not found"}
    _run_task_wrapper(rule_id)
    return {"status": "ok"}


def _seed_default_rules() -> None:
    """Create default automation rules if none exist."""
    existing = db.list_automation_rules()
    if existing:
        return

    now = datetime.now().isoformat()
    defaults = [
        {
            "name": "Auto-Match New Candidates",
            "description": "Automatically match new candidates against open jobs.",
            "rule_type": "auto_match",
            "trigger_type": "interval",
            "schedule_value": json.dumps({"minutes": 30}),
            "conditions_json": json.dumps({"min_score_threshold": 0.3}),
            "actions_json": json.dumps({"update_status": False}),
        },
        {
            "name": "Inbox Scanner",
            "description": "Check IMAP inbox for candidate replies every 15 minutes.",
            "rule_type": "inbox_scan",
            "trigger_type": "interval",
            "schedule_value": json.dumps({"minutes": 15}),
            "conditions_json": "{}",
            "actions_json": json.dumps({"update_candidate_status": True}),
        },
        {
            "name": "Auto Follow-Up",
            "description": "Draft follow-up emails for candidates who haven't replied in 3 days.",
            "rule_type": "auto_followup",
            "trigger_type": "cron",
            "schedule_value": json.dumps({"hour": 9, "minute": 0}),
            "conditions_json": json.dumps({"days_since_contact": 3, "max_followups": 2}),
            "actions_json": json.dumps({"auto_send": False}),
        },
        {
            "name": "Pipeline Cleanup",
            "description": "Find stale candidates and suggest cleanup actions weekly.",
            "rule_type": "pipeline_cleanup",
            "trigger_type": "cron",
            "schedule_value": json.dumps({"day_of_week": "mon", "hour": 8, "minute": 0}),
            "conditions_json": json.dumps({
                "days_stale": 7,
                "target_statuses": ["contacted"],
            }),
            "actions_json": json.dumps({
                "reject_after_days": 14,
                "archive_after_days": 21,
                "dry_run": True,
            }),
        },
    ]

    for d in defaults:
        d["id"] = uuid.uuid4().hex[:8]
        d["enabled"] = False
        d["created_at"] = now
        d["updated_at"] = now
        db.insert_automation_rule(d)

    log.info("Seeded %d default automation rules.", len(defaults))
