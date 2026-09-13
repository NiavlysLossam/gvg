import os
import uuid
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.event import Event
from app.models.order import Order, BookingItem
from app.models.email_log import EmailLog

logger = logging.getLogger(__name__)

# Initialize Jinja2 environment pointing to email templates directory
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def format_event_date(dt: Optional[datetime]) -> str:
    """Format a datetime into a clean French date string, e.g. '14 juin 2026'."""
    if not dt:
        return ""
    months_fr = [
        "", "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"
    ]
    return f"{dt.day} {months_fr[dt.month]} {dt.year}"


def render_template(template_name: str, context: Dict[str, Any]) -> Tuple[str, str]:
    """
    Render both HTML and Plain-Text templates for a given template base name.
    Expects '{template_name}.html' and '{template_name}.txt' in templates/emails/.
    """
    html_template = jinja_env.get_template(f"{template_name}.html")
    txt_template = jinja_env.get_template(f"{template_name}.txt")

    html_content = html_template.render(**context)
    text_content = txt_template.render(**context)
    return html_content, text_content


def get_session(db: Optional[Session] = None) -> Tuple[Session, bool]:
    """
    Return a database session and a boolean indicating whether the caller
    owns the session (True means it must close it in finally).
    """
    if db is not None:
        return db, False
    return SessionLocal(), True


def send_raw_email(
    recipient: str,
    subject: str,
    html_content: str,
    text_content: str,
    event_id: Optional[uuid.UUID] = None,
    order_id: Optional[uuid.UUID] = None,
    email_type: str = "general",
    db: Optional[Session] = None,
) -> Optional[EmailLog]:
    """
    Core function to deliver an email via SMTP or simulate delivery in development.
    Persists an EmailLog record in the database for traceability and audit.
    Never raises exceptions to the caller.
    """
    recipient = (recipient or "").strip()
    if not recipient or "@" not in recipient:
        logger.warning(f"Email sending skipped: invalid recipient '{recipient}'")
        return None

    # Guarantee subject length safety for VARCHAR(500)
    subject_safe = (subject or "")[:490]

    session, own_session = get_session(db)

    status = "sent"
    error_message = None

    try:
        if not settings.SMTP_HOST:
            # Simulated mode (development / tests)
            status = "simulated"
            logger.info(
                f"[EMAIL SIMULATION] Type: {email_type} | To: {recipient} | Subject: '{subject_safe}'"
            )
        else:
            # Actual SMTP transmission with RFC 5322 UTF-8 compliant headers
            msg = MIMEMultipart("alternative")
            msg["Subject"] = Header(subject_safe, "utf-8")
            from_name = str(Header(settings.EMAILS_FROM_NAME or "GVG", "utf-8"))
            msg["From"] = formataddr((from_name, settings.EMAILS_FROM_EMAIL))
            msg["To"] = recipient

            part_text = MIMEText(text_content, "plain", "utf-8")
            part_html = MIMEText(html_content, "html", "utf-8")
            msg.attach(part_text)
            msg.attach(part_html)

            server = None
            try:
                if settings.SMTP_SSL:
                    server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
                else:
                    server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
                    if settings.SMTP_TLS:
                        server.starttls()

                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

                server.sendmail(settings.EMAILS_FROM_EMAIL, [recipient], msg.as_string())
                logger.info(f"Email delivered via SMTP to {recipient} ({email_type})")
            finally:
                if server is not None:
                    try:
                        server.quit()
                    except Exception:
                        pass

    except Exception as exc:
        status = "failed"
        error_message = str(exc)
        logger.error(f"Failed to send email to {recipient} ({email_type}): {exc}", exc_info=True)

    log_entry = None
    try:
        log_entry = EmailLog(
            event_id=event_id,
            order_id=order_id,
            recipient=recipient,
            email_type=email_type,
            subject=subject_safe,
            status=status,
            error_message=error_message,
        )
        session.add(log_entry)
        session.commit()
        session.refresh(log_entry)
    except Exception as db_exc:
        session.rollback()
        logger.error(f"Failed to persist EmailLog to database: {db_exc}")
    finally:
        if own_session:
            session.close()

    return log_entry


def _resolve_order_and_event(
    session: Session,
    order: Union[Order, uuid.UUID],
    event: Union[Event, uuid.UUID],
) -> Tuple[Optional[Order], Optional[Event]]:
    """Helper to safely reload Order and Event within session using IDs."""
    order_id = order.id if isinstance(order, Order) else (uuid.UUID(str(order)) if isinstance(order, (str, uuid.UUID)) else order)
    event_id = event.id if isinstance(event, Event) else (uuid.UUID(str(event)) if isinstance(event, (str, uuid.UUID)) else event)

    local_order = (
        session.query(Order)
        .options(joinedload(Order.items).joinedload(BookingItem.spot))
        .filter(Order.id == order_id)
        .first()
    ) if order_id else None

    local_event = (
        session.query(Event).filter(Event.id == event_id).first()
    ) if event_id else None

    return local_order, local_event


def get_order_spot_labels(order: Order) -> List[str]:
    """Helper to extract spot labels from order items."""
    labels = []
    for item in order.items:
        if item.spot and item.spot.label:
            labels.append(item.spot.label)
        elif item.spot_id:
            labels.append(str(item.spot_id)[:8])
    return labels


def get_order_linear_meters(order: Order) -> float:
    """Helper to calculate total linear meters for an order."""
    total = 0.0
    for item in order.items:
        if item.spot and item.spot.linear_meters:
            total += float(item.spot.linear_meters)
    return round(total, 1)


def send_order_confirmation_email(
    order: Union[Order, uuid.UUID],
    event: Union[Event, uuid.UUID],
    db: Optional[Session] = None,
) -> Optional[EmailLog]:
    """
    Send order confirmation or submission acknowledgement email to the exhibitor.
    Safely accepts either ORM objects or scalar IDs.
    """
    session, own_session = get_session(db)

    try:
        local_order, local_event = _resolve_order_and_event(session, order, event)
        if not local_order or not local_event or not local_order.email:
            return None

        # Idempotency check: avoid duplicate confirmation emails
        existing = (
            session.query(EmailLog)
            .filter(
                EmailLog.order_id == local_order.id,
                EmailLog.email_type == "confirmation",
                EmailLog.status.in_(["sent", "simulated"]),
            )
            .first()
        )
        if existing:
            logger.info(
                f"Confirmation email already sent for order {local_order.id}; skipping duplicate."
            )
            return existing

        spot_labels = get_order_spot_labels(local_order)
        total_meters = get_order_linear_meters(local_order)
        total_price = f"{local_order.total_price_cents / 100.0:.2f}"
        event_date = format_event_date(local_event.start_date)

        setup_hours = (
            f"{local_event.setup_start_time} - {local_event.setup_end_time}"
            if local_event.setup_start_time and local_event.setup_end_time
            else None
        )
        public_hours = (
            f"{local_event.public_start_time} - {local_event.public_end_time}"
            if local_event.public_start_time and local_event.public_end_time
            else None
        )

        base_url = settings.FRONTEND_BASE_URL.rstrip("/")
        confirmation_url = f"{base_url}/e/{local_event.slug}/confirmation/{local_order.id}?token={local_order.access_token}"
        cancellation_url = f"{base_url}/e/{local_event.slug}/annulation/{local_order.id}?token={local_order.access_token}"

        is_pending = local_order.status == "pending_approval"
        subject = (
            f"Demande d'inscription enregistrée - {local_event.title}"
            if is_pending
            else f"Confirmation de votre inscription - {local_event.title}"
        )

        context = {
            "event_title": local_event.title,
            "event_date": event_date,
            "event_location": local_event.location_address or "Consulter le plan",
            "organizer_email": local_event.organizer_email,
            "first_name": local_order.first_name,
            "last_name": local_order.last_name,
            "order_number": local_order.order_number,
            "status": local_order.status,
            "spot_labels": spot_labels,
            "total_linear_meters": total_meters,
            "total_price": total_price,
            "payment_method": local_order.payment_method,
            "offline_reference": local_order.offline_payment_reference,
            "setup_hours": setup_hours,
            "public_hours": public_hours,
            "confirmation_url": confirmation_url,
            "cancellation_url": cancellation_url,
        }

        try:
            html, txt = render_template("order_confirmation", context)
        except Exception as render_exc:
            logger.error(f"Template rendering error for order confirmation: {render_exc}", exc_info=True)
            return send_raw_email(
                recipient=local_order.email,
                subject=subject,
                html_content="",
                text_content="",
                event_id=local_event.id,
                order_id=local_order.id,
                email_type="confirmation",
                db=session,
            )

        return send_raw_email(
            recipient=local_order.email,
            subject=subject,
            html_content=html,
            text_content=txt,
            event_id=local_event.id,
            order_id=local_order.id,
            email_type="confirmation",
            db=session,
        )
    finally:
        if own_session:
            session.close()


def send_moderation_decision_email(
    order: Union[Order, uuid.UUID],
    event: Union[Event, uuid.UUID],
    approved: bool,
    reason: Optional[str] = None,
    db: Optional[Session] = None,
) -> Optional[EmailLog]:
    """
    Send moderation decision notification (approved or rejected) to the exhibitor.
    Safely accepts either ORM objects or scalar IDs.
    """
    session, own_session = get_session(db)

    try:
        local_order, local_event = _resolve_order_and_event(session, order, event)
        if not local_order or not local_event or not local_order.email:
            return None

        # Idempotency check: avoid duplicate moderation decision emails
        email_type = "moderation_approved" if approved else "moderation_rejected"
        existing = (
            session.query(EmailLog)
            .filter(
                EmailLog.order_id == local_order.id,
                EmailLog.email_type.in_(["moderation_approved", "moderation_rejected"]),
                EmailLog.status.in_(["sent", "simulated"]),
            )
            .first()
        )
        if existing:
            logger.info(
                f"Moderation decision email already recorded for order {local_order.id}; skipping duplicate."
            )
            return existing

        spot_labels = get_order_spot_labels(local_order)
        total_price = f"{local_order.total_price_cents / 100.0:.2f}"
        event_date = format_event_date(local_event.start_date)

        setup_hours = (
            f"{local_event.setup_start_time} - {local_event.setup_end_time}"
            if local_event.setup_start_time and local_event.setup_end_time
            else None
        )

        base_url = settings.FRONTEND_BASE_URL.rstrip("/")
        confirmation_url = f"{base_url}/e/{local_event.slug}/confirmation/{local_order.id}?token={local_order.access_token}"
        cancellation_url = f"{base_url}/e/{local_event.slug}/annulation/{local_order.id}?token={local_order.access_token}"

        subject = (
            f"Votre inscription a été validée ! - {local_event.title}"
            if approved
            else f"Mise à jour concernant votre inscription - {local_event.title}"
        )

        context = {
            "event_title": local_event.title,
            "event_date": event_date,
            "event_location": local_event.location_address or "Consulter le plan",
            "organizer_email": local_event.organizer_email,
            "first_name": local_order.first_name,
            "last_name": local_order.last_name,
            "order_number": local_order.order_number,
            "approved": approved,
            "reason": reason,
            "spot_labels": spot_labels,
            "total_price": total_price,
            "setup_hours": setup_hours,
            "confirmation_url": confirmation_url,
            "cancellation_url": cancellation_url,
        }

        try:
            html, txt = render_template("moderation_decision", context)
        except Exception as render_exc:
            logger.error(f"Template rendering error for moderation decision: {render_exc}", exc_info=True)
            return send_raw_email(
                recipient=local_order.email,
                subject=subject,
                html_content="",
                text_content="",
                event_id=local_event.id,
                order_id=local_order.id,
                email_type=email_type,
                db=session,
            )

        return send_raw_email(
            recipient=local_order.email,
            subject=subject,
            html_content=html,
            text_content=txt,
            event_id=local_event.id,
            order_id=local_order.id,
            email_type=email_type,
            db=session,
        )
    finally:
        if own_session:
            session.close()


def send_cancellation_arbitration_email(
    order: Union[Order, uuid.UUID],
    event: Union[Event, uuid.UUID],
    accepted: bool,
    reason: Optional[str] = None,
    refund_amount: Optional[float] = None,
    db: Optional[Session] = None,
) -> Optional[EmailLog]:
    """
    Send arbitration decision regarding exhibitor cancellation request.
    Safely accepts either ORM objects or scalar IDs.
    """
    session, own_session = get_session(db)

    try:
        local_order, local_event = _resolve_order_and_event(session, order, event)
        if not local_order or not local_event or not local_order.email:
            return None

        # Idempotency check: avoid duplicate arbitration emails
        email_type = "refund_validated" if accepted else "refund_rejected"
        existing = (
            session.query(EmailLog)
            .filter(
                EmailLog.order_id == local_order.id,
                EmailLog.email_type.in_(["refund_validated", "refund_rejected"]),
                EmailLog.status.in_(["sent", "simulated"]),
            )
            .first()
        )
        if existing:
            logger.info(
                f"Cancellation arbitration email already recorded for order {local_order.id}; skipping duplicate."
            )
            return existing

        spot_labels = get_order_spot_labels(local_order)
        total_price = f"{local_order.total_price_cents / 100.0:.2f}"
        amount_str = f"{refund_amount:.2f}" if refund_amount is not None else total_price
        event_date = format_event_date(local_event.start_date)

        base_url = settings.FRONTEND_BASE_URL.rstrip("/")
        confirmation_url = f"{base_url}/e/{local_event.slug}/confirmation/{local_order.id}?token={local_order.access_token}"
        cancellation_url = f"{base_url}/e/{local_event.slug}/annulation/{local_order.id}?token={local_order.access_token}"

        subject = (
            f"Remboursement validé - {local_event.title}"
            if accepted
            else f"Décision concernant votre demande d'annulation - {local_event.title}"
        )

        context = {
            "event_title": local_event.title,
            "event_date": event_date,
            "organizer_email": local_event.organizer_email,
            "first_name": local_order.first_name,
            "last_name": local_order.last_name,
            "order_number": local_order.order_number,
            "accepted": accepted,
            "reason": reason,
            "refund_amount": amount_str,
            "total_price": total_price,
            "payment_method": local_order.payment_method,
            "spot_labels": spot_labels,
            "confirmation_url": confirmation_url,
            "cancellation_url": cancellation_url,
        }

        try:
            html, txt = render_template("cancellation_arbitration", context)
        except Exception as render_exc:
            logger.error(f"Template rendering error for cancellation arbitration: {render_exc}", exc_info=True)
            return send_raw_email(
                recipient=local_order.email,
                subject=subject,
                html_content="",
                text_content="",
                event_id=local_event.id,
                order_id=local_order.id,
                email_type=email_type,
                db=session,
            )

        return send_raw_email(
            recipient=local_order.email,
            subject=subject,
            html_content=html,
            text_content=txt,
            event_id=local_event.id,
            order_id=local_order.id,
            email_type=email_type,
            db=session,
        )
    finally:
        if own_session:
            session.close()


def send_event_cancellation_email(
    order: Union[Order, uuid.UUID],
    event: Union[Event, uuid.UUID],
    reason: Optional[str] = None,
    db: Optional[Session] = None,
) -> Optional[EmailLog]:
    """
    Send emergency event cancellation notice and refund explanation to the exhibitor.
    Safely accepts either ORM objects or scalar IDs.
    """
    session, own_session = get_session(db)

    try:
        local_order, local_event = _resolve_order_and_event(session, order, event)
        if not local_order or not local_event or not local_order.email:
            return None

        # Idempotency check: avoid duplicate event cancellation emails
        existing = (
            session.query(EmailLog)
            .filter(
                EmailLog.order_id == local_order.id,
                EmailLog.email_type == "event_cancelled",
                EmailLog.status.in_(["sent", "simulated"]),
            )
            .first()
        )
        if existing:
            logger.info(
                f"Event cancellation email already recorded for order {local_order.id}; skipping duplicate."
            )
            return existing

        total_price = f"{local_order.total_price_cents / 100.0:.2f}"
        event_date = format_event_date(local_event.start_date)
        spot_labels = get_order_spot_labels(local_order)
        is_pending_approval = (local_order.status == "pending_approval")

        subject = f"URGENT : Annulation du vide-grenier {local_event.title}"

        context = {
            "event_title": local_event.title,
            "event_date": event_date,
            "organizer_email": local_event.organizer_email,
            "first_name": local_order.first_name,
            "last_name": local_order.last_name,
            "order_number": local_order.order_number,
            "reason": reason,
            "total_price": total_price,
            "payment_method": local_order.payment_method,
            "spot_labels": spot_labels,
            "is_pending_approval": is_pending_approval,
        }

        try:
            html, txt = render_template("event_cancellation", context)
        except Exception as render_exc:
            logger.error(f"Template rendering error for event cancellation: {render_exc}", exc_info=True)
            return send_raw_email(
                recipient=local_order.email,
                subject=subject,
                html_content="",
                text_content="",
                event_id=local_event.id,
                order_id=local_order.id,
                email_type="event_cancelled",
                db=session,
            )

        return send_raw_email(
            recipient=local_order.email,
            subject=subject,
            html_content=html,
            text_content=txt,
            event_id=local_event.id,
            order_id=local_order.id,
            email_type="event_cancelled",
            db=session,
        )
    finally:
        if own_session:
            session.close()
