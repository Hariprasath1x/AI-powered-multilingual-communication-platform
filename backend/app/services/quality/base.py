"""Quality assessment models and finding contracts for Content Quality and Compliance Engine."""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class FindingCategory(str, Enum):
    GRAMMAR = "grammar"
    READABILITY = "readability"
    TONE = "tone"
    TRANSLATION = "translation"
    FACTUAL = "factual"
    CHANNEL = "channel"
    SAFETY_SENSITIVE = "safety_sensitive"
    PLACEHOLDER = "placeholder"
    COMPLETENESS = "completeness"
    COMPLIANCE = "compliance"


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class EvaluationSource(str, Enum):
    DETERMINISTIC = "deterministic"
    AI = "ai"


class ReviewerDecision(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CORRECTED = "corrected"


class AssessmentStatus(str, Enum):
    NOT_EVALUATED = "not_evaluated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    OUTDATED = "outdated"


class ContentQualityFindingDTO(BaseModel):
    """Data transfer object for an individual quality finding."""

    category: FindingCategory
    severity: FindingSeverity
    title: str = Field(..., max_length=255)
    explanation: str
    affected_text: Optional[str] = None
    suggested_correction: Optional[str] = None
    evaluation_source: EvaluationSource = EvaluationSource.DETERMINISTIC
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    rule_id: Optional[str] = None


class DimensionScores(BaseModel):
    """Dimension-level scores (0-100) across six key assessment axes."""

    language_grammar: float = 100.0
    readability: float = 100.0
    tone_consistency: float = 100.0
    translation_consistency: Optional[float] = None  # None when not applicable
    factual_consistency: float = 100.0
    channel_compliance: float = 100.0


class QualityEvaluationResult(BaseModel):
    """Aggregate result from deterministic rules and AI evaluation."""

    overall_score: float = Field(..., ge=0.0, le=100.0)
    status: AssessmentStatus
    dimension_scores: DimensionScores
    findings: List[ContentQualityFindingDTO] = Field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    evaluator_metadata: Dict[str, Any] = Field(default_factory=dict)

