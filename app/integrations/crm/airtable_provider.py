"""Airtable REST API integration adapter."""

import httpx
from app.core.config import settings
from app.core.constants import CRMSyncStatus
from app.core.logging import logger
from app.integrations.crm.base import BaseCRMProvider
from app.schemas.crm import CRMLeadPayload, CRMSyncResult


class AirtableCRMProvider(BaseCRMProvider):
    """Integrates with Airtable REST API."""

    def __init__(
        self,
        api_key: str = settings.AIRTABLE_API_KEY or "",
        base_id: str = settings.AIRTABLE_BASE_ID or "",
        table_name: str = settings.AIRTABLE_TABLE_NAME,
    ):
        self.api_key = api_key
        self.base_id = base_id
        self.table_name = table_name

    async def sync_lead(self, payload: CRMLeadPayload) -> CRMSyncResult:
        if not self.api_key or not self.base_id:
            logger.warning("Airtable credentials not set; CRM sync disabled.")
            return CRMSyncResult(
                success=False,
                status=CRMSyncStatus.FAILED,
                error_message="Airtable credentials not configured",
            )

        url = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        fields = {
            "WhatsApp ID": payload.wa_id,
            "Customer Name": payload.name or "N/A",
            "Company": payload.company_name or "N/A",
            "Budget": payload.budget_amount or 0.0,
            "Qualification Status": payload.qualification_status,
            "Urgency": payload.problem_urgency,
            "Calendar Event ID": payload.calendar_event_id or "",
            "Meeting URL": payload.meeting_url or "",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=headers, json={"fields": fields})
                res.raise_for_status()
                data = res.json()
                record_id = data.get("id")
                return CRMSyncResult(
                    success=True,
                    status=CRMSyncStatus.SYNCED,
                    crm_record_id=record_id,
                )
        except Exception as exc:
            logger.error(f"Airtable lead sync failed: {exc}")
            return CRMSyncResult(
                success=False,
                status=CRMSyncStatus.FAILED,
                error_message=str(exc),
            )

    async def update_booking_status(
        self,
        crm_record_id: str,
        booking_status: str,
        event_id: str,
    ) -> bool:
        return True
