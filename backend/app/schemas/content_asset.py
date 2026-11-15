"""Pydantic v2 schemas for Content Generation, Translation, Review, and Persistence."""

import math
import re
from datetime import datetime
from typing import List, Optional, Dict, Any, Set
from pydantic import BaseModel, Field, field_validator, computed_field, ConfigDict, model_validator

SUPPORTED_CHANNELS: Set[str] = {"Email", "SMS", "WhatsApp", "Voice"}
SUPPORTED_TONES: Set[str] = {"formal", "informative", "friendly", "urgent", "empathetic"}
SUPPORTED_LANGUAGES: Set[str] = {
    "en",  # English
    "hi",  # Hindi
    "kn",  # Kannada
    "ta",  # Tamil
    "te",  # Telugu
    "mr",  # Marathi
    "bn",  # Bengali
    "gu",  # Gujarati
    "ml",  # Malayalam
    "pa",  # Punjabi
    "ur",  # Urdu
}
SUPPORTED_REVIEW_STATUSES: Set[str] = {
    "Draft",
    "Pending",
    "Generated",
    "Needs Review",
    "Approved",
    "Rejected",
    "In Review",  # Retained for backward compatibility
}
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

    target_language: str = Field(..., description="Target Indian language code (hi, kn, ta, te, mr, bn, gu, ml, pa, ur)")
    notes: Optional[str] = Field(None, max_length=500, description="Additional context or stylistic guidance")

    @field_validator("target_language")
    @classmethod
    def validate_target_language(cls, v: str) -> str:
        clean = v.lower().strip()
        if clean not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Target language '{v}' is not supported. Must be one of: {', '.join(sorted(SUPPORTED_LANGUAGES))}")
        return clean


class ContentBatchTranslateRequest(BaseModel):
    """Request payload to translate an asset into multiple target Indian languages concurrently."""

    target_languages: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of target Indian language codes (e.g. ['hi', 'kn', 'ta', 'te'])",
    )
    notes: Optional[str] = Field(None, max_length=500, description="Additional context or stylistic guidance")
    provider_type: Optional[str] = Field(None, description="Optional provider override (e.g. 'mock' or 'gemini')")

    @field_validator("target_languages")
    @classmethod
    def validate_target_languages(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one target language must be selected.")
        cleaned = []
        for lang in v:
            c = lang.lower().strip()
            if c not in cleaned:
                cleaned.append(c)
        return cleaned


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


class ContentPreviewMetricsRequest(BaseModel):
    """Stateless channel constraint simulation request."""

    channel: str = Field(..., description="Email, SMS, WhatsApp, Voice")
    body: str = Field("", max_length=10000, description="Draft body text to analyze")
    title: Optional[str] = Field(None, max_length=255, description="Draft title or subject")
    call_to_action: Optional[str] = Field(None, max_length=255, description="Draft call to action")
    language: Optional[str] = Field(None, max_length=32, description="Target language code (e.g. en, ta, hi)")
    mode: Optional[str] = Field("freeform", max_length=32, description="Optional channel mode: freeform or template")

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        clean = v.strip().title() if v.lower() != "sms" and v.lower() != "whatsapp" else ("SMS" if v.lower() == "sms" else "WhatsApp")
        if clean not in SUPPORTED_CHANNELS:
            raise ValueError(f"Channel must be one of: {', '.join(sorted(SUPPORTED_CHANNELS))}")
        return clean


class ChannelWarningResponse(BaseModel):
    """Structured, machine-readable channel constraint warning."""

    code: str = Field(..., description="Stable machine-readable warning code")
    severity: str = Field(..., description="Warning severity: CRITICAL, HIGH, MEDIUM, LOW, or INFO")
    message: str = Field(..., description="Human-readable explanation and correction guidance")


class SMSDetailResponse(BaseModel):
    """
    Detailed telecom SMS encoding and segmentation metrics.

    Note: Encoding analysis uses UTF-16 code units for UCS-2 compatibility estimates.
    Supplementary characters (e.g., emojis) consume 2 code units. Strict UCS-2 gateways
    may not support supplementary characters; carrier delivery cannot be guaranteed.
    """

    encoding: str = Field(..., description="GSM-7 or UCS-2")
    character_count: int = Field(..., description="Total characters in content body")
    encoded_units: int = Field(..., description="Total septets (GSM-7) or UTF-16 code units (UCS-2)")
    segment_count: int = Field(..., description="Calculated SMS segments required")
    segment_capacity: int = Field(..., description="Capacity of current segment tier (160/153 or 70/67)")
    remaining_in_segment: int = Field(..., description="Remaining capacity in final segment")
    is_multipart: bool = Field(..., description="True if message requires multi-segment concatenation")
    has_extension_characters: bool = Field(default=False, description="True if GSM-7 extension characters used")
    has_surrogate_pairs: bool = Field(default=False, description="True if supplementary Unicode characters used")
    non_gsm_characters: List[str] = Field(default_factory=list, description="Deduplicated sample of non-GSM characters")


class ChannelMetricsResponse(BaseModel):
    """Complete channel simulation and constraint metrics."""

    channel: str = Field(..., description="Normalized channel name")
    character_count: int = Field(..., description="Total characters in content body")
    word_count: int = Field(..., description="Total words in content body")
    estimated_duration_seconds: Optional[int] = Field(None, description="Spoken duration estimate for Voice")
    sms: Optional[SMSDetailResponse] = Field(None, description="Detailed telecom SMS metrics if channel is SMS")
    is_within_recommended_limit: bool = Field(..., description="Whether content satisfies recommended UX boundaries")
    is_within_hard_limit: bool = Field(..., description="Whether content satisfies technical hard limits")
    warnings: List[ChannelWarningResponse] = Field(default_factory=list, description="Structured warnings")
    rule_version: str = Field("v1.0", description="Version of the channel constraint rule engine")


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
    channel_metrics: Optional[ChannelMetricsResponse] = None
    created_by: int
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def ensure_channel_metrics(self) -> "ContentAssetResponse":
        """
        Ensure channel_metrics is always present in response.
        If present in provider_metadata snapshot, deserialize it.
        If missing (e.g. older record without snapshot), compute dynamically.
        """
        if self.channel_metrics is None:
            if (
                self.provider_metadata
                and isinstance(self.provider_metadata, dict)
                and "channel_metrics" in self.provider_metadata
            ):
                try:
                    self.channel_metrics = ChannelMetricsResponse.model_validate(
                        self.provider_metadata["channel_metrics"]
                    )
                except Exception:
                    pass
            if self.channel_metrics is None:
                from app.services.channel_constraints import calculate_channel_metrics

                calculated = calculate_channel_metrics(
                    channel=self.channel,
                    title=self.title,
                    body=self.body,
                    call_to_action=self.call_to_action,
                    language=self.target_language or self.source_language,
                )
                self.channel_metrics = ChannelMetricsResponse.model_validate(calculated.to_dict())
        return self

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
        """Estimate standard 160-char SMS segments for GSM-7 or 70-char for UCS-2."""
        if self.channel_metrics and self.channel_metrics.sms:
            return max(1, self.channel_metrics.sms.segment_count) if self.body else 1
        from app.services.channel_constraints import calculate_sms_metrics

        sms_data = calculate_sms_metrics(self.body or "")
        return max(1, sms_data.segment_count) if self.body else 1

    @computed_field
    @property
    def voice_duration_seconds(self) -> int:
        """Estimate spoken audio duration at language-appropriate speaking rates."""
        if self.channel_metrics and self.channel_metrics.estimated_duration_seconds is not None:
            return self.channel_metrics.estimated_duration_seconds
        from app.services.channel_constraints import calculate_voice_duration_seconds

        return calculate_voice_duration_seconds(
            self.body or "",
            language=self.target_language or self.source_language,
        )

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


class BatchTranslationFailure(BaseModel):
    """Details of an individual target language translation failure in a batch."""

    target_language: str
    error: str
    status_code: int = 422


class ContentBatchTranslateResponse(BaseModel):
    """Result of batch translation across multiple target languages."""

    source_asset_id: int
    successes: List[ContentAssetResponse] = Field(default_factory=list)
    failures: List[BatchTranslationFailure] = Field(default_factory=list)
    total_requested: int
    total_succeeded: int
    total_failed: int


class TranslationReviewHistoryResponse(BaseModel):
    """Audit record of a translation review state transition."""

    id: int
    content_asset_id: int
    from_status: str
    to_status: str
    reviewer_id: int
    reviewer_name: Optional[str] = None
    review_notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
