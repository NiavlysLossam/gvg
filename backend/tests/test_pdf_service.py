import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.spot import Spot
from app.models.order import Order, BookingItem
from app.services import pdf_service
from app.services.pdf_service import (
    generate_attestation_pdf,
    format_french_date,
    format_address,
    format_spots_summary,
    pdf_jinja_env,
)


def create_test_event_and_confirmed_order(db: Session) -> tuple[Event, Order, Spot]:
    """Helper creating a test event, spot, and confirmed order in DB."""
    event = Event(
        title="Vide-Greniers des Cerisiers",
        slug=f"vide-greniers-cerisiers-{uuid.uuid4().hex[:6]}",
        description="Le rendez-vous annuel du quartier",
        price_per_meter_cents=500,
        map_type="geographic",
        start_date=datetime(2026, 6, 14, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 6, 14, 18, 0, tzinfo=timezone.utc),
        setup_start_time="06:30",
        setup_end_time="08:00",
        public_start_time="08:00",
        public_end_time="18:00",
        location_address="12 Rue des Cerisiers, 75015 Paris",
        organizer_email="contact@cerisiers.org",
        status="published",
    )
    db.add(event)
    db.flush()

    # Create a spot using raw SQL or dummy geometry compatible with PostGIS / SpatiaLite
    spot = Spot(
        event_id=event.id,
        label="C-14",
        linear_meters=3.0,
        price_cents=1500,
        status="reserved",
        geom="SRID=-1;POLYGON((0 0, 0 2, 3 2, 3 0, 0 0))",
    )
    db.add(spot)
    db.flush()

    order = Order(
        event_id=event.id,
        order_number=f"GVG-2026-{uuid.uuid4().hex[:4].upper()}",
        first_name="Monique",
        last_name="Dupont",
        email="monique.dupont@example.com",
        phone="06 12 34 56 78",
        street_address="45 Avenue de la République",
        postal_code="75011",
        city="Paris",
        honor_declaration_accepted=True,
        total_price_cents=1500,
        status="confirmed",
        payment_method="stripe",
    )
    db.add(order)
    db.flush()

    item = BookingItem(
        order_id=order.id,
        spot_id=spot.id,
        price_cents=1500,
    )
    db.add(item)
    db.commit()
    db.refresh(order)
    db.refresh(event)

    return event, order, spot


# ==============================================================================
# Unit Tests : pdf_service & Jinja2 Template
# ==============================================================================

def test_pdf_format_helpers():
    """Verify string formatting helpers for dates, addresses, and spots."""
    # Date helper
    dt = datetime(2026, 9, 20, 10, 30)
    assert format_french_date(dt) == "20 septembre 2026"
    assert format_french_date(None) == "Non spécifiée"

    # Address helper
    order = Order(
        first_name="Jean",
        last_name="Valjean",
        street_address="Rue de la Paix",
        postal_code="75002",
        city="Paris",
        phone="0123456789",
    )
    assert format_address(order) == "Rue de la Paix, 75002 Paris"

    # Incomplete address
    order_empty_addr = Order(first_name="Jean", last_name="Valjean", phone="0123456789")
    assert format_address(order_empty_addr) == "Non renseignée"

    # Spot summary
    spot1 = Spot(label="A-01", linear_meters=2.0, price_cents=1000)
    item1 = BookingItem(spot=spot1, price_cents=1000)
    order.items = [item1]
    spots_str, meters_str = format_spots_summary(order)
    assert spots_str == "Stand A-01"
    assert meters_str == "2,00 m"


def test_generate_attestation_pdf_nominal():
    """Verify that PDF generation produces valid PDF bytes with all legal contents."""
    event = Event(
        title="Brocante d'Été 2026",
        slug="brocante-ete-2026",
        start_date=datetime(2026, 7, 5, 8, 0),
        location_address="Place Centrale, 33000 Bordeaux",
        setup_start_time="06:00",
    )
    spot = Spot(label="B-07", linear_meters=2.5, price_cents=1250)
    item = BookingItem(spot=spot, price_cents=1250)
    order = Order(
        order_number="GVG-2026-X999",
        first_name="Bernadette",
        last_name="Martin",
        email="bernadette@example.org",
        phone="06 98 76 54 32",
        street_address="14 Rue des Moulins",
        postal_code="33000",
        city="Bordeaux",
        status="confirmed",
        items=[item],
    )

    pdf_bytes = generate_attestation_pdf(order, event)

    # Validate output
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 5000
    assert pdf_bytes.startswith(b"%PDF-")


def test_attestation_html_template_contains_mandatory_legal_mentions():
    """Verify that the rendered HTML contains all French legal mentions."""
    event = Event(
        title="Grand Vide-Grenier de la Concorde",
        start_date=datetime(2026, 5, 17, 8, 0),
        location_address="Esplanade des Invalides, 75007 Paris",
    )
    spot = Spot(label="E-42", linear_meters=4.0, price_cents=2000)
    item = BookingItem(spot=spot, price_cents=2000)
    order = Order(
        order_number="GVG-2026-LEGAL",
        first_name="Camille",
        last_name="Desmoulins",
        email="camille@republique.fr",
        phone="01 40 50 60 70",
        street_address="10 Rue Saint-Honoré",
        postal_code="75001",
        city="Paris",
        items=[item],
    )

    template = pdf_jinja_env.get_template("attestation.html")
    rendered = template.render(
        order=order,
        event=event,
        event_date_formatted="17 mai 2026",
        address_formatted="10 Rue Saint-Honoré, 75001 Paris",
        spots_formatted="Stand E-42",
        total_linear_meters_formatted="4,00 m",
        current_year=2026,
    )

    # Regulatory checks
    assert "Article L. 310-2 du Code de commerce" in rendered
    assert "Article R. 310-8" in rendered
    assert "Article 441-7 du Code pénal" in rendered
    assert "deux manifestations par an au maximum" in rendered
    assert "exclusivement que des objets personnels et usagés" in rendered
    assert "pièce d'identité originale et en cours de validité" in rendered
    assert "Lu et approuvé" in rendered
    assert "Cadre réservé à l'Organisateur" in rendered
    assert "Délivrée le :" in rendered
    assert "Camille Desmoulins" in rendered
    assert "GVG-2026-LEGAL" in rendered
    assert "Stand E-42" in rendered
    assert "4,00 m" in rendered


def test_generate_attestation_pdf_missing_optional_fields():
    """Ensure PDF generation never crashes when optional fields are None."""
    event = Event(
        title="Brocante Sans Adresse",
        start_date=None,
        location_address=None,
        setup_start_time=None,
    )
    order = Order(
        order_number="GVG-2026-EMPTY",
        first_name="Guichet",
        last_name="Anonyme",
        email=None,
        phone=None,
        street_address=None,
        postal_code=None,
        city=None,
        status="confirmed",
        items=[],
    )

    pdf_bytes = generate_attestation_pdf(order, event)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")


def test_generate_attestation_pdf_accents_and_special_chars():
    """Ensure proper UTF-8 handling for complex French names, quotes, and symbols."""
    event = Event(
        title="Foire d'Automne à l'Île-d'Yeu — « Spécialité & Brocante »",
        start_date=datetime(2026, 10, 25, 9, 0),
        location_address="Place de la République & Quai des Pêcheurs, 85350 L'Île-d'Yeu",
    )
    spot = Spot(label="Stand-Île-1", linear_meters=2.0, price_cents=1000)
    item = BookingItem(spot=spot, price_cents=1000)
    order = Order(
        order_number="GVG-2026-ACCENT",
        first_name="François-Noël",
        last_name="de l'Éperonnière",
        email="francois@ile-d-yeu.fr",
        phone="+33 2 51 00 00 00",
        street_address="3 Impasse de l'Échiquier",
        postal_code="85350",
        city="L'Île-d'Yeu",
        status="confirmed",
        items=[item],
    )

    pdf_bytes = generate_attestation_pdf(order, event)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")


def test_generate_attestation_pdf_multiple_spots():
    """Ensure natural alphanumeric sorting and correct cumul of linear meters for multiple stalls."""
    event = Event(
        title="Grande Braderie",
        start_date=datetime(2026, 9, 6, 8, 0),
    )
    # Stalls provided in random/unsorted order
    spots = [
        Spot(label="S-10", linear_meters=2.0, price_cents=1000),
        Spot(label="S-02", linear_meters=2.0, price_cents=1000),
        Spot(label="S-01", linear_meters=2.0, price_cents=1000),
    ]
    items = [BookingItem(spot=s, price_cents=1000) for s in spots]
    order = Order(
        order_number="GVG-2026-MULTI",
        first_name="Michel",
        last_name="Dubois",
        phone="0600000000",
        items=items,
    )

    spots_summary, meters_summary = format_spots_summary(order)
    # Must be sorted alphanumerically: S-01, S-02, S-10
    assert spots_summary == "Stands S-01, S-02, S-10"
    assert meters_summary == "6,00 m"

    pdf_bytes = generate_attestation_pdf(order, event)
    assert pdf_bytes.startswith(b"%PDF-")


def test_attestation_pdf_single_page_count():
    """Verify that generated attestation renders into exactly 1 A4 page."""
    import weasyprint
    event = Event(
        title="Vide-Greniers des Lilas",
        start_date=datetime(2026, 6, 14, 8, 0),
        location_address="10 Rue des Fleurs, 75020 Paris",
        setup_start_time="06:30",
    )
    spots = [
        Spot(label=f"A-{i:02d}", linear_meters=2.0, price_cents=1000)
        for i in range(1, 4)
    ]
    items = [BookingItem(spot=s, price_cents=1000) for s in spots]
    order = Order(
        order_number="GVG-2026-PAGES",
        first_name="Monique",
        last_name="Dupont",
        email="monique.dupont@example.com",
        phone="06 12 34 56 78",
        street_address="12 Rue de la République",
        postal_code="75011",
        city="Paris",
        status="confirmed",
        items=items,
    )
    template = pdf_jinja_env.get_template("attestation.html")
    spots_formatted, total_meters = format_spots_summary(order)
    rendered = template.render(
        order=order,
        event=event,
        event_date_formatted="14 juin 2026",
        address_formatted="12 Rue de la République, 75011 Paris",
        spots_formatted=spots_formatted,
        total_linear_meters_formatted=total_meters,
        current_year=2026,
    )
    doc = weasyprint.HTML(string=rendered).render()
    assert len(doc.pages) == 1



# ==============================================================================
# Integration Tests : Public Endpoint GET /public/events/{slug}/orders/{id}/attestation.pdf
# ==============================================================================

def test_public_attestation_download_nominal(client: TestClient, db_session: Session):
    """Exhibitor can download attestation PDF with valid HMAC access token."""
    event, order, _ = create_test_event_and_confirmed_order(db_session)

    res = client.get(
        f"/api/v1/public/events/{event.slug}/orders/{order.id}/attestation.pdf",
        params={"token": order.access_token},
    )

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["cache-control"] == "private, no-store, must-revalidate"
    assert f'filename="attestation_{order.order_number}.pdf"' in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF-")


def test_public_attestation_download_null_access_token_guard():
    """If order.access_token is unexpectedly None, compare_digest must not raise TypeError."""
    from unittest.mock import MagicMock
    from fastapi import HTTPException
    from app.api.v1.endpoints.public import download_public_attestation_pdf

    mock_db = MagicMock()
    mock_event = MagicMock()
    mock_order = MagicMock()
    mock_order.access_token = None
    mock_order.status = "confirmed"

    mock_db.query.return_value.filter.return_value.first.return_value = mock_event
    mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_order

    with pytest.raises(HTTPException) as exc_info:
        download_public_attestation_pdf(
            slug="test-event",
            order_id=uuid.uuid4(),
            token="some-token",
            db=mock_db,
        )
    assert exc_info.value.status_code == 403
    assert "jeton" in exc_info.value.detail.lower()




def test_public_attestation_download_via_header(client: TestClient, db_session: Session):
    """Exhibitor can provide token via X-Access-Token header."""
    event, order, _ = create_test_event_and_confirmed_order(db_session)

    res = client.get(
        f"/api/v1/public/events/{event.slug}/orders/{order.id}/attestation.pdf",
        headers={"X-Access-Token": order.access_token},
    )

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF-")


def test_public_attestation_download_missing_token_forbidden(client: TestClient, db_session: Session):
    """Request without token is immediately rejected with 403 Forbidden."""
    event, order, _ = create_test_event_and_confirmed_order(db_session)

    res = client.get(f"/api/v1/public/events/{event.slug}/orders/{order.id}/attestation.pdf")
    assert res.status_code == 403
    assert "jeton" in res.text.lower()


def test_public_attestation_download_invalid_token_forbidden(client: TestClient, db_session: Session):
    """Request with invalid/tampered token is rejected with 403 Forbidden."""
    event, order, _ = create_test_event_and_confirmed_order(db_session)

    res = client.get(
        f"/api/v1/public/events/{event.slug}/orders/{order.id}/attestation.pdf",
        params={"token": "invalid-random-token-12345"},
    )
    assert res.status_code == 403
    assert "jeton" in res.text.lower()


@pytest.mark.parametrize("unconfirmed_status", ["pending", "pending_approval", "refunded", "cancelled", "rejected"])
def test_public_attestation_download_unconfirmed_rejected(
    client: TestClient,
    db_session: Session,
    unconfirmed_status: str,
):
    """Attestation is only issued for confirmed orders. Unconfirmed orders return 400 Bad Request."""
    event, order, _ = create_test_event_and_confirmed_order(db_session)
    order.status = unconfirmed_status
    db_session.commit()

    res = client.get(
        f"/api/v1/public/events/{event.slug}/orders/{order.id}/attestation.pdf",
        params={"token": order.access_token},
    )
    assert res.status_code == 400
    assert "confirmée" in res.text.lower()


def test_public_attestation_download_not_found(client: TestClient, db_session: Session):
    """404 when event slug or order_id does not exist."""
    event, order, _ = create_test_event_and_confirmed_order(db_session)

    # Unknown event slug
    res = client.get(
        f"/api/v1/public/events/nonexistent-event-slug/orders/{order.id}/attestation.pdf",
        params={"token": order.access_token},
    )
    assert res.status_code == 404

    # Unknown order ID
    random_id = uuid.uuid4()
    res = client.get(
        f"/api/v1/public/events/{event.slug}/orders/{random_id}/attestation.pdf",
        params={"token": order.access_token},
    )
    assert res.status_code == 404


# ==============================================================================
# Integration Tests : Admin Endpoint GET /events/{id_or_slug}/orders/{id}/attestation.pdf
# ==============================================================================

def test_admin_attestation_download_nominal(client: TestClient, db_session: Session):
    """Organizer can download attestation PDF without exhibitor token."""
    event, order, _ = create_test_event_and_confirmed_order(db_session)

    # Query by event ID
    res = client.get(f"/api/v1/events/{event.id}/orders/{order.id}/attestation.pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["cache-control"] == "private, no-store, must-revalidate"
    assert f'filename="attestation_{order.order_number}.pdf"' in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF-")

    # Query by event slug
    res_slug = client.get(f"/api/v1/events/{event.slug}/orders/{order.id}/attestation.pdf")
    assert res_slug.status_code == 200
    assert res_slug.headers["cache-control"] == "private, no-store, must-revalidate"
    assert res_slug.content.startswith(b"%PDF-")


def test_admin_attestation_download_unconfirmed_order_rejected(client: TestClient, db_session: Session):
    """Admin route returns 400 if order is not confirmed."""
    event, order, _ = create_test_event_and_confirmed_order(db_session)
    order.status = "pending_approval"
    db_session.commit()

    res = client.get(f"/api/v1/events/{event.id}/orders/{order.id}/attestation.pdf")
    assert res.status_code == 400
    assert "confirmée" in res.text.lower()


def test_admin_attestation_download_not_found(client: TestClient, db_session: Session):
    """Admin route returns 404 if event does not exist or order does not belong to event."""
    event, order, _ = create_test_event_and_confirmed_order(db_session)

    # Unknown order ID
    res = client.get(f"/api/v1/events/{event.id}/orders/{uuid.uuid4()}/attestation.pdf")
    assert res.status_code == 404

    # Other event
    other_event = Event(
        title="Autre Événement",
        slug="autre-evenement",
        price_per_meter_cents=500,
        start_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 8, 1, 18, 0, tzinfo=timezone.utc),
    )
    db_session.add(other_event)
    db_session.commit()

    res_cross = client.get(f"/api/v1/events/{other_event.id}/orders/{order.id}/attestation.pdf")
    assert res_cross.status_code == 404

