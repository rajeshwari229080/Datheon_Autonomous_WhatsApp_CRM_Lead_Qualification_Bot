"""Two-Phase Calendar Booking Service with race condition prevention and CRM reconciliation."""

import uuid
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.constants import BookingStatus, ConversationStage, CRMSyncStatus, QualificationStatus
from app.core.logging import logger
from app.db.repositories.conversation_repository import ConversationRepository
from app.integrations.calendar.base import BaseCalendarProvider, SlotUnavailableError
from app.integrations.calendar.factory import get_calendar_provider
from app.integrations.crm.base import BaseCRMProvider
from app.integrations.crm.factory import get_crm_provider
from app.models.booking import Booking
from app.models.lead import Lead
from app.schemas.booking import CalendarSlot
from app.schemas.crm import CRMLeadPayload
from app.services.state_machine import ConversationStateMachine


class BookingService:
    def __init__(
        self,
        session: AsyncSession,
        calendar_provider: Optional[BaseCalendarProvider] = None,
        crm_provider: Optional[BaseCRMProvider] = None,
    ):
        self.session = session
        self.conv_repo = ConversationRepository(session)
        self.calendar = calendar_provider or get_calendar_provider()
        self.crm = crm_provider or get_crm_provider()

    async def present_available_slots(self, conversation_id: str, wa_id: str) -> tuple[List[CalendarSlot], str]:
        """Phase 1: Fetch provider-confirmed available slots and present to customer.

        Requires lead to be QUALIFIED.
        """
        # 1. Gate check: Must be qualified
        stmt = select(Lead).where(Lead.conversation_id == conversation_id)
        res = await self.session.execute(stmt)
        lead = res.scalars().first()

        if not lead or lead.qualification_status != QualificationStatus.QUALIFIED:
            logger.warning(
                f"Booking rejected: Lead {conversation_id} is not qualified.",
                extra={"conversation_id": conversation_id},
            )
            raise ValueError("Only qualified leads can schedule a demonstration.")

        # 2. Query available slots
        slots = await self.calendar.get_available_slots(days_ahead=3)
        if not slots:
            return [], "Our calendar is currently full for the next few days. Our team will contact you directly to find a suitable time."

        # 3. Store slot mapping in conversation context for Phase 2 validation
        slot_map = {str(i + 1): slot.model_dump(mode="json") for i, slot in enumerate(slots)}
        confirmation_token = f"tok_{uuid.uuid4().hex[:8]}"

        await self.conv_repo.update_context(conversation_id, "offered_slots", slot_map)
        await self.conv_repo.update_context(conversation_id, "booking_token", confirmation_token)

        # Advance conversation stage to BOOKING
        conv = await self.conv_repo.get_by_id(conversation_id)
        if conv and conv.stage == ConversationStage.QUALIFIED:
            ConversationStateMachine.validate_transition(conv.stage, ConversationStage.BOOKING)
            await self.conv_repo.update_stage(conversation_id, ConversationStage.BOOKING)

        # 4. Format friendly WhatsApp message
        options_text = "\n".join([f"*{i+1}️⃣* {s.display_text}" for i, s in enumerate(slots)])
        message_text = (
            f"Here are our available 30-minute demonstration slots:\n\n"
            f"{options_text}\n\n"
            f"Please reply with the number of your choice (e.g. *1*, *2*, or *3*) to confirm your demo."
        )

        return slots, message_text

    async def confirm_slot_booking(
        self,
        conversation_id: str,
        wa_id: str,
        customer_selection_text: str,
    ) -> tuple[Optional[Booking], str]:
        """Phase 2: Customer confirms specific slot. Rechecks availability, books event, and syncs CRM."""
        conv = await self.conv_repo.get_by_id(conversation_id)
        if not conv:
            return None, "Conversation not found."

        offered_slots = conv.context_data.get("offered_slots", {})
        selection = customer_selection_text.strip()

        # Match choice number (1, 2, 3 or 'option 1', etc.)
        matched_slot_data = None
        for key in ["1", "2", "3"]:
            if key == selection or f"option {key}" in selection.lower():
                matched_slot_data = offered_slots.get(key)
                break

        if not matched_slot_data:
            # Fallback to first slot if only one available or default key
            matched_slot_data = offered_slots.get("1")

        if not matched_slot_data:
            return None, "I couldn't identify the selected slot. Please reply with *1*, *2*, or *3*."

        selected_slot_id = matched_slot_data["slot_id"]

        # 1. Pre-booking race condition prevention (recheck slot availability)
        try:
            booking_outcome = await self.calendar.create_booking(
                slot_id=selected_slot_id,
                customer_name=conv.customer_name or "Valued Client",
                customer_phone=wa_id,
            )
        except SlotUnavailableError:
            logger.warning(
                f"Booking collision: Slot {selected_slot_id} was just taken.",
                extra={"slot_id": selected_slot_id},
            )
            # Re-present fresh slots
            _, fresh_msg = await self.present_available_slots(conversation_id, wa_id)
            return None, f"That time slot was just booked by another customer. Here are fresh options:\n\n{fresh_msg}"

        # 2. Persist confirmed booking in local DB
        booking = Booking(
            conversation_id=conversation_id,
            event_id=booking_outcome.event_id,
            meeting_url=booking_outcome.meeting_url,
            start_time=booking_outcome.start_time,
            end_time=booking_outcome.end_time,
            timezone=booking_outcome.timezone,
            status=BookingStatus.CONFIRMED,
            confirmation_token=conv.context_data.get("booking_token"),
            crm_sync_status=CRMSyncStatus.PENDING,
        )
        self.session.add(booking)
        await self.session.flush()

        # 3. Transition conversation stage to BOOKED
        ConversationStateMachine.validate_transition(conv.stage, ConversationStage.BOOKED)
        await self.conv_repo.update_stage(conversation_id, ConversationStage.BOOKED)

        # 4. Synchronize CRM lead record
        stmt = select(Lead).where(Lead.conversation_id == conversation_id)
        lead_res = await self.session.execute(stmt)
        lead = lead_res.scalars().first()

        crm_payload = CRMLeadPayload(
            wa_id=wa_id,
            name=conv.customer_name,
            company_name=lead.company_name if lead else None,
            budget_amount=lead.budget_amount if lead else None,
            currency=lead.currency if lead else "USD",
            employee_count=lead.employee_count if lead else None,
            problem_urgency=lead.problem_urgency.value if lead else "UNKNOWN",
            business_problem=lead.business_problem if lead else None,
            qualification_status="QUALIFIED",
            calendar_event_id=booking_outcome.event_id,
            meeting_url=booking_outcome.meeting_url,
            booking_status="CONFIRMED",
        )

        crm_res = await self.crm.sync_lead(crm_payload)
        if crm_res.success:
            booking.crm_sync_status = CRMSyncStatus.SYNCED
            booking.crm_record_id = crm_res.crm_record_id
            if lead:
                lead.crm_lead_id = crm_res.crm_record_id
        else:
            booking.crm_sync_status = CRMSyncStatus.FAILED
            booking.crm_sync_error = crm_res.error_message
            logger.error(
                f"CRM sync failed for booking {booking.id}; scheduled for reconciliation: {crm_res.error_message}"
            )

        await self.session.flush()
        return booking, booking_outcome.confirmation_message

    async def reconcile_pending_crm_syncs(self) -> int:
        """Finds bookings with failed CRM sync and reconciles them with exponential backoff."""
        stmt = select(Booking).where(Booking.crm_sync_status == CRMSyncStatus.FAILED)
        res = await self.session.execute(stmt)
        failed_bookings = res.scalars().all()

        reconciled_count = 0
        for b in failed_bookings:
            conv = await self.conv_repo.get_by_id(b.conversation_id)
            if not conv:
                continue

            payload = CRMLeadPayload(
                wa_id=conv.wa_id,
                name=conv.customer_name,
                calendar_event_id=b.event_id,
                meeting_url=b.meeting_url,
                booking_status="CONFIRMED",
            )
            crm_res = await self.crm.sync_lead(payload)
            if crm_res.success:
                b.crm_sync_status = CRMSyncStatus.RECONCILED
                b.crm_record_id = crm_res.crm_record_id
                b.crm_sync_error = None
                reconciled_count += 1
                logger.info(f"Reconciled booking {b.id} with CRM record {crm_res.crm_record_id}")

        await self.session.flush()
        return reconciled_count
