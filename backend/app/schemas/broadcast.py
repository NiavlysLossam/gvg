import uuid
from typing import Optional, List
import re
from pydantic import BaseModel, Field, EmailStr, field_validator


class BroadcastPreviewRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=500, description="Email subject with dynamic tags")
    body: str = Field(..., min_length=1, description="Email body content with dynamic tags")
    order_id: Optional[uuid.UUID] = Field(None, description="Optional specific order ID to use as sample")

    @field_validator("subject")
    @classmethod
    def sanitize_subject(cls, v: str) -> str:
        if isinstance(v, str):
            v = re.sub(r"[\r\n]+", " ", v).strip()
        return v


class BroadcastPreviewResponse(BaseModel):
    subject: str = Field(..., description="Interpolated subject rendered with sample data")
    body_text: str = Field(..., description="Interpolated body rendered in plain-text template")
    body_html: str = Field(..., description="Interpolated body rendered in HTML responsive template")
    sample_order_number: Optional[str] = Field(None, description="Sample order number used for preview")
    sample_exhibitor_name: Optional[str] = Field(None, description="Sample exhibitor name used for preview")
    sample_recipient_email: Optional[str] = Field(None, description="Sample recipient email used for preview")
    sample_spots: Optional[str] = Field(None, description="Sample spot labels used for preview")
    total_eligible_recipients: int = Field(..., description="Total confirmed orders with valid email eligible for broadcast")


class BroadcastSendRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=500, description="Email subject with dynamic tags")
    body: str = Field(..., min_length=1, description="Email body content with dynamic tags")
    target_audience: str = Field("all_confirmed", description="'all_confirmed' or 'selected'")
    selected_order_ids: Optional[List[uuid.UUID]] = Field(None, description="List of specific order UUIDs if target_audience is 'selected'")
    is_test: bool = Field(False, description="Whether this is a single test send to the organizer or test email")
    test_recipient: Optional[str] = Field(None, description="Recipient email address when is_test=True")

    @field_validator("subject")
    @classmethod
    def sanitize_subject(cls, v: str) -> str:
        if isinstance(v, str):
            v = re.sub(r"[\r\n]+", " ", v).strip()
        return v


class BroadcastSendResponse(BaseModel):
    status: str = Field(..., description="'enqueued', 'completed', or 'simulated'")
    event_id: uuid.UUID
    event_title: str
    total_targeted: int
    recipients_without_email: int = 0
    is_test: bool = False
    test_recipient: Optional[str] = None
    message: str

