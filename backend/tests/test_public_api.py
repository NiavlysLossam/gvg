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
    status="published",
):
    now = datetime.now(timezone.utc)
    payload = {
        "title": title,
        "description": "Vide-grenier annuel sur la place du village",
        "map_type": map_type,
        "price_per_meter": price_per_meter,
        "status": status,
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


def test_get_public_event_showcase_metadata_and_spot_counts(client: TestClient, db_session: Session):
    """Vérifie que la page vitrine publique reçoit l'affiche officielle et les compteurs de stands réels."""
    now = datetime.now(timezone.utc)
    ev = Event(
        title="Grande Braderie de Printemps",
        slug="grande-braderie-printemps-2026",
        description="Venez chiner parmi plus de 100 exposants locaux !",
        map_type="geographic",
        price_per_meter_cents=500,
        start_date=now + timedelta(days=10),
        end_date=now + timedelta(days=10, hours=10),
        setup_start_time="05:30",
        setup_end_time="07:30",
        public_start_time="08:00",
        public_end_time="19:00",
        location_address="Boulevard de la Liberté, 35000 Rennes",
        organizer_email="contact@braderie-rennes.fr",
        rules_text="Installation dès 5h30. Buvette et restauration sur place. Véhicules interdits après 7h30.",
        status="published",
        poster_image_url="/uploads/events/braderie-2026/poster.webp",
    )
    db_session.add(ev)
    db_session.commit()
    db_session.refresh(ev)

    # Spot 1: Available
    s1 = Spot(
        event_id=ev.id,
        label="A-01",
        linear_meters=3.0,
        price_cents=1500,
        geom=geojson_to_wkt_polygon(SAMPLE_POLY_COORDS),
        status="available",
    )
    # Spot 2: Reserved
    s2 = Spot(
        event_id=ev.id,
        label="A-02",
        linear_meters=2.0,
        price_cents=1000,
        geom=geojson_to_wkt_polygon(SAMPLE_POLY_COORDS),
        status="reserved",
    )
    # Spot 3: Locked but expired (should count as available)
    s3 = Spot(
        event_id=ev.id,
        label="A-03",
        linear_meters=4.0,
        price_cents=2000,
        geom=geojson_to_wkt_polygon(SAMPLE_POLY_COORDS),
        status="locked",
        locked_until=now - timedelta(minutes=5),
    )
    # Spot 4: Locked with active unexpired lock (must NOT count as available)
    s4 = Spot(
        event_id=ev.id,
        label="A-04",
        linear_meters=2.0,
        price_cents=1000,
        geom=geojson_to_wkt_polygon(SAMPLE_POLY_COORDS),
        status="locked",
        locked_until=now + timedelta(minutes=10),
    )
    # Spot 5: Blocked spot (must NOT count as available)
    s5 = Spot(
        event_id=ev.id,
        label="A-05",
        linear_meters=2.0,
        price_cents=1000,
        geom=geojson_to_wkt_polygon(SAMPLE_POLY_COORDS),
        status="blocked",
    )
    db_session.add_all([s1, s2, s3, s4, s5])
    db_session.commit()

    response = client.get(f"/api/v1/public/events/{ev.slug}")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["title"] == "Grande Braderie de Printemps"
    assert data["poster_image_url"] == "/uploads/events/braderie-2026/poster.webp"
    assert data["total_spots"] == 5
    assert data["available_spots"] == 2  # s1 (available) + s3 (expired lock)
    assert data["setup_start_time"] == "05:30"
    assert data["setup_end_time"] == "07:30"
    assert data["public_start_time"] == "08:00"
    assert data["public_end_time"] == "19:00"
    assert "Buvette et restauration" in data["rules_text"]
    assert data["organizer_email"] == "contact@braderie-rennes.fr"


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


def test_lock_spot_success(client: TestClient, db_session: Session):
    event = create_sample_event(client, title="Brocante Saint-Malo")
    event_id = event["id"]
    slug = event["slug"]

    # Create spot
    r_spot = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "A-01",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    assert r_spot.status_code == 201
    spot_id = r_spot.json()["id"]

    # Lock spot
    token = "session-visitor-1"
    response = client.post(
        f"/api/v1/public/events/{slug}/spots/{spot_id}/lock",
        json={"session_token": token},
    )
    assert response.status_code == 200, response.text
    cart = response.json()

    assert cart["session_token"] == token
    assert cart["total_count"] == 1
    assert cart["total_linear_meters"] == 2.0
    assert cart["total_price_cents"] == 800
    assert cart["total_price"] == 8.0
    assert cart["expires_at"] is not None
    assert len(cart["spots"]) == 1
    assert cart["spots"][0]["id"] == spot_id
    assert cart["spots"][0]["label"] == "A-01"

    # Verify database state
    db_spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_id)).first()
    assert db_spot.status == "locked"
    assert db_spot.locked_by_token == token
    assert db_spot.locked_until is not None
    now = datetime.now(timezone.utc)
    locked_dt = db_spot.locked_until if db_spot.locked_until.tzinfo else db_spot.locked_until.replace(tzinfo=timezone.utc)
    assert now + timedelta(minutes=14) <= locked_dt <= now + timedelta(minutes=16)


def test_lock_multi_spots_aggregates_cart(client: TestClient):
    event = create_sample_event(client, title="Brocante Dinan")
    event_id = event["id"]
    slug = event["slug"]

    # Create 2 spots
    r1 = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "B-01",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    r2 = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "B-02",
            "linear_meters": 3.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    id1 = r1.json()["id"]
    id2 = r2.json()["id"]

    token = "session-monique"
    # Lock first spot
    res1 = client.post(
        f"/api/v1/public/events/{slug}/spots/{id1}/lock",
        json={"session_token": token},
    )
    assert res1.status_code == 200
    assert res1.json()["total_count"] == 1
    spot1_locked_until = res1.json()["spots"][0]["locked_until"]

    # Lock second spot
    res2 = client.post(
        f"/api/v1/public/events/{slug}/spots/{id2}/lock",
        json={"session_token": token},
    )
    assert res2.status_code == 200
    cart = res2.json()
    assert cart["total_count"] == 2
    assert cart["total_linear_meters"] == 5.0
    assert cart["total_price_cents"] == 2000
    assert cart["total_price"] == 20.0
    assert len(cart["spots"]) == 2
    assert cart["expires_at"] == spot1_locked_until


def test_lock_spot_concurrent_collision_returns_409(client: TestClient, db_session: Session):
    event = create_sample_event(client, title="Collision Event")
    event_id = event["id"]
    slug = event["slug"]

    r = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "C-01",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    spot_id = r.json()["id"]

    # User A locks C-01
    res_a = client.post(
        f"/api/v1/public/events/{slug}/spots/{spot_id}/lock",
        json={"session_token": "token-user-a"},
    )
    assert res_a.status_code == 200

    # User B tries to lock C-01
    res_b = client.post(
        f"/api/v1/public/events/{slug}/spots/{spot_id}/lock",
        json={"session_token": "token-user-b"},
    )
    assert res_b.status_code == 409
    assert res_b.json()["detail"] == "Ce stand est en cours de commande par un autre visiteur"

    # Verify User A's lock is intact
    db_spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_id)).first()
    assert db_spot.locked_by_token == "token-user-a"


def test_lock_spot_sold_or_blocked_returns_409(client: TestClient):
    event = create_sample_event(client, title="Sold Event")
    event_id = event["id"]
    slug = event["slug"]

    r = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "D-01",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    spot_id = r.json()["id"]

    # Mark as reserved
    client.patch(
        f"/api/v1/events/{event_id}/spots/{spot_id}",
        json={"status": "reserved"},
    )

    # Attempt to lock
    res = client.post(
        f"/api/v1/public/events/{slug}/spots/{spot_id}/lock",
        json={"session_token": "token-random"},
    )
    assert res.status_code == 409
    assert res.json()["detail"] == "Cet emplacement n'est plus disponible à la vente"


def test_unlock_spot_success(client: TestClient, db_session: Session):
    event = create_sample_event(client, title="Unlock Event")
    event_id = event["id"]
    slug = event["slug"]

    r = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "E-01",
            "linear_meters": 2.5,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    spot_id = r.json()["id"]

    token = "session-e"
    # Lock
    res_lock = client.post(
        f"/api/v1/public/events/{slug}/spots/{spot_id}/lock",
        json={"session_token": token},
    )
    assert res_lock.status_code == 200
    assert res_lock.json()["total_count"] == 1

    # Unlock
    res_unlock = client.post(
        f"/api/v1/public/events/{slug}/spots/{spot_id}/unlock",
        json={"session_token": token},
    )
    assert res_unlock.status_code == 200
    cart = res_unlock.json()
    assert cart["total_count"] == 0
    assert len(cart["spots"]) == 0

    # Verify spot is now available in DB
    db_spot = db_session.query(Spot).filter(Spot.id == uuid.UUID(spot_id)).first()
    assert db_spot.status == "available"
    assert db_spot.locked_until is None
    assert db_spot.locked_by_token is None


def test_unlock_spot_locked_by_other_user_fails(client: TestClient):
    event = create_sample_event(client, title="Unauthorized Unlock")
    event_id = event["id"]
    slug = event["slug"]

    r = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "F-01",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    spot_id = r.json()["id"]

    # Lock by user A
    client.post(
        f"/api/v1/public/events/{slug}/spots/{spot_id}/lock",
        json={"session_token": "user-a"},
    )

    # User B tries to unlock
    res = client.post(
        f"/api/v1/public/events/{slug}/spots/{spot_id}/unlock",
        json={"session_token": "user-b"},
    )
    assert res.status_code == 409
    assert res.json()["detail"] == "Ce stand est verrouillé par un autre visiteur"


def test_lock_expired_spot_takeover(client: TestClient, db_session: Session):
    event = create_sample_event(client, title="Takeover Event")
    event_id = uuid.UUID(event["id"])
    slug = event["slug"]

    wkt = geojson_to_wkt_polygon({"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS})
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    spot = Spot(
        event_id=event_id,
        label="EXPIRED-TAKEOVER",
        linear_meters=2.0,
        price_cents=800,
        geom=wkt,
        status="locked",
        locked_until=expired_time,
        locked_by_token="user-old",
    )
    db_session.add(spot)
    db_session.commit()
    db_session.refresh(spot)

    # User new locks expired spot
    res = client.post(
        f"/api/v1/public/events/{slug}/spots/{spot.id}/lock",
        json={"session_token": "user-new"},
    )
    assert res.status_code == 200
    cart = res.json()
    assert cart["total_count"] == 1
    assert cart["spots"][0]["id"] == str(spot.id)

    # Verify DB has user-new as owner and future locked_until
    db_spot = db_session.query(Spot).filter(Spot.id == spot.id).first()
    assert db_spot.locked_by_token == "user-new"
    locked_dt = db_spot.locked_until
    if locked_dt.tzinfo is None:
        locked_dt = locked_dt.replace(tzinfo=timezone.utc)
    assert locked_dt > datetime.now(timezone.utc)


def test_get_cart_rehydration_and_expired_pruning(client: TestClient, db_session: Session):
    event = create_sample_event(client, title="Cart Rehydration Event")
    event_id = uuid.UUID(event["id"])
    slug = event["slug"]
    token = "session-rehydration"

    wkt = geojson_to_wkt_polygon({"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS})
    
    # Active spot
    s1 = Spot(
        event_id=event_id,
        label="ACTIVE-S1",
        linear_meters=2.0,
        price_cents=800,
        geom=wkt,
        status="locked",
        locked_until=datetime.now(timezone.utc) + timedelta(minutes=10),
        locked_by_token=token,
    )
    # Expired spot
    s2 = Spot(
        event_id=event_id,
        label="EXPIRED-S2",
        linear_meters=3.0,
        price_cents=1200,
        geom=wkt,
        status="locked",
        locked_until=datetime.now(timezone.utc) - timedelta(minutes=2),
        locked_by_token=token,
    )
    db_session.add_all([s1, s2])
    db_session.commit()

    # Query cart
    res = client.get(f"/api/v1/public/events/{slug}/cart?session_token={token}")
    assert res.status_code == 200
    cart = res.json()

    assert cart["total_count"] == 1
    assert cart["total_linear_meters"] == 2.0
    assert cart["total_price"] == 8.0
    assert cart["spots"][0]["label"] == "ACTIVE-S1"

    # Verify expired spot was cleaned up in DB
    db_s2 = db_session.query(Spot).filter(Spot.id == s2.id).first()
    assert db_s2.status == "available"
    assert db_s2.locked_until is None
    assert db_s2.locked_by_token is None


def test_get_cart_empty_or_no_token(client: TestClient):
    event = create_sample_event(client, title="Empty Cart Event")
    slug = event["slug"]

    res = client.get(f"/api/v1/public/events/{slug}/cart")
    assert res.status_code == 200
    cart = res.json()
    assert cart["total_count"] == 0
    assert cart["spots"] == []
    assert cart["expires_at"] is None


def test_session_isolation_in_cart(client: TestClient):
    event = create_sample_event(client, title="Cart Isolation Event")
    event_id = event["id"]
    slug = event["slug"]

    r1 = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "ISO-01",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    r2 = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "ISO-02",
            "linear_meters": 4.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    id1 = r1.json()["id"]
    id2 = r2.json()["id"]

    # User 1 locks ISO-01
    client.post(f"/api/v1/public/events/{slug}/spots/{id1}/lock", json={"session_token": "token-1"})
    # User 2 locks ISO-02
    client.post(f"/api/v1/public/events/{slug}/spots/{id2}/lock", json={"session_token": "token-2"})

    # Check cart User 1
    c1 = client.get(f"/api/v1/public/events/{slug}/cart?session_token=token-1").json()
    assert c1["total_count"] == 1
    assert c1["spots"][0]["id"] == id1

    # Check cart User 2
    c2 = client.get(f"/api/v1/public/events/{slug}/cart?session_token=token-2").json()
    assert c2["total_count"] == 1
    assert c2["spots"][0]["id"] == id2


def test_list_public_events_unauthenticated(client: TestClient, db_session: Session):
    event = create_sample_event(client, title="Public Open Event")
    # Mark as published with poster image
    client.patch(
        f"/api/v1/events/{event['id']}",
        json={"status": "published", "poster_image_url": "https://example.com/poster.jpg"},
    )

    # Fetch without auth header
    response = client.get("/api/v1/public/events", headers={"X-No-Auth": "1"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    found = [e for e in data if e["id"] == event["id"]]
    assert len(found) == 1
    item = found[0]
    assert item["title"] == "Public Open Event"
    assert item["status"] == "published"
    assert "total_spots" in item
    assert "available_spots" in item
    assert item["price_per_meter"] == 4.0
    assert item["poster_image_url"] == "https://example.com/poster.jpg"


def test_list_public_events_filters_draft_and_past(client: TestClient, db_session: Session):
    now = datetime.now(timezone.utc)

    # 1. Published upcoming event
    e_pub = create_sample_event(client, title="Upcoming Published Event")
    client.patch(f"/api/v1/events/{e_pub['id']}", json={"status": "published"})

    # 2. Draft upcoming event
    e_draft = create_sample_event(client, title="Upcoming Draft Event", status="draft")
    # remains draft

    # 3. Archived upcoming event
    e_archived = create_sample_event(client, title="Upcoming Archived Event", status="draft")
    client.patch(f"/api/v1/events/{e_archived['id']}", json={"status": "archived"})

    # 4. Past published event directly in DB (ended yesterday)
    e_past = Event(
        title="Past Published Event",
        slug="past-published-event-" + str(uuid.uuid4())[:8],
        status="published",
        price_per_meter_cents=500,
        start_date=now - timedelta(days=5),
        end_date=now - timedelta(days=1),
        location_address="Ancienne Place, Rennes",
    )
    db_session.add(e_past)
    db_session.commit()

    # Query public events
    res = client.get("/api/v1/public/events", headers={"X-No-Auth": "1"})
    assert res.status_code == 200
    returned_ids = [e["id"] for e in res.json()]

    assert e_pub["id"] in returned_ids
    assert e_draft["id"] not in returned_ids
    assert e_archived["id"] not in returned_ids
    assert str(e_past.id) not in returned_ids


def test_get_public_event_draft_or_archived_returns_404(client: TestClient):
    """Vérifie que les événements draft et archived ne sont jamais exposés publiquement."""
    # Draft event
    e_draft = create_sample_event(client, title="Draft Private Event", status="draft")
    res_draft = client.get(f"/api/v1/public/events/{e_draft['slug']}")
    assert res_draft.status_code == 404
    assert res_draft.json()["detail"] == "Événement introuvable ou non publié"

    # Archived event
    e_archived = create_sample_event(client, title="Archived Private Event", status="draft")
    client.patch(f"/api/v1/events/{e_archived['id']}", json={"status": "archived"})
    res_archived = client.get(f"/api/v1/public/events/{e_archived['slug']}")
    assert res_archived.status_code == 404
    assert res_archived.json()["detail"] == "Événement introuvable ou non publié"


def test_list_public_events_spot_availability_aggregation(client: TestClient, db_session: Session):
    now = datetime.now(timezone.utc)
    event = create_sample_event(client, title="Aggregated Spots Event")
    event_id = uuid.UUID(event["id"])
    client.patch(f"/api/v1/events/{event['id']}", json={"status": "published"})

    wkt = geojson_to_wkt_polygon({"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS})

    # Spot 1: available
    s1 = Spot(
        event_id=event_id,
        label="AVAIL-01",
        linear_meters=2.0,
        price_cents=800,
        geom=wkt,
        status="available",
    )
    # Spot 2: locked expired
    s2 = Spot(
        event_id=event_id,
        label="EXPIRED-01",
        linear_meters=2.0,
        price_cents=800,
        geom=wkt,
        status="locked",
        locked_until=now - timedelta(minutes=5),
        locked_by_token="token-expired",
    )
    # Spot 3: locked active
    s3 = Spot(
        event_id=event_id,
        label="LOCKED-01",
        linear_meters=2.0,
        price_cents=800,
        geom=wkt,
        status="locked",
        locked_until=now + timedelta(minutes=10),
        locked_by_token="token-active",
    )
    # Spot 4: reserved
    s4 = Spot(
        event_id=event_id,
        label="RES-01",
        linear_meters=3.0,
        price_cents=1200,
        geom=wkt,
        status="reserved",
    )
    # Spot 5: blocked
    s5 = Spot(
        event_id=event_id,
        label="BLOCKED-01",
        linear_meters=3.0,
        price_cents=1200,
        geom=wkt,
        status="blocked",
    )
    db_session.add_all([s1, s2, s3, s4, s5])

    # Another published event with 0 spots
    e_zero = create_sample_event(client, title="Zero Spots Event")
    client.patch(f"/api/v1/events/{e_zero['id']}", json={"status": "published"})

    db_session.commit()

    res = client.get("/api/v1/public/events", headers={"X-No-Auth": "1"})
    assert res.status_code == 200
    data = res.json()

    item_with_spots = next(e for e in data if e["id"] == str(event_id))
    assert item_with_spots["total_spots"] == 5
    # available (s1) + expired lock (s2) = 2 available spots
    assert item_with_spots["available_spots"] == 2

    item_zero = next(e for e in data if e["id"] == e_zero["id"])
    assert item_zero["total_spots"] == 0
    assert item_zero["available_spots"] == 0


def test_list_public_events_search_filter(client: TestClient):
    e_rennes = create_sample_event(client, title="Grande Braderie de Rennes")
    client.patch(
        f"/api/v1/events/{e_rennes['id']}",
        json={"status": "published", "location_address": "Place Sainte-Anne, 35000 Rennes"},
    )

    e_nantes = create_sample_event(client, title="Brocante de l'Erdre")
    client.patch(
        f"/api/v1/events/{e_nantes['id']}",
        json={"status": "published", "location_address": "Quai de la Fosse, 44000 Nantes"},
    )

    # Event matching via unique keyword in description
    e_desc = create_sample_event(client, title="Foire aux Livres")
    client.patch(
        f"/api/v1/events/{e_desc['id']}",
        json={
            "status": "published",
            "description": "Vente exceptionnelle de bandes dessinées et vinyles rares",
            "location_address": "Gymnase Municipal, 29000 Brest",
        },
    )

    # Search for Rennes
    res_rennes = client.get("/api/v1/public/events?search=rennes", headers={"X-No-Auth": "1"})
    assert res_rennes.status_code == 200
    ids_rennes = [e["id"] for e in res_rennes.json()]
    assert e_rennes["id"] in ids_rennes
    assert e_nantes["id"] not in ids_rennes
    assert e_desc["id"] not in ids_rennes

    # Search for Erdre
    res_erdre = client.get("/api/v1/public/events?search=erdre", headers={"X-No-Auth": "1"})
    assert res_erdre.status_code == 200
    ids_erdre = [e["id"] for e in res_erdre.json()]
    assert e_nantes["id"] in ids_erdre
    assert e_rennes["id"] not in ids_erdre
    assert e_desc["id"] not in ids_erdre

    # Search for keyword in description
    res_desc = client.get("/api/v1/public/events?search=vinyles", headers={"X-No-Auth": "1"})
    assert res_desc.status_code == 200
    ids_desc = [e["id"] for e in res_desc.json()]
    assert e_desc["id"] in ids_desc
    assert e_rennes["id"] not in ids_desc
    assert e_nantes["id"] not in ids_desc

    # Search non-matching
    res_none = client.get("/api/v1/public/events?search=xyzinexistant", headers={"X-No-Auth": "1"})
    assert res_none.status_code == 200
    assert res_none.json() == []


def test_list_public_events_chronological_ordering(client: TestClient, db_session: Session):
    now = datetime.now(timezone.utc)

    # Event in 10 days
    e_later = create_sample_event(client, title="Later Event")
    client.patch(
        f"/api/v1/events/{e_later['id']}",
        json={
            "status": "published",
            "start_date": (now + timedelta(days=10)).isoformat(),
            "end_date": (now + timedelta(days=11)).isoformat(),
        },
    )

    # Event in 2 days
    e_sooner = create_sample_event(client, title="Sooner Event")
    client.patch(
        f"/api/v1/events/{e_sooner['id']}",
        json={
            "status": "published",
            "start_date": (now + timedelta(days=2)).isoformat(),
            "end_date": (now + timedelta(days=3)).isoformat(),
        },
    )

    res = client.get("/api/v1/public/events", headers={"X-No-Auth": "1"})
    assert res.status_code == 200
    data = res.json()

    ids = [e["id"] for e in data if e["id"] in (e_later["id"], e_sooner["id"])]
    assert ids == [e_sooner["id"], e_later["id"]]


def test_list_public_events_zero_sensitive_data_leak(client: TestClient):
    event = create_sample_event(client, title="Secure Public Listing Event")
    client.patch(f"/api/v1/events/{event['id']}", json={"status": "published"})

    res = client.get("/api/v1/public/events", headers={"X-No-Auth": "1"})
    assert res.status_code == 200
    item = next(e for e in res.json() if e["id"] == event["id"])

    assert "stripe_account_id" not in item
    assert "owner_id" not in item
    assert "organizer_email" not in item


