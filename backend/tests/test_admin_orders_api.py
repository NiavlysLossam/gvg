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


def create_test_event(client: TestClient, title: str = "Brocante d'Automne") -> dict:
    payload = {
        "title": title,
        "description": "Grand vide-grenier annuel du centre-bourg",
        "price_per_meter": 6.0,
        "map_type": "geographic",
        "start_date": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=14, hours=10)).isoformat(),
        "setup_start_time": "06:00",
        "setup_end_time": "08:00",
        "public_start_time": "08:00",
        "public_end_time": "18:00",
        "location_address": "Place de la Mairie, 35000 Rennes",
        "organizer_email": "contact@rennes-asso.fr",
        "status": "published",
    }
    res = client.post("/api/v1/events", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def create_test_spot(
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


def test_get_dashboard_stats_empty_event(client: TestClient):
    """Test dashboard stats for an event with no spots or orders."""
    ev = create_test_event(client, "Vide-grenier Vide")
    ev_id = ev["id"]

    res = client.get(f"/api/v1/events/{ev_id}/dashboard-stats")
    assert res.status_code == 200
    data = res.json()
    assert data["total_spots"] == 0
    assert data["reserved_spots"] == 0
    assert data["available_spots"] == 0
    assert data["occupancy_rate"] == 0.0
    assert data["total_revenue"] == 0.0
    assert data["stripe_revenue"] == 0.0
    assert data["offline_revenue"] == 0.0


def test_get_dashboard_stats_not_found(client: TestClient):
    """404 when querying dashboard stats for a non-existent event."""
    res = client.get(f"/api/v1/events/{uuid.uuid4()}/dashboard-stats")
    assert res.status_code == 404
    assert "introuvable" in res.json()["detail"].lower()


def test_create_manual_order_success(client: TestClient):
    """Marc creates a manual offline booking with check payment."""
    ev = create_test_event(client, "Brocante Printemps")
    ev_id = ev["id"]

    sp1 = create_test_spot(client, ev_id, "A-01", 3.0)
    sp2 = create_test_spot(client, ev_id, "A-02", 2.0)

    manual_payload = {
        "spot_ids": [sp1["id"], sp2["id"]],
        "first_name": "Robert",
        "last_name": "Durand",
        "email": "robert.durand@example.fr",
        "phone": "0601020304",
        "street_address": "12 rue de la Paix",
        "postal_code": "35000",
        "city": "Rennes",
        "payment_method": "check",
        "offline_payment_reference": "CHQ-987654",
        "admin_notes": "Chèque remis en mairie le 10/09",
    }

    res = client.post(f"/api/v1/events/{ev_id}/orders/manual", json=manual_payload)
    assert res.status_code == 201, res.text
    order = res.json()

    assert order["first_name"] == "Robert"
    assert order["last_name"] == "Durand"
    assert order["full_name"] == "Robert Durand"
    assert order["email"] == "robert.durand@example.fr"
    assert order["phone"] == "0601020304"
    assert order["status"] == "confirmed"
    assert order["payment_method"] == "check"
    assert order["is_offline"] is True
    assert order["offline_payment_reference"] == "CHQ-987654"
    assert order["admin_notes"] == "Chèque remis en mairie le 10/09"
    assert set(order["spot_labels"]) == {"A-01", "A-02"}
    assert len(order["items"]) == 2
    # Price should equal sum of spots price (3m * 6€ = 18€, 2m * 6€ = 12€ -> 30€ = 3000 cts)
    assert order["total_price_cents"] == 3000
    assert order["total_price"] == 30.0

    # Verify spots in DB are now reserved
    spots_res = client.get(f"/api/v1/events/{ev_id}/spots")
    assert spots_res.status_code == 200
    features = spots_res.json()["features"]
    for feat in features:
        assert feat["properties"]["status"] == "reserved"
        assert feat["properties"]["is_offline"] is True
        assert feat["properties"]["payment_method"] == "check"


def test_create_manual_order_without_email(client: TestClient):
    """Exhibitor signs up in town hall with phone only (no email address)."""
    ev = create_test_event(client, "Vide-Grenier Mairie")
    ev_id = ev["id"]

    sp = create_test_spot(client, ev_id, "B-01", 2.0)

    manual_payload = {
        "spot_ids": [sp["id"]],
        "first_name": "Jeanne",
        "last_name": "Dupont",
        "phone": "0699887766",
        "payment_method": "cash",
        "admin_notes": "Règlement en espèces direct au guichet",
    }

    res = client.post(f"/api/v1/events/{ev_id}/orders/manual", json=manual_payload)
    assert res.status_code == 201, res.text
    order = res.json()

    assert order["email"] is None
    assert order["payment_method"] == "cash"
    assert order["is_offline"] is True
    assert order["status"] == "confirmed"


def test_create_manual_order_conflict_already_reserved(client: TestClient):
    """Attempting to manually reserve a spot that is already reserved must return 409 Conflict."""
    ev = create_test_event(client, "Brocante Conflit")
    ev_id = ev["id"]

    sp = create_test_spot(client, ev_id, "C-01", 2.0)

    # First reservation succeeds
    payload1 = {
        "spot_ids": [sp["id"]],
        "first_name": "Paul",
        "last_name": "Martin",
        "phone": "0611223344",
        "payment_method": "check",
    }
    res1 = client.post(f"/api/v1/events/{ev_id}/orders/manual", json=payload1)
    assert res1.status_code == 201

    # Second reservation on the same spot fails with 409
    payload2 = {
        "spot_ids": [sp["id"]],
        "first_name": "Alice",
        "last_name": "Lemoine",
        "phone": "0655667788",
        "payment_method": "cash",
    }
    res2 = client.post(f"/api/v1/events/{ev_id}/orders/manual", json=payload2)
    assert res2.status_code == 409
    assert "pas disponible" in res2.json()["detail"].lower()


def test_create_manual_order_conflict_active_locked_spot(client: TestClient, db_session: Session):
    """Attempting to manually reserve a spot actively locked by a visitor returns 409 Conflict."""
    ev = create_test_event(client, "Brocante Lock")
    ev_id = ev["id"]

    sp = create_test_spot(client, ev_id, "D-01", 2.0)

    # Lock spot manually with future expiration
    db_spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(sp["id"])).first()
    db_spot.status = "locked"
    db_spot.locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
    db_spot.locked_by_token = "some-visitor-session-token"
    db_session.commit()

    payload = {
        "spot_ids": [sp["id"]],
        "first_name": "Bernard",
        "last_name": "Leclerc",
        "phone": "0622334455",
        "payment_method": "other",
    }
    res = client.post(f"/api/v1/events/{ev_id}/orders/manual", json=payload)
    assert res.status_code == 409
    assert "verrouillé" in res.json()["detail"].lower()


def test_create_manual_order_invalid_payment_method(client: TestClient):
    """Only 'check', 'cash', and 'other' are allowed for manual offline orders."""
    ev = create_test_event(client, "Brocante Validation")
    ev_id = ev["id"]

    sp = create_test_spot(client, ev_id, "E-01", 2.0)

    payload = {
        "spot_ids": [sp["id"]],
        "first_name": "Test",
        "last_name": "User",
        "phone": "0612345678",
        "payment_method": "stripe",  # Not an offline payment method
    }
    res = client.post(f"/api/v1/events/{ev_id}/orders/manual", json=payload)
    assert res.status_code == 422


def test_list_orders_and_kpis(client: TestClient, db_session: Session):
    """Test listing orders, pagination, search, and KPI calculations."""
    ev = create_test_event(client, "Brocante KPIs")
    ev_id = ev["id"]

    # 4 spots: 2 reserved offline, 1 online (stripe), 1 available
    sp1 = create_test_spot(client, ev_id, "Z-01", 2.0)  # 12€
    sp2 = create_test_spot(client, ev_id, "Z-02", 2.0)  # 12€
    sp3 = create_test_spot(client, ev_id, "Z-03", 2.0)  # 12€
    sp4 = create_test_spot(client, ev_id, "Z-04", 2.0)  # 12€ (available)

    # 1. Offline order with check
    res_off1 = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp1["id"]],
            "first_name": "Robert",
            "last_name": "Dubois",
            "email": "robert@dubois.fr",
            "phone": "0600000001",
            "payment_method": "check",
            "offline_payment_reference": "CHQ-111",
        },
    )
    assert res_off1.status_code == 201

    # 2. Offline order with cash
    res_off2 = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp2["id"]],
            "first_name": "Camille",
            "last_name": "Moreau",
            "phone": "0600000002",
            "payment_method": "cash",
        },
    )
    assert res_off2.status_code == 201

    # 3. Online order (simulate confirmed Stripe order in DB)
    online_order = Order(
        event_id=uuid.UUID(ev_id),
        first_name="Sophie",
        last_name="Girard",
        email="sophie.girard@example.com",
        phone="0600000003",
        street_address="5 avenue des Fleurs",
        postal_code="35000",
        city="Rennes",
        total_price_cents=1200,
        status="confirmed",
        payment_method="stripe",
        stripe_payment_intent_id="pi_test_12345",
    )
    db_session.add(online_order)
    db_session.flush()

    item3 = BookingItem(
        order_id=online_order.id,
        spot_id=uuid.UUID(sp3["id"]),
        price_cents=1200,
    )
    db_session.add(item3)

    spot3_db = db_session.query(Spot).filter(Spot.id == uuid.UUID(sp3["id"])).first()
    spot3_db.status = "reserved"
    db_session.commit()

    # Query GET /api/v1/events/{id}/orders
    res = client.get(f"/api/v1/events/{ev_id}/orders")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3

    stats = data["stats"]
    assert stats["total_spots"] == 4
    assert stats["reserved_spots"] == 3
    assert stats["available_spots"] == 1
    assert stats["occupancy_rate"] == 75.0
    assert stats["stripe_revenue"] == 12.0
    assert stats["offline_revenue"] == 24.0
    assert stats["total_revenue"] == 36.0
    assert stats["offline_check_revenue"] == 12.0
    assert stats["offline_cash_revenue"] == 12.0
    assert stats["confirmed_orders_count"] == 3
    assert stats["offline_orders_count"] == 2

    # Test filter by status=offline
    res_offline = client.get(f"/api/v1/events/{ev_id}/orders?status=offline")
    assert res_offline.status_code == 200
    data_offline = res_offline.json()
    assert data_offline["total"] == 2
    for item in data_offline["items"]:
        assert item["is_offline"] is True

    # Test search by exhibitor name
    res_search_name = client.get(f"/api/v1/events/{ev_id}/orders?search=Robert")
    assert res_search_name.status_code == 200
    data_name = res_search_name.json()
    assert data_name["total"] == 1
    assert data_name["items"][0]["first_name"] == "Robert"

    # Test search by full name "Prénom Nom"
    res_search_fullname = client.get(f"/api/v1/events/{ev_id}/orders?search=Robert+Dubois")
    assert res_search_fullname.status_code == 200
    data_fullname = res_search_fullname.json()
    assert data_fullname["total"] == 1
    assert data_fullname["items"][0]["first_name"] == "Robert"

    # Test search by spot label
    res_search_spot = client.get(f"/api/v1/events/{ev_id}/orders?search=Z-03")
    assert res_search_spot.status_code == 200
    data_spot = res_search_spot.json()
    assert data_spot["total"] == 1
    assert data_spot["items"][0]["first_name"] == "Sophie"

    # Test search with no match
    res_search_empty = client.get(f"/api/v1/events/{ev_id}/orders?search=Inexistant")
    assert res_search_empty.status_code == 200
    assert res_search_empty.json()["total"] == 0
    assert res_search_empty.json()["items"] == []


def test_public_spots_reflects_offline_tag(client: TestClient):
    """Verify that public GeoJSON spots include is_offline without exposing payment_method."""
    ev = create_test_event(client, "Brocante Public View")
    ev_id = ev["id"]
    slug = ev["slug"]

    sp = create_test_spot(client, ev_id, "PUB-01", 2.5)

    # Initially available, is_offline is False
    res_pub1 = client.get(f"/api/v1/public/events/{slug}/spots")
    assert res_pub1.status_code == 200
    props1 = res_pub1.json()["features"][0]["properties"]
    assert props1["status"] == "available"
    assert props1["is_offline"] is False

    # Manual booking
    res_book = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "Marc",
            "last_name": "Organisateur",
            "phone": "0612345678",
            "payment_method": "check",
        },
    )
    assert res_book.status_code == 201

    # Now reserved with is_offline = True, and payment_method not exposed
    res_pub2 = client.get(f"/api/v1/public/events/{slug}/spots")
    assert res_pub2.status_code == 200
    props2 = res_pub2.json()["features"][0]["properties"]
    assert props2["status"] == "reserved"
    assert props2["is_offline"] is True
    assert "payment_method" not in props2


def test_orders_pagination_with_multi_spot_orders(client: TestClient):
    """Verify that pagination (limit/offset) slices orders correctly even with multi-spot orders."""
    ev = create_test_event(client, "Pagination Multi-Spot Event")
    ev_id = ev["id"]

    sp1 = create_test_spot(client, ev_id, "PAG-01", 2.0)
    sp2 = create_test_spot(client, ev_id, "PAG-02", 2.0)
    sp3 = create_test_spot(client, ev_id, "PAG-03", 2.0)

    # Order 1: 2 spots
    res1 = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp1["id"], sp2["id"]],
            "first_name": "Alice",
            "last_name": "Multi",
            "phone": "0600000001",
            "payment_method": "cash",
        },
    )
    assert res1.status_code == 201

    # Order 2: 1 spot
    res2 = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp3["id"]],
            "first_name": "Bob",
            "last_name": "Single",
            "phone": "0600000002",
            "payment_method": "check",
        },
    )
    assert res2.status_code == 201

    # Page 1: limit=1, skip=0 -> Should return exactly 1 order
    page1 = client.get(f"/api/v1/events/{ev_id}/orders?limit=1&skip=0")
    assert page1.status_code == 200
    data1 = page1.json()
    assert data1["total"] == 2
    assert len(data1["items"]) == 1

    # Page 2: limit=1, skip=1 -> Should return exactly 1 order (the second one)
    page2 = client.get(f"/api/v1/events/{ev_id}/orders?limit=1&skip=1")
    assert page2.status_code == 200
    data2 = page2.json()
    assert data2["total"] == 2
    assert len(data2["items"]) == 1
    assert data2["items"][0]["id"] != data1["items"][0]["id"]

    # Verify that the order with 2 spots loaded all items without slicing
    all_orders = client.get(f"/api/v1/events/{ev_id}/orders?limit=10&skip=0").json()
    multi_order = next(o for o in all_orders["items"] if o["first_name"] == "Alice")
    assert len(multi_order["items"]) == 2
    assert len(multi_order["spot_labels"]) == 2


def test_manual_order_custom_price_cents_zero(client: TestClient):
    """Verify that custom_price_cents=0 is respected and not overwritten by default spot pricing."""
    ev = create_test_event(client, "Free Stand Event")
    ev_id = ev["id"]

    sp = create_test_spot(client, ev_id, "FREE-01", 3.0)

    res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "Benevole",
            "last_name": "Gratuit",
            "phone": "0600000000",
            "payment_method": "other",
            "custom_price_cents": 0,
            "admin_notes": "Emplacement offert à l'association",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["total_price_cents"] == 0
    assert data["total_price"] == 0.0
    assert data["admin_notes"] == "Emplacement offert à l'association"


def test_manual_booking_rejects_blocked_spot_with_409(client: TestClient, db_session: Session):
    """Verify that manual booking rejects blocked spots with 409 and dashboard stats account for blocked spots."""
    ev = create_test_event(client, "Blocked Spot Event")
    ev_id = ev["id"]

    sp_avail = create_test_spot(client, ev_id, "BLK-01", 2.0)
    sp_blocked = create_test_spot(client, ev_id, "BLK-02", 2.0)

    # Set sp_blocked to status='blocked'
    spot_db = db_session.query(Spot).filter(Spot.id == uuid.UUID(sp_blocked["id"])).first()
    spot_db.status = "blocked"
    db_session.commit()

    # Check dashboard stats: available_spots should subtract the blocked spot
    stats_res = client.get(f"/api/v1/events/{ev_id}/dashboard-stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_spots"] == 2
    assert stats["reserved_spots"] == 0
    assert stats["locked_spots"] == 0
    assert stats["available_spots"] == 1  # 2 total - 1 blocked = 1 available

    # Try to manually book the blocked spot
    res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp_blocked["id"]],
            "first_name": "Jean",
            "last_name": "Test",
            "phone": "0612345678",
            "payment_method": "cash",
        },
    )
    assert res.status_code == 409
    assert "n'est pas disponible" in res.json()["detail"] or "conflit" in res.json()["detail"].lower()

