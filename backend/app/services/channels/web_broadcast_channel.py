"""WebBroadcastChannel adapter for real-time citizen portal announcements."""

from __future__ import annotations
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from app.services.channels.base import BaseChannel, ChannelSendResult
from app.services.channels.broadcast_manager import broadcast_manager

logger = logging.getLogger("masscommai.web_broadcast_channel")


class WebBroadcastChannel(BaseChannel):
    """
    Channel adapter for public web announcements and real-time citizen broadcasts.
    Broadcasts via WebSockets and Server-Sent Events (SSE) to connected public citizens.
    Privacy Guarantee: Never transmits recipient identity, email, or telephone numbers.
    """

    def __init__(
        self,
        provider_type: str = "mock",
        sender_address: str = "masscomm-broadcast-hub",
        sender_name: str = "Civora Web Broadcast",
        credentials: Optional[Dict[str, Any]] = None,
    ):
        self.provider_type = provider_type.lower().strip()
        self.sender_address = sender_address.strip()
        self.sender_name = sender_name.strip()
        self.credentials = credentials or {}

    def get_channel_name(self) -> str:
        return "Web"

    def validate_recipient(self, recipient: Any) -> Tuple[bool, Optional[str]]:
        """Web broadcast is public; every recipient or broadcast target is valid."""
        return True, None

    async def send(self, message: Any, recipient: Any) -> ChannelSendResult:
        """Dispatches public announcement payload to all active web listeners."""
        campaign_id = getattr(message, "campaign_id", 0)
        title = (
            getattr(message, "title", None)
            or getattr(message, "subject", None)
            or getattr(recipient, "title", None)
            or self.sender_name
        )
        body = getattr(message, "rendered_content", None) or getattr(message, "body", "")
        language = getattr(message, "language", "en")
        is_emergency = getattr(message, "is_emergency", False)
        priority = getattr(message, "priority", "normal")
        tracking_id = getattr(message, "tracking_id", None) or f"trk_{uuid.uuid4().hex[:16]}"
        broadcast_id = f"bc-{uuid.uuid4().hex[:12]}"

        payload = {
            "id": broadcast_id,
            "campaign_id": campaign_id,
            "title": title,
            "body": body,
            "language": language,
            "is_emergency": is_emergency,
            "priority": priority,
            "tracking_id": tracking_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        delivered_count = await broadcast_manager.broadcast(payload)

        return ChannelSendResult(
            success=True,
            status="Delivered",
            provider_name="web_broadcast",
            provider_message_id=broadcast_id,
            metadata={
                "channel": "Web",
                "connected_clients": delivered_count,
                "tracking_id": tracking_id,
                "broadcast_id": broadcast_id,
            },
        )

    async def send_test(
        self,
        destination: str,
        body: str,
        subject: Optional[str] = None,
        config_override: Optional[Dict[str, Any]] = None,
    ) -> ChannelSendResult:
        """Broadcasts a test announcement over active WebSockets and SSE streams."""
        test_id = f"test-bc-{uuid.uuid4().hex[:10]}"
        payload = {
            "id": test_id,
            "campaign_id": 0,
            "title": subject or "Civora Public Web Alert (Test)",
            "body": body,
            "language": "en",
            "is_emergency": False,
            "priority": "test",
            "is_test": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        count = await broadcast_manager.broadcast(payload)

        return ChannelSendResult(
            success=True,
            status="Delivered",
            provider_name="web_broadcast",
            provider_message_id=test_id,
            metadata={"connected_clients": count, "is_test": True},
        )
