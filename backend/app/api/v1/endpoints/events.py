import uuid
from datetime import timezone
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from slugify import slugify

from app.core.config import settings
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


@router.post(
    "/{id_or_slug}/background-image",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload background floorplan image for planar event",
)
async def upload_background_image(
    id_or_slug: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Event:
    """
    Upload an indoor floorplan image (PNG, JPEG, WebP) up to 10 MB.
    Saves the image with a collision-safe filename to /uploads/backgrounds/
    and updates the event's background_image_url and map_type.
    """
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

    ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Format non supporté (PNG, JPEG, WebP uniquement)",
        )

    extension_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }
    ext = extension_map.get(content_type, ".png")
    if file.filename and "." in file.filename:
        file_ext = Path(file.filename).suffix.lower()
        if file_ext in [".png", ".jpg", ".jpeg", ".webp"]:
            ext = file_ext

    contents = bytearray()
    total_size = 0
    while chunk := await file.read(1024 * 1024):  # 1 MB chunks
        total_size += len(chunk)
        if total_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="L'image dépasse la taille maximale autorisée de 10 Mo",
            )
        contents.extend(chunk)

    if total_size == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le fichier téléversé est vide",
        )

    # Validate image magic bytes to prevent spoofed content types
    is_valid_image = False
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        is_valid_image = True
    elif contents.startswith(b"\xff\xd8\xff"):
        is_valid_image = True
    elif contents.startswith(b"RIFF") and len(contents) >= 12 and contents[8:12] == b"WEBP":
        is_valid_image = True

    if not is_valid_image:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Le contenu du fichier n'est pas une image valide (PNG, JPEG, WebP attendu)",
        )

    filename = f"{uuid.uuid4().hex}{ext}"
    bg_dir = settings.upload_dir_path / "backgrounds"
    bg_dir.mkdir(parents=True, exist_ok=True)
    target_path = bg_dir / filename

    from starlette.concurrency import run_in_threadpool

    def _write_file():
        with open(target_path, "wb") as f:
            f.write(contents)

    await run_in_threadpool(_write_file)

    event.background_image_url = f"/uploads/backgrounds/{filename}"
    event.map_type = "planar"

    try:
        db.commit()
        db.refresh(event)
    except Exception as exc:
        db.rollback()
        if target_path.exists():
            target_path.unlink()
        raise exc

    return event
