"""Pydantic v2 schemas for Content Generation, Translation, Review, and Persistence."""

import math
import re
from datetime import datetime
from typing import List, Optional, Dict, Any, Set
from pydantic import BaseModel, Field, field_validator, computed_field, ConfigDict

SUPPORTED_CHANNELS: Set[str] = {"Email", "SMS", "WhatsApp", "Voice"}
SUPPORTED_TONES: Set[str] = {"formal", "informative", "friendly", "urgent", "empathetic"}
SUPPORTED_LANGUAGES: Set[str] = {"en", "hi", "ta", "te", "bn", "mr"}
SUPPORTED_REVIEW_STATUSES: Set[str] = {"Draft", "In Review", "Approved", "Rejected"}
PLACEHOLDER_REGEX = re.compile(r"\{[a-zA-Z0-9_]+\}")


class ContentGenerateRequest(BaseModel):
    """Request payload to generate content from a structured public awareness brief."""

    topic: str = Field(..., min_length=3, max_length=200, description="Campaign topic or focus area")
    objective: str = Field(..., min_length=5, max_length=500, description="Primary goal or communication directive")
    audience_description: Optional[str] = Field(None, max_length=500, description="Target demographic summary")
    category: str = Field(..., min_length=2, max_length=50, description="Public domain category")
    tone: str = Field("informative", description="formal, informative, friendly, urgent, empathetic")
    channel: str = Field("Email", description="Email, SMS, WhatsApp, Voice")
    source_language: str = Field("en", description="Source language code (e.g., en, hi, ta)")
    facts: Optional[str] = Field(None, max_length=2000, description="Factual bullets, verified contacts, dates, or official links")
    constraints: Optional[str] = Field(None, max_length=500, description="Format constraints, mandatory phrases")
    campaign_id: Optional[int] = Field(None, description="Optional association with an existing campaign")
    template_id: Optional[int] = Field(None, description="Optional association with an existing template")

    @field_validator("tone")
    @classmethod
    def validate_tone(cls, v: str) -> str:
        clean = v.lower().strip()
        if clean not in SUPPORTED_TONES:
            raise ValueError(f"Tone must be one of: {', '.join(sorted(SUPPORTED_TONES))}")
        return clean

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        clean = v.strip().title() if v.lower() != "sms" and v.lower() != "whatsapp" else ("SMS" if v.lower() == "sms" else "WhatsApp")
        if clean not in SUPPORTED_CHANNELS:
            raise ValueError(f"Channel must be one of: {', '.join(sorted(SUPPORTED_CHANNELS))}")
        return clean

    @field_validator("source_language")
    @classmethod
    def validate_source_language(cls, v: str) -> str:
        clean = v.lower().strip()
        if clean not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Source language '{v}' is not supported. Must be one of: {', '.join(sorted(SUPPORTED_LANGUAGES))}")
        return clean


class ContentTranslateRequest(BaseModel):
    """Request payload to translate an existing content asset into a target Indian language."""

    target_language: str = Field(..., description="Target Indian language code: en, ta, hi, te, bn, mr")
    notes: Optional[str] = Field(None, max_length=500, description="Additional context or stylistic guidance")

    @field_validator("target_language")
    @classmethod
    def validate_target_language(cls, v: str) -> str:
        clean = v.lower().strip()
        if clean not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Target language '{v}' is not supported. Must be one of: {', '.join(sorted(SUPPORTED_LANGUAGES))}")
        return clean


class ContentAssetCreate(BaseModel):
    """Manual draft content creation payload."""

    title: str = Field(..., min_length=2, max_length=255)
    body: str = Field(..., min_length=5)
    summary: Optional[str] = Field(None, max_length=1000)
    call_to_action: Optional[str] = Field(None, max_length=255)
    category: str = Field("Healthcare", max_length=50)
    tone: str = Field("informative", max_length=30)
    channel: str = Field("Email", max_length=30)
    source_language: str = Field("en", max_length=10)
    campaign_id: Optional[int] = None
    template_id: Optional[int] = None


class ContentAssetUpdate(BaseModel):
    """Payload to update an editable draft or human-edited copy."""

    title: Optional[str] = Field(None, min_length=2, max_length=255)
    body: Optional[str] = Field(None, min_length=5)
    summary: Optional[str] = Field(None, max_length=1000)
    call_to_action: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=50)
    tone: Optional[str] = Field(None, max_length=30)
    channel: Optional[str] = Field(None, max_length=30)


class ContentReviewStatusUpdate(BaseModel):
    """Payload to transition review status."""

    review_status: str = Field(..., description="Draft, In Review, Approved, Rejected")
    review_notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("review_status")
    @classmethod
    def validate_review_status(cls, v: str) -> str:
        clean = v.strip().title() if v.lower() != "in review" else "In Review"
        if clean not in SUPPORTED_REVIEW_STATUSES:
            raise ValueError(f"review_status must be one of: {', '.join(sorted(SUPPORTED_REVIEW_STATUSES))}")
        return clean


class ContentAttachRequest(BaseModel):
    """Payload to associate content with an existing campaign or save as template."""

    campaign_id: Optional[int] = Field(None, description="Campaign ID to update message body")
    save_as_template: bool = Field(False, description="Whether to also save this content as a reusable template")
    template_name: Optional[str] = Field(None, max_length=150, description="Template title if save_as_template is True")
    template_category: Optional[str] = Field(None, max_length=50, description="Template category")


class ContentAssetResponse(BaseModel):
    """Full representation of a ContentAsset entity with computed channel simulation metrics."""

    id: int
    title: str
    body: str
    summary: Optional[str] = None
    call_to_action: Optional[str] = None
    category: str
    tone: str
    channel: str
    source_language: str
    target_language: Optional[str] = None
    operation_type: str
    parent_id: Optional[int] = None
    campaign_id: Optional[int] = None
    template_id: Optional[int] = None
    review_status: str
    review_notes: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    provider_metadata: Optional[Dict[str, Any]] = None
    created_by: int
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def character_count(self) -> int:
        return len(self.body)

    @computed_field
    @property
    def word_count(self) -> int:
        return len(self.body.split())

    @computed_field
    @property
    def sms_segment_count(self) -> int:
        """Estimate standard 160-char SMS segments for ASCII or 70-char for Unicode."""
        is_ascii = all(ord(c) < 128 for c in self.body)
        segment_limit = 160 if is_ascii else 70
        return max(1, math.ceil(len(self.body) / segment_limit)) if self.body else 1

    @computed_field
    @property
    def voice_duration_seconds(self) -> int:
        """Estimate spoken audio duration at ~150 words per minute (2.5 words/second)."""
        words = len(self.body.split())
        return max(5, math.ceil(words / 2.5)) if words else 5

    @computed_field
    @property
    def detected_placeholders(self) -> List[str]:
        """Extract placeholders like {name}, {city} from body, title, cta."""
        all_text = f"{self.title} {self.body} {self.call_to_action or ''}"
        return sorted(list(set(PLACEHOLDER_REGEX.findall(all_text))))

    model_config = ConfigDict(from_attributes=True)


class ContentVariantSummaryResponse(BaseModel):
    """Summary of a translated variant or historical revision."""

    id: int
    title: str
    channel: str
    source_language: str
    target_language: Optional[str] = None
    operation_type: str
    review_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedContentAssetResponse(BaseModel):
    """Paginated list of ContentAsset items."""

    items: List[ContentAssetResponse]
    total: int
    page: int
    size: int
    pages: int
