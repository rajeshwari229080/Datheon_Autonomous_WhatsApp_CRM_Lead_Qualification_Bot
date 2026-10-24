"""Abstract Base Class for Interchangeable LLM Providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from app.schemas.qualification import QualificationExtractionResult


class BaseLLMProvider(ABC):
    """Abstract interface for LLM extraction and structured conversational qualification."""

    @abstractmethod
    async def extract_lead_qualification(
        self,
        customer_message: str,
        conversation_history: List[Dict[str, str]],
        current_state: Dict[str, Any],
    ) -> QualificationExtractionResult:
        """Analyze inbound customer input and extract structured qualification data."""
        pass
