"""Unit tests for multi-signal customer frustration and human escalation engine."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ConversationStage
from app.models.conversation import Conversation
from app.models.escalation import EscalationEvent
from app.services.escalation_service import EscalationService


@pytest.mark.asyncio
async def test_frustration_detection_keywords():
    """Signals accurately identify anger and human requests."""
    service = EscalationService(session=None)

    escalate_human, reason, _ = service.detect_signals("Please let me speak with a representative")
    assert escalate_human is True
    assert reason == "HUMAN_REQUEST"

    escalate_anger, reason_anger, _ = service.detect_signals("This is a complete scam and waste of time!")
    assert escalate_anger is True
    assert reason_anger == "FRUSTRATION_KEYWORD"

    no_escalate, _, _ = service.detect_signals("I want to know your pricing for 20 users.")
    assert no_escalate is False


@pytest.mark.asyncio
async def test_human_request_triggers_escalation_and_halts_autonomous_replies(db_session: AsyncSession):
    """Triggering escalation sets autonomous_active to False and transitions stage to HUMAN_HANDOFF."""
    conv = Conversation(wa_id="15557778899", stage=ConversationStage.QUALIFICATION, is_autonomous_active=True)
    db_session.add(conv)
    await db_session.commit()

    service = EscalationService(session=db_session)
    statement = "I am tired of this bot. Get me a human right now!"
    escalation, handoff_msg = await service.trigger_escalation(
        conversation_id=conv.id,
        wa_id=conv.wa_id,
        trigger_reason="HUMAN_REQUEST",
        customer_statement=statement,
    )

    assert escalation is not None
    assert escalation.trigger_reason == "HUMAN_REQUEST"
    assert "human support team" in handoff_msg

    # Verify conversation state is halted
    await db_session.refresh(conv)
    assert conv.is_autonomous_active is False
    assert conv.stage == ConversationStage.HUMAN_HANDOFF


@pytest.mark.asyncio
async def test_resolve_escalation_and_resume_automation(client: AsyncClient, db_session: AsyncSession):
    """Human agent resolves escalation through admin API and can optionally resume automation."""
    conv = Conversation(wa_id="15559990011", stage=ConversationStage.HUMAN_HANDOFF, is_autonomous_active=False)
    db_session.add(conv)
    await db_session.flush()

    event = EscalationEvent(
        conversation_id=conv.id,
        trigger_reason="HUMAN_REQUEST",
        customer_statement="I need help",
        is_resolved=False,
    )
    db_session.add(event)
    await db_session.commit()

    # Call resolution endpoint
    payload = {
        "agent_name": "Sarah Connor",
        "resolution_notes": "Assisted customer on phone, resolved pricing inquiry.",
        "resume_automation": True,
    }
    res = await client.post(f"/api/v1/escalations/{conv.id}/resolve", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "resolved"

    await db_session.refresh(conv)
    assert conv.is_autonomous_active is True
    assert conv.stage == ConversationStage.QUALIFICATION

    await db_session.refresh(event)
    assert event.is_resolved is True
    assert event.resolved_by == "Sarah Connor"
