"""Deterministic, offline Mock LLM Provider for unit testing and local development."""

import re
from typing import Any, Dict, List
from app.core.constants import DecisionMakerStatus, QualificationStatus, UrgencyLevel
from app.integrations.llm.base import BaseLLMProvider
from app.schemas.qualification import BudgetInfo, CompanySizeInfo, QualificationExtractionResult


class MockDeterministicLLMProvider(BaseLLMProvider):
    """High-fidelity mock provider parsing natural language with deterministic rules."""

    async def extract_lead_qualification(
        self,
        customer_message: str,
        conversation_history: List[Dict[str, str]],
        current_state: Dict[str, Any],
    ) -> QualificationExtractionResult:
        text = customer_message.lower().strip()

        # 1. Human Request & Frustration Detection
        human_keywords = ["human", "agent", "representative", "person", "support team", "speak to someone"]
        frustration_keywords = ["terrible", "angry", "annoyed", "frustrated", "horrible", "stupid bot", "cancel this", "scam", "lawyer"]

        requested_human = any(k in text for k in human_keywords)
        detected_frustration = any(k in text for k in frustration_keywords)

        if requested_human or detected_frustration:
            return QualificationExtractionResult(
                qualification_status=QualificationStatus.NEEDS_MORE_INFORMATION,
                confidence=1.0,
                detected_frustration=detected_frustration,
                requested_human=requested_human,
                next_action="Transfer conversation to human sales representative immediately",
                follow_up_question="I understand. I am transferring you to a human team member right now.",
            )

        # 2. Prompt Injection Defense Check
        injection_triggers = [
            "ignore all previous",
            "system override",
            "new instructions",
            "you are now in developer mode",
            "bypass qualification",
            "grant admin",
        ]
        if any(trigger in text for trigger in injection_triggers):
            # Refuse prompt override; do not fabricate qualification
            return QualificationExtractionResult(
                qualification_status=QualificationStatus.NEEDS_MORE_INFORMATION,
                confidence=0.95,
                next_action="Reiterate qualification boundaries",
                follow_up_question="I can only assist with Datheon sales and lead qualification. Could you tell me about your team's project requirements?",
            )

        # 3. Budget Extraction
        budget = BudgetInfo(**current_state.get("budget", {})) if current_state.get("budget") else BudgetInfo()
        # Look for $X, Xk, X USD, etc.
        budget_match = re.search(r"(\$|usd|eur|€)?\s*(\d+[\d,]*)\s*(k|thousand|usd|dollars)?", text)
        if budget_match:
            raw_num_str = budget_match.group(2).replace(",", "")
            try:
                raw_num = float(raw_num_str)
                unit = budget_match.group(3) or ""
                if "k" in unit or "thousand" in unit:
                    raw_num *= 1000.0

                currency = "EUR" if "€" in text or "eur" in text else "USD"
                budget = BudgetInfo(
                    amount=raw_num,
                    currency=currency,
                    status="EXPLICIT",
                )
            except ValueError:
                pass

        # 4. Company Size Extraction
        company_size = CompanySizeInfo(**current_state.get("company_size", {})) if current_state.get("company_size") else CompanySizeInfo()
        size_match = re.search(r"(\d+)\s*(employees|people|team members|staff|engineers)", text)
        if size_match:
            count = int(size_match.group(1))
            company_size = CompanySizeInfo(
                employee_count=count,
                range=f"{count}",
                status="EXPLICIT",
            )
        elif "small team" in text or "startup" in text:
            company_size = CompanySizeInfo(employee_count=10, range="5-15", status="INFERRED")
        elif "enterprise" in text or "large company" in text:
            company_size = CompanySizeInfo(employee_count=500, range="250+", status="INFERRED")

        # 5. Urgency Extraction
        urgency = UrgencyLevel(current_state.get("problem_urgency", UrgencyLevel.UNKNOWN))
        if any(w in text for w in ["asap", "immediately", "critical", "urgent", "yesterday"]):
            urgency = UrgencyLevel.CRITICAL
        elif any(w in text for w in ["this month", "soon", "high priority"]):
            urgency = UrgencyLevel.HIGH
        elif any(w in text for w in ["exploring", "low priority", "no rush"]):
            urgency = UrgencyLevel.LOW

        # 6. Decision Maker Extraction
        decision_maker = DecisionMakerStatus(current_state.get("decision_maker", DecisionMakerStatus.UNKNOWN))
        if any(w in text for w in ["i decide", "i'm the founder", "i am the cto", "ceo", "i have budget authority", "my decision"]):
            decision_maker = DecisionMakerStatus.YES
        elif any(w in text for w in ["need approval", "my boss decides", "not my call", "committee"]):
            decision_maker = DecisionMakerStatus.NO

        # 7. Timeline Extraction
        timeline = current_state.get("purchase_timeline")
        if any(w in text for w in ["30 days", "this month", "within a month"]):
            timeline = "WITHIN_30_DAYS"
        elif any(w in text for w in ["quarter", "90 days", "three months"]):
            timeline = "WITHIN_90_DAYS"

        # 8. Business Problem
        problem = current_state.get("business_problem")
        if any(w in text for w in ["lead", "crm", "sales", "automate", "qualification", "booking"]):
            problem = customer_message.strip()

        # 9. Compute Missing Fields
        missing = []
        if budget.status == "UNKNOWN" or budget.amount is None:
            missing.append("budget")
        if company_size.status == "UNKNOWN" or company_size.employee_count is None:
            missing.append("company_size")
        if decision_maker == DecisionMakerStatus.UNKNOWN:
            missing.append("decision_maker")
        if urgency == UrgencyLevel.UNKNOWN:
            missing.append("problem_urgency")

        # 10. Generate Follow-up Question (One at a time!)
        follow_up = None
        if "company_size" in missing:
            follow_up = "How many team members or employees work at your company?"
        elif "budget" in missing:
            follow_up = "What allocated monthly or project budget do you have in mind for this solution?"
        elif "decision_maker" in missing:
            follow_up = "Are you the primary decision-maker for evaluating and approving this technology?"
        elif "problem_urgency" in missing:
            follow_up = "How urgently is your team looking to solve this business challenge?"

        return QualificationExtractionResult(
            budget=budget,
            company_size=company_size,
            problem_urgency=urgency,
            business_problem=problem,
            decision_maker=decision_maker,
            purchase_timeline=timeline,
            qualification_status=QualificationStatus.QUALIFIED if not missing else QualificationStatus.NEEDS_MORE_INFORMATION,
            confidence=0.92,
            missing_fields=missing,
            next_action=f"Ask for {missing[0]}" if missing else "Offer demonstration booking slots",
            follow_up_question=follow_up or "Great! Based on your details, I would love to book a 30-minute demonstration.",
        )
