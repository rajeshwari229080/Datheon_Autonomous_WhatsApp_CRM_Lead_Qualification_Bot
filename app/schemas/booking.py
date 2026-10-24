"""Pydantic schemas for calendar availability and demonstration bookings."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from app.core.constants import BookingStatus


class CalendarSlot(BaseModel):
    """An individual available demonstration time slot."""

    slot_id: str
    start_time: datetime
    end_time: datetime
    display_text: str


class AvailabilityResponse(BaseModel):
    """List of available time slots returned to customer."""

    slots: List[CalendarSlot]
    timezone: str = "UTC"


class BookingConfirmationRequest(BaseModel):
    """Customer selection of a specific slot option."""

    selected_slot_id: str
    confirmation_token: str
    customer_notes: Optional[str] = None


class BookingOutcome(BaseModel):
    """Final result of confirmed calendar booking."""

    booking_id: str
    event_id: str
    meeting_url: Optional[str] = None
    start_time: datetime
    end_time: datetime
    timezone: str = "UTC"
    status: BookingStatus = BookingStatus.CONFIRMED
    confirmation_message: str
