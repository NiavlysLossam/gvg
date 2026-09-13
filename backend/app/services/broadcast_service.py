import re
import uuid
import html
import logging
from typing import Optional, List, Dict, Any, Tuple, Union
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.event import Event
from app.models.order import Order, BookingItem
from app.schemas.broadcast import (
    BroadcastPreviewRequest,
    BroadcastPreviewResponse,
    BroadcastSendRequest,
    BroadcastSendResponse,
)
from app.services.email_service import (
    get_session,
    send_raw_email,
    render_template,
    format_event_date,
    get_order_spot_labels,
    get_order_linear_meters,
)

logger = logging.getLogger(__name__)

TAG_REGEX = re.compile(r"\{\{\s*([\w\.\-]+)\s*\}\}|\{\s*([\w\.\-]+)\s*\}", re.UNICODE)


def sanitize_subject(text: str) -> str:
    """Replace newlines and carriage returns with a single space."""
    if not text:
        return ""
    return re.sub(r"[\r\n]+", " ", text).strip()


def format_message_body_html(text: str) -> str:
    """
    Safely format message text into HTML paragraphs and linebreaks for responsive emails.
    Protects against XSS while preserving multi-line whitespace.
    """
    if not text:
        return ""
    escaped = html.escape(text)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", escaped) if p.strip()]
    if not paragraphs:
        return ""
    formatted_p = []
    for p in paragraphs:
        p_with_breaks = p.replace("\n", "<br/>")
        formatted_p.append(f'<p style="margin: 0 0 14px 0; line-height: 1.6;">{p_with_breaks}</p>')
    return "".join(formatted_p)


def render_dynamic_tags(text: str, context: Dict[str, Any]) -> str:
    """
    Interpolates dynamic tags like {{exposant.prenom}} or {exposant.prenom}.
    Unknown variables are cleanly replaced with an empty string without raising KeyError.
    Malformed braces or orphan brackets remain untouched.
    """
    if not text:
        return ""

    def _replace_match(match: re.Match) -> str:
        key = match.group(1) or match.group(2)
        if not key:
            return ""
        clean_key = key.strip().lower()
        if clean_key in context:
            val = context[clean_key]
            return "" if val is None else str(val)
        return ""

    return TAG_REGEX.sub(_replace_match, text)


def build_order_context(order: Optional[Order], event: Event) -> Dict[str, Any]:
    """
    Build dictionary of interpolation variables from an Order and an Event.
    If order is None, populates realistic sample data.
    """
    event_title = event.title or "Vide-Greniers"
    event_date = format_event_date(event.start_date)
    frontend_base = (getattr(settings, "FRONTEND_BASE_URL", None) or "http://localhost:5173").rstrip("/")

    if order is not None:
        first_name = order.first_name or ""
        last_name = order.last_name or ""
        order_number = order.order_number or ""
        spot_labels = get_order_spot_labels(order)
        spots_text = ", ".join(spot_labels) if spot_labels else "Non spécifié"
        linear_meters = get_order_linear_meters(order)
        order_link = f"{frontend_base}/e/{event.slug}/confirmation/{order.id}?token={order.access_token}"
        email = order.email or ""
    else:
        # Realistic sample data when no order exists in event
        first_name = "Monique"
        last_name = "Durand"
        order_number = "GVG-2026-EXMP"
        spot_labels = ["A-12"]
        spots_text = "A-12"
        linear_meters = 2.0
        order_link = f"{frontend_base}/e/{event.slug}"
        email = "monique.durand@example.fr"

    setup_hours = None
    if event.setup_start_time and event.setup_end_time:
        setup_hours = f"{event.setup_start_time} - {event.setup_end_time}"
    elif event.setup_start_time:
        setup_hours = f"Dès {event.setup_start_time}"

    ctx = {
        # Canonical tags specified in Story 4.3 & accented aliases
        "exposant.prenom": first_name,
        "exposant.prénom": first_name,
        "exposant.nom": last_name,
        "commande.numero": order_number,
        "commande.numéro": order_number,
        "commande.emplacements": spots_text,
        "commande.emplacement": spots_text,
        "evenement.titre": event_title,
        "événement.titre": event_title,
        "evenement.date": event_date,
        "événement.date": event_date,
        "commande.lien": order_link,
        # Common aliases & helper keys
        "prenom": first_name,
        "prénom": first_name,
        "nom": last_name,
        "first_name": first_name,
        "last_name": last_name,
        "order_number": order_number,
        "spot_labels": spot_labels,
        "spot_labels_text": spots_text,
        "total_linear_meters": linear_meters,
        "event_title": event_title,
        "event_date": event_date,
        "setup_hours": setup_hours,
        "confirmation_url": order_link,
        "recipient_email": email,
        "organizer_email": event.organizer_email or "",
    }
    return ctx


def _resolve_event(session: Session, event_id_or_slug: Union[str, uuid.UUID]) -> Optional[Event]:
    """Helper to query event by UUID or slug."""
    if isinstance(event_id_or_slug, uuid.UUID):
        return session.query(Event).filter(Event.id == event_id_or_slug).first()

    try:
        val_uuid = uuid.UUID(str(event_id_or_slug))
        ev = session.query(Event).filter(Event.id == val_uuid).first()
        if ev:
            return ev
    except ValueError:
        pass

    return session.query(Event).filter(Event.slug == str(event_id_or_slug)).first()


def generate_broadcast_preview(
    event_id_or_slug: Union[str, uuid.UUID],
    subject: str,
    body: str,
    order_id: Optional[uuid.UUID] = None,
    db: Optional[Session] = None,
) -> BroadcastPreviewResponse:
    """
    Generate instant rendered HTML and plain-text preview using live event data
    and a sample confirmed order (or fallback mock data).
    """
    session, own_session = get_session(db)
    try:
        event = _resolve_event(session, event_id_or_slug)
        if not event:
            raise ValueError("Événement introuvable")

        total_eligible = (
            session.query(Order)
            .filter(
                Order.event_id == event.id,
                Order.status == "confirmed",
                Order.email.isnot(None),
                Order.email != "",
            )
            .count()
        )

        sample_order = None
        if order_id:
            sample_order = (
                session.query(Order)
                .options(joinedload(Order.items).joinedload(BookingItem.spot))
                .filter(Order.id == order_id, Order.event_id == event.id)
                .first()
            )
        if not sample_order:
            sample_order = (
                session.query(Order)
                .options(joinedload(Order.items).joinedload(BookingItem.spot))
                .filter(Order.event_id == event.id, Order.status == "confirmed")
                .order_by(Order.created_at.asc())
                .first()
            )
        if not sample_order:
            sample_order = (
                session.query(Order)
                .options(joinedload(Order.items).joinedload(BookingItem.spot))
                .filter(Order.event_id == event.id)
                .order_by(Order.created_at.asc())
                .first()
            )

        context = build_order_context(sample_order, event)
        interpolated_subject = sanitize_subject(render_dynamic_tags(subject, context))
        interpolated_body = render_dynamic_tags(body, context)

        template_ctx = dict(context)
        template_ctx["email_subject"] = interpolated_subject
        template_ctx["message_body"] = format_message_body_html(interpolated_body)
        html_content, _ = render_template("custom_broadcast", template_ctx)

        text_ctx = dict(context)
        text_ctx["email_subject"] = interpolated_subject
        text_ctx["message_body"] = interpolated_body
        _, text_content = render_template("custom_broadcast", text_ctx)

        return BroadcastPreviewResponse(
            subject=interpolated_subject,
            body_text=text_content,
            body_html=html_content,
            sample_order_number=context["commande.numero"],
            sample_exhibitor_name=f"{context['exposant.prenom']} {context['exposant.nom']}".strip(),
            sample_recipient_email=context.get("recipient_email"),
            sample_spots=context["commande.emplacements"],
            total_eligible_recipients=total_eligible,
        )
    finally:
        if own_session:
            session.close()


def send_broadcast_emails(
    event_id: uuid.UUID,
    payload: Union[BroadcastSendRequest, dict],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Deliver broadcast emails asynchronously with individual tag interpolation.
    Logs every email in email_logs with email_type='custom_broadcast'.
    Never interrupts the batch on individual recipient failure.
    """
    session, own_session = get_session(db)
    try:
        if isinstance(payload, dict):
            payload = BroadcastSendRequest(**payload)

        event = session.query(Event).filter(Event.id == event_id).first()
        if not event:
            logger.error(f"Cannot send broadcast: Event {event_id} not found")
            return {
                "status": "failed",
                "event_id": event_id,
                "total_targeted": 0,
                "sent_count": 0,
                "failed_count": 0,
                "recipients_without_email": 0,
                "errors": ["Événement introuvable"],
            }

        # Case 1: Test send to organizer or specified email
        if payload.is_test:
            recipient = (payload.test_recipient or event.organizer_email or settings.EMAILS_FROM_EMAIL or "").strip()
            if not recipient or "@" not in recipient:
                return {
                    "status": "failed",
                    "event_id": event.id,
                    "total_targeted": 1,
                    "sent_count": 0,
                    "failed_count": 1,
                    "recipients_without_email": 1,
                    "errors": [f"Adresse de test invalide : '{recipient}'"],
                }

            sample_order = (
                session.query(Order)
                .options(joinedload(Order.items).joinedload(BookingItem.spot))
                .filter(Order.event_id == event.id, Order.status == "confirmed")
                .first()
            )
            context = build_order_context(sample_order, event)
            interpolated_subject = sanitize_subject(render_dynamic_tags(payload.subject, context))
            if not interpolated_subject.startswith("[TEST]"):
                test_subject = f"[TEST] {interpolated_subject}"
            else:
                test_subject = interpolated_subject
            interpolated_body = render_dynamic_tags(payload.body, context)

            template_ctx = dict(context)
            template_ctx["email_subject"] = test_subject
            template_ctx["message_body"] = format_message_body_html(interpolated_body)
            html_content, _ = render_template("custom_broadcast", template_ctx)

            text_ctx = dict(context)
            text_ctx["email_subject"] = test_subject
            text_ctx["message_body"] = interpolated_body
            _, text_content = render_template("custom_broadcast", text_ctx)

            log_entry = send_raw_email(
                recipient=recipient,
                subject=test_subject,
                html_content=html_content,
                text_content=text_content,
                event_id=event.id,
                order_id=None,
                email_type="custom_broadcast",
                db=session,
            )

            is_success = log_entry is not None and log_entry.status in ("sent", "simulated")
            return {
                "status": "completed" if is_success else "failed",
                "event_id": event.id,
                "total_targeted": 1,
                "sent_count": 1 if is_success else 0,
                "failed_count": 0 if is_success else 1,
                "recipients_without_email": 0,
                "is_test": True,
                "test_recipient": recipient,
                "errors": [] if is_success else [log_entry.error_message or "Erreur SMTP"] if log_entry else ["Envoi échoué"],
            }

        # Case 2: Nominal broadcast to confirmed exhibitors
        query = (
            session.query(Order)
            .options(joinedload(Order.items).joinedload(BookingItem.spot))
            .filter(Order.event_id == event.id, Order.status == "confirmed")
        )
        if payload.target_audience == "selected":
            selected_ids = payload.selected_order_ids or []
            query = query.filter(Order.id.in_(selected_ids))

        orders = query.all()
        total_targeted = len(orders)
        recipients_without_email = 0
        sent_count = 0
        failed_count = 0
        errors = []

        for order in orders:
            recipient_email = (order.email or "").strip()
            if not recipient_email or "@" not in recipient_email:
                recipients_without_email += 1
                continue

            try:
                order_ctx = build_order_context(order, event)
                subject_rendered = sanitize_subject(render_dynamic_tags(payload.subject, order_ctx))
                body_rendered = render_dynamic_tags(payload.body, order_ctx)

                t_ctx = dict(order_ctx)
                t_ctx["email_subject"] = subject_rendered
                t_ctx["message_body"] = format_message_body_html(body_rendered)
                html_content, _ = render_template("custom_broadcast", t_ctx)

                txt_ctx = dict(order_ctx)
                txt_ctx["email_subject"] = subject_rendered
                txt_ctx["message_body"] = body_rendered
                _, text_content = render_template("custom_broadcast", txt_ctx)

                log_entry = send_raw_email(
                    recipient=recipient_email,
                    subject=subject_rendered,
                    html_content=html_content,
                    text_content=text_content,
                    event_id=event.id,
                    order_id=order.id,
                    email_type="custom_broadcast",
                    db=session,
                )

                if log_entry and log_entry.status in ("sent", "simulated"):
                    sent_count += 1
                else:
                    failed_count += 1
                    err_msg = log_entry.error_message if log_entry else "Erreur d'envoi"
                    errors.append(f"{recipient_email}: {err_msg}")

            except Exception as exc:
                logger.error(f"Error broadcasting to {recipient_email} (order {order.id}): {exc}", exc_info=True)
                failed_count += 1
                errors.append(f"{recipient_email}: {str(exc)}")

        logger.info(
            f"Broadcast completed for event {event.id}: targeted={total_targeted}, sent={sent_count}, failed={failed_count}, no_email={recipients_without_email}"
        )

        return {
            "status": "completed",
            "event_id": event.id,
            "total_targeted": total_targeted,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "recipients_without_email": recipients_without_email,
            "errors": errors,
        }

    finally:
        if own_session:
            session.close()
