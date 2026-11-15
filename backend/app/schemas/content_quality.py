"""Pydantic v2 schemas for Content Quality, Compliance, and Editorial Review."""

from datetime import datetime
from typing import List, Optional, Dict, Any, Set
from pydantic import BaseModel, Field, field_validator, ConfigDict

SUPPORTED_DECISIONS: Set[str] = {"accepted", "rejected", "corrected"}


class FindingDecisionUpdateRequest(BaseModel):
    """Payload to record a human reviewer's decision on a quality finding."""

    reviewer_decision: str = Field(..., description="accepted, rejected, or corrected")
    decision_notes: Optional[str] = Field(None, max_length=1000, description="Editorial justification or explanation")

    @field_validator("reviewer_decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        clean = v.lower().strip()
        if clean not in SUPPORTED_DECISIONS:
            raise ValueError(f"Decision must be one of: {', '.join(sorted(SUPPORTED_DECISIONS))}")
        return clean


class ContentQualityFindingResponse(BaseModel):
    """Full serialization of a content quality finding."""

    id: int
    assessment_id: int
    category: str
    severity: str
    title: str
    explanation: str
    affected_text: Optional[str] = None
    suggested_correction: Optional[str] = None
    evaluation_source: str
    confidence: Optional[float] = None
    rule_id: Optional[str] = None
    reviewer_decision: str
    decision_notes: Optional[str] = None
    resolved_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContentQualityAssessmentResponse(BaseModel):
    """Quality assessment report with dimension scores, findings, and freshness detection."""

    id: int
    content_asset_id: int
    content_version_hash: str
    is_outdated: bool = False
    overall_score: float
    status: str
    dimension_scores: Dict[str, Optional[float]]
    evaluator_type: str
    evaluator_metadata: Optional[Dict[str, Any]] = None
    critical_issues_count: int
    high_issues_count: int
    medium_issues_count: int
    low_issues_count: int
    info_issues_count: int
    findings: List[ContentQualityFindingResponse] = Field(default_factory=list)
    created_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EditorialReadinessResponse(BaseModel):
    """Summary of editorial readiness and approval guard status."""

    content_asset_id: int
    has_assessment: bool
    is_outdated: bool
    overall_score: Optional[float] = None
    critical_unresolved_count: int = 0
    is_approval_blocked: bool = False
    blocking_reasons: List[str] = Field(default_factory=list)
    readiness_status: str


class QualityEvaluateRequest(BaseModel):
    """Optional parameters when triggering a quality assessment."""

    reference_facts: Optional[str] = Field(None, max_length=2000, description="Explicit facts to verify against")
    provider_type: Optional[str] = Field(None, description="mock, gemini, or auto")

