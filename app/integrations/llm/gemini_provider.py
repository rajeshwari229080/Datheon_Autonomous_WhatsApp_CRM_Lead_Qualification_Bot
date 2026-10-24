"""Google Gemini LLM Provider adapter using structured REST endpoint."""

import json
from typing import Any, Dict, List
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.integrations.llm.base import BaseLLMProvider
from app.prompts.v1.qualification import QUALIFICATION_SYSTEM_PROMPT, format_qualification_prompt
from app.schemas.qualification import QualificationExtractionResult


class GeminiLLMProvider(BaseLLMProvider):
    """Integrates with Google Gemini API via official REST endpoint."""

    def __init__(
        self,
        api_key: str = settings.GEMINI_API_KEY or "",
        model: str = settings.GEMINI_MODEL,
    ):
        self.api_key = api_key
        self.model = model

    async def extract_lead_qualification(
        self,
        customer_message: str,
        conversation_history: List[Dict[str, str]],
        current_state: Dict[str, Any],
    ) -> QualificationExtractionResult:
        if not self.api_key:
            logger.warning("Gemini API key missing; falling back to safe default response.")
            return QualificationExtractionResult(
                confidence=0.0,
                next_action="Request requirements",
                follow_up_question="Could you tell me a bit more about your company and project timeline?",
            )

        prompt = format_qualification_prompt(customer_message, conversation_history, current_state)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        payload = {
            "system_instruction": {"parts": [{"text": QUALIFICATION_SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_text)
                return QualificationExtractionResult.model_validate(parsed)
        except Exception as exc:
            logger.error(f"Gemini extraction call failed: {exc}")
            return QualificationExtractionResult(
                confidence=0.0,
                next_action="Clarify inquiry",
                follow_up_question="Could you share a bit more detail about your project goals?",
            )
