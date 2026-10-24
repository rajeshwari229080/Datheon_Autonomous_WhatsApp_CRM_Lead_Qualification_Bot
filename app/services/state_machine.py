"""Conversation State Machine with transition guards and lifecycle validation."""

from typing import Dict, Set
from app.core.constants import ConversationStage
from app.core.logging import logger


class InvalidStateTransitionError(Exception):
    """Raised when an illegal conversation stage transition is attempted."""

    def __init__(self, from_stage: ConversationStage, to_stage: ConversationStage):
        self.from_stage = from_stage
        self.to_stage = to_stage
        super().__init__(
            f"Illegal conversation transition from '{from_stage.value}' to '{to_stage.value}'"
        )


class ConversationStateMachine:
    """Deterministic finite state machine governing conversation stages."""

    # Explicit legal transitions
    TRANSITIONS: Dict[ConversationStage, Set[ConversationStage]] = {
        ConversationStage.NEW: {
            ConversationStage.GREETING,
            ConversationStage.QUALIFICATION,
            ConversationStage.HUMAN_HANDOFF,
            ConversationStage.CLOSED,
        },
        ConversationStage.GREETING: {
            ConversationStage.QUALIFICATION,
            ConversationStage.HUMAN_HANDOFF,
            ConversationStage.CLOSED,
        },
        ConversationStage.QUALIFICATION: {
            ConversationStage.QUALIFICATION,  # Self-transition for multi-turn qualification
            ConversationStage.QUALIFIED,
            ConversationStage.NOT_QUALIFIED,
            ConversationStage.HUMAN_HANDOFF,
            ConversationStage.CLOSED,
        },
        ConversationStage.QUALIFIED: {
            ConversationStage.BOOKING,
            ConversationStage.BOOKED,
            ConversationStage.HUMAN_HANDOFF,
            ConversationStage.CLOSED,
        },
        ConversationStage.NOT_QUALIFIED: {
            ConversationStage.CLOSED,
            ConversationStage.HUMAN_HANDOFF,
        },
        ConversationStage.BOOKING: {
            ConversationStage.BOOKING,  # Multi-turn slot selection
            ConversationStage.BOOKED,
            ConversationStage.HUMAN_HANDOFF,
            ConversationStage.CLOSED,
        },
        ConversationStage.BOOKED: {
            ConversationStage.CLOSED,
            ConversationStage.HUMAN_HANDOFF,
        },
        ConversationStage.HUMAN_HANDOFF: {
            ConversationStage.CLOSED,
            ConversationStage.GREETING,
            ConversationStage.QUALIFICATION,
        },
        ConversationStage.CLOSED: {
            ConversationStage.NEW,
            ConversationStage.GREETING,
        },
    }

    @classmethod
    def can_transition(
        cls,
        from_stage: ConversationStage,
        to_stage: ConversationStage,
    ) -> bool:
        """Check if transition from one stage to another is legal."""
        allowed = cls.TRANSITIONS.get(from_stage, set())
        return to_stage in allowed

    @classmethod
    def validate_transition(
        cls,
        from_stage: ConversationStage,
        to_stage: ConversationStage,
    ) -> None:
        """Validate transition, raising InvalidStateTransitionError if illegal."""
        if not cls.can_transition(from_stage, to_stage):
            logger.error(
                f"State transition rejected: {from_stage.value} -> {to_stage.value}"
            )
            raise InvalidStateTransitionError(from_stage, to_stage)
        logger.info(
            f"State transitioned: {from_stage.value} -> {to_stage.value}"
        )
