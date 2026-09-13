import uuid
import logging
from typing import Optional, Tuple, Any
import stripe
from sqlalchemy.orm import Session
from sqlalchemy import update, func
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.order import Order, BookingItem
from app.models.event import Event
from app.models.spot import Spot

logger = logging.getLogger(__name__)


def create_or_get_payment_intent(
    db: Session,
    order: Order,
    event: Event,
) -> Tuple[str, str]:
    """
    Create or retrieve a Stripe PaymentIntent for the given order and event.
    Attaches metadata: order_id, order_number, event_id, event_slug, exhibitor_email.
    Updates and persists order.stripe_payment_intent_id.
    Returns (client_secret, payment_intent_id).
    """
    api_key = settings.STRIPE_SECRET_KEY
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Le service de paiement Stripe n'est pas configuré (clé secrète manquante).",
        )

    # Minimum charge validation for Stripe (50 cents)
    if order.total_price_cents < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le montant minimum de paiement est de 0,50 €.",
        )

    # 1. Reuse existing PaymentIntent if already attached to the order and not canceled
    if order.stripe_payment_intent_id:
        try:
            existing_intent = stripe.PaymentIntent.retrieve(
                order.stripe_payment_intent_id,
                api_key=api_key,
            )
            intent_status = getattr(existing_intent, "status", None) or existing_intent.get("status")
            if intent_status not in ("canceled",):
                client_secret = getattr(existing_intent, "client_secret", None) or existing_intent.get("client_secret")
                intent_id = getattr(existing_intent, "id", None) or existing_intent.get("id")
                return client_secret, intent_id
        except stripe.StripeError as e:
            logger.warning("Could not retrieve existing PaymentIntent %s: %s", order.stripe_payment_intent_id, e)

    # 2. Create a new PaymentIntent
    metadata = {
        "order_id": str(order.id),
        "order_number": str(order.order_number),
        "event_id": str(event.id),
        "event_slug": str(event.slug),
        "exhibitor_email": str(order.email),
    }
    description = f"Commande {order.order_number} - {event.title}"

    create_params = {
        "amount": order.total_price_cents,
        "currency": "eur",
        "description": description,
        "metadata": metadata,
        "automatic_payment_methods": {"enabled": True},
        "api_key": api_key,
    }
    if getattr(event, "manual_approval_required", False):
        create_params["capture_method"] = "manual"

    try:
        intent = stripe.PaymentIntent.create(**create_params)
    except stripe.StripeError as e:
        logger.error("Stripe PaymentIntent creation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Erreur lors de l'initialisation du paiement Stripe: {str(e)}",
        )

    client_secret = getattr(intent, "client_secret", None) or intent.get("client_secret")
    intent_id = getattr(intent, "id", None) or intent.get("id")

    order.stripe_payment_intent_id = intent_id
    db.add(order)
    db.commit()
    db.refresh(order)

    return client_secret, intent_id


def verify_webhook_event(payload: bytes, sig_header: str) -> Any:
    """
    Cryptographically verify incoming Stripe webhook signature.
    Raises ValueError or stripe.SignatureVerificationError if verification fails.
    """
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    if not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Le secret de webhook Stripe n'est pas configuré.",
        )

    return stripe.Webhook.construct_event(
        payload=payload,
        sig_header=sig_header,
        secret=webhook_secret,
    )


def confirm_order_from_payment_intent(
    db: Session,
    payment_intent_id: str,
    order_id: Optional[str] = None,
    amount_received: Optional[int] = None,
    currency: Optional[str] = None,
) -> Optional[Order]:
    """
    Idempotently transition an Order to 'confirmed' and its associated spots to 'reserved'.
    This cryptographically verified webhook event is the single source of financial truth (AD-3).
    """
    order: Optional[Order] = None

    # Try locating order by order_id from PaymentIntent metadata first
    if order_id:
        try:
            uid = uuid.UUID(str(order_id))
            order = db.query(Order).filter(Order.id == uid).first()
        except ValueError:
            pass

    # Fallback: locate order by stripe_payment_intent_id
    if not order and payment_intent_id:
        order = db.query(Order).filter(Order.stripe_payment_intent_id == payment_intent_id).first()

    if not order:
        logger.warning(
            "Webhook received for unknown order: order_id=%s, payment_intent_id=%s",
            order_id,
            payment_intent_id,
        )
        return None

    # Idempotent execution: if already confirmed, do nothing and return
    if order.status == "confirmed":
        logger.info("Order %s already confirmed; skipping redundant transition", order.order_number)
        return order

    if order.status not in ("pending", "pending_approval"):
        logger.warning(
            "Order %s has status '%s' (expected 'pending' or 'pending_approval'); skipping confirmation",
            order.order_number,
            order.status,
        )
        return None

    # Validate payment amount and currency
    if amount_received is not None and amount_received != order.total_price_cents:
        logger.error(
            "Payment amount mismatch for order %s: received %d cents, expected %d cents",
            order.order_number,
            amount_received,
            order.total_price_cents,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incohérence du montant payé: {amount_received} != {order.total_price_cents}",
        )

    if currency is not None and currency.lower() != "eur":
        logger.error(
            "Payment currency mismatch for order %s: %s (expected eur)",
            order.order_number,
            currency,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Devise de paiement non supportée: {currency} (attendu: eur)",
        )

    # Find spot IDs linked to this order
    booking_items = db.query(BookingItem).filter(BookingItem.order_id == order.id).all()
    spot_ids = [item.spot_id for item in booking_items]

    if spot_ids:
        existing_spots = db.query(Spot).filter(Spot.id.in_(spot_ids)).all()
        if order.status == "pending":
            already_reserved = [s.label for s in existing_spots if s.status == "reserved"]
            if already_reserved:
                logger.error(
                    "Spot collision detected when confirming order %s: spots %s are already reserved!",
                    order.order_number,
                    already_reserved,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Conflit de réservation: les stands suivants sont déjà réservés: {', '.join(already_reserved)}",
                )
        else:
            other_reserved_count = (
                db.query(BookingItem)
                .join(Order, Order.id == BookingItem.order_id)
                .filter(
                    BookingItem.spot_id.in_(spot_ids),
                    Order.id != order.id,
                    Order.status.in_(["confirmed", "pending_approval"]),
                )
                .count()
            )
            if other_reserved_count > 0:
                logger.error(
                    "Spot collision detected when confirming order %s: spots are already reserved by another order!",
                    order.order_number,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflit de réservation: les stands sélectionnés sont déjà réservés par une autre commande.",
                )

        stmt = (
            update(Spot)
            .where(Spot.id.in_(spot_ids))
            .values(
                status="reserved",
                locked_until=None,
                locked_by_token=None,
                updated_at=func.now(),
            )
        )
        db.execute(stmt)

    # Atomically transition order
    order.status = "confirmed"
    order.payment_method = "stripe"
    order.stripe_payment_intent_id = payment_intent_id
    order.updated_at = func.now()

    db.add(order)
    db.commit()
    db.refresh(order)
    logger.info("Order %s successfully confirmed with %d spots reserved", order.order_number, len(spot_ids))
    return order


def hold_order_for_approval(
    db: Session,
    payment_intent_id: str,
    order_id: Optional[str] = None,
    amount_received: Optional[int] = None,
    currency: Optional[str] = None,
) -> Optional[Order]:
    """
    Idempotently transition an Order to 'pending_approval' and its associated spots to 'reserved'.
    Called when Stripe PaymentIntent reaches 'requires_capture' (or via 'payment_intent.amount_capturable_updated' webhook).
    Stands are protected and cannot be booked by others.
    """
    order: Optional[Order] = None

    if order_id:
        try:
            uid = uuid.UUID(str(order_id))
            order = db.query(Order).filter(Order.id == uid).first()
        except ValueError:
            pass

    if not order and payment_intent_id:
        order = db.query(Order).filter(Order.stripe_payment_intent_id == payment_intent_id).first()

    if not order:
        logger.warning(
            "Webhook/event received for unknown order: order_id=%s, payment_intent_id=%s",
            order_id,
            payment_intent_id,
        )
        return None

    # Idempotent execution: if already in pending_approval, do nothing and return
    if order.status == "pending_approval":
        logger.info("Order %s already pending approval; skipping redundant transition", order.order_number)
        return order

    if order.status == "confirmed":
        logger.info("Order %s already confirmed; skipping hold transition", order.order_number)
        return order

    if order.status != "pending":
        logger.warning(
            "Order %s has status '%s' (expected 'pending'); skipping hold transition",
            order.order_number,
            order.status,
        )
        return None

    # Validate amount and currency
    if amount_received is not None and amount_received != order.total_price_cents:
        logger.error(
            "Payment pre-auth amount mismatch for order %s: received %d cents, expected %d cents",
            order.order_number,
            amount_received,
            order.total_price_cents,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incohérence du montant pré-autorisé: {amount_received} != {order.total_price_cents}",
        )

    if currency is not None and currency.lower() != "eur":
        logger.error(
            "Payment currency mismatch for order %s: %s (expected eur)",
            order.order_number,
            currency,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Devise de paiement non supportée: {currency} (attendu: eur)",
        )

    # Protect spots by transitioning them to 'reserved'
    booking_items = db.query(BookingItem).filter(BookingItem.order_id == order.id).all()
    spot_ids = [item.spot_id for item in booking_items]

    if spot_ids:
        existing_spots = db.query(Spot).filter(Spot.id.in_(spot_ids)).all()
        already_reserved = [s.label for s in existing_spots if s.status == "reserved"]
        if already_reserved:
            logger.error(
                "Spot collision detected when holding order %s: spots %s are already reserved!",
                order.order_number,
                already_reserved,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflit de réservation: les stands suivants sont déjà réservés: {', '.join(already_reserved)}",
            )

        stmt = (
            update(Spot)
            .where(Spot.id.in_(spot_ids))
            .values(
                status="reserved",
                locked_until=None,
                locked_by_token=None,
                updated_at=func.now(),
            )
        )
        db.execute(stmt)

    # Atomically transition order
    order.status = "pending_approval"
    order.payment_method = "stripe"
    order.stripe_payment_intent_id = payment_intent_id
    order.updated_at = func.now()

    db.add(order)
    db.commit()
    db.refresh(order)
    logger.info("Order %s transitioned to pending_approval with %d spots protected", order.order_number, len(spot_ids))
    return order


def approve_and_capture_order(
    db: Session,
    order: Order,
    notes: Optional[str] = None,
) -> Order:
    """
    Approve an order in 'pending_approval' status:
    1. Capture authorized funds via stripe.PaymentIntent.capture.
    2. Transition order status to 'confirmed'.
    3. Ensure spots remain 'reserved'.
    """
    if order.status == "confirmed":
        logger.info("Order %s already confirmed", order.order_number)
        return order

    if order.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible d'approuver une commande avec le statut '{order.status}' (attendu: 'pending_approval')",
        )

    # Capture funds in Stripe
    if not order.stripe_payment_intent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identifiant de paiement Stripe manquant pour cette commande.",
        )

    api_key = settings.STRIPE_SECRET_KEY
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="La clé secrète Stripe n'est pas configurée.",
        )
    try:
        stripe.PaymentIntent.capture(
            order.stripe_payment_intent_id,
            api_key=api_key,
        )
    except stripe.StripeError as exc:
        err_msg = str(exc).lower()
        err_code = getattr(exc, "code", "") or ""
        if (
            "already captured" in err_msg
            or "has already been captured" in err_msg
            or err_code == "charge_already_captured"
        ):
            logger.info("PaymentIntent %s already captured, treating idempotently as confirmed", order.stripe_payment_intent_id)
        else:
            logger.error("Stripe capture failed for order %s (PI %s): %s", order.order_number, order.stripe_payment_intent_id, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Échec de la capture du paiement Stripe : {exc}",
            )

    # Update spots to ensure reserved status
    booking_items = db.query(BookingItem).filter(BookingItem.order_id == order.id).all()
    spot_ids = [item.spot_id for item in booking_items]
    if spot_ids:
        stmt = (
            update(Spot)
            .where(Spot.id.in_(spot_ids))
            .values(
                status="reserved",
                locked_until=None,
                locked_by_token=None,
                updated_at=func.now(),
            )
        )
        db.execute(stmt)

    order.status = "confirmed"
    if notes and notes.strip():
        existing_notes = order.admin_notes or ""
        order.admin_notes = f"{existing_notes}\n{notes.strip()}".strip()
    order.updated_at = func.now()

    db.add(order)
    db.commit()
    db.refresh(order)
    logger.info("Order %s successfully approved and captured", order.order_number)
    return order


def reject_and_cancel_order(
    db: Session,
    order: Order,
    reason: Optional[str] = None,
) -> Order:
    """
    Reject an order in 'pending_approval' status:
    1. Cancel pre-authorization via stripe.PaymentIntent.cancel (NO refund, as funds were not captured).
    2. Release spots to 'available' status immediately.
    3. Transition order status to 'rejected' and record optional reason in admin_notes.
    """
    if order.status == "rejected":
        logger.info("Order %s already rejected", order.order_number)
        return order

    if order.status not in ("pending_approval", "pending"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de refuser une commande avec le statut '{order.status}' (attendu: 'pending_approval')",
        )

    # Cancel pre-authorization in Stripe
    if order.stripe_payment_intent_id:
        api_key = settings.STRIPE_SECRET_KEY
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="La clé secrète Stripe n'est pas configurée.",
            )
        try:
            stripe.PaymentIntent.cancel(
                order.stripe_payment_intent_id,
                api_key=api_key,
            )
        except stripe.StripeError as exc:
            err_msg = str(exc).lower()
            err_code = getattr(exc, "code", "") or ""
            if (
                "already canceled" in err_msg
                or "already been canceled" in err_msg
                or "already cancelled" in err_msg
                or "already been cancelled" in err_msg
                or "expired" in err_msg
                or "cannot be canceled" in err_msg
                or err_code in ("payment_intent_unexpected_state", "resource_missing")
            ):
                logger.info(
                    "PaymentIntent %s was already canceled/expired in Stripe (%s), proceeding with rejection and spot liberation",
                    order.stripe_payment_intent_id,
                    exc,
                )
            else:
                logger.error("Stripe cancellation failed for order %s (PI %s): %s", order.order_number, order.stripe_payment_intent_id, exc)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Échec de l'annulation de l'autorisation Stripe : {exc}",
                )

    # Release spots immediately
    booking_items = db.query(BookingItem).filter(BookingItem.order_id == order.id).all()
    spot_ids = [item.spot_id for item in booking_items]
    if spot_ids:
        stmt = (
            update(Spot)
            .where(Spot.id.in_(spot_ids))
            .values(
                status="available",
                locked_until=None,
                locked_by_token=None,
                updated_at=func.now(),
            )
        )
        db.execute(stmt)

    order.status = "rejected"
    if reason and reason.strip():
        existing_notes = order.admin_notes or ""
        reason_text = f"Motif de refus : {reason.strip()}"
        order.admin_notes = f"{existing_notes}\n{reason_text}".strip()
    order.updated_at = func.now()

    db.add(order)
    db.commit()
    db.refresh(order)
    logger.info("Order %s rejected, auth canceled and %d spots released", order.order_number, len(spot_ids))
    return order


def process_order_refund(
    db: Session,
    order: Order,
    reason: Optional[str] = None,
    amount_cents: Optional[int] = None,
) -> Order:
    """
    Arbitrate and process a refund for an order:
    1. Idempotently return order if already 'refunded'.
    2. Check that status is eligible ('cancellation_requested', 'confirmed', 'pending_approval').
    3. If payment_method == 'stripe':
       - If pending_approval: cancel pre-authorization in Stripe.
       - If confirmed or cancellation_requested: call stripe.Refund.create.
       - Handle errors idempotently if already refunded in Stripe, or raise 502 with clear message.
    4. If payment_method in ('check', 'cash', 'other'):
       - Do NOT call Stripe API. Mark refunded offline with trace in admin_notes.
    5. Atomically release all associated spots to 'available' (locked_until=None, locked_by_token=None).
    6. Transition order.status to 'refunded', save reason in admin_notes, update updated_at, commit and refresh.
    """
    if order.status == "refunded":
        logger.info("Order %s already refunded; skipping redundant refund", order.order_number)
        return order

    if order.status not in ("cancellation_requested", "confirmed", "pending_approval"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de rembourser une commande avec le statut '{order.status}'.",
        )

    if amount_cents is not None and amount_cents > order.total_price_cents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le montant du remboursement ({amount_cents / 100:.2f} €) ne peut pas dépasser le montant total de la commande ({order.total_price:.2f} €).",
        )

    # 1. Stripe payment handling
    stripe_refund_id: Optional[str] = None
    if order.payment_method == "stripe":
        if not order.stripe_payment_intent_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Identifiant de paiement Stripe manquant pour cette commande.",
            )
        api_key = settings.STRIPE_SECRET_KEY
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="La clé secrète Stripe n'est pas configurée.",
            )

        if order.status == "pending_approval":
            # Pre-authorization was not captured yet: cancel PI instead of refunding
            try:
                stripe.PaymentIntent.cancel(order.stripe_payment_intent_id, api_key=api_key)
            except stripe.StripeError as exc:
                err_msg = str(exc).lower()
                if "already canceled" not in err_msg and "already been canceled" not in err_msg:
                    logger.error("Stripe cancellation failed for order %s: %s", order.order_number, exc)
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Échec de l'annulation de l'autorisation Stripe : {exc}",
                    )
        else:
            refund_kwargs: dict = {
                "payment_intent": order.stripe_payment_intent_id,
                "api_key": api_key,
                "idempotency_key": f"refund_{order.id}",
            }
            if amount_cents is not None:
                refund_kwargs["amount"] = amount_cents

            try:
                refund_obj = stripe.Refund.create(**refund_kwargs)
                stripe_refund_id = getattr(refund_obj, "id", None) if refund_obj else None
            except stripe.StripeError as exc:
                err_msg = str(exc).lower()
                err_code = getattr(exc, "code", "") or ""
                if (
                    "already been refunded" in err_msg
                    or "already refunded" in err_msg
                    or "charge_already_refunded" in err_msg
                    or err_code == "charge_already_refunded"
                ):
                    logger.info(
                        "PaymentIntent %s already refunded in Stripe, treating idempotently",
                        order.stripe_payment_intent_id,
                    )
                else:
                    logger.error(
                        "Stripe refund failed for order %s (PI %s): %s",
                        order.order_number,
                        order.stripe_payment_intent_id,
                        exc,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Échec du remboursement Stripe : {exc}",
                    )
    else:
        logger.info(
            "Processing offline refund for order %s (payment_method: %s) without Stripe API call",
            order.order_number,
            order.payment_method,
        )

    # 2. Release associated spots immediately
    booking_items = db.query(BookingItem).filter(BookingItem.order_id == order.id).all()
    spot_ids = [item.spot_id for item in booking_items]
    if spot_ids:
        stmt = (
            update(Spot)
            .where(Spot.id.in_(spot_ids))
            .values(
                status="available",
                locked_until=None,
                locked_by_token=None,
                updated_at=func.now(),
            )
        )
        db.execute(stmt)

    # 3. Transition order status and record notes
    order.status = "refunded"
    existing_notes = order.admin_notes or ""
    note_lines = []
    if existing_notes:
        note_lines.append(existing_notes)
    if stripe_refund_id:
        note_lines.append(f"Réf remboursement Stripe : {stripe_refund_id}")
    if order.payment_method in ("check", "cash", "other"):
        note_lines.append(f"Remboursement hors-ligne validé ({order.payment_method}).")
    if reason and reason.strip():
        note_lines.append(f"Motif du remboursement : {reason.strip()}")

    if note_lines:
        order.admin_notes = "\n".join(note_lines).strip()
    order.updated_at = func.now()

    db.add(order)
    db.commit()
    db.refresh(order)
    logger.info("Order %s successfully refunded and %d spots released", order.order_number, len(spot_ids))
    return order


def reject_cancellation_request(
    db: Session,
    order: Order,
    reason: Optional[str] = None,
) -> Order:
    """
    Reject an exhibitor cancellation request:
    1. Idempotently return order if already 'confirmed' and refusal was previously recorded.
    2. Check that status is 'cancellation_requested'.
    3. Require mandatory reason (400 if empty).
    4. Transition status to 'confirmed'.
    5. Spots remain 'reserved'.
    6. Record refusal reason in admin_notes and clear active cancellation request timestamp.
    """
    if order.status == "confirmed":
        if order.admin_notes and "Demande d'annulation refusée" in order.admin_notes:
            logger.info("Order %s already confirmed following rejection; skipping redundant rejection", order.order_number)
            return order
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de refuser la demande d'annulation : aucune demande d'annulation active sur cette commande.",
        )

    if order.status != "cancellation_requested":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de refuser la demande d'annulation : la commande a le statut '{order.status}' (attendu: 'cancellation_requested').",
        )

    if not reason or not reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le motif du refus de l'annulation est obligatoire.",
        )

    # Revert order status to confirmed while leaving spots reserved
    order.status = "confirmed"
    order.cancellation_requested_at = None
    existing_notes = order.admin_notes or ""
    refusal_entry = f"Demande d'annulation refusée : {reason.strip()}"
    if existing_notes:
        order.admin_notes = f"{existing_notes}\n{refusal_entry}".strip()
    else:
        order.admin_notes = refusal_entry
    order.updated_at = func.now()

    db.add(order)
    db.commit()
    db.refresh(order)
    logger.info("Cancellation request for order %s rejected with reason: %s", order.order_number, reason)
    return order


def cancel_and_refund_all_event_orders(
    db: Session,
    event_id: uuid.UUID,
    reason: Optional[str] = None,
) -> dict:
    """
    Emergency bulk cancellation for an event:
    1. Cancel event (status='cancelled').
    2. Resiliently process each active order (confirmed, cancellation_requested, pending_approval, pending).
    3. Stripe orders -> process_order_refund (or cancel auth for pending_approval).
    4. Offline orders -> marked refunded/cancelled with notes.
    5. Release all spots belonging to the event to 'available'.
    6. Return detailed consolidated report.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable",
        )

    active_statuses = ["confirmed", "cancellation_requested", "pending_approval", "pending"]
    orders = (
        db.query(Order)
        .filter(
            Order.event_id == event_id,
            Order.status.in_(active_statuses),
        )
        .all()
    )

    total_processed = 0
    refunded_count = 0
    cancelled_count = 0
    failed_count = 0
    errors: list[str] = []

    cancellation_note = (
        reason.strip() if reason and reason.strip() else "Annulation générale de l'événement"
    )

    for ord_item in orders:
        total_processed += 1
        if ord_item.status == "pending_approval":
            try:
                reject_and_cancel_order(db=db, order=ord_item, reason=cancellation_note)
                cancelled_count += 1
            except Exception as exc:
                db.rollback()
                logger.error("Error cancelling pending approval order %s: %s", ord_item.order_number, exc)
                failed_count += 1
                errors.append(f"Commande {ord_item.order_number}: {exc}")
                try:
                    err_order = db.query(Order).filter(Order.id == ord_item.id).first()
                    if err_order:
                        existing = err_order.admin_notes or ""
                        err_order.admin_notes = f"{existing}\n[Échec annulation pré-autorisation : {exc}]".strip()
                        db.add(err_order)
                        db.commit()
                except Exception:
                    db.rollback()
        elif ord_item.status == "pending":
            try:
                ord_item.status = "cancelled"
                existing = ord_item.admin_notes or ""
                ord_item.admin_notes = f"{existing}\n{cancellation_note}".strip()
                db.add(ord_item)
                db.commit()
                cancelled_count += 1
            except Exception as exc:
                db.rollback()
                logger.error("Error cancelling pending order %s: %s", ord_item.order_number, exc)
                failed_count += 1
                errors.append(f"Commande {ord_item.order_number}: {exc}")
        elif ord_item.status in ("confirmed", "cancellation_requested"):
            try:
                process_order_refund(db=db, order=ord_item, reason=cancellation_note)
                refunded_count += 1
            except Exception as exc:
                db.rollback()
                logger.error("Error refunding order %s: %s", ord_item.order_number, exc)
                failed_count += 1
                errors.append(f"Commande {ord_item.order_number}: {exc}")
                try:
                    err_order = db.query(Order).filter(Order.id == ord_item.id).first()
                    if err_order:
                        existing = err_order.admin_notes or ""
                        err_order.admin_notes = f"{existing}\n[Échec remboursement annulation générale : {exc}]".strip()
                        db.add(err_order)
                        db.commit()
                except Exception:
                    db.rollback()

    # Atomically release reserved and locked spots belonging to this event (preserves blocked spots)
    stmt = (
        update(Spot)
        .where(
            Spot.event_id == event_id,
            Spot.status.in_(["reserved", "locked"]),
        )
        .values(
            status="available",
            locked_until=None,
            locked_by_token=None,
            updated_at=func.now(),
        )
    )
    db.execute(stmt)

    # Set event status to cancelled
    event.status = "cancelled"
    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "total_processed": total_processed,
        "refunded_count": refunded_count,
        "cancelled_count": cancelled_count,
        "failed_count": failed_count,
        "errors": errors,
        "event_status": event.status,
    }


def refund_order_from_charge(
    db: Session,
    payment_intent_id: Optional[str] = None,
    order_id: Optional[str] = None,
    is_full_refund: bool = True,
) -> Optional[Order]:
    """
    Idempotently sync refund from Stripe 'charge.refunded' webhook event.
    Releases spots to 'available' and marks order as 'refunded' only on full refund.
    """
    order: Optional[Order] = None
    if order_id:
        try:
            uid = uuid.UUID(str(order_id))
            order = db.query(Order).filter(Order.id == uid).first()
        except ValueError:
            pass

    if not order and payment_intent_id:
        order = db.query(Order).filter(Order.stripe_payment_intent_id == payment_intent_id).first()

    if not order:
        logger.warning(
            "Webhook charge.refunded received for unknown order: order_id=%s, payment_intent_id=%s",
            order_id,
            payment_intent_id,
        )
        return None

    if not is_full_refund:
        logger.info("Webhook charge.refunded is partial; logging trace without releasing spots for order %s", order.order_number)
        existing = order.admin_notes or ""
        partial_note = "[Remboursement partiel détecté via webhook Stripe charge.refunded]"
        order.admin_notes = f"{existing}\n{partial_note}".strip()
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    if order.status == "refunded":
        logger.info("Order %s already refunded; skipping redundant webhook transition", order.order_number)
        return order

    # Release spots
    booking_items = db.query(BookingItem).filter(BookingItem.order_id == order.id).all()
    spot_ids = [item.spot_id for item in booking_items]
    if spot_ids:
        stmt = (
            update(Spot)
            .where(Spot.id.in_(spot_ids))
            .values(
                status="available",
                locked_until=None,
                locked_by_token=None,
                updated_at=func.now(),
            )
        )
        db.execute(stmt)

    order.status = "refunded"
    existing = order.admin_notes or ""
    sync_note = "Remboursement synchronisé via webhook Stripe charge.refunded."
    if existing:
        order.admin_notes = f"{existing}\n{sync_note}".strip()
    else:
        order.admin_notes = sync_note
    order.updated_at = func.now()

    db.add(order)
    db.commit()
    db.refresh(order)
    logger.info("Order %s updated to 'refunded' via webhook charge.refunded and spots released", order.order_number)
    return order

