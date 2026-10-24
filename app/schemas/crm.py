"""Pydantic schemas for CRM lead record synchronization and reconciliation."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from app.core.constants import CRMSyncStatus


class CRMLeadPayload(BaseModel):
    """Normalized lead record to be synced into Airtable or CRM provider."""

    wa_id: str
    name: Optional[str] = None
    company_name: Optional[str] = None
    budget_amount: Optional[float] = None
    currency: str = "USD"
    employee_count: Optional[int] = None
    problem_urgency: str = "UNKNOWN"
    business_problem: Optional[str] = None
    qualification_status: str = "QUALIFIED"
    calendar_event_id: Optional[str] = None
    meeting_url: Optional[str] = None
    booking_status: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CRMSyncResult(BaseModel):
    """Result of CRM synchronization operation."""

    success: bool
    status: CRMSyncStatus
    crm_record_id: Optional[str] = None
    error_message: Optional[str] = None
