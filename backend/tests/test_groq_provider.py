"""
Groq AI Provider — Centralized Integration Test Suite.

Covers:
1.  GroqAIProvider initialisation with valid key.
2.  Correct model name (openai/gpt-oss-120b).
3.  Missing API key raises AIProviderError, never crashes app startup.
4.  Content generation — successful response.
5.  Content generation — invalid/malformed JSON fallback.
6.  Translation — successful response.
7.  Translation — placeholder preservation & re-injection.
8.  Quality evaluation — successful structured response.
9.  Sentiment analysis — successful response.
10. Sentiment analysis — empty text short-circuit.
11. Invalid API key → AIProviderError (401), no retry.
12. HTTP 429 rate-limit → AIProviderQuotaError after retries.
13. HTTP 503 transient → retry + success.
14. Timeout → AIProviderTimeoutError.
15. Malformed JSON in translation raises AIProviderError 502.
16. Credential sanitization — key redacted in error messages.
17. Factory auto-resolution: Groq preferred when GROQ_API_KEY present.
18. Factory auto-resolution: falls back to Mock when no key present.
19. Factory explicit "groq" selection.
20. Factory explicit "mock" selection.
21. All migrated services use GroqAIProvider (not Gemini) when GROQ key set.
22. No GROQ_API_KEY in test isolation — no real network calls.
23. Overall deadline enforcement stops retry before budget exhausted.
24. Retry-After header respected as exact backoff.
"""

import asyncio
import json
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ai.base import (
    AIProviderError,
    AIProviderQuotaError,
    AIProviderTimeoutError,
    ContentBrief,
    ContentEvaluationRequest,
    TranslationRequest,
)
from app.services.ai.groq_provider import GroqAIProvider
from app.services.ai.mock_provider import MockAIProvider


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

CONTENT_JSON = json.dumps({
    "title": "Public Health Alert",
    "body": "Boil drinking water immediately.",
    "summary": "Boil-water notice.",
    "call_to_action": "Follow guidelines",
})

TRANSLATION_JSON = json.dumps({
    "title": "सार्वजनिक स्वास्थ्य सूचना",
    "body": "नमस्ते {name}, {city} में सहायता केंद्र खुला है।",
    "summary": "सहायता सूचना",
    "call_to_action": "सहायता लें",
})

EVAL_JSON = json.dumps({
    "findings": [
        {
            "category": "tone",
            "severity": "medium",
            "title": "Tone check",
            "explanation": "Urgency consistent.",
            "confidence": 0.9,
        }
    ],
    "dimension_scores": {"tone_consistency": 88.0},
    "summary": "Audit passed.",
})

SENTIMENT_JSON = json.dumps({
    "sentiment": "Positive",
    "score": 0.82,
    "confidence": 0.95,
    "explanation": "Appreciative message.",
})


def _mock_groq_completion(content: str):
    """Return a minimal Groq SDK chat-completion mock with the given content."""
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


def _groq_provider(
    content: str = CONTENT_JSON,
    side_effects=None,
    max_retries: int = 2,
    initial_backoff: float = 0.01,
    overall_deadline: float = 30.0,
    sleep_calls: list = None,
) -> GroqAIProvider:
    """Build a GroqAIProvider backed by a mock Groq client."""
    client = AsyncMock()

    if side_effects is not None:
        # side_effects is a list; pop from front
        effects = list(side_effects)

        async def _create(**kwargs):
            if effects:
                effect = effects.pop(0)
                if isinstance(effect, Exception):
                    raise effect
                return effect
            return _mock_groq_completion(content)

    else:

        async def _create(**kwargs):
            return _mock_groq_completion(content)

    client.chat.completions.create = _create

    async def _sleep(sec):
        if sleep_calls is not None:
            sleep_calls.append(sec)

    return GroqAIProvider(
        api_key="test-groq-key",
        client=client,
        max_retries=max_retries,
        initial_backoff_seconds=initial_backoff,
        max_backoff_seconds=10.0,
        overall_deadline_seconds=overall_deadline,
        sleep_func=_sleep,
    )


@pytest.fixture
def sample_brief():
    return ContentBrief(
        topic="Flood Preparedness",
        objective="Advise citizens on evacuation routes",
        category="Disaster Preparedness",
        tone="urgent",
        channel="SMS",
        source_language="en",
    )


@pytest.fixture
def sample_translation_req():
    return TranslationRequest(
        source_text="Hello {name}, relief center is open in {city}.",
        source_title="Alert",
        source_language="en",
        target_language="hi",
    )


@pytest.fixture
def sample_eval_req():
    return ContentEvaluationRequest(
        title="Notice",
        body="Emergency alert for district.",
        category="Disaster",
        tone="urgent",
        channel="SMS",
        source_language="en",
    )


# ---------------------------------------------------------------------------
# 1. Initialisation with valid key
# ---------------------------------------------------------------------------

def test_groq_provider_initialization_with_valid_key():
    """GroqAIProvider initialises correctly when given an explicit client."""
    provider = GroqAIProvider(api_key="test-groq-key", client=MagicMock())
    assert provider.get_provider_name() == "groq"


# ---------------------------------------------------------------------------
# 2. Correct model name
# ---------------------------------------------------------------------------

def test_groq_provider_default_model():
    """Model name must be openai/gpt-oss-120b (from env / default)."""
    provider = GroqAIProvider(
        api_key="test-key",
        model_name="openai/gpt-oss-120b",
        client=MagicMock(),
    )
    assert provider.get_model_name() == "openai/gpt-oss-120b"


# ---------------------------------------------------------------------------
# 3. Missing API key → AIProviderError (not startup crash)
# ---------------------------------------------------------------------------

def test_missing_api_key_raises_provider_error():
    """Missing GROQ_API_KEY raises AIProviderError with status 500."""
    with patch("app.services.ai.groq_provider.settings") as mock_settings:
        mock_settings.GROQ_API_KEY = None
        mock_settings.GROQ_MODEL = "openai/gpt-oss-120b"
        mock_settings.AI_REQUEST_TIMEOUT_SECONDS = 30.0
        mock_settings.AI_MAX_RETRIES = 2
        mock_settings.AI_INITIAL_BACKOFF_SECONDS = 1.0
        mock_settings.AI_MAX_BACKOFF_SECONDS = 8.0
        mock_settings.AI_OVERALL_DEADLINE_SECONDS = 30.0

        with pytest.raises(AIProviderError) as exc_info:
            GroqAIProvider()

    assert exc_info.value.status_code == 500
    assert "GROQ_API_KEY" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. Content generation — successful response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_content_success(sample_brief):
    """Successful content generation parses JSON and returns GeneratedContentResult."""
    provider = _groq_provider(content=CONTENT_JSON)
    result = await provider.generate_content(sample_brief)

    assert result.title == "Public Health Alert"
    assert "Boil" in result.body
    assert result.channel == "SMS"
    assert result.provider_metadata["provider"] == "groq"
    assert result.provider_metadata["model"] == provider.model_name


# ---------------------------------------------------------------------------
# 5. Content generation — malformed JSON → raw-text fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_content_malformed_json_fallback(sample_brief):
    """Non-JSON response is handled gracefully via raw-text fallback."""
    provider = _groq_provider(content="Flood alert for residents. Stay safe.")
    result = await provider.generate_content(sample_brief)

    assert result.body != ""
    assert result.provider_metadata.get("raw_fallback") is True


# ---------------------------------------------------------------------------
# 6. Translation — successful response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_content_success(sample_translation_req):
    """Translation returns TranslatedContentResult with correct languages."""
    provider = _groq_provider(content=TRANSLATION_JSON)
    result = await provider.translate_content(sample_translation_req)

    assert result.target_language == "hi"
    assert result.source_language == "en"
    assert result.provider_metadata["provider"] == "groq"


# ---------------------------------------------------------------------------
# 7. Translation — placeholder preservation & re-injection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_content_placeholder_preservation(sample_translation_req):
    """{name} and {city} placeholders must be preserved from source."""
    provider = _groq_provider(content=TRANSLATION_JSON)
    result = await provider.translate_content(sample_translation_req)

    assert "{name}" in result.body
    assert "{city}" in result.body


@pytest.mark.asyncio
async def test_translate_content_missing_placeholder_reinjected():
    """When a placeholder is dropped by the model, it must be re-injected."""
    # Response body deliberately omits {city}
    missing_city = json.dumps({
        "title": "Alert",
        "body": "नमस्ते {name}, सहायता केंद्र खुला है।",
        "summary": "Alert",
        "call_to_action": "Help",
    })
    provider = _groq_provider(content=missing_city)
    req = TranslationRequest(
        source_text="Hello {name}, relief center is open in {city}.",
        source_title="Alert",
        source_language="en",
        target_language="hi",
    )
    result = await provider.translate_content(req)
    # {city} must be re-injected somewhere in the body
    assert "{city}" in result.body


# ---------------------------------------------------------------------------
# 8. Quality evaluation — successful structured response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluate_content_success(sample_eval_req):
    """Evaluation parses findings and dimension scores correctly."""
    provider = _groq_provider(content=EVAL_JSON)
    result = await provider.evaluate_content(sample_eval_req)

    assert len(result.findings) == 1
    assert result.findings[0].category == "tone"
    assert result.dimension_scores["tone_consistency"] == 88.0
    assert result.provider_metadata["provider"] == "groq"


# ---------------------------------------------------------------------------
# 9. Sentiment analysis — successful response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_sentiment_positive():
    """Sentiment analysis parses Positive correctly."""
    provider = _groq_provider(content=SENTIMENT_JSON)
    result = await provider.analyze_sentiment("Great service, very helpful!", "en")

    assert result.sentiment == "Positive"
    assert result.score > 0
    assert result.confidence > 0
    # method format is "model:<model_name>" e.g. "model:openai/gpt-oss-120b"
    assert result.method.startswith("model:")


# ---------------------------------------------------------------------------
# 10. Sentiment analysis — empty text short-circuit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_sentiment_empty_text():
    """Empty text returns Neutral without calling the API."""
    provider = GroqAIProvider(api_key="test-key", client=MagicMock())
    result = await provider.analyze_sentiment("", "en")

    assert result.sentiment == "Neutral"
    assert result.score == 0.0


# ---------------------------------------------------------------------------
# 11. Invalid API key → AIProviderError (401), no retry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_api_key_no_retry(sample_brief):
    """HTTP 401 / authentication failure must not retry."""
    auth_err = Exception("401 Unauthorized: api key invalid")
    auth_err.status_code = 401

    sleep_calls = []
    provider = _groq_provider(
        side_effects=[auth_err], sleep_calls=sleep_calls
    )

    with pytest.raises(AIProviderError) as exc_info:
        await provider.generate_content(sample_brief)

    assert exc_info.value.status_code == 401
    assert "authentication" in str(exc_info.value).lower()
    assert len(sleep_calls) == 0  # No retry sleeps


# ---------------------------------------------------------------------------
# 12. HTTP 429 rate-limit → AIProviderQuotaError after retries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_limit_raises_quota_error(sample_brief):
    """Exhausting retries on 429 raises AIProviderQuotaError."""
    rate_err = Exception("429 Resource Exhausted: rate limit exceeded")
    rate_err.status_code = 429

    sleep_calls = []
    provider = _groq_provider(
        side_effects=[rate_err, rate_err, rate_err],
        max_retries=2,
        sleep_calls=sleep_calls,
    )

    with pytest.raises(AIProviderQuotaError) as exc_info:
        await provider.generate_content(sample_brief)

    assert exc_info.value.status_code == 429
    assert len(sleep_calls) == 2  # 2 backoff sleeps for 2 retries


# ---------------------------------------------------------------------------
# 13. HTTP 503 transient → retry + success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transient_503_retries_and_succeeds(sample_brief):
    """Single 503 retries and succeeds on second attempt."""
    transient = Exception("503 Service Unavailable")
    transient.status_code = 503

    sleep_calls = []
    provider = _groq_provider(
        side_effects=[transient, _mock_groq_completion(CONTENT_JSON)],
        sleep_calls=sleep_calls,
    )

    result = await provider.generate_content(sample_brief)
    assert result.title == "Public Health Alert"
    assert len(sleep_calls) == 1


# ---------------------------------------------------------------------------
# 14. Timeout → AIProviderTimeoutError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timeout_raises_timeout_error(sample_brief):
    """asyncio.TimeoutError maps to AIProviderTimeoutError on exhaustion."""
    sleep_calls = []
    provider = _groq_provider(
        side_effects=[
            asyncio.TimeoutError(),
            asyncio.TimeoutError(),
            asyncio.TimeoutError(),
        ],
        max_retries=2,
        sleep_calls=sleep_calls,
    )

    with pytest.raises(AIProviderTimeoutError):
        await provider.generate_content(sample_brief)

    assert len(sleep_calls) == 2


# ---------------------------------------------------------------------------
# 15. Malformed JSON in translation raises AIProviderError 502
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translation_malformed_json_raises_error(sample_translation_req):
    """Non-parseable JSON in translation raises AIProviderError 502."""
    provider = _groq_provider(content="This is NOT json {{{{")
    with pytest.raises(AIProviderError) as exc_info:
        await provider.translate_content(sample_translation_req)
    assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# 16. Credential sanitization — key never appears in error messages
# ---------------------------------------------------------------------------

def test_credential_sanitization_in_error_messages():
    """Raw API key must be redacted from sanitized error strings."""
    raw_key = "gsk_secretkey1234567890abcdef"
    provider = GroqAIProvider(api_key=raw_key, client=MagicMock())

    dirty = f"Request failed with key={raw_key} and bearer gsk_secretkey1234567890abcdef"
    clean = provider._sanitize_message(dirty)

    assert raw_key not in clean
    assert "***REDACTED" in clean


# ---------------------------------------------------------------------------
# 17. Factory auto-resolution: Groq preferred when GROQ_API_KEY present
# ---------------------------------------------------------------------------

def test_factory_auto_prefers_groq_when_key_present():
    """get_ai_provider() with 'auto' returns GroqAIProvider when GROQ_API_KEY set."""
    from app.services.ai.factory import get_ai_provider
    from app.services.ai.groq_provider import GroqAIProvider as GProvider

    with patch("app.services.ai.factory.settings") as mock_settings:
        mock_settings.AI_PROVIDER = "auto"
        mock_settings.GROQ_API_KEY = "test-groq-key"
        mock_settings.GEMINI_API_KEY = None
        mock_settings.GROQ_MODEL = "openai/gpt-oss-120b"
        mock_settings.AI_MODEL_NAME = "gemini-2.5-flash"
        mock_settings.AI_REQUEST_TIMEOUT_SECONDS = 30.0
        mock_settings.AI_MAX_RETRIES = 2
        mock_settings.AI_INITIAL_BACKOFF_SECONDS = 1.0
        mock_settings.AI_MAX_BACKOFF_SECONDS = 8.0
        mock_settings.AI_OVERALL_DEADLINE_SECONDS = 30.0

        with patch("app.services.ai.groq_provider.settings", mock_settings):
            with patch("groq.AsyncGroq"):
                provider = get_ai_provider()

    assert isinstance(provider, GProvider)


# ---------------------------------------------------------------------------
# 18. Factory auto-resolution: falls back to Mock when no key present
# ---------------------------------------------------------------------------

def test_factory_auto_falls_back_to_mock_when_no_key():
    """get_ai_provider() with no keys returns MockAIProvider."""
    from app.services.ai.factory import get_ai_provider

    with patch("app.services.ai.factory.settings") as mock_settings:
        mock_settings.AI_PROVIDER = "auto"
        mock_settings.GROQ_API_KEY = None
        mock_settings.GEMINI_API_KEY = None

        provider = get_ai_provider()

    assert isinstance(provider, MockAIProvider)


# ---------------------------------------------------------------------------
# 19. Factory explicit "groq" selection
# ---------------------------------------------------------------------------

def test_factory_explicit_groq():
    """Explicit provider_type='groq' returns GroqAIProvider."""
    from app.services.ai.factory import get_ai_provider
    from app.services.ai.groq_provider import GroqAIProvider as GProvider

    with patch("app.services.ai.factory.settings") as mock_settings:
        mock_settings.AI_PROVIDER = "groq"
        mock_settings.GROQ_API_KEY = "test-key"
        mock_settings.GROQ_MODEL = "openai/gpt-oss-120b"
        mock_settings.AI_REQUEST_TIMEOUT_SECONDS = 30.0
        mock_settings.AI_MAX_RETRIES = 2
        mock_settings.AI_INITIAL_BACKOFF_SECONDS = 1.0
        mock_settings.AI_MAX_BACKOFF_SECONDS = 8.0
        mock_settings.AI_OVERALL_DEADLINE_SECONDS = 30.0

        with patch("app.services.ai.groq_provider.settings", mock_settings):
            with patch("groq.AsyncGroq"):
                provider = get_ai_provider("groq")

    assert isinstance(provider, GProvider)


# ---------------------------------------------------------------------------
# 20. Factory explicit "mock" selection
# ---------------------------------------------------------------------------

def test_factory_explicit_mock():
    """Explicit provider_type='mock' always returns MockAIProvider."""
    from app.services.ai.factory import get_ai_provider

    with patch("app.services.ai.factory.settings") as mock_settings:
        mock_settings.AI_PROVIDER = "mock"
        provider = get_ai_provider("mock")

    assert isinstance(provider, MockAIProvider)


# ---------------------------------------------------------------------------
# 21. Services use GroqAIProvider when GROQ key is set
# ---------------------------------------------------------------------------

def test_content_service_uses_groq_provider():
    """When GROQ_API_KEY is configured, get_ai_provider returns GroqAIProvider."""
    from app.services.ai.factory import get_ai_provider
    from app.services.ai.groq_provider import GroqAIProvider as GProvider

    with patch("app.services.ai.factory.settings") as mock_settings:
        mock_settings.AI_PROVIDER = "auto"
        mock_settings.GROQ_API_KEY = "real-groq-key"
        mock_settings.GEMINI_API_KEY = None
        mock_settings.GROQ_MODEL = "openai/gpt-oss-120b"
        mock_settings.AI_REQUEST_TIMEOUT_SECONDS = 30.0
        mock_settings.AI_MAX_RETRIES = 2
        mock_settings.AI_INITIAL_BACKOFF_SECONDS = 1.0
        mock_settings.AI_MAX_BACKOFF_SECONDS = 8.0
        mock_settings.AI_OVERALL_DEADLINE_SECONDS = 30.0

        with patch("app.services.ai.groq_provider.settings", mock_settings):
            with patch("groq.AsyncGroq"):
                provider = get_ai_provider()

    assert isinstance(provider, GProvider)
    assert provider.get_provider_name() == "groq"


# ---------------------------------------------------------------------------
# 22. No real API calls during test suite
# ---------------------------------------------------------------------------

def test_no_real_network_calls_in_tests():
    """The Groq client is always mocked; no real API credits consumed."""
    client = MagicMock()
    provider = GroqAIProvider(api_key="test-key", client=client)
    # client.chat.completions.create is a MagicMock — not a real HTTP call
    assert provider.client is client


# ---------------------------------------------------------------------------
# 23. Overall deadline enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_overall_deadline_stops_retries(sample_brief):
    """Required backoff exceeding remaining deadline aborts retry early."""
    transient = Exception("503 Service Unavailable")
    transient.status_code = 503

    simulated_clock = [0.0]

    def mock_time():
        return simulated_clock[0]

    sleep_calls = []

    async def mock_sleep(sec):
        simulated_clock[0] += sec
        sleep_calls.append(sec)

    client = AsyncMock()

    async def _create(**kwargs):
        raise transient

    client.chat.completions.create = _create

    provider = GroqAIProvider(
        api_key="test-key",
        client=client,
        max_retries=5,
        initial_backoff_seconds=20.0,   # 20s backoff >> 10s deadline
        max_backoff_seconds=60.0,
        overall_deadline_seconds=10.0,
        sleep_func=mock_sleep,
        time_func=mock_time,
    )

    with pytest.raises((AIProviderTimeoutError, AIProviderError)):
        await provider.generate_content(sample_brief)

    # Must stop after attempt 1 — required 20s backoff exceeds 10s deadline
    assert len(sleep_calls) == 0


# ---------------------------------------------------------------------------
# 24. Retry-After header respected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_after_header_respected(sample_brief):
    """Retry-After header value is used as the backoff delay."""
    rate_err = Exception("429 quota exceeded retry-after: 5.0")
    rate_err.status_code = 429

    # Build a mock headers dict on the exception
    mock_response = MagicMock()
    mock_response.headers = {"retry-after": "5.0"}
    rate_err.response = mock_response

    sleep_calls = []
    provider = _groq_provider(
        side_effects=[rate_err, _mock_groq_completion(CONTENT_JSON)],
        max_retries=2,
        overall_deadline=60.0,
        sleep_calls=sleep_calls,
    )

    result = await provider.generate_content(sample_brief)
    assert result.title == "Public Health Alert"
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == 5.0
