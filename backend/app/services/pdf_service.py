import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import weasyprint
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.event import Event
from app.models.order import Order

logger = logging.getLogger(__name__)

PDF_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "pdf"

pdf_jinja_env = Environment(
    loader=FileSystemLoader(str(PDF_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def format_french_date(dt: Optional[datetime]) -> str:
    """Format a datetime into a standard French readable date, e.g. '14 juin 2026'."""
    if not dt:
        return "Non spécifiée"
    months_fr = [
        "", "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"
    ]
    return f"{dt.day} {months_fr[dt.month]} {dt.year}"


def format_address(order: Order) -> str:
    """Format an exhibitor's postal address from its components."""
    parts = []
    if order.street_address and order.street_address.strip():
        parts.append(order.street_address.strip())
    city_line = []
    if order.postal_code and order.postal_code.strip():
        city_line.append(order.postal_code.strip())
    if order.city and order.city.strip():
        city_line.append(order.city.strip())
    if city_line:
        parts.append(" ".join(city_line))
    
    if not parts:
        return "Non renseignée"
    return ", ".join(parts)


def natural_sort_key(s: str) -> list:
    """Natural alphanumeric sort key for spot labels (e.g. A01, A02, A10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]


def format_spots_summary(order: Order) -> tuple[str, str]:
    """
    Extract assigned spots and calculate total linear meters.
    Returns a tuple of (formatted_spots_str, formatted_meters_str).
    """
    if not order.items:
        return "Non attribué", "0,00 m"

    spot_labels = []
    total_meters = 0.0

    for item in order.items:
        if item.spot:
            spot_labels.append(item.spot.label)
            if item.spot.linear_meters is not None:
                total_meters += float(item.spot.linear_meters)

    spot_labels.sort(key=natural_sort_key)

    if not spot_labels:
        formatted_spots = "Non attribué"
    elif len(spot_labels) == 1:
        formatted_spots = f"Stand {spot_labels[0]}"
    else:
        formatted_spots = "Stands " + ", ".join(spot_labels)

    formatted_meters = f"{total_meters:.2f}".replace(".", ",") + " m"
    return formatted_spots, formatted_meters


def generate_attestation_pdf(order: Order, event: Event) -> bytes:
    """
    Generate an in-memory PDF document for the official sworn statement (Attestation sur l'honneur)
    pursuant to Article L. 310-2 of the French Code de commerce.
    Returns raw PDF bytes.
    """
    spots_formatted, total_linear_meters_formatted = format_spots_summary(order)
    event_date_formatted = format_french_date(event.start_date)
    address_formatted = format_address(order)
    current_year = event.start_date.year if event.start_date else datetime.now().year

    context = {
        "order": order,
        "event": event,
        "event_date_formatted": event_date_formatted,
        "address_formatted": address_formatted,
        "spots_formatted": spots_formatted,
        "total_linear_meters_formatted": total_linear_meters_formatted,
        "current_year": current_year,
    }

    template = pdf_jinja_env.get_template("attestation.html")
    html_content = template.render(**context)

    # Compile HTML to PDF in memory using WeasyPrint
    pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()

    return pdf_bytes

