import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class EmailLogOut(BaseModel):
    id: uuid.UUID
    event_id: Optional[uuid.UUID] = None
    order_id: Optional[uuid.UUID] = None
    recipient: str
    email_type: str
    subject: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmailLogListResponse(BaseModel):
    items: List[EmailLogOut]
    total: int

