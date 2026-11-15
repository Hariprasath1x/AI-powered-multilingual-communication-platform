"""Pydantic schemas for Sentiment-Aware Tone Analysis and Generative Optimization (Task 10)."""

from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class ToneClassification(str, Enum):
    """Five-way tone classification for public awareness communication."""
    URGENT = "Urgent"
    FRIENDLY = "Friendly"
    FORMAL = "Formal"
    HARSH = "Harsh"
    NEUTRAL = "Neutral"


class ToneAlignmentResult(BaseModel):
    """Tone alignment evaluation against configured campaign target tone."""
    target_tone: Optional[str] = None
    detected_tone: str
    is_aligned: bool = True
    alignment_score: float = Field(default=100.0, ge=0.0, le=100.0)
    mismatch_detected: bool = False
    details: str = "Tone aligns with communication objectives."


class ToneAnalyzeRequest(BaseModel):
    """Optional request payload for tone analysis."""
    text_override: Optional[str] = Field(None, description="Optional custom text to analyze instead of asset body")
    target_tone: Optional[str] = Field(None, description="Expected tone (e.g. formal, urgent, friendly, empathetic, neutral)")
    channel: Optional[str] = Field(None, description="Target communication channel")


class ToneAnalyzeResponse(BaseModel):
    """Structured response for sentiment, readability, and tone analysis."""
    content_asset_id: int
    detected_tone: str = Field(..., description="Urgent, Friendly, Formal, Harsh, or Neutral")
    sentiment_polarity: float = Field(..., ge=-1.0, le=1.0, description="Sentiment index from -1.0 (alarmist/negative) to +1.0 (positive/reassuring)")
    readability_score: float = Field(..., ge=0.0, le=100.0, description="Flesch Reading Ease score")
    readability_classification: str = Field(..., description="Literacy level (e.g. Standard / General Public, Easy, Difficult)")
    clarity_score: float = Field(..., ge=0.0, le=100.0, description="Clarity index based on sentence structure and terminology")
    target_tone: Optional[str] = None
    tone_alignment: ToneAlignmentResult
    formatting_anomalies: List[str] = Field(default_factory=list, description="Excessive capitalization, exclamation marks, or punctuation issues")
    suggestions: List[str] = Field(default_factory=list, description="Actionable recommendations to improve tone and clarity")
    findings: List[Dict[str, Any]] = Field(default_factory=list, description="Itemized findings with severity classifications")
    overall_tone_score: float = Field(..., ge=0.0, le=100.0, description="Composite tone quality score")


class ToneImproveRequest(BaseModel):
    """Request payload for generative tone improvement."""
    target_tone: str = Field(..., description="Desired tone: Urgent, Friendly, Formal, Empathetic, Neutral")
    adjustment_instruction: Optional[str] = Field(
        None,
        description="Quick adjustment code: 'more_formal', 'friendlier', 'more_urgent', 'shorter', or custom instruction",
    )
    channel: Optional[str] = Field(None, description="Target communication channel (Email, SMS, WhatsApp, Voice)")
    preserve_anchors: bool = Field(True, description="Strictly preserve emergency helplines, dates, URLs, and placeholders")


class StructuredDiffChunk(BaseModel):
    """Single token or phrase change in text diff."""
    type: str = Field(..., description="'equal', 'insert', or 'delete'")
    text: str


class StructuredDiff(BaseModel):
    """Word-level diff between original and improved copy."""
    added_words_count: int = 0
    deleted_words_count: int = 0
    modified_ratio: float = 0.0
    summary: str = ""
    chunks: List[StructuredDiffChunk] = Field(default_factory=list)


class FactualPreservationResult(BaseModel):
    """Verification outcome of protected factual anchors during rewriting."""
    status: str = Field(..., description="'verified', 'repaired', or 'failed'")
    preserved_helplines: List[str] = Field(default_factory=list)
    preserved_dates: List[str] = Field(default_factory=list)
    preserved_urls: List[str] = Field(default_factory=list)
    preserved_placeholders: List[str] = Field(default_factory=list)
    missing_helplines: List[str] = Field(default_factory=list)
    missing_dates: List[str] = Field(default_factory=list)
    details: str = "All verified factual anchors were preserved intact."


class ToneImproveResponse(BaseModel):
    """Structured response containing revised copy and factual preservation verification."""
    content_asset_id: int
    original_content: str
    improved_content: str
    target_tone: str
    adjustment_instruction: Optional[str] = None
    rationale: str
    suggestions: List[str] = Field(default_factory=list)
    diff: StructuredDiff
    factual_preservation: FactualPreservationResult

