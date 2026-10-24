"""Abstract Base Class for Human Agent Notification Providers."""

from abc import ABC, abstractmethod
from app.models.escalation import EscalationEvent


class BaseNotificationProvider(ABC):
    """Abstract interface for alerting human support and sales engineering teams."""

    @abstractmethod
    async def send_escalation_alert(
        self,
        event: EscalationEvent,
        customer_name: str,
        wa_id: str,
    ) -> bool:
        """Dispatches an urgent escalation notification to human staff."""
        pass
