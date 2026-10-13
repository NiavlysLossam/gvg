import logging
import uuid
from fastapi import APIRouter, Request, Header, HTTPException, Depends, status, BackgroundTasks
from sqlalchemy.orm import Session
import stripe

from app.core.config import settings
from app.core.database import get_db
from app.models.event import Event
from app.models.spot import Spot
from app.models.order import Order, BookingItem
from app.services import stripe_service, email_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/stripe",
    summary="Stripe Webhook Handler",
    description="Receive and cryptographically verify signed Stripe events. Transitions order to confirmed and spots to reserved upon payment_intent.succeeded.",
)
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
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

        try:
            confirmed_order = stripe_service.confirm_order_from_payment_intent(
                db=db,
                payment_intent_id=payment_intent_id,
                order_id=order_id,
                amount_received=amount_received,
                currency=currency,
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_409_CONFLICT:
                logger.error(
                    "Spot collision (409) during payment_intent.succeeded for order %s (PI %s). Initiating emergency auto-refund: %s",
                    order_id,
                    payment_intent_id,
                    exc.detail,
                )
                # Find order to record audit trail and mark refunded/cancelled
                conflict_order = None
                if order_id:
                    try:
                        conflict_order = db.query(Order).filter(Order.id == uuid.UUID(str(order_id))).first()
                    except ValueError:
                        pass
                if not conflict_order and payment_intent_id:
                    conflict_order = db.query(Order).filter(Order.stripe_payment_intent_id == payment_intent_id).first()

                # Release any spots that were locked by this order's session or items back to available
                if conflict_order:
                    items = db.query(BookingItem).filter(BookingItem.order_id == conflict_order.id).all()
                    order_spot_ids = [it.spot_id for it in items]
                    if order_spot_ids:
                        db.query(Spot).filter(
                            Spot.id.in_(order_spot_ids),
                            Spot.status == "locked",
                        ).update(
                            {
                                "status": "available",
                                "locked_until": None,
                                "locked_by_token": None,
                            },
                            synchronize_session=False,
                        )

                # Issue immediate full Stripe refund
                api_key = settings.STRIPE_SECRET_KEY
                refund_id = None
                refund_error = None
                if api_key and payment_intent_id:
                    try:
                        refund_obj = stripe.Refund.create(
                            payment_intent=payment_intent_id,
                            api_key=api_key,
                            idempotency_key=f"auto_refund_conflict_{payment_intent_id}",
                        )
                        refund_id = getattr(refund_obj, "id", None)
                    except stripe.StripeError as s_exc:
                        refund_error = str(s_exc)
                        logger.error("Failed to execute emergency auto-refund on Stripe for PI %s: %s", payment_intent_id, s_exc)

                if conflict_order:
                    if refund_id:
                        conflict_order.status = "refunded"
                        note = "[Système] Conflit de stand lors du webhook de paiement : remboursement automatique effectué."
                    else:
                        conflict_order.status = "cancelled"
                        note = f"[Alerte Sécurité] Conflit de stand lors du webhook (409) mais le remboursement Stripe automatique a échoué: {refund_error or 'Clé Stripe manquante'}. Action manuelle requise."

                    conflict_order.admin_notes = f"{conflict_order.admin_notes}\n{note}".strip() if conflict_order.admin_notes else note
                    conflict_order.stripe_payment_intent_id = payment_intent_id
                    db.commit()

                # If Stripe refund failed, re-raise 502 Bad Gateway to force Stripe to retry the webhook delivery
                if not refund_id and not (isinstance(refund_error, str) and "already been refunded" in refund_error.lower()):
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Échec de l'auto-remboursement Stripe lors du conflit 409 : {refund_error or 'Clé API manquante'}",
                    )

                # Return 200 OK to Stripe to ack the event and avoid infinite webhook retries
                return {
                    "status": "conflict_refunded",
                    "reason": "spot_already_taken",
                    "detail": str(exc.detail),
                    "refund_id": refund_id,
                }
            raise

        if not confirmed_order:
            logger.warning(
                "Stripe payment_intent.succeeded could not be matched to an order: pi=%s, order_id=%s",
                payment_intent_id,
                order_id,
            )
            return {"status": "ignored", "reason": "order_not_found"}

        event_obj = db.query(Event).filter(Event.id == confirmed_order.event_id).first()
        if event_obj and confirmed_order.email:
            background_tasks.add_task(
                email_service.send_order_confirmation_email,
                order=confirmed_order.id,
                event=event_obj.id,
            )

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

        try:
            held_order = stripe_service.hold_order_for_approval(
                db=db,
                payment_intent_id=payment_intent_id,
                order_id=order_id,
                amount_received=amount_capturable,
                currency=currency,
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_409_CONFLICT:
                logger.error(
                    "Spot collision (409) during amount_capturable_updated for order %s (PI %s). Canceling pre-authorization: %s",
                    order_id,
                    payment_intent_id,
                    exc.detail,
                )
                cancel_success = False
                cancel_error = None
                api_key = settings.STRIPE_SECRET_KEY
                if api_key and payment_intent_id:
                    try:
                        stripe.PaymentIntent.cancel(payment_intent_id, api_key=api_key)
                        cancel_success = True
                    except stripe.StripeError as s_exc:
                        cancel_error = str(s_exc)
                        if "already canceled" in cancel_error.lower() or "already been canceled" in cancel_error.lower():
                            cancel_success = True
                        else:
                            logger.error("Failed to cancel PaymentIntent %s: %s", payment_intent_id, s_exc)

                conflict_order = None
                if order_id:
                    try:
                        conflict_order = db.query(Order).filter(Order.id == uuid.UUID(str(order_id))).first()
                    except ValueError:
                        pass
                if not conflict_order and payment_intent_id:
                    conflict_order = db.query(Order).filter(Order.stripe_payment_intent_id == payment_intent_id).first()

                # Release any locked spots belonging to this order
                if conflict_order:
                    items = db.query(BookingItem).filter(BookingItem.order_id == conflict_order.id).all()
                    order_spot_ids = [it.spot_id for it in items]
                    if order_spot_ids:
                        db.query(Spot).filter(
                            Spot.id.in_(order_spot_ids),
                            Spot.status == "locked",
                        ).update(
                            {
                                "status": "available",
                                "locked_until": None,
                                "locked_by_token": None,
                            },
                            synchronize_session=False,
                        )

                    conflict_order.status = "cancelled"
                    note = (
                        "[Système] Conflit de stand lors du webhook de pré-autorisation : autorisation Stripe annulée."
                        if cancel_success
                        else f"[Alerte Sécurité] Conflit de stand (409) mais l'annulation de pré-autorisation Stripe a échoué: {cancel_error}. Action manuelle requise."
                    )
                    conflict_order.admin_notes = f"{conflict_order.admin_notes}\n{note}".strip() if conflict_order.admin_notes else note
                    db.commit()

                if not cancel_success:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Échec de l'annulation de pré-autorisation Stripe lors du conflit 409 : {cancel_error or 'Clé API manquante'}",
                    )

                return {
                    "status": "conflict_cancelled",
                    "reason": "spot_already_taken",
                    "detail": str(exc.detail),
                }
            raise

        if not held_order:
            logger.warning(
                "Stripe payment_intent.amount_capturable_updated could not be matched to an order: pi=%s, order_id=%s",
                payment_intent_id,
                order_id,
            )
            return {"status": "ignored", "reason": "order_not_found"}

        event_obj = db.query(Event).filter(Event.id == held_order.event_id).first()
        if event_obj and held_order.email:
            background_tasks.add_task(
                email_service.send_order_confirmation_email,
                order=held_order.id,
                event=event_obj.id,
            )

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
            was_pending_approval = (order.status == "pending_approval")
            rejected_order = stripe_service.reject_and_cancel_order(
                db=db,
                order=order,
                reason="Annulation Stripe (expiration pré-autorisation ou annulation bancaire)",
            )
            event_obj = db.query(Event).filter(Event.id == rejected_order.event_id).first()
            # Only notify exhibitor of rejection if order had actually been submitted for moderation
            if was_pending_approval and event_obj and rejected_order.email:
                background_tasks.add_task(
                    email_service.send_moderation_decision_email,
                    order=rejected_order.id,
                    event=event_obj.id,
                    approved=False,
                    reason="Annulation Stripe de la pré-autorisation",
                )
            return {
                "status": "success",
                "order_id": str(rejected_order.id),
                "order_number": rejected_order.order_number,
                "order_status": rejected_order.status,
            }

        return {"status": "ignored", "reason": f"order_status_{order.status}"}

    elif event_type == "charge.refunded":
        data_obj = event["data"]["object"] if isinstance(event, dict) else event.data.object
        is_refunded = (
            data_obj.get("refunded")
            if isinstance(data_obj, dict)
            else getattr(data_obj, "refunded", True)
        )
        if is_refunded is False:
            logger.info("Stripe charge.refunded received for partial refund; skipping full order cancellation")
            return {"status": "ignored", "reason": "partial_refund"}

        payment_intent_id = (
            data_obj.get("payment_intent")
            if isinstance(data_obj, dict)
            else getattr(data_obj, "payment_intent", None)
        )
        metadata = data_obj.get("metadata", {}) if isinstance(data_obj, dict) else getattr(data_obj, "metadata", {})
        order_id = metadata.get("order_id") if isinstance(metadata, dict) else getattr(metadata, "order_id", None)

        refunded_order = stripe_service.refund_order_from_charge(
            db=db,
            payment_intent_id=payment_intent_id,
            order_id=order_id,
            is_full_refund=True,
        )

        if not refunded_order:
            logger.warning(
                "Stripe charge.refunded could not be matched to an order: pi=%s, order_id=%s",
                payment_intent_id,
                order_id,
            )
            return {"status": "ignored", "reason": "order_not_found"}

        event_obj = db.query(Event).filter(Event.id == refunded_order.event_id).first()
        # Only send individual arbitration email if event was not cancelled in bulk
        if event_obj and event_obj.status != "cancelled" and refunded_order.email:
            background_tasks.add_task(
                email_service.send_cancellation_arbitration_email,
                order=refunded_order.id,
                event=event_obj.id,
                accepted=True,
                reason="Remboursement Stripe confirmé",
                refund_amount=refunded_order.total_price_cents / 100.0,
            )

        return {
            "status": "success",
            "order_id": str(refunded_order.id),
            "order_number": refunded_order.order_number,
            "order_status": refunded_order.status,
        }

    return {"status": "ignored", "event_type": event_type}

