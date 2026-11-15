"""Deterministic Mock Voice Telephony Provider Adapter."""

import re
import uuid
from app.services.distribution.providers.base_provider import (
    BaseDeliveryProvider,
    DeliveryPayload,
    DeliveryResult,
)

PHONE_REGEX = re.compile(r"^\+?[0-9]{10,15}$")


class MockVoiceProvider(BaseDeliveryProvider):
    """Mock Voice Telephony provider simulating spoken text-to-speech calls."""

    def get_provider_name(self) -> str:
        return "mock_voice"

    def get_channel(self) -> str:
        return "Voice"

    def validate_address(self, address: str) -> bool:
        if not address:
            return False
        clean = address.strip().replace(" ", "").replace("-", "")
        return bool(PHONE_REGEX.match(clean))

    async def send_message(self, payload: DeliveryPayload) -> DeliveryResult:
        addr = payload.recipient_address.strip()

        if "fail_perm" in addr:
            return DeliveryResult(
                success=False,
                status="failed",
                provider_name=self.get_provider_name(),
                provider_reference=f"mock-call-err-{uuid.uuid4().hex[:10]}",
                error_code="TELEPHONY_DISCONNECTED_NUMBER",
                error_message="SIP 404 Not Found: Telephone number is permanently disconnected.",
                is_retryable=False,
            )

        if "fail_temp" in addr or payload.metadata.get("simulate_retryable_error"):
            return DeliveryResult(
                success=False,
                status="failed",
                provider_name=self.get_provider_name(),
                provider_reference=f"mock-call-err-{uuid.uuid4().hex[:10]}",
                error_code="TELEPHONY_LINE_BUSY",
                error_message="SIP 486 Busy Here: Recipient line is engaged. Retry scheduled.",
                is_retryable=True,
            )

        if not self.validate_address(addr):
            return DeliveryResult(
                success=False,
                status="failed",
                provider_name=self.get_provider_name(),
                provider_reference=f"mock-err-{uuid.uuid4().hex[:10]}",
                error_code="INVALID_TELEPHONY_NUMBER",
                error_message=f"Phone number '{addr}' is not dialable.",
                is_retryable=False,
            )

        ref = f"mock-call-{uuid.uuid4().hex[:12]}"
        word_count = len(payload.body.split())
        est_duration = max(5, int((word_count / 150) * 60))

        return DeliveryResult(
            success=True,
            status="delivered",
            provider_name=self.get_provider_name(),
            provider_reference=ref,
            response_metadata={
                "channel": "Voice",
                "call_sid": ref,
                "call_duration_seconds": est_duration,
                "speech_rate_wpm": 150,
                "simulated_delivery": True,
            },
        )
