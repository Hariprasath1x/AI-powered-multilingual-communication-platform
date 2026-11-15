"""Base provider abstraction and data transfer contracts for Multichannel Delivery."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class DeliveryPayload(BaseModel):
    """Standardized message payload delivered to a provider adapter."""

    recipient_id: int
    recipient_address: str = Field(..., description="Destination address: email, phone, or account identifier")
    recipient_name: str = Field(..., description="Recipient display name")
    channel: str = Field(..., description="Target channel: Email, SMS, WhatsApp, Voice, Web")
    subject: Optional[str] = Field(default=None, description="Message subject or title")
    body: str = Field(..., description="Personalized rendered body copy")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Contextual campaign and job metadata")


class DeliveryResult(BaseModel):
    """Standardized response from a delivery provider adapter."""

    success: bool
    status: str = Field(..., description="delivered, sent, failed, skipped")
    provider_name: str
    provider_reference: str = Field(..., description="Provider transaction or dispatch tracking reference")
    error_code: Optional[str] = Field(default=None, description="Standardized error code e.g. INVALID_RECIPIENT")
    error_message: Optional[str] = Field(default=None, description="Sanitized failure explanation")
    is_retryable: bool = Field(default=False, description="Whether this failure type can be safely retried")
    response_metadata: Dict[str, Any] = Field(default_factory=dict, description="Provider diagnostic headers/metadata")
    latency_ms: int = Field(default=0, description="Simulated execution latency in milliseconds")


class BaseDeliveryProvider(ABC):
    """Abstract interface for all delivery provider adapters."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Unique provider identifier."""
        pass

    @abstractmethod
    def get_channel(self) -> str:
        """Target channel handled by this provider."""
        pass

    @abstractmethod
    def validate_address(self, address: str) -> bool:
        """Validate destination address format for this channel."""
        pass

    @abstractmethod
    async def send_message(self, payload: DeliveryPayload) -> DeliveryResult:
        """Dispatch message to destination and return standardized DeliveryResult."""
        pass

