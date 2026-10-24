"""Abstract Base Class for CRM Providers (Airtable, Webhook, Mock)."""

from abc import ABC, abstractmethod
from app.schemas.crm import CRMLeadPayload, CRMSyncResult


class BaseCRMProvider(ABC):
    """Abstract interface for synchronizing qualified leads and bookings with CRM systems."""

    @abstractmethod
    async def sync_lead(self, payload: CRMLeadPayload) -> CRMSyncResult:
        """Create or update a lead record in the CRM."""
        pass

    @abstractmethod
    async def update_booking_status(
        self,
        crm_record_id: str,
        booking_status: str,
        event_id: str,
    ) -> bool:
        """Update an existing CRM record with calendar booking details."""
        pass
