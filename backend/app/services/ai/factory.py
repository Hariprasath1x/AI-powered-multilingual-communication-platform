"""AI Provider factory for MassCommAI."""

import logging
from typing import Optional
from app.core.config import settings
from app.services.ai.base import BaseAIProvider
from app.services.ai.mock_provider import MockAIProvider
from app.services.ai.gemini_provider import GeminiAIProvider

logger = logging.getLogger(__name__)


def get_ai_provider(provider_type: Optional[str] = None) -> BaseAIProvider:
    """
    Factory function returning configured AI provider.
    Defaults to Gemini if GEMINI_API_KEY is present and provider is not forced to mock.
    Defaults to MockAIProvider otherwise.
    """
    selected_provider = (provider_type or settings.AI_PROVIDER).lower().strip()

    if selected_provider == "gemini" or (selected_provider == "auto" and settings.GEMINI_API_KEY):
        try:
            return GeminiAIProvider()
        except Exception as exc:
            logger.warning("Failed to initialize GeminiAIProvider (%s), falling back to MockAIProvider.", exc)
            return MockAIProvider()

    return MockAIProvider()

