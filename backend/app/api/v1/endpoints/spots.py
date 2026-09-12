import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from app.core.database import get_db
from app.models.event import Event
from app.models.spot import Spot
from app.schemas.spot import (
    SpotCreate,
    SpotUpdate,
    SpotFeature,
    SpotFeatureCollection,
    geojson_to_wkt_polygon,
    spot_to_feature,
    spots_to_feature_collection,
)

router = APIRouter()


def get_event_by_id_or_slug(db: Session, id_or_slug: str) -> Event:
    """Retrieve an event by UUID or slug, raising 404 if not found."""
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
    return event


@router.get(
    "/{id_or_slug}/spots",
    response_model=SpotFeatureCollection,
    summary="List all spots for an event in GeoJSON FeatureCollection format",
)
def list_spots(
    id_or_slug: str,
    db: Session = Depends(get_db),
) -> SpotFeatureCollection:
    """Retrieve all stalls for the specified event in GeoJSON format."""
    event = get_event_by_id_or_slug(db, id_or_slug)

    results = (
        db.query(Spot, func.ST_AsGeoJSON(Spot.geom).label("geojson"))
        .filter(Spot.event_id == event.id)
        .order_by(Spot.created_at.asc())
        .all()
    )

    return spots_to_feature_collection(results)


@router.post(
    "/{id_or_slug}/spots",
    response_model=SpotFeature,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new spot for an event",
)
def create_spot(
    id_or_slug: str,
    spot_in: SpotCreate,
    db: Session = Depends(get_db),
) -> SpotFeature:
    """
    Create a new stall spot with geometry, label, and linear meters.
    Automatically computes price_cents based on event price_per_meter_cents if not manually overridden.
    """
    event = get_event_by_id_or_slug(db, id_or_slug)

    # Compute price in cents if not provided or overridden
    if spot_in.price_cents is not None:
        price_cents = spot_in.price_cents
    else:
        price_cents = int(round(spot_in.linear_meters * event.price_per_meter_cents))

    try:
        wkt = geojson_to_wkt_polygon(spot_in.geometry)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Géométrie de stand invalide : {str(exc)}",
        ) from exc

    spot = Spot(
        event_id=event.id,
        label=spot_in.label.strip(),
        linear_meters=spot_in.linear_meters,
        price_cents=price_cents,
        geom=wkt,
        status="available",
    )

    db.add(spot)
    try:
        db.commit()
        db.refresh(spot)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Un emplacement avec le libellé « {spot_in.label.strip()} » existe déjà pour cet événement",
        ) from exc

    geojson_str = db.query(func.ST_AsGeoJSON(Spot.geom)).filter(Spot.id == spot.id).scalar()
    return spot_to_feature(spot, geojson_str)


@router.get(
    "/{id_or_slug}/spots/{spot_id}",
    response_model=SpotFeature,
    summary="Get single spot by ID in GeoJSON Feature format",
)
def get_spot(
    id_or_slug: str,
    spot_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> SpotFeature:
    """Retrieve details and geometry for a single spot."""
    event = get_event_by_id_or_slug(db, id_or_slug)

    res = (
        db.query(Spot, func.ST_AsGeoJSON(Spot.geom).label("geojson"))
        .filter(Spot.id == spot_id, Spot.event_id == event.id)
        .first()
    )

    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emplacement introuvable",
        )

    return spot_to_feature(res.Spot, res.geojson)


@router.patch(
    "/{id_or_slug}/spots/{spot_id}",
    response_model=SpotFeature,
    summary="Update spot properties, pricing, or geometry",
)
def update_spot(
    id_or_slug: str,
    spot_id: uuid.UUID,
    spot_in: SpotUpdate,
    db: Session = Depends(get_db),
) -> SpotFeature:
    """
    Update spot label, linear meters, price override, status, or geometry.
    If linear_meters is updated without specifying price_cents, price_cents is recalculated.
    """
    event = get_event_by_id_or_slug(db, id_or_slug)

    spot = db.query(Spot).filter(Spot.id == spot_id, Spot.event_id == event.id).first()
    if not spot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emplacement introuvable",
        )

    # Handle linear_meters and price updates
    if spot_in.linear_meters is not None:
        spot.linear_meters = spot_in.linear_meters
        if spot_in.price_cents is not None:
            spot.price_cents = spot_in.price_cents
        else:
            spot.price_cents = int(round(spot.linear_meters * event.price_per_meter_cents))
    elif spot_in.price_cents is not None:
        spot.price_cents = spot_in.price_cents

    if spot_in.label is not None:
        spot.label = spot_in.label.strip()

    if spot_in.status is not None:
        spot.status = spot_in.status

    if spot_in.geometry is not None:
        try:
            spot.geom = geojson_to_wkt_polygon(spot_in.geometry)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Géométrie de stand invalide : {str(exc)}",
            ) from exc

    try:
        db.commit()
        db.refresh(spot)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Un emplacement avec le libellé « {spot.label} » existe déjà pour cet événement",
        ) from exc

    geojson_str = db.query(func.ST_AsGeoJSON(Spot.geom)).filter(Spot.id == spot.id).scalar()
    return spot_to_feature(spot, geojson_str)


@router.delete(
    "/{id_or_slug}/spots/{spot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a spot",
)
def delete_spot(
    id_or_slug: str,
    spot_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a spot by ID."""
    event = get_event_by_id_or_slug(db, id_or_slug)

    spot = db.query(Spot).filter(Spot.id == spot_id, Spot.event_id == event.id).first()
    if not spot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emplacement introuvable",
        )

    if spot.status == "reserved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de supprimer un emplacement déjà réservé",
        )

    db.delete(spot)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

