import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


def create_test_event(client: TestClient, title: str = "Vide-Grenier Annulations") -> dict:
    payload = {
        "title": title,
        "description": "Événement de test pour workflow annulation",
        "price_per_meter": 4.0,
        "map_type": "geographic",
        "start_date": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=14, hours=10)).isoformat(),
        "setup_start_time": "06:00",
        "setup_end_time": "08:00",
        "public_start_time": "08:00",
        "public_end_time": "18:00",
        "location_address": "Place de l'Église, Rennes",
        "organizer_email": "marc@gvg.fr",
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
) -> Order:
    order = Order(
        event_id=event_id,
        first_name="Monique",
        last_name="Dupont",
        email="monique.dupont@test.fr",
        phone="0601020304",
        street_address="12 rue de la Paix",
        postal_code="35000",
        city="Rennes",
        honor_declaration_accepted=True,
        total_price_cents=spot.price_cents,
        status=status,
        payment_method=payment_method,
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


def test_cancellation_missing_token(client: TestClient, db_session: Session):
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="CAN-01")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="confirmed")

    # POST without token
    res = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}/cancellation-request",
        json={"cancellation_reason": "medical", "cancellation_comment": "Malade"},
    )
    assert res.status_code == 401
    assert "token" in res.json()["detail"].lower()


def test_cancellation_invalid_token(client: TestClient, db_session: Session):
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="CAN-02")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="confirmed")

    # POST with wrong token
    res = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}/cancellation-request?token=wrong_invalid_token",
        json={"cancellation_reason": "medical", "cancellation_comment": "Malade"},
    )
    assert res.status_code == 403
    assert "invalide" in res.json()["detail"].lower()


def test_cancellation_order_not_found(client: TestClient):
    event = create_test_event(client)
    fake_order_id = uuid.uuid4()
    res = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{fake_order_id}/cancellation-request?token=any_token",
        json={"cancellation_reason": "medical"},
    )
    assert res.status_code == 404
    assert "introuvable" in res.json()["detail"].lower()


def test_cancellation_eligible_confirmed_order_nominal(client: TestClient, db_session: Session):
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="CAN-03")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="confirmed")

    res = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}/cancellation-request?token={order.access_token}",
        json={
            "cancellation_reason": "medical",
            "cancellation_comment": "Empêchement de santé imprévu",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "cancellation_requested"
    assert data["cancellation_reason"] == "medical"
    assert data["cancellation_comment"] == "Empêchement de santé imprévu"
    assert data["cancellation_requested_at"] is not None

    # Verify DB persistence
    db_session.refresh(order)
    assert order.status == "cancellation_requested"
    assert order.cancellation_reason == "medical"
    assert order.cancellation_comment == "Empêchement de santé imprévu"
    assert order.cancellation_requested_at is not None

    # Critical boundary: spot MUST remain reserved
    db_session.refresh(spot)
    assert spot.status == "reserved"


def test_cancellation_pending_approval_order(client: TestClient, db_session: Session):
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="CAN-04")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="pending_approval")

    res = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}/cancellation-request",
        headers={"X-Access-Token": order.access_token},
        json={
            "cancellation_reason": "personal",
            "cancellation_comment": "Urgence familiale",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "cancellation_requested"
    assert data["cancellation_reason"] == "personal"

    db_session.refresh(spot)
    assert spot.status == "reserved"


def test_cancellation_idempotent_on_repeated_request(client: TestClient, db_session: Session):
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="CAN-05")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="confirmed")

    # First request
    res1 = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}/cancellation-request?token={order.access_token}",
        json={"cancellation_reason": "weather", "cancellation_comment": "Pluie"},
    )
    assert res1.status_code == 200
    first_time = res1.json()["cancellation_requested_at"]

    # Second request: idempotent 200
    res2 = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}/cancellation-request?token={order.access_token}",
        json={"cancellation_reason": "weather", "cancellation_comment": "Pluie"},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "cancellation_requested"
    assert res2.json()["cancellation_requested_at"] == first_time


def test_cancellation_empty_reason_rejected(client: TestClient, db_session: Session):
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="CAN-06")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="confirmed")

    res = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}/cancellation-request?token={order.access_token}",
        json={"cancellation_reason": "", "cancellation_comment": "Note"},
    )
    assert res.status_code in (400, 422)
    detail_str = str(res.json()["detail"]).lower()
    assert "obligatoire" in detail_str or "validation" in detail_str or "reason" in detail_str


def test_cancellation_other_reason_without_comment_rejected(client: TestClient, db_session: Session):
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="CAN-07")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="confirmed")

    # "other" without comment
    res = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}/cancellation-request?token={order.access_token}",
        json={"cancellation_reason": "other", "cancellation_comment": ""},
    )
    assert res.status_code in (400, 422)
    detail_str = str(res.json()["detail"]).lower()
    assert "autre" in detail_str or "comment" in detail_str


def test_cancellation_invalid_reason_rejected(client: TestClient, db_session: Session):
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="CAN-07B")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="confirmed")

    res = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}/cancellation-request?token={order.access_token}",
        json={"cancellation_reason": "unknown_reason", "cancellation_comment": "Test"},
    )
    assert res.status_code in (400, 422)
    detail_str = str(res.json()["detail"]).lower()
    assert "invalide" in detail_str or "medical" in detail_str


def test_cancellation_other_reason_with_comment_accepted(client: TestClient, db_session: Session):
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="CAN-08")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="confirmed")

    res = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}/cancellation-request?token={order.access_token}",
        json={"cancellation_reason": "other", "cancellation_comment": "Déménagement imprévu"},
    )
    assert res.status_code == 200
    assert res.json()["cancellation_reason"] == "other"
    assert res.json()["cancellation_comment"] == "Déménagement imprévu"


def test_cancellation_ineligible_statuses(client: TestClient, db_session: Session):
    event = create_test_event(client)

    # 1. Pending (unpaid / checkout incomplete)
    spot1_data = create_test_spot(client, event["id"], label="INEL-01")
    spot1 = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot1_data["id"])).first()
    order_pending = create_test_order(db_session, uuid.UUID(event["id"]), spot1, status="pending")
    res_pending = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order_pending.id}/cancellation-request?token={order_pending.access_token}",
        json={"cancellation_reason": "medical"},
    )
    assert res_pending.status_code == 409

    # 2. Cancelled
    spot2_data = create_test_spot(client, event["id"], label="INEL-02")
    spot2 = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot2_data["id"])).first()
    order_cancelled = create_test_order(db_session, uuid.UUID(event["id"]), spot2, status="cancelled")
    res_cancelled = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order_cancelled.id}/cancellation-request?token={order_cancelled.access_token}",
        json={"cancellation_reason": "medical"},
    )
    assert res_cancelled.status_code == 409
    assert "plus modifiable" in res_cancelled.json()["detail"].lower()

    # 3. Rejected
    spot3_data = create_test_spot(client, event["id"], label="INEL-03")
    spot3 = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot3_data["id"])).first()
    order_rejected = create_test_order(db_session, uuid.UUID(event["id"]), spot3, status="rejected")
    res_rejected = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order_rejected.id}/cancellation-request?token={order_rejected.access_token}",
        json={"cancellation_reason": "medical"},
    )
    assert res_rejected.status_code == 409
    assert "plus modifiable" in res_rejected.json()["detail"].lower()

    # 4. Refunded
    spot4_data = create_test_spot(client, event["id"], label="INEL-04")
    spot4 = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot4_data["id"])).first()
    order_refunded = create_test_order(db_session, uuid.UUID(event["id"]), spot4, status="refunded")
    res_refunded = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order_refunded.id}/cancellation-request?token={order_refunded.access_token}",
        json={"cancellation_reason": "medical"},
    )
    assert res_refunded.status_code == 409
    assert "plus modifiable" in res_refunded.json()["detail"].lower()


def test_public_get_order_exposes_cancellation_fields(client: TestClient, db_session: Session):
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="CAN-09")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="confirmed")

    # Request cancellation
    client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}/cancellation-request?token={order.access_token}",
        json={"cancellation_reason": "medical", "cancellation_comment": "Blessure"},
    )

    # GET public order
    get_res = client.get(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}?token={order.access_token}"
    )
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["status"] == "cancellation_requested"
    assert data["cancellation_reason"] == "medical"
    assert data["cancellation_comment"] == "Blessure"
    assert data["cancellation_requested_at"] is not None


def test_admin_orders_stats_and_filter_cancellation_requested(client: TestClient, db_session: Session):
    event = create_test_event(client)
    spot1_data = create_test_spot(client, event["id"], label="ADM-01")
    spot1 = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot1_data["id"])).first()
    order1 = create_test_order(db_session, uuid.UUID(event["id"]), spot1, status="confirmed")

    spot2_data = create_test_spot(client, event["id"], label="ADM-02")
    spot2 = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot2_data["id"])).first()
    order2 = create_test_order(db_session, uuid.UUID(event["id"]), spot2, status="confirmed")

    # Order 2 requests cancellation
    client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order2.id}/cancellation-request?token={order2.access_token}",
        json={"cancellation_reason": "personal", "cancellation_comment": "Empêchement familial"},
    )

    # Check dashboard stats
    stats_res = client.get(f"/api/v1/events/{event['id']}/dashboard-stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["cancellation_requested_orders_count"] == 1

    # Check order listing with cancellation_requested filter
    list_res = client.get(f"/api/v1/events/{event['id']}/orders?status=cancellation_requested")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 1
    assert list_data["items"][0]["id"] == str(order2.id)
    assert list_data["items"][0]["status"] == "cancellation_requested"
    assert list_data["items"][0]["cancellation_reason"] == "personal"
    assert list_data["items"][0]["cancellation_comment"] == "Empêchement familial"
    assert list_data["items"][0]["cancellation_requested_at"] is not None


def test_public_order_does_not_disclose_admin_notes(client: TestClient, db_session: Session):
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="SEC-01")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="confirmed")
    order.admin_notes = "CONFIDENTIAL INTERNAL NOTE"
    db_session.commit()

    # Public GET
    get_res = client.get(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}?token={order.access_token}"
    )
    assert get_res.status_code == 200
    assert "admin_notes" not in get_res.json()

    # Public POST cancellation-request
    post_res = client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}/cancellation-request?token={order.access_token}",
        json={"cancellation_reason": "medical", "cancellation_comment": "Maladie"},
    )
    assert post_res.status_code == 200
    assert "admin_notes" not in post_res.json()


def test_dashboard_stats_keeps_cancellation_requested_in_revenue(client: TestClient, db_session: Session):
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="REV-01")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="confirmed")

    # Before cancellation request
    stats_before = client.get(f"/api/v1/events/{event['id']}/dashboard-stats").json()
    assert stats_before["confirmed_orders_count"] == 1
    assert stats_before["total_revenue_cents"] == 800

    # Request cancellation
    client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}/cancellation-request?token={order.access_token}",
        json={"cancellation_reason": "weather", "cancellation_comment": "Tempête"},
    )

    # After cancellation request: should still be in revenue and confirmed_orders_count until arbitration
    stats_after = client.get(f"/api/v1/events/{event['id']}/dashboard-stats").json()
    assert stats_after["confirmed_orders_count"] == 1
    assert stats_after["total_revenue_cents"] == 800
    assert stats_after["cancellation_requested_orders_count"] == 1


def test_admin_orders_search_by_cancellation_fields(client: TestClient, db_session: Session):
    event = create_test_event(client)
    spot_data = create_test_spot(client, event["id"], label="SRCH-01")
    spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_data["id"])).first()
    order = create_test_order(db_session, uuid.UUID(event["id"]), spot, status="confirmed")

    client.post(
        f"/api/v1/public/events/{event['slug']}/orders/{order.id}/cancellation-request?token={order.access_token}",
        json={"cancellation_reason": "other", "cancellation_comment": "Déménagement exceptionnel"},
    )

    # Search by reason
    res_reason = client.get(f"/api/v1/events/{event['id']}/orders?search=other")
    assert res_reason.status_code == 200
    assert res_reason.json()["total"] == 1

    # Search by comment keyword
    res_comment = client.get(f"/api/v1/events/{event['id']}/orders?search=exceptionnel")
    assert res_comment.status_code == 200
    assert res_comment.json()["total"] == 1
