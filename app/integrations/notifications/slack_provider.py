"""Slack incoming webhook provider for real-time human agent alerts."""

from typing import Optional
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.integrations.notifications.base import BaseNotificationProvider
from app.models.escalation import EscalationEvent


class SlackNotificationProvider(BaseNotificationProvider):
    """Sends Block Kit formatted escalation cards to a configured Slack channel."""

    def __init__(self, webhook_url: Optional[str] = settings.SLACK_WEBHOOK_URL):
        self.webhook_url = webhook_url

    async def send_escalation_alert(
        self,
        event: EscalationEvent,
        customer_name: str,
        wa_id: str,
    ) -> bool:
        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured; skipping dispatch.")
            return False

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 WhatsApp Customer Escalation Alert",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Customer:*\n{customer_name}"},
                    {"type": "mrkdwn", "text": f"*WhatsApp ID:*\n+{wa_id}"},
                    {"type": "mrkdwn", "text": f"*Trigger Reason:*\n`{event.trigger_reason}`"},
                    {"type": "mrkdwn", "text": f"*Conversation ID:*\n`{event.conversation_id}`"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Latest Statement:*\n> _{event.customer_statement or 'N/A'}_",
                },
            },
        ]

        payload = {
            "text": f"🚨 Urgent WhatsApp escalation for {customer_name}: {event.trigger_reason}",
            "blocks": blocks,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(self.webhook_url, json=payload)
                res.raise_for_status()
                return True
        except Exception as exc:
            logger.error(f"Failed to dispatch Slack escalation alert: {exc}")
            return False
