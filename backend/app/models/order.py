import uuid
import secrets
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    Boolean,
    ForeignKey,
    func,
    Uuid,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


def generate_order_number() -> str:
    """Generate a human-friendly unique order number, e.g. GVG-2026-ABCD."""
    year = datetime.now().year
    suffix = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(4))
    return f"GVG-{year}-{suffix}"


def generate_access_token() -> str:
    """Generate an unguessable URL-safe access token for passwordless order management."""
    return secrets.token_urlsafe(32)


class Order(Base):
    __tablename__ = "orders"

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    event_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_number = Column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        default=generate_order_number,
    )

    # Exhibitor contact information (Guest checkout - no password)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=False)
    street_address = Column(String(255), nullable=True)
    postal_code = Column(String(20), nullable=True)
    city = Column(String(100), nullable=True)

    # Offline manual booking metadata
    offline_payment_reference = Column(String(255), nullable=True)
    admin_notes = Column(Text, nullable=True)

    # Legal sworn declaration (art. L310-2 du Code de commerce)
    honor_declaration_accepted = Column(Boolean, nullable=False, default=True)
    honor_declaration_accepted_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Order financial & status
    total_price_cents = Column(Integer, nullable=False, default=0)
    status = Column(
        String(50),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    payment_method = Column(
        String(50),
        nullable=False,
        default="stripe",
        server_default="stripe",
    )
    stripe_payment_intent_id = Column(String(255), nullable=True)

    # Passwordless magic access token
    access_token = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        default=generate_access_token,
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    event = relationship("Event", back_populates="orders")
    items = relationship("BookingItem", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Order id={self.id} order_number={self.order_number!r} status={self.status!r}>"

    @property
    def total_price(self) -> float:
        if self.total_price_cents is not None:
            return round(self.total_price_cents / 100.0, 2)
        return 0.0

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class BookingItem(Base):
    __tablename__ = "booking_items"

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    order_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    spot_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("spots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price_cents = Column(Integer, nullable=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    order = relationship("Order", back_populates="items")
    spot = relationship("Spot", back_populates="booking_items")

    def __repr__(self) -> str:
        return f"<BookingItem id={self.id} order_id={self.order_id} spot_id={self.spot_id} price_cents={self.price_cents}>"

    @property
    def price(self) -> float:
        if self.price_cents is not None:
            return round(self.price_cents / 100.0, 2)
        return 0.0
