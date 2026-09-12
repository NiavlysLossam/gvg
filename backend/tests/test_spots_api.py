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


def test_batch_create_spots_success(client: TestClient):
    event = create_sample_event(client, price_per_meter=10.0)
    event_id = event["id"]

    spots_payload = []
    for i in range(1, 11):
        x_offset = i * 0.005
        spot_item = {
            "label": f"Allée A - {i:02d}",
            "linear_meters": 2.0,
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-2.025 + x_offset, 48.650],
                        [-2.020 + x_offset, 48.650],
                        [-2.020 + x_offset, 48.652],
                        [-2.025 + x_offset, 48.652],
                        [-2.025 + x_offset, 48.650],
                    ]
                ],
            },
        }
        # Explicit price override on the first spot to verify it overrides linear meters calculation
        if i == 1:
            spot_item["price_cents"] = 3500
        spots_payload.append(spot_item)

    res = client.post(f"/api/v1/events/{event_id}/spots/batch", json={"spots": spots_payload})
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert data["created_count"] == 10
    assert len(data["features"]) == 10

    for idx, feature in enumerate(data["features"], start=1):
        expected_label = f"Allée A - {idx:02d}"
        assert feature["properties"]["label"] == expected_label
        assert feature["properties"]["linear_meters"] == 2.0
        if idx == 1:
            assert feature["properties"]["price_cents"] == 3500
            assert feature["properties"]["price"] == 35.0
        else:
            # 2.0m * 1000 cents = 2000 cents
            assert feature["properties"]["price_cents"] == 2000
            assert feature["properties"]["price"] == 20.0

    # Verify all 10 are retrieved by GET
    list_res = client.get(f"/api/v1/events/{event_id}/spots")
    assert len(list_res.json()["features"]) == 10


def test_batch_create_spots_duplicate_within_batch_rollback(client: TestClient):
    event = create_sample_event(client)
    event_id = event["id"]

    spots_payload = [
        {
            "label": "Stand X",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
        {
            "label": "Stand X",  # duplicate
            "linear_meters": 3.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    ]

    res = client.post(f"/api/v1/events/{event_id}/spots/batch", json={"spots": spots_payload})
    assert res.status_code == 409
    assert "Stand X" in res.json()["detail"]

    # Verify zero spots were created
    list_res = client.get(f"/api/v1/events/{event_id}/spots")
    assert len(list_res.json()["features"]) == 0


def test_batch_create_spots_duplicate_with_existing_spot_rollback(client: TestClient):
    event = create_sample_event(client)
    event_id = event["id"]

    # Create initial spot
    client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "Allée A - 02",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )

    # Attempt batch creating 3 spots including duplicate "Allée A - 02"
    batch_payload = [
        {
            "label": "Allée A - 01",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
        {
            "label": "Allée A - 02",  # Collision!
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
        {
            "label": "Allée A - 03",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    ]

    res = client.post(f"/api/v1/events/{event_id}/spots/batch", json={"spots": batch_payload})
    assert res.status_code == 409
    assert "Allée A - 02" in res.json()["detail"]

    # Verify only initial spot remains, none of the batch spots were inserted
    list_res = client.get(f"/api/v1/events/{event_id}/spots")
    features = list_res.json()["features"]
    assert len(features) == 1
    assert features[0]["properties"]["label"] == "Allée A - 02"


def test_batch_create_spots_planar_coordinates(client: TestClient):
    event = create_sample_event(client, map_type="planar")
    event_id = event["id"]

    planar_coords = [
        [[100.0, 150.0], [200.0, 150.0], [200.0, 250.0], [100.0, 250.0], [100.0, 150.0]]
    ]
    batch_payload = [
        {
            "label": "Salle Stand 1",
            "linear_meters": 3.0,
            "geometry": {"type": "Polygon", "coordinates": planar_coords},
        }
    ]

    res = client.post(f"/api/v1/events/{event_id}/spots/batch", json={"spots": batch_payload})
    assert res.status_code == 201
    assert res.json()["features"][0]["geometry"]["coordinates"] == planar_coords


def test_batch_renumber_sequential_with_prefix_and_padding(client: TestClient):
    event = create_sample_event(client)
    event_id = event["id"]

    # Create 3 spots with provisional labels
    created_ids = []
    for i in range(1, 4):
        create_res = client.post(
            f"/api/v1/events/{event_id}/spots",
            json={
                "label": f"Old {i}",
                "linear_meters": 2.0,
                "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
            },
        )
        created_ids.append(create_res.json()["id"])

    # Renumber with prefix, start=1, zero_padding=2
    renumber_res = client.post(
        f"/api/v1/events/{event_id}/spots/batch-renumber",
        json={
            "spot_ids": created_ids,
            "prefix": "Allée B - ",
            "start_number": 1,
            "zero_padding": 2,
        },
    )
    assert renumber_res.status_code == 200, renumber_res.text
    data = renumber_res.json()
    assert data["updated_count"] == 3
    assert [f["properties"]["label"] for f in data["features"]] == [
        "Allée B - 01",
        "Allée B - 02",
        "Allée B - 03",
    ]


def test_batch_renumber_two_phase_swap_and_shift(client: TestClient):
    event = create_sample_event(client)
    event_id = event["id"]

    # Create spots "1", "2", "3"
    ids = []
    for lbl in ["1", "2", "3"]:
        res = client.post(
            f"/api/v1/events/{event_id}/spots",
            json={
                "label": lbl,
                "linear_meters": 2.0,
                "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
            },
        )
        ids.append(res.json()["id"])

    # Shift labels: spot 1 -> 2, spot 2 -> 3, spot 3 -> 1
    # This would fail with UniqueConstraint if not done in two phases
    mapping = [
        {"spot_id": ids[0], "label": "2"},
        {"spot_id": ids[1], "label": "3"},
        {"spot_id": ids[2], "label": "1"},
    ]

    renumber_res = client.post(
        f"/api/v1/events/{event_id}/spots/batch-renumber",
        json={"renumberings": mapping},
    )
    assert renumber_res.status_code == 200, renumber_res.text
    labels = [f["properties"]["label"] for f in renumber_res.json()["features"]]
    assert labels == ["2", "3", "1"]


def test_batch_renumber_conflict_with_existing_spot_rollback(client: TestClient):
    event = create_sample_event(client)
    event_id = event["id"]

    # Create an existing spot "Occupied"
    client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "Occupied",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )

    # Create two spots "ToRenumber1" and "ToRenumber2"
    res1 = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "ToRenumber1",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    target_id1 = res1.json()["id"]

    res2 = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "ToRenumber2",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    target_id2 = res2.json()["id"]

    # Attempt renumbering ToRenumber1 to "ValidLabel" and ToRenumber2 to "Occupied"
    # -> HTTP 409, and BOTH spots must roll back atomically!
    renumber_res = client.post(
        f"/api/v1/events/{event_id}/spots/batch-renumber",
        json={
            "renumberings": [
                {"spot_id": target_id1, "label": "ValidLabel"},
                {"spot_id": target_id2, "label": "Occupied"},
            ],
        },
    )
    assert renumber_res.status_code == 409
    assert "Occupied" in renumber_res.json()["detail"]

    # Verify NEITHER label changed (atomic rollback)
    check1 = client.get(f"/api/v1/events/{event_id}/spots/{target_id1}")
    assert check1.json()["properties"]["label"] == "ToRenumber1"

    check2 = client.get(f"/api/v1/events/{event_id}/spots/{target_id2}")
    assert check2.json()["properties"]["label"] == "ToRenumber2"


def test_batch_renumber_cross_event_isolation(client: TestClient):
    event1 = create_sample_event(client, title="Event 1")
    event2 = create_sample_event(client, title="Event 2")

    # Spot in Event 2
    res2 = client.post(
        f"/api/v1/events/{event2['id']}/spots",
        json={
            "label": "SpotEv2",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    spot_ev2_id = res2.json()["id"]

    # Try renumbering spot of Event 2 via Event 1 endpoint -> 400 Bad Request
    renumber_res = client.post(
        f"/api/v1/events/{event1['id']}/spots/batch-renumber",
        json={
            "renumberings": [{"spot_id": spot_ev2_id, "label": "NewEv1"}],
        },
    )
    assert renumber_res.status_code == 400
    assert "n'appartient pas" in renumber_res.json()["detail"]


def test_batch_renumber_duplicate_spot_ids_rejected(client: TestClient):
    event = create_sample_event(client)
    event_id = event["id"]

    res = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "Spot1",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    spot_id = res.json()["id"]

    # Duplicate in spot_ids
    res_dup_ids = client.post(
        f"/api/v1/events/{event_id}/spots/batch-renumber",
        json={"spot_ids": [spot_id, spot_id], "prefix": "A-"},
    )
    assert res_dup_ids.status_code == 422
    assert "dupliqués" in res_dup_ids.text

    # Duplicate in renumberings
    res_dup_renum = client.post(
        f"/api/v1/events/{event_id}/spots/batch-renumber",
        json={
            "renumberings": [
                {"spot_id": spot_id, "label": "LabelA"},
                {"spot_id": spot_id, "label": "LabelB"},
            ]
        },
    )
    assert res_dup_renum.status_code == 422
    assert "dupliqués" in res_dup_renum.text


def test_batch_renumber_prefix_too_long_rejected(client: TestClient):
    event = create_sample_event(client)
    event_id = event["id"]

    res = client.post(
        f"/api/v1/events/{event_id}/spots",
        json={
            "label": "SpotLong",
            "linear_meters": 2.0,
            "geometry": {"type": "Polygon", "coordinates": SAMPLE_POLY_COORDS},
        },
    )
    spot_id = res.json()["id"]

    # Prefix > 80 chars
    long_prefix = "A" * 85
    res_long = client.post(
        f"/api/v1/events/{event_id}/spots/batch-renumber",
        json={"spot_ids": [spot_id], "prefix": long_prefix},
    )
    assert res_long.status_code == 422



