"""Pydantic schemas for Channel Configurations, Test Dispatches, and Campaign Sending."""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


def mask_secret(value: Optional[str]) -> Optional[str]:
    """Masks secret API tokens or passwords for secure API presentation."""
    if not value or not isinstance(value, str):
        return None
    val = value.strip()
    if len(val) <= 4:
        return "****"
    if len(val) <= 8:
        return f"{val[:2]}****"
    return f"{val[:3]}****{val[-3:]}"


class ChannelConfigResponse(BaseModel):
    """Public safe representation of a channel configuration with masked credentials."""

    id: int
    channel: str
    is_enabled: bool
    provider_type: str
    sender_address: Optional[str] = None
    sender_name: Optional[str] = None
    has_credentials: bool = False
    masked_credentials: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ChannelConfigUpdateRequest(BaseModel):
    """Administrative update payload for channel provider, enabled toggle, and credentials."""

    is_enabled: Optional[bool] = None
    provider_type: Optional[str] = Field(None, description="mock, smtp, sendgrid, twilio, fast2sms")
    sender_address: Optional[str] = None
    sender_name: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None


class ChannelTestRequest(BaseModel):
    """Administrative payload requesting an isolated channel connectivity test message."""

    destination: str = Field(..., description="Target email or phone number for the test send")
    message: Optional[str] = Field(
        default="This is an automated connectivity test message from MassCommAI.",
        description="Test body text",
    )
    subject: Optional[str] = Field(
        default="MassCommAI Channel Test Notification",
        description="Optional subject line (used for Email)",
    )


class ChannelTestResponse(BaseModel):
    """Result of administrative channel test dispatch."""

    success: bool
    status: str
    provider_name: str
    provider_message_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CampaignSendRequest(BaseModel):
    """Payload to initiate campaign message distribution."""

    channels: Optional[List[str]] = Field(
        default=None,
        description="Subset of campaign channels to target (defaults to all campaign channels)",
    )


class MessageSummary(BaseModel):
    """Summary record of an individual dispatched or attempted message."""

    id: int
    tracking_id: str
    recipient_id: int
    recipient_name: str
    recipient_address: str
    channel: str
    language: str
    content_asset_id: Optional[int] = None
    content_variant_id: Optional[int] = None
    status: str
    provider_message_id: Optional[str] = None
    failure_reason: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime


class ChannelDeliverySummary(BaseModel):
    """Aggregate statistics for a specific delivery channel."""

    total: int = 0
    sent: int = 0
    delivered: int = 0
    failed: int = 0
    pending: int = 0


class CampaignSendSummaryResponse(BaseModel):
    """Comprehensive campaign distribution outcome returned by POST /campaigns/{id}/send."""

    campaign_id: int
    campaign_name: str
    campaign_status: str
    total_intended_recipients: int
    eligible_recipients: int
    opted_out_recipients: int
    sent_messages: int
    delivered_messages: int
    failed_messages: int
    channel_summary: Dict[str, ChannelDeliverySummary] = Field(default_factory=dict)
    messages: List[MessageSummary] = Field(default_factory=list)
    execution_timestamp: datetime = Field(default_factory=datetime.utcnow)

