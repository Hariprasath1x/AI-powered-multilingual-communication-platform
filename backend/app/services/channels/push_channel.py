"""PushChannel adapter supporting Mock/Demo mode and Firebase Cloud Messaging (FCM)."""

from __future__ import annotations
import uuid
import logging
from typing import Optional, Dict, Any, Tuple
import httpx
from app.services.channels.base import BaseChannel, ChannelSendResult

logger = logging.getLogger("masscommai.push_channel")


class PushChannel(BaseChannel):
    """
    Channel adapter for Push Notifications supporting Mock mode and Firebase Cloud Messaging (FCM).
    """

    def __init__(
        self,
        provider_type: str = "mock",
        sender_address: str = "masscommai-fcm-project",
        sender_name: str = "MassCommAI Citizen Push",
        credentials: Optional[Dict[str, Any]] = None,
    ):
        self.provider_type = provider_type.lower().strip()
        self.sender_address = sender_address.strip()
        self.sender_name = sender_name.strip()
        self.credentials = credentials or {}

    def get_channel_name(self) -> str:
        return "Push"

    def _resolve_token(self, recipient: Any) -> Optional[str]:
        """Extracts device token from an audience member, user, or dictionary."""
        if isinstance(recipient, str):
            return recipient.strip() or None

        # Check direct token attributes
        token = (
            getattr(recipient, "device_token", None)
            or getattr(recipient, "token", None)
            or getattr(recipient, "push_token", None)
        )
        if token and isinstance(token, str) and token.strip():
            return token.strip()

        # Check if recipient has device_tokens relationship
        device_tokens = getattr(recipient, "device_tokens", None)
        if device_tokens:
            for dt in device_tokens:
                if getattr(dt, "is_active", True) and getattr(dt, "token", None):
                    return dt.token.strip()

        # Check address attribute if formatted as push token
        addr = getattr(recipient, "address", None)
        if addr and isinstance(addr, str) and (addr.startswith("fcm_") or addr.startswith("token_") or len(addr) > 30):
            return addr.strip()

        return None

    def validate_recipient(self, recipient: Any) -> Tuple[bool, Optional[str]]:
        """Validates that recipient has an active device token."""
        token = self._resolve_token(recipient)
        if not token:
            return False, "Recipient has no registered device token for Push notification."
        return True, None

    async def send(self, message: Any, recipient: Any) -> ChannelSendResult:
        """Dispatches a push notification to the recipient device."""
        token = self._resolve_token(recipient)
        if not token:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name=f"push_{self.provider_type}",
                error_code="MISSING_DEVICE_TOKEN",
                error_message="Recipient has no registered device token for Push notification.",
            )

        body = getattr(message, "rendered_content", None) or getattr(message, "body", "")
        subject = getattr(message, "title", None) or getattr(message, "subject", None) or self.sender_name
        tracking_id = getattr(message, "tracking_id", None) or f"trk_{uuid.uuid4().hex[:16]}"

        return await self._dispatch(
            device_token=token,
            title=subject,
            body=body,
            tracking_id=tracking_id,
            provider_type=self.provider_type,
            sender_address=self.sender_address,
            credentials=self.credentials,
        )

    async def send_test(
        self,
        destination: str,
        body: str,
        subject: Optional[str] = None,
        config_override: Optional[Dict[str, Any]] = None,
    ) -> ChannelSendResult:
        """Sends an administrative test push notification."""
        token = destination.strip()
        if not token:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="push_validator",
                error_code="INVALID_TEST_DESTINATION",
                error_message="Test device token cannot be empty.",
            )

        override = config_override or {}
        provider = (override.get("provider_type") or self.provider_type).lower().strip()
        sender_addr = override.get("sender_address") or self.sender_address
        creds = override.get("credentials") or self.credentials
        title = subject or override.get("sender_name") or self.sender_name
        tracking_id = f"test_{uuid.uuid4().hex[:12]}"

        return await self._dispatch(
            device_token=token,
            title=title,
            body=body,
            tracking_id=tracking_id,
            provider_type=provider,
            sender_address=sender_addr,
            credentials=creds,
        )

    async def _dispatch(
        self,
        device_token: str,
        title: str,
        body: str,
        tracking_id: str,
        provider_type: str,
        sender_address: str,
        credentials: Dict[str, Any],
    ) -> ChannelSendResult:
        if provider_type == "fcm":
            return await self._dispatch_fcm(
                device_token=device_token,
                title=title,
                body=body,
                tracking_id=tracking_id,
                sender_address=sender_address,
                credentials=credentials,
            )
        else:
            return self._dispatch_mock(device_token, title, body, tracking_id)

    def _dispatch_mock(
        self,
        device_token: str,
        title: str,
        body: str,
        tracking_id: str,
    ) -> ChannelSendResult:
        if "fail_perm" in device_token:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="push_mock",
                error_code="DEVICE_TOKEN_INVALID",
                error_message="FCM error: Registration token is unregistered or expired.",
                metadata={"token": device_token, "tracking_id": tracking_id},
            )

        if "fail_temp" in device_token:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="push_mock",
                error_code="GATEWAY_TIMEOUT",
                error_message="Push notification gateway response timed out. Resend permissible.",
                metadata={"token": device_token, "tracking_id": tracking_id},
            )

        msg_id = f"mock-fcm-{uuid.uuid4().hex[:12]}"
        return ChannelSendResult(
            success=True,
            status="Sent",
            provider_name="push_mock",
            provider_message_id=msg_id,
            metadata={
                "channel": "Push",
                "device_token": device_token,
                "tracking_id": tracking_id,
                "simulated_delivery": True,
            },
        )

    async def _dispatch_fcm(
        self,
        device_token: str,
        title: str,
        body: str,
        tracking_id: str,
        sender_address: str,
        credentials: Dict[str, Any],
    ) -> ChannelSendResult:
        project_id = credentials.get("project_id") or sender_address
        server_key = credentials.get("server_key") or credentials.get("access_token")

        if not project_id:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="push_fcm",
                error_code="MISSING_FCM_PROJECT_ID",
                error_message="FCM provider requires 'project_id' in configuration.",
            )

        url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {server_key}" if server_key else "",
        }

        payload = {
            "message": {
                "token": device_token,
                "notification": {
                    "title": title,
                    "body": body[:500],
                },
                "data": {
                    "tracking_id": tracking_id,
                },
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload, headers=headers)

            if res.status_code in (200, 201, 202):
                data = res.json()
                msg_name = data.get("name") or f"projects/{project_id}/messages/{uuid.uuid4().hex[:12]}"
                return ChannelSendResult(
                    success=True,
                    status="Sent",
                    provider_name="push_fcm",
                    provider_message_id=msg_name,
                    metadata={"tracking_id": tracking_id, "fcm_response": data},
                )
            else:
                data = res.json()
                err_status = data.get("error", {}).get("status", "FCM_ERROR")
                err_msg = data.get("error", {}).get("message", res.text[:200])
                error_code = "DEVICE_TOKEN_INVALID" if err_status in ("UNREGISTERED", "INVALID_ARGUMENT", "NOT_FOUND") else err_status

                return ChannelSendResult(
                    success=False,
                    status="Failed",
                    provider_name="push_fcm",
                    error_code=error_code,
                    error_message=err_msg,
                )
        except Exception as exc:
            logger.error("FCM dispatch exception: %s", exc)
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="push_fcm",
                error_code="CONNECTION_ERROR",
                error_message=str(exc),
            )
