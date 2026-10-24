"""Audit logging model for sensitive operations and state changes."""

from typing import Any, Dict, Optional
from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class AuditLog(Base):
    """Immutable log of state changes, qualification decisions, and human interventions."""

    __tablename__ = "audit_logs"

    entity_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    changes: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
