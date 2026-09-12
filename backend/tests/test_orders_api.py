import re
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


def create_sample_event(client: TestClient, title: str = "Grand Vide-Grenier") -> dict:
    """Helper creating a published event for order tests."""
    payload = {
        "title": title,
        "description": "Brocante communale annuelle",
        "price_per_meter": 5.0,
        "map_type": "geographic",
        "start_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=7, hours=10)).isoformat(),
        "setup_start_time": "06:00",
        "setup_end_time": "08:00",
        "public_start_time": "08:00",
        "public_end_time": "18:00",
        "location_address": "Place de la Mairie, 35000 Rennes",
        "organizer_email": "contact@asso-rennes.fr",
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
    """Helper creating a spot for an event."""
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


def test_create_guest_order_nominal(client: TestClient, db_session: Session):
    """Test standard valid guest checkout submission with 2 held stalls."""
    event = create_sample_event(client, title="Vide-Grenier Centre")
    event_id = event["id"]
    slug = event["slug"]
    session_token = "sess_monique_12345"

    spot1 = create_sample_spot(client, event_id, label="A-01", linear_meters=2.0)
    spot2 = create_sample_spot(client, event_id, label="A-02", linear_meters=3.0)

    # Lock both spots in cart
    res_lock1 = client.post(
        f"/api/v1/public/events/{slug}/spots/{spot1['id']}/lock",
        json={"session_token": session_token},
    )
    assert res_lock1.status_code == 200, res_lock1.text

    res_lock2 = client.post(
        f"/api/v1/public/events/{slug}/spots/{spot2['id']}/lock",
        json={"session_token": session_token},
    )
    assert res_lock2.status_code == 200, res_lock2.text

    # Expected totals: spot1 is 2m * 5€ = 1000 cents; spot2 is 3m * 5€ = 1500 cents => 2500 cents (25.00 €)
    order_payload = {
        "session_token": session_token,
        "first_name": "Monique",
        "last_name": "Durand",
        "email": "monique.durand@example.fr",
        "phone": "06 12 34 56 78",
        "street_address": "12 rue des Lilas",
        "postal_code": "35000",
        "city": "Rennes",
        "honor_declaration_accepted": True,
    }

    res_order = client.post(f"/api/v1/public/events/{slug}/orders", json=order_payload)
    assert res_order.status_code == 201, res_order.text
    data = res_order.json()

    # Verify order metadata
    assert data["first_name"] == "Monique"
    assert data["last_name"] == "Durand"
    assert data["email"] == "monique.durand@example.fr"
    assert data["phone"] == "06 12 34 56 78"
    assert data["street_address"] == "12 rue des Lilas"
    assert data["postal_code"] == "35000"
    assert data["city"] == "Rennes"
    assert data["status"] == "pending"
    assert data["payment_method"] == "stripe"
    assert data["honor_declaration_accepted"] is True
    assert "honor_declaration_accepted_at" in data
    assert data["total_price_cents"] == 2500
    assert data["total_price"] == 25.0

    # Verify unique human-friendly order number: GVG-YYYY-XXXX
    assert re.match(r"^GVG-\d{4}-[A-Z0-9]{4}$", data["order_number"])
    assert len(data["access_token"]) >= 32

    # Verify items
    assert len(data["items"]) == 2
    item_spot_ids = {it["spot_id"] for it in data["items"]}
    assert item_spot_ids == {spot1["id"], spot2["id"]}
    labels = {it["spot_label"] for it in data["items"]}
    assert labels == {"A-01", "A-02"}

    # Assert item price_cents, price, and spot_linear_meters
    item_by_label = {it["spot_label"]: it for it in data["items"]}
    assert item_by_label["A-01"]["price_cents"] == 1000
    assert item_by_label["A-01"]["price"] == 10.0
    assert item_by_label["A-01"]["spot_linear_meters"] == 2.0

    assert item_by_label["A-02"]["price_cents"] == 1500
    assert item_by_label["A-02"]["price"] == 15.0
    assert item_by_label["A-02"]["spot_linear_meters"] == 3.0

    # Verify DB persistence
    order_id = uuid.UUID(data["id"])
    db_order = db_session.query(Order).filter(Order.id == order_id).first()
    assert db_order is not None
    assert db_order.total_price_cents == 2500
    assert len(db_order.items) == 2

    # Verify spots in DB remain locked (not yet reserved in Story 2.3) and lock was extended
    db_spot1 = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot1["id"])).first()
    assert db_spot1.status == "locked"
    assert db_spot1.locked_by_token == session_token
    assert db_spot1.locked_until is not None


def test_create_order_with_x_session_token_header_alone(client: TestClient):
    """Test creating an order where session_token is omitted from JSON body and passed via X-Session-Token header alone."""
    event = create_sample_event(client, title="Vide-Grenier Header Session")
    event_id = event["id"]
    slug = event["slug"]
    session_token = "sess_header_only_456"

    spot = create_sample_spot(client, event_id, label="H-01", linear_meters=2.0)
    res_lock = client.post(
        f"/api/v1/public/events/{slug}/spots/{spot['id']}/lock",
        headers={"X-Session-Token": session_token},
    )
    assert res_lock.status_code == 200

    order_payload = {
        # session_token omitted from body
        "first_name": "Julien",
        "last_name": "Mercier",
        "email": "julien.mercier@example.fr",
        "phone": "06 22 33 44 55",
        "street_address": "14 boulevard Clemenceau",
        "postal_code": "35000",
        "city": "Rennes",
        "honor_declaration_accepted": True,
    }

    res_order = client.post(
        f"/api/v1/public/events/{slug}/orders",
        json=order_payload,
        headers={"X-Session-Token": session_token},
    )
    assert res_order.status_code == 201, res_order.text
    data = res_order.json()
    assert data["first_name"] == "Julien"
    assert len(data["items"]) == 1
    assert data["items"][0]["spot_label"] == "H-01"
    assert data["items"][0]["spot_linear_meters"] == 2.0


def test_create_order_partial_expiration_rejection(client: TestClient, db_session: Session):
    """Test that if 1 of 2 held spots has expired, order creation is rejected with HTTP 409 and expired spot is pruned."""
    event = create_sample_event(client, title="Brocante Partial Expiration")
    event_id = uuid.UUID(event["id"])
    slug = event["slug"]
    session_token = "sess_partial_exp_999"

    # Spot 1 is actively locked (future)
    future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
    wkt1 = geojson_to_wkt_polygon({"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS})
    spot1 = Spot(
        event_id=event_id,
        label="PARTIAL-ACTIVE",
        linear_meters=2.0,
        price_cents=1000,
        geom=wkt1,
        status="locked",
        locked_until=future_time,
        locked_by_token=session_token,
    )

    # Spot 2 is expired
    past_time = datetime.now(timezone.utc) - timedelta(minutes=3)
    coords2 = [
        [
            [-1.66, 48.11],
            [-1.65, 48.11],
            [-1.65, 48.12],
            [-1.66, 48.12],
            [-1.66, 48.11],
        ]
    ]
    wkt2 = geojson_to_wkt_polygon({"type": "Polygon", "coordinates": coords2})
    spot2 = Spot(
        event_id=event_id,
        label="PARTIAL-EXPIRED",
        linear_meters=2.0,
        price_cents=1000,
        geom=wkt2,
        status="locked",
        locked_until=past_time,
        locked_by_token=session_token,
    )
    db_session.add_all([spot1, spot2])
    db_session.commit()

    order_payload = {
        "session_token": session_token,
        "first_name": "Claire",
        "last_name": "Moreau",
        "email": "claire.moreau@example.fr",
        "phone": "06 55 66 77 88",
        "street_address": "20 avenue Pasteur",
        "postal_code": "35000",
        "city": "Rennes",
        "honor_declaration_accepted": True,
    }

    res = client.post(f"/api/v1/public/events/{slug}/orders", json=order_payload)
    assert res.status_code == 409, res.text
    assert "Votre réservation temporaire a expiré, veuillez resélectionner vos stands." in res.json()["detail"]

    # Verify expired spot2 was pruned back to available
    db_session.refresh(spot2)
    assert spot2.status == "available"
    assert spot2.locked_until is None
    assert spot2.locked_by_token is None

    # Verify no partial order was created
    order_count = db_session.query(Order).filter(Order.event_id == event_id).count()
    assert order_count == 0


def test_create_order_rejected_without_honor_declaration(client: TestClient):
    """Test that submitting order without accepting sworn statement returns HTTP 422 with exact error message."""
    event = create_sample_event(client, title="Brocante Village")
    event_id = event["id"]
    slug = event["slug"]
    session_token = "sess_reject_honor"

    spot = create_sample_spot(client, event_id, label="B-01", linear_meters=2.0)
    client.post(
        f"/api/v1/public/events/{slug}/spots/{spot['id']}/lock",
        json={"session_token": session_token},
    )

    payload = {
        "session_token": session_token,
        "first_name": "Jean",
        "last_name": "Dupont",
        "email": "jean.dupont@example.fr",
        "phone": "06 98 76 54 32",
        "street_address": "5 place du Marché",
        "postal_code": "35000",
        "city": "Rennes",
        "honor_declaration_accepted": False,
    }

    res = client.post(f"/api/v1/public/events/{slug}/orders", json=payload)
    assert res.status_code == 422, res.text
    detail = res.text
    assert "L'attestation sur l'honneur est obligatoire pour participer au vide-grenier." in detail


def test_create_order_empty_cart_conflict(client: TestClient):
    """Test order submission when cart has 0 spots returns HTTP 409."""
    event = create_sample_event(client, title="Foire Vide")
    slug = event["slug"]

    payload = {
        "session_token": "sess_empty_cart_999",
        "first_name": "Alice",
        "last_name": "Martin",
        "email": "alice.martin@example.fr",
        "phone": "07 11 22 33 44",
        "street_address": "1 allée des Roses",
        "postal_code": "75001",
        "city": "Paris",
        "honor_declaration_accepted": True,
    }

    res = client.post(f"/api/v1/public/events/{slug}/orders", json=payload)
    assert res.status_code == 409, res.text
    assert "Votre réservation temporaire a expiré, veuillez resélectionner vos stands." in res.json()["detail"]


def test_create_order_expired_cart_conflict(client: TestClient, db_session: Session):
    """Test order submission when hold locks have expired returns HTTP 409 and releases spots."""
    event = create_sample_event(client, title="Brocante Expirée")
    event_id = uuid.UUID(event["id"])
    slug = event["slug"]
    session_token = "sess_expired_test"

    # Create spot with expired lock directly in DB
    past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    wkt = geojson_to_wkt_polygon({"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS})
    spot = Spot(
        event_id=event_id,
        label="EXP-1",
        linear_meters=2.0,
        price_cents=1000,
        geom=wkt,
        status="locked",
        locked_until=past_time,
        locked_by_token=session_token,
    )
    db_session.add(spot)
    db_session.commit()
    db_session.refresh(spot)

    payload = {
        "session_token": session_token,
        "first_name": "Pierre",
        "last_name": "Lemoine",
        "email": "pierre.lemoine@example.fr",
        "phone": "06 44 55 66 77",
        "street_address": "8 rue du Stade",
        "postal_code": "44000",
        "city": "Nantes",
        "honor_declaration_accepted": True,
    }

    res = client.post(f"/api/v1/public/events/{slug}/orders", json=payload)
    assert res.status_code == 409, res.text
    assert "Votre réservation temporaire a expiré, veuillez resélectionner vos stands." in res.json()["detail"]

    # Verify spot lock was pruned back to available
    db_session.refresh(spot)
    assert spot.status == "available"
    assert spot.locked_until is None
    assert spot.locked_by_token is None


def test_create_order_contact_validation(client: TestClient):
    """Test validation errors on missing or malformed contact fields."""
    event = create_sample_event(client, title="Test Validation")
    slug = event["slug"]

    base_payload = {
        "session_token": "valid_token",
        "first_name": "Monique",
        "last_name": "Durand",
        "email": "monique@example.fr",
        "phone": "06 12 34 56 78",
        "street_address": "12 rue Verte",
        "postal_code": "35000",
        "city": "Rennes",
        "honor_declaration_accepted": True,
    }

    # 1. Invalid email
    p1 = {**base_payload, "email": "not-an-email"}
    assert client.post(f"/api/v1/public/events/{slug}/orders", json=p1).status_code == 422

    # 2. Blank first name
    p2 = {**base_payload, "first_name": "   "}
    assert client.post(f"/api/v1/public/events/{slug}/orders", json=p2).status_code == 422

    # 3. Blank last name
    p3 = {**base_payload, "last_name": ""}
    assert client.post(f"/api/v1/public/events/{slug}/orders", json=p3).status_code == 422

    # 4. Invalid phone (too short)
    p4 = {**base_payload, "phone": "123"}
    assert client.post(f"/api/v1/public/events/{slug}/orders", json=p4).status_code == 422

    # 5. Invalid postal code
    p5 = {**base_payload, "postal_code": ""}
    assert client.post(f"/api/v1/public/events/{slug}/orders", json=p5).status_code == 422


def test_get_public_order_by_token(client: TestClient):
    """Test retrieving order by ID and access_token."""
    event = create_sample_event(client, title="Brocante du Port")
    event_id = event["id"]
    slug = event["slug"]
    session_token = "sess_port_1"

    spot = create_sample_spot(client, event_id, label="P-01", linear_meters=2.0)
    client.post(
        f"/api/v1/public/events/{slug}/spots/{spot['id']}/lock",
        json={"session_token": session_token},
    )

    order_payload = {
        "session_token": session_token,
        "first_name": "Marcelle",
        "last_name": "Robin",
        "email": "marcelle.robin@example.fr",
        "phone": "06 77 88 99 00",
        "street_address": "3 quai Duguay",
        "postal_code": "35400",
        "city": "Saint-Malo",
        "honor_declaration_accepted": True,
    }
    res_order = client.post(f"/api/v1/public/events/{slug}/orders", json=order_payload)
    assert res_order.status_code == 201
    order_data = res_order.json()
    order_id = order_data["id"]
    access_token = order_data["access_token"]

    # 1. Fetch with valid token via query param
    res_get = client.get(f"/api/v1/public/events/{slug}/orders/{order_id}?token={access_token}")
    assert res_get.status_code == 200, res_get.text
    fetched = res_get.json()
    assert fetched["id"] == order_id
    assert fetched["first_name"] == "Marcelle"
    assert len(fetched["items"]) == 1

    # 2. Fetch with valid token via header
    res_get_hdr = client.get(
        f"/api/v1/public/events/{slug}/orders/{order_id}",
        headers={"X-Access-Token": access_token},
    )
    assert res_get_hdr.status_code == 200

    # 3. Fetch with wrong token -> 403
    res_bad_tok = client.get(f"/api/v1/public/events/{slug}/orders/{order_id}?token=wrong_token")
    assert res_bad_tok.status_code == 403

    # 4. Fetch without token -> 401
    res_no_tok = client.get(f"/api/v1/public/events/{slug}/orders/{order_id}")
    assert res_no_tok.status_code == 401

    # 5. Fetch non-existent order -> 404
    fake_id = uuid.uuid4()
    res_404 = client.get(f"/api/v1/public/events/{slug}/orders/{fake_id}?token={access_token}")
    assert res_404.status_code == 404


def test_order_schema_guarantees_no_passwords_or_cni():
    """Verify that Order model and schemas never include password or identity document fields."""
    from app.models.order import Order
    from app.schemas.order import GuestOrderCreate, OrderOut

    forbidden_terms = ["password", "mot_de_passe", "cni", "identity_card", "passport", "piece_identite"]

    order_columns = [col.name.lower() for col in Order.__table__.columns]
    for term in forbidden_terms:
        for col in order_columns:
            assert term not in col, f"Forbidden field '{col}' found in Order model!"

    create_fields = [f.lower() for f in GuestOrderCreate.model_fields.keys()]
    for term in forbidden_terms:
        for f in create_fields:
            assert term not in f, f"Forbidden field '{f}' found in GuestOrderCreate schema!"

    out_fields = [f.lower() for f in OrderOut.model_fields.keys()]
    for term in forbidden_terms:
        for f in out_fields:
            assert term not in f, f"Forbidden field '{f}' found in OrderOut schema!"
