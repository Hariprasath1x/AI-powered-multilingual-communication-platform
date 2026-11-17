"""Pydantic v2 schemas for Campaign Scheduling, Automation Rules, Delivery Tracking, and Retries."""

from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


# =========================================================================
# Scheduling Schemas
# =========================================================================

class CampaignScheduleCreateRequest(BaseModel):
    """Payload to configure campaign execution schedule."""

    schedule_type: str = Field(
        default="once",
        description="Schedule execution type: 'now' (immediate), 'once' (future date/time), 'daily', or 'weekly'",
    )
    scheduled_at: Optional[datetime] = Field(
        default=None,
        description="Target UTC timestamp for one-time future execution",
    )
    recurrence_time: Optional[str] = Field(
        default=None,
        description="HH:MM target time in specified timezone (e.g. '09:00')",
    )
    recurrence_days: Optional[List[str]] = Field(
        default_factory=list,
        description="Days of week for weekly schedule: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']",
    )
    timezone: str = Field(
        default="UTC",
        description="IANA timezone identifier (e.g. 'Asia/Kolkata', 'UTC', 'America/New_York')",
    )
    channels: Optional[List[str]] = Field(
        default=None,
        description="Selected distribution channels override",
    )
    fallback_order: Optional[List[str]] = Field(
        default_factory=lambda: ["WhatsApp", "SMS", "Email"],
        description="Ordered multi-channel fallback sequence",
    )
    enable_fallback: bool = Field(
        default=True,
        description="Whether multi-channel fallback should be attempted on failure",
    )

    @field_validator("schedule_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ("now", "once", "daily", "weekly"):
            raise ValueError(f"Invalid schedule_type '{v}'. Allowed: 'now', 'once', 'daily', 'weekly'.")
        return clean

    @field_validator("recurrence_days")
    @classmethod
    def validate_days(cls, v: Optional[List[str]]) -> List[str]:
        if not v:
            return []
        valid_days = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        clean_days = [d.strip().lower()[:3] for d in v if d]
        for d in clean_days:
            if d not in valid_days:
                raise ValueError(f"Invalid day '{d}'. Allowed: mon, tue, wed, thu, fri, sat, sun")
        return list(dict.fromkeys(clean_days))

    @model_validator(mode="after")
    def validate_schedule_requirements(self) -> "CampaignScheduleCreateRequest":
        if self.schedule_type == "once" and not self.scheduled_at:
            raise ValueError("Field 'scheduled_at' is required for one-time future scheduling.")
        if self.schedule_type in ("daily", "weekly") and not self.recurrence_time:
            raise ValueError("Field 'recurrence_time' (HH:MM) is required for recurring campaigns.")
        if self.schedule_type == "weekly" and not self.recurrence_days:
            raise ValueError("Field 'recurrence_days' is required for weekly recurring campaigns.")
        return self


class CampaignScheduleUpdateRequest(BaseModel):
    """Payload to modify existing campaign schedule."""

    schedule_type: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    recurrence_time: Optional[str] = None
    recurrence_days: Optional[List[str]] = None
    timezone: Optional[str] = None
    channels: Optional[List[str]] = None
    fallback_order: Optional[List[str]] = None
    enable_fallback: Optional[bool] = None
    status: Optional[str] = None  # active, paused, cancelled


class CampaignScheduleResponse(BaseModel):
    """Full serialization of campaign schedule."""

    id: int
    campaign_id: int
    campaign_name: str
    schedule_type: str
    scheduled_at: Optional[datetime] = None
    recurrence_pattern: Optional[str] = None
    recurrence_time: Optional[str] = None
    recurrence_days: List[str] = Field(default_factory=list)
    timezone: str
    status: str
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    job_id: Optional[str] = None
    execution_count: int = 0
    channels: List[str] = Field(default_factory=list)
    fallback_order: List[str] = Field(default_factory=list)
    enable_fallback: bool = True
    created_at: datetime
    updated_at: datetime


class ScheduledCampaignItem(BaseModel):
    """Summary item of a scheduled campaign for calendar and management lists."""

    schedule_id: int
    campaign_id: int
    campaign_name: str
    campaign_status: str
    campaign_type: str
    priority: str
    schedule_type: str
    scheduled_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    recurrence_time: Optional[str] = None
    recurrence_days: List[str] = Field(default_factory=list)
    timezone: str
    status: str
    execution_count: int
    channels: List[str] = Field(default_factory=list)


class ScheduledCampaignsListResponse(BaseModel):
    total: int
    items: List[ScheduledCampaignItem]


# =========================================================================
# Automation Rules Schemas
# =========================================================================

class AutomationRuleCreateRequest(BaseModel):
    """Payload to create an automation rule."""

    name: str = Field(..., min_length=2, max_length=150, description="Rule descriptive title")
    trigger_condition: str = Field(
        default="message_not_opened",
        description="Trigger condition: 'message_not_opened', 'message_delivery_failed'",
    )
    wait_hours: int = Field(
        default=24,
        ge=0,
        le=720,
        description="Waiting period in hours before trigger fires (e.g. 24)",
    )
    wait_minutes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Optional wait period in minutes (useful for granular testing)",
    )
    action_type: str = Field(
        default="send_reminder",
        description="Action to execute: 'send_reminder', 'send_fallback', 'notify_admin'",
    )
    action_channel: str = Field(
        default="SMS",
        description="Target channel for action (e.g. 'SMS', 'WhatsApp', 'Email', 'Push')",
    )
    custom_message: Optional[str] = Field(
        default=None,
        description="Optional custom reminder message text override",
    )
    is_enabled: bool = Field(default=True)

    @field_validator("trigger_condition")
    @classmethod
    def validate_condition(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ("message_not_opened", "message_delivery_failed", "message_not_delivered"):
            raise ValueError(f"Unsupported trigger condition '{v}'.")
        return clean

    @field_validator("action_channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        clean = v.strip()
        if clean not in ("Email", "SMS", "WhatsApp", "Push", "Web"):
            raise ValueError(f"Unsupported action channel '{v}'.")
        return clean


class AutomationRuleUpdateRequest(BaseModel):
    """Payload to update an automation rule."""

    name: Optional[str] = None
    trigger_condition: Optional[str] = None
    wait_hours: Optional[int] = None
    wait_minutes: Optional[int] = None
    action_type: Optional[str] = None
    action_channel: Optional[str] = None
    custom_message: Optional[str] = None
    is_enabled: Optional[bool] = None


class AutomationRuleResponse(BaseModel):
    """Full serialization of automation rule."""

    id: int
    campaign_id: int
    name: str
    trigger_condition: str
    wait_hours: int
    wait_minutes: Optional[int] = None
    action_type: str
    action_channel: str
    custom_message: Optional[str] = None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class AutomationExecutionLogResponse(BaseModel):
    """Audit log entry of an automated rule execution."""

    id: int
    rule_id: int
    campaign_id: int
    message_id: int
    audience_member_id: int
    recipient_name: Optional[str] = None
    action_taken: str
    target_channel: str
    status: str
    error_message: Optional[str] = None
    executed_at: datetime


# =========================================================================
# Delivery Tracking & Retry Schemas
# =========================================================================

class DeliveryTrackingSummaryResponse(BaseModel):
    """Comprehensive delivery and retry metrics for a campaign."""

    campaign_id: int
    campaign_name: str
    campaign_status: str
    total_messages: int
    sent_count: int
    delivered_count: int
    failed_count: int
    pending_count: int
    opened_count: int
    retried_count: int
    channel_breakdown: Dict[str, Dict[str, int]]
    failure_reasons: Dict[str, int]
    last_updated: datetime


class FailedMessageItem(BaseModel):
    """Detailed item for failed messages table."""

    id: int
    tracking_id: str
    campaign_id: int
    campaign_name: Optional[str] = None
    recipient_id: int
    recipient_name: str
    recipient_address: str
    channel: str
    language: str
    status: str
    retry_count: int
    max_retries: int
    can_retry: bool
    failure_reason: Optional[str] = None
    fallback_attempts: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class FailedMessagesListResponse(BaseModel):
    total: int
    items: List[FailedMessageItem]


class MessageRetryResponse(BaseModel):
    """Result of retrying an individual message."""

    message_id: int
    tracking_id: str
    previous_status: str
    new_status: str
    retry_count: int
    max_retries: int
    channel_attempted: str
    success: bool
    detail: str


class RetryBatchResponse(BaseModel):
    """Result of retrying multiple failed messages."""

    total_eligible: int
    retried_count: int
    succeeded_count: int
    failed_count: int
    skipped_count: int
    details: List[MessageRetryResponse]


class DeliveryCallbackPayload(BaseModel):
    """Standardized delivery callback payload from providers."""

    provider: str
    provider_message_id: Optional[str] = None
    tracking_id: Optional[str] = None
    status: str  # sent, delivered, failed, read, opened
    failure_reason: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
