"""WhatsAppChannel adapter supporting Mock/Demo mode and Meta WhatsApp Business Cloud API."""

from __future__ import annotations
import re
import uuid
import logging
from typing import Optional, Dict, Any, Tuple
import httpx
from app.services.channels.base import BaseChannel, ChannelSendResult

logger = logging.getLogger("masscommai.whatsapp_channel")
PHONE_REGEX = re.compile(r"^\+?[0-9]{10,15}$")


class WhatsAppChannel(BaseChannel):
    """
    Channel adapter for WhatsApp distribution supporting Mock/Demo mode
    and Meta WhatsApp Business Cloud API (Graph API v21.0).
    """

    def __init__(
        self,
        provider_type: str = "mock",
        sender_address: str = "+1555010099",
        sender_name: str = "Civora WhatsApp Official",
        credentials: Optional[Dict[str, Any]] = None,
    ):
        self.provider_type = provider_type.lower().strip()
        self.sender_address = sender_address.strip()
        self.sender_name = sender_name.strip()
        self.credentials = credentials or {}

    def get_channel_name(self) -> str:
        return "WhatsApp"

    def validate_recipient(self, recipient: Any) -> Tuple[bool, Optional[str]]:
        """Validates recipient WhatsApp phone number."""
        phone = getattr(recipient, "phone", None) or getattr(recipient, "address", None)
        if not phone or not isinstance(phone, str) or not phone.strip():
            return False, "Recipient phone number is missing or empty for WhatsApp."
        clean = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if "fail_perm" in clean or "fail_temp" in clean or "fail_wa" in clean:
            return True, None
        if not PHONE_REGEX.match(clean):
            return False, f"Invalid phone number format: '{phone}'. Expected 10-15 digits (E.164)."
        return True, None

    async def send(self, message: Any, recipient: Any) -> ChannelSendResult:
        """Dispatches a WhatsApp message to the recipient."""
        is_valid, validation_err = self.validate_recipient(recipient)
        if not is_valid:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name=f"whatsapp_{self.provider_type}",
                error_code="INVALID_WHATSAPP_NUMBER",
                error_message=validation_err,
            )

        raw_phone = (getattr(recipient, "phone", None) or getattr(recipient, "address", "")).strip()
        clean_phone = raw_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        body = getattr(message, "rendered_content", None) or getattr(message, "body", "")
        tracking_id = getattr(message, "tracking_id", None) or f"trk_{uuid.uuid4().hex[:16]}"
        template_name = getattr(message, "template_name", None) or self.credentials.get("template_name")
        template_lang = getattr(message, "language", None) or self.credentials.get("template_language", "en")

        return await self._dispatch(
            recipient_phone=clean_phone,
            body=body,
            tracking_id=tracking_id,
            template_name=template_name,
            template_language=template_lang,
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
        """Sends an administrative test WhatsApp message."""
        clean = destination.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not clean or not PHONE_REGEX.match(clean):
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="whatsapp_validator",
                error_code="INVALID_TEST_DESTINATION",
                error_message=f"Test recipient '{destination}' is not a valid 10-15 digit phone number.",
            )

        override = config_override or {}
        provider = (override.get("provider_type") or self.provider_type).lower().strip()
        sender_addr = override.get("sender_address") or self.sender_address
        creds = override.get("credentials") or self.credentials
        tracking_id = f"test_{uuid.uuid4().hex[:12]}"

        return await self._dispatch(
            recipient_phone=clean,
            body=body,
            tracking_id=tracking_id,
            template_name=creds.get("template_name"),
            template_language=creds.get("template_language", "en"),
            provider_type=provider,
            sender_address=sender_addr,
            credentials=creds,
        )

    async def _dispatch(
        self,
        recipient_phone: str,
        body: str,
        tracking_id: str,
        template_name: Optional[str],
        template_language: str,
        provider_type: str,
        sender_address: str,
        credentials: Dict[str, Any],
    ) -> ChannelSendResult:
        if provider_type == "meta":
            return await self._dispatch_meta(
                recipient_phone=recipient_phone,
                body=body,
                tracking_id=tracking_id,
                template_name=template_name,
                template_language=template_language,
                sender_address=sender_address,
                credentials=credentials,
            )
        else:
            return self._dispatch_mock(recipient_phone, body, tracking_id)

    def _dispatch_mock(self, recipient_phone: str, body: str, tracking_id: str) -> ChannelSendResult:
        if "fail_perm" in recipient_phone or "fail_wa" in recipient_phone:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="whatsapp_mock",
                error_code="USER_NOT_REGISTERED_ON_WHATSAPP",
                error_message="Meta Graph API Error 131026: User phone is not associated with an active WhatsApp account.",
                metadata={"recipient": recipient_phone, "tracking_id": tracking_id},
            )

        if "fail_temp" in recipient_phone:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="whatsapp_mock",
                error_code="WHATSAPP_SESSION_BUSY",
                error_message="Meta Graph API Error 131051: Service overloaded. Message queued for resend.",
                metadata={"recipient": recipient_phone, "tracking_id": tracking_id},
            )

        wamid = f"wamid.{uuid.uuid4().hex}"
        return ChannelSendResult(
            success=True,
            status="Sent",
            provider_name="whatsapp_mock",
            provider_message_id=wamid,
            metadata={
                "channel": "WhatsApp",
                "recipient": recipient_phone,
                "tracking_id": tracking_id,
                "simulated_delivery": True,
            },
        )

    async def _dispatch_meta(
        self,
        recipient_phone: str,
        body: str,
        tracking_id: str,
        template_name: Optional[str],
        template_language: str,
        sender_address: str,
        credentials: Dict[str, Any],
    ) -> ChannelSendResult:
        phone_number_id = credentials.get("phone_number_id") or sender_address
        access_token = credentials.get("access_token")

        if not phone_number_id or not access_token:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="whatsapp_meta",
                error_code="MISSING_CREDENTIALS",
                error_message="Meta WhatsApp Cloud API requires 'phone_number_id' and 'access_token'.",
            )

        url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Format recipient: ensure no '+' in 'to' field for Meta API
        to_phone = recipient_phone.lstrip("+")

        if template_name:
            payload: Dict[str, Any] = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to_phone,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": template_language},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": body[:1024]}
                            ]
                        }
                    ],
                },
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to_phone,
                "type": "text",
                "text": {"preview_url": False, "body": body[:4096]},
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload, headers=headers)

            if res.status_code in (200, 201, 202):
                data = res.json()
                messages_data = data.get("messages", [])
                wamid = messages_data[0].get("id") if messages_data else f"wamid.{uuid.uuid4().hex}"
                return ChannelSendResult(
                    success=True,
                    status="Sent",
                    provider_name="whatsapp_meta",
                    provider_message_id=wamid,
                    metadata={"tracking_id": tracking_id, "meta_response": data},
                )
            else:
                err_data = res.json().get("error", {})
                return ChannelSendResult(
                    success=False,
                    status="Failed",
                    provider_name="whatsapp_meta",
                    error_code=str(err_data.get("code", "META_API_ERROR")),
                    error_message=err_data.get("message", res.text[:200]),
                )
        except Exception as exc:
            logger.error("Meta WhatsApp dispatch exception: %s", exc)
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="whatsapp_meta",
                error_code="CONNECTION_ERROR",
                error_message=str(exc),
            )
