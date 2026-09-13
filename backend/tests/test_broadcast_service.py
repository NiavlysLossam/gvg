import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.event import Event
from app.models.spot import Spot
from app.models.order import Order, BookingItem, generate_order_number, generate_access_token
from app.models.email_log import EmailLog
from app.services import broadcast_service, email_service


@pytest.fixture(autouse=True)
def bind_services_session(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """
    Ensure email_service and broadcast_service share the test database transaction.
    """
    monkeypatch.setattr(
        "app.services.email_service.get_session",
        lambda db=None: (db or db_session, False),
    )
    monkeypatch.setattr(
        "app.services.broadcast_service.get_session",
        lambda db=None: (db or db_session, False),
    )


SAMPLE_POLY = [
    [
        [-1.68, 48.11],
        [-1.67, 48.11],
        [-1.67, 48.12],
        [-1.68, 48.12],
        [-1.68, 48.11],
    ]
]


def create_broadcast_test_event(client: TestClient, title: str = "Brocante Diffusion") -> dict:
    start_dt = datetime.now(timezone.utc) + timedelta(days=5)
    end_dt = start_dt + timedelta(hours=8)
    payload = {
        "title": title,
        "description": "Grand vide-grenier communal",
        "price_per_meter": 5.0,
        "map_type": "geographic",
        "start_date": start_dt.isoformat(),
        "end_date": end_dt.isoformat(),
        "setup_start_time": "06:30",
        "setup_end_time": "08:00",
        "public_start_time": "08:00",
        "public_end_time": "18:00",
        "location_address": "Place de la Liberté, 35000 Rennes",
        "organizer_email": "marc.organisateur@example.fr",
        "status": "published",
    }
    res = client.post("/api/v1/events", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def create_spot(client: TestClient, event_id: str, label: str = "A-01", linear_meters: float = 2.0) -> dict:
    res = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": label,
            "linear_meters": linear_meters,
            "geometry": {
                "type": "Polygon",
                "coordinates": SAMPLE_POLY,
            },
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def create_order_direct(
    db: Session,
    event_id: uuid.UUID,
    first_name: str,
    last_name: str,
    email: Optional[str],
    status: str = "confirmed",
    spots: Optional[list] = None,
) -> Order:
    order = Order(
        event_id=event_id,
        order_number=generate_order_number(),
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone="0611223344",
        street_address="10 Rue Haute",
        postal_code="35000",
        city="Rennes",
        total_price_cents=1600,
        status=status,
        payment_method="stripe",
        access_token=generate_access_token(),
    )
    db.add(order)
    db.flush()

    if spots:
        for sp in spots:
            item = BookingItem(
                order_id=order.id,
                spot_id=sp.id if hasattr(sp, "id") else uuid.UUID(sp["id"]),
                price_cents=800,
            )
            db.add(item)
    db.commit()
    db.refresh(order)
    return order


# ===================================================================
# 1. Unit Tests : Dynamic Tag Interpolation
# ===================================================================

def test_render_dynamic_tags_both_syntaxes():
    """Test both {{tag}} and {tag} syntaxes, with optional whitespace."""
    context = {
        "exposant.prenom": "Jean",
        "exposant.nom": "Dupont",
        "commande.numero": "GVG-2026-9999",
        "commande.emplacements": "A-01, A-02",
        "evenement.titre": "Braderie d'Automne",
        "evenement.date": "20 septembre 2026",
        "commande.lien": "http://localhost:5173/e/braderie/confirmation/123",
    }

    text_double = (
        "Bonjour {{exposant.prenom}} {{ exposant.nom }},\n"
        "Votre stand {{ commande.emplacements }} pour {{evenement.titre}} le {{evenement.date}}.\n"
        "Réf: {{commande.numero}} - Accès: {{commande.lien}}"
    )
    rendered_double = broadcast_service.render_dynamic_tags(text_double, context)
    assert "Bonjour Jean Dupont," in rendered_double
    assert "Votre stand A-01, A-02 pour Braderie d'Automne le 20 septembre 2026." in rendered_double
    assert "Réf: GVG-2026-9999 - Accès: http://localhost:5173/e/braderie/confirmation/123" in rendered_double

    text_single = (
        "Bonjour {exposant.prenom} { exposant.nom }, stand {commande.emplacements} pour {evenement.titre} ({evenement.date})."
    )
    rendered_single = broadcast_service.render_dynamic_tags(text_single, context)
    assert "Bonjour Jean Dupont, stand A-01, A-02 pour Braderie d'Automne (20 septembre 2026)." in rendered_single


def test_render_dynamic_tags_unknown_and_malformed():
    """Unknown tags are replaced with empty string, orphan brackets are untouched."""
    context = {"exposant.prenom": "Marc"}

    text = "Hello {{exposant.prenom}}! Inconnu: {{variable_inconnue}} et {autre_inconnu}. Orphelin: { et { 12, 34 }."
    rendered = broadcast_service.render_dynamic_tags(text, context)
    assert "Hello Marc! Inconnu:  et . Orphelin: { et { 12, 34 }." in rendered


def test_format_message_body_html():
    """Test converting plaintext to sanitized HTML with paragraph tags."""
    raw = "Premier paragraphe.\nLigne 2 du premier.\n\nDeuxième paragraphe avec <script>alert(1)</script>."
    html_out = broadcast_service.format_message_body_html(raw)
    assert "<p style=" in html_out
    assert "Premier paragraphe.<br/>Ligne 2 du premier." in html_out
    assert "&lt;script&gt;" in html_out
    assert "<script>" not in html_out


# ===================================================================
# 2. API Tests : Preview Endpoint
# ===================================================================

def test_preview_broadcast_with_real_order(client: TestClient, db_session: Session):
    ev = create_broadcast_test_event(client, "Vide-Grenier Rennes Centre")
    ev_id = uuid.UUID(ev["id"])

    sp1 = create_spot(client, ev["id"], "B-10", 3.0)
    sp2 = create_spot(client, ev["id"], "B-11", 2.0)

    order = create_order_direct(
        db_session,
        ev_id,
        first_name="Camille",
        last_name="Martin",
        email="camille.martin@example.fr",
        status="confirmed",
        spots=[sp1, sp2],
    )

    req = {
        "subject": "Important : Accès {{commande.emplacements}} pour {{evenement.titre}}",
        "body": "Bonjour {{exposant.prenom}},\nVoici le rappel pour votre réservation {{commande.numero}}.",
        "order_id": str(order.id),
    }

    res = client.post(f"/api/v1/events/{ev['id']}/broadcast/preview", json=req)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["subject"] == "Important : Accès B-10, B-11 pour Vide-Grenier Rennes Centre"
    assert "Bonjour Camille," in data["body_text"]
    assert f"réservation {order.order_number}" in data["body_text"]
    assert "B-10" in data["body_html"]
    assert data["sample_exhibitor_name"] == "Camille Martin"
    assert data["total_eligible_recipients"] == 1


def test_preview_broadcast_with_no_orders_fallback(client: TestClient):
    """If an event has 0 orders, preview falls back to realistic sample data."""
    ev = create_broadcast_test_event(client, "Vide-Grenier Vide")

    req = {
        "subject": "Rappel pour {{exposant.prenom}}",
        "body": "Bonjour {{exposant.prenom}} {{exposant.nom}}, stand {{commande.emplacements}}.",
    }

    res = client.post(f"/api/v1/events/{ev['id']}/broadcast/preview", json=req)
    assert res.status_code == 200, res.text
    data = res.json()

    assert "Monique" in data["subject"]
    assert "Monique Durand" in data["body_text"]
    assert "A-12" in data["body_text"]
    assert data["total_eligible_recipients"] == 0


def test_preview_broadcast_not_found(client: TestClient):
    fake_id = str(uuid.uuid4())
    res = client.post(f"/api/v1/events/{fake_id}/broadcast/preview", json={"subject": "S", "body": "B"})
    assert res.status_code == 404


# ===================================================================
# 3. Tests : Send Broadcast (Test & Nominal)
# ===================================================================

def test_send_broadcast_test_email(client: TestClient, db_session: Session):
    """Test send delivers only to test_recipient without notifying exhibitors."""
    ev = create_broadcast_test_event(client, "Brocante Test Mode")
    ev_id = uuid.UUID(ev["id"])

    # Create real exhibitor
    create_order_direct(
        db_session,
        ev_id,
        first_name="Alice",
        last_name="Exposant",
        email="alice.real@example.fr",
        status="confirmed",
    )

    req = {
        "subject": "Alerte météo pour {{evenement.titre}}",
        "body": "Bonjour {{exposant.prenom}}, prévoyez des bâches.",
        "is_test": True,
        "test_recipient": "marc.organisateur@example.fr",
    }

    # Run synchronously with background=False
    res = client.post(f"/api/v1/events/{ev['id']}/broadcast/send?background=false", json=req)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["is_test"] is True
    assert data["total_targeted"] == 1
    assert data["status"] in ("completed", "simulated")

    # Verify EmailLog: ONLY test_recipient received an email, NOT alice.real@example.fr
    logs = db_session.query(EmailLog).filter(EmailLog.event_id == ev_id).all()
    assert len(logs) == 1
    assert logs[0].recipient == "marc.organisateur@example.fr"
    assert logs[0].email_type == "custom_broadcast"
    assert "[TEST]" in logs[0].subject


def test_send_broadcast_nominal_and_ignores_no_email(client: TestClient, db_session: Session):
    """
    Nominal broadcast targets confirmed orders with valid email.
    Orders with email=None or cancelled are ignored and logged as recipients_without_email.
    """
    ev = create_broadcast_test_event(client, "Brocante Générale")
    ev_id = uuid.UUID(ev["id"])

    sp1 = create_spot(client, ev["id"], "C-01")
    sp2 = create_spot(client, ev["id"], "C-02")
    sp3 = create_spot(client, ev["id"], "C-03")

    # 2 confirmed orders with email
    ord1 = create_order_direct(db_session, ev_id, "Luc", "Besson", "luc@cinema.fr", status="confirmed", spots=[sp1])
    ord2 = create_order_direct(db_session, ev_id, "Sophie", "Marceau", "sophie@cinema.fr", status="confirmed", spots=[sp2])
    # 1 confirmed order WITHOUT email (counter / offline)
    create_order_direct(db_session, ev_id, "Sans", "Mail", None, status="confirmed", spots=[sp3])
    # 1 cancelled order (should be ignored)
    create_order_direct(db_session, ev_id, "Jean", "Dujardin", "jean@cinema.fr", status="cancelled")

    req = {
        "subject": "Consignes d'accès {{evenement.titre}}",
        "body": "Bonjour {{exposant.prenom}}, votre stand est {{commande.emplacements}}.",
        "target_audience": "all_confirmed",
    }

    res = client.post(f"/api/v1/events/{ev['id']}/broadcast/send?background=false", json=req)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total_targeted"] == 3  # 3 confirmed orders
    assert data["recipients_without_email"] == 1  # 1 without email

    # Verify logs
    logs = db_session.query(EmailLog).filter(EmailLog.event_id == ev_id).all()
    recipients = [l.recipient for l in logs]
    assert "luc@cinema.fr" in recipients
    assert "sophie@cinema.fr" in recipients
    assert "jean@cinema.fr" not in recipients
    assert len(logs) == 2
    for l in logs:
        assert l.email_type == "custom_broadcast"
        assert l.status in ("sent", "simulated")


def test_send_broadcast_selected_audience(client: TestClient, db_session: Session):
    """Broadcast targets only the selected orders when target_audience='selected'."""
    ev = create_broadcast_test_event(client, "Brocante Sélection")
    ev_id = uuid.UUID(ev["id"])

    ord1 = create_order_direct(db_session, ev_id, "User1", "Test", "user1@example.fr", status="confirmed")
    ord2 = create_order_direct(db_session, ev_id, "User2", "Test", "user2@example.fr", status="confirmed")

    req = {
        "subject": "Message ciblé",
        "body": "Bonjour {{exposant.prenom}}.",
        "target_audience": "selected",
        "selected_order_ids": [str(ord1.id)],
    }

    res = client.post(f"/api/v1/events/{ev['id']}/broadcast/send?background=false", json=req)
    assert res.status_code == 200
    data = res.json()
    assert data["total_targeted"] == 1

    logs = db_session.query(EmailLog).filter(EmailLog.event_id == ev_id).all()
    assert len(logs) == 1
    assert logs[0].recipient == "user1@example.fr"


def test_send_broadcast_asynchronous_enqueue(client: TestClient, db_session: Session):
    """Default endpoint call uses FastAPI BackgroundTasks and returns 'enqueued' immediately."""
    ev = create_broadcast_test_event(client, "Brocante Async")
    ev_id = uuid.UUID(ev["id"])

    create_order_direct(db_session, ev_id, "Bernard", "Tapie", "bernard@example.fr", status="confirmed")

    req = {
        "subject": "Notification rapide",
        "body": "Bonjour {{exposant.prenom}}.",
    }

    # Default background=True
    res = client.post(f"/api/v1/events/{ev['id']}/broadcast/send", json=req)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "enqueued"
    assert data["total_targeted"] == 1
    assert "en arrière-plan" in data["message"] or "en tâche de fond" in data["message"]

    # Starlette TestClient runs background tasks before returning from client.post
    logs = db_session.query(EmailLog).filter(EmailLog.event_id == ev_id).all()
    assert len(logs) == 1
    assert logs[0].recipient == "bernard@example.fr"
    assert logs[0].email_type == "custom_broadcast"


def test_send_broadcast_resilient_to_partial_failure(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """A failure on one recipient doesn't stop delivery to other recipients."""
    ev = create_broadcast_test_event(client, "Brocante Erreurs")
    ev_id = uuid.UUID(ev["id"])

    ord1 = create_order_direct(db_session, ev_id, "FailUser", "Un", "fail@error.fr", status="confirmed")
    ord2 = create_order_direct(db_session, ev_id, "SuccessUser", "Deux", "ok@success.fr", status="confirmed")

    real_send_raw = email_service.send_raw_email

    def mocked_send_raw(recipient, *args, **kwargs):
        if "fail@error.fr" in recipient:
            log = EmailLog(
                event_id=ev_id,
                order_id=ord1.id,
                recipient=recipient,
                email_type="custom_broadcast",
                subject="Test",
                status="failed",
                error_message="550 Mailbox unavailable",
            )
            db_session.add(log)
            db_session.commit()
            return log
        return real_send_raw(recipient, *args, **kwargs)

    monkeypatch.setattr("app.services.broadcast_service.send_raw_email", mocked_send_raw)

    req = {
        "subject": "Message météo",
        "body": "Bonjour {{exposant.prenom}}.",
    }

    res = client.post(f"/api/v1/events/{ev['id']}/broadcast/send?background=false", json=req)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"

    logs = db_session.query(EmailLog).filter(EmailLog.event_id == ev_id).all()
    assert len(logs) == 2
    failed_log = next(l for l in logs if l.recipient == "fail@error.fr")
    success_log = next(l for l in logs if l.recipient == "ok@success.fr")
    assert failed_log.status == "failed"
    assert success_log.status in ("sent", "simulated")


def test_render_dynamic_tags_edge_cases():
    """Verify edge cases: empty strings, {{{triple}}}, {{}}, orphan braces."""
    context = {"exposant.prenom": "Pierre", "foo": "bar"}

    assert broadcast_service.render_dynamic_tags("", context) == ""
    assert broadcast_service.render_dynamic_tags(None, context) == ""
    assert broadcast_service.render_dynamic_tags("{{}}", context) == "{{}}"
    assert broadcast_service.render_dynamic_tags("{{{foo}}}", context) == "{bar}"
    assert broadcast_service.render_dynamic_tags("{ orphelin sans fermeture", context) == "{ orphelin sans fermeture"
    assert broadcast_service.render_dynamic_tags("fermeture } orpheline", context) == "fermeture } orpheline"


def test_send_broadcast_invalid_test_email(client: TestClient):
    """Test send with an invalid email address in test mode returns failed status cleanly."""
    ev = create_broadcast_test_event(client, "Brocante Test Invalide")

    req = {
        "subject": "Test Sujet",
        "body": "Test Corps",
        "is_test": True,
        "test_recipient": "not-an-email",
    }
    res = client.post(f"/api/v1/events/{ev['id']}/broadcast/send?background=false", json=req)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "failed"
    assert data["recipients_without_email"] == 1


def test_send_broadcast_event_not_found(client: TestClient):
    fake_id = str(uuid.uuid4())
    req = {
        "subject": "Test Sujet",
        "body": "Test Corps",
    }
    res = client.post(f"/api/v1/events/{fake_id}/broadcast/send", json=req)
    assert res.status_code == 404


def test_preview_broadcast_specific_order_id(client: TestClient, db_session: Session):
    """When order_id is explicitly provided, preview uses that specific order even among multiple."""
    ev = create_broadcast_test_event(client, "Brocante Multi Orders")
    ev_id = uuid.UUID(ev["id"])

    ord1 = create_order_direct(db_session, ev_id, "Alice", "First", "alice@example.fr", status="confirmed")
    ord2 = create_order_direct(db_session, ev_id, "Bob", "Second", "bob@example.fr", status="confirmed")

    req = {
        "subject": "Bonjour {{exposant.prenom}}",
        "body": "Cher(e) {{exposant.prenom}} {{exposant.nom}}",
        "order_id": str(ord2.id),
    }
    res = client.post(f"/api/v1/events/{ev['id']}/broadcast/preview", json=req)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["subject"] == "Bonjour Bob"
    assert "Cher(e) Bob Second" in data["body_text"]
    assert data["sample_exhibitor_name"] == "Bob Second"
    assert data["total_eligible_recipients"] == 2


def test_send_broadcast_empty_selected_order_ids(client: TestClient, db_session: Session):
    """Broadcasting with target_audience='selected' and empty list returns 400 and sends 0 emails."""
    ev = create_broadcast_test_event(client, "Brocante Empty Selection")
    ev_id = uuid.UUID(ev["id"])

    create_order_direct(db_session, ev_id, "Test", "User", "test@example.fr", status="confirmed")

    req = {
        "subject": "Alerte sélection",
        "body": "Message",
        "target_audience": "selected",
        "selected_order_ids": [],
    }
    res = client.post(f"/api/v1/events/{ev['id']}/broadcast/send?background=false", json=req)
    assert res.status_code == 400
    assert "Aucune commande sélectionnée" in res.json()["detail"]

    logs = db_session.query(EmailLog).filter(EmailLog.event_id == ev_id).all()
    assert len(logs) == 0


def test_broadcast_endpoints_reject_cancelled_event(client: TestClient, db_session: Session):
    """Preview and send endpoints reject cancelled events with HTTP 400."""
    ev = create_broadcast_test_event(client, "Brocante Annulée")
    ev_id = uuid.UUID(ev["id"])

    event_record = db_session.query(Event).filter(Event.id == ev_id).first()
    event_record.status = "cancelled"
    db_session.commit()

    req_preview = {"subject": "Test", "body": "Corps"}
    res_prev = client.post(f"/api/v1/events/{ev['id']}/broadcast/preview", json=req_preview)
    assert res_prev.status_code == 400
    assert "annulé" in res_prev.json()["detail"]

    req_send = {"subject": "Test", "body": "Corps"}
    res_send = client.post(f"/api/v1/events/{ev['id']}/broadcast/send", json=req_send)
    assert res_send.status_code == 400
    assert "annulé" in res_send.json()["detail"]

