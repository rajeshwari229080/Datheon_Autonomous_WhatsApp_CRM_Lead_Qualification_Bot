"""Deterministic Mock Notification Provider for testing."""

from typing import Dict, List
from app.core.logging import logger
from app.integrations.notifications.base import BaseNotificationProvider
from app.models.escalation import EscalationEvent


class MockNotificationProvider(BaseNotificationProvider):
    """In-memory notification recorder for unit and integration testing."""

    def __init__(self):
        self.dispatched_alerts: List[Dict] = []

    async def send_escalation_alert(
        self,
        event: EscalationEvent,
        customer_name: str,
        wa_id: str,
    ) -> bool:
        alert = {
            "conversation_id": event.conversation_id,
            "trigger_reason": event.trigger_reason,
            "customer_name": customer_name,
            "wa_id": wa_id,
            "statement": event.customer_statement,
        }
        self.dispatched_alerts.append(alert)
        logger.info(
            f"MockNotificationProvider: Dispatched alert for {customer_name} ({wa_id}): {event.trigger_reason}",
            extra=alert,
        )
        return True
