import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, func, Uuid
from sqlalchemy.orm import relationship
from app.core.database import Base


class UserRole:
    SUPER_ADMIN = "super_admin"
    EVENT_ADMIN = "event_admin"


class User(Base):
    __tablename__ = "users"

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default=UserRole.EVENT_ADMIN)
    is_active = Column(Boolean, nullable=False, default=True)

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

    # Relationships: One admin owns zero, one or multiple events
    events = relationship("Event", back_populates="owner")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role!r} is_active={self.is_active}>"

