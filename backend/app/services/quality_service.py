"""Service layer for Content Quality, Editorial Intelligence, and Compliance Evaluation."""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select, desc, or_, func
from sqlalchemy.orm import Session, joinedload

from app.models.user import User
from app.models.campaign import Campaign
from app.models.content_asset import ContentAsset
from app.models.content_quality import ContentQualityAssessment, ContentQualityFinding
from app.models.compliance_rule import ComplianceRule
from app.schemas.content_quality import (
    FindingDecisionUpdateRequest,
    ContentQualityFindingResponse,
    ContentQualityAssessmentResponse,
    EditorialReadinessResponse,
)
from app.services.quality.base import (
    FindingCategory,
    FindingSeverity,
    EvaluationSource,
    ReviewerDecision,
    AssessmentStatus,
    ContentQualityFindingDTO,
)
from app.services.quality.rule_engine import DeterministicRuleEngine
from app.services.quality.scoring import calculate_quality_score
from app.services.ai.base import (
    ContentEvaluationRequest,
    AIProviderError,
    AIProviderTimeoutError,
)
from app.services.ai.factory import get_ai_provider

logger = logging.getLogger("masscommai.quality_service")


def compute_content_version_hash(title: str, body: str, call_to_action: Optional[str]) -> str:
    """Compute SHA-256 fingerprint of content copy to detect subsequent modifications."""
    raw = f"{(title or '').strip()}|{(body or '').strip()}|{(call_to_action or '').strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _check_editorial_permission(current_user: User) -> None:
    """Ensure user has Admin or Campaign Manager role."""
    role_name = current_user.role.name if current_user.role else ""
    if role_name not in ("Admin", "Campaign Manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins and Campaign Managers have permission to run quality evaluations or record editorial decisions.",
        )


async def evaluate_content_asset(
    db: Session,
    asset_id: int,
    current_user: User,
    reference_facts: Optional[str] = None,
    provider_type: Optional[str] = None,
) -> ContentQualityAssessmentResponse:
    """
    Executes comprehensive content quality evaluation combining deterministic
    compliance rules and AI-assisted editorial intelligence.
    Persists assessment and findings with version hash.
    """
    _check_editorial_permission(current_user)

    stmt = (
        select(ContentAsset)
        .options(
            joinedload(ContentAsset.parent),
            joinedload(ContentAsset.creator),
            joinedload(ContentAsset.campaign).joinedload(Campaign.creator),
        )
        .where(ContentAsset.id == asset_id)
    )
    asset = db.execute(stmt).scalar_one_or_none()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content asset with ID {asset_id} not found.",
        )

    current_hash = compute_content_version_hash(asset.title, asset.body, asset.call_to_action)

    # Resolve applicable organization scope
    target_org = None
    if asset.campaign and asset.campaign.creator and asset.campaign.creator.organization:
        target_org = asset.campaign.creator.organization
    elif asset.creator and asset.creator.organization:
        target_org = asset.creator.organization

    # Bulk load active dynamic compliance rules matching org/global and channel/language
    rule_stmt = select(ComplianceRule).where(
        ComplianceRule.is_active == True,
        or_(
            ComplianceRule.is_global == True,
            ComplianceRule.organization.is_(None),
            ComplianceRule.organization == target_org,
        ),
    )
    if asset.channel:
        rule_stmt = rule_stmt.where(
            or_(
                ComplianceRule.channel.is_(None),
                func.lower(ComplianceRule.channel) == asset.channel.lower(),
            )
        )
    effective_lang = asset.target_language or asset.source_language
    if effective_lang:
        rule_stmt = rule_stmt.where(
            or_(
                ComplianceRule.language.is_(None),
                func.lower(ComplianceRule.language) == effective_lang.lower(),
            )
        )
    compliance_rules = db.execute(rule_stmt).scalars().all()

    # 1. Execute Deterministic Rule Engine
    parent_title = asset.parent.title if asset.parent else None
    parent_body = asset.parent.body if asset.parent else None
    parent_cta = asset.parent.call_to_action if asset.parent else None

    deterministic_findings: List[ContentQualityFindingDTO] = DeterministicRuleEngine.evaluate(
        title=asset.title,
        body=asset.body,
        call_to_action=asset.call_to_action,
        channel=asset.channel,
        source_language=asset.source_language,
        target_language=asset.target_language,
        reference_facts=reference_facts,
        parent_title=parent_title,
        parent_body=parent_body,
        parent_cta=parent_cta,
        compliance_rules=compliance_rules,
    )

    # 2. Execute AI-assisted Evaluation
    ai_findings: List[ContentQualityFindingDTO] = []
    ai_dimension_scores: Dict[str, float] = {}
    evaluator_metadata: Dict[str, Any] = {
        "deterministic_rules_count": len(deterministic_findings),
        "compliance_rules_loaded": len(compliance_rules),
    }
    if target_org:
        evaluator_metadata["target_organization"] = target_org
    ai_provider = get_ai_provider(provider_type)

    try:
        ai_req = ContentEvaluationRequest(
            title=asset.title,
            body=asset.body,
            call_to_action=asset.call_to_action,
            category=asset.category,
            tone=asset.tone,
            channel=asset.channel,
            source_language=asset.source_language,
            target_language=asset.target_language,
            reference_facts=reference_facts,
            parent_title=parent_title,
            parent_body=parent_body,
            parent_cta=parent_cta,
        )
        ai_res = await ai_provider.evaluate_content(ai_req)
        evaluator_metadata["ai_provider"] = ai_provider.get_provider_name()
        evaluator_metadata["ai_summary"] = ai_res.summary
        ai_dimension_scores = ai_res.dimension_scores

        for f in ai_res.findings:
            try:
                cat = FindingCategory(f.category)
            except ValueError:
                cat = FindingCategory.GRAMMAR
            try:
                sev = FindingSeverity(f.severity)
            except ValueError:
                sev = FindingSeverity.MEDIUM

            ai_findings.append(
                ContentQualityFindingDTO(
                    category=cat,
                    severity=sev,
                    title=f.title,
                    explanation=f.explanation,
                    affected_text=f.affected_text,
                    suggested_correction=f.suggested_correction,
                    evaluation_source=EvaluationSource.AI,
                    confidence=f.confidence,
                    rule_id=None,
                )
            )
    except AIProviderTimeoutError as exc:
        logger.warning("AI quality evaluation timed out: %s. Proceeding with deterministic rules.", exc)
        evaluator_metadata["ai_warning"] = "AI evaluation timed out; deterministic rules applied exclusively."
        deterministic_findings.append(
            ContentQualityFindingDTO(
                category=FindingCategory.COMPLETENESS,
                severity=FindingSeverity.INFORMATIONAL,
                title="AI Assistance Unavailable (Timeout)",
                explanation="AI evaluation service did not respond within the bounded timeout. Deterministic safety checks completed successfully.",
                suggested_correction="Retry AI evaluation later or proceed with manual human review.",
                evaluation_source=EvaluationSource.DETERMINISTIC,
                confidence=1.0,
            )
        )
    except Exception as exc:
        logger.warning("AI quality evaluation failed (%s). Proceeding with deterministic rules.", exc)
        evaluator_metadata["ai_warning"] = f"AI evaluation skipped: {str(exc)}"
        deterministic_findings.append(
            ContentQualityFindingDTO(
                category=FindingCategory.COMPLETENESS,
                severity=FindingSeverity.INFORMATIONAL,
                title="AI Assistance Unavailable",
                explanation=f"AI evaluation service was unreachable ({str(exc)[:100]}). Deterministic compliance rules applied.",
                suggested_correction="Ensure provider credentials are configured or proceed with manual review.",
                evaluation_source=EvaluationSource.DETERMINISTIC,
                confidence=1.0,
            )
        )

    # Combine findings
    all_findings = deterministic_findings + ai_findings
    is_translation = bool(asset.target_language and asset.target_language != asset.source_language)

    # 3. Compute Transparent Quality Score & Dimension Scores
    overall_score, dim_scores, assessment_status, counts = calculate_quality_score(
        findings=all_findings,
        is_translation=is_translation,
        ai_dimension_scores=ai_dimension_scores,
    )

    evaluator_type = "hybrid" if ai_findings else "deterministic"

    # 4. Persist ContentQualityAssessment
    assessment = ContentQualityAssessment(
        content_asset_id=asset.id,
        content_version_hash=current_hash,
        overall_score=overall_score,
        status=assessment_status.value,
        dimension_scores=dim_scores.model_dump(),
        evaluator_type=evaluator_type,
        evaluator_metadata=evaluator_metadata,
        critical_issues_count=counts["critical"],
        high_issues_count=counts["high"],
        medium_issues_count=counts["medium"],
        low_issues_count=counts["low"],
        info_issues_count=counts["info"],
        created_by=current_user.id,
    )
    db.add(assessment)
    db.flush()

    # Persist Findings
    for dto in all_findings:
        finding = ContentQualityFinding(
            assessment_id=assessment.id,
            category=dto.category.value,
            severity=dto.severity.value,
            title=dto.title,
            explanation=dto.explanation,
            affected_text=dto.affected_text,
            suggested_correction=dto.suggested_correction,
            evaluation_source=dto.evaluation_source.value,
            confidence=dto.confidence,
            rule_id=dto.rule_id,
            reviewer_decision="pending",
        )
        db.add(finding)

    db.commit()
    db.refresh(assessment)

    return _build_assessment_response(assessment, asset)


def get_latest_assessment(
    db: Session,
    asset_id: int,
) -> Optional[ContentQualityAssessmentResponse]:
    """Retrieve the latest quality assessment for an asset with staleness detection."""
    asset = db.get(ContentAsset, asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content asset with ID {asset_id} not found.",
        )

    stmt = (
        select(ContentQualityAssessment)
        .options(joinedload(ContentQualityAssessment.findings))
        .where(ContentQualityAssessment.content_asset_id == asset_id)
        .order_by(desc(ContentQualityAssessment.created_at), desc(ContentQualityAssessment.id))
    )
    assessments = db.execute(stmt).scalars().unique().all()
    # Filter out variant-specific assessments so root asset assessments are returned
    asset_assessments = [
        a for a in assessments
        if not (a.evaluator_metadata and a.evaluator_metadata.get("target_type") == "content_variant")
    ]
    if not asset_assessments:
        return None

    return _build_assessment_response(asset_assessments[0], asset)


def get_assessment_history(
    db: Session,
    asset_id: int,
) -> List[ContentQualityAssessmentResponse]:
    """Retrieve all historical quality assessments for an asset."""
    asset = db.get(ContentAsset, asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content asset with ID {asset_id} not found.",
        )

    stmt = (
        select(ContentQualityAssessment)
        .options(joinedload(ContentQualityAssessment.findings))
        .where(ContentQualityAssessment.content_asset_id == asset_id)
        .order_by(desc(ContentQualityAssessment.created_at), desc(ContentQualityAssessment.id))
    )
    assessments = db.execute(stmt).scalars().unique().all()
    asset_assessments = [
        a for a in assessments
        if not (a.evaluator_metadata and a.evaluator_metadata.get("target_type") == "content_variant")
    ]
    return [_build_assessment_response(a, asset) for a in asset_assessments]


def update_finding_decision(
    db: Session,
    finding_id: int,
    payload: FindingDecisionUpdateRequest,
    current_user: User,
) -> ContentQualityFindingResponse:
    """Record a human reviewer's decision on an editorial finding."""
    _check_editorial_permission(current_user)

    finding = db.get(ContentQualityFinding, finding_id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quality finding with ID {finding_id} not found.",
        )

    finding.reviewer_decision = payload.reviewer_decision
    finding.decision_notes = payload.decision_notes
    finding.resolved_by = current_user.id
    finding.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(finding)

    return ContentQualityFindingResponse.model_validate(finding)


def get_editorial_readiness(
    db: Session,
    asset_id: int,
) -> EditorialReadinessResponse:
    """
    Determines whether a content asset is editorially ready for human review sign-off.
    Blocks approval if no assessment exists, if content was edited post-assessment (outdated),
    or if any critical findings remain unresolved.
    """
    asset = db.get(ContentAsset, asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content asset with ID {asset_id} not found.",
        )

    stmt = (
        select(ContentQualityAssessment)
        .options(joinedload(ContentQualityAssessment.findings))
        .where(ContentQualityAssessment.content_asset_id == asset_id)
        .order_by(desc(ContentQualityAssessment.created_at), desc(ContentQualityAssessment.id))
    )
    assessments = db.execute(stmt).scalars().unique().all()
    asset_assessments = [
        a for a in assessments
        if not (a.evaluator_metadata and a.evaluator_metadata.get("target_type") == "content_variant")
    ]
    assessment = asset_assessments[0] if asset_assessments else None

    if not assessment:
        return EditorialReadinessResponse(
            content_asset_id=asset_id,
            has_assessment=False,
            is_outdated=False,
            overall_score=None,
            critical_unresolved_count=0,
            is_approval_blocked=True,
            blocking_reasons=["Content has not been evaluated for quality and compliance."],
            readiness_status="Not Evaluated",
        )

    current_hash = compute_content_version_hash(asset.title, asset.body, asset.call_to_action)
    is_outdated = (assessment.content_version_hash != current_hash)

    # Check for unresolved critical findings
    unresolved_critical = [
        f for f in assessment.findings
        if f.severity == "critical" and f.reviewer_decision == "pending"
    ]

    blocking_reasons: List[str] = []
    if assessment.content_asset_id != asset_id:
        blocking_reasons.append("Quality assessment record does not match target content asset.")
    if getattr(assessment, "status", None) in ("failed", "error"):
        blocking_reasons.append("Quality assessment failed or was incomplete. Re-evaluation required.")
    if is_outdated:
        blocking_reasons.append("Content has been modified since the last quality assessment. Re-evaluation required.")
    if unresolved_critical:
        blocking_reasons.append(
            f"{len(unresolved_critical)} critical issue(s) require reviewer resolution before editorial approval."
        )

    is_blocked = len(blocking_reasons) > 0

    if is_blocked:
        status_label = "Evaluation Outdated" if is_outdated else "Needs Correction"
    else:
        status_label = "Ready for Approval"

    return EditorialReadinessResponse(
        content_asset_id=asset_id,
        has_assessment=True,
        is_outdated=is_outdated,
        overall_score=assessment.overall_score,
        critical_unresolved_count=len(unresolved_critical),
        is_approval_blocked=is_blocked,
        blocking_reasons=blocking_reasons,
        readiness_status=status_label,
    )


def validate_content_approval_readiness(
    db: Session,
    asset_id: int,
) -> Tuple[bool, Optional[str], List[str]]:
    """
    Validates whether a content asset satisfies all quality invariants for approval.
    Enforces Invariants A, B, and C:
    - Assessment must exist (Invariant A).
    - Assessment lookup must succeed (fails closed).
    - Assessment must not be failed/incomplete (Invariant B).
    - Assessment must belong to target asset (Invariant B).
    - Assessment must be fresh matching current content hash (Invariant C).
    - Assessment must have zero unresolved critical findings (Invariant B).

    Returns:
        (is_eligible: bool, error_code: Optional[str], blocking_reasons: List[str])
    """
    try:
        readiness = get_editorial_readiness(db, asset_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Quality assessment lookup failed for asset %d: %s", asset_id, exc)
        return False, "QUALITY_ASSESSMENT_ERROR", [f"Quality assessment verification failed: {exc}"]

    if not readiness.has_assessment:
        return False, "QUALITY_ASSESSMENT_REQUIRED", readiness.blocking_reasons
    if readiness.is_outdated:
        return False, "QUALITY_ASSESSMENT_STALE", readiness.blocking_reasons
    if readiness.is_approval_blocked or (readiness.critical_unresolved_count > 0):
        return False, "CONTENT_HAS_BLOCKING_ISSUES", readiness.blocking_reasons

    return True, None, []


def validate_content_dispatch_eligibility(
    db: Session,
    asset: Optional[ContentAsset],
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates Invariant E for broadcasting/dispatching a ContentAsset.
    Enforces that:
    1. Asset is not None.
    2. Asset review_status is 'Approved'.
    3. Asset has a valid quality assessment.
    4. Asset is not modified post-assessment (not outdated).
    5. Asset has 0 unresolved critical findings.

    Returns:
        (is_eligible: bool, error_code: Optional[str], error_message: Optional[str])
    """
    if asset is None:
        return False, "CONTENT_NOT_FOUND", "No valid content asset associated for delivery."

    if asset.review_status != "Approved":
        return (
            False,
            "CONTENT_NOT_APPROVED",
            f"Content asset #{asset.id} review status is '{asset.review_status}'. Only 'Approved' content can be dispatched.",
        )

    try:
        readiness = get_editorial_readiness(db, asset.id)
    except Exception as exc:
        logger.error("Failed to verify quality readiness for content asset #%d: %s", asset.id, exc)
        return (
            False,
            "QUALITY_ASSESSMENT_ERROR",
            f"Failed to verify quality readiness for content asset #{asset.id}: {exc}",
        )

    if not readiness.has_assessment:
        return (
            False,
            "QUALITY_ASSESSMENT_REQUIRED",
            f"Content asset #{asset.id} has no quality assessment. Mandatory quality assessment is required before distribution.",
        )
    if readiness.is_outdated:
        return (
            False,
            "QUALITY_ASSESSMENT_STALE",
            f"Content asset #{asset.id} was modified after its quality audit. Re-evaluation required before distribution.",
        )
    if readiness.is_approval_blocked or (readiness.critical_unresolved_count > 0):
        reasons = "; ".join(readiness.blocking_reasons)
        return (
            False,
            "CONTENT_HAS_BLOCKING_ISSUES",
            f"Content asset #{asset.id} has blocking quality issues: {reasons}",
        )

    return True, None, None


# ---------------------------------------------------------------------------
# Task 9.A: Content Variant Quality Assessment & Security Gating
# ---------------------------------------------------------------------------

def validate_variant_approval_readiness(
    db: Session,
    variant: Any,
) -> Tuple[bool, Optional[str], List[str]]:
    """
    Validates whether a ContentVariant satisfies all quality invariants for approval.
    Enforces Invariants A, B, and C on content variants:
    1. Variant must have a linked assessment (assessment_id).
    2. Assessment must exist in DB.
    3. Assessment must belong specifically to this variant (not parent asset or other variant).
    4. Assessment content_version_hash must match current variant text (freshness).
    5. Assessment must have zero unresolved critical findings.
    """
    from app.services.personalization_service import compute_variant_hash
    current_hash = compute_variant_hash(variant.variant_title, variant.variant_body, variant.variant_cta)

    if not variant.assessment_id:
        return False, "VARIANT_ASSESSMENT_REQUIRED", ["Variant has not undergone quality assessment."]

    assessment = db.get(ContentQualityAssessment, variant.assessment_id)
    if not assessment:
        return False, "VARIANT_ASSESSMENT_NOT_FOUND", ["Linked quality assessment record not found."]

    # Verify assessment belongs to this specific variant (Invariant B / Scenario 3)
    meta = assessment.evaluator_metadata or {}
    is_variant_assessment = (meta.get("target_type") == "content_variant" and meta.get("variant_id") == variant.id)
    if not is_variant_assessment:
        return False, "PARENT_ASSESSMENT_NOT_APPLICABLE", [
            "An assessment belonging to the parent content asset cannot authorize a demographic variant."
        ]

    # Verify freshness (Invariant C / Scenario 5)
    if assessment.content_version_hash != current_hash:
        return False, "VARIANT_ASSESSMENT_STALE", [
            "Variant was modified after quality audit. Fresh assessment required before approval."
        ]

    # Verify no critical issues (Invariant B / Scenario 6)
    if assessment.critical_issues_count > 0:
        return False, "VARIANT_HAS_BLOCKING_ISSUES", [
            f"Variant has {assessment.critical_issues_count} unresolved critical compliance findings."
        ]

    return True, None, []


def validate_variant_dispatch_eligibility(
    db: Session,
    variant: Optional[Any],
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates Invariant E for broadcasting/staging a ContentVariant.
    Enforces that:
    1. Variant is not None.
    2. Variant review_status is 'Approved'.
    3. Variant has a valid quality assessment linked.
    4. Assessment belongs specifically to this variant.
    5. Assessment and variant hashes are fresh matching current content.
    6. Assessment has zero critical findings.
    """
    if variant is None:
        return False, "VARIANT_NOT_FOUND", "No valid variant associated for delivery."

    if variant.review_status != "Approved":
        return (
            False,
            "VARIANT_NOT_APPROVED",
            f"Variant #{variant.id} review status is '{variant.review_status}'. Only 'Approved' variants can be dispatched.",
        )

    is_ready, err_code, reasons = validate_variant_approval_readiness(db, variant)
    if not is_ready:
        return False, err_code, "; ".join(reasons)

    return True, None, None


def evaluate_content_variant(
    db: Session,
    variant_id: int,
    current_user: User,
) -> ContentQualityAssessment:
    """
    Executes compliance and quality evaluation specifically for a demographic ContentVariant.
    Creates and persists ContentQualityAssessment and ContentQualityFinding records linked to this variant.
    Updates variant.assessment_id and variant.content_version_hash.
    """
    _check_editorial_permission(current_user)
    from app.models.content_variant import ContentVariant
    from app.services.personalization_service import compute_variant_hash
    from app.services.quality.scoring import calculate_quality_score

    variant = db.get(ContentVariant, variant_id)
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content variant #{variant_id} not found.",
        )

    # Multi-tenant boundary check
    user_role = current_user.role.name if current_user.role else "Viewer"
    is_admin = (user_role == "Admin")
    user_org = getattr(current_user, "organization", None)
    asset_org = None
    if variant.campaign and variant.campaign.creator:
        asset_org = getattr(variant.campaign.creator, "organization", None)
    elif variant.creator:
        asset_org = getattr(variant.creator, "organization", None)

    if not is_admin and user_org and asset_org and user_org != asset_org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Content variant belongs to another organization.",
        )

    current_hash = compute_variant_hash(variant.variant_title, variant.variant_body, variant.variant_cta)

    # Bulk load active dynamic compliance rules
    active_rules: List[Any] = []
    try:
        rule_query = select(ComplianceRule).where(
            ComplianceRule.is_active == True,
            or_(
                ComplianceRule.is_global == True,
                ComplianceRule.organization.is_(None),
                ComplianceRule.organization == user_org,
            ),
        )
        active_rules = list(db.execute(rule_query).scalars().all())
    except Exception:
        active_rules = []

    # Run deterministic compliance check
    deterministic_findings = DeterministicRuleEngine.evaluate(
        channel=variant.channel,
        title=variant.variant_title,
        body=variant.variant_body,
        call_to_action=variant.variant_cta,
        source_language="en",
        target_language=variant.language,
        compliance_rules=active_rules,
    )

    overall_score, dim_scores, assessment_status, counts = calculate_quality_score(
        findings=deterministic_findings,
        is_translation=False,
    )

    evaluator_metadata = {
        "target_type": "content_variant",
        "variant_id": variant.id,
        "segment_id": variant.segment_id,
        "channel": variant.channel,
        "language": variant.language,
        "target_organization": user_org,
    }

    assessment = ContentQualityAssessment(
        content_asset_id=variant.source_content_id,
        content_version_hash=current_hash,
        overall_score=overall_score,
        status=assessment_status.value,
        dimension_scores=dim_scores.model_dump(),
        evaluator_type="deterministic",
        evaluator_metadata=evaluator_metadata,
        critical_issues_count=counts["critical"],
        high_issues_count=counts["high"],
        medium_issues_count=counts["medium"],
        low_issues_count=counts["low"],
        info_issues_count=counts["info"],
        created_by=current_user.id,
    )
    db.add(assessment)
    db.flush()

    for dto in deterministic_findings:
        finding = ContentQualityFinding(
            assessment_id=assessment.id,
            category=dto.category.value,
            severity=dto.severity.value,
            title=dto.title,
            explanation=dto.explanation,
            affected_text=dto.affected_text,
            suggested_correction=dto.suggested_correction,
            evaluation_source=dto.evaluation_source.value,
            confidence=dto.confidence,
            rule_id=dto.rule_id,
            reviewer_decision="pending",
        )
        db.add(finding)

    # Link variant to this exact assessment and hash
    variant.assessment_id = assessment.id
    variant.content_version_hash = current_hash
    db.commit()
    db.refresh(variant)
    db.refresh(assessment)
    return assessment



def _build_assessment_response(
    assessment: ContentQualityAssessment,
    asset: Optional[ContentAsset] = None,
    variant: Optional[Any] = None,
) -> ContentQualityAssessmentResponse:
    """Helper to construct ContentQualityAssessmentResponse with freshness detection."""
    if variant is not None:
        from app.services.personalization_service import compute_variant_hash
        current_hash = compute_variant_hash(
            variant.variant_title or "",
            variant.variant_body or "",
            variant.variant_cta,
        )
        is_outdated = (assessment.content_version_hash != current_hash)
    elif asset is not None:
        current_hash = compute_content_version_hash(asset.title, asset.body, asset.call_to_action)
        is_outdated = (assessment.content_version_hash != current_hash)
    else:
        is_outdated = False

    return ContentQualityAssessmentResponse(
        id=assessment.id,
        content_asset_id=assessment.content_asset_id,
        content_version_hash=assessment.content_version_hash,
        is_outdated=is_outdated,
        overall_score=assessment.overall_score,
        status="outdated" if is_outdated else assessment.status,
        dimension_scores=assessment.dimension_scores or {},
        evaluator_type=assessment.evaluator_type,
        evaluator_metadata=assessment.evaluator_metadata or {},
        critical_issues_count=assessment.critical_issues_count,
        high_issues_count=assessment.high_issues_count,
        medium_issues_count=assessment.medium_issues_count,
        low_issues_count=assessment.low_issues_count,
        info_issues_count=assessment.info_issues_count,
        findings=[ContentQualityFindingResponse.model_validate(f) for f in assessment.findings],
        created_by=assessment.created_by,
        created_at=assessment.created_at,
    )
