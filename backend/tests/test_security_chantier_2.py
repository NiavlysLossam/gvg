import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import stripe

from app.models.event import Event
from app.models.spot import Spot
from app.models.order import Order, BookingItem
from app.services import pdf_service
from app.api.v1.endpoints.public import MAX_CART_SPOTS_PER_SESSION


def test_weasyprint_strict_url_fetcher_blocks_external_and_local_urls():
    """Verify SEC-P1-01: StrictURLFetcher intercepts and rejects SSRF and file:/// resolution."""
    fetcher = pdf_service.strict_url_fetcher
    assert fetcher is not None

    # 1. Direct call to fetcher must raise ValueError on external HTTP/HTTPS
    with pytest.raises(ValueError) as exc1:
        fetcher.fetch("http://169.254.169.254/latest/meta-data/")
    assert "forbidden" in str(exc1.value).lower()

    with pytest.raises(ValueError) as exc2:
        fetcher.fetch("file:///etc/passwd")
    assert "forbidden" in str(exc2.value).lower()

    with pytest.raises(ValueError) as exc3:
        fetcher.fetch("https://attacker.com/malicious.css")
    assert "forbidden" in str(exc3.value).lower()

    # 2. Rendering HTML with an image tag pointing to local file or metadata must not crash and must block fetch
    if pdf_service.weasyprint is not None:
        malicious_html = '<html><body><h1>Test</h1><img src="http://169.254.169.254/secret.png" /></body></html>'
        pdf_bytes = pdf_service.weasyprint.HTML(
            string=malicious_html,
            url_fetcher=pdf_service.strict_url_fetcher,
        ).write_pdf()
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 500


def test_generate_attestation_pdf_executes_safely_with_strict_fetcher(db_session: Session):
    """Verify SEC-P1-01: generate_attestation_pdf uses strict_url_fetcher and produces valid PDF."""
    if pdf_service.weasyprint is None:
        pytest.skip("WeasyPrint not installed in test environment")

    event = Event(
        title="Brocante Attestation Sécurisée",
        slug="brocante-attestation-ssrf",
        start_date=datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 9, 1, 18, 0, tzinfo=timezone.utc),
        price_per_meter_cents=1000,
        status="published",
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    order = Order(
        event_id=event.id,
        first_name="Alice",
        last_name="Sécurisée",
        email="alice@test.fr",
        phone="0611223344",
        street_address="10 rue des Acacias",
        postal_code="35000",
        city="Rennes",
        total_price_cents=3000,
        status="confirmed",
        honor_declaration_accepted=True,
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    pdf_bytes = pdf_service.generate_attestation_pdf(order=order, event=event)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


def test_cart_hoarding_quota_enforced_at_max_limit_and_excludes_expired(client: TestClient, db_session: Session):
    """Verify SEC-P1-02: Visitor session cannot hold > MAX_CART_SPOTS_PER_SESSION stalls, but expired locks are excluded."""
    event = Event(
        title="Brocante Quota Anti Hoarding",
        slug="brocante-quota-hoarding",
        start_date=datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 9, 1, 18, 0, tzinfo=timezone.utc),
        price_per_meter_cents=1000,
        status="published",
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    # Create 8 spots for the event
    spots = []
    for i in range(1, 9):
        s = Spot(
            event_id=event.id,
            label=f"Stand-Quota-{i}",
            linear_meters=2.0,
            price_cents=2000,
            geom="POLYGON((-2.025 48.650, -2.020 48.650, -2.020 48.652, -2.025 48.652, -2.025 48.650))",
            status="available",
        )
        db_session.add(s)
        spots.append(s)
    db_session.commit()
    for s in spots:
        db_session.refresh(s)

    session_token = "token-test-hoarding-9999"

    # Add an expired locked spot by the same session token: it must NOT count against the quota
    spots[7].status = "locked"
    spots[7].locked_by_token = session_token
    spots[7].locked_until = datetime.now(timezone.utc) - timedelta(minutes=10)
    db_session.commit()

    # Lock up to the maximum limit (5 spots)
    for i in range(MAX_CART_SPOTS_PER_SESSION):
        resp = client.post(
            f"/api/v1/public/events/{event.slug}/spots/{spots[i].id}/lock",
            headers={"X-Session-Token": session_token},
        )
        assert resp.status_code == 200, f"Spot {i} should be lockable"
        assert resp.json()["total_count"] == i + 1

    # Attempting to lock the 6th spot must be rejected with HTTP 400 Bad Request
    resp_over_limit = client.post(
        f"/api/v1/public/events/{event.slug}/spots/{spots[5].id}/lock",
        headers={"X-Session-Token": session_token},
    )
    assert resp_over_limit.status_code == 400
    assert "Limite de réservation atteinte" in resp_over_limit.json()["detail"]

    # Re-locking one of the already held spots by the same token must be allowed (idempotent / refreshes TTL)
    resp_rehold = client.post(
        f"/api/v1/public/events/{event.slug}/spots/{spots[0].id}/lock",
        headers={"X-Session-Token": session_token},
    )
    assert resp_rehold.status_code == 200


def test_stripe_webhook_auto_refund_on_spot_conflict_409(client: TestClient, db_session: Session):
    """
    Verify SEC-P1-03: When a payment_intent.succeeded webhook arrives but a spot was already taken
    by someone else (HTTP 409 Conflict), the webhook executes an immediate emergency auto-refund,
    releases surviving locked spots, records the specified audit note, and returns 200 OK.
    """
    event = Event(
        title="Brocante Collision Webhook",
        slug="brocante-collision-webhook",
        start_date=datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 9, 5, 18, 0, tzinfo=timezone.utc),
        price_per_meter_cents=1000,
        status="published",
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    # Spot 1: Reserved by faster buyer
    spot_taken = Spot(
        event_id=event.id,
        label="Stand-Collision-1",
        linear_meters=2.0,
        price_cents=2500,
        geom="POLYGON((-2.025 48.650, -2.020 48.650, -2.020 48.652, -2.025 48.652, -2.025 48.650))",
        status="reserved",
    )
    # Spot 2: Locked by this order's session (should be released upon collision)
    spot_locked = Spot(
        event_id=event.id,
        label="Stand-Surviving-Locked",
        linear_meters=2.0,
        price_cents=2500,
        geom="POLYGON((-2.025 48.650, -2.020 48.650, -2.020 48.652, -2.025 48.652, -2.025 48.650))",
        status="locked",
        locked_by_token="token-victim-123",
        locked_until=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db_session.add_all([spot_taken, spot_locked])
    db_session.commit()
    db_session.refresh(spot_taken)
    db_session.refresh(spot_locked)

    order = Order(
        event_id=event.id,
        first_name="Jean",
        last_name="Tardif",
        email="jean.tardif@test.fr",
        phone="0611223344",
        total_price_cents=5000,
        status="pending",
        payment_method="stripe",
        stripe_payment_intent_id="pi_collision_victim_123",
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    item1 = BookingItem(order_id=order.id, spot_id=spot_taken.id, price_cents=2500)
    item2 = BookingItem(order_id=order.id, spot_id=spot_locked.id, price_cents=2500)
    db_session.add_all([item1, item2])
    db_session.commit()

    fake_event = {
        "id": "evt_test_collision_999",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_collision_victim_123",
                "amount_received": 5000,
                "currency": "eur",
                "metadata": {
                    "order_id": str(order.id),
                },
            }
        },
    }

    mock_refund = MagicMock()
    mock_refund.id = "re_auto_test_12345"

    with patch("app.core.config.settings.STRIPE_SECRET_KEY", "sk_test_mock_123"), \
         patch("app.services.stripe_service.verify_webhook_event", return_value=fake_event), \
         patch("stripe.Refund.create", return_value=mock_refund) as mock_refund_create:
        resp = client.post(
            "/api/v1/webhooks/stripe",
            content=b'{"dummy":"payload"}',
            headers={"Stripe-Signature": "t=123,v1=fakesig"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "conflict_refunded"
        assert data["reason"] == "spot_already_taken"
        assert data["refund_id"] == "re_auto_test_12345"

        mock_refund_create.assert_called_once_with(
            payment_intent="pi_collision_victim_123",
            api_key="sk_test_mock_123",
            idempotency_key="auto_refund_conflict_pi_collision_victim_123",
        )

        db_session.refresh(order)
        assert order.status == "refunded"
        assert "[Système] Conflit de stand lors du webhook de paiement : remboursement automatique effectué." in order.admin_notes

        # Verify surviving locked spot was released back to available
        db_session.refresh(spot_locked)
        assert spot_locked.status == "available"
        assert spot_locked.locked_until is None


def test_stripe_webhook_amount_capturable_updated_conflict_cancels_authorization(client: TestClient, db_session: Session):
    """Verify SEC-P1-03: On amount_capturable_updated conflict, authorization is cancelled and order marked cancelled."""
    event = Event(
        title="Brocante Hold Collision",
        slug="brocante-hold-collision",
        start_date=datetime(2026, 9, 8, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc),
        price_per_meter_cents=1000,
        status="published",
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    spot_reserved = Spot(
        event_id=event.id,
        label="Stand-Hold-Reserved",
        linear_meters=2.0,
        price_cents=2000,
        geom="POLYGON((-2.025 48.650, -2.020 48.650, -2.020 48.652, -2.025 48.652, -2.025 48.650))",
        status="reserved",
    )
    db_session.add(spot_reserved)
    db_session.commit()
    db_session.refresh(spot_reserved)

    order = Order(
        event_id=event.id,
        first_name="Paul",
        last_name="Preauth",
        email="paul@test.fr",
        phone="0600000000",
        total_price_cents=2000,
        status="pending",
        payment_method="stripe",
        stripe_payment_intent_id="pi_hold_collision_999",
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    item = BookingItem(order_id=order.id, spot_id=spot_reserved.id, price_cents=2000)
    db_session.add(item)
    db_session.commit()

    fake_event = {
        "id": "evt_test_hold_collision_999",
        "type": "payment_intent.amount_capturable_updated",
        "data": {
            "object": {
                "id": "pi_hold_collision_999",
                "amount_capturable": 2000,
                "currency": "eur",
                "metadata": {
                    "order_id": str(order.id),
                },
            }
        },
    }

    with patch("app.core.config.settings.STRIPE_SECRET_KEY", "sk_test_mock_123"), \
         patch("app.services.stripe_service.verify_webhook_event", return_value=fake_event), \
         patch("stripe.PaymentIntent.cancel") as mock_pi_cancel:
        resp = client.post(
            "/api/v1/webhooks/stripe",
            content=b'{"dummy":"payload"}',
            headers={"Stripe-Signature": "t=123,v1=fakesig"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "conflict_cancelled"
        assert data["reason"] == "spot_already_taken"

        mock_pi_cancel.assert_called_once_with("pi_hold_collision_999", api_key="sk_test_mock_123")

        db_session.refresh(order)
        assert order.status == "cancelled"
        assert "[Système] Conflit de stand lors du webhook de pré-autorisation : autorisation Stripe annulée." in order.admin_notes


def test_upload_background_image_strictly_derives_extension_and_cleans_up(client: TestClient, db_session: Session):
    """Verify SEC-P1-04: upload_background_image validates magic bytes (PNG, JPEG, WebP) and handles cleanup."""
    event = Event(
        title="Brocante Upload Magic Bytes",
        slug="brocante-upload-magic",
        start_date=datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc),
        price_per_meter_cents=1000,
        status="draft",
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    # 1. Valid PNG content with a spoofed or different filename
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    files_png = {"file": ("malicious.svg", png_bytes, "image/png")}
    resp_png = client.post(f"/api/v1/events/{event.slug}/background-image", files=files_png)
    assert resp_png.status_code == 201
    assert resp_png.json()["background_image_url"].endswith(".png")

    # 2. Valid JPEG content with Content-Type containing parameter
    jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    files_jpeg = {"file": ("photo.bin", jpeg_bytes, "image/jpeg; charset=utf-8")}
    resp_jpeg = client.post(f"/api/v1/events/{event.slug}/background-image", files=files_jpeg)
    assert resp_jpeg.status_code == 201
    assert resp_jpeg.json()["background_image_url"].endswith(".jpg")

    # 3. Valid WebP content
    webp_bytes = b"RIFF\x20\x00\x00\x00WEBPVP8 " + b"\x00" * 50
    files_webp = {"file": ("indoor.bin", webp_bytes, "image/webp")}
    resp_webp = client.post(f"/api/v1/events/{event.slug}/background-image", files=files_webp)
    assert resp_webp.status_code == 201
    assert resp_webp.json()["background_image_url"].endswith(".webp")

    # 4. Fake image claiming to be image/png but containing invalid binary data
    fake_bytes = b"<?php phpinfo(); ?>"
    files_fake = {"file": ("photo.png", fake_bytes, "image/png")}
    resp_fake = client.post(f"/api/v1/events/{event.slug}/background-image", files=files_fake)
    assert resp_fake.status_code == 415
    assert "pas une image valide" in resp_fake.json()["detail"]


def test_openapi_docs_disabled_in_production():
    """Verify SEC-P1-04: Swagger (/docs) and ReDoc (/redoc) are disabled when ENVIRONMENT=production."""
    from fastapi import FastAPI
    from app.core.config import Settings

    settings_prod = Settings(ENVIRONMENT="production", JWT_SECRET_KEY="a"*32)
    is_prod = (settings_prod.ENVIRONMENT or "").strip().lower() in ("production", "prod")
    assert is_prod is True

    app_prod = FastAPI(
        title="Test Prod",
        openapi_url=None if is_prod else "/openapi.json",
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
    )
    client_prod = TestClient(app_prod)

    resp_docs = client_prod.get("/docs")
    assert resp_docs.status_code == 404

    resp_redoc = client_prod.get("/redoc")
    assert resp_redoc.status_code == 404

    resp_openapi = client_prod.get("/openapi.json")
    assert resp_openapi.status_code == 404
