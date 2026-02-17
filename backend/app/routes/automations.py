"""Automation routes — CRUD for rules, logs, manual trigger, scheduler status."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app import database as db
from app.auth import get_current_user
from app.models import AutomationRule, AutomationRuleCreate, AutomationRuleUpdate

router = APIRouter()


@router.get("/rules")
async def list_rules(_user: dict = Depends(get_current_user)):
    return db.list_automation_rules()


@router.post("/rules")
async def create_rule(
    req: AutomationRuleCreate, _user: dict = Depends(get_current_user)
):
    rule = AutomationRule(
        name=req.name,
        description=req.description,
        rule_type=req.rule_type,
        trigger_type=req.trigger_type,
        schedule_value=req.schedule_value,
        conditions_json=req.conditions_json,
        actions_json=req.actions_json,
        enabled=req.enabled,
    )
    db.insert_automation_rule(rule.model_dump())

    if req.enabled:
        from app.scheduler import schedule_rule

        schedule_rule(rule.id)

    return rule.model_dump()


@router.get("/rules/{rule_id}")
async def get_rule(rule_id: str, _user: dict = Depends(get_current_user)):
    rule = db.get_automation_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.patch("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    req: AutomationRuleUpdate,
    _user: dict = Depends(get_current_user),
):
    rule = db.get_automation_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    updates = {k: v for k, v in req.model_dump(exclude_none=True).items()}
    if updates:
        updates["updated_at"] = datetime.now().isoformat()
        # Convert enum to value if present
        if "trigger_type" in updates and hasattr(updates["trigger_type"], "value"):
            updates["trigger_type"] = updates["trigger_type"].value
        db.update_automation_rule(rule_id, updates)

    # Reschedule if enabled/schedule changed
    from app.scheduler import schedule_rule, unschedule_rule

    updated_rule = db.get_automation_rule(rule_id)
    if updated_rule and updated_rule["enabled"]:
        schedule_rule(rule_id)
    else:
        unschedule_rule(rule_id)

    return updated_rule


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, _user: dict = Depends(get_current_user)):
    rule = db.get_automation_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    from app.scheduler import unschedule_rule

    unschedule_rule(rule_id)
    db.delete_automation_rule(rule_id)
    return {"status": "deleted"}


@router.post("/rules/{rule_id}/toggle")
async def toggle_rule(rule_id: str, _user: dict = Depends(get_current_user)):
    rule = db.get_automation_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    new_enabled = not rule["enabled"]
    db.update_automation_rule(rule_id, {
        "enabled": new_enabled,
        "updated_at": datetime.now().isoformat(),
    })

    from app.scheduler import schedule_rule, unschedule_rule

    if new_enabled:
        schedule_rule(rule_id)
    else:
        unschedule_rule(rule_id)

    return {"enabled": new_enabled}


@router.post("/rules/{rule_id}/run")
async def run_rule_now(rule_id: str, _user: dict = Depends(get_current_user)):
    """Manually trigger a rule immediately."""
    rule = db.get_automation_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    from app.scheduler import run_rule_now as do_run

    result = do_run(rule_id)
    return result


@router.get("/logs")
async def list_logs(
    rule_id: str | None = None,
    limit: int = 100,
    _user: dict = Depends(get_current_user),
):
    return db.list_automation_logs(rule_id=rule_id, limit=limit)


@router.get("/status")
async def scheduler_status(_user: dict = Depends(get_current_user)):
    """Return scheduler health and summary of active jobs."""
    from app.scheduler import get_scheduler

    scheduler = get_scheduler()
    jobs = scheduler.get_jobs() if scheduler.running else []
    return {
        "running": scheduler.running,
        "active_jobs": len(jobs),
        "jobs": [
            {"id": j.id, "name": j.name, "next_run": str(j.next_run_time)}
            for j in jobs
        ],
    }
