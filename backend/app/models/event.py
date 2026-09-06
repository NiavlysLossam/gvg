import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean, func, Uuid
from app.core.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    title = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    map_type = Column(String(50), nullable=False, default="geographic")
    background_image_url = Column(String(1024), nullable=True)
    price_per_meter_cents = Column(Integer, nullable=False)
    
    # Dates and schedule
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    setup_start_time = Column(String(10), nullable=True, default="06:00")
    setup_end_time = Column(String(10), nullable=True, default="08:00")
    public_start_time = Column(String(10), nullable=True, default="08:00")
    public_end_time = Column(String(10), nullable=True, default="18:00")

    # Location & contacts
    location_address = Column(String(500), nullable=True)
    organizer_email = Column(String(255), nullable=True)

    # Financial and management
    stripe_account_id = Column(String(255), nullable=True)
    manual_approval_required = Column(Boolean, nullable=False, default=False)
    rules_text = Column(Text, nullable=True)

    # Status: 'draft', 'published', 'archived', etc.
    status = Column(String(50), nullable=False, default="draft")

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

    def __repr__(self) -> str:
        return f"<Event id={self.id} title={self.title!r} slug={self.slug!r} status={self.status!r}>"

    @property
    def price_per_meter(self) -> float:
        if self.price_per_meter_cents is not None:
            return round(self.price_per_meter_cents / 100.0, 2)
        return 0.0

