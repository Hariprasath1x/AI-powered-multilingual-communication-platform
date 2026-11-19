"""PushChannel adapter supporting Mock/Demo mode and Firebase Cloud Messaging (FCM HTTP v1)."""

from __future__ import annotations
import uuid
import json
import logging
import datetime
import threading
from typing import Optional, Dict, Any, Tuple
import httpx
from app.services.channels.base import BaseChannel, ChannelSendResult

logger = logging.getLogger("masscommai.push_channel")

# Required OAuth2 scope for Google Firebase Cloud Messaging HTTP v1 API
FCM_OAUTH_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class PushChannel(BaseChannel):
    """
    Channel adapter for Push Notifications supporting Mock mode and
    Firebase Cloud Messaging (FCM) HTTP v1 with Google OAuth2 authentication.
    """

    # In-memory cache for short-lived Google OAuth2 access tokens:
    # Key: cache_key (e.g. client_email:project_id) -> Value: (token_str, expiry_datetime_utc)
    _token_cache: Dict[str, Tuple[str, datetime.datetime]] = {}
    _cache_lock = threading.Lock()

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

    @classmethod
    def clear_token_cache(cls) -> None:
        """Clears cached OAuth2 access tokens (used in testing and credential rotation)."""
        cls._token_cache.clear()

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

    def _get_fcm_access_token(
        self,
        credentials: Dict[str, Any],
        project_id: str,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Retrieves or generates a short-lived Google OAuth2 access token for FCM HTTP v1.
        Returns: (access_token, error_code, error_message)
        """
        # 1. Direct explicit token (support for unit tests and direct bearer token override)
        if credentials.get("access_token"):
            return str(credentials["access_token"]), None, None

        has_sa_structure = (
            bool(credentials.get("service_account_info"))
            or bool(credentials.get("service_account_json"))
            or (bool(credentials.get("private_key")) and bool(credentials.get("client_email")))
        )

        if not has_sa_structure and credentials.get("server_key"):
            # Static bearer override for legacy/mock compatibility
            return str(credentials["server_key"]), None, None

        # 2. Extract Google Service Account credentials dictionary
        sa_info: Optional[Dict[str, Any]] = None

        if isinstance(credentials.get("service_account_info"), dict):
            sa_info = dict(credentials["service_account_info"])
        elif isinstance(credentials.get("service_account_json"), str):
            raw_json = credentials["service_account_json"].strip()
            if not raw_json:
                return None, "INVALID_FCM_CREDENTIALS", "FCM service_account_json cannot be empty."
            try:
                parsed = json.loads(raw_json)
                if not isinstance(parsed, dict):
                    return None, "INVALID_FCM_CREDENTIALS", "FCM service_account_json must decode to a JSON object."
                sa_info = parsed
            except Exception as exc:
                return None, "INVALID_FCM_CREDENTIALS", f"Malformed service_account_json: {str(exc)}"
        elif credentials.get("private_key") and credentials.get("client_email"):
            sa_info = {
                "type": "service_account",
                "project_id": credentials.get("project_id") or project_id,
                "private_key": credentials.get("private_key"),
                "client_email": credentials.get("client_email"),
                "token_uri": credentials.get("token_uri", "https://oauth2.googleapis.com/token"),
            }
        else:
            return (
                None,
                "INVALID_FCM_CREDENTIALS",
                "Missing FCM service-account credentials. Provide 'service_account_info', 'service_account_json', or 'client_email' and 'private_key'.",
            )

        client_email = sa_info.get("client_email")
        private_key = sa_info.get("private_key")

        if not client_email or not private_key:
            return (
                None,
                "INVALID_FCM_CREDENTIALS",
                "Incomplete FCM service-account credentials. Both 'client_email' and 'private_key' are required.",
            )

        # 3. Cache lookup with 60-second safety margin
        cache_key = f"{client_email}:{project_id}"
        now = datetime.datetime.now(datetime.timezone.utc)

        if cache_key in self._token_cache:
            cached_token, expiry = self._token_cache[cache_key]
            if expiry > now + datetime.timedelta(seconds=60):
                return cached_token, None, None

        # 4. Mint short-lived OAuth2 token via google-auth under thread lock
        with self._cache_lock:
            # Re-check cache inside lock to protect against concurrent refresh races
            now = datetime.datetime.now(datetime.timezone.utc)
            if cache_key in self._token_cache:
                cached_token, expiry = self._token_cache[cache_key]
                if expiry > now + datetime.timedelta(seconds=60):
                    return cached_token, None, None

            try:
                from google.oauth2 import service_account
                from google.auth.transport.requests import Request

                google_creds = service_account.Credentials.from_service_account_info(
                    sa_info,
                    scopes=[FCM_OAUTH_SCOPE],
                )
                google_creds.refresh(Request())

                token = google_creds.token
                if not token:
                    return None, "FCM_AUTH_ERROR", "Google OAuth2 refresh returned an empty access token."

                expiry = google_creds.expiry
                if expiry is not None:
                    if expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=datetime.timezone.utc)
                else:
                    expiry = now + datetime.timedelta(seconds=3500)

                self._token_cache[cache_key] = (token, expiry)
                return token, None, None
            except Exception as exc:
                logger.error("Failed to authenticate Google Service Account for FCM: %s", exc)
                return None, "FCM_AUTH_ERROR", f"FCM OAuth2 authentication failed: {str(exc)}"

    async def _dispatch_fcm(
        self,
        device_token: str,
        title: str,
        body: str,
        tracking_id: str,
        sender_address: str,
        credentials: Dict[str, Any],
    ) -> ChannelSendResult:
        sa_dict = credentials.get("service_account_info") if isinstance(credentials.get("service_account_info"), dict) else {}
        project_id = credentials.get("project_id") or sa_dict.get("project_id") or sender_address

        if not project_id:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="push_fcm",
                error_code="MISSING_FCM_PROJECT_ID",
                error_message="FCM provider requires 'project_id' in configuration.",
            )

        # Retrieve OAuth2 Bearer token
        access_token, err_code, auth_err = self._get_fcm_access_token(credentials, project_id)
        if not access_token:
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="push_fcm",
                error_code=err_code or "FCM_AUTH_ERROR",
                error_message=auth_err or "Failed to obtain FCM OAuth2 access token.",
            )

        url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
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
                try:
                    data = res.json()
                except Exception:
                    data = {}

                err_obj = data.get("error", {})
                err_status = err_obj.get("status", f"HTTP_{res.status_code}")
                err_msg = err_obj.get("message", res.text[:200])

                # Inspect FCM HTTP v1 errorCode in details
                fcm_error_code = None
                details = err_obj.get("details", [])
                if isinstance(details, list):
                    for detail in details:
                        if isinstance(detail, dict) and "errorCode" in detail:
                            fcm_error_code = detail["errorCode"]
                            break

                # Map to standard MassCommAI channel error codes
                if (
                    fcm_error_code in ("UNREGISTERED", "INVALID_ARGUMENT")
                    or err_status in ("UNREGISTERED", "NOT_FOUND")
                    or "unregistered" in err_msg.lower()
                    or "invalid registration token" in err_msg.lower()
                ):
                    error_code = "DEVICE_TOKEN_INVALID"
                elif res.status_code in (401, 403) or err_status in ("UNAUTHENTICATED", "PERMISSION_DENIED"):
                    error_code = "FCM_AUTH_ERROR"
                elif res.status_code == 429 or fcm_error_code == "QUOTA_EXCEEDED":
                    error_code = "RATE_LIMIT_EXCEEDED"
                elif res.status_code >= 500 or fcm_error_code in ("UNAVAILABLE", "INTERNAL"):
                    error_code = "GATEWAY_TIMEOUT"
                else:
                    error_code = fcm_error_code or err_status

                # Ensure sensitive bearer token or keys are not leaked in error messages
                sanitized_err_msg = err_msg[:300]
                if access_token and access_token in sanitized_err_msg:
                    sanitized_err_msg = sanitized_err_msg.replace(access_token, "[REDACTED]")

                return ChannelSendResult(
                    success=False,
                    status="Failed",
                    provider_name="push_fcm",
                    error_code=error_code,
                    error_message=sanitized_err_msg,
                )
        except httpx.TimeoutException as exc:
            logger.error("FCM dispatch timeout: %s", exc)
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="push_fcm",
                error_code="GATEWAY_TIMEOUT",
                error_message="Push gateway connection timed out.",
            )
        except Exception as exc:
            logger.error("FCM dispatch exception: %s", exc)
            return ChannelSendResult(
                success=False,
                status="Failed",
                provider_name="push_fcm",
                error_code="CONNECTION_ERROR",
                error_message="Push gateway connection error.",
            )
