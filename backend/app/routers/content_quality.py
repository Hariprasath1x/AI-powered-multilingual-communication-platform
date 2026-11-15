"""FastAPI router for Content Quality, Compliance Audit, and Editorial Review endpoints."""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.core.dependencies import require_role
from app.schemas.content_quality import (
    FindingDecisionUpdateRequest,
    ContentQualityFindingResponse,
    ContentQualityAssessmentResponse,
    EditorialReadinessResponse,
    QualityEvaluateRequest,
)
from app.services import quality_service

logger = logging.getLogger("masscommai.content_quality_router")

router = APIRouter(prefix="/content", tags=["Content Quality & Compliance"])

QUALITY_READ_ROLES = ["Admin", "Campaign Manager", "Communication Team"]
QUALITY_WRITE_ROLES = ["Admin", "Campaign Manager"]


@router.post(
    "/{id}/evaluate",
    response_model=ContentQualityAssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger comprehensive content quality and compliance assessment",
)
async def evaluate_content_quality(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    payload: Optional[QualityEvaluateRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(QUALITY_WRITE_ROLES)),
) -> Any:
    """
    Executes deterministic rules and AI-assisted editorial intelligence on the content asset.
    Stores assessment scores, staleness fingerprint hash, and categorized findings.
    Accessible to Admin and Campaign Manager.
    """
    reference_facts = payload.reference_facts if payload else None
    provider_type = payload.provider_type if payload else None

    assessment = await quality_service.evaluate_content_asset(
        db=db,
        asset_id=id,
        current_user=current_user,
        reference_facts=reference_facts,
        provider_type=provider_type,
    )
    return assessment


@router.get(
    "/{id}/quality",
    response_model=Optional[ContentQualityAssessmentResponse],
    summary="Retrieve latest quality assessment report for a content asset",
)
def get_latest_quality_assessment(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(QUALITY_READ_ROLES)),
) -> Any:
    """
    Retrieves the most recent quality assessment with freshness staleness detection.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    assessment = quality_service.get_latest_assessment(db=db, asset_id=id)
    return assessment


@router.get(
    "/{id}/quality/history",
    response_model=List[ContentQualityAssessmentResponse],
    summary="Retrieve audit assessment history for a content asset",
)
def get_quality_assessment_history(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(QUALITY_READ_ROLES)),
) -> Any:
    """Returns chronological audit trail of all evaluations performed on this content asset."""
    history = quality_service.get_assessment_history(db=db, asset_id=id)
    return history


@router.patch(
    "/{id}/quality/findings/{finding_id}",
    response_model=ContentQualityFindingResponse,
    summary="Record human reviewer decision on an individual editorial finding",
)
def update_finding_decision(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    finding_id: int = Path(..., ge=1, description="Quality Finding ID"),
    payload: FindingDecisionUpdateRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(QUALITY_WRITE_ROLES)),
) -> Any:
    """
    Updates the reviewer decision for a specific finding (accepted, rejected, corrected)
    along with editorial notes and timestamp audit records.
    Accessible to Admin and Campaign Manager.
    """
    finding = quality_service.update_finding_decision(
        db=db,
        finding_id=finding_id,
        payload=payload,
        current_user=current_user,
    )
    return finding


@router.get(
    "/{id}/editorial-readiness",
    response_model=EditorialReadinessResponse,
    summary="Get editorial readiness summary and approval blocker status",
)
def get_editorial_readiness(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(QUALITY_READ_ROLES)),
) -> Any:
    """
    Returns high-level editorial readiness status indicating whether the asset can be
    formally approved or whether critical issues / outdated evaluations block approval.
    """
    readiness = quality_service.get_editorial_readiness(db=db, asset_id=id)
    return readiness

