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


def test_duplicate_event_clean_slate_and_spots(client: TestClient, db_session):
    """
    Test duplicating an event with spots, orders, poster, and background image:
    - Spots are duplicated with identical geometries, but status is reset to 'available'
    - No orders or bookings are copied
    - Status is reset to 'draft' even if source event was 'published'
    - New unique slug is generated
    - Media files are cloned independently
    - Shifted dates preserve event duration
    """
    from app.models.spot import Spot
    from app.models.order import Order, BookingItem
    from app.models.event import Event

    now = datetime.now(timezone.utc)
    source_start = now + timedelta(days=30)
    source_end = now + timedelta(days=31)

    create_res = client.post(
        "/api/v1/events",
        json={
            "title": "Vide-Grenier Annuel 2026",
            "description": "Superbe vide-grenier de quartier",
            "location_address": "Place de la Mairie",
            "organizer_email": "orga@example.com",
            "start_date": source_start.isoformat(),
            "end_date": source_end.isoformat(),
            "price_per_meter": 5.0,
        },
    )
    assert create_res.status_code == 201
    source_id = uuid.UUID(create_res.json()["id"])

    # Mark source event as published to verify duplicate resets to draft
    source_event = db_session.query(Event).filter(Event.id == source_id).first()
    source_event.status = "published"
    db_session.commit()

    # Upload poster to source event
    png_content = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x00\x00"
        b"\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    files = {"file": ("source_poster.png", io.BytesIO(png_content), "image/png")}
    poster_res = client.post(f"/api/v1/events/{source_id}/poster", files=files)
    assert poster_res.status_code == 200
    source_poster_url = poster_res.json()["poster_image_url"]

    # Upload background image to source event
    bg_files = {"file": ("source_bg.png", io.BytesIO(png_content), "image/png")}
    bg_res = client.post(f"/api/v1/events/{source_id}/background-image", files=bg_files)
    assert bg_res.status_code == 201
    source_bg_url = bg_res.json()["background_image_url"]

    # Create 2 spots via API in source event: 1 available, 1 reserved with an order
    coords1 = [[[-2.025, 48.650], [-2.020, 48.650], [-2.020, 48.652], [-2.025, 48.652], [-2.025, 48.650]]]
    coords2 = [[[-2.020, 48.650], [-2.015, 48.650], [-2.015, 48.652], [-2.020, 48.652], [-2.020, 48.650]]]
    sp1_res = client.post(
        f"/api/v1/events/{source_id}/spots",
        json={"label": "A-01", "linear_meters": 3.0, "geometry": {"type": "Polygon", "coordinates": coords1}},
    )
    assert sp1_res.status_code == 201
    sp2_res = client.post(
        f"/api/v1/events/{source_id}/spots",
        json={"label": "A-02", "linear_meters": 3.0, "geometry": {"type": "Polygon", "coordinates": coords2}},
    )
    assert sp2_res.status_code == 201
    spot2_id = uuid.UUID(sp2_res.json()["id"])

    # Mark spot 2 as reserved with an order in source
    spot2 = db_session.query(Spot).filter(Spot.id == spot2_id).first()
    spot2.status = "reserved"
    spot2.locked_until = now + timedelta(hours=1)
    spot2.locked_by_token = "token123"

    order = Order(
        id=uuid.uuid4(),
        event_id=source_id,
        order_number="CMD-2026-001",
        status="confirmed",
        total_price_cents=1500,
        first_name="Jean",
        last_name="Dupont",
        phone="0612345678",
        email="dupont@example.com",
    )
    db_session.add(order)
    db_session.flush()

    b_item = BookingItem(
        id=uuid.uuid4(),
        order_id=order.id,
        spot_id=spot2_id,
        price_cents=1500,
    )
    db_session.add(b_item)
    db_session.commit()

    # Now duplicate the event with default options (empty body)
    dup_res = client.post(f"/api/v1/events/{source_id}/duplicate")
    assert dup_res.status_code == 201, dup_res.text
    dup_data = dup_res.json()
    new_id = uuid.UUID(dup_data["id"])

    assert new_id != source_id
    assert dup_data["title"] == "Vide-Grenier Annuel 2026 - Copie"
    assert dup_data["status"] == "draft"  # Strictly draft even if source was published
    assert dup_data["slug"] != create_res.json()["slug"]
    assert dup_data["location_address"] == "Place de la Mairie"
    assert dup_data["organizer_email"] == "orga@example.com"
    assert dup_data["price_per_meter"] == 5.0

    # Verify shifted dates (+365 days preserving duration)
    def parse_ts(val):
        if isinstance(val, str):
            val = datetime.fromisoformat(val.replace("Z", "+00:00"))
        if val.tzinfo is None:
            val = val.replace(tzinfo=timezone.utc)
        return val.timestamp()

    expected_start = source_start + timedelta(days=365)
    expected_end = source_end + timedelta(days=365)
    assert abs(parse_ts(dup_data["start_date"]) - parse_ts(expected_start)) < 5
    assert abs(parse_ts(dup_data["end_date"]) - parse_ts(expected_end)) < 5

    # Verify poster independent clone
    new_poster_url = dup_data["poster_image_url"]
    assert new_poster_url is not None
    assert new_poster_url != source_poster_url
    assert new_poster_url.startswith("/uploads/posters/")

    from app.core.config import settings
    source_poster_disk = settings.upload_dir_path / "posters" / source_poster_url.removeprefix("/uploads/posters/")
    new_poster_disk = settings.upload_dir_path / "posters" / new_poster_url.removeprefix("/uploads/posters/")
    assert source_poster_disk.is_file()
    assert new_poster_disk.is_file()

    # Verify background image independent clone
    new_bg_url = dup_data["background_image_url"]
    assert new_bg_url is not None
    assert new_bg_url != source_bg_url
    assert new_bg_url.startswith("/uploads/backgrounds/")
    source_bg_disk = settings.upload_dir_path / "backgrounds" / source_bg_url.removeprefix("/uploads/backgrounds/")
    new_bg_disk = settings.upload_dir_path / "backgrounds" / new_bg_url.removeprefix("/uploads/backgrounds/")
    assert source_bg_disk.is_file()
    assert new_bg_disk.is_file()

    # Verify spots were cloned with clean slate and identical geometries
    cloned_spots = db_session.query(Spot).filter(Spot.event_id == new_id).order_by(Spot.label).all()
    assert len(cloned_spots) == 2

    # Spot 1
    assert cloned_spots[0].label == "A-01"
    assert cloned_spots[0].linear_meters == 3.0
    assert cloned_spots[0].price_cents == 1500
    assert cloned_spots[0].status == "available"

    # Spot 2 (which was reserved in source!) must be available with no lock
    assert cloned_spots[1].label == "A-02"
    assert cloned_spots[1].linear_meters == 3.0
    assert cloned_spots[1].price_cents == 1500
    assert cloned_spots[1].status == "available"
    assert cloned_spots[1].locked_until is None
    assert cloned_spots[1].locked_by_token is None

    # Verify geometry via spots GeoJSON endpoint
    spots_res = client.get(f"/api/v1/events/{new_id}/spots")
    assert spots_res.status_code == 200
    features = sorted(spots_res.json()["features"], key=lambda f: f["properties"]["label"])
    assert len(features) == 2
    assert features[0]["geometry"]["coordinates"] == coords1
    assert features[1]["geometry"]["coordinates"] == coords2

    # Verify zero orders and bookings for the new event
    order_count = db_session.query(Order).filter(Order.event_id == new_id).count()
    assert order_count == 0


def test_duplicate_event_custom_title_and_dates(client: TestClient):
    """Test duplicating an event with custom title and start/end dates, by slug, and end_date alone."""
    now = datetime.now(timezone.utc)
    create_res = client.post(
        "/api/v1/events",
        json={
            "title": "Vide-Grenier 2026",
            "start_date": (now + timedelta(days=10)).isoformat(),
            "end_date": (now + timedelta(days=11)).isoformat(),
            "price_per_meter": 4.5,
        },
    )
    source_id = create_res.json()["id"]
    source_slug = create_res.json()["slug"]

    custom_start = now + timedelta(days=360)
    custom_end = now + timedelta(days=362)

    def parse_ts(val):
        if isinstance(val, str):
            val = datetime.fromisoformat(val.replace("Z", "+00:00"))
        if val.tzinfo is None:
            val = val.replace(tzinfo=timezone.utc)
        return val.timestamp()

    # 1. Duplicate using slug instead of UUID
    dup_res = client.post(
        f"/api/v1/events/{source_slug}/duplicate",
        json={
            "title": "Vide-Grenier Édition 2027",
            "start_date": custom_start.isoformat(),
            "end_date": custom_end.isoformat(),
        },
    )
    assert dup_res.status_code == 201
    dup_data = dup_res.json()
    assert dup_data["title"] == "Vide-Grenier Édition 2027"
    assert dup_data["status"] == "draft"

    assert abs(parse_ts(dup_data["start_date"]) - parse_ts(custom_start)) < 5
    assert abs(parse_ts(dup_data["end_date"]) - parse_ts(custom_end)) < 5

    # 2. Test providing end_date alone (start_date shifted preserving 1 day duration)
    end_alone = now + timedelta(days=400)
    dup_res2 = client.post(
        f"/api/v1/events/{source_id}/duplicate",
        json={
            "title": "Vide-Grenier 2027 Bis",
            "end_date": end_alone.isoformat(),
        },
    )
    assert dup_res2.status_code == 201
    dup_data2 = dup_res2.json()
    assert abs(parse_ts(dup_data2["end_date"]) - parse_ts(end_alone)) < 5
    diff = parse_ts(dup_data2["end_date"]) - parse_ts(dup_data2["start_date"])
    assert abs(diff - 86400) < 5


def test_duplicate_event_by_superadmin(client: TestClient, db_session):
    """Test that a super-admin can duplicate an event owned by another organizer."""
    from app.models.user import User, UserRole
    from app.core.security import hash_password, create_access_token

    admin = User(
        email="super_dup@example.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )
    organizer = User(
        email="orga_dup@example.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.EVENT_ADMIN,
        is_active=True,
    )
    db_session.add_all([admin, organizer])
    db_session.commit()

    admin_token = create_access_token(data={"sub": str(admin.id), "role": str(admin.role), "email": admin.email})
    organizer_token = create_access_token(data={"sub": str(organizer.id), "role": str(organizer.role), "email": organizer.email})

    now = datetime.now(timezone.utc)
    create_res = client.post(
        "/api/v1/events",
        headers={"Authorization": f"Bearer {organizer_token}"},
        json={
            "title": "Organizer Event",
            "start_date": (now + timedelta(days=10)).isoformat(),
            "end_date": (now + timedelta(days=11)).isoformat(),
            "price_per_meter": 5.0,
        },
    )
    event_id = create_res.json()["id"]

    # Super-admin duplicates organizer's event
    dup_res = client.post(
        f"/api/v1/events/{event_id}/duplicate",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "Organizer Event Duplicated By SuperAdmin"},
    )
    assert dup_res.status_code == 201
    assert dup_res.json()["title"] == "Organizer Event Duplicated By SuperAdmin"


def test_duplicate_event_zero_spots_and_long_title(client: TestClient):
    """Test duplicating an event with 0 spots and title length near 255 characters."""
    now = datetime.now(timezone.utc)
    long_title = "A" * 250
    create_res = client.post(
        "/api/v1/events",
        json={
            "title": long_title,
            "start_date": (now + timedelta(days=10)).isoformat(),
            "end_date": (now + timedelta(days=11)).isoformat(),
            "price_per_meter": 5.0,
        },
    )
    assert create_res.status_code == 201
    event_id = create_res.json()["id"]

    # Default duplication appends ' - Copie' without crashing 255 length constraint
    dup_res = client.post(f"/api/v1/events/{event_id}/duplicate")
    assert dup_res.status_code == 201
    dup_data = dup_res.json()
    assert len(dup_data["title"]) <= 255
    assert dup_data["title"].endswith(" - Copie")



def test_duplicate_event_validation_and_access_control(client: TestClient, db_session):
    """Test invalid date ranges, non-existent events, and access control."""
    from app.models.user import User, UserRole
    from app.core.security import hash_password, create_access_token

    owner = User(
        email="owner_dup@example.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.EVENT_ADMIN,
        is_active=True,
    )
    stranger = User(
        email="stranger_dup@example.com",
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
            "title": "Protected Event For Duplication",
            "start_date": (now + timedelta(days=10)).isoformat(),
            "end_date": (now + timedelta(days=11)).isoformat(),
            "price_per_meter": 4.0,
        },
    )
    event_id = create_res.json()["id"]

    # 1. Stranger cannot duplicate
    bad_dup = client.post(
        f"/api/v1/events/{event_id}/duplicate",
        headers={"Authorization": f"Bearer {stranger_token}"},
    )
    assert bad_dup.status_code == 403

    # 2. Invalid date range (end_date < start_date)
    inv_dates = client.post(
        f"/api/v1/events/{event_id}/duplicate",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "start_date": (now + timedelta(days=20)).isoformat(),
            "end_date": (now + timedelta(days=15)).isoformat(),
        },
    )
    assert inv_dates.status_code == 422

    # 3. Non-existent event returns 404
    non_existent = client.post(
        f"/api/v1/events/{uuid.uuid4()}/duplicate",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert non_existent.status_code == 404


def test_wms_create_with_wms_url(client: TestClient):
    """Test creating an event with wms_url and wms_layer persists both fields."""
    now = datetime.now(timezone.utc)
    payload = {
        "title": "Vide-Grenier WMS IGN",
        "start_date": (now + timedelta(days=10)).isoformat(),
        "end_date": (now + timedelta(days=10, hours=8)).isoformat(),
        "price_per_meter": 4.0,
        "map_type": "geographic",
        "wms_url": "https://wxs.ign.fr/decouverte/geoportail/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image%2Fjpeg",
        "wms_layer": "ORTHOIMAGERY.ORTHOPHOTOS",
    }
    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["wms_url"] == payload["wms_url"]
    assert data["wms_layer"] == payload["wms_layer"]


def test_wms_patch_update_layer(client: TestClient):
    """Test updating wms_url and wms_layer via PATCH persists new values."""
    now = datetime.now(timezone.utc)
    create_resp = client.post(
        "/api/v1/events",
        json={
            "title": "Vide-Grenier WMS Patch",
            "start_date": (now + timedelta(days=5)).isoformat(),
            "end_date": (now + timedelta(days=5, hours=8)).isoformat(),
            "price_per_meter": 3.0,
        },
    )
    assert create_resp.status_code == 201
    event_id = create_resp.json()["id"]

    # Patch with IGN Cadastre layer
    cadastre_url = (
        "https://wxs.ign.fr/decouverte/geoportail/wmts?SERVICE=WMTS&REQUEST=GetTile"
        "&VERSION=1.0.0&LAYER=CADASTRALPARCELS.PARCELLAIRE_EXPRESS&STYLE=normal"
        "&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image%2Fpng"
    )
    patch_resp = client.patch(
        f"/api/v1/events/{event_id}",
        json={"wms_url": cadastre_url, "wms_layer": "CADASTRALPARCELS.PARCELLAIRE_EXPRESS"},
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["wms_url"] == cadastre_url
    assert updated["wms_layer"] == "CADASTRALPARCELS.PARCELLAIRE_EXPRESS"


def test_wms_read_persisted_layer(client: TestClient):
    """Test that wms_url is returned on GET after being set via PATCH."""
    now = datetime.now(timezone.utc)
    create_resp = client.post(
        "/api/v1/events",
        json={
            "title": "Vide-Grenier WMS Read",
            "start_date": (now + timedelta(days=5)).isoformat(),
            "end_date": (now + timedelta(days=5, hours=8)).isoformat(),
            "price_per_meter": 3.0,
        },
    )
    assert create_resp.status_code == 201
    event_id = create_resp.json()["id"]

    wms_url = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    client.patch(
        f"/api/v1/events/{event_id}",
        json={"wms_url": wms_url, "wms_layer": "OSM"},
    )

    get_resp = client.get(f"/api/v1/events/{event_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["wms_url"] == wms_url
    assert data["wms_layer"] == "OSM"


def test_wms_reset_to_null(client: TestClient):
    """Test that wms_url can be reset to null via PATCH (default OSM applies)."""
    now = datetime.now(timezone.utc)
    create_resp = client.post(
        "/api/v1/events",
        json={
            "title": "Vide-Grenier WMS Reset",
            "start_date": (now + timedelta(days=5)).isoformat(),
            "end_date": (now + timedelta(days=5, hours=8)).isoformat(),
            "price_per_meter": 3.0,
            "wms_url": "https://wxs.ign.fr/decouverte/geoportail/wmts?SERVICE=WMTS&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2",
            "wms_layer": "GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2",
        },
    )
    assert create_resp.status_code == 201
    event_id = create_resp.json()["id"]
    assert create_resp.json()["wms_url"] is not None

    # Reset to null
    patch_resp = client.patch(
        f"/api/v1/events/{event_id}",
        json={"wms_url": None, "wms_layer": None},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["wms_url"] is None
    assert patch_resp.json()["wms_layer"] is None

    # Confirm via GET
    get_resp = client.get(f"/api/v1/events/{event_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["wms_url"] is None
    assert get_resp.json()["wms_layer"] is None


def test_wms_null_by_default(client: TestClient):
    """Test that wms_url and wms_layer are null by default (no regression for existing events)."""
    now = datetime.now(timezone.utc)
    create_resp = client.post(
        "/api/v1/events",
        json={
            "title": "Vide-Grenier WMS Default Null",
            "start_date": (now + timedelta(days=5)).isoformat(),
            "end_date": (now + timedelta(days=5, hours=8)).isoformat(),
            "price_per_meter": 3.0,
        },
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["wms_url"] is None
    assert data["wms_layer"] is None


def test_duplicate_event_preserves_wms_layers(client: TestClient):
    """Test that duplicating an event preserves wms_url and wms_layer."""
    now = datetime.now(timezone.utc)
    wms_url = "https://wxs.ign.fr/decouverte/geoportail/wmts?SERVICE=WMTS&LAYER=CADASTRALPARCELS.PARCELLAIRE_EXPRESS"
    wms_layer = "CADASTRALPARCELS.PARCELLAIRE_EXPRESS"

    create_res = client.post(
        "/api/v1/events",
        json={
            "title": "Vide-Grenier WMS Original",
            "start_date": (now + timedelta(days=10)).isoformat(),
            "end_date": (now + timedelta(days=10, hours=8)).isoformat(),
            "price_per_meter": 4.0,
            "wms_url": wms_url,
            "wms_layer": wms_layer,
        },
    )
    assert create_res.status_code == 201
    source_id = create_res.json()["id"]

    dup_res = client.post(
        f"/api/v1/events/{source_id}/duplicate",
        json={"title": "Vide-Grenier WMS Clone"},
    )
    assert dup_res.status_code == 201
    data = dup_res.json()
    assert data["wms_url"] == wms_url
    assert data["wms_layer"] == wms_layer






