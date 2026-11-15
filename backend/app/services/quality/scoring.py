"""Transparent Quality Scoring and Penalty Engine with Safety Overrides."""

from typing import List, Optional, Tuple, Dict
from app.services.quality.base import (
    FindingCategory,
    FindingSeverity,
    AssessmentStatus,
    DimensionScores,
    ContentQualityFindingDTO,
    QualityEvaluationResult,
)

# Standard Dimension Weights (sum = 1.0)
STANDARD_WEIGHTS = {
    "language_grammar": 0.20,
    "readability": 0.15,
    "tone_consistency": 0.15,
    "translation_consistency": 0.20,
    "factual_consistency": 0.20,
    "channel_compliance": 0.10,
}

# Finding severity penalties per occurrence
SEVERITY_PENALTIES = {
    FindingSeverity.CRITICAL: 40.0,
    FindingSeverity.HIGH: 20.0,
    FindingSeverity.MEDIUM: 10.0,
    FindingSeverity.LOW: 5.0,
    FindingSeverity.INFORMATIONAL: 0.0,
}

# Category to Dimension mapping
CATEGORY_DIMENSION_MAP = {
    FindingCategory.GRAMMAR: "language_grammar",
    FindingCategory.COMPLETENESS: "language_grammar",
    FindingCategory.READABILITY: "readability",
    FindingCategory.TONE: "tone_consistency",
    FindingCategory.TRANSLATION: "translation_consistency",
    FindingCategory.PLACEHOLDER: "translation_consistency",  # Or channel/translation
    FindingCategory.FACTUAL: "factual_consistency",
    FindingCategory.SAFETY_SENSITIVE: "factual_consistency",
    FindingCategory.COMPLIANCE: "factual_consistency",
    FindingCategory.CHANNEL: "channel_compliance",
}


def calculate_quality_score(
    findings: List[ContentQualityFindingDTO],
    is_translation: bool = False,
    ai_dimension_scores: Optional[Dict[str, float]] = None,
) -> Tuple[float, DimensionScores, AssessmentStatus, Dict[str, int]]:
    """
    Computes explainable quality score (0-100) and dimension sub-scores.
    Re-normalizes weights dynamically when translation is not applicable.
    Enforces the Safety Override rule: Any CRITICAL issue caps the overall score at <= 49.0.
    """
    # 1. Initialize baseline dimension scores (100.0)
    scores = {
        "language_grammar": 100.0,
        "readability": 100.0,
        "tone_consistency": 100.0,
        "translation_consistency": 100.0 if is_translation else None,
        "factual_consistency": 100.0,
        "channel_compliance": 100.0,
    }

    # Blend AI-reported dimension scores if provided
    if ai_dimension_scores:
        for dim, ai_val in ai_dimension_scores.items():
            if dim in scores and scores[dim] is not None and isinstance(ai_val, (int, float)):
                # Weighted average: 50% AI assessment, 50% baseline
                scores[dim] = min(100.0, max(0.0, float(ai_val)))

    # 2. Apply findings penalties by dimension
    critical_count = 0
    high_count = 0
    medium_count = 0
    low_count = 0
    info_count = 0

    for finding in findings:
        sev = finding.severity
        if sev == FindingSeverity.CRITICAL:
            critical_count += 1
        elif sev == FindingSeverity.HIGH:
            high_count += 1
        elif sev == FindingSeverity.MEDIUM:
            medium_count += 1
        elif sev == FindingSeverity.LOW:
            low_count += 1
        elif sev == FindingSeverity.INFORMATIONAL:
            info_count += 1

        dim_key = CATEGORY_DIMENSION_MAP.get(finding.category, "language_grammar")
        if dim_key == "translation_consistency" and not is_translation:
            # Map translation placeholder issue to language_grammar if not a translation asset
            dim_key = "language_grammar"

        penalty = SEVERITY_PENALTIES.get(sev, 0.0)
        if scores[dim_key] is not None:
            scores[dim_key] = max(0.0, scores[dim_key] - penalty)

    # 3. Dynamic Weight Re-normalization
    weights: Dict[str, float] = {}
    if is_translation:
        weights = STANDARD_WEIGHTS.copy()
    else:
        # Re-normalize 5 applicable weights without translation_consistency
        total_non_trans_weight = sum(w for k, w in STANDARD_WEIGHTS.items() if k != "translation_consistency")
        for k, w in STANDARD_WEIGHTS.items():
            if k != "translation_consistency":
                weights[k] = w / total_non_trans_weight

    # 4. Compute weighted overall score
    raw_overall = 0.0
    for dim, weight in weights.items():
        dim_score = scores.get(dim)
        if dim_score is not None:
            raw_overall += dim_score * weight

    raw_overall = round(max(0.0, min(100.0, raw_overall)), 1)

    # 5. SAFETY OVERRIDE:
    # "Never let a high numerical score hide a critical factual or safety concern."
    # If any critical issue is present, cap score at 49.0
    if critical_count > 0:
        overall_score = min(raw_overall, 49.0)
    else:
        overall_score = raw_overall

    # 6. Determine Assessment Status
    if critical_count > 0 or overall_score < 70.0:
        status = AssessmentStatus.COMPLETED_WITH_WARNINGS
    else:
        status = AssessmentStatus.COMPLETED

    dim_scores = DimensionScores(
        language_grammar=round(scores["language_grammar"], 1),
        readability=round(scores["readability"], 1),
        tone_consistency=round(scores["tone_consistency"], 1),
        translation_consistency=round(scores["translation_consistency"], 1) if scores["translation_consistency"] is not None else None,
        factual_consistency=round(scores["factual_consistency"], 1),
        channel_compliance=round(scores["channel_compliance"], 1),
    )

    counts = {
        "critical": critical_count,
        "high": high_count,
        "medium": medium_count,
        "low": low_count,
        "info": info_count,
    }

    return overall_score, dim_scores, status, counts

