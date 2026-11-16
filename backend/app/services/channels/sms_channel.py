"""SMSChannel implementation with support for Mock, Twilio, and Fast2SMS providers."""

from __future__ import annotations
import re
import uuid
import logging
from typing import Optional, Dict, Any, Tuple
import httpx
from app.services.channels.base import BaseChannel, ChannelSendResult
from app.services.channel_constraints import calculate_sms_metrics

logger = logging.getLogger("masscommai.sms_channel")
PHONE_REGEX = re.compile(r"^\+?[0-9]{10,15}$")


class SMSChannel(BaseChannel):
    """
    Channel adapter for SMS distribution supporting Mock/Demo mode,
    Twilio Cloud Communications API, and Fast2SMS Indian SMS gateway.
    """

    def __init__(
        self,
        provider_type: str = "mock",
        sender_address: str = "GOVMSG",
        sender_name: str = "Govt Citizen Alert",
        credentials: Optional[Dict[str, Any]] = None,
    ):
        self.provider_type = provider_type.lower().strip()
        self.sender_address = sender_address.strip()
        self.sender_name = sender_name.strip()
        self.credentials = credentials or {}

    def get_channel_name(self) -> str:
        return "SMS"

    def validate_recipient(self, recipient: Any) -> Tuple[bool, Optional[str]]:
        """Validate recipient phone number format."""
        phone = getattr(recipient, "phone", None) or getattr(recipient, "address", None)
        if not phone or not isinstance(phone, str) or not phone.strip():
            return False, "Recipient phone number is missing or empty."
        clean = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if "fail_perm" in clean or "fail_temp" in clean:
            return True, None
        if not PHONE_REGEX.match(clean):
            return False, f"Invalid phone number format: '{phone}'. Expected 10-15 digits (E.164)."
        return True, None

    async def send(self, message: Any, recipient: Any) -> ChannelSendResult:
        """Dispatches an SMS message to the specified recipient."""
        # 1. Validate destination
        is_valid, validation_err = self.validate_recipient(recipient)
        if not is_valid:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name=f"sms_{self.provider_type}",
                error_code="INVALID_PHONE_NUMBER",
                error_message=validation_err,
            )

        raw_phone = (getattr(recipient, "phone", None) or getattr(recipient, "address", "")).strip()
        clean_phone = raw_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        body = getattr(message, "rendered_content", None) or getattr(message, "body", "")
        tracking_id = getattr(message, "tracking_id", None) or f"trk_{uuid.uuid4().hex[:16]}"

        return await self._dispatch(
            recipient_phone=clean_phone,
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
        """Sends an administrative test SMS to verify gateway credentials and connectivity."""
        clean = destination.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not clean or not PHONE_REGEX.match(clean):
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="sms_validator",
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
            provider_type=provider,
            sender_address=sender_addr,
            credentials=creds,
        )

    async def _dispatch(
        self,
        recipient_phone: str,
        body: str,
        tracking_id: str,
        provider_type: str,
        sender_address: str,
        credentials: Dict[str, Any],
    ) -> ChannelSendResult:
        """Internal router executing SMS dispatch according to configured provider type."""
        provider = provider_type.lower().strip()

        # Route 1: Mock Mode
        if provider == "mock":
            return self._dispatch_mock(recipient_phone, body, tracking_id)

        # Route 2: Twilio SMS Gateway
        if provider == "twilio":
            return await self._dispatch_twilio(
                recipient_phone=recipient_phone,
                body=body,
                tracking_id=tracking_id,
                sender_address=sender_address,
                credentials=credentials,
            )

        # Route 3: Fast2SMS Gateway
        if provider == "fast2sms":
            return await self._dispatch_fast2sms(
                recipient_phone=recipient_phone,
                body=body,
                tracking_id=tracking_id,
                sender_address=sender_address,
                credentials=credentials,
            )

        return ChannelSendResult(
            success=False,
            status="Failed",
            provider_name=f"sms_{provider}",
            error_code="UNSUPPORTED_SMS_PROVIDER",
            error_message=f"SMS provider type '{provider}' is not supported. Choose mock, twilio, or fast2sms.",
        )

    def _dispatch_mock(
        self,
        recipient_phone: str,
        body: str,
        tracking_id: str,
    ) -> ChannelSendResult:
        """Deterministic mock SMS execution for test and demo environments."""
        clean = recipient_phone.strip()

        # Deterministic simulation triggers
        if "fail_perm" in clean:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="mock_sms",
                provider_message_id=f"mock-sms-err-{uuid.uuid4().hex[:10]}",
                error_code="CARRIER_UNREACHABLE_DESTINATION",
                error_message="Telecom operator code 30005: Destination handset is inactive or blacklisted.",
                metadata={"tracking_id": tracking_id, "simulated": True},
            )

        if "fail_temp" in clean:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="mock_sms",
                provider_message_id=f"mock-sms-err-{uuid.uuid4().hex[:10]}",
                error_code="CARRIER_RATE_LIMIT_EXCEEDED",
                error_message="Gateway code 429: Operator throughput throttled. Retry recommended.",
                metadata={"tracking_id": tracking_id, "simulated": True},
            )

        metrics = calculate_sms_metrics(body or "")
        ref = f"mock-sms-{uuid.uuid4().hex[:12]}"
        return ChannelSendResult(
            success=True,
            status="Delivered",
            provider_name="mock_sms",
            provider_message_id=ref,
            metadata={
                "tracking_id": tracking_id,
                "segment_count": max(1, metrics.segment_count),
                "encoding": metrics.encoding,
                "simulated": True,
            },
        )

    async def _dispatch_twilio(
        self,
        recipient_phone: str,
        body: str,
        tracking_id: str,
        sender_address: str,
        credentials: Dict[str, Any],
    ) -> ChannelSendResult:
        """Dispatches SMS via Twilio REST API."""
        account_sid = credentials.get("account_sid") or credentials.get("twilio_account_sid")
        auth_token = credentials.get("auth_token") or credentials.get("twilio_auth_token")
        from_number = credentials.get("from_number") or credentials.get("twilio_from_number") or sender_address

        if not account_sid or not auth_token:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="twilio",
                error_code="TWILIO_CREDENTIALS_MISSING",
                error_message="Twilio Account SID or Auth Token is missing.",
                metadata={"tracking_id": tracking_id},
            )

        # Standardize destination to E.164
        dest = recipient_phone if recipient_phone.startswith("+") else f"+91{recipient_phone}"
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        data = {
            "To": dest,
            "From": from_number,
            "Body": body,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, data=data, auth=(account_sid, auth_token))
                resp_json = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}

                if resp.status_code in (200, 201):
                    sid = resp_json.get("sid") or f"SM{uuid.uuid4().hex}"
                    return ChannelSendResult(
                        success=True,
                        status="Sent",
                        provider_name="twilio",
                        provider_message_id=sid,
                        metadata={"tracking_id": tracking_id, "twilio_status": resp_json.get("status")},
                    )
                else:
                    err_msg = resp_json.get("message") or resp.text
                    err_code = str(resp_json.get("code") or f"TWILIO_{resp.status_code}")
                    return ChannelSendResult(
                        success=False,
                        status="Failed",
                        provider_name="twilio",
                        error_code=err_code,
                        error_message=f"Twilio API error: {err_msg}",
                        metadata={"tracking_id": tracking_id, "http_status": resp.status_code},
                    )
        except Exception as exc:
            logger.error("Twilio HTTP exception: %s", exc)
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="twilio",
                error_code="TWILIO_CONNECTION_ERROR",
                error_message=f"Network error connecting to Twilio: {exc}",
                metadata={"tracking_id": tracking_id},
            )

    async def _dispatch_fast2sms(
        self,
        recipient_phone: str,
        body: str,
        tracking_id: str,
        sender_address: str,
        credentials: Dict[str, Any],
    ) -> ChannelSendResult:
        """Dispatches SMS via Fast2SMS Indian SMS Gateway."""
        api_key = credentials.get("api_key") or credentials.get("fast2sms_api_key")
        if not api_key:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="fast2sms",
                error_code="FAST2SMS_KEY_MISSING",
                error_message="Fast2SMS API Key is not configured.",
                metadata={"tracking_id": tracking_id},
            )

        # Fast2SMS requires 10-digit Indian numbers without country code
        clean_10 = recipient_phone.replace("+91", "").lstrip("0")[-10:]
        url = "https://www.fast2sms.com/dev/bulkV2"
        headers = {
            "authorization": api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "route": "v3",
            "sender_id": sender_address or "TXTIND",
            "message": body,
            "language": "english",
            "flash": 0,
            "numbers": clean_10,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp_json = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}

                if resp_json.get("return") is True:
                    req_id = str(resp_json.get("request_id") or f"f2s-{uuid.uuid4().hex[:10]}")
                    return ChannelSendResult(
                        success=True,
                        status="Sent",
                        provider_name="fast2sms",
                        provider_message_id=req_id,
                        metadata={"tracking_id": tracking_id, "request_id": req_id},
                    )
                else:
                    err_msg = resp_json.get("message") or resp.text
                    return ChannelSendResult(
                        success=False,
                        status="Failed",
                        provider_name="fast2sms",
                        error_code="FAST2SMS_DISPATCH_REJECTED",
                        error_message=f"Fast2SMS rejected dispatch: {err_msg}",
                        metadata={"tracking_id": tracking_id},
                    )
        except Exception as exc:
            logger.error("Fast2SMS HTTP exception: %s", exc)
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="fast2sms",
                error_code="FAST2SMS_CONNECTION_ERROR",
                error_message=f"Network error connecting to Fast2SMS: {exc}",
                metadata={"tracking_id": tracking_id},
            )
