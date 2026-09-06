import uuid
from datetime import timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from slugify import slugify

from app.core.database import get_db
from app.models.event import Event
from app.schemas.event import (
    EventCreate,
    EventUpdate,
    EventResponse,
    EventListResponse,
)

router = APIRouter()


def generate_unique_slug(db: Session, title: str, exclude_event_id: Optional[uuid.UUID] = None) -> str:
    """
    Generates a unique slug for an event based on its title.
    Truncates base slug to 240 chars to reserve room for counter suffixes within the 255-char column limit.
    Excludes the provided event ID if updating to prevent self-collision.
    """
    base_slug = slugify(title)
    if not base_slug:
        base_slug = "evenement"
    base_slug = base_slug[:240]
    
    slug = base_slug
    counter = 2

    def slug_exists(candidate: str) -> bool:
        query = db.query(Event).filter(Event.slug == candidate)
        if exclude_event_id is not None:
            query = query.filter(Event.id != exclude_event_id)
        return query.first() is not None

    while slug_exists(slug):
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new flea market event",
)
def create_event(
    event_in: EventCreate,
    db: Session = Depends(get_db),
) -> Event:
    """
    Create a new event with metadata, schedules, pricing, and initial draft status.
    Generates a unique slug from title with collision prevention.
    """
    slug = generate_unique_slug(db, event_in.title)

    event_data = event_in.model_dump(exclude={"price_per_meter"})
    # Ensure price_per_meter_cents is populated
    if event_data.get("price_per_meter_cents") is None and event_in.price_per_meter is not None:
        event_data["price_per_meter_cents"] = int(round(event_in.price_per_meter * 100))

    event = Event(
        **event_data,
        slug=slug,
    )
    db.add(event)
    try:
        db.commit()
        db.refresh(event)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An event with conflicting unique constraints already exists",
        ) from exc

    return event


@router.get(
    "",
    response_model=EventListResponse,
    summary="List all events with optional status filter",
)
def list_events(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
) -> dict:
    """List events with pagination and optional filtering."""
    query = db.query(Event)
    if status_filter:
        query = query.filter(Event.status == status_filter)
    
    total = query.count()
    items = query.order_by(Event.start_date.desc()).offset(skip).limit(limit).all()
    return {"items": items, "total": total}


@router.get(
    "/{id_or_slug}",
    response_model=EventResponse,
    summary="Get event details by UUID or Slug",
)
def get_event(
    id_or_slug: str,
    db: Session = Depends(get_db),
) -> Event:
    """Retrieve an event by its UUID identifier or public URL slug."""
    event: Optional[Event] = None

    # Try UUID parse
    try:
        val_uuid = uuid.UUID(id_or_slug)
        event = db.query(Event).filter(Event.id == val_uuid).first()
    except ValueError:
        # Not a UUID, search by slug
        event = db.query(Event).filter(Event.slug == id_or_slug).first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return event


@router.patch(
    "/{id_or_slug}",
    response_model=EventResponse,
    summary="Update an existing event",
)
def update_event(
    id_or_slug: str,
    event_in: EventUpdate,
    db: Session = Depends(get_db),
) -> Event:
    """Update event metadata or configuration."""
    event: Optional[Event] = None
    try:
        val_uuid = uuid.UUID(id_or_slug)
        event = db.query(Event).filter(Event.id == val_uuid).first()
    except ValueError:
        event = db.query(Event).filter(Event.slug == id_or_slug).first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    update_data = event_in.model_dump(exclude_unset=True, exclude={"price_per_meter"})
    if "price_per_meter" in event_in.model_fields_set and event_in.price_per_meter is not None:
        update_data["price_per_meter_cents"] = int(round(event_in.price_per_meter * 100))

    # Validate partial or full date update against existing dates
    new_start = update_data.get("start_date", event.start_date)
    new_end = update_data.get("end_date", event.end_date)
    
    def _to_utc(dt):
        if dt is None:
            return None
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    if _to_utc(new_end) < _to_utc(new_start):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be greater than or equal to start_date",
        )

    # If title is updated, re-generate slug if title changed (excluding current event ID)
    if "title" in update_data and update_data["title"] != event.title:
        update_data["slug"] = generate_unique_slug(db, update_data["title"], exclude_event_id=event.id)

    for field, value in update_data.items():
        setattr(event, field, value)

    try:
        db.commit()
        db.refresh(event)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An event with conflicting unique constraints already exists",
        ) from exc

    return event
