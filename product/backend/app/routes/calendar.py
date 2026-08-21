"""Calendar routes — CRUD for scheduling events."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app import database as db
from app.auth import get_current_user
from app.models import CalendarEvent, CalendarEventCreate, CalendarEventUpdate

router = APIRouter()


@router.get("")
async def list_events(
    month: str | None = Query(None),
    candidate_id: str | None = Query(None),
    job_id: str | None = Query(None),
    _user: dict = Depends(get_current_user),
):
    return db.list_events(month=month, candidate_id=candidate_id, job_id=job_id)


@router.post("")
async def create_event(req: CalendarEventCreate, _user: dict = Depends(get_current_user)):
    event = CalendarEvent(
        title=req.title,
        start_time=req.start_time,
        end_time=req.end_time,
        event_type=req.event_type,
        candidate_id=req.candidate_id,
        candidate_name=req.candidate_name,
        job_id=req.job_id,
        job_title=req.job_title,
        notes=req.notes,
    )
    db.insert_event(event.model_dump())
    return event.model_dump()


@router.get("/{event_id}")
async def get_event(event_id: str, _user: dict = Depends(get_current_user)):
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.put("/{event_id}")
async def update_event(event_id: str, req: CalendarEventUpdate, _user: dict = Depends(get_current_user)):
    existing = db.get_event(event_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")
    updates = req.model_dump(exclude_none=True)
    if updates:
        updates["updated_at"] = datetime.now().isoformat()
        db.update_event(event_id, updates)
    return db.get_event(event_id)


@router.delete("/{event_id}")
async def delete_event(event_id: str, _user: dict = Depends(get_current_user)):
    if not db.delete_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    return {"status": "deleted"}
