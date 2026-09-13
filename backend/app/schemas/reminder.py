import uuid
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class ReminderStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    event_slug: str
    event_title: str
    start_date: str
    days_until_event: float
    j7_eligible: bool
    j7_sent_count: int
    j2_eligible: bool
    j2_sent_count: int
    total_confirmed_orders: int
    total_confirmed_with_email: int


class ReminderTriggerAction(BaseModel):
    reminder_type: Optional[str] = None  # "j7", "j2", or None for automatic window-based
    force: bool = False  # If True, bypasses existing log checks (for manual test sends)


class ReminderTriggerResponse(BaseModel):
    event_id: uuid.UUID
    event_title: str
    reminder_type: str
    orders_processed: int
    reminders_sent: int
    reminders_skipped: int
    orders_without_email: int
    errors: List[str] = []


class SystemRemindersRunResponse(BaseModel):
    events_evaluated: int
    total_reminders_sent: int
    total_reminders_skipped: int
    reports: List[ReminderTriggerResponse] = []

