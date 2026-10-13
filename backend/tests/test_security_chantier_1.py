import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.event import Event
from app.models.spot import Spot
from app.models.order import Order, BookingItem
from app.services import stripe_service


def test_jwt_secret_validation_in_production_and_staging():
    """Verify that Settings refuses default, placeholder, or weak JWT_SECRET_KEY in non-development environments."""
    insecure_default = "gvg_default_insecure_jwt_secret_key_change_in_production"
    template_placeholder = "changer_cette_cle_secrete_jwt_par_une_chaine_aleatoire_tres_longue"

    # 1. Default key in production, staging, and prod must fail
    for env in ("production", "staging", "prod", "preprod"):
        with pytest.raises(ValueError, match="CRITICAL SECURITY CONFIGURATION ERROR.*Refusing to start"):
            Settings(ENVIRONMENT=env, JWT_SECRET_KEY=insecure_default)

        # Template placeholder from .env.example must also fail
        with pytest.raises(ValueError, match="CRITICAL SECURITY CONFIGURATION ERROR.*Refusing to start"):
            Settings(ENVIRONMENT=env, JWT_SECRET_KEY=template_placeholder)

        # Empty or None key must fail
        with pytest.raises(ValueError, match="CRITICAL SECURITY CONFIGURATION ERROR"):
            Settings(ENVIRONMENT=env, JWT_SECRET_KEY="")

    # 2. Exact boundary tests: 31 chars fails, 32 chars passes
    key_31_chars = "a" * 31
    key_32_chars = "a" * 32
    with pytest.raises(ValueError, match="at least 32 characters long"):
        Settings(ENVIRONMENT="production", JWT_SECRET_KEY=key_31_chars)

    prod_settings_32 = Settings(ENVIRONMENT="production", JWT_SECRET_KEY=key_32_chars)
    assert prod_settings_32.JWT_SECRET_KEY == key_32_chars

    # 3. In development, default key is allowed
    dev_settings = Settings(ENVIRONMENT="development", JWT_SECRET_KEY=insecure_default)
    assert dev_settings.JWT_SECRET_KEY == insecure_default


def test_create_guest_order_prevents_pii_leak_on_reclaimed_spots(client: TestClient, db_session: Session):
    """
    Verify SEC-CRIT-01: An abandoned pending order from User A is NOT returned to User B.
    User B gets a new order, and User A's previous pending order is cancelled.
    """
    # 1. Create a published event and an available spot
    event = Event(
        title="Brocante Sécurité Anti-Fuite",
        slug="brocante-anti-fuite",
        start_date=datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 8, 1, 18, 0, tzinfo=timezone.utc),
        price_per_meter_cents=1000,
        status="published",
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    spot = Spot(
        event_id=event.id,
        label="Stand-42",
        linear_meters=3.0,
        price_cents=3000,
        geom="POLYGON((-2.025 48.650, -2.020 48.650, -2.020 48.652, -2.025 48.652, -2.025 48.650))",
        status="available",
    )
    db_session.add(spot)
    db_session.commit()
    db_session.refresh(spot)

    # 2. User A locks the spot and creates a pending order
    session_token_a = "token-user-a-12345678"
    lock_resp_a = client.post(
        f"/api/v1/public/events/{event.slug}/spots/{spot.id}/lock",
        headers={"X-Session-Token": session_token_a},
    )
    assert lock_resp_a.status_code == 200

    order_payload_a = {
        "first_name": "Alice",
        "last_name": "Dupont",
        "email": "alice.dupont@secret-corp.org",
        "phone": "0601020304",
        "street_address": "12 rue Secrète",
        "postal_code": "75001",
        "city": "Paris",
        "honor_declaration_accepted": True,
    }
    resp_a = client.post(
        f"/api/v1/public/events/{event.slug}/orders",
        json=order_payload_a,
        headers={"X-Session-Token": session_token_a},
    )
    assert resp_a.status_code == 201
    order_a_data = resp_a.json()
    assert order_a_data["first_name"] == "Alice"
    assert order_a_data["email"] == "alice.dupont@secret-corp.org"
    token_a = order_a_data["access_token"]

    # 3. Time passes: lock expires, User B claims the spot
    spot_in_db = db_session.query(Spot).filter(Spot.id == spot.id).first()
    spot_in_db.status = "available"
    spot_in_db.locked_until = None
    spot_in_db.locked_by_token = None
    db_session.commit()

    session_token_b = "token-user-b-87654321"
    lock_resp_b = client.post(
        f"/api/v1/public/events/{event.slug}/spots/{spot.id}/lock",
        headers={"X-Session-Token": session_token_b},
    )
    assert lock_resp_b.status_code == 200

    # User B now creates a guest order for the same spot
    order_payload_b = {
        "first_name": "Bob",
        "last_name": "Martin",
        "email": "bob.martin@public-mail.org",
        "phone": "0699887766",
        "street_address": "45 avenue Publique",
        "postal_code": "69001",
        "city": "Lyon",
        "honor_declaration_accepted": True,
    }
    resp_b = client.post(
        f"/api/v1/public/events/{event.slug}/orders",
        json=order_payload_b,
        headers={"X-Session-Token": session_token_b},
    )
    assert resp_b.status_code == 201
    order_b_data = resp_b.json()

    # CRITICAL SECURITY ASSERTIONS:
    # Bob MUST NOT receive Alice's order, PII, or access token!
    assert order_b_data["id"] != order_a_data["id"]
    assert order_b_data["order_number"] != order_a_data["order_number"]
    assert order_b_data["access_token"] != token_a
    assert order_b_data["first_name"] == "Bob"
    assert order_b_data["email"] == "bob.martin@public-mail.org"
    assert "Alice" not in resp_b.text
    assert "alice.dupont@secret-corp.org" not in resp_b.text

    # Alice's order must be marked cancelled in DB with specific audit note
    order_a_in_db = db_session.query(Order).filter(Order.id == uuid.UUID(order_a_data["id"])).first()
    assert order_a_in_db.status == "cancelled"
    assert "[Système] Commande temporaire non finalisée annulée suite à réattribution des stands." in order_a_in_db.admin_notes


def test_create_guest_order_reuses_matching_order_and_extends_lock(client: TestClient, db_session: Session):
    """Verify that the same user resubmitting the same spots updates contact info and extends lock TTL."""
    event = Event(
        title="Brocante Réutilisation Légitime",
        slug="brocante-reuse",
        start_date=datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 8, 1, 18, 0, tzinfo=timezone.utc),
        price_per_meter_cents=1000,
        status="published",
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    spot = Spot(
        event_id=event.id,
        label="Stand-Reuse-1",
        linear_meters=3.0,
        price_cents=3000,
        geom="POLYGON((-2.025 48.650, -2.020 48.650, -2.020 48.652, -2.025 48.652, -2.025 48.650))",
        status="available",
    )
    db_session.add(spot)
    db_session.commit()
    db_session.refresh(spot)

    session_token = "token-user-reuse-1111"
    lock_resp = client.post(
        f"/api/v1/public/events/{event.slug}/spots/{spot.id}/lock",
        headers={"X-Session-Token": session_token},
    )
    assert lock_resp.status_code == 200

    payload_initial = {
        "first_name": "Claire",
        "last_name": "Lemoine",
        "email": "claire@test.fr",
        "phone": "0612345678",
        "street_address": "10 rue des Fleurs",
        "postal_code": "35000",
        "city": "Rennes",
        "honor_declaration_accepted": True,
    }
    resp1 = client.post(
        f"/api/v1/public/events/{event.slug}/orders",
        json=payload_initial,
        headers={"X-Session-Token": session_token},
    )
    assert resp1.status_code == 201
    order1 = resp1.json()

    # User updates their address and phone in the form and resubmits
    payload_updated = {
        "first_name": "Claire",
        "last_name": "Lemoine",
        "email": "CLAIRE@TEST.FR",  # test case insensitivity
        "phone": "0699999999",
        "street_address": "12 rue des Fleurs Bis",
        "postal_code": "35000",
        "city": "Rennes",
        "honor_declaration_accepted": True,
    }
    resp2 = client.post(
        f"/api/v1/public/events/{event.slug}/orders",
        json=payload_updated,
        headers={"X-Session-Token": session_token},
    )
    assert resp2.status_code == 201
    order2 = resp2.json()

    # Order ID must be preserved, phone and address updated
    assert order2["id"] == order1["id"]
    assert order2["phone"] == "0699999999"
    assert order2["street_address"] == "12 rue des Fleurs Bis"

    # Spot locked_until must be extended (greater than now + 10 minutes)
    db_session.refresh(spot)
    assert spot.locked_until is not None
    locked_until = spot.locked_until.replace(tzinfo=timezone.utc) if spot.locked_until.tzinfo is None else spot.locked_until
    now = datetime.now(timezone.utc)
    assert locked_until > now + timedelta(minutes=10)


def test_process_order_refund_preserves_spots_on_partial_refund(db_session: Session):
    """
    Verify SEC-CRIT-03: Partial refund keeps spots reserved and order confirmed.
    Only full refund releases spots to available and marks order refunded.
    """
    # 1. Setup event, spot and confirmed order
    event = Event(
        title="Brocante Remboursement Partiel",
        slug="brocante-remboursement",
        start_date=datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 9, 1, 18, 0, tzinfo=timezone.utc),
        price_per_meter_cents=1000,
        status="published",
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    spot = Spot(
        event_id=event.id,
        label="Stand-Partial-1",
        linear_meters=4.0,
        price_cents=4000,
        geom="POLYGON((-2.025 48.650, -2.020 48.650, -2.020 48.652, -2.025 48.652, -2.025 48.650))",
        status="reserved",
    )
    db_session.add(spot)
    db_session.commit()
    db_session.refresh(spot)

    order = Order(
        event_id=event.id,
        first_name="Jean",
        last_name="Exposant",
        email="jean@test.fr",
        phone="0611223344",
        total_price_cents=4000,
        status="cancellation_requested",  # test settling from cancellation_requested
        payment_method="check",  # offline payment to test without Stripe API call
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    booking_item = BookingItem(
        order_id=order.id,
        spot_id=spot.id,
        price_cents=4000,
    )
    db_session.add(booking_item)
    db_session.commit()

    # 2. Perform a PARTIAL refund (10.00 € out of 40.00 €)
    refunded_order_partial = stripe_service.process_order_refund(
        order=order,
        amount_cents=1000,
        reason="Geste commercial intempéries",
        db=db_session,
    )

    # Spots MUST STILL BE RESERVED and status settled to confirmed!
    db_session.refresh(spot)
    assert spot.status == "reserved"
    assert refunded_order_partial.status == "confirmed"
    assert "Remboursement partiel validé : 10.00 €" in (refunded_order_partial.admin_notes or "")

    # 3. Perform an EXPLICIT FULL refund (remaining 4000 cents >= order.total_price_cents)
    refunded_order_full = stripe_service.process_order_refund(
        order=order,
        amount_cents=4000,  # Explicit amount >= total_price_cents
        reason="Annulation complète",
        db=db_session,
    )

    # Spots MUST NOW BE RELEASED and status refunded!
    db_session.refresh(spot)
    assert spot.status == "available"
    assert spot.locked_until is None
    assert spot.locked_by_token is None
    assert refunded_order_full.status == "refunded"


def test_hold_order_for_approval_idempotency_and_spot_collision(db_session: Session):
    """Verify that hold_order_for_approval handles idempotent retries cleanly and rejects collisions with HTTP 409."""
    event = Event(
        title="Brocante Modération Idempotence",
        slug="brocante-moderation",
        start_date=datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 9, 1, 18, 0, tzinfo=timezone.utc),
        price_per_meter_cents=1000,
        manual_approval_required=True,
        status="published",
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    spot = Spot(
        event_id=event.id,
        label="Stand-Mod-1",
        linear_meters=2.0,
        price_cents=2000,
        geom="POLYGON((-2.025 48.650, -2.020 48.650, -2.020 48.652, -2.025 48.652, -2.025 48.650))",
        status="available",
    )
    db_session.add(spot)
    db_session.commit()
    db_session.refresh(spot)

    order = Order(
        event_id=event.id,
        first_name="Marc",
        last_name="Modéré",
        email="marc@test.fr",
        phone="0600000000",
        total_price_cents=2000,
        status="pending",
        payment_method="stripe",
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    booking_item = BookingItem(
        order_id=order.id,
        spot_id=spot.id,
        price_cents=2000,
    )
    db_session.add(booking_item)
    db_session.commit()

    # 1. Hold order for approval transitions spots to reserved and order to pending_approval
    held_order = stripe_service.hold_order_for_approval(
        db=db_session,
        payment_intent_id="pi_test_hold_123",
        order_id=str(order.id),
        amount_received=2000,
        currency="eur",
    )
    assert held_order.status == "pending_approval"
    db_session.refresh(spot)
    assert spot.status == "reserved"

    # 2. Idempotent retry: webhook redelivery must return held order without 409
    held_order_retry = stripe_service.hold_order_for_approval(
        db=db_session,
        payment_intent_id="pi_test_hold_123",
        order_id=str(order.id),
        amount_received=2000,
        currency="eur",
    )
    assert held_order_retry.status == "pending_approval"

    # 3. Collision: another pending order for the same reserved spot must raise HTTP 409
    order_conflict = Order(
        event_id=event.id,
        first_name="Paul",
        last_name="Conflit",
        email="paul@test.fr",
        phone="0611111111",
        total_price_cents=2000,
        status="pending",
        payment_method="stripe",
    )
    db_session.add(order_conflict)
    db_session.commit()
    db_session.refresh(order_conflict)

    conflict_item = BookingItem(
        order_id=order_conflict.id,
        spot_id=spot.id,
        price_cents=2000,
    )
    db_session.add(conflict_item)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        stripe_service.hold_order_for_approval(
            db=db_session,
            payment_intent_id="pi_test_conflict_999",
            order_id=str(order_conflict.id),
            amount_received=2000,
            currency="eur",
        )
    assert exc_info.value.status_code == 409
    assert "Conflit de réservation" in exc_info.value.detail
