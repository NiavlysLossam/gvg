import json
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import stripe
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.event import Event
from app.models.spot import Spot
from app.models.order import Order, BookingItem, generate_order_number, generate_access_token
from app.models.email_log import EmailLog
from app.services import email_service


@pytest.fixture(autouse=True)
def bind_email_service_session(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """
    Ensure email_service background calls and helper functions share the test transaction
    without closing the fixture db_session prematurely.
    """
    monkeypatch.setattr(
        "app.services.email_service.get_session",
        lambda db=None: (db or db_session, False),
    )


SAMPLE_POLY_COORDS = [
    [
        [-1.68, 48.11],
        [-1.67, 48.11],
        [-1.67, 48.12],
        [-1.68, 48.12],
        [-1.68, 48.11],
    ]
]


def create_test_event(client: TestClient, title: str = "Brocante Test Emails") -> dict:
    payload = {
        "title": title,
        "description": "Vide-grenier pour valider l'envoi d'emails",
        "price_per_meter": 5.0,
        "map_type": "geographic",
        "start_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=7, hours=8)).isoformat(),
        "setup_start_time": "06:30",
        "setup_end_time": "08:00",
        "public_start_time": "08:00",
        "public_end_time": "18:00",
        "location_address": "Esplanade Charles de Gaulle, 35000 Rennes",
        "organizer_email": "orga@rennes-videgrenier.fr",
        "status": "published",
    }
    res = client.post("/api/v1/events", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def create_test_spot(client: TestClient, event_id: str, label: str = "E-01", linear_meters: float = 3.0) -> dict:
    payload = {
        "label": label,
        "linear_meters": linear_meters,
        "geometry": {
            "type": "Polygon",
            "coordinates": SAMPLE_POLY_COORDS,
        },
    }
    res = client.post(f"/api/v1/events/{event_id}/spots", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


# ==============================================================================
# 1. TEMPLATE RENDERING TESTS
# ==============================================================================

def test_render_all_templates():
    """Verify that all email templates compile and render without syntax errors."""
    context = {
        "event_title": "Grand Vide-Grenier du Printemps",
        "event_date": "14 juin 2026",
        "event_location": "Place de la Liberté, Brest",
        "organizer_email": "contact@brest-fetes.fr",
        "first_name": "Jean",
        "last_name": "Dupont",
        "order_number": "GVG-2026-TEST01",
        "status": "confirmed",
        "spot_labels": ["A-10", "A-11"],
        "total_linear_meters": 4.0,
        "total_price": "24.00",
        "payment_method": "stripe",
        "offline_reference": None,
        "setup_hours": "06:00 - 08:00",
        "public_hours": "08:00 - 18:00",
        "confirmation_url": "https://gvg.local/e/test/confirmation/123?token=abc",
        "cancellation_url": "https://gvg.local/e/test/annulation/123?token=abc",
        "approved": True,
        "accepted": True,
        "reason": "Motif de test",
        "refund_amount": "24.00",
    }

    templates = [
        "order_confirmation",
        "moderation_decision",
        "cancellation_arbitration",
        "event_cancellation",
    ]

    for tmpl in templates:
        html, txt = email_service.render_template(tmpl, context)
        assert len(html) > 50, f"HTML content too short for {tmpl}"
        assert len(txt) > 20, f"TXT content too short for {tmpl}"
        assert "Jean" in html
        assert "Jean" in txt
        assert "Grand Vide-Grenier du Printemps" in html
        assert "Grand Vide-Grenier du Printemps" in txt
        assert "{{" not in html, f"Unrendered variable in {tmpl}.html"
        assert "{{" not in txt, f"Unrendered variable in {tmpl}.txt"


def test_render_moderation_decision_templates():
    """Test both approved and rejected states for moderation decision template."""
    ctx_approved = {
        "event_title": "Vide-Grenier Centre",
        "first_name": "Marie",
        "last_name": "Curie",
        "order_number": "GVG-2026-MC01",
        "approved": True,
        "spot_labels": ["B-01"],
        "total_price": "15.00",
        "confirmation_url": "https://gvg.local/confirm",
    }
    html, txt = email_service.render_template("moderation_decision", ctx_approved)
    assert "validée" in html.lower() or "validee" in html.lower()
    assert "confirmé" in html.lower() or "confirme" in html.lower()

    ctx_rejected = {
        "event_title": "Vide-Grenier Centre",
        "first_name": "Marie",
        "last_name": "Curie",
        "order_number": "GVG-2026-MC01",
        "approved": False,
        "reason": "Pièce d'identité illisible",
        "spot_labels": ["B-01"],
        "total_price": "15.00",
        "confirmation_url": "https://gvg.local/confirm",
    }
    html_rej, txt_rej = email_service.render_template("moderation_decision", ctx_rejected)
    assert "non retenue" in html_rej.lower() or "n'a pas pu valider" in html_rej.lower()
    assert "illisible" in html_rej
    assert "Pièce d'identité illisible" in txt_rej


# ==============================================================================
# 2. EMAIL SERVICE CORE LOGIC & SIMULATION TESTS
# ==============================================================================

def test_send_raw_email_simulation(db_session: Session):
    """Test send_raw_email in simulated mode (SMTP_HOST is None)."""
    assert settings.SMTP_HOST is None or settings.SMTP_HOST == ""

    log = email_service.send_raw_email(
        recipient="exposant@example.com",
        subject="Test simulation",
        html_content="<p>Test HTML</p>",
        text_content="Test Plain",
        email_type="test",
        db=db_session,
    )

    assert log is not None
    assert log.status == "simulated"
    assert log.recipient == "exposant@example.com"
    assert log.subject == "Test simulation"
    assert log.email_type == "test"
    assert log.error_message is None

    # Check persistence in db
    db_log = db_session.query(EmailLog).filter(EmailLog.id == log.id).first()
    assert db_log is not None
    assert db_log.status == "simulated"


def test_send_raw_email_invalid_recipient(db_session: Session):
    """Test send_raw_email rejects invalid email addresses without throwing exceptions."""
    assert email_service.send_raw_email("", "Subject", "h", "t", db=db_session) is None
    assert email_service.send_raw_email("invalid-email", "Subject", "h", "t", db=db_session) is None
    assert email_service.send_raw_email(None, "Subject", "h", "t", db=db_session) is None


def test_send_raw_email_smtp_failure_handling(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """Test SMTP failure is intercepted, recorded as 'failed', and does not raise an exception."""
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_PORT", 9999)  # unreachable port

    log = email_service.send_raw_email(
        recipient="exposant.fail@example.com",
        subject="Test Failure",
        html_content="<p>Fail</p>",
        text_content="Fail",
        email_type="test_fail",
        db=db_session,
    )

    assert log is not None
    assert log.status == "failed"
    assert log.error_message is not None
    assert log.recipient == "exposant.fail@example.com"


def test_send_order_confirmation_idempotency(db_session: Session, client: TestClient):
    """Test that send_order_confirmation_email sends once and idempotently skips duplicates."""
    ev_data = create_test_event(client, "Vide-Grenier Idempotency")
    event = db_session.query(Event).filter(Event.id == uuid.UUID(ev_data["id"])).first()

    order = Order(
        event_id=event.id,
        order_number=generate_order_number(),
        first_name="Alice",
        last_name="Martin",
        email="alice.martin@example.com",
        phone="0601020304",
        honor_declaration_accepted=True,
        total_price_cents=3000,
        status="confirmed",
        payment_method="stripe",
        access_token=generate_access_token(),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    # First send
    log1 = email_service.send_order_confirmation_email(order=order, event=event, db=db_session)
    assert log1 is not None
    assert log1.status == "simulated"
    assert log1.email_type == "confirmation"

    # Second send: should return the existing log without creating a new record
    log2 = email_service.send_order_confirmation_email(order=order, event=event, db=db_session)
    assert log2 is not None
    assert log2.id == log1.id

    logs_count = db_session.query(EmailLog).filter(EmailLog.order_id == order.id).count()
    assert logs_count == 1


def test_offline_order_without_email_returns_none(db_session: Session, client: TestClient):
    """Exhibitors without email addresses do not generate email logs."""
    ev_data = create_test_event(client, "Vide-Grenier No Email")
    event = db_session.query(Event).filter(Event.id == uuid.UUID(ev_data["id"])).first()

    order = Order(
        event_id=event.id,
        order_number=generate_order_number(),
        first_name="Bob",
        last_name="SansMail",
        email=None,
        phone="0600000000",
        honor_declaration_accepted=True,
        total_price_cents=1000,
        status="confirmed",
        payment_method="cash",
        access_token=generate_access_token(),
    )
    db_session.add(order)
    db_session.commit()

    res = email_service.send_order_confirmation_email(order=order, event=event, db=db_session)
    assert res is None

    logs_count = db_session.query(EmailLog).filter(EmailLog.order_id == order.id).count()
    assert logs_count == 0


# ==============================================================================
# 3. ENDPOINT INTEGRATION TESTS (API TRIGGERS & AUDIT LOGS)
# ==============================================================================

def test_api_manual_booking_triggers_confirmation_email(client: TestClient, db_session: Session):
    """Creating a manual booking with an email triggers an email log."""
    ev = create_test_event(client, "Vide-Grenier Manuel Email")
    spot = create_test_spot(client, ev["id"], "M-01")

    payload = {
        "spot_ids": [spot["id"]],
        "first_name": "Claire",
        "last_name": "Lefebvre",
        "email": "claire.lefebvre@example.com",
        "phone": "0612345678",
        "payment_method": "check",
        "offline_payment_reference": "CHQ-98765",
    }
    res = client.post(f"/api/v1/events/{ev['id']}/orders/manual", json=payload)
    assert res.status_code == 201, res.text
    order_id = res.json()["id"]

    # Check the email audit endpoint
    email_res = client.get(f"/api/v1/events/{ev['id']}/orders/{order_id}/emails")
    assert email_res.status_code == 200, email_res.text
    email_data = email_res.json()
    assert email_data["total"] == 1
    assert email_data["items"][0]["recipient"] == "claire.lefebvre@example.com"
    assert email_data["items"][0]["email_type"] == "confirmation"
    assert email_data["items"][0]["status"] == "simulated"


def test_api_manual_booking_without_email_leaves_zero_logs(client: TestClient, db_session: Session):
    """Creating a manual booking without an email address produces 0 email logs."""
    ev = create_test_event(client, "Vide-Grenier Manuel Sans Email")
    spot = create_test_spot(client, ev["id"], "M-02")

    payload = {
        "spot_ids": [spot["id"]],
        "first_name": "Gérard",
        "last_name": "Espèces",
        "email": None,
        "phone": "0611223344",
        "payment_method": "cash",
    }
    res = client.post(f"/api/v1/events/{ev['id']}/orders/manual", json=payload)
    assert res.status_code == 201, res.text
    order_id = res.json()["id"]

    email_res = client.get(f"/api/v1/events/{ev['id']}/orders/{order_id}/emails")
    assert email_res.status_code == 200
    assert email_res.json()["total"] == 0


def test_api_moderation_decisions_trigger_emails(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """Approving or rejecting a pending_approval order triggers moderation decision emails."""
    ev = create_test_event(client, "Vide-Grenier Moderation Emails")
    event_id = ev["id"]

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_secret_key")
    # Mock Stripe capture and cancel
    monkeypatch.setattr("stripe.PaymentIntent.capture", lambda *args, **kwargs: {"status": "succeeded"})
    monkeypatch.setattr("stripe.PaymentIntent.cancel", lambda *args, **kwargs: {"status": "canceled"})

    # 1. Order for approval
    order_appr = Order(
        event_id=uuid.UUID(event_id),
        order_number=generate_order_number(),
        first_name="Paul",
        last_name="Valide",
        email="paul.valide@example.com",
        phone="0601020304",
        honor_declaration_accepted=True,
        total_price_cents=2000,
        status="pending_approval",
        payment_method="stripe",
        stripe_payment_intent_id="pi_test_appr_123",
        access_token=generate_access_token(),
    )
    # 2. Order for rejection
    order_rej = Order(
        event_id=uuid.UUID(event_id),
        order_number=generate_order_number(),
        first_name="Marc",
        last_name="Refuse",
        email="marc.refuse@example.com",
        phone="0601020305",
        honor_declaration_accepted=True,
        total_price_cents=2000,
        status="pending_approval",
        payment_method="stripe",
        stripe_payment_intent_id="pi_test_rej_123",
        access_token=generate_access_token(),
    )
    db_session.add_all([order_appr, order_rej])
    db_session.commit()
    db_session.refresh(order_appr)
    db_session.refresh(order_rej)

    # Approve
    res_appr = client.post(
        f"/api/v1/events/{event_id}/orders/{order_appr.id}/approve",
        json={"reason": "Dossier conforme"},
    )
    assert res_appr.status_code == 200, res_appr.text

    emails_appr = client.get(f"/api/v1/events/{event_id}/orders/{order_appr.id}/emails").json()
    assert emails_appr["total"] == 1
    assert emails_appr["items"][0]["email_type"] == "moderation_approved"
    assert "validée" in emails_appr["items"][0]["subject"].lower() or "validee" in emails_appr["items"][0]["subject"].lower()

    # Reject
    res_rej = client.post(
        f"/api/v1/events/{event_id}/orders/{order_rej.id}/reject",
        json={"reason": "Dossier incomplet"},
    )
    assert res_rej.status_code == 200, res_rej.text

    emails_rej = client.get(f"/api/v1/events/{event_id}/orders/{order_rej.id}/emails").json()
    assert emails_rej["total"] == 1
    assert emails_rej["items"][0]["email_type"] == "moderation_rejected"
    assert "mise à jour" in emails_rej["items"][0]["subject"].lower() or "mise a jour" in emails_rej["items"][0]["subject"].lower()


def test_api_cancellation_arbitration_triggers_emails(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """Validating refund or rejecting cancellation triggers arbitration emails."""
    ev = create_test_event(client, "Vide-Grenier Arbitrage Emails")
    event_id = ev["id"]

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_secret_key")
    monkeypatch.setattr("stripe.Refund.create", lambda *args, **kwargs: {"id": "re_test_123", "status": "succeeded"})

    # Order for refund validation
    order_ref = Order(
        event_id=uuid.UUID(event_id),
        order_number=generate_order_number(),
        first_name="Sophie",
        last_name="Rembourse",
        email="sophie.rembourse@example.com",
        phone="0699887766",
        honor_declaration_accepted=True,
        total_price_cents=2500,
        status="cancellation_requested",
        payment_method="stripe",
        stripe_payment_intent_id="pi_test_ref_123",
        access_token=generate_access_token(),
    )
    # Order for cancellation rejection
    order_maint = Order(
        event_id=uuid.UUID(event_id),
        order_number=generate_order_number(),
        first_name="Lucas",
        last_name="Maintenu",
        email="lucas.maintenu@example.com",
        phone="0699887755",
        honor_declaration_accepted=True,
        total_price_cents=2500,
        status="cancellation_requested",
        payment_method="stripe",
        stripe_payment_intent_id="pi_test_maint_123",
        access_token=generate_access_token(),
    )
    db_session.add_all([order_ref, order_maint])
    db_session.commit()
    db_session.refresh(order_ref)
    db_session.refresh(order_maint)

    # 1. Refund
    res_refund = client.post(
        f"/api/v1/events/{event_id}/orders/{order_ref.id}/refund",
        json={"reason": "Certificat médical fourni", "amount_cents": 2500},
    )
    assert res_refund.status_code == 200, res_refund.text

    emails_ref = client.get(f"/api/v1/events/{event_id}/orders/{order_ref.id}/emails").json()
    assert emails_ref["total"] == 1
    assert emails_ref["items"][0]["email_type"] == "refund_validated"
    assert "remboursement validé" in emails_ref["items"][0]["subject"].lower() or "remboursement valide" in emails_ref["items"][0]["subject"].lower()

    # 2. Reject cancellation
    res_maint = client.post(
        f"/api/v1/events/{event_id}/orders/{order_maint.id}/reject-cancellation",
        json={"reason": "Délai de rétractation dépassé"},
    )
    assert res_maint.status_code == 200, res_maint.text

    emails_maint = client.get(f"/api/v1/events/{event_id}/orders/{order_maint.id}/emails").json()
    assert emails_maint["total"] == 1
    assert emails_maint["items"][0]["email_type"] == "refund_rejected"
    assert "décision" in emails_maint["items"][0]["subject"].lower() or "decision" in emails_maint["items"][0]["subject"].lower()


def test_api_bulk_event_cancellation_triggers_emails(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """Emergency bulk event cancellation sends email notice to all affected exhibitors."""
    ev = create_test_event(client, "Vide-Grenier Annulation Totale")
    event_id = ev["id"]

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_secret_key")
    monkeypatch.setattr("stripe.Refund.create", lambda *args, **kwargs: {"id": "re_bulk_1", "status": "succeeded"})

    o1 = Order(
        event_id=uuid.UUID(event_id),
        order_number=generate_order_number(),
        first_name="User1",
        last_name="Test",
        email="user1@example.com",
        phone="0600000001",
        honor_declaration_accepted=True,
        total_price_cents=1500,
        status="confirmed",
        payment_method="stripe",
        stripe_payment_intent_id="pi_bulk_1",
        access_token=generate_access_token(),
    )
    o2 = Order(
        event_id=uuid.UUID(event_id),
        order_number=generate_order_number(),
        first_name="User2",
        last_name="Test",
        email="user2@example.com",
        phone="0600000002",
        honor_declaration_accepted=True,
        total_price_cents=1500,
        status="cancellation_requested",
        payment_method="check",
        access_token=generate_access_token(),
    )
    db_session.add_all([o1, o2])
    db_session.commit()
    db_session.refresh(o1)
    db_session.refresh(o2)

    res = client.post(
        f"/api/v1/events/{event_id}/cancel-and-refund-all",
        json={
            "confirmation": "CONFIRMER",
            "reason": "Intempéries majeures (alerte rouge Météo France)",
        },
    )
    assert res.status_code == 200, res.text

    # Verify both received emergency cancellation emails
    e1 = client.get(f"/api/v1/events/{event_id}/orders/{o1.id}/emails").json()
    assert e1["total"] == 1
    assert e1["items"][0]["email_type"] == "event_cancelled"
    assert "URGENT" in e1["items"][0]["subject"]

    e2 = client.get(f"/api/v1/events/{event_id}/orders/{o2.id}/emails").json()
    assert e2["total"] == 1
    assert e2["items"][0]["email_type"] == "event_cancelled"
    assert "URGENT" in e2["items"][0]["subject"]


# ==============================================================================
# 4. WEBHOOK & PUBLIC SYNC EMAIL INTEGRATION TESTS
# ==============================================================================

TEST_WEBHOOK_SECRET = "whsec_test_secret_for_cryptographic_verification"


def _deliver_signed_webhook(client: TestClient, event_payload: dict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    raw_payload = json.dumps(event_payload)
    sig_header = stripe.WebhookSignature.generate_signature_header(
        payload=raw_payload,
        secret=TEST_WEBHOOK_SECRET,
    )
    return client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": sig_header,
        },
    )


def test_webhook_payment_intent_succeeded_triggers_confirmation_email(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Webhook payment_intent.succeeded enqueues order confirmation email."""
    ev = create_test_event(client, "Vide-Grenier Webhook Success")
    spot = create_test_spot(client, ev["id"], "WH-01")

    order = Order(
        event_id=uuid.UUID(ev["id"]),
        order_number=generate_order_number(),
        first_name="Webhook",
        last_name="Success",
        email="wh.success@example.com",
        phone="0611223344",
        honor_declaration_accepted=True,
        total_price_cents=2000,
        status="pending",
        payment_method="stripe",
        stripe_payment_intent_id="pi_wh_success_123",
        access_token=generate_access_token(),
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(BookingItem(order_id=order.id, spot_id=uuid.UUID(spot["id"]), price_cents=2000))
    db_session.commit()

    webhook_event = {
        "id": "evt_test_success_1",
        "object": "event",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_wh_success_123",
                "object": "payment_intent",
                "amount_received": 2000,
                "currency": "eur",
                "status": "succeeded",
                "metadata": {
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                },
            }
        },
    }

    res = _deliver_signed_webhook(client, webhook_event, monkeypatch)
    assert res.status_code == 200, res.text

    emails = client.get(f"/api/v1/events/{ev['id']}/orders/{order.id}/emails").json()
    assert emails["total"] == 1
    assert emails["items"][0]["email_type"] == "confirmation"
    assert emails["items"][0]["recipient"] == "wh.success@example.com"
    assert "Confirmation de votre inscription" in emails["items"][0]["subject"]


def test_webhook_amount_capturable_updated_triggers_pending_confirmation_email(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Webhook payment_intent.amount_capturable_updated enqueues pending approval confirmation email."""
    ev = create_test_event(client, "Vide-Grenier Webhook Hold")
    spot = create_test_spot(client, ev["id"], "WH-02")

    order = Order(
        event_id=uuid.UUID(ev["id"]),
        order_number=generate_order_number(),
        first_name="Webhook",
        last_name="Hold",
        email="wh.hold@example.com",
        phone="0611223344",
        honor_declaration_accepted=True,
        total_price_cents=2000,
        status="pending",
        payment_method="stripe",
        stripe_payment_intent_id="pi_wh_hold_123",
        access_token=generate_access_token(),
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(BookingItem(order_id=order.id, spot_id=uuid.UUID(spot["id"]), price_cents=2000))
    db_session.commit()

    webhook_event = {
        "id": "evt_test_hold_1",
        "object": "event",
        "type": "payment_intent.amount_capturable_updated",
        "data": {
            "object": {
                "id": "pi_wh_hold_123",
                "object": "payment_intent",
                "amount_capturable": 2000,
                "currency": "eur",
                "status": "requires_capture",
                "metadata": {
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                },
            }
        },
    }

    res = _deliver_signed_webhook(client, webhook_event, monkeypatch)
    assert res.status_code == 200, res.text

    emails = client.get(f"/api/v1/events/{ev['id']}/orders/{order.id}/emails").json()
    assert emails["total"] == 1
    assert emails["items"][0]["email_type"] == "confirmation"
    assert "Demande d'inscription enregistrée" in emails["items"][0]["subject"]


def test_webhook_charge_refunded_triggers_arbitration_email(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Webhook charge.refunded enqueues refund arbitration email."""
    ev = create_test_event(client, "Vide-Grenier Webhook Refund")
    spot = create_test_spot(client, ev["id"], "WH-03")

    order = Order(
        event_id=uuid.UUID(ev["id"]),
        order_number=generate_order_number(),
        first_name="Webhook",
        last_name="Refund",
        email="wh.refund@example.com",
        phone="0611223344",
        honor_declaration_accepted=True,
        total_price_cents=2500,
        status="cancellation_requested",
        payment_method="stripe",
        stripe_payment_intent_id="pi_wh_refund_123",
        access_token=generate_access_token(),
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(BookingItem(order_id=order.id, spot_id=uuid.UUID(spot["id"]), price_cents=2500))
    db_session.commit()

    webhook_event = {
        "id": "evt_test_refund_1",
        "object": "event",
        "type": "charge.refunded",
        "data": {
            "object": {
                "id": "ch_wh_refund_123",
                "object": "charge",
                "refunded": True,
                "amount_refunded": 2500,
                "payment_intent": "pi_wh_refund_123",
                "metadata": {
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                },
            }
        },
    }

    res = _deliver_signed_webhook(client, webhook_event, monkeypatch)
    assert res.status_code == 200, res.text

    emails = client.get(f"/api/v1/events/{ev['id']}/orders/{order.id}/emails").json()
    assert emails["total"] == 1
    assert emails["items"][0]["email_type"] == "refund_validated"
    assert "remboursement validé" in emails["items"][0]["subject"].lower() or "remboursement valide" in emails["items"][0]["subject"].lower()


def test_public_order_sync_triggers_confirmation_email(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Polling public get_order triggers confirmation email when synced from Stripe."""
    ev = create_test_event(client, "Vide-Grenier Public Polling Sync")
    spot = create_test_spot(client, ev["id"], "SYNC-01")

    order = Order(
        event_id=uuid.UUID(ev["id"]),
        order_number=generate_order_number(),
        first_name="Sync",
        last_name="Exposant",
        email="sync.exposant@example.com",
        phone="0611223344",
        honor_declaration_accepted=True,
        total_price_cents=1800,
        status="pending",
        payment_method="stripe",
        stripe_payment_intent_id="pi_sync_123",
        access_token=generate_access_token(),
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(BookingItem(order_id=order.id, spot_id=uuid.UUID(spot["id"]), price_cents=1800))
    db_session.commit()

    # Mock stripe.PaymentIntent.retrieve
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_secret_key")
    monkeypatch.setattr(
        "stripe.PaymentIntent.retrieve",
        lambda pi_id: {
            "id": pi_id,
            "status": "succeeded",
            "amount_received": 1800,
            "currency": "eur",
        },
    )

    slug = ev["slug"]
    res = client.get(f"/api/v1/public/events/{slug}/orders/{order.id}?token={order.access_token}")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "confirmed"

    emails = client.get(f"/api/v1/events/{ev['id']}/orders/{order.id}/emails").json()
    assert emails["total"] == 1
    assert emails["items"][0]["email_type"] == "confirmation"
    assert emails["items"][0]["recipient"] == "sync.exposant@example.com"


def test_render_order_confirmation_pending_approval_template():
    """Verify pending_approval confirmation template displays amber badge and pending text."""
    ctx_pending = {
        "event_title": "Grand Marché",
        "first_name": "Julien",
        "last_name": "Attente",
        "order_number": "GVG-2026-ATT01",
        "status": "pending_approval",
        "spot_labels": ["C-01"],
        "total_linear_meters": 2.0,
        "total_price": "10.00",
        "payment_method": "stripe",
        "confirmation_url": "https://gvg.local/confirm/123",
        "cancellation_url": "https://gvg.local/cancel/123",
    }
    html, txt = email_service.render_template("order_confirmation", ctx_pending)
    assert "En attente de validation" in html
    assert "Demande d'inscription enregistrée" in html
    assert "pré-autorisation bancaire" in html
    assert "En attente de validation" in txt or "validation" in txt.lower()

