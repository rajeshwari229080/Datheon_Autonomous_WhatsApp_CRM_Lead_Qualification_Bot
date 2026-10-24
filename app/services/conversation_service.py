"""High-level orchestration service for WhatsApp conversation processing."""

import uuid
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.constants import ConversationStage, MessageStatus
from app.core.logging import logger
from app.db.repositories.conversation_repository import ConversationRepository
from app.db.repositories.message_repository import MessageRepository
from app.models.conversation import Conversation
from app.schemas.whatsapp import WhatsAppContact, WhatsAppMessage
from app.services.state_machine import ConversationStateMachine


class ConversationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.conv_repo = ConversationRepository(session)
        self.msg_repo = MessageRepository(session)

    async def handle_status_update(
        self,
        provider_message_id: str,
        status_name: str,
    ) -> bool:
        """Process delivery, read, or failure receipts without triggering new bot messages."""
        status_map = {
            "sent": MessageStatus.SENT,
            "delivered": MessageStatus.DELIVERED,
            "read": MessageStatus.READ,
            "failed": MessageStatus.FAILED,
        }
        new_status = status_map.get(status_name.lower())
        if not new_status:
            return False

        updated = await self.msg_repo.update_status_by_provider_id(
            provider_message_id=provider_message_id,
            new_status=new_status,
        )
        logger.info(
            f"Message status updated: {provider_message_id} -> {new_status.value} (found={updated})"
        )
        return updated

    async def process_inbound_message(
        self,
        contact: WhatsAppContact,
        message: WhatsAppMessage,
        raw_payload: Dict[str, Any],
    ) -> tuple[Conversation, bool, Optional[str]]:
        """Ingests an inbound WhatsApp message idempotently.

        Returns: (Conversation, is_duplicate: bool, bot_reply_text: Optional[str])
        """
        # 1. Idempotency Check
        if await self.msg_repo.is_message_processed(message.id):
            logger.info(
                f"Idempotent skip: Message {message.id} already processed.",
                extra={"provider_message_id": message.id, "wa_id": contact.wa_id},
            )
            conv = await self.conv_repo.get_by_wa_id(contact.wa_id)
            return conv, True, None

        # 2. Retrieve or create persistent conversation
        customer_name = contact.profile.name if contact.profile else "Valued Customer"
        conv, is_new = await self.conv_repo.get_or_create(
            wa_id=contact.wa_id,
            customer_name=customer_name,
        )

        # 3. Persist inbound message
        content = message.get_text_content()
        await self.msg_repo.save_inbound_message(
            conversation_id=conv.id,
            provider_message_id=message.id,
            content=content,
            raw_payload=raw_payload,
            message_type=message.type,
        )

        # 4. Check if autonomous actions are disabled (e.g. conversation in HUMAN_HANDOFF)
        if not conv.is_autonomous_active or conv.stage == ConversationStage.HUMAN_HANDOFF:
            logger.info(
                f"Autonomous processing skipped: conversation {conv.id} is in HUMAN_HANDOFF.",
                extra={"conversation_id": conv.id},
            )
            return conv, False, None

        # 5. Advance stage if NEW
        if is_new or conv.stage == ConversationStage.NEW:
            ConversationStateMachine.validate_transition(
                conv.stage, ConversationStage.GREETING
            )
            await self.conv_repo.update_stage(conv.id, ConversationStage.GREETING)
            conv.stage = ConversationStage.GREETING

        return conv, False, None
