"""Deterministic Mock WhatsApp Delivery Provider Adapter."""

import re
import uuid
from app.services.distribution.providers.base_provider import (
    BaseDeliveryProvider,
    DeliveryPayload,
    DeliveryResult,
)

PHONE_REGEX = re.compile(r"^\+?[0-9]{10,15}$")


class MockWhatsAppProvider(BaseDeliveryProvider):
    """Mock WhatsApp Business API provider simulating templated broadcast."""

    def get_provider_name(self) -> str:
        return "mock_whatsapp"

    def get_channel(self) -> str:
        return "WhatsApp"

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
                provider_reference=f"mock-wa-err-{uuid.uuid4().hex[:10]}",
                error_code="USER_NOT_REGISTERED_ON_WHATSAPP",
                error_message="Meta Graph API Error 131026: User phone is not associated with an active WhatsApp account.",
                is_retryable=False,
            )

        if "fail_temp" in addr or payload.metadata.get("simulate_retryable_error"):
            return DeliveryResult(
                success=False,
                status="failed",
                provider_name=self.get_provider_name(),
                provider_reference=f"mock-wa-err-{uuid.uuid4().hex[:10]}",
                error_code="WHATSAPP_SESSION_BUSY",
                error_message="Meta Graph API Error 131051: Service overloaded. Message queued for resend.",
                is_retryable=True,
            )

        if not self.validate_address(addr):
            return DeliveryResult(
                success=False,
                status="failed",
                provider_name=self.get_provider_name(),
                provider_reference=f"mock-err-{uuid.uuid4().hex[:10]}",
                error_code="INVALID_WHATSAPP_NUMBER",
                error_message=f"Phone number '{addr}' is invalid for WhatsApp dispatch.",
                is_retryable=False,
            )

        ref = f"mock-wamid-{uuid.uuid4().hex[:14]}"
        return DeliveryResult(
            success=True,
            status="delivered",
            provider_name=self.get_provider_name(),
            provider_reference=ref,
            response_metadata={
                "channel": "WhatsApp",
                "wamid": ref,
                "simulated_delivery": True,
            },
        )
