"""Factory to instantiate the configured Notification Provider."""

from app.core.config import settings
from app.core.constants import NotificationProviderType
from app.core.logging import logger
from app.integrations.notifications.base import BaseNotificationProvider
from app.integrations.notifications.mock_notification import MockNotificationProvider
from app.integrations.notifications.slack_provider import SlackNotificationProvider

_singleton_mock_notify = MockNotificationProvider()


def get_notification_provider() -> BaseNotificationProvider:
    """Return configured notification provider."""
    provider_type = settings.NOTIFICATION_PROVIDER

    if provider_type == NotificationProviderType.SLACK:
        logger.info("Using Slack Notification Provider")
        return SlackNotificationProvider()
    else:
        logger.info("Using Mock Notification Provider")
        return _singleton_mock_notify
