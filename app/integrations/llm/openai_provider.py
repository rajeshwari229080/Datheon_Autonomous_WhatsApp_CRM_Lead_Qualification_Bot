"""OpenAI-compatible LLM Provider adapter using Structured Outputs."""

import json
from typing import Any, Dict, List
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.integrations.llm.base import BaseLLMProvider
from app.prompts.v1.qualification import QUALIFICATION_SYSTEM_PROMPT, format_qualification_prompt
from app.schemas.qualification import QualificationExtractionResult


class OpenAILLMProvider(BaseLLMProvider):
    """Integrates with OpenAI API or OpenAI-compatible endpoints with JSON schema enforcement."""

    def __init__(
        self,
        api_key: str = settings.OPENAI_API_KEY or "",
        model: str = settings.OPENAI_MODEL,
        base_url: str = "https://api.openai.com/v1",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def extract_lead_qualification(
        self,
        customer_message: str,
        conversation_history: List[Dict[str, str]],
        current_state: Dict[str, Any],
    ) -> QualificationExtractionResult:
        if not self.api_key:
            logger.warning("OpenAI API key missing; falling back to safe default response.")
            return QualificationExtractionResult(
                confidence=0.0,
                next_action="Request requirements",
                follow_up_question="Could you tell me a bit more about your company and project timeline?",
            )

        prompt = format_qualification_prompt(customer_message, conversation_history, current_state)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": QUALIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                raw_content = data["choices"][0]["message"]["content"]
                parsed = json.loads(raw_content)
                return QualificationExtractionResult.model_validate(parsed)
        except Exception as exc:
            logger.error(f"OpenAI extraction call failed: {exc}")
            return QualificationExtractionResult(
                confidence=0.0,
                next_action="Clarify inquiry",
                follow_up_question="Could you share a bit more detail about your project goals?",
            )
