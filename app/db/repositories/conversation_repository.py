"""Repository for atomic Conversation database operations."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.constants import ConversationStage
from app.core.logging import logger
from app.models.conversation import Conversation


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_wa_id(self, wa_id: str, load_relationships: bool = False) -> Optional[Conversation]:
        """Fetch conversation by WhatsApp ID."""
        stmt = select(Conversation).where(Conversation.wa_id == wa_id)
        if load_relationships:
            stmt = stmt.options(
                selectinload(Conversation.messages),
                selectinload(Conversation.lead),
                selectinload(Conversation.bookings),
            )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_id(self, conv_id: str, load_relationships: bool = False) -> Optional[Conversation]:
        """Fetch conversation by primary key ID."""
        stmt = select(Conversation).where(Conversation.id == conv_id)
        if load_relationships:
            stmt = stmt.options(
                selectinload(Conversation.messages),
                selectinload(Conversation.lead),
                selectinload(Conversation.bookings),
                selectinload(Conversation.escalations),
            )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_or_create(self, wa_id: str, customer_name: Optional[str] = None) -> tuple[Conversation, bool]:
        """Fetch existing conversation or create new one atomically."""
        conv = await self.get_by_wa_id(wa_id)
        if conv:
            if customer_name and not conv.customer_name:
                conv.customer_name = customer_name
                conv.last_interaction_at = datetime.now(timezone.utc)
                await self.session.flush()
            return conv, False

        conv = Conversation(
            wa_id=wa_id,
            customer_name=customer_name or "Valued Customer",
            stage=ConversationStage.NEW,
            last_interaction_at=datetime.now(timezone.utc),
            context_data={},
            is_autonomous_active=True,
        )
        self.session.add(conv)
        await self.session.flush()
        logger.info(
            f"Created new conversation for wa_id={wa_id}",
            extra={"conversation_id": conv.id, "wa_id": wa_id},
        )
        return conv, True

    async def update_stage(self, conv_id: str, new_stage: ConversationStage) -> None:
        """Update the conversation stage."""
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conv_id)
            .values(
                stage=new_stage,
                last_interaction_at=datetime.now(timezone.utc),
            )
        )
        await self.session.flush()

    async def update_context(self, conv_id: str, key: str, value: Any) -> None:
        """Append or update a key in the JSON context_data."""
        conv = await self.get_by_id(conv_id)
        if conv:
            updated_data = dict(conv.context_data)
            updated_data[key] = value
            conv.context_data = updated_data
            conv.last_interaction_at = datetime.now(timezone.utc)
            await self.session.flush()

    async def set_autonomous_state(self, conv_id: str, is_active: bool) -> None:
        """Toggle autonomous AI replies (e.g. deactivate on escalation)."""
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conv_id)
            .values(
                is_autonomous_active=is_active,
                last_interaction_at=datetime.now(timezone.utc),
            )
        )
        await self.session.flush()
