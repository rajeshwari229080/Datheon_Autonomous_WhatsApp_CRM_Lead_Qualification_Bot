"""Database models for Conversation state and Message history."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.constants import ConversationStage, MessageDirection, MessageStatus
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.booking import Booking
    from app.models.escalation import EscalationEvent
    from app.models.lead import Lead


class Conversation(Base):
    """Tracks an ongoing customer conversation over WhatsApp."""

    __tablename__ = "conversations"

    wa_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stage: Mapped[ConversationStage] = mapped_column(
        Enum(ConversationStage),
        default=ConversationStage.NEW,
        nullable=False,
        index=True,
    )
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    context_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_interaction_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    is_autonomous_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    lead: Mapped[Optional["Lead"]] = relationship(
        "Lead",
        back_populates="conversation",
        uselist=False,
        cascade="all, delete-orphan",
    )
    bookings: Mapped[List["Booking"]] = relationship(
        "Booking",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    escalations: Mapped[List["EscalationEvent"]] = relationship(
        "EscalationEvent",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class Message(Base):
    """Individual inbound or outbound message record with idempotency support."""

    __tablename__ = "messages"

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_message_id: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=False,
        doc="Meta WhatsApp message ID (e.g. wamid.HBg...) for deduplication and idempotency",
    )
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection),
        nullable=False,
    )
    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus),
        default=MessageStatus.RECEIVED,
        nullable=False,
    )
    message_type: Mapped[str] = mapped_column(String(32), default="text", nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationship
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )


Index("idx_message_conv_created", Message.conversation_id, Message.created_at)
