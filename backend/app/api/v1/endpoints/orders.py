import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, select, or_, and_

from app.core.database import get_db
from app.models.event import Event
from app.models.spot import Spot
from app.models.order import Order, BookingItem
from app.schemas.order import (
    OfflineOrderCreate,
    EventDashboardStats,
    AdminOrderOut,
    AdminOrderListResponse,
    OrderApprovalAction,
)
from app.services import stripe_service

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


def compute_dashboard_stats(db: Session, event: Event) -> EventDashboardStats:
    """Compute real-time occupancy and revenue KPIs for an event."""
    total_spots = (
        db.query(func.count(Spot.id))
        .filter(Spot.event_id == event.id)
        .scalar()
        or 0
    )
    reserved_spots = (
        db.query(func.count(Spot.id))
        .filter(Spot.event_id == event.id, Spot.status == "reserved")
        .scalar()
        or 0
    )
    locked_spots = (
        db.query(func.count(Spot.id))
        .filter(
            Spot.event_id == event.id,
            Spot.status == "locked",
            Spot.locked_until > func.now(),
        )
        .scalar()
        or 0
    )
    blocked_spots = (
        db.query(func.count(Spot.id))
        .filter(Spot.event_id == event.id, Spot.status == "blocked")
        .scalar()
        or 0
    )
    available_spots = max(0, total_spots - reserved_spots - locked_spots - blocked_spots)
    occupancy_rate = (
        round((reserved_spots / total_spots) * 100, 1) if total_spots > 0 else 0.0
    )

    # Revenues from confirmed orders
    stripe_revenue_cents = (
        db.query(func.coalesce(func.sum(Order.total_price_cents), 0))
        .filter(
            Order.event_id == event.id,
            Order.status == "confirmed",
            Order.payment_method == "stripe",
        )
        .scalar()
        or 0
    )

    offline_check_cents = (
        db.query(func.coalesce(func.sum(Order.total_price_cents), 0))
        .filter(
            Order.event_id == event.id,
            Order.status == "confirmed",
            Order.payment_method == "check",
        )
        .scalar()
        or 0
    )

    offline_cash_cents = (
        db.query(func.coalesce(func.sum(Order.total_price_cents), 0))
        .filter(
            Order.event_id == event.id,
            Order.status == "confirmed",
            Order.payment_method == "cash",
        )
        .scalar()
        or 0
    )

    offline_other_cents = (
        db.query(func.coalesce(func.sum(Order.total_price_cents), 0))
        .filter(
            Order.event_id == event.id,
            Order.status == "confirmed",
            Order.payment_method == "other",
        )
        .scalar()
        or 0
    )

    offline_revenue_cents = offline_check_cents + offline_cash_cents + offline_other_cents
    total_revenue_cents = stripe_revenue_cents + offline_revenue_cents

    total_orders_count = (
        db.query(func.count(Order.id))
        .filter(Order.event_id == event.id)
        .scalar()
        or 0
    )
    confirmed_orders_count = (
        db.query(func.count(Order.id))
        .filter(Order.event_id == event.id, Order.status == "confirmed")
        .scalar()
        or 0
    )
    pending_orders_count = (
        db.query(func.count(Order.id))
        .filter(Order.event_id == event.id, Order.status == "pending")
        .scalar()
        or 0
    )
    pending_approval_orders_count = (
        db.query(func.count(Order.id))
        .filter(Order.event_id == event.id, Order.status == "pending_approval")
        .scalar()
        or 0
    )
    offline_orders_count = (
        db.query(func.count(Order.id))
        .filter(
            Order.event_id == event.id,
            Order.status == "confirmed",
            Order.payment_method.in_(["check", "cash", "other"]),
        )
        .scalar()
        or 0
    )

    return EventDashboardStats(
        total_spots=total_spots,
        reserved_spots=reserved_spots,
        locked_spots=locked_spots,
        available_spots=available_spots,
        occupancy_rate=occupancy_rate,
        total_revenue_cents=total_revenue_cents,
        total_revenue=round(total_revenue_cents / 100.0, 2),
        stripe_revenue_cents=stripe_revenue_cents,
        stripe_revenue=round(stripe_revenue_cents / 100.0, 2),
        offline_revenue_cents=offline_revenue_cents,
        offline_revenue=round(offline_revenue_cents / 100.0, 2),
        offline_check_cents=offline_check_cents,
        offline_check_revenue=round(offline_check_cents / 100.0, 2),
        offline_cash_cents=offline_cash_cents,
        offline_cash_revenue=round(offline_cash_cents / 100.0, 2),
        offline_other_cents=offline_other_cents,
        offline_other_revenue=round(offline_other_cents / 100.0, 2),
        total_orders_count=total_orders_count,
        confirmed_orders_count=confirmed_orders_count,
        pending_orders_count=pending_orders_count,
        offline_orders_count=offline_orders_count,
        pending_approval_orders_count=pending_approval_orders_count,
    )


@router.get(
    "/{id_or_slug}/dashboard-stats",
    response_model=EventDashboardStats,
    summary="Get real-time dashboard KPIs for an event",
)
def get_dashboard_stats(
    id_or_slug: str,
    db: Session = Depends(get_db),
) -> EventDashboardStats:
    """Returns real-time occupancy and revenue stats (Stripe vs Offline) for an event."""
    event = get_event_by_id_or_slug(db, id_or_slug)
    return compute_dashboard_stats(db, event)


@router.get(
    "/{id_or_slug}/orders",
    response_model=AdminOrderListResponse,
    summary="List orders for an event with filtering, search and dashboard stats",
)
def list_event_orders(
    id_or_slug: str,
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status: 'all', 'confirmed', 'pending', 'offline'",
    ),
    search: Optional[str] = Query(
        None,
        description="Search by exhibitor name, spot label, email, phone, or order number",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> AdminOrderListResponse:
    """Retrieve orders for the event with optional status filter and instant search."""
    event = get_event_by_id_or_slug(db, id_or_slug)

    query = (
        db.query(Order)
        .options(
            selectinload(Order.items).selectinload(BookingItem.spot),
        )
        .filter(Order.event_id == event.id)
    )

    # Status filter
    if status_filter and status_filter.lower() != "all":
        st = status_filter.lower().strip()
        if st == "offline":
            query = query.filter(Order.payment_method.in_(["check", "cash", "other"]))
        elif st in ("pending_approval", "to_validate"):
            query = query.filter(Order.status == "pending_approval")
        elif st in ("confirmed", "pending", "rejected", "cancelled"):
            query = query.filter(Order.status == st)

    # Search filter
    if search and search.strip():
        term = f"%{search.strip()}%"
        matching_spot_orders = (
            select(BookingItem.order_id)
            .join(Spot, Spot.id == BookingItem.spot_id)
            .where(Spot.label.ilike(term))
        )
        query = query.filter(
            or_(
                Order.first_name.ilike(term),
                Order.last_name.ilike(term),
                func.concat(Order.first_name, " ", Order.last_name).ilike(term),
                func.concat(Order.last_name, " ", Order.first_name).ilike(term),
                Order.email.ilike(term),
                Order.phone.ilike(term),
                Order.order_number.ilike(term),
                Order.id.in_(matching_spot_orders),
            )
        )

    total = query.count()
    orders = query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()

    stats = compute_dashboard_stats(db, event)

    return AdminOrderListResponse(
        items=[AdminOrderOut.model_validate(o) for o in orders],
        total=total,
        stats=stats,
    )


@router.post(
    "/{id_or_slug}/orders/manual",
    response_model=AdminOrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manual offline booking for an exhibitor",
)
def create_manual_booking(
    id_or_slug: str,
    payload: OfflineOrderCreate,
    db: Session = Depends(get_db),
) -> AdminOrderOut:
    """
    Create a manual offline booking without Stripe.
    Atomically transitions the selected spots to 'reserved' and records payment method (check, cash, other).
    Rejects with 409 Conflict if any selected spot is already reserved, blocked, or actively locked.
    """
    event = get_event_by_id_or_slug(db, id_or_slug)

    # Validate that at least one spot is selected
    if not payload.spot_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Au moins un stand doit être sélectionné pour la réservation.",
        )

    # Retrieve spots with lock if supported
    spot_query = db.query(Spot).filter(
        Spot.id.in_(payload.spot_ids),
        Spot.event_id == event.id,
    )
    if db.bind and db.bind.dialect.name != "sqlite":
        spot_query = spot_query.with_for_update()
    spots = spot_query.all()

    if len(spots) != len(set(payload.spot_ids)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Un ou plusieurs stands spécifiés sont introuvables pour cet événement.",
        )

    # Verify each spot availability
    now_utc = datetime.now(timezone.utc)
    for spot in spots:
        if spot.status in ("reserved", "blocked"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Le stand '{spot.label}' n'est pas disponible (statut actuel : {spot.status}).",
            )
        if spot.status == "locked":
            locked_until = spot.locked_until
            if locked_until is not None and locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until and locked_until > now_utc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Le stand '{spot.label}' est temporairement verrouillé par une réservation en cours.",
                )

    # Compute financial amount
    if payload.custom_price_cents is not None:
        total_price_cents = payload.custom_price_cents
    else:
        total_price_cents = sum(spot.price_cents for spot in spots)

    # Create order
    order = Order(
        event_id=event.id,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        email=payload.email.strip().lower() if payload.email and payload.email.strip() else None,
        phone=payload.phone.strip(),
        street_address=payload.street_address.strip() if payload.street_address and payload.street_address.strip() else None,
        postal_code=payload.postal_code.strip() if payload.postal_code and payload.postal_code.strip() else None,
        city=payload.city.strip() if payload.city and payload.city.strip() else None,
        honor_declaration_accepted=True,
        total_price_cents=total_price_cents,
        status="confirmed",
        payment_method=payload.payment_method,
        offline_payment_reference=payload.offline_payment_reference.strip() if payload.offline_payment_reference else None,
        admin_notes=payload.admin_notes.strip() if payload.admin_notes else None,
    )
    db.add(order)
    db.flush()

    # Link booking items and update spot status to reserved
    for spot in spots:
        spot.status = "reserved"
        spot.locked_until = None
        spot.locked_by_token = None

        booking_item = BookingItem(
            order_id=order.id,
            spot_id=spot.id,
            price_cents=spot.price_cents,
        )
        db.add(booking_item)

    db.commit()

    # Reload order with relations
    order = (
        db.query(Order)
        .options(selectinload(Order.items).selectinload(BookingItem.spot))
        .filter(Order.id == order.id)
        .first()
    )

    return AdminOrderOut.model_validate(order)


@router.post(
    "/{id_or_slug}/orders/{order_id}/approve",
    response_model=AdminOrderOut,
    summary="Approve a pending_approval order and capture payment",
)
def approve_order(
    id_or_slug: str,
    order_id: uuid.UUID,
    payload: Optional[OrderApprovalAction] = None,
    db: Session = Depends(get_db),
) -> AdminOrderOut:
    """
    Approve an exhibitor order currently in 'pending_approval' status.
    Captures authorized funds in Stripe, confirms the order, and keeps spots reserved.
    """
    event = get_event_by_id_or_slug(db, id_or_slug)

    order_query = (
        db.query(Order)
        .options(selectinload(Order.items).selectinload(BookingItem.spot))
        .filter(Order.id == order_id, Order.event_id == event.id)
    )
    if db.bind and getattr(db.bind, "dialect", None) and db.bind.dialect.name != "sqlite":
        order_query = order_query.with_for_update()
    order = order_query.first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commande introuvable pour cet événement.",
        )

    if order.status == "confirmed":
        return AdminOrderOut.model_validate(order)

    if order.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible d'approuver cette commande (statut actuel: '{order.status}'). Seules les commandes 'pending_approval' peuvent être approuvées.",
        )

    notes = payload.reason if payload else None
    approved_order = stripe_service.approve_and_capture_order(
        db=db,
        order=order,
        notes=notes,
    )

    refreshed_order = (
        db.query(Order)
        .options(selectinload(Order.items).selectinload(BookingItem.spot))
        .filter(Order.id == approved_order.id)
        .first()
    )
    return AdminOrderOut.model_validate(refreshed_order)


@router.post(
    "/{id_or_slug}/orders/{order_id}/reject",
    response_model=AdminOrderOut,
    summary="Reject a pending_approval order, cancel authorization, and release spots",
)
def reject_order(
    id_or_slug: str,
    order_id: uuid.UUID,
    payload: Optional[OrderApprovalAction] = None,
    db: Session = Depends(get_db),
) -> AdminOrderOut:
    """
    Reject an exhibitor order currently in 'pending_approval' status.
    Cancels pre-authorization in Stripe without debiting, marks order as 'rejected',
    and immediately releases stalls back to 'available'.
    """
    event = get_event_by_id_or_slug(db, id_or_slug)

    order_query = (
        db.query(Order)
        .options(selectinload(Order.items).selectinload(BookingItem.spot))
        .filter(Order.id == order_id, Order.event_id == event.id)
    )
    if db.bind and getattr(db.bind, "dialect", None) and db.bind.dialect.name != "sqlite":
        order_query = order_query.with_for_update()
    order = order_query.first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commande introuvable pour cet événement.",
        )

    if order.status == "rejected":
        return AdminOrderOut.model_validate(order)

    if order.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de refuser cette commande (statut actuel: '{order.status}'). Seules les commandes 'pending_approval' peuvent être refusées.",
        )

    reason = payload.reason if payload else None
    rejected_order = stripe_service.reject_and_cancel_order(
        db=db,
        order=order,
        reason=reason,
    )

    refreshed_order = (
        db.query(Order)
        .options(selectinload(Order.items).selectinload(BookingItem.spot))
        .filter(Order.id == rejected_order.id)
        .first()
    )
    return AdminOrderOut.model_validate(refreshed_order)
