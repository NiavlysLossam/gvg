import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Union

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.event import Event
from app.models.order import Order, BookingItem
from app.models.email_log import EmailLog
from app.services import email_service
from app.schemas.reminder import (
    ReminderStatusResponse,
    ReminderTriggerResponse,
    SystemRemindersRunResponse,
)

logger = logging.getLogger(__name__)


def _ensure_utc(dt: Optional[datetime]) -> datetime:
    """Ensure datetime is timezone-aware UTC."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def calculate_event_reminder_windows(event: Event, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculate the number of days remaining until the event start date
    and check eligibility for J-7 and J-2 reminder windows.
    Strictly mutually exclusive windows.
    """
    current_time = _ensure_utc(now)
    event_start = _ensure_utc(event.start_date)

    delta = event_start - current_time
    days_until = delta.total_seconds() / 86400.0

    # J-7 window: strictly between 2.5 and 7.5 days before start
    j7_eligible = 2.5 < days_until <= 7.5

    # J-2 window: strictly between 0.0 (event start) and 2.5 days before start
    j2_eligible = 0.0 <= days_until <= 2.5

    return {
        "days_until_event": round(days_until, 2),
        "j7_eligible": j7_eligible,
        "j2_eligible": j2_eligible,
    }


def get_event_reminder_status(
    event_id_or_slug: str,
    db: Session,
    now: Optional[datetime] = None,
) -> ReminderStatusResponse:
    """Retrieve reminder readiness and delivery counters for an event."""
    event = None
    try:
        ev_id = uuid.UUID(str(event_id_or_slug))
        event = db.query(Event).filter(Event.id == ev_id).first()
    except (ValueError, AttributeError):
        pass

    if not event:
        event = db.query(Event).filter(Event.slug == str(event_id_or_slug)).first()

    if not event:
        raise ValueError(f"Événement introuvable pour '{event_id_or_slug}'")

    windows = calculate_event_reminder_windows(event, now)

    total_confirmed = (
        db.query(func.count(Order.id))
        .filter(Order.event_id == event.id, Order.status == "confirmed")
        .scalar()
        or 0
    )

    total_with_email = (
        db.query(func.count(Order.id))
        .filter(
            Order.event_id == event.id,
            Order.status == "confirmed",
            Order.email.is_not(None),
            Order.email != "",
        )
        .scalar()
        or 0
    )

    # Distinct confirmed orders that have received J-7 reminder
    j7_sent = (
        db.query(func.count(func.distinct(EmailLog.order_id)))
        .join(Order, Order.id == EmailLog.order_id)
        .filter(
            EmailLog.event_id == event.id,
            EmailLog.email_type == "reminder_j7",
            EmailLog.status.in_(["sent", "simulated"]),
            Order.status == "confirmed",
        )
        .scalar()
        or 0
    )

    # Distinct confirmed orders that have received J-2 reminder
    j2_sent = (
        db.query(func.count(func.distinct(EmailLog.order_id)))
        .join(Order, Order.id == EmailLog.order_id)
        .filter(
            EmailLog.event_id == event.id,
            EmailLog.email_type == "reminder_j2",
            EmailLog.status.in_(["sent", "simulated"]),
            Order.status == "confirmed",
        )
        .scalar()
        or 0
    )

    start_date_str = (
        event.start_date.strftime("%d/%m/%Y %H:%M")
        if event.start_date
        else "Date inconnue"
    )

    return ReminderStatusResponse(
        event_id=event.id,
        event_slug=event.slug,
        event_title=event.title,
        start_date=start_date_str,
        days_until_event=windows["days_until_event"],
        j7_eligible=windows["j7_eligible"],
        j7_sent_count=j7_sent,
        j2_eligible=windows["j2_eligible"],
        j2_sent_count=j2_sent,
        total_confirmed_orders=total_confirmed,
        total_confirmed_with_email=total_with_email,
    )


def send_order_reminder_email(
    order: Union[Order, uuid.UUID],
    event: Union[Event, uuid.UUID],
    reminder_type: str,
    force: bool = False,
    db: Optional[Session] = None,
) -> Optional[EmailLog]:
    """
    Send an idempotent J-7 or J-2 reminder email for an order.
    """
    session, should_close = email_service.get_session(db)
    try:
        order_obj, event_obj = email_service._resolve_order_and_event(session, order, event)
        if not order_obj or not event_obj:
            logger.warning("Could not resolve order or event for reminder email")
            return None

        if order_obj.status != "confirmed":
            logger.info(
                "Skipping reminder for order %s (status is '%s', not 'confirmed')",
                order_obj.id,
                order_obj.status,
            )
            return None

        if not order_obj.email or "@" not in order_obj.email:
            logger.info("Order %s has no valid email address; skipping reminder", order_obj.id)
            return None

        normalized_type = reminder_type.lower().strip()
        if normalized_type not in ("j7", "j2"):
            raise ValueError(f"Type de rappel invalide '{reminder_type}' : attendu 'j7' ou 'j2'")

        log_email_type = f"reminder_{normalized_type}"
        template_name = f"reminder_{normalized_type}"

        # Idempotency check unless explicitly forced
        if not force:
            existing = (
                session.query(EmailLog)
                .filter(
                    EmailLog.order_id == order_obj.id,
                    EmailLog.email_type == log_email_type,
                    EmailLog.status.in_(["sent", "simulated"]),
                )
                .first()
            )
            if existing:
                logger.info(
                    "Reminder %s already delivered to order %s (log_id=%s); skipping duplicate",
                    log_email_type,
                    order_obj.id,
                    existing.id,
                )
                return existing

        # Extract spots and linear meters
        spot_labels = [
            item.spot.label
            for item in order_obj.items
            if item.spot and item.spot.label
        ]
        total_meters = sum(
            (item.spot.linear_meters or 0.0)
            for item in order_obj.items
            if item.spot and item.spot.linear_meters
        )

        event_date_str = email_service.format_event_date(event_obj.start_date)

        setup_start = event_obj.setup_start_time or "06:00"
        setup_end = event_obj.setup_end_time or "08:00"
        public_start = event_obj.public_start_time or "08:00"
        public_end = event_obj.public_end_time or "18:00"

        base_url = (settings.FRONTEND_BASE_URL or "http://localhost:5173").rstrip("/")
        confirmation_url = f"{base_url}/e/{event_obj.slug}/confirmation/{order_obj.id}?token={order_obj.access_token}"

        context = {
            "event_title": event_obj.title,
            "event_date": event_date_str,
            "event_location": event_obj.location_address or "Adresse communiquée sur le plan",
            "organizer_email": event_obj.organizer_email or settings.EMAILS_FROM_EMAIL or "contact@gvg.local",
            "first_name": order_obj.first_name,
            "last_name": order_obj.last_name,
            "order_number": order_obj.order_number,
            "spot_labels": spot_labels,
            "total_linear_meters": f"{total_meters:.1f}",
            "setup_hours": f"{setup_start} - {setup_end}",
            "public_hours": f"{public_start} - {public_end}",
            "setup_start_time": setup_start,
            "setup_end_time": setup_end,
            "confirmation_url": confirmation_url,
        }

        if normalized_type == "j7":
            subject = f"[Rappel J-7] Votre vide-grenier approche : préparez votre arrivée - {event_obj.title}"
        else:
            subject = f"[Rappel J-2] Dernières consignes Jour J - {event_obj.title}"

        try:
            html_content, text_content = email_service.render_template(template_name, context)
        except Exception as e:
            logger.error("Failed to render %s email template: %s", template_name, e)
            return None

        return email_service.send_raw_email(
            recipient=order_obj.email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=log_email_type,
            order_id=order_obj.id,
            event_id=event_obj.id,
            db=session,
        )
    finally:
        if should_close:
            session.close()


def process_event_reminders(
    event_id: uuid.UUID,
    reminder_type: Optional[str] = None,
    force: bool = False,
    db: Optional[Session] = None,
    now: Optional[datetime] = None,
) -> ReminderTriggerResponse:
    """
    Process reminder emails for all confirmed orders of a specific event.
    """
    session, should_close = email_service.get_session(db)
    try:
        event = session.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise ValueError(f"Événement introuvable pour id={event_id}")

        if event.status != "published":
            raise ValueError(
                f"Impossible d'envoyer des rappels pour un événement au statut '{event.status}'. "
                f"Seuls les événements publiés ('published') sont éligibles."
            )

        windows = calculate_event_reminder_windows(event, now)

        # Determine reminder types to send
        types_to_send: List[str] = []
        if reminder_type:
            nt = reminder_type.lower().strip()
            if nt not in ("j7", "j2"):
                raise ValueError(f"Type de rappel invalide '{reminder_type}' : attendu 'j7' ou 'j2'")
            types_to_send.append(nt)
        else:
            if windows["j7_eligible"]:
                types_to_send.append("j7")
            elif windows["j2_eligible"]:
                types_to_send.append("j2")

        if not types_to_send:
            return ReminderTriggerResponse(
                event_id=event.id,
                event_title=event.title,
                reminder_type="none",
                orders_processed=0,
                reminders_sent=0,
                reminders_skipped=0,
                orders_without_email=0,
                errors=["Aucune fenêtre de rappel active (J-7 ou J-2) pour cet événement."],
            )

        confirmed_orders = (
            session.query(Order)
            .options(selectinload(Order.items).selectinload(BookingItem.spot))
            .filter(Order.event_id == event.id, Order.status == "confirmed")
            .all()
        )

        sent_count = 0
        skipped_count = 0
        no_email_count = 0
        errors: List[str] = []

        for order in confirmed_orders:
            if not order.email or "@" not in order.email:
                no_email_count += 1
                continue

            for t in types_to_send:
                try:
                    # Check idempotence in advance for accurate counting
                    log_type = f"reminder_{t}"
                    if not force:
                        existing = (
                            session.query(EmailLog)
                            .filter(
                                EmailLog.order_id == order.id,
                                EmailLog.email_type == log_type,
                                EmailLog.status.in_(["sent", "simulated"]),
                            )
                            .first()
                        )
                        if existing:
                            skipped_count += 1
                            continue

                    log = send_order_reminder_email(
                        order=order,
                        event=event,
                        reminder_type=t,
                        force=force,
                        db=session,
                    )
                    if log and log.status in ("sent", "simulated"):
                        sent_count += 1
                    elif log and log.status == "failed":
                        errors.append(f"Échec envoi à {order.email}: {log.error_message}")
                except Exception as ex:
                    errors.append(f"Erreur pour commande {order.order_number}: {str(ex)}")
                    logger.exception("Error processing reminder for order %s", order.id)

        label_type = "+".join(types_to_send)
        return ReminderTriggerResponse(
            event_id=event.id,
            event_title=event.title,
            reminder_type=label_type,
            orders_processed=len(confirmed_orders),
            reminders_sent=sent_count,
            reminders_skipped=skipped_count,
            orders_without_email=no_email_count,
            errors=errors,
        )
    finally:
        if should_close:
            session.close()


def process_all_scheduled_reminders(
    db: Optional[Session] = None,
    now: Optional[datetime] = None,
) -> SystemRemindersRunResponse:
    """
    Cron / background task runner: scan all published upcoming events
    and process eligible J-7 and J-2 reminders.
    """
    session, should_close = email_service.get_session(db)
    try:
        current_time = _ensure_utc(now)
        # Scan events occurring within the next 8 days
        max_horizon = current_time + timedelta(days=8)

        upcoming_events = (
            session.query(Event)
            .filter(
                Event.status == "published",
                Event.start_date >= current_time,
                Event.start_date <= max_horizon,
            )
            .all()
        )

        total_sent = 0
        total_skipped = 0
        reports: List[ReminderTriggerResponse] = []

        for ev in upcoming_events:
            try:
                report = process_event_reminders(
                    event_id=ev.id,
                    reminder_type=None,
                    force=False,
                    db=session,
                    now=current_time,
                )
                if report.reminders_sent > 0 or report.reminders_skipped > 0 or report.errors:
                    reports.append(report)
                    total_sent += report.reminders_sent
                    total_skipped += report.reminders_skipped
            except Exception as ev_err:
                logger.error("Error processing event %s reminders: %s", ev.id, ev_err)

        return SystemRemindersRunResponse(
            events_evaluated=len(upcoming_events),
            total_reminders_sent=total_sent,
            total_reminders_skipped=total_skipped,
            reports=reports,
        )
    finally:
        if should_close:
            session.close()
