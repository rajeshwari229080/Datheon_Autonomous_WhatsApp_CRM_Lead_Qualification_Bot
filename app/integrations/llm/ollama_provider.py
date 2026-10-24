"""Local Ollama open-weights model adapter for structured qualification."""

import json
from typing import Any, Dict, List
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.integrations.llm.base import BaseLLMProvider
from app.prompts.v1.qualification import QUALIFICATION_SYSTEM_PROMPT, format_qualification_prompt
from app.schemas.qualification import QualificationExtractionResult


class OllamaLLMProvider(BaseLLMProvider):
    """Integrates with locally hosted Ollama instance (e.g. Llama 3.2, Mistral)."""

    def __init__(self, base_url: str = settings.OLLAMA_BASE_URL, model: str = settings.OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def extract_lead_qualification(
        self,
        customer_message: str,
        conversation_history: List[Dict[str, str]],
        current_state: Dict[str, Any],
    ) -> QualificationExtractionResult:
        prompt = format_qualification_prompt(customer_message, conversation_history, current_state)

        payload = {
            "model": self.model,
            "system": QUALIFICATION_SYSTEM_PROMPT,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(f"{self.base_url}/api/generate", json=payload)
                res.raise_for_status()
                data = res.json()
                response_text = data.get("response", "{}")
                parsed_json = json.loads(response_text)
                return QualificationExtractionResult.model_validate(parsed_json)
        except Exception as exc:
            logger.error(
                f"Ollama structured extraction failed: {exc}",
                extra={"model": self.model},
            )
            # Safe degraded fallback
            return QualificationExtractionResult(
                confidence=0.0,
                next_action="Clarify customer inquiry",
                follow_up_question="Thank you for your message. Could you share a few more details about your team and budget requirements?",
            )
