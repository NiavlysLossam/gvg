import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.event import Event
from app.models.order import Order
from app.models.user import User
from app.api.deps import get_current_user, check_event_ownership
from app.schemas.broadcast import (
    BroadcastPreviewRequest,
    BroadcastPreviewResponse,
    BroadcastSendRequest,
    BroadcastSendResponse,
)
from app.services import broadcast_service

router = APIRouter()


def get_event_by_id_or_slug(
    db: Session,
    id_or_slug: str,
    current_user: Optional[User] = None,
) -> Event:
    """Retrieve an event by UUID or slug, raising 404 if not found and 403 if forbidden."""
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


@router.post(
    "/{id_or_slug}/broadcast/preview",
    response_model=BroadcastPreviewResponse,
    summary="Generate instant rendered preview of a broadcast email with interpolated tags",
)
def preview_broadcast(
    id_or_slug: str,
    payload: BroadcastPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BroadcastPreviewResponse:
    """
    Renders live HTML and plain-text preview of an announcement email using actual
    event details and a sample exhibitor reservation.
    """
    event = get_event_by_id_or_slug(db, id_or_slug, current_user)
    if event.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de prévisualiser ou diffuser des e-mails sur un événement annulé",
        )

    try:
        return broadcast_service.generate_broadcast_preview(
            event_id_or_slug=event.id,
            subject=payload.subject,
            body=payload.body,
            order_id=payload.order_id,
            db=db,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/{id_or_slug}/broadcast/send",
    response_model=BroadcastSendResponse,
    summary="Trigger asynchronous broadcast delivery or test send to exhibitors",
)
def send_broadcast(
    id_or_slug: str,
    payload: BroadcastSendRequest,
    background_tasks: BackgroundTasks,
    background: bool = Query(True, description="Whether to enqueue delivery via BackgroundTasks"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BroadcastSendResponse:
    """
    Dispatches individualized broadcast emails with tag interpolation to confirmed exhibitors
    or sends a single test email to the organizer.
    Always asynchronous by default using FastAPI BackgroundTasks.
    """
    event = get_event_by_id_or_slug(db, id_or_slug, current_user)
    if event.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de prévisualiser ou diffuser des e-mails sur un événement annulé",
        )

    if not payload.is_test and payload.target_audience == "selected" and not payload.selected_order_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune commande sélectionnée pour la diffusion ciblée",
        )

    # Compute preview counts upfront
    if payload.is_test:
        total_targeted = 1
        recipients_without_email = 0
    else:
        query = db.query(Order).filter(Order.event_id == event.id, Order.status == "confirmed")
        if payload.target_audience == "selected":
            query = query.filter(Order.id.in_(payload.selected_order_ids or []))
        orders = query.all()
        total_targeted = len(orders)
        recipients_without_email = sum(
            1 for o in orders if not o.email or "@" not in o.email.strip()
        )

    if background:
        background_tasks.add_task(
            broadcast_service.send_broadcast_emails,
            event_id=event.id,
            payload=payload,
        )
        return BroadcastSendResponse(
            status="enqueued",
            event_id=event.id,
            event_title=event.title,
            total_targeted=total_targeted,
            recipients_without_email=recipients_without_email,
            is_test=payload.is_test,
            test_recipient=payload.test_recipient,
            message="Diffusion en cours d'expédition en tâche de fond."
            if not payload.is_test
            else f"E-mail de test en cours d'envoi à {payload.test_recipient or event.organizer_email}.",
        )

    # Synchronous execution (useful for deterministic testing)
    result = broadcast_service.send_broadcast_emails(
        event_id=event.id,
        payload=payload,
        db=db,
    )

    return BroadcastSendResponse(
        status=result["status"],
        event_id=event.id,
        event_title=event.title,
        total_targeted=result["total_targeted"],
        recipients_without_email=result["recipients_without_email"],
        is_test=payload.is_test,
        test_recipient=payload.test_recipient,
        message=f"Diffusion terminée ({result['sent_count']} envoyés, {result['failed_count']} échoués).",
    )

