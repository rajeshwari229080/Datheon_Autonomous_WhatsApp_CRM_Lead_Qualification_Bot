"""Multi-signal customer frustration detection and autonomous human escalation engine."""

from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.constants import ConversationStage
from app.core.logging import logger
from app.db.repositories.conversation_repository import ConversationRepository
from app.db.repositories.message_repository import MessageRepository
from app.models.escalation import EscalationEvent
from app.services.state_machine import ConversationStateMachine


class EscalationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.conv_repo = ConversationRepository(session)
        self.msg_repo = MessageRepository(session)

    # Signal 1 & 2 Keyword Dictionaries
    HUMAN_KEYWORDS = [
        "human",
        "agent",
        "representative",
        "person",
        "operator",
        "advisor",
        "specialist",
        "speak to someone",
        "talk to someone",
        "real person",
    ]

    FRUSTRATION_KEYWORDS = [
        "angry",
        "annoyed",
        "frustrated",
        "terrible",
        "horrible",
        "awful",
        "stupid bot",
        "useless",
        "waste of time",
        "scam",
        "fraud",
        "lawyer",
        "sue you",
        "disgusted",
        "ridiculous",
    ]

    def detect_signals(self, text: str) -> Tuple[bool, str, float]:
        """Detects escalation signals.

        Returns: (should_escalate: bool, trigger_reason: str, sentiment_score: float)
        """
        clean_text = text.lower().strip()

        # Check explicit human request
        if any(k in clean_text for k in self.HUMAN_KEYWORDS):
            return True, "HUMAN_REQUEST", 0.0

        # Check frustration / hostility
        if any(k in clean_text for k in self.FRUSTRATION_KEYWORDS):
            return True, "FRUSTRATION_KEYWORD", -0.9

        return False, "NONE", 0.0

    async def check_loop_or_repetition(self, conversation_id: str) -> bool:
        """Signal 3: Detects if customer is stuck in an unhelpful loop (>4 messages without progress)."""
        messages = await self.msg_repo.get_recent_history(conversation_id, limit=6)
        if len(messages) >= 6:
            # Check if customer sent repeated messages
            inbound_texts = [m.content.lower().strip() for m in messages if m.direction.value == "INBOUND" and m.content]
            if len(inbound_texts) >= 3 and len(set(inbound_texts)) <= 2:
                logger.warning(
                    f"Repetitive loop detected in conversation {conversation_id}",
                    extra={"conversation_id": conversation_id},
                )
                return True
        return False

    async def trigger_escalation(
        self,
        conversation_id: str,
        wa_id: str,
        trigger_reason: str,
        customer_statement: str,
        sentiment_score: float = -1.0,
    ) -> Tuple[EscalationEvent, str]:
        """Halts autonomous replies immediately, records escalation event, and prepares human handoff."""
        conv = await self.conv_repo.get_by_id(conversation_id)
        if not conv:
            raise ValueError(f"Conversation {conversation_id} not found.")

        logger.info(
            f"Triggering escalation for conversation {conversation_id}: {trigger_reason}",
            extra={"conversation_id": conversation_id, "trigger_reason": trigger_reason},
        )

        # 1. Immediately halt autonomous bot actions
        await self.conv_repo.set_autonomous_state(conversation_id, is_active=False)

        # 2. Transition state machine to HUMAN_HANDOFF
        ConversationStateMachine.validate_transition(conv.stage, ConversationStage.HUMAN_HANDOFF)
        await self.conv_repo.update_stage(conversation_id, ConversationStage.HUMAN_HANDOFF)

        # 3. Compile transcript summary dossier
        history = await self.msg_repo.get_recent_history(conversation_id, limit=10)
        dossier_lines = [
            f"[{m.created_at.strftime('%H:%M:%S')}] {m.direction.value}: {m.content}"
            for m in history
        ]
        summary_dossier = "\n".join(dossier_lines)

        # 4. Create persistent EscalationEvent
        escalation = EscalationEvent(
            conversation_id=conversation_id,
            trigger_reason=trigger_reason,
            sentiment_score=sentiment_score,
            customer_statement=customer_statement,
            summary_dossier=summary_dossier,
            notification_dispatched=False,
            notification_channel=settings.NOTIFICATION_PROVIDER.value,
        )
        self.session.add(escalation)
        await self.session.flush()

        # 5. Customer polite handoff response
        handoff_message = (
            f"I have transferred our conversation to our human support team. A representative will be with you shortly. "
            f"You may also contact us directly at {settings.FALLBACK_HUMAN_PHONE}."
        )

        return escalation, handoff_message
