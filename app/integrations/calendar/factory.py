"""Factory to instantiate the configured Calendar Provider."""

from app.core.config import settings
from app.core.constants import CalendarProviderType
from app.core.logging import logger
from app.integrations.calendar.base import BaseCalendarProvider
from app.integrations.calendar.calcom_provider import CalComCalendarProvider
from app.integrations.calendar.google_calendar import GoogleCalendarProvider
from app.integrations.calendar.mock_calendar import MockCalendarProvider

_singleton_mock_calendar: MockCalendarProvider = MockCalendarProvider()


def get_calendar_provider() -> BaseCalendarProvider:
    """Return instance of configured Calendar Provider."""
    provider_type = settings.CALENDAR_PROVIDER

    if provider_type == CalendarProviderType.GOOGLE:
        logger.info("Using Google Calendar Provider")
        return GoogleCalendarProvider()
    elif provider_type == CalendarProviderType.CALCOM:
        logger.info("Using Cal.com Calendar Provider")
        return CalComCalendarProvider()
    else:
        logger.info("Using Mock Calendar Provider")
        return _singleton_mock_calendar
