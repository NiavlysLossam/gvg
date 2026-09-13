import uuid
import secrets
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, and_, or_, update, text, select

from app.core.config import settings
from app.core.database import get_db
from app.models.event import Event
from app.models.spot import Spot
from app.models.order import Order, BookingItem, generate_order_number, generate_access_token
from app.schemas.public import (
    PublicEventResponse,
    PublicSpotFeatureCollection,
    public_spots_to_feature_collection,
    LockSpotRequest,
    UnlockSpotRequest,
    CartSpotItem,
    CartResponse,
)
from app.schemas.order import GuestOrderCreate, OrderOut, PaymentIntentResponse, CancellationRequestIn
from app.services import stripe_service


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

    order_payment_method = (
        select(Order.payment_method)
        .join(BookingItem, BookingItem.order_id == Order.id)
        .where(BookingItem.spot_id == Spot.id, Order.status == "confirmed")
        .order_by(Order.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )

    results = (
        db.query(
            Spot,
            func.ST_AsGeoJSON(Spot.geom).label("geojson"),
            effective_status,
            order_payment_method.label("order_payment_method"),
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


@router.post(
    "/events/{slug}/orders",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a guest order from currently held cart spots",
)
def create_guest_order(
    slug: str,
    payload: GuestOrderCreate,
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    db: Session = Depends(get_db),
) -> OrderOut:
    """
    Public unauthenticated endpoint to create a guest order bound to spots held in visitor cart.
    Requires valid contact fields and accepted sworn declaration (art. L310-2 du Code de commerce).
    Atomically creates an Order in 'pending' status with unique order_number and unguessable access_token,
    along with BookingItem records for each held stall.
    Returns HTTP 409 Conflict if the cart is empty or hold locks have expired.
    """
    session_token = (payload.session_token or x_session_token or "").strip()
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le jeton de session (session_token) est obligatoire",
        )

    if not payload.honor_declaration_accepted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="L'attestation sur l'honneur est obligatoire pour participer au vide-grenier.",
        )

    event = get_public_event_by_slug(db, slug)

    # 1. Fetch all spots locked by this session token
    held_spots = (
        db.query(Spot)
        .filter(
            Spot.event_id == event.id,
            Spot.status == "locked",
            Spot.locked_by_token == session_token,
        )
        .order_by(Spot.created_at.asc())
        .all()
    )

    if not held_spots:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Votre réservation temporaire a expiré, veuillez resélectionner vos stands.",
        )

    now_utc = datetime.now(timezone.utc)
    expired_spots = []
    active_spots = []
    for s in held_spots:
        locked_until = s.locked_until
        if locked_until is not None and locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until is None or locked_until <= now_utc:
            expired_spots.append(s)
        else:
            active_spots.append(s)

    # If ANY spot locked by this session_token has expired, prune it and reject to avoid partial orders
    if expired_spots:
        for s in expired_spots:
            s.status = "available"
            s.locked_until = None
            s.locked_by_token = None
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Votre réservation temporaire a expiré, veuillez resélectionner vos stands.",
        )

    if not active_spots:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Votre réservation temporaire a expiré, veuillez resélectionner vos stands.",
        )

    active_spot_ids = [s.id for s in active_spots]

    # Check for an existing pending order for these spots to avoid duplicate pending orders on double submission
    existing_pending_order = (
        db.query(Order)
        .join(BookingItem, BookingItem.order_id == Order.id)
        .filter(
            Order.event_id == event.id,
            Order.status == "pending",
            BookingItem.spot_id.in_(active_spot_ids),
        )
        .options(joinedload(Order.items).joinedload(BookingItem.spot))
        .first()
    )
    if existing_pending_order:
        return existing_pending_order

    # 2. Compute total amount
    total_cents = sum(spot.price_cents for spot in active_spots)

    # 3. Create Order
    order_number = generate_order_number()
    while db.query(Order).filter(Order.order_number == order_number).first() is not None:
        order_number = generate_order_number()

    access_token = generate_access_token()

    order = Order(
        event_id=event.id,
        order_number=order_number,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=str(payload.email),
        phone=payload.phone,
        street_address=payload.street_address,
        postal_code=payload.postal_code,
        city=payload.city,
        honor_declaration_accepted=payload.honor_declaration_accepted,
        total_price_cents=total_cents,
        status="pending",
        payment_method="stripe",
        access_token=access_token,
    )
    db.add(order)
    db.flush()

    # 4. Create BookingItem for each held spot
    for spot in active_spots:
        item = BookingItem(
            order_id=order.id,
            spot_id=spot.id,
            price_cents=spot.price_cents,
        )
        db.add(item)

    # 5. Extend locked_until on held spots to now() + 15 min upon order creation
    bind = db.get_bind()
    is_pg = (bind.dialect.name == "postgresql") if bind else False
    locked_until_expr = (func.now() + text("INTERVAL '15 minutes'")) if is_pg else func.datetime("now", "+15 minutes")

    stmt = (
        update(Spot)
        .where(
            Spot.id.in_(active_spot_ids),
            Spot.event_id == event.id,
        )
        .values(
            locked_until=locked_until_expr,
            updated_at=func.now(),
        )
    )
    db.execute(stmt)

    db.commit()

    # Query with joinedload for response
    persisted_order = (
        db.query(Order)
        .options(joinedload(Order.items).joinedload(BookingItem.spot))
        .filter(Order.id == order.id)
        .first()
    )

    return persisted_order


@router.get(
    "/events/{slug}/orders/{order_id}",
    response_model=OrderOut,
    summary="Get order details by order ID and access token",
)
def get_public_order(
    slug: str,
    order_id: uuid.UUID,
    token: Optional[str] = Query(None, description="Order access token"),
    x_access_token: Optional[str] = Header(None, alias="X-Access-Token"),
    db: Session = Depends(get_db),
) -> OrderOut:
    """
    Public unauthenticated endpoint to view order summary and status using the passwordless magic access_token.
    """
    event = get_public_event_by_slug(db, slug)
    access_token = (token or x_access_token or "").strip()
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Le jeton d'accès (token) est obligatoire pour consulter la commande",
        )

    order = (
        db.query(Order)
        .options(joinedload(Order.items).joinedload(BookingItem.spot))
        .filter(
            Order.id == order_id,
            Order.event_id == event.id,
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commande introuvable",
        )

    if not secrets.compare_digest(order.access_token, access_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé : jeton de commande invalide",
        )

    # Resilience: If order is pending and has a PaymentIntent, verify with Stripe (vital for local dev / webhook delay)
    if order.status == "pending" and order.stripe_payment_intent_id and settings.STRIPE_SECRET_KEY:
        try:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            pi = stripe.PaymentIntent.retrieve(order.stripe_payment_intent_id)
            pi_status = getattr(pi, "status", None) if not isinstance(pi, dict) else pi.get("status")
            if pi_status == "succeeded":
                amount_received = (
                    pi.get("amount_received")
                    if (isinstance(pi, dict) and "amount_received" in pi and pi.get("amount_received") is not None)
                    else (pi.get("amount") if isinstance(pi, dict) else (getattr(pi, "amount_received", None) or getattr(pi, "amount", None)))
                )
                stripe_service.confirm_order_from_payment_intent(
                    db,
                    payment_intent_id=order.stripe_payment_intent_id,
                    order_id=str(order.id),
                    amount_received=amount_received,
                    currency=pi.get("currency") if isinstance(pi, dict) else getattr(pi, "currency", None),
                )
                db.refresh(order)
            elif pi_status == "requires_capture" and order.status == "pending":
                amount_capturable = (
                    pi.get("amount_capturable")
                    if (isinstance(pi, dict) and "amount_capturable" in pi and pi.get("amount_capturable") is not None)
                    else (pi.get("amount") if isinstance(pi, dict) else (getattr(pi, "amount_capturable", None) or getattr(pi, "amount", None)))
                )
                stripe_service.hold_order_for_approval(
                    db,
                    payment_intent_id=order.stripe_payment_intent_id,
                    order_id=str(order.id),
                    amount_received=amount_capturable,
                    currency=pi.get("currency") if isinstance(pi, dict) else getattr(pi, "currency", None),
                )
                db.refresh(order)
        except Exception:
            pass

    return order


@router.post(
    "/events/{slug}/orders/{order_id}/payment-intent",
    response_model=PaymentIntentResponse,
    summary="Create or retrieve Stripe PaymentIntent for a pending order",
)
def create_order_payment_intent(
    slug: str,
    order_id: uuid.UUID,
    token: Optional[str] = Query(None, description="Order access token"),
    x_access_token: Optional[str] = Header(None, alias="X-Access-Token"),
    db: Session = Depends(get_db),
) -> PaymentIntentResponse:
    """
    Public unauthenticated endpoint to initialize a Stripe PaymentIntent for a pending guest order.
    Requires valid order access_token and confirms that spot hold locks are still active.
    Returns client_secret and publishable_key for Stripe Elements checkout.
    """
    event = get_public_event_by_slug(db, slug)
    access_token = (token or x_access_token or "").strip()
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Le jeton d'accès (token) est obligatoire pour régler la commande",
        )

    order = (
        db.query(Order)
        .options(joinedload(Order.items).joinedload(BookingItem.spot))
        .filter(
            Order.id == order_id,
            Order.event_id == event.id,
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commande introuvable",
        )

    if not secrets.compare_digest(order.access_token, access_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé : jeton de commande invalide",
        )

    if order.status == "confirmed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette commande est déjà confirmée et réglée.",
        )

    if order.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cette commande ne peut plus être réglée (statut : {order.status}).",
        )

    # Verify that spot locks are still active
    now_utc = datetime.now(timezone.utc)
    expired = False
    if not order.items:
        expired = True
    else:
        for it in order.items:
            spot = it.spot
            if not spot or spot.status != "locked":
                expired = True
                break
            locked_until = spot.locked_until
            if locked_until is not None and locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until is None or locked_until <= now_utc:
                expired = True
                break

    if expired:
        spot_ids = [it.spot_id for it in order.items]
        if spot_ids:
            stmt = (
                update(Spot)
                .where(
                    Spot.id.in_(spot_ids),
                    Spot.status == "locked",
                )
                .values(
                    status="available",
                    locked_until=None,
                    locked_by_token=None,
                    updated_at=func.now(),
                )
            )
            db.execute(stmt)
        order.status = "cancelled"
        order.updated_at = func.now()
        db.add(order)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Votre réservation temporaire a expiré, veuillez resélectionner vos stands.",
        )

    client_secret, payment_intent_id = stripe_service.create_or_get_payment_intent(
        db=db,
        order=order,
        event=event,
    )

    return PaymentIntentResponse(
        client_secret=client_secret,
        publishable_key=settings.STRIPE_PUBLISHABLE_KEY,
        payment_intent_id=payment_intent_id,
        amount_cents=order.total_price_cents,
        currency="eur",
    )


@router.post(
    "/events/{slug}/orders/{order_id}/cancellation-request",
    response_model=OrderOut,
    summary="Submit a cancellation request for an order",
)
def submit_cancellation_request(
    slug: str,
    order_id: uuid.UUID,
    payload: CancellationRequestIn,
    token: Optional[str] = Query(None, description="Order access token"),
    x_access_token: Optional[str] = Header(None, alias="X-Access-Token"),
    db: Session = Depends(get_db),
) -> OrderOut:
    """
    Public unauthenticated endpoint for exhibitors to request an order cancellation.
    Secured by constant-time verification of the passwordless HMAC magic access_token.
    Eligible for confirmed or pending_approval orders.
    Spots remain reserved until formal organizer review and arbitration.
    """
    event = get_public_event_by_slug(db, slug)
    access_token = (token or x_access_token or "").strip()
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Le jeton d'accès (token) est obligatoire pour demander une annulation",
        )

    order = (
        db.query(Order)
        .options(joinedload(Order.items).joinedload(BookingItem.spot))
        .filter(
            Order.id == order_id,
            Order.event_id == event.id,
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commande introuvable",
        )

    if not secrets.compare_digest(order.access_token, access_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé : jeton de commande invalide",
        )

    # Idempotent return if already in cancellation_requested status
    if order.status == "cancellation_requested":
        return order

    # Ineligible terminal states
    if order.status in ("cancelled", "rejected", "refunded"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette commande n'est plus modifiable.",
        )

    # Only confirmed (or pending_approval) orders are eligible
    if order.status not in ("confirmed", "pending_approval"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cette commande ne peut pas faire l'objet d'une demande d'annulation (statut actuel : {order.status}).",
        )

    VALID_CANCELLATION_REASONS = {"medical", "personal", "weather", "other"}
    reason = (payload.cancellation_reason or "").strip().lower()
    if not reason or reason not in VALID_CANCELLATION_REASONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le motif d'annulation est obligatoire et doit être l'un des suivants : {', '.join(sorted(VALID_CANCELLATION_REASONS))}.",
        )

    comment = (
        payload.cancellation_comment.strip()
        if payload.cancellation_comment and payload.cancellation_comment.strip()
        else None
    )

    if reason == "other" and not comment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Une précision dans le commentaire est obligatoire pour le motif 'Autre'.",
        )

    order.status = "cancellation_requested"
    order.cancellation_reason = reason
    order.cancellation_comment = comment
    order.cancellation_requested_at = datetime.now(timezone.utc)
    order.updated_at = func.now()

    db.commit()
    db.refresh(order)

    return order


