import uuid
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, create_access_token
from app.models.user import User, UserRole
from app.models.event import Event
from app.models.spot import Spot
from app.models.order import Order, BookingItem
from app.models.email_log import EmailLog


@pytest.fixture
def auth_context(db_session: Session):
    """Fixture providing a superadmin and an event_admin with valid Bearer tokens."""
    superadmin = User(
        email="superadmin_console@example.com",
        hashed_password=hash_password("SuperSecret123!"),
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )
    organizer = User(
        email="organizer_console@example.com",
        hashed_password=hash_password("OrganizerSecret123!"),
        role=UserRole.EVENT_ADMIN,
        is_active=True,
    )
    db_session.add_all([superadmin, organizer])
    db_session.commit()
    db_session.refresh(superadmin)
    db_session.refresh(organizer)

    token_super = create_access_token(
        data={"sub": str(superadmin.id), "role": str(superadmin.role), "email": superadmin.email}
    )
    token_org = create_access_token(
        data={"sub": str(organizer.id), "role": str(organizer.role), "email": organizer.email}
    )

    return {
        "superadmin": superadmin,
        "token_super": token_super,
        "headers_super": {"Authorization": f"Bearer {token_super}"},
        "organizer": organizer,
        "token_org": token_org,
        "headers_org": {"Authorization": f"Bearer {token_org}"},
    }


def test_list_admin_users_permissions(client: TestClient, auth_context: dict, db_session: Session):
    """Only super_admin can list all users; event_admin gets 403, unauthenticated gets 401."""
    # Create an event owned by organizer to verify non-zero events_count aggregation
    now = datetime.now(timezone.utc)
    ev = Event(
        title="Brocante Organisateur Test",
        slug="brocante-organisateur-test",
        owner_id=auth_context["organizer"].id,
        price_per_meter_cents=500,
        start_date=now + timedelta(days=10),
        end_date=now + timedelta(days=11),
        status="published",
    )
    db_session.add(ev)
    db_session.commit()

    # 1. Unauthenticated -> 401
    resp = client.get("/api/v1/admin/users", headers={"X-No-Auth": "1"})
    assert resp.status_code == 401

    # 2. Event admin -> 403
    resp = client.get("/api/v1/admin/users", headers=auth_context["headers_org"])
    assert resp.status_code == 403

    # 3. Super admin -> 200 OK with list of users
    resp = client.get("/api/v1/admin/users", headers=auth_context["headers_super"])
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    emails = [u["email"] for u in users]
    assert auth_context["superadmin"].email in emails
    assert auth_context["organizer"].email in emails

    # Check fields and events_count aggregation
    target = next(u for u in users if u["email"] == auth_context["organizer"].email)
    assert target["events_count"] == 1
    assert target["role"] == "event_admin"
    assert target["is_active"] is True


def test_create_admin_user(client: TestClient, auth_context: dict):
    """Super_admin can create new organizers; duplicate emails are rejected with 409."""
    # Forbidden for event_admin
    resp = client.post(
        "/api/v1/admin/users",
        json={"email": "new_org@example.com", "password": "Password123!", "role": "event_admin"},
        headers=auth_context["headers_org"],
    )
    assert resp.status_code == 403

    # Success for super_admin
    resp = client.post(
        "/api/v1/admin/users",
        json={"email": "new_org@example.com", "password": "Password123!", "role": "event_admin"},
        headers=auth_context["headers_super"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new_org@example.com"
    assert data["role"] == "event_admin"
    assert data["is_active"] is True
    assert data["events_count"] == 0

    # Verify newly created user can log in with credentials
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "new_org@example.com", "password": "Password123!"},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()

    # Duplicate email -> 409 Conflict
    resp_dup = client.post(
        "/api/v1/admin/users",
        json={"email": "new_org@example.com", "password": "AnotherPassword123!", "role": "event_admin"},
        headers=auth_context["headers_super"],
    )
    assert resp_dup.status_code == 409



def test_update_admin_user_and_self_lockout(client: TestClient, auth_context: dict):
    """Super_admin can toggle active status and change roles, but cannot lock self out."""
    org_id = str(auth_context["organizer"].id)
    super_id = str(auth_context["superadmin"].id)

    # Deactivate organizer -> 200 OK
    resp = client.patch(
        f"/api/v1/admin/users/{org_id}",
        json={"is_active": False},
        headers=auth_context["headers_super"],
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Organizer cannot log in once deactivated
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": auth_context["organizer"].email, "password": "OrganizerSecret123!"},
    )
    assert login_resp.status_code == 400
    assert "Inactive user" in login_resp.json()["detail"]

    # Reactivate organizer -> 200 OK
    resp_re = client.patch(
        f"/api/v1/admin/users/{org_id}",
        json={"is_active": True},
        headers=auth_context["headers_super"],
    )
    assert resp_re.status_code == 200
    assert resp_re.json()["is_active"] is True

    # Promote organizer to super_admin -> 200 OK
    resp_promo = client.patch(
        f"/api/v1/admin/users/{org_id}",
        json={"role": "super_admin"},
        headers=auth_context["headers_super"],
    )
    assert resp_promo.status_code == 200
    assert resp_promo.json()["role"] == "super_admin"

    # Demote organizer back to event_admin -> 200 OK
    resp_demo = client.patch(
        f"/api/v1/admin/users/{org_id}",
        json={"role": "event_admin"},
        headers=auth_context["headers_super"],
    )
    assert resp_demo.status_code == 200
    assert resp_demo.json()["role"] == "event_admin"

    # Attempt to deactivate self as super_admin -> 400 Bad Request
    resp_self_deact = client.patch(
        f"/api/v1/admin/users/{super_id}",
        json={"is_active": False},
        headers=auth_context["headers_super"],
    )
    assert resp_self_deact.status_code == 400

    # Attempt to downgrade self role -> 400 Bad Request
    resp_self_downgrade = client.patch(
        f"/api/v1/admin/users/{super_id}",
        json={"role": "event_admin"},
        headers=auth_context["headers_super"],
    )
    assert resp_self_downgrade.status_code == 400


def test_reset_admin_user_password(client: TestClient, auth_context: dict):
    """Super_admin can reset another user's password; the user can then log in with it."""
    org_id = str(auth_context["organizer"].id)

    # Event admin cannot reset passwords -> 403
    resp = client.post(
        f"/api/v1/admin/users/{org_id}/reset-password",
        json={"new_password": "BrandNewPassword123!"},
        headers=auth_context["headers_org"],
    )
    assert resp.status_code == 403

    # Super admin resets password -> 200 OK
    resp = client.post(
        f"/api/v1/admin/users/{org_id}/reset-password",
        json={"new_password": "BrandNewPassword123!"},
        headers=auth_context["headers_super"],
    )
    assert resp.status_code == 200
    assert "succès" in resp.json()["message"]

    # Old password fails
    resp_old = client.post(
        "/api/v1/auth/login",
        json={"email": auth_context["organizer"].email, "password": "OrganizerSecret123!"},
    )
    assert resp_old.status_code == 401

    # New password succeeds
    resp_new = client.post(
        "/api/v1/auth/login",
        json={"email": auth_context["organizer"].email, "password": "BrandNewPassword123!"},
    )
    assert resp_new.status_code == 200
    assert "access_token" in resp_new.json()


def test_delete_event_cascade_and_file_cleanup(client: TestClient, auth_context: dict, db_session: Session):
    """Super_admin can delete an event and all dependent rows and images are removed in cascade."""
    now = datetime.now(timezone.utc)

    # 1. Create an event owned by organizer
    event = Event(
        title="Event To Delete",
        slug="event-to-delete",
        start_date=now + timedelta(days=1),
        end_date=now + timedelta(days=1, hours=8),
        price_per_meter_cents=500,
        owner_id=auth_context["organizer"].id,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    # Create dummy background image file on disk
    bg_dir = settings.upload_dir_path / "backgrounds"
    bg_dir.mkdir(parents=True, exist_ok=True)
    dummy_filename = f"test_bg_{uuid.uuid4().hex}.png"
    dummy_file = bg_dir / dummy_filename
    dummy_file.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagecontent")
    assert dummy_file.exists()

    event.background_image_url = f"/uploads/backgrounds/{dummy_filename}"

    # 2. Add spots
    spot1 = Spot(
        event_id=event.id,
        label="DEL-01",
        linear_meters=2.0,
        price_cents=1000,
        geom="POLYGON((0 0, 2 0, 2 2, 0 2, 0 0))",
        status="reserved",
    )
    db_session.add(spot1)
    db_session.commit()
    db_session.refresh(spot1)

    # 3. Add order and booking items
    order = Order(
        event_id=event.id,
        order_number="ORD-DEL-001",
        first_name="Jean",
        last_name="Dupont",
        email="jean@example.com",
        phone="0600000000",
        total_price_cents=1000,
        status="confirmed",
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    item = BookingItem(
        order_id=order.id,
        spot_id=spot1.id,
        price_cents=1000,
    )
    db_session.add(item)

    # 4. Add email log
    log = EmailLog(
        event_id=event.id,
        order_id=order.id,
        recipient="jean@example.com",
        email_type="confirmation",
        subject="Confirmation",
        status="sent",
    )
    db_session.add(log)
    db_session.commit()

    event_id_str = str(event.id)
    spot_id = spot1.id
    order_id = order.id
    log_id = log.id

    # 5. Non-existent event returns 404
    resp_404 = client.delete("/api/v1/events/unknown-slug-xyz", headers=auth_context["headers_super"])
    assert resp_404.status_code == 404

    # 6. Event admin attempts to delete -> 403 Forbidden
    resp_org = client.delete(f"/api/v1/events/{event.slug}", headers=auth_context["headers_org"])
    assert resp_org.status_code == 403

    # 7. Super admin deletes by slug -> 204 No Content
    resp_super = client.delete(f"/api/v1/events/{event.slug}", headers=auth_context["headers_super"])
    assert resp_super.status_code == 204

    # 7. Verify file unlinked from disk
    assert not dummy_file.exists()

    # 8. Verify all DB entities deleted in cascade
    assert db_session.query(Event).filter(Event.id == event.id).first() is None
    assert db_session.query(Spot).filter(Spot.id == spot_id).first() is None
    assert db_session.query(Order).filter(Order.id == order_id).first() is None
    assert db_session.query(BookingItem).filter(BookingItem.id == item.id).first() is None
    assert db_session.query(EmailLog).filter(EmailLog.id == log_id).first() is None
