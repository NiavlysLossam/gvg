import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import stripe

from app.core.config import settings
from app.models.event import Event
from app.models.spot import Spot
from app.models.order import Order, BookingItem
from app.schemas.spot import geojson_to_wkt_polygon

SAMPLE_POLY_COORDS = [
    [
        [-1.68, 48.11],
        [-1.67, 48.11],
        [-1.67, 48.12],
        [-1.68, 48.12],
        [-1.68, 48.11],
    ]
]

TEST_WEBHOOK_SECRET = "whsec_test_secret_for_cryptographic_verification"


def create_sample_event(client: TestClient, title: str = "Brocante du Village") -> dict:
    payload = {
        "title": title,
        "description": "Flea market description",
        "price_per_meter": 5.0,
        "map_type": "geographic",
        "start_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=7, hours=10)).isoformat(),
        "setup_start_time": "06:00",
        "setup_end_time": "08:00",
        "public_start_time": "08:00",
        "public_end_time": "18:00",
        "location_address": "Place de l'Église, 35000 Rennes",
        "organizer_email": "contact@brocante.fr",
        "status": "published",
    }
    res = client.post("/api/v1/events", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def create_sample_spot(
    client: TestClient,
    event_id: str,
    label: str = "A-01",
    linear_meters: float = 2.0,
) -> dict:
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


def setup_order_fixture(client: TestClient, session_token: str = "session-monique-stripe-42") -> dict:
    """Helper to create an event, 2 spots, lock them, and submit a guest order."""
    ev = create_sample_event(client, title=f"Vide-Grenier {uuid.uuid4().hex[:6]}")
    slug = ev["slug"]
    s1 = create_sample_spot(client, ev["id"], label="A-01", linear_meters=2.0)
    s2 = create_sample_spot(client, ev["id"], label="A-02", linear_meters=3.0)

    # Lock both spots
    lock1 = client.post(
        f"/api/v1/public/events/{slug}/spots/{s1['id']}/lock",
        headers={"X-Session-Token": session_token},
        json={"session_token": session_token},
    )
    assert lock1.status_code == 200, lock1.text

    lock2 = client.post(
        f"/api/v1/public/events/{slug}/spots/{s2['id']}/lock",
        headers={"X-Session-Token": session_token},
        json={"session_token": session_token},
    )
    assert lock2.status_code == 200, lock2.text

    # Create guest order
    order_payload = {
        "session_token": session_token,
        "first_name": "Monique",
        "last_name": "Dubois",
        "email": "monique.dubois@test.fr",
        "phone": "0612345678",
        "street_address": "12 rue de la Brocante",
        "postal_code": "35000",
        "city": "Rennes",
        "honor_declaration_accepted": True,
    }
    res_order = client.post(f"/api/v1/public/events/{slug}/orders", json=order_payload)
    assert res_order.status_code == 201, res_order.text
    return {
        "event": ev,
        "slug": slug,
        "spots": [s1, s2],
        "order": res_order.json(),
    }


def test_create_payment_intent_nominal(client: TestClient, db_session: Session, monkeypatch):
    """Test nominal creation of Stripe PaymentIntent for a pending guest order."""
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_secret_key")
    monkeypatch.setattr(settings, "STRIPE_PUBLISHABLE_KEY", "pk_test_mock_pub_key")

    fixture = setup_order_fixture(client)
    slug = fixture["slug"]
    order = fixture["order"]
    order_id = order["id"]
    access_token = order["access_token"]

    mock_intent = MagicMock()
    mock_intent.id = "pi_3MtwBwLkdIwHu7ix28a3tqPa"
    mock_intent.client_secret = "pi_3MtwBwLkdIwHu7ix28a3tqPa_secret_xY789"
    mock_intent.status = "requires_payment_method"

    with patch("stripe.PaymentIntent.create", return_value=mock_intent) as mock_create:
        res = client.post(
            f"/api/v1/public/events/{slug}/orders/{order_id}/payment-intent",
            headers={"X-Access-Token": access_token},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["client_secret"] == "pi_3MtwBwLkdIwHu7ix28a3tqPa_secret_xY789"
        assert data["payment_intent_id"] == "pi_3MtwBwLkdIwHu7ix28a3tqPa"
        assert data["publishable_key"] == "pk_test_mock_pub_key"
        assert data["amount_cents"] == order["total_price_cents"]
        assert data["currency"] == "eur"

        # Verify stripe.PaymentIntent.create was called with metadata
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        assert kwargs["amount"] == order["total_price_cents"]
        assert kwargs["currency"] == "eur"
        assert kwargs["metadata"]["order_id"] == order_id
        assert kwargs["metadata"]["order_number"] == order["order_number"]

    # Verify order in DB has stripe_payment_intent_id updated
    db_order = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    assert db_order is not None
    assert db_order.stripe_payment_intent_id == "pi_3MtwBwLkdIwHu7ix28a3tqPa"

    # Test reuse of existing payment intent
    with patch("stripe.PaymentIntent.retrieve", return_value=mock_intent) as mock_retrieve, \
         patch("stripe.PaymentIntent.create") as mock_create_2:
        res_reuse = client.post(
            f"/api/v1/public/events/{slug}/orders/{order_id}/payment-intent?token={access_token}",
        )
        assert res_reuse.status_code == 200, res_reuse.text
        assert res_reuse.json()["client_secret"] == "pi_3MtwBwLkdIwHu7ix28a3tqPa_secret_xY789"
        mock_retrieve.assert_called_once()
        mock_create_2.assert_not_called()


def test_create_payment_intent_auth_failures(client: TestClient, monkeypatch):
    """Test authentication and authorization boundaries on payment-intent endpoint."""
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_secret_key")
    fixture = setup_order_fixture(client)
    slug = fixture["slug"]
    order_id = fixture["order"]["id"]

    # 1. Missing token -> 401
    res_no_token = client.post(f"/api/v1/public/events/{slug}/orders/{order_id}/payment-intent")
    assert res_no_token.status_code == 401

    # 2. Invalid token -> 403
    res_bad_token = client.post(
        f"/api/v1/public/events/{slug}/orders/{order_id}/payment-intent",
        headers={"X-Access-Token": "invalid-token-42"},
    )
    assert res_bad_token.status_code == 403

    # 3. Non-existent order id -> 404
    fake_id = str(uuid.uuid4())
    res_not_found = client.post(
        f"/api/v1/public/events/{slug}/orders/{fake_id}/payment-intent",
        headers={"X-Access-Token": "some-token"},
    )
    assert res_not_found.status_code == 404


def test_create_payment_intent_rejects_already_confirmed_order(client: TestClient, db_session: Session, monkeypatch):
    """Ensure orders that are already confirmed cannot create new payment intents."""
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_secret_key")
    fixture = setup_order_fixture(client)
    slug = fixture["slug"]
    order_id = fixture["order"]["id"]
    token = fixture["order"]["access_token"]

    # Manually transition order to confirmed
    db_order = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    db_order.status = "confirmed"
    db_session.commit()

    res = client.post(
        f"/api/v1/public/events/{slug}/orders/{order_id}/payment-intent",
        headers={"X-Access-Token": token},
    )
    assert res.status_code == 409
    assert "déjà confirmée" in res.json()["detail"]


def test_create_payment_intent_expired_hold_lock(client: TestClient, db_session: Session, monkeypatch):
    """Ensure payment-intent creation is rejected with 409 if spot locks have expired."""
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_secret_key")
    fixture = setup_order_fixture(client)
    slug = fixture["slug"]
    order_id = fixture["order"]["id"]
    token = fixture["order"]["access_token"]
    spot_ids = [uuid.UUID(s["id"]) for s in fixture["spots"]]

    # Expire the hold locks on the spots
    past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    for sp_id in spot_ids:
        sp = db_session.query(Spot).filter(Spot.id == sp_id).first()
        sp.locked_until = past_time
    db_session.commit()

    res = client.post(
        f"/api/v1/public/events/{slug}/orders/{order_id}/payment-intent",
        headers={"X-Access-Token": token},
    )
    assert res.status_code == 409
    assert "a expiré" in res.json()["detail"]

    # Verify spots are now released to available
    for sp_id in spot_ids:
        sp = db_session.query(Spot).filter(Spot.id == sp_id).first()
        assert sp.status == "available"
        assert sp.locked_until is None


def test_stripe_webhook_nominal_flow(client: TestClient, db_session: Session, monkeypatch):
    """
    Test nominal cryptographic Stripe webhook processing:
    payment_intent.succeeded atomically transitions Order to 'confirmed' and Spots to 'reserved'.
    """
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    fixture = setup_order_fixture(client)
    order = fixture["order"]
    order_id = order["id"]
    spot_ids = [uuid.UUID(s["id"]) for s in fixture["spots"]]

    payment_intent_id = f"pi_test_webhook_{uuid.uuid4().hex[:8]}"

    event_payload = {
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "object": "event",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_intent_id,
                "object": "payment_intent",
                "amount": order["total_price_cents"],
                "currency": "eur",
                "status": "succeeded",
                "metadata": {
                    "order_id": order_id,
                    "order_number": order["order_number"],
                },
            }
        },
    }
    raw_payload = json.dumps(event_payload)
    sig_header = stripe.WebhookSignature.generate_signature_header(
        payload=raw_payload,
        secret=TEST_WEBHOOK_SECRET,
    )

    # Deliver webhook
    res = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": sig_header,
        },
    )
    assert res.status_code == 200, res.text
    resp_data = res.json()
    assert resp_data["status"] == "success"
    assert resp_data["order_id"] == order_id

    # Verify Order in DB is now confirmed with single source of truth
    db_order = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    assert db_order is not None
    assert db_order.status == "confirmed"
    assert db_order.payment_method == "stripe"
    assert db_order.stripe_payment_intent_id == payment_intent_id

    # Verify all associated spots are now reserved
    for sp_id in spot_ids:
        sp = db_session.query(Spot).filter(Spot.id == sp_id).first()
        assert sp.status == "reserved"
        assert sp.locked_until is None
        assert sp.locked_by_token is None


def test_stripe_webhook_idempotency(client: TestClient, db_session: Session, monkeypatch):
    """
    Ensure delivering the same payment_intent.succeeded event multiple times
    is idempotent, returning HTTP 200 without duplicate modifications.
    """
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    fixture = setup_order_fixture(client)
    order = fixture["order"]
    order_id = order["id"]
    payment_intent_id = f"pi_idempotent_{uuid.uuid4().hex[:8]}"

    event_payload = {
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "object": "event",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_intent_id,
                "status": "succeeded",
                "metadata": {
                    "order_id": order_id,
                },
            }
        },
    }
    raw_payload = json.dumps(event_payload)
    sig_header = stripe.WebhookSignature.generate_signature_header(raw_payload, TEST_WEBHOOK_SECRET)

    # 1. First delivery
    res1 = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload.encode("utf-8"),
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header},
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "success"

    # 2. Duplicate delivery
    res2 = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload.encode("utf-8"),
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "success"

    # DB state remains confirmed
    db_order = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    assert db_order.status == "confirmed"


def test_stripe_webhook_invalid_signature_rejected(client: TestClient, db_session: Session, monkeypatch):
    """Ensure forged or corrupted signatures are rejected with HTTP 400."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    fixture = setup_order_fixture(client)
    order_id = fixture["order"]["id"]

    event_payload = {
        "id": "evt_forged",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_forged",
                "metadata": {"order_id": order_id},
            }
        },
    }
    raw_payload = json.dumps(event_payload)

    # Corrupted / invalid signature
    bad_sig = "t=1700000000,v1=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    res = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload.encode("utf-8"),
        headers={"Content-Type": "application/json", "Stripe-Signature": bad_sig},
    )
    assert res.status_code == 400
    assert "invalide" in res.json()["detail"].lower()

    # Verify order in DB was NOT changed
    db_order = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    assert db_order.status == "pending"


def test_stripe_webhook_missing_signature(client: TestClient):
    """Ensure missing Stripe-Signature header returns HTTP 400."""
    res = client.post(
        "/api/v1/webhooks/stripe",
        content=b'{"id": "evt_test"}',
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 400
    assert "manquant" in res.json()["detail"].lower()


def test_stripe_webhook_unhandled_event(client: TestClient, monkeypatch):
    """Ensure non-payment_intent.succeeded events are acknowledged with HTTP 200 ignored."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    event_payload = {
        "id": "evt_failed",
        "object": "event",
        "type": "payment_intent.payment_failed",
        "data": {"object": {"id": "pi_failed"}},
    }
    raw_payload = json.dumps(event_payload)
    sig_header = stripe.WebhookSignature.generate_signature_header(raw_payload, TEST_WEBHOOK_SECRET)

    res = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload.encode("utf-8"),
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ignored"
    assert res.json()["event_type"] == "payment_intent.payment_failed"


def test_stripe_webhook_unknown_order(client: TestClient, monkeypatch):
    """Ensure webhook for unknown order returns 200 ignored gracefully."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    event_payload = {
        "id": "evt_unknown",
        "object": "event",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_unknown",
                "metadata": {"order_id": str(uuid.uuid4())},
            }
        },
    }
    raw_payload = json.dumps(event_payload)
    sig_header = stripe.WebhookSignature.generate_signature_header(raw_payload, TEST_WEBHOOK_SECRET)

    res = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload.encode("utf-8"),
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ignored"
    assert res.json()["reason"] == "order_not_found"


def test_create_payment_intent_stripe_error_raises_502(client: TestClient, monkeypatch):
    """Ensure Stripe API errors raise HTTP 502 Bad Gateway."""
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_secret_key")
    fixture = setup_order_fixture(client)
    slug = fixture["slug"]
    order_id = fixture["order"]["id"]
    token = fixture["order"]["access_token"]

    with patch("stripe.PaymentIntent.create", side_effect=stripe.StripeError("Stripe API connection failure")):
        res = client.post(
            f"/api/v1/public/events/{slug}/orders/{order_id}/payment-intent",
            headers={"X-Access-Token": token},
        )
        assert res.status_code == 502
        assert "Erreur lors de l'initialisation du paiement Stripe" in res.json()["detail"]


def test_create_payment_intent_minimum_charge_validation(client: TestClient, db_session: Session, monkeypatch):
    """Ensure orders below 0,50 € are rejected with HTTP 400."""
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_secret_key")
    fixture = setup_order_fixture(client)
    slug = fixture["slug"]
    order_id = fixture["order"]["id"]
    token = fixture["order"]["access_token"]

    # Set order total below 50 cents
    db_order = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    db_order.total_price_cents = 30
    db_session.commit()

    res = client.post(
        f"/api/v1/public/events/{slug}/orders/{order_id}/payment-intent",
        headers={"X-Access-Token": token},
    )
    assert res.status_code == 400
    assert "0,50 €" in res.json()["detail"]


def test_create_payment_intent_expired_hold_cancels_order(client: TestClient, db_session: Session, monkeypatch):
    """Ensure expired hold marks the order status as cancelled and spots available."""
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_secret_key")
    fixture = setup_order_fixture(client)
    slug = fixture["slug"]
    order_id = fixture["order"]["id"]
    token = fixture["order"]["access_token"]
    spot_ids = [uuid.UUID(s["id"]) for s in fixture["spots"]]

    # Expire locks
    past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    for sp_id in spot_ids:
        sp = db_session.query(Spot).filter(Spot.id == sp_id).first()
        sp.locked_until = past_time
    db_session.commit()

    res = client.post(
        f"/api/v1/public/events/{slug}/orders/{order_id}/payment-intent",
        headers={"X-Access-Token": token},
    )
    assert res.status_code == 409
    assert "a expiré" in res.json()["detail"]

    # Verify order is marked cancelled
    db_order = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    assert db_order.status == "cancelled"

    # Verify spots are available
    for sp_id in spot_ids:
        sp = db_session.query(Spot).filter(Spot.id == sp_id).first()
        assert sp.status == "available"


def test_stripe_webhook_root_route(client: TestClient, db_session: Session, monkeypatch):
    """Ensure root /webhooks/stripe route properly receives and processes webhooks."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    fixture = setup_order_fixture(client)
    order = fixture["order"]
    order_id = order["id"]
    payment_intent_id = f"pi_root_route_{uuid.uuid4().hex[:8]}"

    event_payload = {
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "object": "event",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_intent_id,
                "amount": order["total_price_cents"],
                "currency": "eur",
                "status": "succeeded",
                "metadata": {"order_id": order_id},
            }
        },
    }
    raw_payload = json.dumps(event_payload)
    sig_header = stripe.WebhookSignature.generate_signature_header(raw_payload, TEST_WEBHOOK_SECRET)

    res = client.post(
        "/webhooks/stripe",
        content=raw_payload.encode("utf-8"),
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "success"

    db_order = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    assert db_order.status == "confirmed"


def test_stripe_webhook_fallback_lookup_empty_metadata(client: TestClient, db_session: Session, monkeypatch):
    """Ensure webhook fallback lookup by stripe_payment_intent_id succeeds when metadata is empty."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    fixture = setup_order_fixture(client)
    order = fixture["order"]
    order_id = order["id"]
    payment_intent_id = f"pi_empty_meta_{uuid.uuid4().hex[:8]}"

    # Associate order with stripe_payment_intent_id
    db_order = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    db_order.stripe_payment_intent_id = payment_intent_id
    db_session.commit()

    event_payload = {
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "object": "event",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_intent_id,
                "amount": order["total_price_cents"],
                "currency": "eur",
                "status": "succeeded",
                "metadata": {},  # Empty metadata
            }
        },
    }
    raw_payload = json.dumps(event_payload)
    sig_header = stripe.WebhookSignature.generate_signature_header(raw_payload, TEST_WEBHOOK_SECRET)

    res = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload.encode("utf-8"),
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "success"

    db_session.refresh(db_order)
    assert db_order.status == "confirmed"


def test_stripe_webhook_amount_and_currency_mismatch(client: TestClient, db_session: Session, monkeypatch):
    """Ensure webhook rejects mismatched amount or unsupported currency with HTTP 400."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    fixture = setup_order_fixture(client)
    order = fixture["order"]
    order_id = order["id"]
    payment_intent_id = f"pi_mismatch_{uuid.uuid4().hex[:8]}"

    # 1. Mismatched amount
    bad_amount_payload = {
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "object": "event",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_intent_id,
                "amount": order["total_price_cents"] + 500,  # 5€ mismatch
                "currency": "eur",
                "status": "succeeded",
                "metadata": {"order_id": order_id},
            }
        },
    }
    raw_bad_amount = json.dumps(bad_amount_payload)
    sig_header1 = stripe.WebhookSignature.generate_signature_header(raw_bad_amount, TEST_WEBHOOK_SECRET)

    res1 = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_bad_amount.encode("utf-8"),
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header1},
    )
    assert res1.status_code == 400
    assert "Incohérence du montant" in res1.json()["detail"]

    # 2. Unsupported currency
    bad_curr_payload = {
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "object": "event",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_intent_id,
                "amount": order["total_price_cents"],
                "currency": "usd",  # USD instead of EUR
                "status": "succeeded",
                "metadata": {"order_id": order_id},
            }
        },
    }
    raw_bad_curr = json.dumps(bad_curr_payload)
    sig_header2 = stripe.WebhookSignature.generate_signature_header(raw_bad_curr, TEST_WEBHOOK_SECRET)

    res2 = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_bad_curr.encode("utf-8"),
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header2},
    )
    assert res2.status_code == 400
    assert "Devise de paiement non supportée" in res2.json()["detail"]


def test_stripe_webhook_spot_collision_rejected(client: TestClient, db_session: Session, monkeypatch):
    """Ensure webhook raises 409 and does not double-book if a spot is already reserved."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    fixture = setup_order_fixture(client)
    order = fixture["order"]
    order_id = order["id"]
    spot_id = uuid.UUID(fixture["spots"][0]["id"])

    # Simulate another confirmed order already reserving that spot
    spot = db_session.query(Spot).filter(Spot.id == spot_id).first()
    spot.status = "reserved"
    db_session.commit()

    event_payload = {
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "object": "event",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": f"pi_collision_{uuid.uuid4().hex[:8]}",
                "amount": order["total_price_cents"],
                "currency": "eur",
                "status": "succeeded",
                "metadata": {"order_id": order_id},
            }
        },
    }
    raw_payload = json.dumps(event_payload)
    sig_header = stripe.WebhookSignature.generate_signature_header(raw_payload, TEST_WEBHOOK_SECRET)

    res = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload.encode("utf-8"),
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header},
    )
    assert res.status_code == 409
    assert "Conflit de réservation" in res.json()["detail"]


def test_stripe_webhook_missing_secret_raises_500(client: TestClient, monkeypatch):
    """Ensure missing STRIPE_WEBHOOK_SECRET raises HTTP 500 and is not swallowed as 400."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    res = client.post(
        "/api/v1/webhooks/stripe",
        content=b'{"id": "evt_test"}',
        headers={"Content-Type": "application/json", "Stripe-Signature": "t=1,v1=abc"},
    )
    assert res.status_code == 500
    assert "Le secret de webhook Stripe n'est pas configuré" in res.json()["detail"]

