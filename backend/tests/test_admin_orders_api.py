import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.spot import Spot
from app.models.order import Order, BookingItem
from app.models.email_log import EmailLog
from app.models.user import User, UserRole
from app.core.security import hash_password, create_access_token

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


# ---------------------------------------------------------------------------
# Story 8.2: Fiche Détaillée d'Inscription Modifiable & Notes Internes
# ---------------------------------------------------------------------------


def test_update_admin_order_contact_success(client: TestClient, db_session: Session):
    """Marc updates exhibitor contact coordinates (name, email, phone, address)."""
    ev = create_test_event(client, "Vide-grenier Story 8.2")
    ev_id = ev["id"]
    sp = create_test_spot(client, ev_id, "VG-01", 2.0)

    # Create initial manual order
    order_res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "Jean",
            "last_name": "Dupont",
            "email": "jean.dupont@initial.fr",
            "phone": "0601020304",
            "payment_method": "cash",
            "street_address": "1 rue de la Paix",
            "postal_code": "75001",
            "city": "Paris",
        },
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]

    # PATCH order contact info
    patch_payload = {
        "first_name": "Jean-Marc",
        "last_name": "Dupont-Moretti",
        "email": "jean-marc.corrige@nouveau-domaine.fr",
        "phone": "0711223344",
        "street_address": "15 boulevard Haussmann",
        "postal_code": "75009",
        "city": "Paris 9e",
        "admin_notes": "Adresse et e-mail rectifiés par téléphone avec l'exposant.",
    }
    patch_res = client.patch(f"/api/v1/events/{ev_id}/orders/{order_id}", json=patch_payload)
    assert patch_res.status_code == 200, patch_res.text
    updated = patch_res.json()

    assert updated["first_name"] == "Jean-Marc"
    assert updated["last_name"] == "Dupont-Moretti"
    assert updated["full_name"] == "Jean-Marc Dupont-Moretti"
    assert updated["email"] == "jean-marc.corrige@nouveau-domaine.fr"
    assert updated["phone"] == "0711223344"
    assert updated["street_address"] == "15 boulevard Haussmann"
    assert updated["postal_code"] == "75009"
    assert updated["city"] == "Paris 9e"
    assert updated["admin_notes"] == "Adresse et e-mail rectifiés par téléphone avec l'exposant."
    assert updated["spot_labels"] == ["VG-01"]

    # Direct database verification
    db_order = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    assert db_order is not None
    assert db_order.first_name == "Jean-Marc"
    assert db_order.email == "jean-marc.corrige@nouveau-domaine.fr"
    assert db_order.phone == "0711223344"
    assert db_order.admin_notes == "Adresse et e-mail rectifiés par téléphone avec l'exposant."


def test_update_admin_order_invalid_email_422(client: TestClient):
    """Rejection with 422 if email format does not conform to strict RFC regex."""
    ev = create_test_event(client, "Event Invalid Email")
    ev_id = ev["id"]
    sp = create_test_spot(client, ev_id, "IE-01", 2.0)

    order_res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "Claire",
            "last_name": "Martin",
            "phone": "0601020304",
            "payment_method": "cash",
        },
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]

    # Invalid email formats
    for bad_email in ["not-an-email", "claire@", "claire@domain", "@nodomain.com"]:
        res = client.patch(
            f"/api/v1/events/{ev_id}/orders/{order_id}",
            json={"email": bad_email},
        )
        assert res.status_code == 422, f"Expected 422 for email {bad_email}"


def test_update_admin_order_invalid_phone_422(client: TestClient):
    """Rejection with 422 if phone length is under 8 or over 15 digits."""
    ev = create_test_event(client, "Event Invalid Phone")
    ev_id = ev["id"]
    sp = create_test_spot(client, ev_id, "IP-01", 2.0)

    order_res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "Paul",
            "last_name": "Durand",
            "phone": "0601020304",
            "payment_method": "cash",
        },
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]

    # Too short (< 8 digits)
    res_short = client.patch(
        f"/api/v1/events/{ev_id}/orders/{order_id}",
        json={"phone": "060102"},
    )
    assert res_short.status_code == 422

    # Too long (> 15 digits)
    res_long = client.patch(
        f"/api/v1/events/{ev_id}/orders/{order_id}",
        json={"phone": "01234567890123456"},
    )
    assert res_long.status_code == 422


def test_update_admin_notes_private_not_exposed_in_public_route(client: TestClient, db_session: Session):
    """admin_notes is persisted but strictly hidden from public exhibitor endpoints."""
    ev = create_test_event(client, "Event Private Notes")
    ev_id = ev["id"]
    slug = ev["slug"]
    sp = create_test_spot(client, ev_id, "PN-01", 2.0)

    order_res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "Sophie",
            "last_name": "Bernard",
            "phone": "0612345678",
            "email": "sophie@example.fr",
            "payment_method": "cash",
        },
    )
    assert order_res.status_code == 201
    order_data = order_res.json()
    order_id = order_data["id"]
    access_token = order_data["access_token"]

    # Save private admin notes
    secret_note = "CONFIDENTIEL : Demande un emplacement ombragé cause santé."
    patch_res = client.patch(
        f"/api/v1/events/{ev_id}/orders/{order_id}",
        json={"admin_notes": secret_note},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["admin_notes"] == secret_note

    # Verify public route does NOT leak admin_notes
    public_res = client.get(
        f"/api/v1/public/events/{slug}/orders/{order_id}?token={access_token}",
        headers={"X-No-Auth": "1"},
    )
    assert public_res.status_code == 200
    pub_data = public_res.json()
    assert "admin_notes" not in pub_data


def test_update_admin_order_financials_and_spots_immutable(client: TestClient, db_session: Session):
    """Financial amounts (total_price_cents) and reserved spots cannot be overwritten by PATCH."""
    ev = create_test_event(client, "Event Immutability")
    ev_id = ev["id"]
    sp = create_test_spot(client, ev_id, "IMM-01", 3.0)

    # 3.0m * 6.0€/m = 18.0€ = 1800 cents
    order_res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "Jacques",
            "last_name": "Lemoine",
            "phone": "0611223344",
            "payment_method": "cash",
        },
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]
    assert order_res.json()["total_price_cents"] == 1800

    # Attempt to tamper with price, items, and status
    tamper_payload = {
        "first_name": "Jacques-Henri",
        "total_price_cents": 0,
        "status": "cancelled",
        "items": [],
    }
    patch_res = client.patch(f"/api/v1/events/{ev_id}/orders/{order_id}", json=tamper_payload)
    assert patch_res.status_code == 200
    res_data = patch_res.json()

    assert res_data["first_name"] == "Jacques-Henri"
    assert res_data["total_price_cents"] == 1800
    assert res_data["total_price"] == 18.0
    assert res_data["status"] == "confirmed"
    assert len(res_data["items"]) == 1


def test_resend_attestation_confirmed_order_success(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Resending attestation compiles PDF in memory, sends email, and logs in EmailLog."""
    from app.services import email_service

    ev = create_test_event(client, "Event Attestation Resend")
    ev_id = ev["id"]
    sp = create_test_spot(client, ev_id, "ATT-01", 3.0)

    # Capture attachments sent to send_raw_email
    captured_attachments = []
    orig_send_raw_email = email_service.send_raw_email

    def spy_send_raw_email(*args, **kwargs):
        attachments = kwargs.get("attachments") or []
        captured_attachments.extend(attachments)
        return orig_send_raw_email(*args, **kwargs)

    monkeypatch.setattr(email_service, "send_raw_email", spy_send_raw_email)

    order_res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "Lucas",
            "last_name": "Roux",
            "phone": "0655443322",
            "email": "lucas.roux@example.org",
            "payment_method": "cash",
        },
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]

    # Trigger attestation resend
    resend_res = client.post(f"/api/v1/events/{ev_id}/orders/{order_id}/resend-attestation")
    assert resend_res.status_code == 200, resend_res.text
    resend_data = resend_res.json()
    assert resend_data["success"] is True
    assert "lucas.roux@example.org" in resend_data["email"]

    # Assert that the PDF attestation was properly compiled and attached
    assert len(captured_attachments) == 1
    att_filename, att_bytes, att_mime = captured_attachments[0]
    assert att_filename.startswith("attestation_")
    assert att_filename.endswith(".pdf")
    assert att_bytes.startswith(b"%PDF-")
    assert att_mime == "application/pdf"

    # Verify EmailLog audit trail entry
    log_entry = (
        db_session.query(EmailLog)
        .filter(EmailLog.order_id == uuid.UUID(order_id), EmailLog.email_type == "attestation")
        .first()
    )
    assert log_entry is not None
    assert log_entry.recipient == "lucas.roux@example.org"
    assert log_entry.status == "simulated"
    assert "attestation" in log_entry.subject.lower()

    # Verify GET /{id_or_slug}/orders/{order_id}/emails returns the attestation log
    emails_res = client.get(f"/api/v1/events/{ev_id}/orders/{order_id}/emails")
    assert emails_res.status_code == 200
    emails_data = emails_res.json()
    assert emails_data["total"] >= 1
    found_attestation = any(item["email_type"] == "attestation" for item in emails_data["items"])
    assert found_attestation is True


def test_resend_attestation_non_confirmed_order_400(client: TestClient, db_session: Session):
    """Cannot resend attestation for non-confirmed orders (returns 400)."""
    ev = create_test_event(client, "Event Non-Confirmed")
    ev_id = ev["id"]
    sp = create_test_spot(client, ev_id, "NC-01", 2.0)

    order_res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "Chloe",
            "last_name": "Moreau",
            "phone": "0699887766",
            "email": "chloe@example.org",
            "payment_method": "cash",
        },
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]

    # Change order status to 'pending'
    ord_db = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    ord_db.status = "pending"
    db_session.commit()

    res = client.post(f"/api/v1/events/{ev_id}/orders/{order_id}/resend-attestation")
    assert res.status_code == 400
    assert "confirmée" in res.json()["detail"].lower()


def test_resend_attestation_missing_email_400(client: TestClient):
    """Cannot resend attestation if exhibitor has no email address (returns 400)."""
    ev = create_test_event(client, "Event No Email")
    ev_id = ev["id"]
    sp = create_test_spot(client, ev_id, "NE-01", 2.0)

    order_res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "Guichetier",
            "last_name": "SansMail",
            "phone": "0600001122",
            "payment_method": "cash",
            # email is omitted / None
        },
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]

    res = client.post(f"/api/v1/events/{ev_id}/orders/{order_id}/resend-attestation")
    assert res.status_code == 400
    assert "adresse e-mail" in res.json()["detail"].lower()


def test_resend_attestation_pdf_compilation_failure_logs_error(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """If WeasyPrint PDF compilation fails, record status='failed' in EmailLog and do not send email."""
    from app.services import pdf_service, email_service

    ev = create_test_event(client, "Event PDF Failure")
    ev_id = ev["id"]
    sp = create_test_spot(client, ev_id, "FAIL-01", 2.0)

    # Monkeypatch pdf_service.generate_attestation_pdf to simulate WeasyPrint crash
    def mock_fail_pdf(*args, **kwargs):
        raise RuntimeError("WeasyPrint rendering out of memory")

    monkeypatch.setattr(pdf_service, "generate_attestation_pdf", mock_fail_pdf)

    # Spy on send_raw_email to ensure it is NOT called
    raw_email_called = []

    def spy_send_raw(*args, **kwargs):
        raw_email_called.append(True)

    monkeypatch.setattr(email_service, "send_raw_email", spy_send_raw)

    order_res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "Marc",
            "last_name": "Erreur",
            "phone": "0699887766",
            "email": "marc.erreur@example.org",
            "payment_method": "cash",
        },
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]

    # Clear calls from initial order creation email
    raw_email_called.clear()

    # Trigger resend attestation
    resend_res = client.post(f"/api/v1/events/{ev_id}/orders/{order_id}/resend-attestation")
    assert resend_res.status_code == 200

    # send_raw_email must NOT have been called
    assert len(raw_email_called) == 0

    # EmailLog must be created with status="failed" and error_message
    log_entry = (
        db_session.query(EmailLog)
        .filter(EmailLog.order_id == uuid.UUID(order_id), EmailLog.email_type == "attestation")
        .first()
    )
    assert log_entry is not None
    assert log_entry.status == "failed"
    assert "WeasyPrint rendering out of memory" in (log_entry.error_message or "")


def test_resend_attestation_unaccepted_honor_declaration_400(
    client: TestClient, db_session: Session
):
    """Cannot resend attestation if honor_declaration_accepted is False (returns 400)."""
    ev = create_test_event(client, "Event Unaccepted Declaration")
    ev_id = ev["id"]
    sp = create_test_spot(client, ev_id, "UHD-01", 2.0)

    order_res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "NoHonor",
            "last_name": "Test",
            "phone": "0612345678",
            "email": "nohonor@example.com",
            "payment_method": "cash",
        },
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]

    # Set honor_declaration_accepted = False in DB
    db_order = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    db_order.honor_declaration_accepted = False
    db_session.commit()

    res = client.post(f"/api/v1/events/{ev_id}/orders/{order_id}/resend-attestation")
    assert res.status_code == 400
    assert "sur l'honneur" in res.json()["detail"].lower()


def test_update_and_resend_unauthorized_organizer_403(client: TestClient, db_session: Session):
    """Organizers cannot modify or resend attestation for events they do not own (403)."""
    # Create two event_admins
    org1 = User(
        email="owner_story82@example.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.EVENT_ADMIN,
        is_active=True,
    )
    org2 = User(
        email="intruder_story82@example.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.EVENT_ADMIN,
        is_active=True,
    )
    db_session.add_all([org1, org2])
    db_session.commit()

    token1 = create_access_token(data={"sub": str(org1.id), "role": str(org1.role), "email": org1.email})
    token2 = create_access_token(data={"sub": str(org2.id), "role": str(org2.role), "email": org2.email})
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    # Org1 creates event
    ev_res = client.post(
        "/api/v1/events",
        json={
            "title": "Org1 Event",
            "description": "Owner event",
            "price_per_meter": 5.0,
            "start_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
            "end_date": (datetime.now(timezone.utc) + timedelta(days=10, hours=8)).isoformat(),
            "location_address": "Rennes",
            "organizer_email": "owner_story82@example.com",
            "status": "published",
        },
        headers=headers1,
    )
    assert ev_res.status_code == 201
    ev_id = ev_res.json()["id"]

    # Spot & Order by Org1
    sp = create_test_spot(client, ev_id, "SEC-01", 2.0)
    order_res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "Test",
            "last_name": "Auth",
            "phone": "0611223344",
            "email": "test@auth.com",
            "payment_method": "cash",
        },
        headers=headers1,
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]

    # Org2 attempts PATCH -> 403
    patch_forbidden = client.patch(
        f"/api/v1/events/{ev_id}/orders/{order_id}",
        json={"first_name": "Hacked"},
        headers=headers2,
    )
    assert patch_forbidden.status_code == 403

    # Org2 attempts resend attestation -> 403
    resend_forbidden = client.post(
        f"/api/v1/events/{ev_id}/orders/{order_id}/resend-attestation",
        headers=headers2,
    )
    assert resend_forbidden.status_code == 403


def test_update_admin_order_null_mandatory_fields_422(client: TestClient):
    """Explicit null for mandatory fields first_name, last_name, or phone returns 422."""
    ev = create_test_event(client, "Event Null Validation")
    ev_id = ev["id"]
    sp = create_test_spot(client, ev_id, "NV-01", 2.0)

    order_res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "Valide",
            "last_name": "Contact",
            "phone": "0612345678",
            "payment_method": "cash",
        },
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]

    # Explicit null for first_name -> 422
    res_fn = client.patch(
        f"/api/v1/events/{ev_id}/orders/{order_id}",
        json={"first_name": None},
    )
    assert res_fn.status_code == 422

    # Explicit null for last_name -> 422
    res_ln = client.patch(
        f"/api/v1/events/{ev_id}/orders/{order_id}",
        json={"last_name": None},
    )
    assert res_ln.status_code == 422

    # Explicit null for phone -> 422
    res_ph = client.patch(
        f"/api/v1/events/{ev_id}/orders/{order_id}",
        json={"phone": None},
    )
    assert res_ph.status_code == 422


def test_update_admin_order_phone_script_injection_rejected_422(client: TestClient):
    """Phone strings with arbitrary injection or text are rejected with 422."""
    ev = create_test_event(client, "Event Phone Sanitization")
    ev_id = ev["id"]
    sp = create_test_spot(client, ev_id, "PS-01", 2.0)

    order_res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "Sanitization",
            "last_name": "Phone",
            "phone": "0612345678",
            "payment_method": "cash",
        },
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]

    res = client.patch(
        f"/api/v1/events/{ev_id}/orders/{order_id}",
        json={"phone": "<script>alert(1)</script> 01234567"},
    )
    assert res.status_code == 422


def test_update_admin_order_notes_exceeding_max_length_422(client: TestClient):
    """admin_notes exceeding 5000 characters is rejected with 422."""
    ev = create_test_event(client, "Event Notes Limit")
    ev_id = ev["id"]
    sp = create_test_spot(client, ev_id, "NL-01", 2.0)

    order_res = client.post(
        f"/api/v1/events/{ev_id}/orders/manual",
        json={
            "spot_ids": [sp["id"]],
            "first_name": "Notes",
            "last_name": "Length",
            "phone": "0612345678",
            "payment_method": "cash",
        },
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]

    res = client.patch(
        f"/api/v1/events/{ev_id}/orders/{order_id}",
        json={"admin_notes": "A" * 5001},
    )
    assert res.status_code == 422


def test_update_admin_order_and_resend_not_found_404(client: TestClient):
    """PATCH and POST resend return 404 when order_id does not exist."""
    ev = create_test_event(client, "Event Not Found Test")
    ev_id = ev["id"]
    fake_order_id = uuid.uuid4()

    res_patch = client.patch(
        f"/api/v1/events/{ev_id}/orders/{fake_order_id}",
        json={"email": "notfound@example.com"},
    )
    assert res_patch.status_code == 404

    res_post = client.post(
        f"/api/v1/events/{ev_id}/orders/{fake_order_id}/resend-attestation",
    )
    assert res_post.status_code == 404


