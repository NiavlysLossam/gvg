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

    try:
        intent = stripe.PaymentIntent.create(
            amount=order.total_price_cents,
            currency="eur",
            description=description,
            metadata=metadata,
            automatic_payment_methods={"enabled": True},
            api_key=api_key,
        )
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

    if order.status != "pending":
        logger.warning(
            "Order %s has status '%s' (expected 'pending'); skipping confirmation",
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
        # Check if any spot in order.items is already reserved by another order before reserving
        existing_spots = db.query(Spot).filter(Spot.id.in_(spot_ids)).all()
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
