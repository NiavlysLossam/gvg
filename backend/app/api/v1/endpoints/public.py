import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_

from app.core.database import get_db
from app.models.event import Event
from app.models.spot import Spot
from app.schemas.public import (
    PublicEventResponse,
    PublicSpotFeatureCollection,
    public_spots_to_feature_collection,
)

router = APIRouter()


def get_public_event_by_slug(db: Session, slug: str) -> Event:
    """Retrieve an event by slug (or UUID as fallback), returning 404 if not found."""
    event: Optional[Event] = db.query(Event).filter(Event.slug == slug).first()
    if not event:
        try:
            val_uuid = uuid.UUID(slug)
            event = db.query(Event).filter(Event.id == val_uuid).first()
        except ValueError:
            pass

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable",
        )
    return event


@router.get(
    "/events/{slug}",
    response_model=PublicEventResponse,
    summary="Get public event details by slug",
)
def get_public_event(
    slug: str,
    db: Session = Depends(get_db),
) -> PublicEventResponse:
    """
    Public unauthenticated endpoint to get event presentation metadata:
    title, dates, hours, location address, and map background settings.
    """
    event = get_public_event_by_slug(db, slug)
    return event


@router.get(
    "/events/{slug}/spots",
    response_model=PublicSpotFeatureCollection,
    summary="Get public spots for an event in GeoJSON format with effective status",
)
def get_public_spots(
    slug: str,
    db: Session = Depends(get_db),
) -> PublicSpotFeatureCollection:
    """
    Public unauthenticated endpoint returning all stalls for an event as a GeoJSON FeatureCollection.
    Applies dynamic SQL lazy lock expiration: any stall with status='locked' whose locked_until is NULL
    or locked_until < now() is returned with effective status='available' without waiting for an asynchronous cleanup job.
    Zero sensitive data (such as session tokens or exhibitor records) is exposed.
    """
    event = get_public_event_by_slug(db, slug)

    # Dynamic lazy lock expiration: compute effective status at query time without DB mutation
    effective_status = case(
        (
            and_(
                Spot.status == "locked",
                or_(Spot.locked_until.is_(None), Spot.locked_until < func.now()),
            ),
            "available",
        ),
        else_=Spot.status,
    ).label("effective_status")

    results = (
        db.query(
            Spot,
            func.ST_AsGeoJSON(Spot.geom).label("geojson"),
            effective_status,
        )
        .filter(Spot.event_id == event.id)
        .order_by(Spot.created_at.asc())
        .all()
    )

    return public_spots_to_feature_collection(results)

