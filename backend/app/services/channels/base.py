"""Base contracts and standardized response schemas for the Channel Abstraction Layer."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field


class ChannelSendResult(BaseModel):
    """Standardized response from any communication channel dispatch."""

    success: bool
    status: str = Field(..., description="Message status: Queued, Sent, Delivered, Failed")
    provider_name: str
    provider_message_id: Optional[str] = Field(
        default=None,
        description="External gateway message ID or dispatch tracking token",
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Machine-readable error classification",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Human-readable failure details",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Diagnostic provider headers, segment metrics, or dispatch latency",
    )


class BaseChannel(ABC):
    """
    Common abstraction interface for all communication channels.
    Additional channels (WhatsApp, Voice, Web) can be registered into the
    ChannelRegistry without modifying the core campaign distribution workflows.
    """

    @abstractmethod
    def get_channel_name(self) -> str:
        """Name of the communication channel (e.g. 'Email', 'SMS')."""
        pass

    @abstractmethod
    async def send(self, message: Any, recipient: Any) -> ChannelSendResult:
        """
        Dispatches a rendered campaign message to an individual recipient.

        Args:
            message: Message record or DTO with id, tracking_id, rendered_content, etc.
            recipient: AudienceMember or resolved recipient with name, address, etc.

        Returns:
            ChannelSendResult indicating delivery status and provider reference.
        """
        pass

    @abstractmethod
    def validate_recipient(self, recipient: Any) -> Tuple[bool, Optional[str]]:
        """
        Validates that the recipient possesses valid contact information for this channel.

        Returns:
            Tuple of (is_valid, validation_error_message).
        """
        pass

    @abstractmethod
    async def send_test(
        self,
        destination: str,
        body: str,
        subject: Optional[str] = None,
        config_override: Optional[Dict[str, Any]] = None,
    ) -> ChannelSendResult:
        """
        Sends an isolated test message to verify administrative channel credentials and health.
        """
        pass

