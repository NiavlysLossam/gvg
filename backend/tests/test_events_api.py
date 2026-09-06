import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "project" in data

    response_v1 = client.get("/api/v1/health")
    assert response_v1.status_code == 200
    assert response_v1.json()["status"] == "ok"


def test_create_valid_event(client: TestClient):
    now = datetime.now(timezone.utc)
    payload = {
        "title": "Vide-Grenier de Printemps",
        "description": "Grand vide-grenier annuel du quartier",
        "start_date": (now + timedelta(days=30)).isoformat(),
        "end_date": (now + timedelta(days=30, hours=12)).isoformat(),
        "setup_start_time": "06:00",
        "setup_end_time": "08:00",
        "public_start_time": "08:00",
        "public_end_time": "18:00",
        "location_address": "Place de la République, 75011 Paris",
        "organizer_email": "marc.organisateur@example.com",
        "price_per_meter": 4.00,
        "map_type": "geographic",
    }

    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()

    assert "id" in data
    assert uuid.UUID(data["id"])  # Valid UUID
    assert data["slug"] == "vide-grenier-de-printemps"
    assert data["status"] == "draft"
    assert data["price_per_meter_cents"] == 400
    assert data["price_per_meter"] == 4.0
    assert data["title"] == payload["title"]
    assert data["location_address"] == payload["location_address"]
    assert data["map_type"] == "geographic"


def test_duplicate_title_collision(client: TestClient):
    now = datetime.now(timezone.utc)
    base_payload = {
        "title": "Vide-Grenier Saint-Michel",
        "start_date": (now + timedelta(days=10)).isoformat(),
        "end_date": (now + timedelta(days=10, hours=10)).isoformat(),
        "price_per_meter_cents": 500,
    }

    # First event
    resp1 = client.post("/api/v1/events", json=base_payload)
    assert resp1.status_code == 201
    assert resp1.json()["slug"] == "vide-grenier-saint-michel"

    # Second event with identical title
    resp2 = client.post("/api/v1/events", json=base_payload)
    assert resp2.status_code == 201
    assert resp2.json()["slug"] == "vide-grenier-saint-michel-2"

    # Third event with identical title
    resp3 = client.post("/api/v1/events", json=base_payload)
    assert resp3.status_code == 201
    assert resp3.json()["slug"] == "vide-grenier-saint-michel-3"


def test_invalid_date_range(client: TestClient):
    now = datetime.now(timezone.utc)
    payload = {
        "title": "Événement Invalide",
        "start_date": (now + timedelta(days=10)).isoformat(),
        "end_date": (now + timedelta(days=9)).isoformat(),  # End before start
        "price_per_meter": 5.0,
    }

    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert any("end_date" in str(err) for err in data["detail"])


def test_negative_or_zero_price(client: TestClient):
    now = datetime.now(timezone.utc)

    # Negative price
    payload_neg = {
        "title": "Tarif Négatif",
        "start_date": (now + timedelta(days=10)).isoformat(),
        "end_date": (now + timedelta(days=10, hours=8)).isoformat(),
        "price_per_meter": -4.00,
    }
    response_neg = client.post("/api/v1/events", json=payload_neg)
    assert response_neg.status_code == 422
    assert "detail" in response_neg.json()

    # Zero price
    payload_zero = {
        "title": "Tarif Zéro",
        "start_date": (now + timedelta(days=10)).isoformat(),
        "end_date": (now + timedelta(days=10, hours=8)).isoformat(),
        "price_per_meter_cents": 0,
    }
    response_zero = client.post("/api/v1/events", json=payload_zero)
    assert response_zero.status_code == 422
    assert "detail" in response_zero.json()


def test_get_event_by_id_and_slug(client: TestClient):
    now = datetime.now(timezone.utc)
    payload = {
        "title": "Brocante du Port",
        "start_date": (now + timedelta(days=20)).isoformat(),
        "end_date": (now + timedelta(days=20, hours=10)).isoformat(),
        "price_per_meter_cents": 650,
        "location_address": "Quai des Pêcheurs, 29200 Brest",
    }
    create_resp = client.post("/api/v1/events", json=payload)
    assert create_resp.status_code == 201
    created = create_resp.json()
    event_id = created["id"]
    event_slug = created["slug"]

    # Retrieve by UUID
    resp_id = client.get(f"/api/v1/events/{event_id}")
    assert resp_id.status_code == 200
    assert resp_id.json()["id"] == event_id
    assert resp_id.json()["title"] == "Brocante du Port"

    # Retrieve by Slug
    resp_slug = client.get(f"/api/v1/events/{event_slug}")
    assert resp_slug.status_code == 200
    assert resp_slug.json()["id"] == event_id
    assert resp_slug.json()["slug"] == event_slug

    # Non-existent UUID
    random_uuid = str(uuid.uuid4())
    resp_404_id = client.get(f"/api/v1/events/{random_uuid}")
    assert resp_404_id.status_code == 404
    assert resp_404_id.json()["detail"] == "Event not found"

    # Non-existent Slug
    resp_404_slug = client.get("/api/v1/events/slug-qui-n-existe-pas")
    assert resp_404_slug.status_code == 404
    assert resp_404_slug.json()["detail"] == "Event not found"


def test_list_events(client: TestClient):
    now = datetime.now(timezone.utc)
    for i in range(3):
        client.post(
            "/api/v1/events",
            json={
                "title": f"Événement {i}",
                "start_date": (now + timedelta(days=i + 1)).isoformat(),
                "end_date": (now + timedelta(days=i + 1, hours=8)).isoformat(),
                "price_per_meter_cents": 300,
            },
        )

    response = client.get("/api/v1/events")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 3
    assert len(data["items"]) == 3


def test_list_events_descending_order_and_pagination(client: TestClient):
    now = datetime.now(timezone.utc)
    # Create 5 events with distinct start dates
    created_titles = []
    for i in range(5):
        title = f"Événement Tri {i}"
        created_titles.append(title)
        client.post(
            "/api/v1/events",
            json={
                "title": title,
                "start_date": (now + timedelta(days=i * 2)).isoformat(),
                "end_date": (now + timedelta(days=i * 2, hours=6)).isoformat(),
                "price_per_meter": 5.0,
            },
        )

    # Test descending order (latest start_date first)
    resp = client.get("/api/v1/events?skip=0&limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    # First item should be the latest (index 4)
    assert data["items"][0]["title"] == "Événement Tri 4"
    assert data["items"][1]["title"] == "Événement Tri 3"

    # Test skip pagination
    resp_page2 = client.get("/api/v1/events?skip=2&limit=2")
    assert resp_page2.status_code == 200
    data_page2 = resp_page2.json()
    assert len(data_page2["items"]) == 2
    assert data_page2["items"][0]["title"] == "Événement Tri 2"
    assert data_page2["items"][1]["title"] == "Événement Tri 1"


def test_patch_event_and_date_validation(client: TestClient):
    now = datetime.now(timezone.utc)
    start = now + timedelta(days=10)
    end = now + timedelta(days=12)

    create_resp = client.post(
        "/api/v1/events",
        json={
            "title": "Grand Marché aux Puces",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "price_per_meter": 4.5,
        },
    )
    assert create_resp.status_code == 201
    event = create_resp.json()
    event_id = event["id"]
    assert event["slug"] == "grand-marche-aux-puces"

    # 1. Successful patch: update title without self-collision
    patch_resp = client.patch(
        f"/api/v1/events/{event_id}",
        json={"title": "Grand Marché aux Puces Rénové", "price_per_meter": 6.0},
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["title"] == "Grand Marché aux Puces Rénové"
    assert updated["slug"] == "grand-marche-aux-puces-renove"
    assert updated["price_per_meter_cents"] == 600
    assert updated["price_per_meter"] == 6.0

    # 2. Patch with same title does not append -2 suffix (avoids self-collision)
    patch_same_title = client.patch(
        f"/api/v1/events/{event_id}",
        json={"title": "Grand Marché aux Puces Rénové"},
    )
    assert patch_same_title.status_code == 200
    assert patch_same_title.json()["slug"] == "grand-marche-aux-puces-renove"

    # 3. Partial date update: updating ONLY start_date to be AFTER existing end_date fails
    bad_start = end + timedelta(days=1)
    resp_bad_start = client.patch(
        f"/api/v1/events/{event_id}",
        json={"start_date": bad_start.isoformat()},
    )
    assert resp_bad_start.status_code == 422
    assert "end_date must be greater than or equal to start_date" in str(resp_bad_start.json()["detail"])

    # 4. Partial date update: updating ONLY end_date to be BEFORE existing start_date fails
    bad_end = start - timedelta(days=1)
    resp_bad_end = client.patch(
        f"/api/v1/events/{event_id}",
        json={"end_date": bad_end.isoformat()},
    )
    assert resp_bad_end.status_code == 422
    assert "end_date must be greater than or equal to start_date" in str(resp_bad_end.json()["detail"])

    # 5. Patch non-existent event returns 404
    resp_404 = client.patch(
        f"/api/v1/events/{uuid.uuid4()}",
        json={"title": "Inconnu"},
    )
    assert resp_404.status_code == 404

    # 6. Patch by slug successfully resolves and updates event
    resp_patch_slug = client.patch(
        f"/api/v1/events/{updated['slug']}",
        json={"description": "Mise à jour via slug"},
    )
    assert resp_patch_slug.status_code == 200
    assert resp_patch_slug.json()["description"] == "Mise à jour via slug"

    # 7. Patch non-existent slug returns 404
    resp_nonexistent_slug = client.patch(
        "/api/v1/events/non-existent-slug-xyz",
        json={"title": "Inconnu"},
    )
    assert resp_nonexistent_slug.status_code == 404


def test_fallback_slug_for_non_alphanumeric_title(client: TestClient):
    now = datetime.now(timezone.utc)
    resp = client.post(
        "/api/v1/events",
        json={
            "title": "🎉 ??? 🚀",
            "start_date": (now + timedelta(days=5)).isoformat(),
            "end_date": (now + timedelta(days=6)).isoformat(),
            "price_per_meter": 5.0,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["slug"] == "evenement"


def test_list_events_status_filter(client: TestClient):
    now = datetime.now(timezone.utc)
    # Create draft event
    draft_resp = client.post(
        "/api/v1/events",
        json={
            "title": "Vide-Grenier Brouillon Filter",
            "start_date": (now + timedelta(days=1)).isoformat(),
            "end_date": (now + timedelta(days=2)).isoformat(),
            "price_per_meter": 3.0,
            "status": "draft",
        },
    )
    assert draft_resp.status_code == 201

    # Create published event
    published_resp = client.post(
        "/api/v1/events",
        json={
            "title": "Vide-Grenier Publie Filter",
            "start_date": (now + timedelta(days=3)).isoformat(),
            "end_date": (now + timedelta(days=4)).isoformat(),
            "price_per_meter": 4.0,
            "status": "published",
        },
    )
    assert published_resp.status_code == 201

    # Filter by draft
    filter_draft = client.get("/api/v1/events?status=draft")
    assert filter_draft.status_code == 200
    draft_items = filter_draft.json()["items"]
    assert all(item["status"] == "draft" for item in draft_items)
    assert any(item["title"] == "Vide-Grenier Brouillon Filter" for item in draft_items)
    assert not any(item["title"] == "Vide-Grenier Publie Filter" for item in draft_items)

    # Filter by published
    filter_pub = client.get("/api/v1/events?status=published")
    assert filter_pub.status_code == 200
    pub_items = filter_pub.json()["items"]
    assert all(item["status"] == "published" for item in pub_items)
    assert any(item["title"] == "Vide-Grenier Publie Filter" for item in pub_items)
    assert not any(item["title"] == "Vide-Grenier Brouillon Filter" for item in pub_items)


