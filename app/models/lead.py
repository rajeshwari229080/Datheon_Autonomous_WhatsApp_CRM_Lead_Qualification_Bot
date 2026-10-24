"""Database model for qualified business leads."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import JSON, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.constants import DecisionMakerStatus, QualificationStatus, UrgencyLevel
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Lead(Base):
    """Business lead extracted and qualified during conversation."""

    __tablename__ = "leads"

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    wa_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_size: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    employee_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Financial & Urgency
    budget_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    problem_urgency: Mapped[UrgencyLevel] = mapped_column(
        Enum(UrgencyLevel),
        default=UrgencyLevel.UNKNOWN,
        nullable=False,
    )
    business_problem: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_maker: Mapped[DecisionMakerStatus] = mapped_column(
        Enum(DecisionMakerStatus),
        default=DecisionMakerStatus.UNKNOWN,
        nullable=False,
    )
    purchase_timeline: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Qualification Outcome
    qualification_status: Mapped[QualificationStatus] = mapped_column(
        Enum(QualificationStatus),
        default=QualificationStatus.NEEDS_MORE_INFORMATION,
        nullable=False,
        index=True,
    )
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    missing_fields: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    qualification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extraction_history: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )

    # CRM Synchronization
    crm_lead_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    # Relationship
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="lead",
    )
