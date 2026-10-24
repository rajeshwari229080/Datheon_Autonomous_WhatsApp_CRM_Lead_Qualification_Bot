"""Factory to instantiate the configured CRM provider."""

from app.core.config import settings
from app.core.constants import CRMProviderType
from app.core.logging import logger
from app.integrations.crm.airtable_provider import AirtableCRMProvider
from app.integrations.crm.base import BaseCRMProvider
from app.integrations.crm.mock_crm import MockCRMProvider
from app.integrations.crm.webhook_crm import WebhookCRMProvider

_singleton_mock_crm = MockCRMProvider()


def get_crm_provider() -> BaseCRMProvider:
    """Return instance of configured CRM provider."""
    provider_type = settings.CRM_PROVIDER

    if provider_type == CRMProviderType.AIRTABLE:
        logger.info("Using Airtable CRM Provider")
        return AirtableCRMProvider()
    elif provider_type == CRMProviderType.WEBHOOK:
        logger.info("Using Generic Webhook CRM Provider")
        return WebhookCRMProvider()
    else:
        logger.info("Using Mock CRM Provider")
        return _singleton_mock_crm
