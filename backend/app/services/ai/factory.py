"""AI Provider factory for MassCommAI.

Provider resolution order (when AI_PROVIDER="auto"):
  1. Groq  — when GROQ_API_KEY is present  (openai/gpt-oss-120b)
  2. Gemini — when GEMINI_API_KEY is present (legacy)
  3. Mock   — offline / testing fallback

If AI_PROVIDER is explicitly set to "groq", "gemini", or "mock",
that provider is selected directly without fallthrough.
"""

import logging
from typing import Optional

from app.core.config import settings
from app.services.ai.base import AIProviderError, BaseAIProvider
from app.services.ai.mock_provider import MockAIProvider

logger = logging.getLogger(__name__)


def get_ai_provider(provider_type: Optional[str] = None) -> BaseAIProvider:
    """
    Factory function returning the configured AI provider instance.

    Resolution order for provider_type="auto" (or settings.AI_PROVIDER="auto"):
      1. GroqAIProvider  when GROQ_API_KEY is present
      2. GeminiAIProvider when GEMINI_API_KEY is present
      3. MockAIProvider  as offline / test fallback

    Explicit values: "groq", "gemini", "mock".

    When Groq is unavailable (missing key, initialization failure), returns a
    clear AIProviderError rather than silently falling back to another key-bearing
    provider.  MockAIProvider is always used as the final no-key fallback.
    """
    selected = (provider_type or settings.AI_PROVIDER).lower().strip()

    # ------------------------------------------------------------------ #
    # Explicit: "groq"
    # ------------------------------------------------------------------ #
    if selected == "groq":
        from app.services.ai.groq_provider import GroqAIProvider
        return GroqAIProvider()

    # ------------------------------------------------------------------ #
    # Explicit: "gemini" (legacy)
    # ------------------------------------------------------------------ #
    if selected == "gemini":
        from app.services.ai.gemini_provider import GeminiAIProvider
        return GeminiAIProvider()

    # ------------------------------------------------------------------ #
    # Explicit: "mock"
    # ------------------------------------------------------------------ #
    if selected == "mock":
        return MockAIProvider()

    # ------------------------------------------------------------------ #
    # Auto resolution: Groq → Gemini → Mock
    # ------------------------------------------------------------------ #
    if selected == "auto":
        # 1. Groq
        if settings.GROQ_API_KEY:
            try:
                from app.services.ai.groq_provider import GroqAIProvider
                provider = GroqAIProvider()
                logger.debug(
                    "AI provider resolved: Groq (model=%s)", provider.get_model_name()
                )
                return provider
            except Exception as exc:
                logger.warning(
                    "Failed to initialize GroqAIProvider (%s); "
                    "attempting Gemini fallback.",
                    exc,
                )

        # 2. Gemini (legacy)
        if settings.GEMINI_API_KEY:
            try:
                from app.services.ai.gemini_provider import GeminiAIProvider
                provider = GeminiAIProvider()
                logger.debug(
                    "AI provider resolved: Gemini (model=%s)", provider.get_model_name()
                )
                return provider
            except Exception as exc:
                logger.warning(
                    "Failed to initialize GeminiAIProvider (%s); "
                    "falling back to MockAIProvider.",
                    exc,
                )

        # 3. Mock
        logger.info(
            "No AI API key configured (GROQ_API_KEY / GEMINI_API_KEY); "
            "using MockAIProvider (offline mode)."
        )
        return MockAIProvider()

    # Unknown value: safe fallback
    logger.warning(
        "Unknown AI_PROVIDER value '%s'; defaulting to MockAIProvider.", selected
    )
    return MockAIProvider()
