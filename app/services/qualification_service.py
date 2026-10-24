"""Structured Lead Qualification Service applying deterministic business rules."""

from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.constants import (
    ConversationStage,
    DecisionMakerStatus,
    QualificationStatus,
    UrgencyLevel,
)
from app.core.logging import logger
from app.db.repositories.conversation_repository import ConversationRepository
from app.db.repositories.message_repository import MessageRepository
from app.integrations.llm.base import BaseLLMProvider
from app.integrations.llm.factory import get_llm_provider
from app.models.lead import Lead
from app.schemas.qualification import QualificationExtractionResult
from app.services.state_machine import ConversationStateMachine


class QualificationRulesEngine:
    """Evaluates business rules independently of LLM confidence."""

    @classmethod
    def evaluate_rules(
        cls,
        extraction: QualificationExtractionResult,
        min_budget: float = settings.QUALIFICATION_MIN_BUDGET,
        min_company_size: int = settings.QUALIFICATION_MIN_COMPANY_SIZE,
        require_decision_maker: bool = settings.REQUIRE_DECISION_MAKER,
    ) -> QualificationStatus:
        """Determines qualification status strictly based on business criteria."""
        # 1. Explicit Disqualification checks take precedence
        if extraction.budget.amount is not None and extraction.budget.amount < min_budget:
            logger.info(f"Lead disqualified: budget {extraction.budget.amount} below minimum {min_budget}")
            return QualificationStatus.NOT_QUALIFIED

        if extraction.company_size.employee_count is not None and extraction.company_size.employee_count < min_company_size:
            logger.info(f"Lead disqualified: company size {extraction.company_size.employee_count} below minimum {min_company_size}")
            return QualificationStatus.NOT_QUALIFIED

        if require_decision_maker and extraction.decision_maker == DecisionMakerStatus.NO:
            logger.info("Lead disqualified: contact has no decision authority.")
            return QualificationStatus.NOT_QUALIFIED

        # 2. Check if required fields are still missing
        if extraction.missing_fields:
            return QualificationStatus.NEEDS_MORE_INFORMATION

        if extraction.budget.amount is None or extraction.company_size.employee_count is None:
            return QualificationStatus.NEEDS_MORE_INFORMATION

        return QualificationStatus.QUALIFIED


class QualificationService:
    def __init__(
        self,
        session: AsyncSession,
        llm_provider: Optional[BaseLLMProvider] = None,
    ):
        self.session = session
        self.conv_repo = ConversationRepository(session)
        self.msg_repo = MessageRepository(session)
        self.llm = llm_provider or get_llm_provider()

    async def get_or_create_lead(self, conversation_id: str, wa_id: str) -> Lead:
        """Fetch existing Lead model or initialize empty one."""
        stmt = select(Lead).where(Lead.conversation_id == conversation_id)
        res = await self.session.execute(stmt)
        lead = res.scalars().first()
        if not lead:
            lead = Lead(
                conversation_id=conversation_id,
                wa_id=wa_id,
                qualification_status=QualificationStatus.NEEDS_MORE_INFORMATION,
            )
            self.session.add(lead)
            await self.session.flush()
        return lead

    async def qualify_message(
        self,
        conversation_id: str,
        wa_id: str,
        customer_message: str,
    ) -> tuple[QualificationExtractionResult, str]:
        """Runs extraction, applies business rules, updates database, and returns follow-up text.

        Returns: (extraction_result, bot_response_message)
        """
        lead = await self.get_or_create_lead(conversation_id, wa_id)
        conv = await self.conv_repo.get_by_id(conversation_id)

        # 1. Fetch message history
        recent_msgs = await self.msg_repo.get_recent_history(conversation_id, limit=6)
        history = [
            {"role": "assistant" if m.direction.value == "OUTBOUND" else "customer", "content": m.content or ""}
            for m in recent_msgs
        ]

        current_lead_dict = {
            "budget": {"amount": lead.budget_amount, "currency": lead.currency},
            "company_size": {"employee_count": lead.employee_count, "range": lead.company_size},
            "problem_urgency": lead.problem_urgency.value,
            "business_problem": lead.business_problem,
            "decision_maker": lead.decision_maker.value,
            "purchase_timeline": lead.purchase_timeline,
        }

        # 2. Execute LLM Structured Extraction
        extraction = await self.llm.extract_lead_qualification(
            customer_message=customer_message,
            conversation_history=history,
            current_state=current_lead_dict,
        )

        # 3. Apply Deterministic Business Rules
        final_status = QualificationRulesEngine.evaluate_rules(extraction)
        extraction.qualification_status = final_status

        # 4. Update Persistent Lead Record
        if extraction.budget.amount is not None:
            lead.budget_amount = extraction.budget.amount
            lead.currency = extraction.budget.currency
        if extraction.company_size.employee_count is not None:
            lead.employee_count = extraction.company_size.employee_count
            lead.company_size = extraction.company_size.range
        if extraction.problem_urgency != UrgencyLevel.UNKNOWN:
            lead.problem_urgency = extraction.problem_urgency
        if extraction.business_problem:
            lead.business_problem = extraction.business_problem
        if extraction.decision_maker != DecisionMakerStatus.UNKNOWN:
            lead.decision_maker = extraction.decision_maker
        if extraction.purchase_timeline:
            lead.purchase_timeline = extraction.purchase_timeline

        lead.qualification_status = final_status
        lead.confidence_score = extraction.confidence
        lead.missing_fields = extraction.missing_fields
        await self.session.flush()

        # 5. Handle State Machine Transitions
        if final_status == QualificationStatus.QUALIFIED:
            ConversationStateMachine.validate_transition(conv.stage, ConversationStage.QUALIFIED)
            await self.conv_repo.update_stage(conv.id, ConversationStage.QUALIFIED)
            # Advance to BOOKING stage
            ConversationStateMachine.validate_transition(ConversationStage.QUALIFIED, ConversationStage.BOOKING)
            await self.conv_repo.update_stage(conv.id, ConversationStage.BOOKING)
            bot_text = extraction.follow_up_question or "Excellent! You meet all criteria. Let's schedule a 30-minute demonstration."
        elif final_status == QualificationStatus.NOT_QUALIFIED:
            ConversationStateMachine.validate_transition(conv.stage, ConversationStage.NOT_QUALIFIED)
            await self.conv_repo.update_stage(conv.id, ConversationStage.NOT_QUALIFIED)
            bot_text = "Thank you for sharing your requirements. At this stage, our enterprise solutions may not be the optimal fit for your current volume, but we welcome you to explore our self-serve guides at datheon.ai."
        else:
            # Stays in QUALIFICATION
            bot_text = extraction.follow_up_question or "Could you tell me more about your requirements?"

        return extraction, bot_text
