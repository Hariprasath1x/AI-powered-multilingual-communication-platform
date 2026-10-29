"""FastAPI router for Audience Segmentation Engine and Dynamic Rule Builder."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.core.dependencies import require_role
from app.schemas.segment import (
    SegmentCreate,
    SegmentUpdate,
    SegmentResponse,
    PaginatedSegmentResponse,
    SegmentPreviewRequest,
    SegmentPreviewResponse,
    RuleGroup,
    SUPPORTED_SEGMENT_FIELDS,
)
from app.services import segment_service

router = APIRouter(prefix="/segments", tags=["Audience Segmentation"])

# Authorization roles:
# - Read & Preview access: Admin, Campaign Manager, Communication Team
# - Create access: Admin, Campaign Manager (Communication Team is restricted)
# - Update & Delete access: Admin (all), Campaign Manager (own segments only)
SEGMENT_READ_ROLES = ["Admin", "Campaign Manager", "Communication Team"]
SEGMENT_WRITE_ROLES = ["Admin", "Campaign Manager"]


@router.get(
    "/fields",
    summary="Get supported segmentation attributes, operators, and metadata",
)
def get_supported_fields(
    current_user: User = Depends(require_role(SEGMENT_READ_ROLES)),
):
    """
    Returns the server-enforced allowlist of audience attributes, data types,
    and compatible operators available for dynamic segmentation.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    return {
        "fields": SUPPORTED_SEGMENT_FIELDS,
        "max_conditions": 20,
        "max_depth": 2,
    }


@router.post(
    "/preview",
    response_model=SegmentPreviewResponse,
    summary="Preview audience members matching an unsaved rule definition",
)
def preview_unsaved_rules(
    payload: SegmentPreviewRequest,
    current_user: User = Depends(require_role(SEGMENT_READ_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Evaluates an unsaved rule definition directly against the audience database.
    Returns total matching count and a paginated sample of audience records.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    return segment_service.preview_rules(
        db=db,
        filter_rules=payload.filter_rules,
        page=payload.page,
        page_size=payload.page_size,
    )


@router.get(
    "",
    response_model=PaginatedSegmentResponse,
    summary="List saved audience segments with pagination and search",
)
def list_segments(
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term matching segment name or description"),
    current_user: User = Depends(require_role(SEGMENT_READ_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Retrieve paginated saved segments with creator metadata and matching audience counts.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    return segment_service.list_segments(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
    )


@router.post(
    "",
    response_model=SegmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new saved audience segment",
)
def create_segment(
    payload: SegmentCreate,
    current_user: User = Depends(require_role(SEGMENT_WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Creates a new audience segment with validated JSON criteria.
    Enforces segment name uniqueness and records creator ID.
    Authorized for Admin and Campaign Manager roles only.
    """
    return segment_service.create_segment(
        db=db,
        data=payload,
        current_user=current_user,
    )


@router.get(
    "/{segment_id}",
    response_model=SegmentResponse,
    summary="Retrieve a saved segment by ID",
)
def get_segment(
    segment_id: int = Path(..., ge=1, description="Segment primary key ID"),
    current_user: User = Depends(require_role(SEGMENT_READ_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Get segment definition, rule configuration, and current matching count by ID.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    return segment_service.get_segment_response(db=db, segment_id=segment_id)


@router.put(
    "/{segment_id}",
    response_model=SegmentResponse,
    summary="Update an existing audience segment",
)
def update_segment(
    payload: SegmentUpdate,
    segment_id: int = Path(..., ge=1, description="Segment primary key ID"),
    current_user: User = Depends(require_role(SEGMENT_WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Update segment name, description, and filter rules.
    Enforces ownership permissions: Admins can update any segment;
    Campaign Managers can only update segments they created.
    """
    return segment_service.update_segment(
        db=db,
        segment_id=segment_id,
        data=payload,
        current_user=current_user,
    )


@router.delete(
    "/{segment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an audience segment",
)
def delete_segment(
    segment_id: int = Path(..., ge=1, description="Segment primary key ID"),
    current_user: User = Depends(require_role(SEGMENT_WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Permanently delete an audience segment.
    Enforces ownership permissions: Admins can delete any segment;
    Campaign Managers can only delete segments they created.
    """
    segment_service.delete_segment(
        db=db,
        segment_id=segment_id,
        current_user=current_user,
    )
    return None


@router.get(
    "/{segment_id}/preview",
    response_model=SegmentPreviewResponse,
    summary="Preview current matching audience members for a saved segment",
)
def preview_saved_segment(
    segment_id: int = Path(..., ge=1, description="Segment primary key ID"),
    page: int = Query(1, ge=1, description="Sample pagination page index"),
    page_size: int = Query(10, ge=1, le=50, description="Sample page size (max 50)"),
    current_user: User = Depends(require_role(SEGMENT_READ_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Re-evaluates a saved segment's stored rules against current audience database records.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    segment = segment_service.get_segment_by_id(db=db, segment_id=segment_id)
    rule_group = RuleGroup.model_validate(segment.filter_rules)
    return segment_service.preview_rules(
        db=db,
        filter_rules=rule_group,
        page=page,
        page_size=page_size,
    )

