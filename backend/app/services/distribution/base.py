"""Enums and contracts for Multichannel Distribution Engine."""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    SKIPPED_CONSENT = "skipped_consent"


class DeliveryChannel(str, Enum):
    EMAIL = "Email"
    SMS = "SMS"
    WHATSAPP = "WhatsApp"
    VOICE = "Voice"
    WEB = "Web"


class ReadinessCheckResult(BaseModel):
    """Pre-dispatch validation checklist assessing whether a campaign is eligible for broadcast."""

    is_ready: bool = Field(..., description="True only if all critical readiness checks pass")
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


class ResolvedRecipient(BaseModel):
    """Audience member resolved and validated for message dispatch."""

    audience_member_id: int
    name: str
    preferred_language: str
    channel: str
    address: str
    consent_status: Optional[bool]
    is_eligible: bool
    ineligibility_reason: Optional[str] = None


# Set of error codes indicating non-recoverable permanent failures that must not be retried
NON_RETRYABLE_ERROR_CODES = {
    "PAYLOAD_EXCEEDS_CHANNEL_HARD_LIMIT",
    "RECIPIENT_MAILBOX_NOT_FOUND",
    "INVALID_EMAIL_FORMAT",
    "INVALID_PHONE_NUMBER",
    "CARRIER_UNREACHABLE_DESTINATION",
    "USER_NOT_REGISTERED_ON_WHATSAPP",
    "INVALID_WHATSAPP_NUMBER",
    "TELEPHONY_DISCONNECTED_NUMBER",
    "INVALID_TELEPHONY_NUMBER",
    "DEVICE_TOKEN_INVALID",
    "EMPTY_RECIPIENT_IDENTIFIER",
    "RECIPIENT_DELETED",
    "MISSING_CONTACT_INFO",
    "CONSENT_WITHDRAWN_POST_JOB",
    "CONSENT_UNCONFIRMED_POST_JOB",
    "LACKS_AFFIRMATIVE_CONSENT",
}


def mask_recipient_address(address: str, channel: str = "") -> str:
    """
    Masks recipient contact information for privacy protection in public listings and audit responses.
    Example: 'aarav@example.gov.in' -> 'aa***@example.gov.in', '+919876543210' -> '+9198****3210'.
    """
    if not address:
        return ""
    addr = address.strip()
    if "@" in addr:
        parts = addr.split("@", 1)
        local, domain = parts[0], parts[1]
        if len(local) <= 2:
            masked_local = local[0] + "***" if local else "***"
        else:
            masked_local = local[:2] + "***"
        return f"{masked_local}@{domain}"
    elif len(addr) >= 8:
        return f"{addr[:4]}****{addr[-4:]}"
    elif len(addr) >= 4:
        return f"{addr[:2]}**{addr[-2:]}"
    return "***"


