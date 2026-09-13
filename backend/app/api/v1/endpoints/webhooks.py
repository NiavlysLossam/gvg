import logging
import uuid
from fastapi import APIRouter, Request, Header, HTTPException, Depends, status
from sqlalchemy.orm import Session
import stripe

from app.core.database import get_db
from app.models.order import Order
from app.services import stripe_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/stripe",
    summary="Stripe Webhook Handler",
    description="Receive and cryptographically verify signed Stripe events. Transitions order to confirmed and spots to reserved upon payment_intent.succeeded.",
)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    if not stripe_signature:
        logger.warning("Stripe webhook received without Stripe-Signature header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="En-tête Stripe-Signature manquant",
        )

    payload = await request.body()

    try:
        event = stripe_service.verify_webhook_event(payload, stripe_signature)
    except HTTPException:
        raise
    except (ValueError, stripe.SignatureVerificationError) as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Signature de webhook Stripe invalide: {exc}",
        )
    except Exception as exc:
        logger.error("Unexpected error during Stripe webhook verification: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur de traitement du webhook: {exc}",
        )

    event_type = event.get("type") if isinstance(event, dict) else getattr(event, "type", None)
    logger.info("Received valid Stripe webhook event: type=%s", event_type)

    if event_type == "payment_intent.succeeded":
        data_obj = event["data"]["object"] if isinstance(event, dict) else event.data.object
        payment_intent_id = data_obj.get("id") if isinstance(data_obj, dict) else getattr(data_obj, "id", None)
        metadata = data_obj.get("metadata", {}) if isinstance(data_obj, dict) else getattr(data_obj, "metadata", {})
        order_id = metadata.get("order_id") if isinstance(metadata, dict) else getattr(metadata, "order_id", None)
        amount_received = (
            data_obj.get("amount_received")
            if (isinstance(data_obj, dict) and "amount_received" in data_obj and data_obj.get("amount_received") is not None)
            else (data_obj.get("amount") if isinstance(data_obj, dict) else (getattr(data_obj, "amount_received", None) or getattr(data_obj, "amount", None)))
        )
        currency = data_obj.get("currency") if isinstance(data_obj, dict) else getattr(data_obj, "currency", None)

        confirmed_order = stripe_service.confirm_order_from_payment_intent(
            db=db,
            payment_intent_id=payment_intent_id,
            order_id=order_id,
            amount_received=amount_received,
            currency=currency,
        )

        if not confirmed_order:
            logger.warning(
                "Stripe payment_intent.succeeded could not be matched to an order: pi=%s, order_id=%s",
                payment_intent_id,
                order_id,
            )
            return {"status": "ignored", "reason": "order_not_found"}

        return {
            "status": "success",
            "order_id": str(confirmed_order.id),
            "order_number": confirmed_order.order_number,
        }

    elif event_type == "payment_intent.amount_capturable_updated":
        data_obj = event["data"]["object"] if isinstance(event, dict) else event.data.object
        payment_intent_id = data_obj.get("id") if isinstance(data_obj, dict) else getattr(data_obj, "id", None)
        metadata = data_obj.get("metadata", {}) if isinstance(data_obj, dict) else getattr(data_obj, "metadata", {})
        order_id = metadata.get("order_id") if isinstance(metadata, dict) else getattr(metadata, "order_id", None)
        amount_capturable = (
            data_obj.get("amount_capturable")
            if (isinstance(data_obj, dict) and "amount_capturable" in data_obj and data_obj.get("amount_capturable") is not None)
            else (data_obj.get("amount") if isinstance(data_obj, dict) else (getattr(data_obj, "amount_capturable", None) or getattr(data_obj, "amount", None)))
        )
        currency = data_obj.get("currency") if isinstance(data_obj, dict) else getattr(data_obj, "currency", None)

        held_order = stripe_service.hold_order_for_approval(
            db=db,
            payment_intent_id=payment_intent_id,
            order_id=order_id,
            amount_received=amount_capturable,
            currency=currency,
        )

        if not held_order:
            logger.warning(
                "Stripe payment_intent.amount_capturable_updated could not be matched to an order: pi=%s, order_id=%s",
                payment_intent_id,
                order_id,
            )
            return {"status": "ignored", "reason": "order_not_found"}

        return {
            "status": "success",
            "order_id": str(held_order.id),
            "order_number": held_order.order_number,
            "order_status": held_order.status,
        }

    elif event_type == "payment_intent.canceled":
        data_obj = event["data"]["object"] if isinstance(event, dict) else event.data.object
        payment_intent_id = data_obj.get("id") if isinstance(data_obj, dict) else getattr(data_obj, "id", None)
        metadata = data_obj.get("metadata", {}) if isinstance(data_obj, dict) else getattr(data_obj, "metadata", {})
        order_id = metadata.get("order_id") if isinstance(metadata, dict) else getattr(metadata, "order_id", None)

        order = None
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
                "Stripe payment_intent.canceled could not be matched to an order: pi=%s, order_id=%s",
                payment_intent_id,
                order_id,
            )
            return {"status": "ignored", "reason": "order_not_found"}

        if order.status in ("pending_approval", "pending"):
            rejected_order = stripe_service.reject_and_cancel_order(
                db=db,
                order=order,
                reason="Annulation Stripe (expiration pré-autorisation ou annulation bancaire)",
            )
            return {
                "status": "success",
                "order_id": str(rejected_order.id),
                "order_number": rejected_order.order_number,
                "order_status": rejected_order.status,
            }

        return {"status": "ignored", "reason": f"order_status_{order.status}"}

    return {"status": "ignored", "event_type": event_type}
