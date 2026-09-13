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


def create_event(client: TestClient, manual_approval: bool = True, title: str = "Brocante Modérée") -> dict:
    payload = {
        "title": title,
        "description": "Vide-grenier avec modération",
        "price_per_meter": 5.0,
        "map_type": "geographic",
        "start_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=7, hours=10)).isoformat(),
        "setup_start_time": "06:00",
        "setup_end_time": "08:00",
        "public_start_time": "08:00",
        "public_end_time": "18:00",
        "location_address": "Place de la Mairie, Rennes",
        "organizer_email": "marc@brocante.fr",
        "manual_approval_required": manual_approval,
        "status": "published",
    }
    res = client.post("/api/v1/events", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def create_spot(client: TestClient, event_id: str, label: str = "M-01", linear_meters: float = 2.0) -> dict:
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


def setup_moderated_order(client: TestClient, manual_approval: bool = True) -> dict:
    ev = create_event(client, manual_approval=manual_approval, title=f"Vide-Grenier {uuid.uuid4().hex[:6]}")
    slug = ev["slug"]
    spot = create_spot(client, ev["id"], label="M-01", linear_meters=2.0)
    session_token = f"session-{uuid.uuid4().hex[:8]}"

    # Lock spot
    lock_res = client.post(
        f"/api/v1/public/events/{slug}/spots/{spot['id']}/lock",
        headers={"X-Session-Token": session_token},
        json={"session_token": session_token},
    )
    assert lock_res.status_code == 200, lock_res.text

    # Create guest order
    order_payload = {
        "session_token": session_token,
        "first_name": "Jean",
        "last_name": "Dupont",
        "email": "jean.dupont@test.fr",
        "phone": "0612345678",
        "street_address": "15 rue des Lilas",
        "postal_code": "35000",
        "city": "Rennes",
        "honor_declaration_accepted": True,
    }
    order_res = client.post(
        f"/api/v1/public/events/{slug}/orders",
        headers={"X-Session-Token": session_token},
        json=order_payload,
    )
    assert order_res.status_code == 201, order_res.text
    order_data = order_res.json()

    return {
        "event": ev,
        "spot": spot,
        "order": order_data,
        "session_token": session_token,
    }


def test_toggle_manual_approval_setting(client: TestClient):
    """Verify that manual_approval_required can be toggled via PATCH /api/v1/events/{id}."""
    ev = create_event(client, manual_approval=False)
    assert ev["manual_approval_required"] is False

    # Turn ON
    res_on = client.patch(f"/api/v1/events/{ev['id']}", json={"manual_approval_required": True})
    assert res_on.status_code == 200
    assert res_on.json()["manual_approval_required"] is True

    # Turn OFF
    res_off = client.patch(f"/api/v1/events/{ev['id']}", json={"manual_approval_required": False})
    assert res_off.status_code == 200
    assert res_off.json()["manual_approval_required"] is False


@patch("stripe.PaymentIntent.create")
def test_create_payment_intent_manual_capture(mock_pi_create, client: TestClient):
    """When manual_approval_required is True, PaymentIntent must have capture_method='manual'."""
    fixture = setup_moderated_order(client, manual_approval=True)
    slug = fixture["event"]["slug"]
    order_id = fixture["order"]["id"]
    access_token = fixture["order"]["access_token"]

    mock_intent = MagicMock()
    mock_intent.client_secret = "pi_manual_secret_123"
    mock_intent.id = "pi_manual_123"
    mock_intent.status = "requires_payment_method"
    mock_pi_create.return_value = mock_intent

    with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123"), \
         patch.object(settings, "STRIPE_PUBLISHABLE_KEY", "pk_test_fake_123"):
        res = client.post(
            f"/api/v1/public/events/{slug}/orders/{order_id}/payment-intent",
            headers={"X-Access-Token": access_token},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["payment_intent_id"] == "pi_manual_123"

        # Verify stripe.PaymentIntent.create was called with capture_method="manual"
        mock_pi_create.assert_called_once()
        _, kwargs = mock_pi_create.call_args
        assert kwargs.get("capture_method") == "manual"


@patch("stripe.PaymentIntent.create")
def test_create_payment_intent_automatic_capture_when_disabled(mock_pi_create, client: TestClient):
    """When manual_approval_required is False, capture_method='manual' must NOT be set."""
    fixture = setup_moderated_order(client, manual_approval=False)
    slug = fixture["event"]["slug"]
    order_id = fixture["order"]["id"]
    access_token = fixture["order"]["access_token"]

    mock_intent = MagicMock()
    mock_intent.client_secret = "pi_auto_secret_123"
    mock_intent.id = "pi_auto_123"
    mock_intent.status = "requires_payment_method"
    mock_pi_create.return_value = mock_intent

    with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123"), \
         patch.object(settings, "STRIPE_PUBLISHABLE_KEY", "pk_test_fake_123"):
        res = client.post(
            f"/api/v1/public/events/{slug}/orders/{order_id}/payment-intent",
            headers={"X-Access-Token": access_token},
        )
        assert res.status_code == 200
        mock_pi_create.assert_called_once()
        _, kwargs = mock_pi_create.call_args
        assert "capture_method" not in kwargs


def test_webhook_amount_capturable_updated(client: TestClient, db_session: Session):
    """Webhook payment_intent.amount_capturable_updated moves order to pending_approval and reserves spots."""
    fixture = setup_moderated_order(client, manual_approval=True)
    order_id = fixture["order"]["id"]
    spot_id = fixture["spot"]["id"]
    pi_id = f"pi_test_cap_{uuid.uuid4().hex[:6]}"

    # Set stripe_payment_intent_id on order in DB
    order_obj = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    order_obj.stripe_payment_intent_id = pi_id
    db_session.commit()

    webhook_event = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "payment_intent.amount_capturable_updated",
        "data": {
            "object": {
                "id": pi_id,
                "amount": 1000,
                "amount_capturable": 1000,
                "currency": "eur",
                "metadata": {
                    "order_id": order_id,
                    "order_number": fixture["order"]["order_number"],
                },
            }
        },
    }

    with patch("stripe.Webhook.construct_event", return_value=webhook_event), \
         patch.object(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET):
        res = client.post(
            "/api/v1/webhooks/stripe",
            headers={"Stripe-Signature": "sig_mock"},
            data=json.dumps(webhook_event).encode("utf-8"),
        )
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        assert res.json()["order_status"] == "pending_approval"

    # Verify order in DB is pending_approval
    db_session.expire_all()
    order_obj = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    assert order_obj.status == "pending_approval"

    # Verify spot is reserved and protected
    spot_obj = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_id)).first()
    assert spot_obj.status == "reserved"
    assert spot_obj.locked_until is None


def test_public_order_resilience_requires_capture(client: TestClient, db_session: Session):
    """Direct sync in get_public_order when Stripe PaymentIntent has requires_capture."""
    fixture = setup_moderated_order(client, manual_approval=True)
    slug = fixture["event"]["slug"]
    order_id = fixture["order"]["id"]
    access_token = fixture["order"]["access_token"]
    spot_id = fixture["spot"]["id"]
    pi_id = f"pi_sync_{uuid.uuid4().hex[:6]}"

    order_obj = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    order_obj.stripe_payment_intent_id = pi_id
    db_session.commit()

    mock_pi = MagicMock()
    mock_pi.status = "requires_capture"
    mock_pi.amount_capturable = 1000
    mock_pi.currency = "eur"

    with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123"), \
         patch("stripe.PaymentIntent.retrieve", return_value=mock_pi):
        res = client.get(
            f"/api/v1/public/events/{slug}/orders/{order_id}?token={access_token}",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "pending_approval"

    db_session.expire_all()
    spot_obj = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_id)).first()
    assert spot_obj.status == "reserved"


@patch("stripe.PaymentIntent.capture")
def test_admin_approve_order_workflow(mock_capture, client: TestClient, db_session: Session):
    """Admin approves a pending_approval order: captures Stripe PI, sets status confirmed, spot remains reserved."""
    fixture = setup_moderated_order(client, manual_approval=True)
    event_id = fixture["event"]["id"]
    order_id = fixture["order"]["id"]
    spot_id = fixture["spot"]["id"]
    pi_id = f"pi_approve_{uuid.uuid4().hex[:6]}"

    order_obj = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    order_obj.status = "pending_approval"
    order_obj.stripe_payment_intent_id = pi_id
    spot_obj = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_id)).first()
    spot_obj.status = "reserved"
    db_session.commit()

    mock_capture.return_value = {"id": pi_id, "status": "succeeded"}

    with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123"):
        # Check stats before approval
        stats_res = client.get(f"/api/v1/events/{event_id}/dashboard-stats")
        assert stats_res.status_code == 200
        assert stats_res.json()["pending_approval_orders_count"] == 1

        # Approve order
        approve_res = client.post(
            f"/api/v1/events/{event_id}/orders/{order_id}/approve",
            json={"reason": "Dossier conforme et validé"},
        )
        assert approve_res.status_code == 200
        data = approve_res.json()
        assert data["status"] == "confirmed"
        mock_capture.assert_called_once_with(pi_id, api_key="sk_test_fake_123")

        # Check order and spot in DB
        db_session.expire_all()
        order_obj = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
        assert order_obj.status == "confirmed"
        assert "Dossier conforme" in (order_obj.admin_notes or "")

        spot_obj = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_id)).first()
        assert spot_obj.status == "reserved"

        # Check stats after approval
        stats_after = client.get(f"/api/v1/events/{event_id}/dashboard-stats")
        assert stats_after.json()["pending_approval_orders_count"] == 0
        assert stats_after.json()["confirmed_orders_count"] >= 1

        # Idempotency: calling approve again returns confirmed order
        approve_again = client.post(
            f"/api/v1/events/{event_id}/orders/{order_id}/approve",
        )
        assert approve_again.status_code == 200
        assert approve_again.json()["status"] == "confirmed"


@patch("stripe.PaymentIntent.cancel")
def test_admin_reject_order_workflow(mock_cancel, client: TestClient, db_session: Session):
    """Admin rejects a pending_approval order: cancels Stripe PI, sets status rejected, spots released to available."""
    fixture = setup_moderated_order(client, manual_approval=True)
    event_id = fixture["event"]["id"]
    order_id = fixture["order"]["id"]
    spot_id = fixture["spot"]["id"]
    slug = fixture["event"]["slug"]
    pi_id = f"pi_reject_{uuid.uuid4().hex[:6]}"

    order_obj = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    order_obj.status = "pending_approval"
    order_obj.stripe_payment_intent_id = pi_id
    spot_obj = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_id)).first()
    spot_obj.status = "reserved"
    db_session.commit()

    mock_cancel.return_value = {"id": pi_id, "status": "canceled"}

    with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123"):
        reject_res = client.post(
            f"/api/v1/events/{event_id}/orders/{order_id}/reject",
            json={"reason": "Marchandises non autorisées"},
        )
        assert reject_res.status_code == 200
        data = reject_res.json()
        assert data["status"] == "rejected"
        mock_cancel.assert_called_once_with(pi_id, api_key="sk_test_fake_123")

        # Check DB state
        db_session.expire_all()
        order_obj = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
        assert order_obj.status == "rejected"
        assert "Marchandises non autorisées" in (order_obj.admin_notes or "")

        # Spot must be available and unlocked
        spot_obj = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_id)).first()
        assert spot_obj.status == "available"
        assert spot_obj.locked_until is None
        assert spot_obj.locked_by_token is None

        # Check public spot endpoint: spot is available
        public_spots = client.get(f"/api/v1/public/events/{slug}/spots")
        assert public_spots.status_code == 200
        features = public_spots.json()["features"]
        matching = [f for f in features if f["id"] == spot_id]
        assert len(matching) == 1
        assert matching[0]["properties"]["status"] == "available"

        # Idempotency: rejecting already rejected order returns rejected
        reject_again = client.post(
            f"/api/v1/events/{event_id}/orders/{order_id}/reject",
        )
        assert reject_again.status_code == 200
        assert reject_again.json()["status"] == "rejected"


def test_approve_reject_invalid_status_rejected(client: TestClient, db_session: Session):
    """Cannot approve or reject an order that is pending (without pre-authorization) or cancelled."""
    fixture = setup_moderated_order(client, manual_approval=True)
    event_id = fixture["event"]["id"]
    order_id = fixture["order"]["id"]

    # Order is 'pending', not 'pending_approval'
    res_app = client.post(f"/api/v1/events/{event_id}/orders/{order_id}/approve")
    assert res_app.status_code == 400
    assert "pending_approval" in res_app.json()["detail"]

    res_rej = client.post(f"/api/v1/events/{event_id}/orders/{order_id}/reject")
    assert res_rej.status_code == 400
    assert "pending_approval" in res_rej.json()["detail"]


@patch("stripe.PaymentIntent.capture")
def test_stripe_capture_failure_returns_502(mock_capture, client: TestClient, db_session: Session):
    """When Stripe capture raises a StripeError, API returns 502 Bad Gateway."""
    fixture = setup_moderated_order(client, manual_approval=True)
    event_id = fixture["event"]["id"]
    order_id = fixture["order"]["id"]
    pi_id = f"pi_err_{uuid.uuid4().hex[:6]}"

    order_obj = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    order_obj.status = "pending_approval"
    order_obj.stripe_payment_intent_id = pi_id
    db_session.commit()

    mock_capture.side_effect = stripe.StripeError("Card was expired or declined at capture")

    with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123"):
        res = client.post(f"/api/v1/events/{event_id}/orders/{order_id}/approve")
        assert res.status_code == 502
        assert "Échec de la capture du paiement Stripe" in res.json()["detail"]


def test_list_orders_status_pending_approval_filter(client: TestClient, db_session: Session):
    """Filtering orders with status=pending_approval returns only matching orders."""
    fixture = setup_moderated_order(client, manual_approval=True)
    event_id = fixture["event"]["id"]
    order_id = fixture["order"]["id"]

    # Transition order to pending_approval
    order_obj = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    order_obj.status = "pending_approval"
    db_session.commit()

    # Query with status=pending_approval
    res = client.get(f"/api/v1/events/{event_id}/orders?status=pending_approval")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == order_id
    assert data["items"][0]["status"] == "pending_approval"
    assert data["stats"]["pending_approval_orders_count"] == 1

    # Query with status=confirmed should return empty
    res_conf = client.get(f"/api/v1/events/{event_id}/orders?status=confirmed")
    assert res_conf.status_code == 200
    assert res_conf.json()["total"] == 0


@patch("stripe.Webhook.construct_event")
def test_webhook_payment_intent_succeeded_on_pending_approval(mock_construct, client: TestClient, db_session: Session):
    """Webhook payment_intent.succeeded on an order in pending_approval transitions it to confirmed."""
    fixture = setup_moderated_order(client, manual_approval=True)
    order_id = fixture["order"]["id"]
    spot_id = fixture["spot"]["id"]
    pi_id = f"pi_succ_{uuid.uuid4().hex[:6]}"

    order_obj = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    order_obj.status = "pending_approval"
    order_obj.stripe_payment_intent_id = pi_id
    spot_obj = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_id)).first()
    spot_obj.status = "reserved"
    db_session.commit()

    webhook_payload = {
        "id": f"evt_{uuid.uuid4().hex[:6]}",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": pi_id,
                "amount_received": 1000,
                "currency": "eur",
                "metadata": {"order_id": order_id},
            }
        },
    }
    mock_construct.return_value = webhook_payload

    with patch.object(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET):
        res = client.post(
            "/api/v1/webhooks/stripe",
            headers={"Stripe-Signature": "t=123,v1=fake_sig"},
            data=json.dumps(webhook_payload),
        )
        assert res.status_code == 200
        assert res.json()["status"] == "success"

        db_session.expire_all()
        order_obj = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
        assert order_obj.status == "confirmed"


@patch("stripe.Webhook.construct_event")
@patch("stripe.PaymentIntent.cancel")
def test_webhook_payment_intent_canceled_releases_spots(mock_cancel, mock_construct, client: TestClient, db_session: Session):
    """Webhook payment_intent.canceled rejects order and frees spots immediately."""
    fixture = setup_moderated_order(client, manual_approval=True)
    order_id = fixture["order"]["id"]
    spot_id = fixture["spot"]["id"]
    pi_id = f"pi_canc_{uuid.uuid4().hex[:6]}"

    order_obj = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    order_obj.status = "pending_approval"
    order_obj.stripe_payment_intent_id = pi_id
    spot_obj = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_id)).first()
    spot_obj.status = "reserved"
    db_session.commit()

    webhook_payload = {
        "id": f"evt_{uuid.uuid4().hex[:6]}",
        "type": "payment_intent.canceled",
        "data": {
            "object": {
                "id": pi_id,
                "metadata": {"order_id": order_id},
            }
        },
    }
    mock_construct.return_value = webhook_payload

    with patch.object(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET):
        with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123"):
            res = client.post(
                "/api/v1/webhooks/stripe",
                headers={"Stripe-Signature": "t=123,v1=fake_sig"},
                data=json.dumps(webhook_payload),
            )
            assert res.status_code == 200
            assert res.json()["status"] == "success"
            assert res.json()["order_status"] == "rejected"

            db_session.expire_all()
            order_obj = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
            assert order_obj.status == "rejected"
            spot_obj = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_id)).first()
            assert spot_obj.status == "available"
            assert spot_obj.locked_until is None


@patch("stripe.PaymentIntent.cancel")
def test_stripe_reject_failure_returns_502(mock_cancel, client: TestClient, db_session: Session):
    """When Stripe cancellation raises an unexpected StripeError, API returns 502 Bad Gateway."""
    fixture = setup_moderated_order(client, manual_approval=True)
    event_id = fixture["event"]["id"]
    order_id = fixture["order"]["id"]
    pi_id = f"pi_rej_err_{uuid.uuid4().hex[:6]}"

    order_obj = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    order_obj.status = "pending_approval"
    order_obj.stripe_payment_intent_id = pi_id
    db_session.commit()

    mock_cancel.side_effect = stripe.StripeError("Network communication with Stripe failed")

    with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123"):
        res = client.post(f"/api/v1/events/{event_id}/orders/{order_id}/reject")
        assert res.status_code == 502
        assert "Échec de l'annulation de l'autorisation Stripe" in res.json()["detail"]


@patch("stripe.PaymentIntent.capture")
def test_stripe_capture_already_captured_idempotent(mock_capture, client: TestClient, db_session: Session):
    """When Stripe reports already captured, approval proceeds idempotently as confirmed."""
    fixture = setup_moderated_order(client, manual_approval=True)
    event_id = fixture["event"]["id"]
    order_id = fixture["order"]["id"]
    pi_id = f"pi_cap_idem_{uuid.uuid4().hex[:6]}"

    order_obj = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    order_obj.status = "pending_approval"
    order_obj.stripe_payment_intent_id = pi_id
    db_session.commit()

    mock_capture.side_effect = stripe.StripeError("PaymentIntent has already been captured")

    with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123"):
        res = client.post(f"/api/v1/events/{event_id}/orders/{order_id}/approve")
        assert res.status_code == 200
        assert res.json()["status"] == "confirmed"
