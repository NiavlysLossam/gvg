import re
import logging
import unicodedata
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


def natural_sort_key(s: Optional[str]) -> list:
    """Natural alphanumeric sort key for spot labels (e.g. A01, A02, A10)."""
    if not s:
        return []
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


def french_alpha_sort_key(s: Optional[str]) -> tuple[str, str]:
    """
    Generate a sort key for French text: case-insensitive and accent-insensitive,
    ensuring correct collation (e.g. 'Éric' sorts before 'François').
    """
    if not s:
        return ("", "")
    normalized = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    ).lower().strip()
    return (normalized, s.lower().strip())


def format_payment_status(order: Order) -> str:
    """Format payment method/status into clear readable label."""
    method_labels = {
        "stripe": "Payé (CB)",
        "cash": "Payé (Espèces)",
        "check": "Payé (Chèque)",
        "other": "Payé (Autre)",
    }
    return method_labels.get(order.payment_method, "Payé")


def build_checkin_rows(orders: list[Order], sort_by: str = "spot") -> list[dict]:
    """
    Build structured rows for the official check-in sheet (PDF and Excel).
    Filters exclusively for confirmed orders.
    In 'spot' mode: expands multi-spot orders so each stall appears in natural alphanumeric order.
    In 'alpha' mode: lists one entry per order with grouped spots, sorted alphabetically by exhibitor name.
    """
    confirmed_orders = [o for o in orders if o.status == "confirmed"]
    rows: list[dict] = []

    if sort_by == "spot":
        for order in confirmed_orders:
            assigned_items = [item for item in (order.items or []) if item.spot is not None]
            if assigned_items:
                for item in assigned_items:
                    spot = item.spot
                    meters = float(spot.linear_meters) if spot.linear_meters is not None else 0.0
                    meters_str = f"{meters:.2f}".replace(".", ",") + " m"
                    rows.append({
                        "spot_label": spot.label or "Sans label",
                        "linear_meters": meters,
                        "linear_meters_str": meters_str,
                        "full_name": order.full_name or "Non renseigné",
                        "last_name": order.last_name or "",
                        "first_name": order.first_name or "",
                        "phone": order.phone or "—",
                        "email": order.email or "—",
                        "payment_status": format_payment_status(order),
                        "payment_method": order.payment_method or "other",
                        "order_number": order.order_number,
                        "order": order,
                    })
            else:
                rows.append({
                    "spot_label": "Non attribué",
                    "linear_meters": 0.0,
                    "linear_meters_str": "0,00 m",
                    "full_name": order.full_name or "Non renseigné",
                    "last_name": order.last_name or "",
                    "first_name": order.first_name or "",
                    "phone": order.phone or "—",
                    "email": order.email or "—",
                    "payment_status": format_payment_status(order),
                    "payment_method": order.payment_method or "other",
                    "order_number": order.order_number,
                    "order": order,
                })

        # Sort naturally by spot_label (e.g. A-1, A-2, A-10), with non-attributed at the end
        rows.sort(key=lambda r: (
            1 if r["spot_label"] == "Non attribué" else 0,
            natural_sort_key(r["spot_label"]),
            french_alpha_sort_key(r["last_name"]),
            french_alpha_sort_key(r["first_name"]),
        ))

    else:
        # sort_by == "alpha"
        for order in confirmed_orders:
            assigned_spots = [item.spot for item in (order.items or []) if item.spot is not None]
            assigned_spots.sort(key=lambda s: natural_sort_key(s.label or ""))
            if assigned_spots:
                labels_str = ", ".join(s.label for s in assigned_spots if s.label)
                total_meters = sum(float(s.linear_meters) for s in assigned_spots if s.linear_meters is not None)
                meters_str = f"{total_meters:.2f}".replace(".", ",") + " m"
            else:
                labels_str = "Non attribué"
                total_meters = 0.0
                meters_str = "0,00 m"

            rows.append({
                "spot_label": labels_str,
                "linear_meters": total_meters,
                "linear_meters_str": meters_str,
                "full_name": order.full_name or "Non renseigné",
                "last_name": order.last_name or "",
                "first_name": order.first_name or "",
                "phone": order.phone or "—",
                "email": order.email or "—",
                "payment_status": format_payment_status(order),
                "payment_method": order.payment_method or "other",
                "order_number": order.order_number,
                "order": order,
            })

        # Sort alphabetically by exhibitor last name, then first name
        rows.sort(key=lambda r: (
            french_alpha_sort_key(r["last_name"]),
            french_alpha_sort_key(r["first_name"]),
            natural_sort_key(r["spot_label"]),
        ))

    return rows


def generate_checkin_pdf(event: Event, orders: list[Order], sort_by: str = "spot") -> bytes:
    """
    Generate an official check-in sheet (feuille d'émargement) PDF for event day.
    Configured in A4 landscape with repeated table headers and check-in pen entry columns.
    Returns raw PDF bytes directly from memory.
    """
    if sort_by not in ("spot", "alpha"):
        sort_by = "spot"

    rows = build_checkin_rows(orders=orders, sort_by=sort_by)
    event_date_formatted = format_french_date(event.start_date)
    total_meters = sum(r["linear_meters"] for r in rows)
    total_linear_meters_formatted = f"{total_meters:.2f}".replace(".", ",") + " m"

    mode_label = (
        "Classement : Par Emplacement (N° Stand)"
        if sort_by == "spot"
        else "Classement : Par Ordre Alphabétique (Nom)"
    )
    sort_label = (
        "Par Emplacement"
        if sort_by == "spot"
        else "Alphabétique"
    )

    now = datetime.now()
    generation_date = f"{now.day:02d}/{now.month:02d}/{now.year} à {now.hour:02d}h{now.minute:02d}"

    context = {
        "event": event,
        "rows": rows,
        "sort_by": sort_by,
        "sort_label": sort_label,
        "mode_label": mode_label,
        "event_date_formatted": event_date_formatted,
        "total_rows": len(rows),
        "total_linear_meters_formatted": total_linear_meters_formatted,
        "generation_date": generation_date,
    }

    template = pdf_jinja_env.get_template("checkin.html")
    html_content = template.render(**context)

    # Compile HTML to PDF in memory using WeasyPrint
    pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
    return pdf_bytes


