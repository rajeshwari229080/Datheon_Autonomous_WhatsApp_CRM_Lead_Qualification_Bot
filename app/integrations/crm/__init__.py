"""CRM integrations package."""

from app.integrations.crm.base import BaseCRMProvider
from app.integrations.crm.mock_crm import MockCRMProvider

__all__ = ["BaseCRMProvider", "MockCRMProvider"]
