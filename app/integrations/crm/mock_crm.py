"""Deterministic Mock CRM Provider supporting failure simulation for reconciliation testing."""

import uuid
from typing import Dict
from app.core.constants import CRMSyncStatus
from app.core.logging import logger
from app.integrations.crm.base import BaseCRMProvider
from app.schemas.crm import CRMLeadPayload, CRMSyncResult


class MockCRMProvider(BaseCRMProvider):
    """Stores CRM records in memory and can simulate temporary outage for reconciliation tests."""

    def __init__(self):
        self.records: Dict[str, Dict] = {}
        self.simulate_failure: bool = False

    async def sync_lead(self, payload: CRMLeadPayload) -> CRMSyncResult:
        if self.simulate_failure:
            logger.warning("MockCRMProvider: Simulating 503 CRM service unavailable outage.")
            return CRMSyncResult(
                success=False,
                status=CRMSyncStatus.FAILED,
                error_message="HTTP 503: CRM Service Unavailable",
            )

        record_id = f"crm_rec_{uuid.uuid4().hex[:10]}"
        self.records[record_id] = payload.model_dump()
        logger.info(
            f"MockCRMProvider: Synced lead wa_id={payload.wa_id} into record {record_id}",
            extra={"crm_record_id": record_id, "wa_id": payload.wa_id},
        )
        return CRMSyncResult(
            success=True,
            status=CRMSyncStatus.SYNCED,
            crm_record_id=record_id,
        )

    async def update_booking_status(
        self,
        crm_record_id: str,
        booking_status: str,
        event_id: str,
    ) -> bool:
        if crm_record_id in self.records:
            self.records[crm_record_id]["booking_status"] = booking_status
            self.records[crm_record_id]["calendar_event_id"] = event_id
            return True
        return False
