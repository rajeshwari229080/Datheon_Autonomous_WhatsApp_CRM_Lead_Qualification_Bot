"""Generic Webhook CRM Adapter for custom integrations (HubSpot, Salesforce, Zapier)."""

import httpx
from app.core.config import settings
from app.core.constants import CRMSyncStatus
from app.core.logging import logger
from app.integrations.crm.base import BaseCRMProvider
from app.schemas.crm import CRMLeadPayload, CRMSyncResult


class WebhookCRMProvider(BaseCRMProvider):
    """Sends JSON webhook payloads to an external endpoint."""

    def __init__(self, webhook_url: str = settings.CRM_WEBHOOK_URL or ""):
        self.webhook_url = webhook_url

    async def sync_lead(self, payload: CRMLeadPayload) -> CRMSyncResult:
        if not self.webhook_url:
            logger.warning("CRM webhook URL not configured.")
            return CRMSyncResult(
                success=False,
                status=CRMSyncStatus.FAILED,
                error_message="Webhook URL not configured",
            )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(self.webhook_url, json=payload.model_dump())
                res.raise_for_status()
                return CRMSyncResult(
                    success=True,
                    status=CRMSyncStatus.SYNCED,
                    crm_record_id=f"hook_{payload.wa_id}",
                )
        except Exception as exc:
            logger.error(f"CRM webhook sync failed: {exc}")
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
