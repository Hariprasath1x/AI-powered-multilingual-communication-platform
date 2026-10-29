"""Audience management API routes: CRUD, filtering, pagination, aggregate stats, and bulk import."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, UploadFile, File, status, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.core.dependencies import require_role
from app.schemas.audience import (
    AudienceMemberCreate,
    AudienceMemberUpdate,
    AudienceMemberResponse,
    PaginatedAudienceResponse,
    AudienceStatsResponse,
    AudienceImportSummary,
)
from app.services import audience_service

router = APIRouter(prefix="/audience", tags=["Audience Management"])

# Authorization roles:
# - Read access: Admin, Campaign Manager, Communication Team
# - Write / Import / Delete access: Admin, Campaign Manager (Communication Team is restricted)
AUDIENCE_READ_ROLES = ["Admin", "Campaign Manager", "Communication Team"]
AUDIENCE_WRITE_ROLES = ["Admin", "Campaign Manager"]


@router.get(
    "",
    response_model=PaginatedAudienceResponse,
    summary="List audience members with pagination and search",
)
def list_audience(
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term matching name, email, phone, city, state, or occupation"),
    preferred_language: Optional[str] = Query(None, description="Filter by preferred language (e.g. en, hi, ta)"),
    preferred_channel: Optional[str] = Query(None, description="Filter by communication channel (Email, SMS, WhatsApp)"),
    gender: Optional[str] = Query(None, description="Filter by gender"),
    city: Optional[str] = Query(None, description="Filter by city"),
    state: Optional[str] = Query(None, description="Filter by state"),
    occupation: Optional[str] = Query(None, description="Filter by occupation"),
    consent_status: Optional[str] = Query(None, description="Filter by consent status: true (opt-in), false (opt-out), or unconfirmed"),
    sort_by: str = Query("created_at", description="Field to sort by: created_at, name, id, updated_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order: asc or desc"),
    current_user: User = Depends(require_role(AUDIENCE_READ_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Retrieve paginated audience members.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    return audience_service.list_audience_members(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        preferred_language=preferred_language,
        preferred_channel=preferred_channel,
        gender=gender,
        city=city,
        state=state,
        occupation=occupation,
        consent_status=consent_status,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get(
    "/stats",
    response_model=AudienceStatsResponse,
    summary="Get audience distribution statistics",
)
def get_audience_stats(
    current_user: User = Depends(require_role(AUDIENCE_READ_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Retrieve aggregate statistics including language, channel, and consent breakdowns.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    return audience_service.get_audience_stats(db=db)


@router.post(
    "",
    response_model=AudienceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new audience member",
)
def create_audience_member(
    payload: AudienceMemberCreate,
    current_user: User = Depends(require_role(AUDIENCE_WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Create a single audience member.
    Enforces contact handle existence and detects duplicate emails or phones.
    Authorized for Admin and Campaign Manager roles only.
    """
    return audience_service.create_audience_member(db=db, data=payload)


@router.post(
    "/import",
    response_model=AudienceImportSummary,
    summary="Bulk import audience records from CSV or Excel file",
)
async def import_audience(
    file: UploadFile = File(..., description="CSV (.csv) or modern Excel (.xlsx) file with audience records"),
    current_user: User = Depends(require_role(AUDIENCE_WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Bulk import audience members from a CSV or Excel spreadsheet.
    Validates each row independently, detects duplicates within the file and database,
    and returns an actionable import summary.
    Authorized for Admin and Campaign Manager roles only.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a valid filename.",
        )

    # Read up to MAX_FILE_SIZE_BYTES + 1 to prevent unbounded memory allocation
    file_bytes = await file.read(audience_service.MAX_FILE_SIZE_BYTES + 1)
    if len(file_bytes) > audience_service.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed upload size of {audience_service.MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    return audience_service.import_audience_file(
        db=db,
        file_bytes=file_bytes,
        filename=file.filename,
    )


@router.get(
    "/{member_id}",
    response_model=AudienceMemberResponse,
    summary="Retrieve an audience member by ID",
)
def get_audience_member(
    member_id: int = Path(..., ge=1, description="Primary key ID of audience member"),
    current_user: User = Depends(require_role(AUDIENCE_READ_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Get full profile details for a specific audience member.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    return audience_service.get_audience_member_by_id(db=db, member_id=member_id)


@router.put(
    "/{member_id}",
    response_model=AudienceMemberResponse,
    summary="Update an existing audience member",
)
def update_audience_member(
    payload: AudienceMemberUpdate,
    member_id: int = Path(..., ge=1, description="Primary key ID of audience member"),
    current_user: User = Depends(require_role(AUDIENCE_WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Update audience member fields.
    Validates updated constraints and prevents collisions with other members.
    Authorized for Admin and Campaign Manager roles only.
    """
    return audience_service.update_audience_member(
        db=db, member_id=member_id, data=payload
    )


@router.delete(
    "/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an audience member",
)
def delete_audience_member(
    member_id: int = Path(..., ge=1, description="Primary key ID of audience member"),
    current_user: User = Depends(require_role(AUDIENCE_WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Delete an audience member by ID.
    Authorized for Admin and Campaign Manager roles only.
    """
    audience_service.delete_audience_member(db=db, member_id=member_id)
    return None
