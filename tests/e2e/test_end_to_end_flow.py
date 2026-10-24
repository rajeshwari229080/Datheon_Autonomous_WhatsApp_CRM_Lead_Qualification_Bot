"""End-to-end integration tests simulating full customer journeys."""

import json
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import BookingStatus, ConversationStage, CRMSyncStatus, QualificationStatus
from app.core.security import generate_hub_signature
from app.models.booking import Booking
from app.models.conversation import Conversation
from app.models.escalation import EscalationEvent
from app.models.lead import Lead
from app.services.booking_service import BookingService
from app.services.escalation_service import EscalationService
from app.services.qualification_service import QualificationService


@pytest.mark.asyncio
async def test_health_and_prometheus_metrics(client: AsyncClient):
    """Health endpoints and Prometheus metrics exposition respond correctly."""
    # Liveness
    live_res = await client.get("/health/live")
    assert live_res.status_code == 200
    assert live_res.json()["status"] == "alive"

    # Readiness
    ready_res = await client.get("/health/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["database"] == "connected"

    # Prometheus Metrics
    metrics_res = await client.get("/metrics")
    assert metrics_res.status_code == 200
    assert "webhooks_received_total" in metrics_res.text
    assert "bookings_confirmed_total" in metrics_res.text


@pytest.mark.asyncio
async def test_complete_qualification_to_booking_e2e(client: AsyncClient, db_session: AsyncSession):
    """End-to-end journey from webhook ingestion to qualification, slot selection, and booking."""
    wa_id = "15559871122"
    customer_name = "Elena Rostova"

    # Step 1: Webhook Inbound Message
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "1001",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "contacts": [{"wa_id": wa_id, "profile": {"name": customer_name}}],
                            "messages": [
                                {
                                    "id": "wamid.E2E_STEP1_MSG",
                                    "from": wa_id,
                                    "timestamp": "1729001000",
                                    "type": "text",
                                    "text": {"body": "Hello, we want to automate lead qualification for our enterprise."},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_hub_signature(raw_body, settings.WHATSAPP_APP_SECRET)

    res = await client.post(
        "/api/v1/whatsapp/webhook",
        content=raw_body,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert res.status_code == 200

    # Verify conversation created and in GREETING stage
    conv_stmt = select(Conversation).where(Conversation.wa_id == wa_id)
    conv_res = await db_session.execute(conv_stmt)
    conv = conv_res.scalars().first()
    assert conv is not None
    assert conv.stage == ConversationStage.GREETING

    # Step 2: Customer provides qualifying details
    qual_service = QualificationService(session=db_session)
    extraction, bot_text = await qual_service.qualify_message(
        conversation_id=conv.id,
        wa_id=wa_id,
        customer_message="I am the founder of an 80 employees firm. Our budget is $15,000 and we need this urgently.",
    )
    assert extraction.qualification_status == QualificationStatus.QUALIFIED
    await db_session.refresh(conv)
    assert conv.stage == ConversationStage.BOOKING

    # Step 3: Present Calendar Slots
    booking_service = BookingService(session=db_session)
    slots, options_msg = await booking_service.present_available_slots(conversation_id=conv.id, wa_id=wa_id)
    assert len(slots) == 3
    assert "1️⃣" in options_msg

    # Step 4: Customer selects Option 1 to confirm
    booking, confirmation_msg = await booking_service.confirm_slot_booking(
        conversation_id=conv.id,
        wa_id=wa_id,
        customer_selection_text="1",
    )
    assert booking is not None
    assert booking.status == BookingStatus.CONFIRMED
    assert booking.crm_sync_status == CRMSyncStatus.SYNCED
    assert "confirmed" in confirmation_msg.lower()

    # Verify final conversation stage is BOOKED
    await db_session.refresh(conv)
    assert conv.stage == ConversationStage.BOOKED


@pytest.mark.asyncio
async def test_complete_frustration_escalation_e2e(client: AsyncClient, db_session: AsyncSession):
    """End-to-end test verifying customer frustration triggers escalation and stops bot messages."""
    wa_id = "15559873344"
    customer_name = "Frustrated Client"

    # Step 1: Initial conversation
    conv = Conversation(wa_id=wa_id, customer_name=customer_name, stage=ConversationStage.GREETING)
    db_session.add(conv)
    await db_session.commit()

    # Step 2: Customer expresses frustration and demands human
    escalation_service = EscalationService(session=db_session)
    escalate, reason, score = escalation_service.detect_signals("This is ridiculous and a scam. I want a human representative right now!")
    assert escalate is True

    escalation, handoff_msg = await escalation_service.trigger_escalation(
        conversation_id=conv.id,
        wa_id=wa_id,
        trigger_reason=reason,
        customer_statement="This is ridiculous and a scam. I want a human representative right now!",
        sentiment_score=score,
    )
    assert escalation is not None
    assert "human support team" in handoff_msg

    # Verify autonomous actions halted
    await db_session.refresh(conv)
    assert conv.is_autonomous_active is False
    assert conv.stage == ConversationStage.HUMAN_HANDOFF

    # Step 3: Verify subsequent inbound messages do not generate autonomous sales replies
    subsequent_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "1002",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "contacts": [{"wa_id": wa_id, "profile": {"name": customer_name}}],
                            "messages": [
                                {
                                    "id": "wamid.E2E_POST_ESCALATE_MSG",
                                    "from": wa_id,
                                    "timestamp": "1729002000",
                                    "type": "text",
                                    "text": {"body": "Is anyone there?"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(subsequent_payload).encode("utf-8")
    sig = generate_hub_signature(raw_body, settings.WHATSAPP_APP_SECRET)

    res = await client.post(
        "/api/v1/whatsapp/webhook",
        content=raw_body,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert res.status_code == 200

    # Ensure conversation still locked in HUMAN_HANDOFF and inactive
    await db_session.refresh(conv)
    assert conv.is_autonomous_active is False
    assert conv.stage == ConversationStage.HUMAN_HANDOFF
