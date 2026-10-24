"""Database model for demonstration calendar bookings."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.constants import BookingStatus, CalendarProviderType, CRMSyncStatus
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Booking(Base):
    """Calendar booking record for a qualified lead demo."""

    __tablename__ = "bookings"

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[CalendarProviderType] = mapped_column(
        Enum(CalendarProviderType),
        default=CalendarProviderType.MOCK,
        nullable=False,
    )
    event_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    meeting_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus),
        default=BookingStatus.PENDING_CONFIRMATION,
        nullable=False,
        index=True,
    )

    # 2-Phase Confirmation Token
    confirmation_token: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )

    # CRM Synchronization State
    crm_sync_status: Mapped[CRMSyncStatus] = mapped_column(
        Enum(CRMSyncStatus),
        default=CRMSyncStatus.PENDING,
        nullable=False,
        index=True,
    )
    crm_record_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    crm_sync_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_info: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationship
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="bookings",
    )
