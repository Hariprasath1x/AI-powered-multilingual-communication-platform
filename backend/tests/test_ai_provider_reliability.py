"""Unit tests for AI Provider Reliability Hardening (M2 Task 7, Step 1)."""

import asyncio
from datetime import datetime, timezone
import logging
import traceback
import pytest
from unittest.mock import MagicMock, patch
from app.services.ai.base import (
    ContentBrief,
    TranslationRequest,
    ContentEvaluationRequest,
    AIProviderError,
    AIProviderTimeoutError,
    AIProviderQuotaError,
)
from app.services.ai.gemini_provider import GeminiAIProvider
from app.services.ai.mock_provider import MockAIProvider
from google.genai import errors


class MockResponse:
    """Mock Gemini response carrying structured JSON text."""

    def __init__(self, text: str = '{"title": "Public Health Alert", "body": "Boil drinking water advisory.", "summary": "Boil water notice.", "call_to_action": "Follow guidelines"}'):
        self.text = text


class MockClient:
    """Mock Google GenAI Client simulating transient and permanent errors."""

    def __init__(self, side_effects=None):
        self.side_effects = list(side_effects) if side_effects is not None else []
        self.call_count = 0
        self.aio = self.Aio(self)

    class Aio:
        def __init__(self, parent):
            self.models = self.Models(parent)

        class Models:
            def __init__(self, parent):
                self.parent = parent

            async def generate_content(self, model, contents, config):
                self.parent.call_count += 1
                if self.parent.side_effects:
                    effect = self.parent.side_effects.pop(0)
                    if isinstance(effect, Exception):
                        raise effect
                    if callable(effect):
                        return effect()
                    return effect
                return MockResponse()


def _create_http_error(code: int, message: str, headers: dict = None):
    """Helper creating google.genai.errors.APIError with mock response headers."""
    resp = MagicMock()
    resp.headers = headers or {}
    err = errors.APIError(code, {"error": {"message": message, "code": code}}, resp)
    return err


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


@pytest.mark.asyncio
async def test_successful_first_attempt(sample_brief):
    """1. Successful call succeeds on attempt 1 without retries or sleep."""
    client = MockClient([MockResponse()])
    sleep_calls = []

    async def mock_sleep(sec):
        sleep_calls.append(sec)

    provider = GeminiAIProvider(
        api_key="test-api-key",
        client=client,
        max_retries=2,
        sleep_func=mock_sleep,
    )

    result = await provider.generate_content(sample_brief)
    assert result.title == "Public Health Alert"
    assert client.call_count == 1
    assert len(sleep_calls) == 0


@pytest.mark.asyncio
async def test_transient_failure_followed_by_success(sample_brief):
    """2. Transient failure (503) followed by success succeeds on attempt 2 after 1 backoff sleep."""
    err_503 = _create_http_error(503, "Service Unavailable")
    client = MockClient([err_503, MockResponse()])
    sleep_calls = []

    async def mock_sleep(sec):
        sleep_calls.append(sec)

    provider = GeminiAIProvider(
        api_key="test-api-key",
        client=client,
        max_retries=2,
        initial_backoff_seconds=1.0,
        max_backoff_seconds=4.0,
        sleep_func=mock_sleep,
    )

    result = await provider.generate_content(sample_brief)
    assert result.title == "Public Health Alert"
    assert client.call_count == 2
    assert len(sleep_calls) == 1
    assert sleep_calls[0] >= 1.0


@pytest.mark.asyncio
async def test_two_retries_followed_by_success(sample_brief):
    """3. Two transient failures (503, 500) succeed on attempt 3 after 2 backoff sleeps."""
    err_503 = _create_http_error(503, "Service Unavailable")
    err_500 = _create_http_error(500, "Internal Server Error")
    client = MockClient([err_503, err_500, MockResponse()])
    sleep_calls = []

    async def mock_sleep(sec):
        sleep_calls.append(sec)

    provider = GeminiAIProvider(
        api_key="test-api-key",
        client=client,
        max_retries=2,
        initial_backoff_seconds=1.0,
        max_backoff_seconds=8.0,
        sleep_func=mock_sleep,
    )

    result = await provider.generate_content(sample_brief)
    assert result.title == "Public Health Alert"
    assert client.call_count == 3
    assert len(sleep_calls) == 2


@pytest.mark.asyncio
async def test_retry_exhaustion_raises_provider_error(sample_brief):
    """4. Retry exhaustion after 3 total attempts raises AIProviderError with original status code."""
    err_503 = _create_http_error(503, "Service Unavailable")
    client = MockClient([err_503, err_503, err_503])
    sleep_calls = []

    async def mock_sleep(sec):
        sleep_calls.append(sec)

    provider = GeminiAIProvider(
        api_key="test-api-key",
        client=client,
        max_retries=2,
        sleep_func=mock_sleep,
    )

    with pytest.raises(AIProviderError) as exc_info:
        await provider.generate_content(sample_brief)

    assert exc_info.value.status_code == 503
    assert "exhausted" in str(exc_info.value).lower() or "failed after 2 retries" in str(exc_info.value).lower()
    assert client.call_count == 3
    assert len(sleep_calls) == 2


@pytest.mark.asyncio
async def test_http_429_handling_with_retry_after(sample_brief):
    """5. HTTP 429 respects Retry-After header and raises AIProviderQuotaError on exhaustion."""
    err_429_with_header = _create_http_error(429, "Resource Exhausted", headers={"Retry-After": "3.5"})
    client = MockClient([err_429_with_header, err_429_with_header, err_429_with_header])
    sleep_calls = []

    async def mock_sleep(sec):
        sleep_calls.append(sec)

    provider = GeminiAIProvider(
        api_key="test-api-key",
        client=client,
        max_retries=2,
        max_backoff_seconds=10.0,
        sleep_func=mock_sleep,
    )

    with pytest.raises(AIProviderQuotaError) as exc_info:
        await provider.generate_content(sample_brief)

    assert exc_info.value.status_code == 429
    assert client.call_count == 3
    # Check that Retry-After (3.5s) was respected for backoff
    assert sleep_calls[0] == 3.5


@pytest.mark.asyncio
async def test_http_5xx_transient_classification(sample_brief):
    """6. HTTP 500, 502, 504 are treated as transient failures and retried."""
    err_502 = _create_http_error(502, "Bad Gateway")
    client = MockClient([err_502, MockResponse()])
    sleep_calls = []

    async def mock_sleep(sec):
        sleep_calls.append(sec)

    provider = GeminiAIProvider(
        api_key="test-api-key",
        client=client,
        max_retries=2,
        sleep_func=mock_sleep,
    )

    result = await provider.generate_content(sample_brief)
    assert result.title == "Public Health Alert"
    assert client.call_count == 2
    assert len(sleep_calls) == 1


@pytest.mark.asyncio
async def test_network_timeout_handling(sample_brief):
    """7. Network asyncio.TimeoutError is treated as transient and maps to AIProviderTimeoutError on exhaustion."""
    client = MockClient([asyncio.TimeoutError(), asyncio.TimeoutError(), asyncio.TimeoutError()])
    sleep_calls = []

    async def mock_sleep(sec):
        sleep_calls.append(sec)

    provider = GeminiAIProvider(
        api_key="test-api-key",
        client=client,
        max_retries=2,
        sleep_func=mock_sleep,
    )

    with pytest.raises(AIProviderTimeoutError):
        await provider.generate_content(sample_brief)

    assert client.call_count == 3
    assert len(sleep_calls) == 2


@pytest.mark.asyncio
async def test_authentication_failure_no_retry(sample_brief):
    """8. Authentication failure (401 / 403) fails immediately on attempt 1 without retries."""
    err_401 = _create_http_error(401, "API_KEY_INVALID: User not authenticated")
    client = MockClient([err_401])
    sleep_calls = []

    async def mock_sleep(sec):
        sleep_calls.append(sec)

    provider = GeminiAIProvider(
        api_key="invalid-key",
        client=client,
        max_retries=2,
        sleep_func=mock_sleep,
    )

    with pytest.raises(AIProviderError) as exc_info:
        await provider.generate_content(sample_brief)

    assert exc_info.value.status_code == 401
    assert "authentication failure" in str(exc_info.value).lower()
    # Immediate rejection verification
    assert client.call_count == 1
    assert len(sleep_calls) == 0


@pytest.mark.asyncio
async def test_invalid_request_no_retry(sample_brief):
    """9. Invalid request (400 / INVALID_ARGUMENT) fails immediately on attempt 1 without retries."""
    err_400 = _create_http_error(400, "INVALID_ARGUMENT: Prompt exceeds context window")
    client = MockClient([err_400])
    sleep_calls = []

    async def mock_sleep(sec):
        sleep_calls.append(sec)

    provider = GeminiAIProvider(
        api_key="test-key",
        client=client,
        max_retries=2,
        sleep_func=mock_sleep,
    )

    with pytest.raises(AIProviderError) as exc_info:
        await provider.generate_content(sample_brief)

    assert exc_info.value.status_code == 400
    assert "invalid request" in str(exc_info.value).lower()
    assert client.call_count == 1
    assert len(sleep_calls) == 0


@pytest.mark.asyncio
async def test_overall_deadline_exhaustion(sample_brief):
    """10. Deadline exhaustion stops retrying when the overall time budget is exceeded."""
    err_503 = _create_http_error(503, "Service Unavailable")
    client = MockClient([err_503, err_503, err_503])
    
    simulated_clock = 0.0

    def mock_time():
        return simulated_clock

    async def mock_sleep(sec):
        nonlocal simulated_clock
        simulated_clock += sec

    provider = GeminiAIProvider(
        api_key="test-key",
        client=client,
        max_retries=5,
        initial_backoff_seconds=4.0,  # 4s initial backoff exceeds 3.0s deadline
        max_backoff_seconds=10.0,
        overall_deadline_seconds=3.0,  # Strict 3s budget
        sleep_func=mock_sleep,
        time_func=mock_time,
    )

    with pytest.raises(AIProviderTimeoutError) as exc_info:
        await provider.generate_content(sample_brief)

    assert "deadline" in str(exc_info.value).lower() or "timed out" in str(exc_info.value).lower()
    # Stops after attempt 1 because required backoff of >=4.0s immediately exceeds 3.0s deadline!
    assert client.call_count == 1


@pytest.mark.asyncio
async def test_mock_ai_provider_behavior_unchanged(sample_brief):
    """11. MockAIProvider behavior remains completely unchanged and functional."""
    mock_p = MockAIProvider()
    assert mock_p.get_provider_name() == "mock"
    
    # Generation
    gen_result = await mock_p.generate_content(sample_brief)
    assert gen_result.title != ""
    assert gen_result.body != ""
    assert gen_result.channel == "SMS"
    
    # Translation
    trans_req = TranslationRequest(
        source_text="Hello {name}, alert in {city}.",
        source_title="Alert",
        source_language="en",
        target_language="hi",
    )
    trans_result = await mock_p.translate_content(trans_req)
    assert "{name}" in trans_result.body
    assert "{city}" in trans_result.body
    assert trans_result.target_language == "hi"

    # Evaluation
    eval_req = ContentEvaluationRequest(
        title="Notice",
        body="Emergency alert for district.",
        category="Disaster",
        tone="urgent",
        channel="SMS",
        source_language="en",
    )
    eval_result = await mock_p.evaluate_content(eval_req)
    assert len(eval_result.dimension_scores) > 0


def test_credential_sanitization_in_error_messages():
    """12. Verifies that raw API keys are strictly redacted from error messages and logs."""
    raw_api_key = "AIzaSyDummySecretKey1234567890abcdef"
    provider = GeminiAIProvider(
        api_key=raw_api_key,
        client=MagicMock(),
    )
    
    dirty_msg = f"Failed to call https://generativelanguage.googleapis.com/v1beta/models?key={raw_api_key} for {raw_api_key}"
    clean = provider._sanitize_message(dirty_msg)
    
    assert raw_api_key not in clean
    assert "***REDACTED" in clean


@pytest.mark.asyncio
async def test_gemini_translation_retry_and_placeholder_preservation():
    """13. Translation endpoint retries transient errors and preserves placeholders upon success."""
    err_503 = _create_http_error(503, "Service Unavailable")
    trans_response = MockResponse('{"title": "सतर्कता", "body": "नमस्ते {name}, {city} में सहायता केंद्र खुला है।", "summary": "अपडेट", "call_to_action": "सहायता लें"}')
    client = MockClient([err_503, trans_response])
    sleep_calls = []

    async def mock_sleep(sec):
        sleep_calls.append(sec)

    provider = GeminiAIProvider(
        api_key="test-key",
        client=client,
        max_retries=2,
        sleep_func=mock_sleep,
    )

    req = TranslationRequest(
        source_text="Hello {name}, relief center is open in {city}.",
        source_title="Alert",
        source_language="en",
        target_language="hi",
    )
    res = await provider.translate_content(req)
    assert res.target_language == "hi"
    assert "{name}" in res.body
    assert "{city}" in res.body
    assert client.call_count == 2
    assert len(sleep_calls) == 1


@pytest.mark.asyncio
async def test_gemini_evaluation_retry_and_structured_response():
    """14. Evaluation endpoint retries transient errors and parses structured findings."""
    err_502 = _create_http_error(502, "Bad Gateway")
    eval_json = '{"findings": [{"category": "tone", "severity": "medium", "title": "Check tone", "explanation": "A bit urgent", "confidence": 0.9}], "dimension_scores": {"tone_consistency": 85.0}, "summary": "Audit passed"}'
    client = MockClient([err_502, MockResponse(eval_json)])
    sleep_calls = []

    async def mock_sleep(sec):
        sleep_calls.append(sec)

    provider = GeminiAIProvider(
        api_key="test-key",
        client=client,
        max_retries=2,
        sleep_func=mock_sleep,
    )

    req = ContentEvaluationRequest(
        title="Notice",
        body="Emergency alert",
        category="Disaster",
        tone="urgent",
        channel="SMS",
        source_language="en",
    )
    res = await provider.evaluate_content(req)
    assert len(res.findings) == 1
    assert res.findings[0].category == "tone"
    assert res.dimension_scores["tone_consistency"] == 85.0
    assert client.call_count == 2
    assert len(sleep_calls) == 1


@pytest.mark.asyncio
async def test_retry_after_numeric_greater_than_max_backoff(sample_brief):
    """15. Numeric Retry-After longer than max_backoff_seconds is preserved and not clamped down."""
    err_429 = _create_http_error(429, "Resource Exhausted", headers={"Retry-After": "12.0"})
    client = MockClient([err_429, MockResponse()])
    sleep_calls = []

    async def mock_sleep(sec):
        sleep_calls.append(sec)

    provider = GeminiAIProvider(
        api_key="test-api-key",
        client=client,
        max_retries=2,
        max_backoff_seconds=5.0,  # Max backoff is 5s, but upstream instructed 12s
        overall_deadline_seconds=30.0,
        sleep_func=mock_sleep,
    )

    result = await provider.generate_content(sample_brief)
    assert result.title == "Public Health Alert"
    assert client.call_count == 2
    # Full upstream delay of 12.0s must be preserved without premature clamping to 5.0s
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == 12.0


def test_http_date_retry_after_parsing():
    """16. RFC HTTP-date Retry-After header parsing and delay calculation."""
    provider = GeminiAIProvider(api_key="test-api-key", client=MagicMock())

    # Reference fixed time: 2026-11-04 09:40:00 UTC
    fixed_now = datetime(2026, 11, 4, 9, 40, 0, tzinfo=timezone.utc)

    # 1. Valid RFC 1123 / 7231 HTTP-date 15 seconds in future
    date_future_15s = "Wed, 04 Nov 2026 09:40:15 GMT"
    delay = provider._parse_retry_after(date_future_15s, now_dt=fixed_now)
    assert delay == pytest.approx(15.0)

    # 2. Date in the past (delay <= 0) should return None
    date_past = "Wed, 04 Nov 2026 09:39:00 GMT"
    assert provider._parse_retry_after(date_past, now_dt=fixed_now) is None

    # 3. Numeric string still works
    assert provider._parse_retry_after("7.5", now_dt=fixed_now) == 7.5

    # 4. Malformed date string returns None
    assert provider._parse_retry_after("not-a-valid-date", now_dt=fixed_now) is None

    # 5. Empty / None returns None
    assert provider._parse_retry_after(None, now_dt=fixed_now) is None
    assert provider._parse_retry_after("", now_dt=fixed_now) is None


@pytest.mark.asyncio
async def test_retry_after_delay_exceeds_overall_deadline(sample_brief):
    """17. Retry-After delay exceeding overall deadline stops retrying immediately and raises AIProviderQuotaError."""
    err_429 = _create_http_error(429, "Resource Exhausted", headers={"Retry-After": "25.0"})
    client = MockClient([err_429, MockResponse()])
    sleep_calls = []

    async def mock_sleep(sec):
        sleep_calls.append(sec)

    provider = GeminiAIProvider(
        api_key="test-api-key",
        client=client,
        max_retries=3,
        overall_deadline_seconds=10.0,  # 10s deadline cannot fit 25s delay
        sleep_func=mock_sleep,
    )

    with pytest.raises(AIProviderQuotaError) as exc_info:
        await provider.generate_content(sample_brief)

    # Stops immediately after attempt 1
    assert client.call_count == 1
    assert len(sleep_calls) == 0
    assert "rate limit exceeded" in str(exc_info.value).lower()
    assert "deadline" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_strict_timeout_enforcement_below_tenth_second(sample_brief):
    """18. Strict timeout enforcement ensures attempt timeout <= remaining budget even below 0.1s without artificial floor."""
    timeout_observed = []

    client = MockClient([MockResponse()])

    # Start at t=0, then advance to t=9.96 (leaving 0.04s out of 10.0s overall deadline)
    clock_readings = [0.0, 9.96, 9.96, 9.96]

    def mock_time():
        if len(clock_readings) > 1:
            return clock_readings.pop(0)
        return clock_readings[0]

    provider = GeminiAIProvider(
        api_key="test-api-key",
        client=client,
        timeout_seconds=5.0,
        overall_deadline_seconds=10.0,
        time_func=mock_time,
    )

    orig_wait_for = asyncio.wait_for

    async def capturing_wait_for(fut, timeout):
        timeout_observed.append(timeout)
        return await orig_wait_for(fut, timeout=timeout)

    with patch("asyncio.wait_for", side_effect=capturing_wait_for):
        result = await provider.generate_content(sample_brief)

    assert result.title == "Public Health Alert"
    assert len(timeout_observed) == 1
    # Must be exactly 0.04s, NOT clamped up to 0.1s!
    assert timeout_observed[0] == pytest.approx(0.04, abs=1e-4)


@pytest.mark.asyncio
async def test_deadline_exhaustion_prior_to_initiating_request(sample_brief):
    """19. When remaining budget <= 0 before attempt 1, request is never initiated."""
    client = MockClient([MockResponse()])

    # Start at t=0, then advance to t=10.5 (budget exhausted before attempt 1)
    clock_readings = [0.0, 10.5]

    def mock_time():
        if len(clock_readings) > 1:
            return clock_readings.pop(0)
        return clock_readings[0]

    provider = GeminiAIProvider(
        api_key="test-api-key",
        client=client,
        overall_deadline_seconds=10.0,
        time_func=mock_time,
    )

    with pytest.raises(AIProviderTimeoutError) as exc_info:
        await provider.generate_content(sample_brief)

    assert "deadline" in str(exc_info.value).lower() or "timed out" in str(exc_info.value).lower()
    # Client must never have been called!
    assert client.call_count == 0


def test_credential_redaction_bearer_token_and_query_params():
    """20. Comprehensive redaction of Bearer tokens (with slashes, pluses, equals, quotes), query parameters, and API keys."""
    raw_key = "AIzaSyDummySecretKey1234567890abcdef"
    provider = GeminiAIProvider(
        api_key=raw_key,
        client=MagicMock(),
    )

    # 1. Bearer tokens: test forward slashes, pluses, equals, and quotes
    # Requirement: Authorization: Bearer abc/def+123= must redact the entire token including after /
    bearer_slash = "Authorization: Bearer abc/def+123="
    sanitized_slash = provider._sanitize_message(bearer_slash)
    assert sanitized_slash == "Authorization: Bearer ***REDACTED_TOKEN***"
    assert "abc" not in sanitized_slash
    assert "def+123=" not in sanitized_slash

    # Quoted tokens (double and single quotes)
    bearer_double_quoted = 'Authorization: Bearer "abc/def+123="'
    sanitized_dq = provider._sanitize_message(bearer_double_quoted)
    assert sanitized_dq == 'Authorization: Bearer "***REDACTED_TOKEN***"'
    assert "abc/def+123=" not in sanitized_dq

    bearer_single_quoted = "Authorization: Bearer 'abc/def+123='"
    sanitized_sq = provider._sanitize_message(bearer_single_quoted)
    assert sanitized_sq == "Authorization: Bearer '***REDACTED_TOKEN***'"
    assert "abc/def+123=" not in sanitized_sq

    # URL-encoded Bearer tokens
    bearer_urlencoded = "bearer secret%2Ftoken%2B123%3D"
    sanitized_ue = provider._sanitize_message(bearer_urlencoded)
    assert sanitized_ue == "bearer ***REDACTED_TOKEN***"
    assert "secret%2F" not in sanitized_ue

    # Standard JWT
    bearer_jwt = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secretpayload.signature"
    sanitized_jwt = provider._sanitize_message(bearer_jwt)
    assert sanitized_jwt == "Authorization: Bearer ***REDACTED_TOKEN***"
    assert "eyJhbGciOi" not in sanitized_jwt
    assert "signature" not in sanitized_jwt

    # 2. Query credentials: key=, api_key=, secret=, client_secret=, access_token= (plain and URL-encoded)
    query_msg = (
        "Failed request: https://generativelanguage.googleapis.com/v1beta/models"
        "?key=AIza%2Fencoded%2Bsecret%3D"
        "&api_key=plain_key_123"
        "&secret=topsecret"
        "&client_secret=client_sec_secret_456"
        "&access_token=ya29.access_token_val%2F789"
    )
    sanitized_query = provider._sanitize_message(query_msg)
    assert "key=***REDACTED***" in sanitized_query
    assert "api_key=***REDACTED***" in sanitized_query
    assert "secret=***REDACTED***" in sanitized_query
    assert "client_secret=***REDACTED***" in sanitized_query
    assert "access_token=***REDACTED***" in sanitized_query
    assert "plain_key_123" not in sanitized_query
    assert "topsecret" not in sanitized_query
    assert "AIza%2F" not in sanitized_query
    assert "client_sec_secret_456" not in sanitized_query
    assert "ya29.access_token_val" not in sanitized_query

    # 3. Google API key masking
    key_msg = f"Request to endpoint with {raw_key} failed"
    sanitized_key = provider._sanitize_message(key_msg)
    assert raw_key not in sanitized_key
    assert "***REDACTED_API_KEY***" in sanitized_key


@pytest.mark.asyncio
async def test_real_logging_captures_records_and_redacts_secrets(caplog, sample_brief):
    """21. Real execution under generate_content emits actual log records with raw secrets redacted."""
    raw_secret_key = "AIzaSySecretLeakInLogs12345"
    raw_bearer = "secret_jwt_token_logs_456"

    # Upstream error carrying simulated sensitive credentials in its message
    err_503 = _create_http_error(
        503,
        f"Service Unavailable: upstream https://generativelanguage.googleapis.com/v1?key={raw_secret_key} failed with Bearer {raw_bearer}",
    )
    client = MockClient([err_503, MockResponse()])

    provider = GeminiAIProvider(
        api_key="test-api-key",
        client=client,
        max_retries=1,
        initial_backoff_seconds=0.01,
    )

    with caplog.at_level(logging.WARNING):
        result = await provider.generate_content(sample_brief)

    assert result.title == "Public Health Alert"
    assert client.call_count == 2

    # Assert that actual log records were emitted during real provider execution
    assert len(caplog.records) > 0
    assert any("attempt 1/2 failed" in rec.message for rec in caplog.records)

    # Assert that none of the simulated secrets appear in any captured log records
    assert raw_secret_key not in caplog.text
    assert raw_bearer not in caplog.text

    # Assert that sanitized redaction tokens appear in place of raw secrets
    assert "key=***REDACTED***" in caplog.text
    assert "Bearer ***REDACTED_TOKEN***" in caplog.text


@pytest.mark.asyncio
async def test_traceback_formatting_suppresses_raw_sdk_exception_secrets(sample_brief):
    """22. Traceback formatting via standard traceback module does not expose raw SDK secrets due to 'from None'."""
    raw_secret_traceback = "AIzaSySecretInTraceback12345678"
    raw_bearer_traceback = "Bearer raw_secret_token_in_traceback_999"

    # 1. Non-transient error (400)
    err_400 = _create_http_error(
        400,
        f"INVALID_ARGUMENT: https://generativelanguage.googleapis.com/v1?key={raw_secret_traceback} with {raw_bearer_traceback}",
    )
    client_400 = MockClient([err_400])
    provider_400 = GeminiAIProvider(api_key="test-key", client=client_400, max_retries=1)

    with pytest.raises(AIProviderError) as exc_info_400:
        await provider_400.generate_content(sample_brief)

    # Format traceback as Python/FastAPI/logging would render it
    tb_400 = "".join(traceback.format_exception(exc_info_400.value))

    # Verify context suppression: __cause__ is None and __suppress_context__ is True
    assert exc_info_400.value.__cause__ is None
    assert exc_info_400.value.__suppress_context__ is True

    # Raw secrets must NOT be in the formatted traceback string
    assert raw_secret_traceback not in tb_400
    assert "raw_secret_token_in_traceback_999" not in tb_400

    # 2. Retry exhaustion error (503)
    raw_secret_exhaust = "secret_in_retry_exhaustion_999"
    err_503 = _create_http_error(503, f"Service Unavailable: key={raw_secret_exhaust} Bearer raw_bearer_exhaust_token_123")
    client_exhaust = MockClient([err_503, err_503])
    provider_exhaust = GeminiAIProvider(
        api_key="test-key",
        client=client_exhaust,
        max_retries=1,
        initial_backoff_seconds=0.01,
    )

    with pytest.raises(AIProviderError) as exc_info_exhaust:
        await provider_exhaust.generate_content(sample_brief)

    tb_exhaust = "".join(traceback.format_exception(exc_info_exhaust.value))
    assert exc_info_exhaust.value.__cause__ is None
    assert exc_info_exhaust.value.__suppress_context__ is True
    assert raw_secret_exhaust not in tb_exhaust
    assert "raw_bearer_exhaust_token_123" not in tb_exhaust

