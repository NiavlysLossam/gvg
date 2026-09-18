import io
import uuid
from pathlib import Path
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
        "poster_image_url": "https://example.com/affiche.webp",
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
    assert data["poster_image_url"] == "https://example.com/affiche.webp"


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
        json={
            "title": "Grand Marché aux Puces Rénové",
            "price_per_meter": 6.0,
            "poster_image_url": "https://example.com/renove.jpg",
        },
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["title"] == "Grand Marché aux Puces Rénové"
    assert updated["slug"] == "grand-marche-aux-puces-renove"
    assert updated["price_per_meter_cents"] == 600
    assert updated["price_per_meter"] == 6.0
    assert updated["poster_image_url"] == "https://example.com/renove.jpg"

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


def test_upload_valid_poster_png_jpeg_webp(client: TestClient):
    """Test valid PNG, JPEG, and WebP poster uploads and static serving."""
    now = datetime.now(timezone.utc)
    create_res = client.post(
        "/api/v1/events",
        json={
            "title": "Vide-Grenier Affiche Test",
            "start_date": (now + timedelta(days=5)).isoformat(),
            "end_date": (now + timedelta(days=6)).isoformat(),
            "price_per_meter": 4.0,
        },
    )
    assert create_res.status_code == 201
    event = create_res.json()
    event_id = event["id"]
    slug = event["slug"]

    # 1. Upload valid PNG
    png_content = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x00\x00"
        b"\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    files_png = {"file": ("poster.png", io.BytesIO(png_content), "image/png")}
    res_png = client.post(f"/api/v1/events/{event_id}/poster", files=files_png)
    assert res_png.status_code == 200, res_png.text
    data_png = res_png.json()
    assert data_png["poster_image_url"] is not None
    assert data_png["poster_image_url"].startswith("/uploads/posters/")
    assert data_png["poster_image_url"].endswith(".png")

    # Verify static file serving via GET
    static_res = client.get(data_png["poster_image_url"])
    assert static_res.status_code == 200
    assert static_res.content == png_content

    # 2. Upload valid JPEG via slug
    jpg_content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb"
    files_jpg = {"file": ("poster.jpg", io.BytesIO(jpg_content), "image/jpeg")}
    res_jpg = client.post(f"/api/v1/events/{slug}/poster", files=files_jpg)
    assert res_jpg.status_code == 200
    assert res_jpg.json()["poster_image_url"].endswith(".jpg")

    # Verify old PNG file was unlinked from disk upon replacement
    from app.core.config import settings
    old_png_disk = settings.upload_dir_path / "posters" / data_png["poster_image_url"].removeprefix("/uploads/posters/")
    assert not old_png_disk.exists()

    # 3. Upload valid WebP
    webp_content = b"RIFF\x14\x00\x00\x00WEBPVP8 \x08\x00\x00\x00"
    files_webp = {"file": ("poster.webp", io.BytesIO(webp_content), "image/webp")}
    res_webp = client.post(f"/api/v1/events/{event_id}/poster", files=files_webp)
    assert res_webp.status_code == 200
    assert res_webp.json()["poster_image_url"].endswith(".webp")


def test_upload_poster_exceeding_5mb_limit(client: TestClient):
    """Test rejection of poster exceeding 5 MB limit with HTTP 413."""
    now = datetime.now(timezone.utc)
    create_res = client.post(
        "/api/v1/events",
        json={
            "title": "Vide-Grenier Poster Size Limit",
            "start_date": (now + timedelta(days=5)).isoformat(),
            "end_date": (now + timedelta(days=6)).isoformat(),
            "price_per_meter": 4.0,
        },
    )
    event_id = create_res.json()["id"]

    # 5.2 MB payload
    oversized = b"A" * (5 * 1024 * 1024 + 200 * 1024)
    files = {"file": ("huge_poster.png", io.BytesIO(oversized), "image/png")}
    response = client.post(f"/api/v1/events/{event_id}/poster", files=files)
    assert response.status_code == 413
    assert "5 Mo" in response.json()["detail"]


def test_upload_poster_validation_errors(client: TestClient):
    """Test MIME, empty file, and spoofed magic bytes rejection."""
    now = datetime.now(timezone.utc)
    create_res = client.post(
        "/api/v1/events",
        json={
            "title": "Vide-Grenier Poster Validation",
            "start_date": (now + timedelta(days=5)).isoformat(),
            "end_date": (now + timedelta(days=6)).isoformat(),
            "price_per_meter": 4.0,
        },
    )
    event_id = create_res.json()["id"]

    # 1. Invalid MIME (PDF)
    files_pdf = {"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4 header"), "application/pdf")}
    res_pdf = client.post(f"/api/v1/events/{event_id}/poster", files=files_pdf)
    assert res_pdf.status_code == 415
    assert "PNG, JPEG, WebP" in res_pdf.json()["detail"]

    # 2. Empty file
    files_empty = {"file": ("empty.png", io.BytesIO(b""), "image/png")}
    res_empty = client.post(f"/api/v1/events/{event_id}/poster", files=files_empty)
    assert res_empty.status_code == 422

    # 3. Spoofed content
    files_fake = {"file": ("fake.png", io.BytesIO(b"Fake content not png"), "image/png")}
    res_fake = client.post(f"/api/v1/events/{event_id}/poster", files=files_fake)
    assert res_fake.status_code == 415
    assert "pas une image valide" in res_fake.json()["detail"]


def test_delete_poster(client: TestClient):
    """Test deleting an uploaded poster resets poster_image_url to null and deletes file from disk."""
    now = datetime.now(timezone.utc)
    create_res = client.post(
        "/api/v1/events",
        json={
            "title": "Vide-Grenier Delete Poster Test",
            "start_date": (now + timedelta(days=5)).isoformat(),
            "end_date": (now + timedelta(days=6)).isoformat(),
            "price_per_meter": 4.0,
        },
    )
    event_id = create_res.json()["id"]

    png_content = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x00\x00"
        b"\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    files = {"file": ("poster.png", io.BytesIO(png_content), "image/png")}
    up_res = client.post(f"/api/v1/events/{event_id}/poster", files=files)
    assert up_res.status_code == 200
    poster_url = up_res.json()["poster_image_url"]

    from app.core.config import settings
    disk_path = settings.upload_dir_path / "posters" / poster_url.removeprefix("/uploads/posters/")
    assert disk_path.is_file()

    # Delete poster
    del_res = client.delete(f"/api/v1/events/{event_id}/poster")
    assert del_res.status_code == 200
    assert del_res.json()["poster_image_url"] is None
    assert not disk_path.exists()

    # Verify event state via GET
    get_res = client.get(f"/api/v1/events/{event_id}")
    assert get_res.status_code == 200
    assert get_res.json()["poster_image_url"] is None


def test_poster_access_control(client: TestClient, db_session):
    """Test that non-owner cannot upload or delete poster, but owner can do both."""
    from app.models.user import User, UserRole
    from app.core.security import hash_password, create_access_token

    # Create owner and non-owner
    owner = User(
        email="owner_user@example.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.EVENT_ADMIN,
        is_active=True,
    )
    stranger = User(
        email="stranger_user@example.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.EVENT_ADMIN,
        is_active=True,
    )
    db_session.add_all([owner, stranger])
    db_session.commit()

    owner_token = create_access_token(data={"sub": str(owner.id), "role": str(owner.role), "email": owner.email})
    stranger_token = create_access_token(data={"sub": str(stranger.id), "role": str(stranger.role), "email": stranger.email})

    now = datetime.now(timezone.utc)
    create_res = client.post(
        "/api/v1/events",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "title": "Vide-Grenier Owner Protected",
            "start_date": (now + timedelta(days=5)).isoformat(),
            "end_date": (now + timedelta(days=6)).isoformat(),
            "price_per_meter": 4.0,
        },
    )
    event_id = create_res.json()["id"]

    png_content = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x00\x00"
        b"\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    files = {"file": ("poster.png", io.BytesIO(png_content), "image/png")}

    # Stranger cannot upload
    bad_upload = client.post(
        f"/api/v1/events/{event_id}/poster",
        headers={"Authorization": f"Bearer {stranger_token}"},
        files=files,
    )
    assert bad_upload.status_code == 403

    # Stranger cannot delete
    bad_delete = client.delete(
        f"/api/v1/events/{event_id}/poster",
        headers={"Authorization": f"Bearer {stranger_token}"},
    )
    assert bad_delete.status_code == 403

    # Owner can upload
    files_ok = {"file": ("poster.png", io.BytesIO(png_content), "image/png")}
    good_upload = client.post(
        f"/api/v1/events/{event_id}/poster",
        headers={"Authorization": f"Bearer {owner_token}"},
        files=files_ok,
    )
    assert good_upload.status_code == 200

    # Owner can delete
    good_delete = client.delete(
        f"/api/v1/events/{event_id}/poster",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert good_delete.status_code == 200
    assert good_delete.json()["poster_image_url"] is None


def test_poster_not_found(client: TestClient):
    """Test 404 for uploading or deleting poster on non-existent event."""
    random_id = str(uuid.uuid4())
    png_content = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x00\x00"
        b"\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    files = {"file": ("poster.png", io.BytesIO(png_content), "image/png")}
    res_up = client.post(f"/api/v1/events/{random_id}/poster", files=files)
    assert res_up.status_code == 404

    res_del = client.delete(f"/api/v1/events/{random_id}/poster")
    assert res_del.status_code == 404


def test_clear_optional_fields_via_patch(client: TestClient):
    """Test that setting optional fields to None in PATCH clears them."""
    now = datetime.now(timezone.utc)
    create_res = client.post(
        "/api/v1/events",
        json={
            "title": "Vide-Grenier Clear Fields",
            "description": "Initial description",
            "location_address": "123 Rue de Paris",
            "organizer_email": "contact@example.com",
            "rules_text": "Rules of conduct",
            "start_date": (now + timedelta(days=5)).isoformat(),
            "end_date": (now + timedelta(days=6)).isoformat(),
            "price_per_meter": 4.0,
        },
    )
    event_id = create_res.json()["id"]
    assert create_res.json()["description"] == "Initial description"
    assert create_res.json()["location_address"] == "123 Rue de Paris"

    patch_res = client.patch(
        f"/api/v1/events/{event_id}",
        json={
            "description": None,
            "location_address": None,
            "organizer_email": None,
            "rules_text": None,
        },
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["description"] is None
    assert data["location_address"] is None
    assert data["organizer_email"] is None
    assert data["rules_text"] is None


def test_delete_event_cleans_up_poster_file(client: TestClient):
    """Test that deleting an event also unlinks its poster file on disk."""
    now = datetime.now(timezone.utc)
    create_res = client.post(
        "/api/v1/events",
        json={
            "title": "Vide-Grenier Clean Poster Test",
            "start_date": (now + timedelta(days=5)).isoformat(),
            "end_date": (now + timedelta(days=6)).isoformat(),
            "price_per_meter": 4.0,
        },
    )
    event_id = create_res.json()["id"]

    png_content = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x00\x00"
        b"\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    files = {"file": ("poster.png", io.BytesIO(png_content), "image/png")}
    up_res = client.post(f"/api/v1/events/{event_id}/poster", files=files)
    assert up_res.status_code == 200
    poster_url = up_res.json()["poster_image_url"]

    # Verify file physically exists
    from app.core.config import settings
    rel_path = poster_url.removeprefix("/uploads/")
    disk_path = settings.upload_dir_path / rel_path
    assert disk_path.is_file()

    # Delete event as superadmin
    del_res = client.delete(f"/api/v1/events/{event_id}")
    assert del_res.status_code == 204

    # Verify file physically deleted
    assert not disk_path.exists()



