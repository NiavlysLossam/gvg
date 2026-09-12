import uuid
from typing import Optional, List
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
    SpotBatchCreate,
    SpotBatchCreateResponse,
    SpotBatchRenumber,
    SpotBatchRenumberResponse,
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


@router.post(
    "/{id_or_slug}/spots/batch",
    response_model=SpotBatchCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Batch create spots for an event atomically",
)
def batch_create_spots(
    id_or_slug: str,
    batch_in: SpotBatchCreate,
    db: Session = Depends(get_db),
) -> SpotBatchCreateResponse:
    """
    Create N spots atomically in a single database transaction.
    If any label collides with an existing spot or within the batch, rolls back completely and returns HTTP 409.
    """
    event = get_event_by_id_or_slug(db, id_or_slug)

    # Check for duplicate labels within the batch payload itself
    seen_labels = set()
    for s_in in batch_in.spots:
        lbl = s_in.label.strip()
        if lbl in seen_labels:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Le stand « {lbl} » existe déjà (libellé en double dans la requête)",
            )
        seen_labels.add(lbl)

    # Check for duplicate labels against existing spots in the event
    existing_conflicts = [
        lbl
        for (lbl,) in db.query(Spot.label)
        .filter(Spot.event_id == event.id, Spot.label.in_(seen_labels))
        .all()
    ]
    if existing_conflicts:
        conflict_label = existing_conflicts[0]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Le stand « {conflict_label} » existe déjà pour cet événement",
        )

    # Prepare spots to insert
    created_spots = []
    for s_in in batch_in.spots:
        if s_in.price_cents is not None:
            price_cents = s_in.price_cents
        else:
            price_cents = int(round(s_in.linear_meters * event.price_per_meter_cents))

        try:
            wkt = geojson_to_wkt_polygon(s_in.geometry)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Géométrie de stand invalide : {str(exc)}",
            ) from exc

        spot = Spot(
            event_id=event.id,
            label=s_in.label.strip(),
            linear_meters=s_in.linear_meters,
            price_cents=price_cents,
            geom=wkt,
            status="available",
        )
        db.add(spot)
        created_spots.append(spot)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflit d'unicité lors de la création groupée des stands",
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création groupée : {str(exc)}",
        ) from exc

    # Query created spots with their GeoJSON geometries
    created_ids = [s.id for s in created_spots]
    results = (
        db.query(Spot, func.ST_AsGeoJSON(Spot.geom).label("geojson"))
        .filter(Spot.id.in_(created_ids))
        .order_by(Spot.created_at.asc())
        .all()
    )
    id_to_row = {
        (row[0].id if hasattr(row, "__getitem__") else row.id): row for row in results
    }
    ordered_results = [id_to_row[s_id] for s_id in created_ids if s_id in id_to_row]
    feature_collection = spots_to_feature_collection(ordered_results)

    return SpotBatchCreateResponse(
        type="FeatureCollection",
        features=feature_collection.features,
        created_count=len(feature_collection.features),
    )


@router.post(
    "/{id_or_slug}/spots/batch-renumber",
    response_model=SpotBatchRenumberResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch renumber spots sequentially or with specific mapping",
)
def batch_renumber_spots(
    id_or_slug: str,
    renumber_in: SpotBatchRenumber,
    db: Session = Depends(get_db),
) -> SpotBatchRenumberResponse:
    """
    Renumber spots atomically using a two-phase update to avoid intermediate unique constraint violations.
    Rolls back completely if any conflict occurs or if a spot does not belong to the event.
    """
    event = get_event_by_id_or_slug(db, id_or_slug)

    # 1. Resolve pairs of (spot_id, target_label)
    pairs: List[tuple[uuid.UUID, str]] = []
    if renumber_in.renumberings:
        pairs = [(item.spot_id, item.label.strip()) for item in renumber_in.renumberings]
    elif renumber_in.spot_ids:
        prefix = renumber_in.prefix or ""
        start = renumber_in.start_number if renumber_in.start_number is not None else 1
        pad = renumber_in.zero_padding if renumber_in.zero_padding is not None else 2
        for idx, s_id in enumerate(renumber_in.spot_ids):
            num = start + idx
            num_str = f"{num:0{pad}d}" if pad > 1 else str(num)
            label = f"{prefix}{num_str}"
            pairs.append((s_id, label))
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Données de renumérotation manquantes (spot_ids ou renumberings requis)",
        )

    # 2. Check for duplicate target labels in the requested mapping
    seen_target_labels = set()
    for _, tgt_label in pairs:
        if tgt_label in seen_target_labels:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Le stand « {tgt_label} » existe déjà (libellé dupliqué dans la renumérotation)",
            )
        seen_target_labels.add(tgt_label)

    # 3. Fetch spots and verify existence and event ownership
    requested_ids = [p[0] for p in pairs]
    db_spots = db.query(Spot).filter(Spot.id.in_(requested_ids)).all()
    spots_by_id = {s.id: s for s in db_spots}

    for s_id in requested_ids:
        if s_id not in spots_by_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Emplacement {s_id} introuvable",
            )
        spot_obj = spots_by_id[s_id]
        if spot_obj.event_id != event.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"L'emplacement {s_id} n'appartient pas à cet événement",
            )

    # 4. Check for conflict with existing spots NOT in the renumber list
    conflicting_spots = (
        db.query(Spot.label)
        .filter(
            Spot.event_id == event.id,
            Spot.label.in_(seen_target_labels),
            ~Spot.id.in_(requested_ids),
        )
        .all()
    )
    if conflicting_spots:
        conflict_label = conflicting_spots[0][0]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Le stand « {conflict_label} » existe déjà pour cet événement",
        )

    # 5. Two-phase update within a single transaction:
    # Phase 1: Assign temporary unique UUID labels to prevent collisions during swap/shifts
    try:
        session_token = uuid.uuid4().hex
        for idx, (s_id, _) in enumerate(pairs):
            spot = spots_by_id[s_id]
            spot.label = f"__tmp_{session_token}_{idx}"
        db.flush()

        # Phase 2: Assign final formatted labels
        for s_id, target_label in pairs:
            spot = spots_by_id[s_id]
            spot.label = target_label

        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflit d'unicité lors de la renumérotation des stands",
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la renumérotation : {str(exc)}",
        ) from exc

    # 6. Return updated spots in the original requested order
    results = (
        db.query(Spot, func.ST_AsGeoJSON(Spot.geom).label("geojson"))
        .filter(Spot.id.in_(requested_ids))
        .all()
    )
    id_to_row = {
        (row[0].id if hasattr(row, "__getitem__") else row.id): row for row in results
    }
    ordered_results = [id_to_row[s_id] for s_id in requested_ids if s_id in id_to_row]
    feature_collection = spots_to_feature_collection(ordered_results)

    return SpotBatchRenumberResponse(
        type="FeatureCollection",
        features=feature_collection.features,
        updated_count=len(feature_collection.features),
    )


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

