import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
    Uuid,
)
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.core.database import Base


class Spot(Base):
    __tablename__ = "spots"

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
    label = Column(String(100), nullable=False)
    linear_meters = Column(Float, nullable=False)
    price_cents = Column(Integer, nullable=False)

    # 2D Polygon geometry
    geom = Column(Geometry("POLYGON", srid=-1, spatial_index=True), nullable=False)

    # Status: 'available', 'locked', 'reserved', 'blocked'
    status = Column(
        String(50),
        nullable=False,
        default="available",
        server_default="available",
        index=True,
    )
    locked_until = Column(DateTime(timezone=True), nullable=True)
    locked_by_token = Column(String(255), nullable=True)

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

    __table_args__ = (
        UniqueConstraint("event_id", "label", name="uq_spots_event_id_label"),
    )

    # Relationships
    event = relationship("Event", back_populates="spots")

    def __repr__(self) -> str:
        return f"<Spot id={self.id} event_id={self.event_id} label={self.label!r} status={self.status!r}>"

    @property
    def price(self) -> float:
        if self.price_cents is not None:
            return round(self.price_cents / 100.0, 2)
        return 0.0

