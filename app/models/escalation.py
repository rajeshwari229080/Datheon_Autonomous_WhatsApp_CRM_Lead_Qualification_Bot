"""Database models for human escalation events and dead-letter queue storage."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class EscalationEvent(Base):
    """Tracks human handoff incidents and escalation resolution lifecycle."""

    __tablename__ = "escalation_events"

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trigger_reason: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="HUMAN_REQUEST | FRUSTRATION_KEYWORD | SENTIMENT_LOOP | SYSTEM_ERROR | OUT_OF_SCOPE",
    )
    sentiment_score: Mapped[float] = mapped_column(Float, default=-1.0, nullable=False)
    customer_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_dossier: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notification_dispatched: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notification_channel: Mapped[str] = mapped_column(String(32), default="slack", nullable=False)

    # Resolution tracking
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="escalations",
    )


class DeadLetterEvent(Base):
    """Stores unprocessable, failed, or poisoned webhook messages for manual analysis."""

    __tablename__ = "dead_letter_events"

    provider_message_id: Mapped[Optional[str]] = mapped_column(
        String(128), index=True, nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64), default="whatsapp_webhook", nullable=False)
    raw_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
