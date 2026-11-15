"""Pydantic schemas for Multichannel Distribution Jobs and Delivery Records."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict


class JobCreateRequest(BaseModel):
    """Payload to initiate a new distribution job for an approved campaign."""

    campaign_id: int = Field(..., description="Target approved campaign ID")
    channel: str = Field(..., description="Target communication channel: Email, SMS, WhatsApp, Voice, Web")

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        allowed = {"Email", "SMS", "WhatsApp", "Voice", "Web"}
        if v not in allowed:
            raise ValueError(f"Channel '{v}' not supported. Must be one of: {', '.join(sorted(allowed))}")
        return v


class ReadinessCheckResponse(BaseModel):
    """Pre-dispatch campaign readiness validation status."""

    is_ready: bool
    campaign_id: int
    campaign_status: str
    campaign_status_valid: bool
    channel: str
    channel_supported: bool
    has_template_or_content: bool
    content_approved: bool
    content_is_outdated: bool
    total_target_audience: int
    confirmed_consent_audience: int
    eligible_recipients_count: int
    blocking_reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    # Additive Phase 2 constraint and audience aggregation fields
    valid_recipients_count: int = 0
    warning_recipients_count: int = 0
    blocked_recipients_count: int = 0
    total_estimated_segments: Optional[int] = None
    max_segments_per_recipient: Optional[int] = None
    estimated_duration_seconds: Optional[int] = None
    channel_metrics: Optional[Dict[str, Any]] = None
    language_breakdown: Optional[Dict[str, Any]] = None


class DeliveryAttemptResponse(BaseModel):
    """Delivery attempt audit trail item."""

    id: int
    attempt_number: int
    provider_name: str
    attempt_status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    response_metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class DeliveryRecordResponse(BaseModel):
    """Recipient delivery record item with status and attempts. Raw recipient address is omitted for PII privacy protection."""

    id: int
    delivery_id: str
    job_id: int
    audience_member_id: int
    recipient_name: Optional[str] = None
    channel: str
    masked_recipient_address: str
    rendered_content: str
    delivery_status: str
    provider_name: Optional[str] = None
    provider_reference: Optional[str] = None
    attempt_count: int
    max_attempts: int
    last_attempt_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    attempts: List[DeliveryAttemptResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class DistributionJobResponse(BaseModel):
    """Distribution job details and aggregate progress metrics."""

    id: int
    job_id: str
    campaign_id: int
    campaign_name: Optional[str] = None
    content_asset_id: Optional[int] = None
    template_id: Optional[int] = None
    channel: str
    status: str
    total_recipients: int
    eligible_recipients: int
    queued_recipients: int
    sent_recipients: int
    delivered_recipients: int
    failed_recipients: int
    skipped_recipients: int
    error_summary: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    locked_by: Optional[str] = None
    lease_expires_at: Optional[datetime] = None
    recovery_count: int = 0
    created_by: int
    creator_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedJobsResponse(BaseModel):
    items: List[DistributionJobResponse]
    total: int
    page: int
    size: int
    pages: int


class PaginatedDeliveriesResponse(BaseModel):
    items: List[DeliveryRecordResponse]
    total: int
    page: int
    size: int
    pages: int


class DistributionMetricsResponse(BaseModel):
    """Operational observability metrics for queue processing and delivery performance."""

    # Job metrics
    total_jobs: int = Field(..., description="Total distribution jobs created")
    queued_jobs: int = Field(..., description="Jobs currently waiting in queue for worker claim")
    processing_jobs: int = Field(..., description="Jobs currently being processed by workers")
    completed_jobs: int = Field(..., description="Jobs completed successfully without errors")
    completed_with_errors_jobs: int = Field(default=0, description="Jobs completed with non-fatal errors (e.g. skipped consent)")
    failed_jobs: int = Field(..., description="Jobs that failed completely")
    cancelled_jobs: int = Field(..., description="Jobs cancelled by operators")

    # Delivery outcome metrics
    total_delivery_records: int = Field(..., description="Total individual delivery records across all jobs")
    pending_deliveries: int = Field(..., description="Deliveries waiting for worker batch dispatch")
    processing_deliveries: int = Field(..., description="Deliveries currently being dispatched by active worker")
    delivered_deliveries: int = Field(..., description="Confirmed successful simulated deliveries")
    failed_deliveries: int = Field(..., description="Permanent or exhausted delivery failures")
    skipped_consent_deliveries: int = Field(..., description="Deliveries skipped due to revoked or unconfirmed consent")
    retrying_deliveries: int = Field(..., description="Deliveries awaiting exponential backoff retry")

    # Operational queue health
    stale_processing_jobs: int = Field(..., description="Jobs stuck in processing beyond their lease expiration")
    active_workers_count: int = Field(..., description="Count of distinct workers currently holding unexpired leases")
    avg_processing_duration_seconds: Optional[float] = Field(
        None,
        description="Average execution duration from start to completion in seconds",
    )
