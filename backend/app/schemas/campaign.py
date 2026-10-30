"""Pydantic v2 schemas for Campaign Creation, Configuration, and Lifecycle."""

from datetime import datetime
from typing import List, Optional, Dict, Any, Set
from pydantic import BaseModel, Field, field_validator, model_validator


SUPPORTED_CAMPAIGN_TYPES: Set[str] = {
    "Awareness",
    "Emergency Alert",
    "Educational",
    "Organizational Announcement",
}

SUPPORTED_CAMPAIGN_PRIORITIES: Set[str] = {
    "Low",
    "Medium",
    "High",
}

SUPPORTED_CAMPAIGN_STATUSES: Set[str] = {
    "Draft",
    "In Review",
    "Approved",
    "Scheduled",
    "Archived",
}

SUPPORTED_CAMPAIGN_CHANNELS: Set[str] = {
    "Email",
    "SMS",
    "WhatsApp",
    "Voice",
}


class CampaignSegmentSummary(BaseModel):
    """Brief metadata summary of a target audience segment associated with a campaign."""

    id: int
    name: str
    description: Optional[str] = None


class CampaignBase(BaseModel):
    """Base campaign payload."""

    name: str = Field(..., min_length=2, max_length=150, description="Campaign title")
    campaign_type: str = Field(..., description="Awareness, Emergency Alert, Educational, etc.")
    objective: Optional[str] = Field(default=None, max_length=1000, description="Purpose or target outcome")
    priority: str = Field(default="Medium", description="Low, Medium, High")
    channels: List[str] = Field(..., min_length=1, description="Selected channels e.g. ['Email', 'SMS']")
    template_id: Optional[int] = Field(default=None, ge=1, description="Linked content template ID")
    start_date: Optional[datetime] = Field(default=None, description="Campaign planned start timestamp")
    end_date: Optional[datetime] = Field(default=None, description="Campaign planned end timestamp")

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        clean = v.strip()
        if len(clean) < 2:
            raise ValueError("Campaign name must be at least 2 characters long.")
        return clean

    @field_validator("campaign_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        clean = v.strip()
        matched = {t.lower(): t for t in SUPPORTED_CAMPAIGN_TYPES}
        if clean.lower() not in matched:
            allowed = ", ".join(sorted(SUPPORTED_CAMPAIGN_TYPES))
            raise ValueError(f"Invalid campaign_type '{v}'. Allowed types: {allowed}")
        return matched[clean.lower()]

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        clean = v.strip()
        matched = {p.lower(): p for p in SUPPORTED_CAMPAIGN_PRIORITIES}
        if clean.lower() not in matched:
            allowed = ", ".join(sorted(SUPPORTED_CAMPAIGN_PRIORITIES))
            raise ValueError(f"Invalid priority '{v}'. Allowed: {allowed}")
        return matched[clean.lower()]

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one communication channel must be selected.")
        normalized: List[str] = []
        seen: Set[str] = set()
        channel_map = {c.lower(): c for c in SUPPORTED_CAMPAIGN_CHANNELS}
        for item in v:
            clean = str(item).strip().lower()
            if clean not in channel_map:
                allowed = ", ".join(sorted(SUPPORTED_CAMPAIGN_CHANNELS))
                raise ValueError(f"Unsupported channel '{item}'. Allowed channels: {allowed}")
            proper = channel_map[clean]
            if proper in seen:
                raise ValueError(f"Duplicate channel '{proper}' detected.")
            seen.add(proper)
            normalized.append(proper)
        return normalized

    @model_validator(mode="after")
    def validate_dates(self) -> "CampaignBase":
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValueError("End date must be greater than or equal to start date.")
        return self


class CampaignCreate(CampaignBase):
    """Payload to create a new campaign with target segment IDs."""

    segment_ids: List[int] = Field(default_factory=list, description="IDs of target audience segments")

    @field_validator("segment_ids")
    @classmethod
    def validate_segment_ids(cls, v: List[int]) -> List[int]:
        for s_id in v:
            if not isinstance(s_id, int) or s_id < 1:
                raise ValueError(f"Invalid segment ID '{s_id}'. Segment IDs must be positive integers.")
        seen = set()
        unique = []
        for s_id in v:
            if s_id not in seen:
                seen.add(s_id)
                unique.append(s_id)
        return unique


class CampaignUpdate(BaseModel):
    """Payload to partially update an existing campaign (all fields optional)."""

    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    campaign_type: Optional[str] = None
    objective: Optional[str] = Field(default=None, max_length=1000)
    priority: Optional[str] = None
    channels: Optional[List[str]] = None
    template_id: Optional[int] = None
    segment_ids: Optional[List[int]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if len(clean) < 2:
                raise ValueError("Campaign name must be at least 2 characters long.")
            return clean
        return None

    @field_validator("campaign_type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            matched = {t.lower(): t for t in SUPPORTED_CAMPAIGN_TYPES}
            if clean.lower() not in matched:
                allowed = ", ".join(sorted(SUPPORTED_CAMPAIGN_TYPES))
                raise ValueError(f"Invalid campaign_type '{v}'. Allowed types: {allowed}")
            return matched[clean.lower()]
        return None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            matched = {p.lower(): p for p in SUPPORTED_CAMPAIGN_PRIORITIES}
            if clean.lower() not in matched:
                allowed = ", ".join(sorted(SUPPORTED_CAMPAIGN_PRIORITIES))
                raise ValueError(f"Invalid priority '{v}'. Allowed: {allowed}")
            return matched[clean.lower()]
        return None

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            if not v:
                raise ValueError("At least one communication channel must be selected.")
            normalized: List[str] = []
            seen: Set[str] = set()
            channel_map = {c.lower(): c for c in SUPPORTED_CAMPAIGN_CHANNELS}
            for item in v:
                clean = str(item).strip().lower()
                if clean not in channel_map:
                    allowed = ", ".join(sorted(SUPPORTED_CAMPAIGN_CHANNELS))
                    raise ValueError(f"Unsupported channel '{item}'. Allowed channels: {allowed}")
                proper = channel_map[clean]
                if proper in seen:
                    raise ValueError(f"Duplicate channel '{proper}' detected.")
                seen.add(proper)
                normalized.append(proper)
            return normalized
        return None

    @field_validator("segment_ids")
    @classmethod
    def validate_segment_ids(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is not None:
            for s_id in v:
                if not isinstance(s_id, int) or s_id < 1:
                    raise ValueError(f"Invalid segment ID '{s_id}'. Segment IDs must be positive integers.")
            seen = set()
            unique = []
            for s_id in v:
                if s_id not in seen:
                    seen.add(s_id)
                    unique.append(s_id)
            return unique
        return None

    @model_validator(mode="after")
    def validate_dates(self) -> "CampaignUpdate":
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValueError("End date must be greater than or equal to start date.")
        return self


class CampaignStatusUpdate(BaseModel):
    """Payload to transition campaign lifecycle status."""

    status: str = Field(..., description="Target lifecycle state")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        clean = v.strip()
        matched = {s.lower(): s for s in SUPPORTED_CAMPAIGN_STATUSES}
        if clean.lower() not in matched:
            allowed = ", ".join(sorted(SUPPORTED_CAMPAIGN_STATUSES))
            raise ValueError(f"Invalid status '{v}'. Allowed statuses: {allowed}")
        return matched[clean.lower()]


class CampaignResponse(BaseModel):
    """Full serialization of a campaign entity with reach metrics and creator details."""

    id: int
    name: str
    campaign_type: str
    objective: Optional[str] = None
    priority: str
    status: str
    channels: List[str]
    template_id: Optional[int] = None
    template_title: Optional[str] = None
    template_body: Optional[str] = None
    segments: List[CampaignSegmentSummary] = Field(default_factory=list)
    total_target_audience: Optional[int] = None
    confirmed_consent_audience: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_by: int
    creator_name: Optional[str] = None
    creator_email: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PaginatedCampaignResponse(BaseModel):
    """Paginated collection of campaigns."""

    items: List[CampaignResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CampaignPreviewRequest(BaseModel):
    """Request parameters for generating safe sample recipient previews."""

    audience_member_id: Optional[int] = Field(default=None, ge=1, description="Specific recipient ID to preview")
    custom_placeholders: Optional[Dict[str, str]] = Field(default=None, description="Optional manual placeholder values")


class ChannelPreviewDetail(BaseModel):
    """Channel-specific formatted preview and metrics."""

    channel: str
    title_or_subject: Optional[str] = None
    rendered_body: str
    metrics: Dict[str, Any] = Field(default_factory=dict)


class CampaignPreviewResponse(BaseModel):
    """Rendered campaign preview across configured communication channels."""

    campaign_id: int
    campaign_name: str
    template_id: Optional[int] = None
    template_title: Optional[str] = None
    sample_recipient: Dict[str, Any]
    rendered_content: str
    placeholders_used: List[str]
    channel_previews: Dict[str, ChannelPreviewDetail]

