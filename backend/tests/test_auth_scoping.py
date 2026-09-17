import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.event import Event
from app.core.security import hash_password, create_access_token


@pytest.fixture
def test_users(db_session: Session):
    """Fixture providing two distinct event_admins and one super_admin."""
    admin1 = User(
        email="organizer1@example.com",
        hashed_password=hash_password("Password123!"),
        role=UserRole.EVENT_ADMIN,
        is_active=True,
    )
    admin2 = User(
        email="organizer2@example.com",
        hashed_password=hash_password("Password123!"),
        role=UserRole.EVENT_ADMIN,
        is_active=True,
    )
    superadmin = User(
        email="superadmin_test@example.com",
        hashed_password=hash_password("Password123!"),
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )
    db_session.add_all([admin1, admin2, superadmin])
    db_session.commit()
    db_session.refresh(admin1)
    db_session.refresh(admin2)
    db_session.refresh(superadmin)

    token1 = create_access_token(data={"sub": str(admin1.id), "role": str(admin1.role), "email": admin1.email})
    token2 = create_access_token(data={"sub": str(admin2.id), "role": str(admin2.role), "email": admin2.email})
    token_super = create_access_token(data={"sub": str(superadmin.id), "role": str(superadmin.role), "email": superadmin.email})

    return {
        "admin1": admin1,
        "token1": token1,
        "headers1": {"Authorization": f"Bearer {token1}"},
        "admin2": admin2,
        "token2": token2,
        "headers2": {"Authorization": f"Bearer {token2}"},
        "superadmin": superadmin,
        "token_super": token_super,
        "headers_super": {"Authorization": f"Bearer {token_super}"},
    }


def test_unauthenticated_requests_blocked(client: TestClient):
    """Admin endpoints should return 401 Unauthorized when no valid token is provided."""
    no_auth_headers = {"X-No-Auth": "1"}

    resp = client.get("/api/v1/events", headers=no_auth_headers)
    assert resp.status_code == 401

    resp = client.post("/api/v1/events", json={"title": "Test"}, headers=no_auth_headers)
    assert resp.status_code == 401

    dummy_id = uuid.uuid4()
    resp = client.get(f"/api/v1/events/{dummy_id}", headers=no_auth_headers)
    assert resp.status_code == 401

    resp = client.get(f"/api/v1/events/{dummy_id}/spots", headers=no_auth_headers)
    assert resp.status_code == 401

    resp = client.get(f"/api/v1/events/{dummy_id}/orders", headers=no_auth_headers)
    assert resp.status_code == 401

    resp = client.get(f"/api/v1/events/{dummy_id}/reminders/status", headers=no_auth_headers)
    assert resp.status_code == 401


def test_create_event_auto_assigns_owner_id(client: TestClient, test_users: dict):
    """When an event_admin creates an event, its owner_id is set to their user ID."""
    now = datetime.now(timezone.utc)
    payload = {
        "title": "Brocante Organizer 1",
        "start_date": (now + timedelta(days=5)).isoformat(),
        "end_date": (now + timedelta(days=5, hours=8)).isoformat(),
        "price_per_meter": 5.0,
    }

    resp = client.post("/api/v1/events", json=payload, headers=test_users["headers1"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["owner_id"] == str(test_users["admin1"].id)


def test_events_list_scoping_between_organizers(client: TestClient, test_users: dict):
    """An event_admin only sees their own events; super_admin sees all events."""
    now = datetime.now(timezone.utc)

    # Admin 1 creates Event 1
    resp1 = client.post(
        "/api/v1/events",
        json={
            "title": "Event by Admin 1",
            "start_date": (now + timedelta(days=10)).isoformat(),
            "end_date": (now + timedelta(days=10, hours=8)).isoformat(),
            "price_per_meter": 4.0,
        },
        headers=test_users["headers1"],
    )
    assert resp1.status_code == 201
    event1_id = resp1.json()["id"]

    # Admin 2 creates Event 2
    resp2 = client.post(
        "/api/v1/events",
        json={
            "title": "Event by Admin 2",
            "start_date": (now + timedelta(days=12)).isoformat(),
            "end_date": (now + timedelta(days=12, hours=8)).isoformat(),
            "price_per_meter": 6.0,
        },
        headers=test_users["headers2"],
    )
    assert resp2.status_code == 201
    event2_id = resp2.json()["id"]

    # Admin 1 lists events: only sees Event 1
    list1 = client.get("/api/v1/events", headers=test_users["headers1"]).json()["items"]
    ids1 = [e["id"] for e in list1]
    assert event1_id in ids1
    assert event2_id not in ids1

    # Admin 2 lists events: only sees Event 2
    list2 = client.get("/api/v1/events", headers=test_users["headers2"]).json()["items"]
    ids2 = [e["id"] for e in list2]
    assert event2_id in ids2
    assert event1_id not in ids2

    # SuperAdmin lists events: sees BOTH
    list_super = client.get("/api/v1/events", headers=test_users["headers_super"]).json()["items"]
    ids_super = [e["id"] for e in list_super]
    assert event1_id in ids_super
    assert event2_id in ids_super


def test_cross_organizer_access_forbidden(client: TestClient, test_users: dict):
    """An event_admin cannot access or mutate another organizer's event (403 Forbidden)."""
    now = datetime.now(timezone.utc)

    # Admin 1 creates Event 1
    resp1 = client.post(
        "/api/v1/events",
        json={
            "title": "Private Event 1",
            "start_date": (now + timedelta(days=20)).isoformat(),
            "end_date": (now + timedelta(days=20, hours=8)).isoformat(),
            "price_per_meter": 5.0,
        },
        headers=test_users["headers1"],
    )
    assert resp1.status_code == 201
    event1_id = resp1.json()["id"]

    # Admin 2 attempts GET on Admin 1's event -> 403 Forbidden
    resp = client.get(f"/api/v1/events/{event1_id}", headers=test_users["headers2"])
    assert resp.status_code == 403

    # Admin 2 attempts PATCH on Admin 1's event -> 403 Forbidden
    resp = client.patch(
        f"/api/v1/events/{event1_id}",
        json={"title": "Hacked Title"},
        headers=test_users["headers2"],
    )
    assert resp.status_code == 403

    # Admin 2 attempts GET spots on Admin 1's event -> 403 Forbidden
    resp = client.get(f"/api/v1/events/{event1_id}/spots", headers=test_users["headers2"])
    assert resp.status_code == 403

    # Admin 2 attempts GET orders on Admin 1's event -> 403 Forbidden
    resp = client.get(f"/api/v1/events/{event1_id}/orders", headers=test_users["headers2"])
    assert resp.status_code == 403

    # Admin 2 attempts reminders status on Admin 1's event -> 403 Forbidden
    resp = client.get(f"/api/v1/events/{event1_id}/reminders/status", headers=test_users["headers2"])
    assert resp.status_code == 403

    # Admin 2 attempts broadcast preview on Admin 1's event -> 403 Forbidden
    resp = client.post(
        f"/api/v1/events/{event1_id}/broadcast/preview",
        json={"subject": "Hello", "body": "World"},
        headers=test_users["headers2"],
    )
    assert resp.status_code == 403


def test_super_admin_can_manage_any_event(client: TestClient, test_users: dict):
    """A super_admin can read and modify events created by any organizer."""
    now = datetime.now(timezone.utc)

    # Admin 1 creates Event 1
    resp1 = client.post(
        "/api/v1/events",
        json={
            "title": "Supervised Event",
            "start_date": (now + timedelta(days=30)).isoformat(),
            "end_date": (now + timedelta(days=30, hours=8)).isoformat(),
            "price_per_meter": 7.0,
        },
        headers=test_users["headers1"],
    )
    assert resp1.status_code == 201
    event1_id = resp1.json()["id"]

    # SuperAdmin reads Event 1 -> 200 OK
    resp = client.get(f"/api/v1/events/{event1_id}", headers=test_users["headers_super"])
    assert resp.status_code == 200
    assert resp.json()["title"] == "Supervised Event"

    # SuperAdmin updates Event 1 -> 200 OK
    resp = client.patch(
        f"/api/v1/events/{event1_id}",
        json={"description": "Updated by SuperAdmin"},
        headers=test_users["headers_super"],
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated by SuperAdmin"
