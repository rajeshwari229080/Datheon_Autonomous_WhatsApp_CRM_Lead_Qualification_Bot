"""Pydantic schemas for LLM structured extraction and lead qualification."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator
from app.core.constants import DecisionMakerStatus, QualificationStatus, UrgencyLevel


class BudgetInfo(BaseModel):
    amount: Optional[float] = None
    currency: str = "USD"
    status: Literal["EXPLICIT", "INFERRED", "UNKNOWN"] = "UNKNOWN"


class CompanySizeInfo(BaseModel):
    employee_count: Optional[int] = None
    range: Optional[str] = None
    status: Literal["EXPLICIT", "INFERRED", "UNKNOWN"] = "UNKNOWN"


class QualificationExtractionResult(BaseModel):
    """Strict schema for LLM structured extraction output."""

    budget: BudgetInfo = Field(default_factory=BudgetInfo)
    company_size: CompanySizeInfo = Field(default_factory=CompanySizeInfo)
    problem_urgency: UrgencyLevel = UrgencyLevel.UNKNOWN
    business_problem: Optional[str] = None
    decision_maker: DecisionMakerStatus = DecisionMakerStatus.UNKNOWN
    purchase_timeline: Optional[str] = None
    qualification_status: QualificationStatus = QualificationStatus.NEEDS_MORE_INFORMATION
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_fields: List[str] = Field(default_factory=list)
    next_action: str = Field(default="Ask missing qualification details")
    follow_up_question: Optional[str] = None

    # Safety & escalation signals
    detected_frustration: bool = False
    requested_human: bool = False

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))
