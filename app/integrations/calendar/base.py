"""Abstract base class for Calendar Providers (Google Calendar, Cal.com, Mock)."""

from abc import ABC, abstractmethod
from typing import List, Optional
from app.schemas.booking import BookingOutcome, CalendarSlot


class SlotUnavailableError(Exception):
    """Raised when a requested slot is no longer available (race condition)."""
    pass


class BaseCalendarProvider(ABC):
    """Abstract interface for checking availability and scheduling demonstration events."""

    @abstractmethod
    async def get_available_slots(self, days_ahead: int = 3) -> List[CalendarSlot]:
        """Fetch provider-confirmed free slots respecting business hours, duration, and notice."""
        pass

    @abstractmethod
    async def create_booking(
        self,
        slot_id: str,
        customer_name: str,
        customer_phone: str,
        notes: Optional[str] = None,
    ) -> BookingOutcome:
        """Book a confirmed calendar meeting for the selected slot."""
        pass

    @abstractmethod
    async def cancel_booking(self, event_id: str) -> bool:
        """Cancel an existing calendar appointment."""
        pass
