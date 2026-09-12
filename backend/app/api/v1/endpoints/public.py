import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, update, text

from app.core.database import get_db
from app.models.event import Event
from app.models.spot import Spot
from app.schemas.public import (
    PublicEventResponse,
    PublicSpotFeatureCollection,
    public_spots_to_feature_collection,
    LockSpotRequest,
    UnlockSpotRequest,
    CartSpotItem,
    CartResponse,
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


def get_cart_for_session(db: Session, event_id: uuid.UUID, session_token: str) -> CartResponse:
    """
    Retrieve all actively locked spots for this session token in the specified event,
    cleaning up any expired hold locks in the process.
    """
    # Release any expired locks held by this token so the DB stays clean
    expired_stmt = (
        update(Spot)
        .where(
            Spot.event_id == event_id,
            Spot.status == "locked",
            Spot.locked_by_token == session_token,
            or_(Spot.locked_until.is_(None), Spot.locked_until < func.now()),
        )
        .values(
            status="available",
            locked_until=None,
            locked_by_token=None,
            updated_at=func.now(),
        )
    )
    db.execute(expired_stmt)
    db.commit()

    active_spots = (
        db.query(Spot)
        .filter(
            Spot.event_id == event_id,
            Spot.status == "locked",
            Spot.locked_by_token == session_token,
            Spot.locked_until.is_not(None),
            Spot.locked_until >= func.now(),
        )
        .order_by(Spot.created_at.asc())
        .all()
    )

    items = [CartSpotItem.model_validate(s) for s in active_spots]
    total_count = len(items)
    total_meters = round(sum(s.linear_meters for s in items), 2)
    total_cents = sum(s.price_cents for s in items)
    total_price = round(total_cents / 100.0, 2)
    expires_at = min((s.locked_until for s in items), default=None)

    return CartResponse(
        session_token=session_token,
        spots=items,
        total_count=total_count,
        total_linear_meters=total_meters,
        total_price_cents=total_cents,
        total_price=total_price,
        expires_at=expires_at,
    )


@router.get(
    "/events/{slug}/cart",
    response_model=CartResponse,
    summary="Get current active held cart for a session token",
)
def get_public_cart(
    slug: str,
    session_token: Optional[str] = Query(None, description="Client anonymous session token"),
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    db: Session = Depends(get_db),
) -> CartResponse:
    """
    Public unauthenticated endpoint to retrieve currently held spots in the visitor's cart.
    Prunes expired items automatically.
    """
    event = get_public_event_by_slug(db, slug)
    token = session_token or x_session_token
    if not token or not token.strip():
        return CartResponse(
            session_token="",
            spots=[],
            total_count=0,
            total_linear_meters=0.0,
            total_price_cents=0,
            total_price=0.0,
            expires_at=None,
        )
    return get_cart_for_session(db, event.id, token.strip())


@router.post(
    "/events/{slug}/spots/{spot_id}/lock",
    response_model=CartResponse,
    summary="Acquire a 15-minute temporary hold lock on a spot",
)
def lock_public_spot(
    slug: str,
    spot_id: uuid.UUID,
    payload: Optional[LockSpotRequest] = None,
    session_token: Optional[str] = Query(None),
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    db: Session = Depends(get_db),
) -> CartResponse:
    """
    Acquire a 15-minute temporary hold lock on a stall using atomic single-transaction SQL.
    Returns HTTP 409 Conflict if stall is already held by another visitor or sold/blocked.
    """
    token = (payload.session_token if payload and payload.session_token else None) or x_session_token or session_token
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le jeton de session (session_token) est obligatoire",
        )
    token = token.strip()
    event = get_public_event_by_slug(db, slug)

    bind = db.get_bind()
    is_pg = (bind.dialect.name == "postgresql") if bind else False
    locked_until_expr = (func.now() + text("INTERVAL '15 minutes'")) if is_pg else func.datetime("now", "+15 minutes")

    stmt = (
        update(Spot)
        .where(
            Spot.id == spot_id,
            Spot.event_id == event.id,
            or_(
                Spot.status == "available",
                and_(
                    Spot.status == "locked",
                    or_(
                        Spot.locked_until.is_(None),
                        Spot.locked_until < func.now(),
                        Spot.locked_by_token == token,
                    ),
                ),
            ),
        )
        .values(
            status="locked",
            locked_until=locked_until_expr,
            locked_by_token=token,
            updated_at=func.now(),
        )
    )
    result = db.execute(stmt)
    db.commit()

    if result.rowcount == 0:
        # Atomic lock failed: inspect spot to return specific error code & message
        spot = db.query(Spot).filter(Spot.id == spot_id, Spot.event_id == event.id).first()
        if not spot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Emplacement introuvable",
            )
        if spot.status in ("reserved", "blocked"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cet emplacement n'est plus disponible à la vente",
            )
        if spot.status == "locked":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ce stand est en cours de commande par un autre visiteur",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossible de verrouiller cet emplacement",
        )

    return get_cart_for_session(db, event.id, token)


@router.post(
    "/events/{slug}/spots/{spot_id}/unlock",
    response_model=CartResponse,
    summary="Release a temporary hold lock on a spot",
)
def unlock_public_spot(
    slug: str,
    spot_id: uuid.UUID,
    payload: Optional[UnlockSpotRequest] = None,
    session_token: Optional[str] = Query(None),
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    db: Session = Depends(get_db),
) -> CartResponse:
    """
    Release a temporary hold lock held by this visitor session, returning the stall to available.
    """
    token = (payload.session_token if payload and payload.session_token else None) or x_session_token or session_token
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le jeton de session (session_token) est obligatoire",
        )
    token = token.strip()
    event = get_public_event_by_slug(db, slug)

    stmt = (
        update(Spot)
        .where(
            Spot.id == spot_id,
            Spot.event_id == event.id,
            Spot.status == "locked",
            Spot.locked_by_token == token,
        )
        .values(
            status="available",
            locked_until=None,
            locked_by_token=None,
            updated_at=func.now(),
        )
    )
    result = db.execute(stmt)
    db.commit()

    if result.rowcount == 0:
        spot = db.query(Spot).filter(Spot.id == spot_id, Spot.event_id == event.id).first()
        if not spot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Emplacement introuvable",
            )
        if spot.status == "available":
            # Idempotent release
            pass
        elif spot.status == "locked" and spot.locked_by_token != token:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ce stand est verrouillé par un autre visiteur",
            )
        elif spot.status in ("reserved", "blocked"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cet emplacement ne peut pas être déverrouillé",
            )

    return get_cart_for_session(db, event.id, token)

