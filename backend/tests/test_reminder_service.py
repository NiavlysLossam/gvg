import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.event import Event
from app.models.spot import Spot
from app.models.order import Order, BookingItem, generate_order_number, generate_access_token
from app.models.email_log import EmailLog
from app.services import email_service, reminder_service


@pytest.fixture(autouse=True)
def bind_email_service_session(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """
    Ensure email_service background calls and helper functions share the test transaction
    without closing the fixture db_session prematurely.
    """
    monkeypatch.setattr(
        "app.services.email_service.get_session",
        lambda db=None: (db or db_session, False),
    )


SAMPLE_POLY_COORDS = [
    [
        [-1.68, 48.11],
        [-1.67, 48.11],
        [-1.67, 48.12],
        [-1.68, 48.12],
        [-1.68, 48.11],
    ]
]


def create_reminder_test_event(
    client: TestClient,
    title: str = "Brocante Rappels",
    days_in_future: float = 7.0,
) -> dict:
    start_dt = datetime.now(timezone.utc) + timedelta(days=days_in_future)
    end_dt = start_dt + timedelta(hours=10)
    payload = {
        "title": title,
        "description": "Vide-grenier pour tester les rappels programmés",
        "price_per_meter": 5.0,
        "map_type": "geographic",
        "start_date": start_dt.isoformat(),
        "end_date": end_dt.isoformat(),
        "setup_start_time": "06:00",
        "setup_end_time": "08:00",
        "public_start_time": "08:00",
        "public_end_time": "18:00",
        "location_address": "Place de la Mairie, 35400 Saint-Malo",
        "organizer_email": "contact@saint-malo-brocante.fr",
        "status": "published",
    }
    res = client.post("/api/v1/events", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def create_test_spot(client: TestClient, event_id: str, label: str = "R-01") -> dict:
    payload = {
        "label": label,
        "linear_meters": 3.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": SAMPLE_POLY_COORDS,
        },
    }
    res = client.post(f"/api/v1/events/{event_id}/spots", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


# ==============================================================================
# 1. TEMPLATE TESTS
# ==============================================================================

def test_render_reminder_templates():
    """Verify reminder_j7 and reminder_j2 templates compile and render cleanly."""
    ctx = {
        "event_title": "Grand Vide-Grenier de la Côte",
        "event_date": "20/09/2026",
        "event_location": "Esplanade du Port, Cancale",
        "organizer_email": "orga@cancale-fetes.fr",
        "first_name": "Monique",
        "last_name": "Dubois",
        "order_number": "GVG-2026-REM01",
        "spot_labels": ["A-01", "A-02"],
        "total_linear_meters": "6.0",
        "setup_hours": "06:00 - 08:00",
        "public_hours": "08:00 - 18:00",
        "setup_start_time": "06:00",
        "setup_end_time": "08:00",
        "confirmation_url": "https://gvg.local/e/cancale/confirmation/123?token=abc",
    }

    for tmpl in ["reminder_j7", "reminder_j2"]:
        html, txt = email_service.render_template(tmpl, ctx)
        assert len(html) > 50
        assert len(txt) > 20
        assert "Monique" in html
        assert "Monique" in txt
        assert "GVG-2026-REM01" in html
        assert "A-01" in html
        assert "{{" not in html, f"Unrendered placeholder in {tmpl}.html"
        assert "{{" not in txt, f"Unrendered placeholder in {tmpl}.txt"

        # Check regulatory notice
        assert "L310-2" in html or "pièce d'identité" in html.lower()
        assert "L310-2" in txt or "pièce d'identité" in txt.lower()


# ==============================================================================
# 2. CALCULATION & ELIGIBILITY TESTS
# ==============================================================================

def test_calculate_event_reminder_windows(client: TestClient, db_session: Session):
    """Test J-7 and J-2 window calculation for various time horizons."""
    ev_data = create_reminder_test_event(client, "Event Horizons", days_in_future=7.0)
    event = db_session.query(Event).filter(Event.id == uuid.UUID(ev_data["id"])).first()

    now = datetime.now(timezone.utc)

    # Exactly 7 days
    w_j7 = reminder_service.calculate_event_reminder_windows(event, now=now)
    assert w_j7["j7_eligible"] is True
    assert w_j7["j2_eligible"] is False
    assert 6.5 < w_j7["days_until_event"] <= 7.5

    # Exactly 2 days before
    w_j2 = reminder_service.calculate_event_reminder_windows(
        event, now=event.start_date - timedelta(days=2)
    )
    assert w_j2["j7_eligible"] is False
    assert w_j2["j2_eligible"] is True

    # 15 days before (too early)
    w_early = reminder_service.calculate_event_reminder_windows(
        event, now=event.start_date - timedelta(days=15)
    )
    assert w_early["j7_eligible"] is False
    assert w_early["j2_eligible"] is False

    # Event already past
    w_past = reminder_service.calculate_event_reminder_windows(
        event, now=event.start_date + timedelta(days=2)
    )
    assert w_past["j7_eligible"] is False
    assert w_past["j2_eligible"] is False


# ==============================================================================
# 3. IDEMPOTENCY & DISPATCH TESTS
# ==============================================================================

def test_send_order_reminder_email_idempotency(client: TestClient, db_session: Session):
    """Ensure reminder emails are sent once per type and idempotent on duplicates."""
    ev_data = create_reminder_test_event(client, "Event Idempotency", days_in_future=7.0)
    event = db_session.query(Event).filter(Event.id == uuid.UUID(ev_data["id"])).first()

    order = Order(
        event_id=event.id,
        order_number=generate_order_number(),
        first_name="Jacques",
        last_name="Martin",
        email="jacques.martin@example.com",
        phone="0611223344",
        honor_declaration_accepted=True,
        total_price_cents=3000,
        status="confirmed",
        payment_method="stripe",
        access_token=generate_access_token(),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    # 1. First J-7 send -> simulated log created
    log1 = reminder_service.send_order_reminder_email(
        order=order, event=event, reminder_type="j7", db=db_session
    )
    assert log1 is not None
    assert log1.status == "simulated"
    assert log1.email_type == "reminder_j7"

    # 2. Duplicate J-7 send with force=False -> returns existing log, 0 new rows
    log2 = reminder_service.send_order_reminder_email(
        order=order, event=event, reminder_type="j7", force=False, db=db_session
    )
    assert log2 is not None
    assert log2.id == log1.id

    logs_count = (
        db_session.query(EmailLog)
        .filter(EmailLog.order_id == order.id, EmailLog.email_type == "reminder_j7")
        .count()
    )
    assert logs_count == 1

    # 3. J-2 send for the same order -> creates a distinct reminder_j2 record
    log3 = reminder_service.send_order_reminder_email(
        order=order, event=event, reminder_type="j2", db=db_session
    )
    assert log3 is not None
    assert log3.email_type == "reminder_j2"
    assert log3.id != log1.id

    total_logs = db_session.query(EmailLog).filter(EmailLog.order_id == order.id).count()
    assert total_logs == 2


def test_send_order_reminder_skips_unconfirmed_and_no_email(client: TestClient, db_session: Session):
    """Unconfirmed orders or orders without email addresses are skipped."""
    ev_data = create_reminder_test_event(client, "Event Skip Cases")
    event = db_session.query(Event).filter(Event.id == uuid.UUID(ev_data["id"])).first()

    # Pending order
    order_pending = Order(
        event_id=event.id,
        order_number=generate_order_number(),
        first_name="Pending",
        last_name="User",
        email="pending@example.com",
        phone="0600000001",
        honor_declaration_accepted=True,
        total_price_cents=1000,
        status="pending",
        access_token=generate_access_token(),
    )
    # Confirmed but without email
    order_no_email = Order(
        event_id=event.id,
        order_number=generate_order_number(),
        first_name="NoMail",
        last_name="User",
        email=None,
        phone="0600000002",
        honor_declaration_accepted=True,
        total_price_cents=1000,
        status="confirmed",
        access_token=generate_access_token(),
    )
    db_session.add_all([order_pending, order_no_email])
    db_session.commit()

    assert reminder_service.send_order_reminder_email(order_pending, event, "j7", db=db_session) is None
    assert reminder_service.send_order_reminder_email(order_no_email, event, "j7", db=db_session) is None

    assert db_session.query(EmailLog).filter(EmailLog.order_id.in_([order_pending.id, order_no_email.id])).count() == 0


def test_process_event_reminders(client: TestClient, db_session: Session):
    """Test process_event_reminders runs bulk dispatch with accurate reports."""
    ev_data = create_reminder_test_event(client, "Bulk Event Reminders", days_in_future=7.0)
    event = db_session.query(Event).filter(Event.id == uuid.UUID(ev_data["id"])).first()
    spot1 = create_test_spot(client, ev_data["id"], "BK-01")
    spot2 = create_test_spot(client, ev_data["id"], "BK-02")

    # Order 1: Confirmed with email
    o1 = Order(
        event_id=event.id,
        order_number=generate_order_number(),
        first_name="Exposant1",
        last_name="Valid",
        email="expo1@example.com",
        phone="0600000001",
        honor_declaration_accepted=True,
        total_price_cents=1500,
        status="confirmed",
        access_token=generate_access_token(),
    )
    # Order 2: Confirmed without email (offline cash)
    o2 = Order(
        event_id=event.id,
        order_number=generate_order_number(),
        first_name="Exposant2",
        last_name="Guichet",
        email=None,
        phone="0600000002",
        honor_declaration_accepted=True,
        total_price_cents=1500,
        status="confirmed",
        access_token=generate_access_token(),
    )
    db_session.add_all([o1, o2])
    db_session.commit()

    # Link spots
    db_session.add_all([
        BookingItem(order_id=o1.id, spot_id=uuid.UUID(spot1["id"]), price_cents=1500),
        BookingItem(order_id=o2.id, spot_id=uuid.UUID(spot2["id"]), price_cents=1500),
    ])
    db_session.commit()

    # First run
    report1 = reminder_service.process_event_reminders(
        event_id=event.id, reminder_type="j7", force=False, db=db_session
    )
    assert report1.orders_processed == 2
    assert report1.reminders_sent == 1
    assert report1.reminders_skipped == 0
    assert report1.orders_without_email == 1

    # Second run (immediate retry): should skip o1 due to idempotence
    report2 = reminder_service.process_event_reminders(
        event_id=event.id, reminder_type="j7", force=False, db=db_session
    )
    assert report2.orders_processed == 2
    assert report2.reminders_sent == 0
    assert report2.reminders_skipped == 1
    assert report2.orders_without_email == 1


# ==============================================================================
# 4. API ENDPOINTS TESTS
# ==============================================================================

def test_api_get_reminders_status(client: TestClient, db_session: Session):
    """Test GET /api/v1/events/{id_or_slug}/reminders/status returns status counters."""
    ev_data = create_reminder_test_event(client, "Status Endpoint Event", days_in_future=6.5)
    event_id = ev_data["id"]

    res = client.get(f"/api/v1/events/{event_id}/reminders/status")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["event_id"] == event_id
    assert data["j7_eligible"] is True
    assert data["j7_sent_count"] == 0
    assert data["total_confirmed_orders"] == 0


def test_api_trigger_event_reminders(client: TestClient, db_session: Session):
    """Test POST /api/v1/events/{id_or_slug}/reminders/trigger triggers reminder batch."""
    ev_data = create_reminder_test_event(client, "Trigger Endpoint Event", days_in_future=7.0)
    event_id = ev_data["id"]

    # Add a confirmed order
    o = Order(
        event_id=uuid.UUID(event_id),
        order_number=generate_order_number(),
        first_name="Pierre",
        last_name="Trigger",
        email="pierre.trigger@example.com",
        phone="0611223344",
        honor_declaration_accepted=True,
        total_price_cents=2000,
        status="confirmed",
        access_token=generate_access_token(),
    )
    db_session.add(o)
    db_session.commit()

    # Trigger via API
    res = client.post(
        f"/api/v1/events/{event_id}/reminders/trigger",
        json={"reminder_type": "j7", "force": False},
    )
    assert res.status_code == 200, res.text
    report = res.json()
    assert report["reminders_sent"] == 1
    assert report["reminders_skipped"] == 0

    # Verify status updated
    st_res = client.get(f"/api/v1/events/{event_id}/reminders/status")
    assert st_res.status_code == 200
    assert st_res.json()["j7_sent_count"] == 1


def test_api_system_reminders_process(client: TestClient, db_session: Session):
    """Test POST /api/v1/system/reminders/process evaluates scheduled upcoming events."""
    ev_data = create_reminder_test_event(client, "System Cron Event", days_in_future=2.0)
    event_id = ev_data["id"]

    o = Order(
        event_id=uuid.UUID(event_id),
        order_number=generate_order_number(),
        first_name="Simone",
        last_name="System",
        email="simone.system@example.com",
        phone="0699887766",
        honor_declaration_accepted=True,
        total_price_cents=2500,
        status="confirmed",
        access_token=generate_access_token(),
    )
    db_session.add(o)
    db_session.commit()

    res = client.post("/api/v1/system/reminders/process")
    assert res.status_code == 200, res.text
    result = res.json()
    assert result["events_evaluated"] >= 1
    assert result["total_reminders_sent"] >= 1


def test_calculate_event_reminder_windows_no_overlap(client: TestClient, db_session: Session):
    """Verify strictly no overlap exists between J-7 and J-2 windows across boundary conditions."""
    ev_data = create_reminder_test_event(client, "Boundary Test Event", days_in_future=7.0)
    event = db_session.query(Event).filter(Event.id == uuid.UUID(ev_data["id"])).first()

    # 2.2 days before: only J-2 should be active, J-7 must be False
    w_2_2 = reminder_service.calculate_event_reminder_windows(
        event, now=event.start_date - timedelta(days=2.2)
    )
    assert w_2_2["j7_eligible"] is False
    assert w_2_2["j2_eligible"] is True

    # 2.6 days before: only J-7 should be active, J-2 must be False
    w_2_6 = reminder_service.calculate_event_reminder_windows(
        event, now=event.start_date - timedelta(days=2.6)
    )
    assert w_2_6["j7_eligible"] is True
    assert w_2_6["j2_eligible"] is False

    # 0.0 days (exact start): J-2 is active
    w_0 = reminder_service.calculate_event_reminder_windows(
        event, now=event.start_date
    )
    assert w_0["j7_eligible"] is False
    assert w_0["j2_eligible"] is True

    # -0.1 days (event started 2.4 hours ago): neither J-7 nor J-2 active
    w_past = reminder_service.calculate_event_reminder_windows(
        event, now=event.start_date + timedelta(hours=2.4)
    )
    assert w_past["j7_eligible"] is False
    assert w_past["j2_eligible"] is False


def test_api_system_reminders_process_j7_automatic(client: TestClient, db_session: Session):
    """Test POST /api/v1/system/reminders/process automatically dispatches J-7 reminders."""
    ev_data = create_reminder_test_event(client, "System J-7 Auto Event", days_in_future=6.8)
    event_id = ev_data["id"]

    o = Order(
        event_id=uuid.UUID(event_id),
        order_number=generate_order_number(),
        first_name="Auto",
        last_name="J7User",
        email="autoj7@example.com",
        phone="0601020304",
        honor_declaration_accepted=True,
        total_price_cents=3000,
        status="confirmed",
        access_token=generate_access_token(),
    )
    db_session.add(o)
    db_session.commit()

    res = client.post("/api/v1/system/reminders/process")
    assert res.status_code == 200, res.text
    result = res.json()

    # Find the report for this event
    ev_reports = [r for r in result["reports"] if r["event_id"] == event_id]
    assert len(ev_reports) == 1
    assert ev_reports[0]["reminder_type"] == "j7"
    assert ev_reports[0]["reminders_sent"] == 1

    # Verify EmailLog in database
    log = db_session.query(EmailLog).filter(EmailLog.order_id == o.id).first()
    assert log is not None
    assert log.email_type == "reminder_j7"


def test_api_get_reminders_status_counters_with_mixed_orders(client: TestClient, db_session: Session):
    """Verify total_confirmed_with_email accurately distinguishes orders with vs without email."""
    ev_data = create_reminder_test_event(client, "Counters Mixed Event", days_in_future=5.0)
    event_id = ev_data["id"]

    o1 = Order(
        event_id=uuid.UUID(event_id),
        order_number=generate_order_number(),
        first_name="User1",
        last_name="Mail",
        email="user1.mail@example.com",
        phone="0600000001",
        honor_declaration_accepted=True,
        total_price_cents=1000,
        status="confirmed",
        access_token=generate_access_token(),
    )
    o2 = Order(
        event_id=uuid.UUID(event_id),
        order_number=generate_order_number(),
        first_name="User2",
        last_name="NoMail",
        email=None,
        phone="0600000002",
        honor_declaration_accepted=True,
        total_price_cents=1000,
        status="confirmed",
        access_token=generate_access_token(),
    )
    o3 = Order(
        event_id=uuid.UUID(event_id),
        order_number=generate_order_number(),
        first_name="User3",
        last_name="Pending",
        email="pending.user@example.com",
        phone="0600000003",
        honor_declaration_accepted=True,
        total_price_cents=1000,
        status="pending",
        access_token=generate_access_token(),
    )
    db_session.add_all([o1, o2, o3])
    db_session.commit()

    res = client.get(f"/api/v1/events/{event_id}/reminders/status")
    assert res.status_code == 200
    data = res.json()
    assert data["total_confirmed_orders"] == 2
    assert data["total_confirmed_with_email"] == 1


def test_process_event_reminders_rejects_non_published_event(client: TestClient, db_session: Session):
    """Triggering reminders on a non-published event returns HTTP 400 Bad Request."""
    ev_data = create_reminder_test_event(client, "Cancelled Event", days_in_future=3.0)
    event_id = ev_data["id"]

    # Mark event as cancelled
    event = db_session.query(Event).filter(Event.id == uuid.UUID(event_id)).first()
    event.status = "cancelled"
    db_session.commit()

    res = client.post(
        f"/api/v1/events/{event_id}/reminders/trigger",
        json={"reminder_type": "j7"},
    )
    assert res.status_code == 400
    assert "seuls les événements publiés" in res.json()["detail"].lower() or "published" in res.json()["detail"].lower()


def test_cli_process_reminders_script(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """Exercise the CLI runner script main() function."""
    import sys
    from app.scripts import process_reminders

    class TestSessionProxy:
        def __init__(self, sess):
            self.sess = sess
        def __getattr__(self, item):
            return getattr(self.sess, item)
        def close(self):
            pass

    monkeypatch.setattr(process_reminders, "SessionLocal", lambda: TestSessionProxy(db_session))

    ev_data = create_reminder_test_event(client, "CLI Test Event", days_in_future=2.0)
    event_id = ev_data["id"]

    # 1. Run for single event via CLI arguments
    monkeypatch.setattr(
        sys,
        "argv",
        ["process_reminders", "--event-id", event_id, "--reminder-type", "j2"],
    )
    exit_code = process_reminders.main()
    assert exit_code == 0

    # 2. Run for invalid UUID
    monkeypatch.setattr(
        sys,
        "argv",
        ["process_reminders", "--event-id", "not-a-uuid"],
    )
    exit_code_invalid = process_reminders.main()
    assert exit_code_invalid == 1


