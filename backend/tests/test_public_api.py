import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.spot import Spot
from app.schemas.spot import geojson_to_wkt_polygon


def create_sample_event(
    client: TestClient,
    title="Vide-Grenier Saint-Michel",
    price_per_meter=4.0,
    map_type="geographic",
):
    now = datetime.now(timezone.utc)
    payload = {
        "title": title,
        "description": "Vide-grenier annuel sur la place du village",
        "map_type": map_type,
        "price_per_meter": price_per_meter,
        "start_date": (now + timedelta(days=5)).isoformat(),
        "end_date": (now + timedelta(days=5, hours=10)).isoformat(),
        "setup_start_time": "06:00",
        "setup_end_time": "08:00",
        "public_start_time": "08:00",
        "public_end_time": "18:00",
        "location_address": "Place de l'Église, 35000 Rennes",
    }
    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


SAMPLE_POLY_COORDS = [
    [
        [-1.680, 48.110],
        [-1.675, 48.110],
        [-1.675, 48.112],
        [-1.680, 48.112],
        [-1.680, 48.110],
    ]
]


def test_get_public_event_by_slug_success(client: TestClient):
    event = create_sample_event(client, title="Brocante d'Automne")
    slug = event["slug"]

    response = client.get(f"/api/v1/public/events/{slug}")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["title"] == "Brocante d'Automne"
    assert data["slug"] == slug
    assert data["location_address"] == "Place de l'Église, 35000 Rennes"
    assert data["price_per_meter"] == 4.0
    assert data["price_per_meter_cents"] == 400
    assert data["map_type"] == "geographic"
    assert "start_date" in data
    assert "end_date" in data
    assert data["public_start_time"] == "08:00"
    assert data["public_end_time"] == "18:00"

    # Verify zero leak of private administrative/stripe tokens
    assert "stripe_account_id" not in data


def test_get_public_event_404_not_found(client: TestClient):
    response = client.get("/api/v1/public/events/inexistent-slug-12345")
    assert response.status_code == 404
    assert response.json()["detail"] == "Événement introuvable"


def test_get_public_spots_empty(client: TestClient):
    event = create_sample_event(client, title="Événement Sans Stands")
    slug = event["slug"]

    response = client.get(f"/api/v1/public/events/{slug}/spots")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["type"] == "FeatureCollection"
    assert data["features"] == []


def test_get_public_spots_nominal(client: TestClient):
    event = create_sample_event(client, title="Foire aux Puces")
    event_id = event["id"]
    slug = event["slug"]

    # Create two spots
    spot_payload_1 = {
        "label": "A-01",
        "linear_meters": 2.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": SAMPLE_POLY_COORDS,
        },
    }
    spot_payload_2 = {
        "label": "A-02",
        "linear_meters": 3.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": SAMPLE_POLY_COORDS,
        },
    }

    r1 = client.post(f"/api/v1/events/{event_id}/spots", json=spot_payload_1)
    assert r1.status_code == 201
    r2 = client.post(f"/api/v1/events/{event_id}/spots", json=spot_payload_2)
    assert r2.status_code == 201

    # Mark second spot as reserved
    spot2_id = r2.json()["id"]
    r_patch = client.patch(
        f"/api/v1/events/{event_id}/spots/{spot2_id}",
        json={"status": "reserved"},
    )
    assert r_patch.status_code == 200

    # Query public endpoint
    response = client.get(f"/api/v1/public/events/{slug}/spots")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 2

    feat1 = next(f for f in data["features"] if f["properties"]["label"] == "A-01")
    assert feat1["type"] == "Feature"
    assert feat1["geometry"]["type"] == "Polygon"
    assert feat1["properties"]["status"] == "available"
    assert feat1["properties"]["linear_meters"] == 2.0
    assert feat1["properties"]["price_cents"] == 800
    assert feat1["properties"]["price"] == 8.0

    feat2 = next(f for f in data["features"] if f["properties"]["label"] == "A-02")
    assert feat2["properties"]["status"] == "reserved"
    assert feat2["properties"]["linear_meters"] == 3.0
    assert feat2["properties"]["price_cents"] == 1200
    assert feat2["properties"]["price"] == 12.0


def test_get_public_spots_lazy_lock_expiration(client: TestClient, db_session: Session):
    event = create_sample_event(client, title="Salon du Jouet Ancien")
    event_id = uuid.UUID(event["id"])
    slug = event["slug"]

    # Insert a spot with expired lock directly into database
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    wkt = geojson_to_wkt_polygon({"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS})
    
    spot = Spot(
        event_id=event_id,
        label="EXPIRED-01",
        linear_meters=2.5,
        price_cents=1000,
        geom=wkt,
        status="locked",
        locked_until=expired_time,
        locked_by_token="secret_client_token_xyz",
    )
    db_session.add(spot)
    db_session.commit()
    db_session.refresh(spot)

    # Query public endpoint
    response = client.get(f"/api/v1/public/events/{slug}/spots")
    assert response.status_code == 200, response.text
    data = response.json()

    assert len(data["features"]) == 1
    feat = data["features"][0]
    # Dynamic SQL lazy lock expiration must return 'available'
    assert feat["properties"]["status"] == "available"
    assert feat["properties"]["label"] == "EXPIRED-01"

    # Verify zero database mutation occurred during read-only query
    db_spot = db_session.query(Spot).filter(Spot.id == spot.id).first()
    assert db_spot.status == "locked"
    db_locked = db_spot.locked_until
    if db_locked.tzinfo is None:
        db_locked = db_locked.replace(tzinfo=timezone.utc)
    assert db_locked == expired_time


def test_get_public_spots_active_lock(client: TestClient, db_session: Session):
    event = create_sample_event(client, title="Brocante d'Été")
    event_id = uuid.UUID(event["id"])
    slug = event["slug"]

    # Insert a spot with active lock into database
    future_time = datetime.now(timezone.utc) + timedelta(minutes=12)
    wkt = geojson_to_wkt_polygon({"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS})

    spot = Spot(
        event_id=event_id,
        label="ACTIVE-LOCK-01",
        linear_meters=2.0,
        price_cents=800,
        geom=wkt,
        status="locked",
        locked_until=future_time,
        locked_by_token="secret_client_token_abc",
    )
    db_session.add(spot)
    db_session.commit()

    response = client.get(f"/api/v1/public/events/{slug}/spots")
    assert response.status_code == 200, response.text
    data = response.json()

    assert len(data["features"]) == 1
    feat = data["features"][0]
    assert feat["properties"]["status"] == "locked"
    assert feat["properties"]["label"] == "ACTIVE-LOCK-01"
    assert feat["properties"]["locked_until"] is not None


def test_get_public_spots_zero_sensitive_data_leak(client: TestClient, db_session: Session):
    event = create_sample_event(client, title="Brocante Confidentielle")
    event_id = uuid.UUID(event["id"])
    slug = event["slug"]

    wkt = geojson_to_wkt_polygon({"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS})
    spot = Spot(
        event_id=event_id,
        label="SECRET-01",
        linear_meters=3.0,
        price_cents=1200,
        geom=wkt,
        status="locked",
        locked_until=datetime.now(timezone.utc) + timedelta(minutes=10),
        locked_by_token="super_secret_session_token_9999",
    )
    db_session.add(spot)
    db_session.commit()

    response = client.get(f"/api/v1/public/events/{slug}/spots")
    assert response.status_code == 200, response.text
    response_text = response.text

    assert "super_secret_session_token_9999" not in response_text
    assert "locked_by_token" not in response_text


def test_get_public_spots_multi_tenant_isolation(client: TestClient):
    event1 = create_sample_event(client, title="Événement Rennes")
    event2 = create_sample_event(client, title="Événement Nantes")

    # Add Spot to Event 1
    client.post(
        f"/api/v1/events/{event1['id']}/spots",
        json={
            "label": "RENNES-01",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )

    # Add Spot to Event 2
    client.post(
        f"/api/v1/events/{event2['id']}/spots",
        json={
            "label": "NANTES-01",
            "linear_meters": 4.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )

    # Query Event 1 spots
    res1 = client.get(f"/api/v1/public/events/{event1['slug']}/spots")
    assert res1.status_code == 200
    labels1 = [f["properties"]["label"] for f in res1.json()["features"]]
    assert "RENNES-01" in labels1
    assert "NANTES-01" not in labels1

    # Query Event 2 spots
    res2 = client.get(f"/api/v1/public/events/{event2['slug']}/spots")
    assert res2.status_code == 200
    labels2 = [f["properties"]["label"] for f in res2.json()["features"]]
    assert "NANTES-01" in labels2
    assert "RENNES-01" not in labels2


def test_get_public_spots_404_on_unknown_slug(client: TestClient):
    response = client.get("/api/v1/public/events/non-existent-event-slug/spots")
    assert response.status_code == 404
    assert response.json()["detail"] == "Événement introuvable"


def test_get_public_spots_null_locked_until_reported_as_available(client: TestClient, db_session: Session):
    event = create_sample_event(client, title="Salon Brocante Null Lock")
    event_id = uuid.UUID(event["id"])
    slug = event["slug"]

    wkt = geojson_to_wkt_polygon({"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS})
    spot = Spot(
        event_id=event_id,
        label="NULL-LOCK-01",
        linear_meters=2.0,
        price_cents=800,
        geom=wkt,
        status="locked",
        locked_until=None,
        locked_by_token="orphan_token",
    )
    db_session.add(spot)
    db_session.commit()

    response = client.get(f"/api/v1/public/events/{slug}/spots")
    assert response.status_code == 200, response.text
    data = response.json()

    assert len(data["features"]) == 1
    feat = data["features"][0]
    assert feat["properties"]["status"] == "available"
    assert feat["properties"]["label"] == "NULL-LOCK-01"
