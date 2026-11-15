"""Pydantic schemas for Audience Demographic Content Variants (Task 9.A)."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ContentVariantBase(BaseModel):
    """Base schema attributes for a content variant."""
    variant_title: str = Field(..., min_length=2, max_length=255)
    variant_body: str = Field(..., min_length=5)
    variant_cta: Optional[str] = Field(None, max_length=255)
    personalization_notes: Optional[str] = None


class ContentVariantCreate(ContentVariantBase):
    """Payload to create a new content variant manually."""
    campaign_id: int
    source_content_id: int
    segment_id: Optional[int] = None
    language: str = Field("en", max_length=10)
    channel: str = Field("Email", max_length=30)


class ContentVariantUpdate(BaseModel):
    """Payload to update an existing content variant or transition its review status."""
    variant_title: Optional[str] = Field(None, min_length=2, max_length=255)
    variant_body: Optional[str] = Field(None, min_length=5)
    variant_cta: Optional[str] = Field(None, max_length=255)
    personalization_notes: Optional[str] = None
    review_status: Optional[str] = Field(None, description="Draft, In_Review, Approved, Rejected")
    review_notes: Optional[str] = None


class ContentVariantResponse(ContentVariantBase):
    """Full detail response schema for a content variant."""
    id: int
    campaign_id: int
    source_content_id: int
    segment_id: Optional[int] = None
    segment_name: Optional[str] = None
    language: str
    channel: str
    review_status: str
    review_notes: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    assessment_id: Optional[int] = None
    content_version_hash: Optional[str] = None
    created_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContentPersonalizeRequest(BaseModel):
    """Payload for batch AI demographic variant generation across audience segments."""
    segment_ids: List[int] = Field(..., min_length=1, description="List of segment IDs to personalize for")
    language: Optional[str] = Field("en", description="Target language code")
    channel: Optional[str] = Field(None, description="Communication channel override")
    target_tone: Optional[str] = Field(None, description="Optional target tone override")


class PersonalizeVariantItemResult(BaseModel):
    """Result for a single segment personalization item."""
    segment_id: int
    segment_name: str
    status: str = Field(..., description="'success' or 'failed'")
    variant: Optional[ContentVariantResponse] = None
    error: Optional[str] = None


class ContentPersonalizeResponse(BaseModel):
    """Batch response for audience personalization."""
    source_content_id: int
    total_requested: int
    success_count: int
    failure_count: int
    variants: List[PersonalizeVariantItemResult] = Field(default_factory=list)


class RecipientPreviewRequest(BaseModel):
    """Payload for simulating how a specific recipient sees their personalized message."""
    recipient_id: int = Field(..., description="AudienceMember ID")
    channel: Optional[str] = Field(None, description="Channel override")
    preferred_language: Optional[str] = Field(None, description="Language override")


class RecipientPreviewResponse(BaseModel):
    """Simulation preview showing rendered personalized copy for a recipient."""
    recipient_id: int
    recipient_name: Optional[str] = None
    recipient_address: str
    matched_segment_id: Optional[int] = None
    matched_segment_name: Optional[str] = None
    used_variant_id: Optional[int] = None
    is_fallback: bool
    channel: str
    language: str
    preview_title: str
    preview_body: str
    preview_cta: Optional[str] = None
    substituted_placeholders: Dict[str, str] = Field(default_factory=dict)
    is_simulation: bool = True

