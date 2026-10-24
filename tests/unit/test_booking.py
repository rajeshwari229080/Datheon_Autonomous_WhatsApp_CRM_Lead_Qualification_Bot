"""Unit tests for Two-Phase Calendar Booking and CRM Synchronization."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import BookingStatus, ConversationStage, CRMSyncStatus, QualificationStatus
from app.integrations.calendar.mock_calendar import MockCalendarProvider
from app.integrations.crm.mock_crm import MockCRMProvider
from app.models.booking import Booking
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.services.booking_service import BookingService


@pytest.mark.asyncio
async def test_unqualified_cannot_book(db_session: AsyncSession):
    """Unqualified lead cannot access or present calendar booking slots."""
    conv = Conversation(wa_id="15550001111", stage=ConversationStage.QUALIFICATION)
    db_session.add(conv)
    await db_session.flush()

    lead = Lead(
        conversation_id=conv.id,
        wa_id=conv.wa_id,
        qualification_status=QualificationStatus.NEEDS_MORE_INFORMATION,
    )
    db_session.add(lead)
    await db_session.commit()

    service = BookingService(session=db_session)
    with pytest.raises(ValueError, match="Only qualified leads can schedule"):
        await service.present_available_slots(conversation_id=conv.id, wa_id=conv.wa_id)


@pytest.mark.asyncio
async def test_present_slots_success(db_session: AsyncSession):
    """Qualified lead receives 3 valid demonstration slots with options."""
    conv = Conversation(wa_id="15550002222", stage=ConversationStage.QUALIFIED)
    db_session.add(conv)
    await db_session.flush()

    lead = Lead(
        conversation_id=conv.id,
        wa_id=conv.wa_id,
        qualification_status=QualificationStatus.QUALIFIED,
        budget_amount=5000.0,
    )
    db_session.add(lead)
    await db_session.commit()

    service = BookingService(session=db_session, calendar_provider=MockCalendarProvider())
    slots, message = await service.present_available_slots(conversation_id=conv.id, wa_id=conv.wa_id)

    assert len(slots) == 3
    assert "1️⃣" in message
    assert "2️⃣" in message
    assert "3️⃣" in message

    # Verify context stored slot mapping
    await db_session.refresh(conv)
    assert "offered_slots" in conv.context_data
    assert "1" in conv.context_data["offered_slots"]


@pytest.mark.asyncio
async def test_confirm_slot_booking_success(db_session: AsyncSession):
    """Customer confirms slot choice '1'; booking is created, stage becomes BOOKED, CRM synced."""
    conv = Conversation(wa_id="15550003333", customer_name="David Miller", stage=ConversationStage.QUALIFIED)
    db_session.add(conv)
    await db_session.flush()

    lead = Lead(
        conversation_id=conv.id,
        wa_id=conv.wa_id,
        qualification_status=QualificationStatus.QUALIFIED,
        budget_amount=10000.0,
        company_name="Acme Corp",
    )
    db_session.add(lead)
    await db_session.commit()

    cal = MockCalendarProvider()
    crm = MockCRMProvider()
    service = BookingService(session=db_session, calendar_provider=cal, crm_provider=crm)

    # Phase 1: Present slots
    await service.present_available_slots(conversation_id=conv.id, wa_id=conv.wa_id)

    # Phase 2: Confirm slot 1
    booking, confirmation_msg = await service.confirm_slot_booking(
        conversation_id=conv.id,
        wa_id=conv.wa_id,
        customer_selection_text="1",
    )

    assert booking is not None
    assert booking.status == BookingStatus.CONFIRMED
    assert booking.meeting_url is not None
    assert booking.crm_sync_status == CRMSyncStatus.SYNCED
    assert "confirmed" in confirmation_msg.lower()

    # Verify conversation state transitioned to BOOKED
    await db_session.refresh(conv)
    assert conv.stage == ConversationStage.BOOKED


@pytest.mark.asyncio
async def test_concurrent_slot_race_condition(db_session: AsyncSession):
    """When a slot is booked by someone else between presentation and confirmation, collision is caught."""
    conv = Conversation(wa_id="15550004444", stage=ConversationStage.QUALIFIED)
    db_session.add(conv)
    await db_session.flush()

    lead = Lead(
        conversation_id=conv.id,
        wa_id=conv.wa_id,
        qualification_status=QualificationStatus.QUALIFIED,
    )
    db_session.add(lead)
    await db_session.commit()

    cal = MockCalendarProvider()
    service = BookingService(session=db_session, calendar_provider=cal)

    slots, _ = await service.present_available_slots(conversation_id=conv.id, wa_id=conv.wa_id)
    slot1_id = slots[0].slot_id

    # Simulate another user booking slot1 concurrently in background
    cal.booked_slots.add(slot1_id)

    # Attempt to confirm slot 1
    booking, error_msg = await service.confirm_slot_booking(
        conversation_id=conv.id,
        wa_id=conv.wa_id,
        customer_selection_text="1",
    )

    assert booking is None
    assert "was just booked" in error_msg.lower()


@pytest.mark.asyncio
async def test_crm_partial_failure_and_reconciliation(db_session: AsyncSession):
    """When CRM provider is degraded, local booking is preserved and later reconciled."""
    conv = Conversation(wa_id="15550005555", stage=ConversationStage.QUALIFIED)
    db_session.add(conv)
    await db_session.flush()

    lead = Lead(
        conversation_id=conv.id,
        wa_id=conv.wa_id,
        qualification_status=QualificationStatus.QUALIFIED,
    )
    db_session.add(lead)
    await db_session.commit()

    cal = MockCalendarProvider()
    crm = MockCRMProvider()
    crm.simulate_failure = True  # Simulate 503 outage

    service = BookingService(session=db_session, calendar_provider=cal, crm_provider=crm)
    await service.present_available_slots(conversation_id=conv.id, wa_id=conv.wa_id)

    booking, _ = await service.confirm_slot_booking(
        conversation_id=conv.id,
        wa_id=conv.wa_id,
        customer_selection_text="1",
    )

    # Booking is confirmed locally despite CRM outage
    assert booking is not None
    assert booking.status == BookingStatus.CONFIRMED
    assert booking.crm_sync_status == CRMSyncStatus.FAILED

    # Now CRM recovers
    crm.simulate_failure = False
    reconciled_count = await service.reconcile_pending_crm_syncs()
    assert reconciled_count == 1

    await db_session.refresh(booking)
    assert booking.crm_sync_status == CRMSyncStatus.RECONCILED
    assert booking.crm_record_id is not None
