"""Pydantic schemas for the end-to-end content generation pipeline (Milestone 2, Task 12)."""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class ContentPipelineRequest(BaseModel):
    """Configuration for starting or scheduling an end-to-end content generation pipeline run."""

    topic: Optional[str] = Field(
        None,
        max_length=255,
        description="Core subject/title. If omitted, falls back to campaign name.",
        examples=["Heatwave & Hydration Public Advisory 2026"],
    )
    objective: Optional[str] = Field(
        None,
        description="Public awareness goal. If omitted, falls back to campaign objective.",
        examples=["Alert vulnerable residents about heat stroke symptoms and nearest water kiosks."],
    )
    category: str = Field(
        "Public Awareness",
        max_length=50,
        description="Content category classification.",
        examples=["Public Awareness", "Emergency Alert", "Healthcare"],
    )
    channels: Optional[List[str]] = Field(
        None,
        description="List of communication channels to generate content for (e.g. SMS, Email, WhatsApp, Voice). Defaults to campaign channels.",
        examples=[["SMS", "Email", "WhatsApp"]],
    )
    source_language: str = Field(
        "en",
        max_length=10,
        description="Source authoring language (default: 'en').",
        examples=["en"],
    )
    target_languages: List[str] = Field(
        default_factory=list,
        description="Target Indian languages for automatic batch translation (e.g. ['hi', 'ta', 'te']).",
        examples=[["hi", "ta", "kn"]],
    )
    segment_ids: Optional[List[int]] = Field(
        None,
        description="Target segment IDs for personalized variants. Defaults to campaign segments if omitted.",
        examples=[[1, 2]],
    )
    target_tone: str = Field(
        "Informative",
        description="Requested tone profile (Urgent, Friendly, Formal, Harsh, Neutral, Informative).",
        examples=["Friendly"],
    )
    tone_instruction: Optional[str] = Field(
        None,
        description="Quick tone adjustment directive (e.g. 'Friendlier & Reassuring', 'More Formal & Official', 'Clear & Informative').",
        examples=["Friendlier & Reassuring"],
    )
    facts: List[str] = Field(
        default_factory=list,
        description="Key facts, emergency numbers, or URLs that MUST be strictly preserved.",
        examples=[["Helpline 1077 is active 24x7", "Water kiosks open at all primary health centers"]],
    )
    constraints: List[str] = Field(
        default_factory=list,
        description="Special editorial or channel constraints.",
        examples=[["Keep SMS body under 160 characters", "Avoid panic jargon"]],
    )
    submit_for_review: bool = Field(
        True,
        description="Whether Stage 5 should automatically transition draft outputs to 'In Review' after quality audit.",
    )
    idempotency_key: Optional[str] = Field(
        None,
        max_length=100,
        description="Client-supplied UUID or unique token to prevent duplicate runs.",
        examples=["pipeline-run-2026-flood-batch-1"],
    )

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            allowed = {"sms", "email", "whatsapp", "voice", "web"}
            for ch in v:
                if ch.lower() not in allowed:
                    raise ValueError(f"Channel '{ch}' is not supported. Supported channels: {sorted(list(allowed))}")
        return v


class StageOutcome(BaseModel):
    """Detailed summary of an individual stage execution."""

    stage_name: str
    status: str  # completed, failed, skipped
    summary: str
    item_count: int = 0
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class ContentPipelineRunResponse(BaseModel):
    """Status and detailed stage output for an end-to-end content generation pipeline run."""

    id: int
    campaign_id: int
    status: str  # pending, in_progress, completed, partially_completed, failed, cancelled
    current_stage: str
    total_stages: int = 5
    completed_stages: int = 0
    progress_percent: float = 0.0
    idempotency_key: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    stage_outputs: Dict[str, Any] = Field(default_factory=dict)
    generated_asset_ids: List[int] = Field(default_factory=list)
    generated_variant_ids: List[int] = Field(default_factory=list)
    error_message: Optional[str] = None
    created_by: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ContentPipelineResumeRequest(BaseModel):
    """Request payload to resume a failed or partially completed pipeline run."""

    force_stage: Optional[str] = Field(
        None,
        description="Optional stage to force execution from: 'generate', 'translate', 'personalize', 'tone_optimize', 'review'.",
    )

