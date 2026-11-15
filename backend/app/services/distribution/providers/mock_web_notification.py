"""Deterministic Mock Web Notification Provider Adapter."""

import uuid
from app.services.distribution.providers.base_provider import (
    BaseDeliveryProvider,
    DeliveryPayload,
    DeliveryResult,
)


class MockWebNotificationProvider(BaseDeliveryProvider):
    """Mock Web Notification provider simulating in-browser push and portal broadcast."""

    def get_provider_name(self) -> str:
        return "mock_web_notification"

    def get_channel(self) -> str:
        return "Web"

    def validate_address(self, address: str) -> bool:
        return bool(address and address.strip())

    async def send_message(self, payload: DeliveryPayload) -> DeliveryResult:
        addr = payload.recipient_address.strip()

        if not self.validate_address(addr):
            return DeliveryResult(
                success=False,
                status="failed",
                provider_name=self.get_provider_name(),
                provider_reference=f"mock-err-{uuid.uuid4().hex[:10]}",
                error_code="EMPTY_RECIPIENT_IDENTIFIER",
                error_message="Web notifications require a valid recipient identifier.",
                is_retryable=False,
            )

        if "fail_perm" in addr:
            return DeliveryResult(
                success=False,
                status="failed",
                provider_name=self.get_provider_name(),
                provider_reference=f"mock-web-err-{uuid.uuid4().hex[:10]}",
                error_code="DEVICE_TOKEN_INVALID",
                error_message="FCM/APNs error: Registration token is unregistered or expired.",
                is_retryable=False,
            )

        if "fail_temp" in addr or payload.metadata.get("simulate_retryable_error"):
            return DeliveryResult(
                success=False,
                status="failed",
                provider_name=self.get_provider_name(),
                provider_reference=f"mock-web-err-{uuid.uuid4().hex[:10]}",
                error_code="GATEWAY_TIMEOUT",
                error_message="Push notification gateway response timed out. Resend permissible.",
                is_retryable=True,
            )

        ref = f"mock-push-{uuid.uuid4().hex[:12]}"
        return DeliveryResult(
            success=True,
            status="delivered",
            provider_name=self.get_provider_name(),
            provider_reference=ref,
            response_metadata={
                "channel": "Web",
                "notification_id": ref,
                "simulated_delivery": True,
            },
        )

