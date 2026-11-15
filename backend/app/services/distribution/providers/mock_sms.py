"""Deterministic Mock SMS Delivery Provider Adapter."""

import re
import uuid
from app.services.distribution.providers.base_provider import (
    BaseDeliveryProvider,
    DeliveryPayload,
    DeliveryResult,
)
from app.services.channel_constraints import calculate_sms_metrics

PHONE_REGEX = re.compile(r"^\+?[0-9]{10,15}$")


class MockSMSProvider(BaseDeliveryProvider):
    """Mock SMS provider simulating telecom gateway dispatch without external network calls."""

    def get_provider_name(self) -> str:
        return "mock_sms"

    def get_channel(self) -> str:
        return "SMS"

    def validate_address(self, address: str) -> bool:
        if not address:
            return False
        clean = address.strip().replace(" ", "").replace("-", "")
        return bool(PHONE_REGEX.match(clean))

    async def send_message(self, payload: DeliveryPayload) -> DeliveryResult:
        addr = payload.recipient_address.strip()

        # Deterministic simulation triggers
        if "fail_perm" in addr:
            return DeliveryResult(
                success=False,
                status="failed",
                provider_name=self.get_provider_name(),
                provider_reference=f"mock-sms-err-{uuid.uuid4().hex[:10]}",
                error_code="CARRIER_UNREACHABLE_DESTINATION",
                error_message="Telecom operator code 30005: Destination handset is not active or blacklisted.",
                is_retryable=False,
            )

        if "fail_temp" in addr or payload.metadata.get("simulate_retryable_error"):
            return DeliveryResult(
                success=False,
                status="failed",
                provider_name=self.get_provider_name(),
                provider_reference=f"mock-sms-err-{uuid.uuid4().hex[:10]}",
                error_code="CARRIER_RATE_LIMIT_EXCEEDED",
                error_message="Gateway code 429: Operator throughput throttled. Retry recommended.",
                is_retryable=True,
            )

        # Format validation
        if not self.validate_address(addr):
            return DeliveryResult(
                success=False,
                status="failed",
                provider_name=self.get_provider_name(),
                provider_reference=f"mock-err-{uuid.uuid4().hex[:10]}",
                error_code="INVALID_PHONE_NUMBER",
                error_message=f"Destination '{addr}' is not a valid E.164 phone number.",
                is_retryable=False,
            )

        ref = f"mock-sms-{uuid.uuid4().hex[:12]}"
        return DeliveryResult(
            success=True,
            status="delivered",
            provider_name=self.get_provider_name(),
            provider_reference=ref,
            response_metadata={
                "channel": "SMS",
                "segment_count": max(1, calculate_sms_metrics(payload.body or "").segment_count),
                "simulated_delivery": True,
            },
        )
