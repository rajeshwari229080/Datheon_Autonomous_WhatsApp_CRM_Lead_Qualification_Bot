"""Deterministic Mock Calendar Provider for testing and offline development."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from app.core.config import settings
from app.core.constants import BookingStatus
from app.integrations.calendar.base import BaseCalendarProvider, SlotUnavailableError
from app.schemas.booking import BookingOutcome, CalendarSlot


class MockCalendarProvider(BaseCalendarProvider):
    """Generates valid demo slots within business hours and simulates real booking flows."""

    def __init__(self):
        # In-memory tracking of booked slots to simulate collisions/race conditions
        self.booked_slots: set[str] = set()

    async def get_available_slots(self, days_ahead: int = 3) -> List[CalendarSlot]:
        """Returns 3 deterministic valid slots for tomorrow within configured business hours."""
        now = datetime.now(timezone.utc)
        tomorrow = now.date() + timedelta(days=1)

        slots = []
        # Generate 3 slots: 10:00, 14:00, 16:00
        hour_offsets = [10, 14, 16]
        for idx, hour in enumerate(hour_offsets):
            start = datetime(
                year=tomorrow.year,
                month=tomorrow.month,
                day=tomorrow.day,
                hour=hour,
                minute=0,
                tzinfo=timezone.utc,
            )
            end = start + timedelta(minutes=settings.MEETING_DURATION_MINUTES)
            slot_id = f"slot_{start.strftime('%Y%m%d_%H%M')}"

            if slot_id not in self.booked_slots:
                display = f"Option {idx + 1}: {start.strftime('%A, %b %d at %I:%M %p UTC')}"
                slots.append(
                    CalendarSlot(
                        slot_id=slot_id,
                        start_time=start,
                        end_time=end,
                        display_text=display,
                    )
                )
        return slots

    async def create_booking(
        self,
        slot_id: str,
        customer_name: str,
        customer_phone: str,
        notes: Optional[str] = None,
    ) -> BookingOutcome:
        """Confirms demo booking if slot is free; raises SlotUnavailableError on collision."""
        if slot_id in self.booked_slots:
            raise SlotUnavailableError(f"Requested slot {slot_id} is no longer available.")

        self.booked_slots.add(slot_id)

        # Parse start from slot_id: slot_YYYYMMDD_HHMM
        try:
            date_part = slot_id.replace("slot_", "")
            start = datetime.strptime(date_part, "%Y%m%d_%H%M").replace(tzinfo=timezone.utc)
        except Exception:
            start = datetime.now(timezone.utc) + timedelta(days=1, hours=2)

        end = start + timedelta(minutes=settings.MEETING_DURATION_MINUTES)
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        meeting_url = f"https://meet.google.com/dth-{uuid.uuid4().hex[:3]}-{uuid.uuid4().hex[:3]}"

        return BookingOutcome(
            booking_id=f"bk_{uuid.uuid4().hex[:8]}",
            event_id=event_id,
            meeting_url=meeting_url,
            start_time=start,
            end_time=end,
            timezone="UTC",
            status=BookingStatus.CONFIRMED,
            confirmation_message=(
                f"Your demonstration is confirmed for {start.strftime('%A, %b %d at %I:%M %p UTC')}. "
                f"Meeting link: {meeting_url}"
            ),
        )

    async def cancel_booking(self, event_id: str) -> bool:
        """Simulates cancellation."""
        return True
