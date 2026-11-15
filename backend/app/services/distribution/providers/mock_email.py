"""Deterministic Mock Email Delivery Provider Adapter."""

import re
import uuid
from app.services.distribution.providers.base_provider import (
    BaseDeliveryProvider,
    DeliveryPayload,
    DeliveryResult,
)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class MockEmailProvider(BaseDeliveryProvider):
    """Mock Email provider simulating SMTP/API dispatch without network requests."""

    def get_provider_name(self) -> str:
        return "mock_email"

    def get_channel(self) -> str:
        return "Email"

    def validate_address(self, address: str) -> bool:
        if not address:
            return False
        return bool(EMAIL_REGEX.match(address.strip()))

    async def send_message(self, payload: DeliveryPayload) -> DeliveryResult:
        addr = payload.recipient_address.strip().lower()

        # Format check
        if not self.validate_address(addr):
            return DeliveryResult(
                success=False,
                status="failed",
                provider_name=self.get_provider_name(),
                provider_reference=f"mock-err-{uuid.uuid4().hex[:10]}",
                error_code="INVALID_EMAIL_FORMAT",
                error_message=f"Destination address '{payload.recipient_address}' is not a valid email.",
                is_retryable=False,
            )

        # Deterministic simulation triggers
        if "fail_perm" in addr:
            return DeliveryResult(
                success=False,
                status="failed",
                provider_name=self.get_provider_name(),
                provider_reference=f"mock-smtp-{uuid.uuid4().hex[:10]}",
                error_code="RECIPIENT_MAILBOX_NOT_FOUND",
                error_message="SMTP 550: Mailbox unavailable or rejected by destination server.",
                is_retryable=False,
            )

        if "fail_temp" in addr or payload.metadata.get("simulate_retryable_error"):
            return DeliveryResult(
                success=False,
                status="failed",
                provider_name=self.get_provider_name(),
                provider_reference=f"mock-smtp-{uuid.uuid4().hex[:10]}",
                error_code="SMTP_421_SERVICE_BUSY",
                error_message="SMTP 421: Connection limit reached, server temporarily busy.",
                is_retryable=True,
            )

        # Successful delivery
        ref = f"mock-msg-{uuid.uuid4().hex[:12]}"
        return DeliveryResult(
            success=True,
            status="delivered",
            provider_name=self.get_provider_name(),
            provider_reference=ref,
            response_metadata={
                "channel": "Email",
                "message_id": ref,
                "simulated_delivery": True,
            },
        )

