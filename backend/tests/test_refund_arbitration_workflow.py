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

TEST_WEBHOOK_SECRET = "whsec_test_secret_for_cryptographic_verification"

SAMPLE_POLY_COORDS = [
    [
        [-1.68, 48.11],
        [-1.67, 48.11],
        [-1.67, 48.12],
        [-1.68, 48.12],
        [-1.68, 48.11],
    ]
]


def create_test_event(client: TestClient, title: str = "Grand Vide-Grenier") -> dict:
    payload = {
        "title": title,
        "description": "Événement de test pour les remboursements",
        "price_per_meter": 4.0,
        "map_type": "geographic",
        "start_date": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=14, hours=10)).isoformat(),
        "setup_start_time": "06:00",
        "setup_end_time": "08:00",
        "public_start_time": "08:00",
        "public_end_time": "18:00",
        "location_address": "Place Centrale, Rennes",
        "organizer_email": "organisateur@gvg.fr",
        "manual_approval_required": False,
        "status": "published",
    }
    res = client.post("/api/v1/events", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def create_test_spot(client: TestClient, event_id: str, label: str = "A-01", meters: float = 2.0) -> dict:
    payload = {
        "label": label,
        "linear_meters": meters,
        "geometry": {
            "type": "Polygon",
            "coordinates": SAMPLE_POLY_COORDS,
        },
    }
    res = client.post(f"/api/v1/events/{event_id}/spots", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def create_test_order(
    db: Session,
    event_id: uuid.UUID,
    spot: Spot,
    status: str = "confirmed",
    payment_method: str = "stripe",
    stripe_pi: str = "pi_test_123456",
) -> Order:
    order = Order(
        event_id=event_id,
        first_name="Monique",
        last_name="Test",
        email="monique@test.fr",
        phone="0611223344",
        street_address="10 rue des Fleurs",
        postal_code="35000",
        city="Rennes",
        honor_declaration_accepted=True,
        total_price_cents=spot.price_cents,
        status=status,
        payment_method=payment_method,
        stripe_payment_intent_id=stripe_pi if payment_method == "stripe" else None,
    )
    db.add(order)
    db.flush()

    item = BookingItem(
        order_id=order.id,
        spot_id=spot.id,
        price_cents=spot.price_cents,
    )
    db.add(item)
    spot.status = "reserved" if status in ("confirmed", "pending_approval", "cancellation_requested") else "available"
    db.commit()
    db.refresh(order)
    return order


def test_refund_stripe_order_success(client: TestClient, db_session: Session):
    """Given a cancellation_requested Stripe order, admin refunds it: calls Stripe and releases spot."""
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="R-01")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="cancellation_requested")

    with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123"), \
         patch("stripe.Refund.create") as mock_refund:
        mock_refund.return_value = MagicMock(id="re_123", status="succeeded")

        res = client.post(
            f"/api/v1/events/{event['id']}/orders/{order.id}/refund",
            json={"reason": "Annulation acceptée - motif médical valable"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "refunded"
        assert "motif médical valable" in (data["admin_notes"] or "")

        mock_refund.assert_called_once()
        assert mock_refund.call_args.kwargs["payment_intent"] == "pi_test_123456"

    # Spot must be released to 'available'
    db_session.refresh(spot)
    assert spot.status == "available"
    assert spot.locked_until is None


def test_refund_stripe_order_failure_502(client: TestClient, db_session: Session):
    """When Stripe Refund API fails, returns 502 Bad Gateway and does not release spot."""
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="R-02")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="cancellation_requested")

    with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123"), \
         patch("stripe.Refund.create", side_effect=stripe.StripeError("Stripe API down")):
        res = client.post(
            f"/api/v1/events/{event['id']}/orders/{order.id}/refund",
            json={"reason": "Test fail"},
        )
        assert res.status_code == 502
        assert "Stripe API down" in res.json()["detail"]

    # Spot remains reserved
    db_session.refresh(spot)
    assert spot.status == "reserved"


def test_refund_offline_order_no_stripe_call(client: TestClient, db_session: Session):
    """Refunding an offline order (check/cash) updates status and frees spots without calling Stripe."""
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="R-03")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(
        db_session,
        uuid.UUID(event["id"]),
        spot,
        status="cancellation_requested",
        payment_method="check",
    )

    with patch("stripe.Refund.create") as mock_refund:
        res = client.post(
            f"/api/v1/events/{event['id']}/orders/{order.id}/refund",
            json={"reason": "Chèque restitué à l'exposant"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "refunded"
        assert "Remboursement hors-ligne validé" in (data["admin_notes"] or "")
        mock_refund.assert_not_called()

    db_session.refresh(spot)
    assert spot.status == "available"


def test_refund_idempotency(client: TestClient, db_session: Session):
    """Calling refund on already refunded order returns 200 without calling Stripe."""
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="R-04")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="refunded")

    with patch("stripe.Refund.create") as mock_refund:
        res = client.post(
            f"/api/v1/events/{event['id']}/orders/{order.id}/refund",
            json={"reason": "Double clic"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "refunded"
        mock_refund.assert_not_called()


def test_refund_invalid_order_status(client: TestClient, db_session: Session):
    """Attempting to refund an order with invalid status (e.g., rejected) returns 400."""
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="R-05")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="rejected")

    res = client.post(
        f"/api/v1/events/{event['id']}/orders/{order.id}/refund",
        json={"reason": "Invalide"},
    )
    assert res.status_code == 400


def test_reject_cancellation_request_success(client: TestClient, db_session: Session):
    """Given a cancellation_requested order, rejecting reverts it to confirmed, keeps spots reserved."""
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="REJ-01")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="cancellation_requested")

    res = client.post(
        f"/api/v1/events/{event['id']}/orders/{order.id}/reject-cancellation",
        json={"reason": "Délai de rétractation de 7 jours dépassé"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "confirmed"
    assert "Délai de rétractation de 7 jours dépassé" in (data["admin_notes"] or "")

    # Spot must remain reserved
    db_session.refresh(spot)
    assert spot.status == "reserved"


def test_reject_cancellation_request_empty_reason_fails(client: TestClient, db_session: Session):
    """Rejecting cancellation without a non-empty reason is blocked with 422 validation error."""
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="REJ-02")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="cancellation_requested")

    res = client.post(
        f"/api/v1/events/{event['id']}/orders/{order.id}/reject-cancellation",
        json={"reason": "    "},
    )
    assert res.status_code in (400, 422)


def test_reject_cancellation_on_non_requested_status(client: TestClient, db_session: Session):
    """Rejecting cancellation on an order that was not in cancellation_requested returns 400."""
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="REJ-03")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="pending")

    res = client.post(
        f"/api/v1/events/{event['id']}/orders/{order.id}/reject-cancellation",
        json={"reason": "Invalide"},
    )
    assert res.status_code == 400


def test_bulk_cancel_invalid_confirmation(client: TestClient, db_session: Session):
    """Bulk cancellation is blocked if confirmation text does not match CONFIRMER, ANNULER or event title."""
    event = create_test_event(client, title="Brocante d'Automne")
    res = client.post(
        f"/api/v1/events/{event['id']}/cancel-and-refund-all",
        json={"confirmation": "OUI", "reason": "Mauvais mot"},
    )
    assert res.status_code == 400
    assert "Confirmation invalide" in res.json()["detail"]


def test_bulk_cancel_and_refund_all_success(client: TestClient, db_session: Session):
    """Bulk cancellation processes all active orders, sets event to cancelled, frees all spots."""
    event = create_test_event(client, title="Brocante Pluvieuse")
    s1_data = create_test_spot(client, event["id"], label="B-01")
    s2_data = create_test_spot(client, event["id"], label="B-02")
    s3_data = create_test_spot(client, event["id"], label="B-03")
    s4_data = create_test_spot(client, event["id"], label="B-04")

    s1 = db_session.query(Spot).filter(Spot.id == uuid.UUID(s1_data["id"])).first()
    s2 = db_session.query(Spot).filter(Spot.id == uuid.UUID(s2_data["id"])).first()
    s3 = db_session.query(Spot).filter(Spot.id == uuid.UUID(s3_data["id"])).first()
    s4 = db_session.query(Spot).filter(Spot.id == uuid.UUID(s4_data["id"])).first()

    # 1. Stripe confirmed
    o1 = create_test_order(db_session, uuid.UUID(event["id"]), s1, status="confirmed", stripe_pi="pi_b1")
    # 2. Stripe cancellation_requested
    o2 = create_test_order(db_session, uuid.UUID(event["id"]), s2, status="cancellation_requested", stripe_pi="pi_b2")
    # 3. Offline cash confirmed
    o3 = create_test_order(db_session, uuid.UUID(event["id"]), s3, status="confirmed", payment_method="cash")
    # 4. Pending approval
    o4 = create_test_order(db_session, uuid.UUID(event["id"]), s4, status="pending_approval", stripe_pi="pi_b4")

    with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123"), \
         patch("stripe.Refund.create") as mock_refund, \
         patch("stripe.PaymentIntent.cancel") as mock_cancel:
        mock_refund.return_value = MagicMock(id="re_bulk")
        mock_cancel.return_value = MagicMock(id="pi_b4", status="canceled")

        # Confirmation using event title
        res = client.post(
            f"/api/v1/events/{event['id']}/cancel-and-refund-all",
            json={
                "confirmation": "Brocante Pluvieuse",
                "reason": "Intempéries majeures et vigilance rouge",
            },
        )
        assert res.status_code == 200, res.text
        report = res.json()
        assert report["total_processed"] == 4
        assert report["refunded_count"] == 3  # o1, o2, o3
        assert report["cancelled_count"] == 1  # o4
        assert report["failed_count"] == 0
        assert report["event_status"] == "cancelled"

        # 2 Stripe refunds called (o1, o2)
        assert mock_refund.call_count == 2
        # 1 Stripe cancel called (o4)
        mock_cancel.assert_called_once()

    # Event must be marked cancelled
    ev_db = db_session.query(Event).filter(Event.id == uuid.UUID(event["id"])).first()
    assert ev_db.status == "cancelled"

    # All spots must be available
    for sp in [s1, s2, s3, s4]:
        db_session.refresh(sp)
        assert sp.status == "available"


def test_bulk_cancel_resilience_on_card_error(client: TestClient, db_session: Session):
    """When a refund fails for one card, bulk cancel does not crash and continues for others."""
    event = create_test_event(client, title="Brocante Aléas")
    s1_data = create_test_spot(client, event["id"], label="ERR-01")
    s2_data = create_test_spot(client, event["id"], label="ERR-02")
    s1 = db_session.query(Spot).filter(Spot.id == uuid.UUID(s1_data["id"])).first()
    s2 = db_session.query(Spot).filter(Spot.id == uuid.UUID(s2_data["id"])).first()

    o1 = create_test_order(db_session, uuid.UUID(event["id"]), s1, status="confirmed", stripe_pi="pi_err1")
    o2 = create_test_order(db_session, uuid.UUID(event["id"]), s2, status="confirmed", stripe_pi="pi_err2")

    def mock_refund_effect(**kwargs):
        if kwargs.get("payment_intent") == "pi_err1":
            raise stripe.StripeError("Card expired or refund rejected")
        return MagicMock(id="re_ok")

    with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123"), \
         patch("stripe.Refund.create", side_effect=mock_refund_effect):
        res = client.post(
            f"/api/v1/events/{event['id']}/cancel-and-refund-all",
            json={"confirmation": "CONFIRMER", "reason": "Annulation globale"},
        )
        assert res.status_code == 200, res.text
        report = res.json()
        assert report["total_processed"] == 2
        assert report["refunded_count"] == 1
        assert report["failed_count"] == 1
        assert len(report["errors"]) == 1
        assert "Card expired or refund rejected" in report["errors"][0]

    # Event is still marked cancelled and spots freed
    ev_db = db_session.query(Event).filter(Event.id == uuid.UUID(event["id"])).first()
    assert ev_db.status == "cancelled"
    db_session.refresh(s1)
    db_session.refresh(s2)
    assert s1.status == "available"
    assert s2.status == "available"


def test_webhook_charge_refunded_sync(client: TestClient, db_session: Session):
    """Webhook charge.refunded updates order status to refunded and frees spots idempotently."""
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="WH-01")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="confirmed", stripe_pi="pi_wh_refund")

    mock_event = {
        "id": "evt_charge_refunded_test",
        "type": "charge.refunded",
        "data": {
            "object": {
                "id": "ch_wh_test",
                "payment_intent": "pi_wh_refund",
                "metadata": {"order_id": str(order.id)},
                "amount_refunded": spot.price_cents,
                "refunded": True,
            }
        },
    }

    with patch.object(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET), \
         patch("stripe.Webhook.construct_event", return_value=mock_event):
        res = client.post(
            "/api/v1/webhooks/stripe",
            headers={"Stripe-Signature": "t=123,v1=fake_signature"},
            content=b"dummy_payload",
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "success"
        assert data["order_status"] == "refunded"

    db_session.refresh(order)
    assert order.status == "refunded"
    db_session.refresh(spot)
    assert spot.status == "available"

    # Second invocation is idempotent
    with patch.object(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET), \
         patch("stripe.Webhook.construct_event", return_value=mock_event):
        res2 = client.post(
            "/api/v1/webhooks/stripe",
            headers={"Stripe-Signature": "t=123,v1=fake_signature"},
            content=b"dummy_payload",
        )
        assert res2.status_code == 200


def test_reject_cancellation_idempotency_and_invalid_cases(client: TestClient, db_session: Session):
    """Calling reject-cancellation twice returns 200 (idempotent), but rejecting a fresh confirmed order returns 400."""
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="REJ-IDEM-01")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="cancellation_requested")

    # 1. First rejection succeeds
    res1 = client.post(
        f"/api/v1/events/{event['id']}/orders/{order.id}/reject-cancellation",
        json={"reason": "Demande tardive"},
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "confirmed"

    # 2. Duplicate rejection returns 200 idempotently
    res2 = client.post(
        f"/api/v1/events/{event['id']}/orders/{order.id}/reject-cancellation",
        json={"reason": "Demande tardive (rappel)"},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "confirmed"

    # 3. Rejecting a clean confirmed order that never asked for cancellation returns 400
    spot2_data = create_test_spot(client, event["id"], label="REJ-IDEM-02")
    spot2 = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot2_data["id"])).first()
    fresh_order = create_test_order(db_session, uuid.UUID(event["id"]), spot2, status="confirmed")

    res3 = client.post(
        f"/api/v1/events/{event['id']}/orders/{fresh_order.id}/reject-cancellation",
        json={"reason": "Raison non applicable"},
    )
    assert res3.status_code == 400
    assert "aucune demande d'annulation" in res3.json()["detail"].lower()


def test_direct_refund_of_confirmed_order(client: TestClient, db_session: Session):
    """Manager can directly refund a confirmed order even without prior cancellation request."""
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="DIR-01")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="confirmed", stripe_pi="pi_direct_123")

    with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123"), \
         patch("stripe.Refund.create") as mock_refund:
        mock_refund.return_value = MagicMock(id="re_direct", status="succeeded")

        res = client.post(
            f"/api/v1/events/{event['id']}/orders/{order.id}/refund",
            json={"reason": "Geste commercial accordé au téléphone"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "refunded"
        assert "Geste commercial accordé au téléphone" in (data["admin_notes"] or "")

        mock_refund.assert_called_once()
        assert mock_refund.call_args.kwargs["payment_intent"] == "pi_direct_123"

    db_session.refresh(spot)
    assert spot.status == "available"


def test_webhook_charge_refunded_partial_ignored(client: TestClient, db_session: Session):
    """Webhook charge.refunded with refunded=False (partial refund) is ignored and does not release spot."""
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="WH-PART-01")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="confirmed", stripe_pi="pi_partial")

    mock_event = {
        "id": "evt_charge_refunded_partial",
        "type": "charge.refunded",
        "data": {
            "object": {
                "id": "ch_partial",
                "payment_intent": "pi_partial",
                "metadata": {"order_id": str(order.id)},
                "amount_refunded": 100,  # 1€ out of full price
                "refunded": False,  # Partial refund!
            }
        },
    }

    with patch.object(settings, "STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET), \
         patch("stripe.Webhook.construct_event", return_value=mock_event):
        res = client.post(
            "/api/v1/webhooks/stripe",
            headers={"Stripe-Signature": "t=123,v1=fake_signature"},
            content=b"dummy_payload",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ignored"
        assert data["reason"] == "partial_refund"

    db_session.refresh(order)
    assert order.status == "confirmed"
    db_session.refresh(spot)
    assert spot.status == "reserved"


def test_bulk_cancel_preserves_blocked_spots(client: TestClient, db_session: Session):
    """Emergency bulk cancellation releases reserved/locked spots, but preserves physically blocked spots."""
    event = create_test_event(client, title="Brocante avec Obstacles")
    s1_data = create_test_spot(client, event["id"], label="ACTIVE-01")
    s2_data = create_test_spot(client, event["id"], label="TREE-01")

    s1 = db_session.query(Spot).filter(Spot.id == uuid.UUID(s1_data["id"])).first()
    s2 = db_session.query(Spot).filter(Spot.id == uuid.UUID(s2_data["id"])).first()
    s2.status = "blocked"
    db_session.commit()

    order = create_test_order(db_session, uuid.UUID(event["id"]), s1, status="confirmed", stripe_pi="pi_obs")

    with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123"), \
         patch("stripe.Refund.create") as mock_refund:
        mock_refund.return_value = MagicMock(id="re_obs")

        res = client.post(
            f"/api/v1/events/{event['id']}/cancel-and-refund-all",
            json={"confirmation": "CONFIRMER", "reason": "Arrêté préfectoral"},
        )
        assert res.status_code == 200, res.text

    # s1 released to available, s2 MUST remain blocked
    db_session.refresh(s1)
    db_session.refresh(s2)
    assert s1.status == "available"
    assert s2.status == "blocked"


def test_booking_blocked_on_cancelled_event(client: TestClient, db_session: Session):
    """Once an event is cancelled, public spot locking, order submission, and manual bookings raise 409."""
    event = create_test_event(client, title="Événement Annulé Test")
    ev_db = db_session.query(Event).filter(Event.id == uuid.UUID(event["id"])).first()
    ev_db.status = "cancelled"
    db_session.commit()

    spot_data = create_test_spot(client, event["id"], label="LOCK-01")

    # 1. lock public spot -> 409
    res_lock = client.post(
        f"/api/v1/public/events/{event['id']}/spots/{spot_data['id']}/lock",
        json={"session_token": "sess_123"},
    )
    assert res_lock.status_code == 409
    assert "annulé" in res_lock.json()["detail"]

    # 2. submit public order -> 409
    res_order = client.post(
        f"/api/v1/public/events/{event['id']}/orders",
        json={
            "session_token": "sess_123",
            "first_name": "Jean",
            "last_name": "Dupont",
            "email": "jean@dupont.fr",
            "phone": "0600000000",
            "street_address": "1 rue de la Paix",
            "postal_code": "75001",
            "city": "Paris",
            "honor_declaration_accepted": True,
        },
    )
    assert res_order.status_code == 409
    assert "annulé" in res_order.json()["detail"]

    # 3. manual admin booking -> 409
    res_manual = client.post(
        f"/api/v1/events/{event['id']}/orders/manual",
        json={
            "first_name": "Paul",
            "last_name": "Durand",
            "phone": "0612345678",
            "street_address": "5 rue Verte",
            "postal_code": "35000",
            "city": "Rennes",
            "spot_ids": [spot_data["id"]],
            "payment_method": "cash",
        },
    )
    assert res_manual.status_code == 409
    assert "annulé" in res_manual.json()["detail"]

