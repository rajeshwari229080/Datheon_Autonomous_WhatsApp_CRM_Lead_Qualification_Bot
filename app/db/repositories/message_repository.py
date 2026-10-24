"""Repository for atomic Message database operations and idempotency checks."""

from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.constants import MessageDirection, MessageStatus
from app.core.logging import logger
from app.models.conversation import Message


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_message_processed(self, provider_message_id: str) -> bool:
        """Check whether a message with the given provider message ID has already been recorded."""
        stmt = select(Message.id).where(Message.provider_message_id == provider_message_id)
        result = await self.session.execute(stmt)
        return result.scalars().first() is not None

    async def save_inbound_message(
        self,
        conversation_id: str,
        provider_message_id: str,
        content: str,
        raw_payload: Dict[str, Any],
        message_type: str = "text",
    ) -> Message:
        """Record an inbound message from WhatsApp with idempotency check."""
        msg = Message(
            conversation_id=conversation_id,
            provider_message_id=provider_message_id,
            direction=MessageDirection.INBOUND,
            status=MessageStatus.RECEIVED,
            message_type=message_type,
            content=content,
            raw_payload=raw_payload,
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def save_outbound_message(
        self,
        conversation_id: str,
        provider_message_id: str,
        content: str,
        status: MessageStatus = MessageStatus.SENT,
        message_type: str = "text",
    ) -> Message:
        """Record an outbound message sent to customer."""
        msg = Message(
            conversation_id=conversation_id,
            provider_message_id=provider_message_id,
            direction=MessageDirection.OUTBOUND,
            status=status,
            message_type=message_type,
            content=content,
            raw_payload={},
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def update_status_by_provider_id(
        self,
        provider_message_id: str,
        new_status: MessageStatus,
    ) -> bool:
        """Update delivery/read status of an outbound message."""
        stmt = (
            update(Message)
            .where(Message.provider_message_id == provider_message_id)
            .values(status=new_status)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def get_recent_history(
        self,
        conversation_id: str,
        limit: int = 15,
    ) -> List[Message]:
        """Fetch chronological message history for prompt context building."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()  # Return in chronological order
        return messages
