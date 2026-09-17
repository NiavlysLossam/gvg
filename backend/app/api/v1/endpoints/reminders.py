import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.api.deps import check_event_ownership, get_current_user
from app.core.database import get_db
from app.models.event import Event
from app.models.user import User
from app.schemas.reminder import (
    ReminderStatusResponse,
    ReminderTriggerAction,
    ReminderTriggerResponse,
    SystemRemindersRunResponse,
)
from app.services import reminder_service

router = APIRouter()
system_router = APIRouter()


def get_event_by_id_or_slug(
    db: Session, id_or_slug: str, current_user: Optional[User] = None
) -> Event:
    """Retrieve an event by UUID or slug, raising 404 if not found and verifying ownership."""
    event: Optional[Event] = None
    try:
        val_uuid = uuid.UUID(id_or_slug)
        event = db.query(Event).filter(Event.id == val_uuid).first()
    except ValueError:
        event = db.query(Event).filter(Event.slug == id_or_slug).first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable",
        )
    if current_user is not None:
        check_event_ownership(event, current_user)
    return event


@router.get(
    "/{id_or_slug}/reminders/status",
    response_model=ReminderStatusResponse,
    summary="Get reminder schedule status and delivery counts for an event",
)
def get_reminders_status(
    id_or_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderStatusResponse:
    """
    Retrieve current days remaining before the event and delivery statistics
    for J-7 and J-2 automatic reminders.
    """
    event = get_event_by_id_or_slug(db, id_or_slug, current_user=current_user)
    try:
        return reminder_service.get_event_reminder_status(str(event.id), db=db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{id_or_slug}/reminders/trigger",
    response_model=ReminderTriggerResponse,
    summary="Trigger reminder emails for an event on demand",
)
def trigger_event_reminders(
    id_or_slug: str,
    background_tasks: BackgroundTasks,
    payload: Optional[ReminderTriggerAction] = None,
    background: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderTriggerResponse:
    """
    Trigger J-7 or J-2 reminder emails on demand for all confirmed exhibitors of an event.
    - If reminder_type is omitted, sends eligible reminders based on current event window.
    - Idempotent: orders that already received the reminder are skipped unless force=true.
    - If background=true, executes via FastAPI BackgroundTasks.
    """
    event = get_event_by_id_or_slug(db, id_or_slug, current_user=current_user)

    reminder_type = payload.reminder_type if payload else None
    force = payload.force if payload else False

    if background:
        background_tasks.add_task(
            reminder_service.process_event_reminders,
            event_id=event.id,
            reminder_type=reminder_type,
            force=force,
        )
        return ReminderTriggerResponse(
            event_id=event.id,
            event_title=event.title,
            reminder_type=reminder_type or "auto",
            orders_processed=0,
            reminders_sent=0,
            reminders_skipped=0,
            orders_without_email=0,
            errors=["Traitement asynchrone démarré en arrière-plan."],
        )

    try:
        report = reminder_service.process_event_reminders(
            event_id=event.id,
            reminder_type=reminder_type,
            force=force,
            db=db,
        )
        return report
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@system_router.post(
    "/reminders/process",
    response_model=SystemRemindersRunResponse,
    summary="Process all scheduled J-7 and J-2 reminders across upcoming published events",
)
def process_system_reminders(
    db: Session = Depends(get_db),
) -> SystemRemindersRunResponse:
    """
    System / Cron hook: evaluates upcoming published events and sends any due J-7 and J-2 reminders.
    Guaranteed idempotent.
    """
    return reminder_service.process_all_scheduled_reminders(db=db)

