"""Factory function to instantiate the configured LLM provider."""

from app.core.config import settings
from app.core.constants import LLMProviderType
from app.core.logging import logger
from app.integrations.llm.base import BaseLLMProvider
from app.integrations.llm.gemini_provider import GeminiLLMProvider
from app.integrations.llm.mock_provider import MockDeterministicLLMProvider
from app.integrations.llm.ollama_provider import OllamaLLMProvider
from app.integrations.llm.openai_provider import OpenAILLMProvider


def get_llm_provider() -> BaseLLMProvider:
    """Return instance of configured LLM provider according to settings."""
    provider_type = settings.LLM_PROVIDER

    if provider_type == LLMProviderType.OLLAMA:
        logger.info(f"Using Ollama local LLM provider at {settings.OLLAMA_BASE_URL}")
        return OllamaLLMProvider()
    elif provider_type == LLMProviderType.OPENAI:
        logger.info("Using OpenAI LLM provider")
        return OpenAILLMProvider()
    elif provider_type == LLMProviderType.GEMINI:
        logger.info("Using Google Gemini LLM provider")
        return GeminiLLMProvider()
    else:
        logger.info("Using deterministic offline Mock LLM provider")
        return MockDeterministicLLMProvider()
