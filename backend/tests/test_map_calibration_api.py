import io
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient


def create_sample_event(client: TestClient, title: str = "Test Calibration Event") -> dict:
    now = datetime.now(timezone.utc)
    payload = {
        "title": title,
        "start_date": (now + timedelta(days=5)).isoformat(),
        "end_date": (now + timedelta(days=5, hours=8)).isoformat(),
        "price_per_meter": 4.50,
        "location_address": "Place de la République, Paris",
    }
    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_patch_geographic_calibration(client: TestClient):
    """Test outdoor map viewpoint calibration via PATCH endpoint."""
    event = create_sample_event(client, "Outdoor Calibration Event")
    event_id = event["id"]

    patch_payload = {
        "map_type": "geographic",
        "center_latitude": 48.8675,
        "center_longitude": 2.3638,
        "default_zoom": 17,
    }

    response = client.patch(f"/api/v1/events/{event_id}", json=patch_payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["map_type"] == "geographic"
    assert data["center_latitude"] == 48.8675
    assert data["center_longitude"] == 2.3638
    assert data["default_zoom"] == 17

    # Verify persistence via GET
    get_res = client.get(f"/api/v1/events/{event_id}")
    assert get_res.status_code == 200
    assert get_res.json()["center_latitude"] == 48.8675
    assert get_res.json()["center_longitude"] == 2.3638
    assert get_res.json()["default_zoom"] == 17


def test_upload_valid_indoor_png(client: TestClient):
    """Test valid PNG floorplan upload and static file serving."""
    event = create_sample_event(client, "Indoor Gym Event")
    event_id = event["id"]

    # Minimal PNG bytes
    png_content = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x00\x00"
        b"\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    files = {
        "file": ("gym_floorplan.png", io.BytesIO(png_content), "image/png")
    }

    response = client.post(f"/api/v1/events/{event_id}/background-image", files=files)
    assert response.status_code == 201, response.text
    data = response.json()

    assert data["map_type"] == "planar"
    assert data["background_image_url"] is not None
    assert data["background_image_url"].startswith("/uploads/backgrounds/")
    assert data["background_image_url"].endswith(".png")

    # Verify static file serving via GET
    file_res = client.get(data["background_image_url"])
    assert file_res.status_code == 200
    assert file_res.content == png_content


def test_upload_valid_jpeg_and_webp(client: TestClient):
    """Test valid JPEG and WebP upload formats."""
    event = create_sample_event(client, "Indoor Multi-format Event")
    event_id = event["id"]

    # Upload JPEG
    jpg_content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb"
    files_jpg = {
        "file": ("hall.jpg", io.BytesIO(jpg_content), "image/jpeg")
    }
    res_jpg = client.post(f"/api/v1/events/{event_id}/background-image", files=files_jpg)
    assert res_jpg.status_code == 201
    assert res_jpg.json()["background_image_url"].endswith(".jpg")

    # Upload WebP by slug
    webp_content = b"RIFF\x14\x00\x00\x00WEBPVP8 \x08\x00\x00\x00"
    files_webp = {
        "file": ("hall.webp", io.BytesIO(webp_content), "image/webp")
    }
    res_webp = client.post(f"/api/v1/events/{event['slug']}/background-image", files=files_webp)
    assert res_webp.status_code == 201
    assert res_webp.json()["background_image_url"].endswith(".webp")


def test_upload_invalid_mime_type(client: TestClient):
    """Test rejection of non-image MIME types with 415 Unsupported Media Type."""
    event = create_sample_event(client, "MIME Validation Event")
    event_id = event["id"]

    pdf_content = b"%PDF-1.4 header content"
    files = {
        "file": ("plan.pdf", io.BytesIO(pdf_content), "application/pdf")
    }

    response = client.post(f"/api/v1/events/{event_id}/background-image", files=files)
    assert response.status_code == 415
    data = response.json()
    assert "detail" in data
    assert "PNG, JPEG, WebP" in data["detail"]


def test_upload_empty_file_rejected(client: TestClient):
    """Test rejection of 0-byte uploaded file."""
    event = create_sample_event(client, "Empty File Event")
    event_id = event["id"]

    files = {
        "file": ("empty.png", io.BytesIO(b""), "image/png")
    }
    response = client.post(f"/api/v1/events/{event_id}/background-image", files=files)
    assert response.status_code == 422


def test_upload_exceeding_10mb_limit(client: TestClient):
    """Test rejection of image exceeding 10 MB limit with 413 Content Too Large."""
    event = create_sample_event(client, "Oversized Image Event")
    event_id = event["id"]

    # 10.5 MB payload
    oversized = b"A" * (10 * 1024 * 1024 + 500 * 1024)
    files = {
        "file": ("huge_map.png", io.BytesIO(oversized), "image/png")
    }

    response = client.post(f"/api/v1/events/{event_id}/background-image", files=files)
    assert response.status_code == 413
    data = response.json()
    assert "detail" in data
    assert "10 Mo" in data["detail"]


def test_upload_nonexistent_event(client: TestClient):
    """Test 404 when uploading for non-existent event ID."""
    random_id = uuid.uuid4()
    files = {
        "file": ("plan.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")
    }
    response = client.post(f"/api/v1/events/{random_id}/background-image", files=files)
    assert response.status_code == 404


def test_upload_spoofed_mime_type_fails_magic_bytes(client: TestClient):
    """Test that a file with image/png content type but invalid magic bytes is rejected."""
    event = create_sample_event(client, "Spoofed Image Event")
    event_id = event["id"]

    spoofed_content = b"echo 'this is not a real image binary file'"
    files = {
        "file": ("fake.png", io.BytesIO(spoofed_content), "image/png")
    }
    response = client.post(f"/api/v1/events/{event_id}/background-image", files=files)
    assert response.status_code == 415
    assert "pas une image valide" in response.json()["detail"]


