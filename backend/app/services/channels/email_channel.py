"""EmailChannel implementation with support for Mock, SMTP, and SendGrid providers."""

from __future__ import annotations
import re
import uuid
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, Tuple
import httpx
from app.services.channels.base import BaseChannel, ChannelSendResult

logger = logging.getLogger("masscommai.email_channel")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailChannel(BaseChannel):
    """
    Channel adapter for Email distribution supporting Mock/Demo mode,
    direct SMTP dispatch, and SendGrid transactional API.
    """

    def __init__(
        self,
        provider_type: str = "mock",
        sender_address: str = "notifications@masscomm.gov.in",
        sender_name: str = "MassCommAI Citizen Communications",
        credentials: Optional[Dict[str, Any]] = None,
    ):
        self.provider_type = provider_type.lower().strip()
        self.sender_address = sender_address.strip()
        self.sender_name = sender_name.strip()
        self.credentials = credentials or {}

    def get_channel_name(self) -> str:
        return "Email"

    def validate_recipient(self, recipient: Any) -> Tuple[bool, Optional[str]]:
        """Validate recipient email address format."""
        email = getattr(recipient, "email", None) or getattr(recipient, "address", None)
        if not email or not isinstance(email, str) or not email.strip():
            return False, "Recipient email address is missing or empty."
        if not EMAIL_REGEX.match(email.strip()):
            return False, f"Invalid email address format: '{email}'."
        return True, None

    async def send(self, message: Any, recipient: Any) -> ChannelSendResult:
        """Dispatches an email message to the specified recipient."""
        # 1. Validate destination
        is_valid, validation_err = self.validate_recipient(recipient)
        if not is_valid:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name=f"email_{self.provider_type}",
                error_code="INVALID_EMAIL_FORMAT",
                error_message=validation_err,
            )

        recipient_email = (getattr(recipient, "email", None) or getattr(recipient, "address", "")).strip()
        recipient_name = getattr(recipient, "name", "Citizen").strip()
        subject = getattr(message, "subject", None) or "Official Citizen Notification"
        body = getattr(message, "rendered_content", None) or getattr(message, "body", "")
        tracking_id = getattr(message, "tracking_id", None) or f"trk_{uuid.uuid4().hex[:16]}"

        return await self._dispatch(
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=subject,
            body=body,
            tracking_id=tracking_id,
            provider_type=self.provider_type,
            sender_address=self.sender_address,
            sender_name=self.sender_name,
            credentials=self.credentials,
        )

    async def send_test(
        self,
        destination: str,
        body: str,
        subject: Optional[str] = None,
        config_override: Optional[Dict[str, Any]] = None,
    ) -> ChannelSendResult:
        """Sends an administrative test email to verify credentials and connection."""
        if not destination or not EMAIL_REGEX.match(destination.strip()):
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="email_validator",
                error_code="INVALID_TEST_DESTINATION",
                error_message=f"Test recipient '{destination}' is not a valid email address.",
            )

        override = config_override or {}
        provider = (override.get("provider_type") or self.provider_type).lower().strip()
        sender_addr = override.get("sender_address") or self.sender_address
        sender_nm = override.get("sender_name") or self.sender_name
        creds = override.get("credentials") or self.credentials
        subj = subject or "MassCommAI Email Channel Connectivity Verification"
        tracking_id = f"test_{uuid.uuid4().hex[:12]}"

        return await self._dispatch(
            recipient_email=destination.strip(),
            recipient_name="Channel Administrator",
            subject=subj,
            body=body,
            tracking_id=tracking_id,
            provider_type=provider,
            sender_address=sender_addr,
            sender_name=sender_nm,
            credentials=creds,
        )

    async def _dispatch(
        self,
        recipient_email: str,
        recipient_name: str,
        subject: str,
        body: str,
        tracking_id: str,
        provider_type: str,
        sender_address: str,
        sender_name: str,
        credentials: Dict[str, Any],
    ) -> ChannelSendResult:
        """Internal router executing dispatch according to configured provider type."""
        provider = provider_type.lower().strip()

        # Route 1: Mock / Demo Mode
        if provider == "mock":
            return self._dispatch_mock(recipient_email, subject, body, tracking_id)

        # Route 2: SMTP Provider
        if provider == "smtp":
            return await self._dispatch_smtp(
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                subject=subject,
                body=body,
                tracking_id=tracking_id,
                sender_address=sender_address,
                sender_name=sender_name,
                credentials=credentials,
            )

        # Route 3: SendGrid API Provider
        if provider == "sendgrid":
            return await self._dispatch_sendgrid(
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                subject=subject,
                body=body,
                tracking_id=tracking_id,
                sender_address=sender_address,
                sender_name=sender_name,
                credentials=credentials,
            )

        # Unknown provider fallback
        return ChannelSendResult(
            success=False,
            status="Failed",
            provider_name=f"email_{provider}",
            error_code="UNSUPPORTED_EMAIL_PROVIDER",
            error_message=f"Email provider type '{provider}' is not supported. Choose mock, smtp, or sendgrid.",
        )

    def _dispatch_mock(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        tracking_id: str,
    ) -> ChannelSendResult:
        """Deterministic mock provider execution for automated testing and demo environments."""
        addr_lower = recipient_email.lower().strip()

        # Deterministic failure triggers
        if "fail_perm" in addr_lower:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="mock_email",
                provider_message_id=f"mock-err-{uuid.uuid4().hex[:10]}",
                error_code="RECIPIENT_MAILBOX_NOT_FOUND",
                error_message="SMTP 550: Mailbox does not exist or rejected by remote destination server.",
                metadata={"tracking_id": tracking_id, "simulated": True},
            )

        if "fail_temp" in addr_lower:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="mock_email",
                provider_message_id=f"mock-err-{uuid.uuid4().hex[:10]}",
                error_code="SMTP_421_SERVICE_BUSY",
                error_message="SMTP 421: Connection limit reached, server temporarily busy.",
                metadata={"tracking_id": tracking_id, "simulated": True},
            )

        # Successful mock dispatch
        msg_id = f"mock-email-{uuid.uuid4().hex[:12]}"
        return ChannelSendResult(
            success=True,
            status="Delivered",
            provider_name="mock_email",
            provider_message_id=msg_id,
            metadata={
                "tracking_id": tracking_id,
                "simulated": True,
                "subject": subject,
                "recipient": recipient_email,
            },
        )

    async def _dispatch_smtp(
        self,
        recipient_email: str,
        recipient_name: str,
        subject: str,
        body: str,
        tracking_id: str,
        sender_address: str,
        sender_name: str,
        credentials: Dict[str, Any],
    ) -> ChannelSendResult:
        """Connects and sends via standard SMTP server."""
        host = credentials.get("smtp_host") or "localhost"
        port = int(credentials.get("smtp_port") or 587)
        username = credentials.get("smtp_username")
        password = credentials.get("smtp_password")
        use_tls = bool(credentials.get("use_tls", True))

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{sender_name} <{sender_address}>" if sender_name else sender_address
        msg["To"] = f"{recipient_name} <{recipient_email}>" if recipient_name else recipient_email
        msg["X-Tracking-ID"] = tracking_id
        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            # Use synchronous smtplib in thread executor or standard connect
            server = smtplib.SMTP(host, port, timeout=10.0)
            if use_tls:
                server.starttls()
            if username and password:
                server.login(username, password)
            server.sendmail(sender_address, [recipient_email], msg.as_string())
            server.quit()

            provider_id = f"smtp-{uuid.uuid4().hex[:12]}"
            # Message is sent to gateway; status is 'Sent' (not 'Delivered' until confirmed)
            return ChannelSendResult(
                success=True,
                status="Sent",
                provider_name="smtp",
                provider_message_id=provider_id,
                metadata={"tracking_id": tracking_id, "host": host, "port": port},
            )
        except smtplib.SMTPAuthenticationError as exc:
            logger.error("SMTP Authentication failure: %s", exc)
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="smtp",
                error_code="SMTP_AUTHENTICATION_FAILED",
                error_message=f"SMTP authentication failed with host {host}:{port}.",
                metadata={"tracking_id": tracking_id},
            )
        except (smtplib.SMTPConnectError, ConnectionRefusedError, OSError) as exc:
            logger.error("SMTP Connection failure: %s", exc)
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="smtp",
                error_code="SMTP_CONNECTION_REFUSED",
                error_message=f"Failed to connect to SMTP server at {host}:{port}: {exc}",
                metadata={"tracking_id": tracking_id},
            )
        except Exception as exc:
            logger.error("SMTP unhandled failure: %s", exc)
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="smtp",
                error_code="SMTP_DELIVERY_ERROR",
                error_message=f"SMTP transmission error: {exc}",
                metadata={"tracking_id": tracking_id},
            )

    async def _dispatch_sendgrid(
        self,
        recipient_email: str,
        recipient_name: str,
        subject: str,
        body: str,
        tracking_id: str,
        sender_address: str,
        sender_name: str,
        credentials: Dict[str, Any],
    ) -> ChannelSendResult:
        """Dispatches email via SendGrid REST API v3."""
        api_key = credentials.get("api_key") or credentials.get("sendgrid_api_key")
        if not api_key:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="sendgrid",
                error_code="SENDGRID_KEY_MISSING",
                error_message="SendGrid API Key is not configured.",
                metadata={"tracking_id": tracking_id},
            )

        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "personalizations": [
                {
                    "to": [{"email": recipient_email, "name": recipient_name}],
                    "custom_args": {"tracking_id": tracking_id},
                }
            ],
            "from": {"email": sender_address, "name": sender_name or "MassCommAI"},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 202:
                    msg_id = resp.headers.get("X-Message-Id") or f"sg-{uuid.uuid4().hex[:12]}"
                    return ChannelSendResult(
                        success=True,
                        status="Sent",
                        provider_name="sendgrid",
                        provider_message_id=msg_id,
                        metadata={"tracking_id": tracking_id, "status_code": 202},
                    )
                else:
                    return ChannelSendResult(
                        success=False,
                        status="Failed",
                        provider_name="sendgrid",
                        error_code=f"SENDGRID_HTTP_{resp.status_code}",
                        error_message=f"SendGrid API rejected dispatch ({resp.status_code}): {resp.text}",
                        metadata={"tracking_id": tracking_id, "status_code": resp.status_code},
                    )
        except Exception as exc:
            logger.error("SendGrid HTTP exception: %s", exc)
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="sendgrid",
                error_code="SENDGRID_CONNECTION_ERROR",
                error_message=f"Network error connecting to SendGrid API: {exc}",
                metadata={"tracking_id": tracking_id},
            )

