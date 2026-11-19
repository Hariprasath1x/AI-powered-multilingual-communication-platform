"""Pytest configuration and test isolation fixtures."""

import pytest
from app.core.rate_limiter import reset_rate_limiters
from app.core.config import settings


@pytest.fixture(autouse=True)
def reset_rate_limiters_fixture():
    """Reset rate limiter state before and after each test to ensure test isolation."""
    reset_rate_limiters()
    yield
    reset_rate_limiters()


@pytest.fixture(autouse=True)
def isolate_ai_provider_in_tests(monkeypatch):
    """
    Ensure automated test suite defaults to MockAIProvider to avoid consuming
    real API credits or making external network requests during regression testing.
    Tests specifically testing Groq or Gemini instantiate the provider with mocked clients.
    """
    if settings.AI_PROVIDER == "auto":
        monkeypatch.setattr(settings, "AI_PROVIDER", "mock")
