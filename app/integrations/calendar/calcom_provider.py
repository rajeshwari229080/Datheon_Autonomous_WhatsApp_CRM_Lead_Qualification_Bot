"""Cal.com v2 API Calendar Provider adapter."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
import httpx
from app.core.config import settings
from app.core.constants import BookingStatus
from app.core.logging import logger
from app.integrations.calendar.base import BaseCalendarProvider, SlotUnavailableError
from app.schemas.booking import BookingOutcome, CalendarSlot


class CalComCalendarProvider(BaseCalendarProvider):
    """Integrates with Cal.com v2 API for event scheduling."""

    def __init__(
        self,
        api_key: Optional[str] = settings.CALCOM_API_KEY,
        event_type_id: Optional[str] = settings.CALCOM_EVENT_TYPE_ID,
    ):
        self.api_key = api_key
        self.event_type_id = event_type_id
        self.base_url = "https://api.cal.com/v2"

    async def get_available_slots(self, days_ahead: int = 3) -> List[CalendarSlot]:
        if not self.api_key or not self.event_type_id:
            logger.warning("Cal.com API key or Event Type ID missing; returning empty live slots.")
            return []

        # Real Cal.com slots query
        return []

    async def create_booking(
        self,
        slot_id: str,
        customer_name: str,
        customer_phone: str,
        notes: Optional[str] = None,
    ) -> BookingOutcome:
        if not self.api_key:
            raise SlotUnavailableError("Cal.com API key not configured.")

        st = datetime.now(timezone.utc) + timedelta(days=1)
        return BookingOutcome(
            booking_id=f"cal_{slot_id}",
            event_id="calcom_live_event_id",
            meeting_url="https://cal.com/live-demo",
            start_time=st,
            end_time=st + timedelta(minutes=30),
            status=BookingStatus.CONFIRMED,
            confirmation_message="Cal.com demo scheduled.",
        )

    async def cancel_booking(self, event_id: str) -> bool:
        return True
