import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient


def create_sample_event(client: TestClient, title="Brocante du Port", price_per_meter=8.0, map_type="geographic"):
    now = datetime.now(timezone.utc)
    payload = {
        "title": title,
        "description": "Un super vide-grenier en plein air",
        "map_type": map_type,
        "price_per_meter": price_per_meter,
        "start_date": (now + timedelta(days=10)).isoformat(),
        "end_date": (now + timedelta(days=10, hours=10)).isoformat(),
        "setup_start_time": "06:00",
        "setup_end_time": "08:00",
        "public_start_time": "08:00",
        "public_end_time": "18:00",
        "location_address": "10 Quai des Flâneurs, 35400 Saint-Malo",
    }
    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


SAMPLE_POLY_COORDS = [
    [
        [-2.025, 48.650],
        [-2.020, 48.650],
        [-2.020, 48.652],
        [-2.025, 48.652],
        [-2.025, 48.650],
    ]
]


def test_create_spot_auto_price_calculation(client: TestClient):
    event = create_sample_event(client, price_per_meter=8.0)
    event_id = event["id"]

    spot_payload = {
        "label": "A01",
        "linear_meters": 3.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": SAMPLE_POLY_COORDS,
        },
    }

    response = client.post(f"/api/v1/events/{event_id}/spots", json=spot_payload)
    assert response.status_code == 201, response.text
    data = response.json()

    assert data["type"] == "Feature"
    assert "id" in data
    assert data["geometry"]["type"] == "Polygon"
    assert data["geometry"]["coordinates"] == SAMPLE_POLY_COORDS
    assert data["properties"]["label"] == "A01"
    assert data["properties"]["linear_meters"] == 3.0
    # 3.0 meters * 800 cents = 2400 cents
    assert data["properties"]["price_cents"] == 2400
    assert data["properties"]["price"] == 24.0
    assert data["properties"]["status"] == "available"


def test_create_spot_with_manual_price_override(client: TestClient):
    event = create_sample_event(client, price_per_meter=8.0)
    event_id = event["id"]

    # Default would be 2.0 * 800 = 1600 cents, but organizer sets 2500 cents (corner spot)
    spot_payload = {
        "label": "Corner 1",
        "linear_meters": 2.0,
        "price_cents": 2500,
        "geometry": {
            "type": "Polygon",
            "coordinates": SAMPLE_POLY_COORDS,
        },
    }

    response = client.post(f"/api/v1/events/{event_id}/spots", json=spot_payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["properties"]["price_cents"] == 2500
    assert data["properties"]["price"] == 25.0


def test_create_spot_invalid_linear_meters_rejected(client: TestClient):
    event = create_sample_event(client)
    event_id = event["id"]

    # 0 linear meters
    res_zero = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "Invalid 1",
            "linear_meters": 0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    assert res_zero.status_code == 422

    # Negative linear meters
    res_neg = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "Invalid 2",
            "linear_meters": -1.5,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    assert res_neg.status_code == 422


def test_create_spot_duplicate_label_conflict(client: TestClient):
    event = create_sample_event(client)
    event_id = event["id"]

    spot_payload = {
        "label": "Stand 1",
        "linear_meters": 2.0,
        "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
    }

    res1 = client.post(f"/api/v1/events/{event_id}/spots", json=spot_payload)
    assert res1.status_code == 201

    # Attempt duplicate
    res2 = client.post(f"/api/v1/events/{event_id}/spots", json=spot_payload)
    assert res2.status_code == 409
    assert "existe déjà" in res2.json()["detail"]


def test_list_spots_as_geojson_feature_collection(client: TestClient):
    event = create_sample_event(client)
    event_id = event["id"]

    # Create two spots
    client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "Stand 1",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "Stand 2",
            "linear_meters": 4.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )

    response = client.get(f"/api/v1/events/{event_id}/spots")
    assert response.status_code == 200
    data = response.json()

    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 2
    assert data["features"][0]["properties"]["label"] == "Stand 1"
    assert data["features"][1]["properties"]["label"] == "Stand 2"


def test_get_and_patch_spot(client: TestClient):
    event = create_sample_event(client, price_per_meter=10.0)
    event_id = event["id"]

    create_res = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "Initial Label",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    spot = create_res.json()
    spot_id = spot["id"]
    assert spot["properties"]["price_cents"] == 2000

    # Retrieve single spot
    get_res = client.get(f"/api/v1/events/{event_id}/spots/{spot_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == spot_id

    # Update linear_meters -> auto recalculates price
    patch_res = client.patch(
        f"/api/v1/events/{event_id}/spots/{spot_id}",
        json={
            "label": "Updated Label",
            "linear_meters": 3.5,
        },
    )
    assert patch_res.status_code == 200
    patched = patch_res.json()
    assert patched["properties"]["label"] == "Updated Label"
    assert patched["properties"]["linear_meters"] == 3.5
    # 3.5 * 1000 = 3500 cents
    assert patched["properties"]["price_cents"] == 3500
    assert patched["properties"]["price"] == 35.0

    # Update geometry (e.g. rotated / moved)
    NEW_COORDS = [
        [
            [-2.030, 48.660],
            [-2.025, 48.660],
            [-2.025, 48.665],
            [-2.030, 48.665],
            [-2.030, 48.660],
        ]
    ]
    patch_geom = client.patch(
        f"/api/v1/events/{event_id}/spots/{spot_id}",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": NEW_COORDS,
            }
        },
    )
    assert patch_geom.status_code == 200
    assert patch_geom.json()["geometry"]["coordinates"] == NEW_COORDS


def test_delete_spot(client: TestClient):
    event = create_sample_event(client)
    event_id = event["id"]

    create_res = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "To Delete",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    spot_id = create_res.json()["id"]

    # Delete
    del_res = client.delete(f"/api/v1/events/{event_id}/spots/{spot_id}")
    assert del_res.status_code == 204

    # Verify not found
    get_res = client.get(f"/api/v1/events/{event_id}/spots/{spot_id}")
    assert get_res.status_code == 404

    # Verify list is empty
    list_res = client.get(f"/api/v1/events/{event_id}/spots")
    assert len(list_res.json()["features"]) == 0


def test_planar_mode_pixel_coordinates(client: TestClient):
    event = create_sample_event(client, map_type="planar")
    event_id = event["id"]

    PLANAR_COORDS = [
        [
            [120.0, 350.0],
            [180.0, 350.0],
            [180.0, 420.0],
            [120.0, 420.0],
            [120.0, 350.0],
        ]
    ]

    create_res = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "Stand Gymnase 1",
            "linear_meters": 2.5,
            "geometry": {
                "type": "Polygon",
                "coordinates": PLANAR_COORDS,
            },
        },
    )
    assert create_res.status_code == 201
    spot = create_res.json()
    assert spot["geometry"]["coordinates"] == PLANAR_COORDS

    list_res = client.get(f"/api/v1/events/{event_id}/spots")
    assert len(list_res.json()["features"]) == 1
    assert list_res.json()["features"][0]["geometry"]["coordinates"] == PLANAR_COORDS


def test_cross_event_data_isolation(client: TestClient):
    event1 = create_sample_event(client, title="Event 1")
    event2 = create_sample_event(client, title="Event 2")

    # Create spot in Event 1
    res1 = client.post(
        f"/api/v1/events/{event1['id']}/spots",
        json={
            "label": "E1-Spot",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    spot1_id = res1.json()["id"]

    # Verify Event 2 list does NOT include spot1
    list2 = client.get(f"/api/v1/events/{event2['id']}/spots").json()
    assert len(list2["features"]) == 0

    # Cross-event access fails with 404
    assert client.get(f"/api/v1/events/{event2['id']}/spots/{spot1_id}").status_code == 404
    assert client.patch(f"/api/v1/events/{event2['id']}/spots/{spot1_id}", json={"label": "Hacked"}).status_code == 404
    assert client.delete(f"/api/v1/events/{event2['id']}/spots/{spot1_id}").status_code == 404


def test_slug_based_event_resolution(client: TestClient):
    event = create_sample_event(client, title="Brocante du Port Slug")
    slug = event["slug"]

    # Create spot via slug
    create_res = client.post(
        f"/api/v1/events/{slug}/spots",
        json={
            "label": "S01",
            "linear_meters": 2.5,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    assert create_res.status_code == 201
    spot_id = create_res.json()["id"]

    # List via slug
    list_res = client.get(f"/api/v1/events/{slug}/spots")
    assert list_res.status_code == 200
    assert len(list_res.json()["features"]) == 1

    # Get single via slug
    get_res = client.get(f"/api/v1/events/{slug}/spots/{spot_id}")
    assert get_res.status_code == 200

    # Patch via slug
    patch_res = client.patch(f"/api/v1/events/{slug}/spots/{spot_id}", json={"label": "S01-Updated"})
    assert patch_res.status_code == 200
    assert patch_res.json()["properties"]["label"] == "S01-Updated"

    # Delete via slug
    del_res = client.delete(f"/api/v1/events/{slug}/spots/{spot_id}")
    assert del_res.status_code == 204


def test_patch_price_override(client: TestClient):
    event = create_sample_event(client, price_per_meter=10.0)
    event_id = event["id"]

    create_res = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "P01",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    spot_id = create_res.json()["id"]
    assert create_res.json()["properties"]["price_cents"] == 2000

    # Explicit price override via price_cents
    patch_res = client.patch(
        f"/api/v1/events/{event_id}/spots/{spot_id}",
        json={"price_cents": 5000},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["properties"]["price_cents"] == 5000
    assert patch_res.json()["properties"]["price"] == 50.0

    # Explicit price override via price in euros
    patch_res2 = client.patch(
        f"/api/v1/events/{event_id}/spots/{spot_id}",
        json={"price": 75.50},
    )
    assert patch_res2.status_code == 200
    assert patch_res2.json()["properties"]["price_cents"] == 7550
    assert patch_res2.json()["properties"]["price"] == 75.5


def test_patch_validation_linear_meters_and_whitespace_label(client: TestClient):
    event = create_sample_event(client)
    event_id = event["id"]

    create_res = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "V01",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    spot_id = create_res.json()["id"]

    # Reject linear_meters = 0
    res_zero = client.patch(f"/api/v1/events/{event_id}/spots/{spot_id}", json={"linear_meters": 0})
    assert res_zero.status_code == 422

    # Reject negative linear_meters
    res_neg = client.patch(f"/api/v1/events/{event_id}/spots/{spot_id}", json={"linear_meters": -1.0})
    assert res_neg.status_code == 422

    # Reject whitespace-only label
    res_ws = client.patch(f"/api/v1/events/{event_id}/spots/{spot_id}", json={"label": "   "})
    assert res_ws.status_code == 422


def test_delete_reserved_spot_rejected(client: TestClient):
    event = create_sample_event(client)
    event_id = event["id"]

    create_res = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "Res01",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    spot_id = create_res.json()["id"]

    # Mark as reserved
    client.patch(f"/api/v1/events/{event_id}/spots/{spot_id}", json={"status": "reserved"})

    # Attempt delete -> 400 Bad Request
    del_res = client.delete(f"/api/v1/events/{event_id}/spots/{spot_id}")
    assert del_res.status_code == 400
    assert "réservé" in del_res.json()["detail"]


