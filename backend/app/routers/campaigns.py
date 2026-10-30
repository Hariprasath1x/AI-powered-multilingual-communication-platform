"""FastAPI router for Campaign Creation, Configuration, Audience Reach, and Lifecycle Management."""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.core.dependencies import require_role
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignStatusUpdate,
    CampaignResponse,
    PaginatedCampaignResponse,
    CampaignPreviewRequest,
    CampaignPreviewResponse,
    SUPPORTED_CAMPAIGN_TYPES,
    SUPPORTED_CAMPAIGN_PRIORITIES,
    SUPPORTED_CAMPAIGN_STATUSES,
    SUPPORTED_CAMPAIGN_CHANNELS,
)
from app.services import campaign_service

logger = logging.getLogger("masscommai.campaigns_router")

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

# RBAC Role Matrix:
# - Read, Meta & Preview access: Admin, Campaign Manager, Communication Team
# - Create access: Admin, Campaign Manager (Communication Team is restricted)
# - Update, Status Transition & Delete access: Admin (all), Campaign Manager (own created campaigns only)
CAMPAIGN_READ_ROLES = ["Admin", "Campaign Manager", "Communication Team"]
CAMPAIGN_WRITE_ROLES = ["Admin", "Campaign Manager"]


@router.get(
    "/meta",
    summary="Get supported campaign metadata (types, priorities, statuses, channels)",
)
def get_campaign_metadata(
    current_user: User = Depends(require_role(CAMPAIGN_READ_ROLES)),
) -> Dict[str, Any]:
    """
    Returns the server-enforced allowlists for campaign configuration:
    supported types, priority levels, lifecycle statuses, and distribution channels.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    return {
        "types": sorted(list(SUPPORTED_CAMPAIGN_TYPES)),
        "priorities": ["Low", "Medium", "High"],
        "statuses": sorted(list(SUPPORTED_CAMPAIGN_STATUSES)),
        "channels": sorted(list(SUPPORTED_CAMPAIGN_CHANNELS)),
    }


@router.get(
    "",
    response_model=PaginatedCampaignResponse,
    summary="List campaigns with pagination, search, status, type, and priority filters",
)
def list_campaigns(
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term matching campaign name or objective"),
    status: Optional[str] = Query(None, description="Filter by status (Draft, In Review, Approved, Scheduled, Archived)"),
    type: Optional[str] = Query(None, description="Filter by campaign type"),
    priority: Optional[str] = Query(None, description="Filter by priority (Low, Medium, High)"),
    current_user: User = Depends(require_role(CAMPAIGN_READ_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Retrieve paginated campaigns with creator metadata, attached segments, and reach metrics.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    return campaign_service.list_campaigns(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        status_filter=status,
        campaign_type=type,
        priority=priority,
    )


@router.post(
    "",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new campaign in Draft status",
)
def create_campaign(
    payload: CampaignCreate,
    current_user: User = Depends(require_role(CAMPAIGN_WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Creates a new campaign in Draft status with target segment and template associations.
    Enforces name uniqueness, valid references, and records creator ID.
    Authorized for Admin and Campaign Manager roles only.
    """
    return campaign_service.create_campaign(
        db=db,
        data=payload,
        current_user=current_user,
    )


@router.get(
    "/{id}/preview",
    response_model=CampaignPreviewResponse,
    summary="Preview campaign content across channels using recipient data or custom mock values",
)
def preview_campaign_get(
    id: int = Path(..., ge=1, description="Campaign primary key ID"),
    audience_member_id: Optional[int] = Query(None, ge=1, description="Optional specific audience member ID for sample preview"),
    current_user: User = Depends(require_role(CAMPAIGN_READ_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Renders simulated multi-channel previews (Email, SMS, WhatsApp, Voice)
    using placeholder data from matching target segment recipients or default sample data.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    return campaign_service.render_campaign_preview(
        db=db,
        campaign_id=id,
        audience_member_id=audience_member_id,
        custom_placeholders=None,
    )


@router.post(
    "/{id}/preview",
    response_model=CampaignPreviewResponse,
    summary="Preview campaign content with optional custom placeholder overrides",
)
def preview_campaign_post(
    payload: CampaignPreviewRequest,
    id: int = Path(..., ge=1, description="Campaign primary key ID"),
    current_user: User = Depends(require_role(CAMPAIGN_READ_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Renders simulated multi-channel previews with custom placeholder overrides or specific recipient selection.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    return campaign_service.render_campaign_preview(
        db=db,
        campaign_id=id,
        audience_member_id=payload.audience_member_id,
        custom_placeholders=payload.custom_placeholders,
    )


@router.get(
    "/{id}",
    response_model=CampaignResponse,
    summary="Retrieve a campaign by ID",
)
def get_campaign(
    id: int = Path(..., ge=1, description="Campaign primary key ID"),
    current_user: User = Depends(require_role(CAMPAIGN_READ_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Get full campaign configuration, linked template, target segments, and live reach statistics.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    return campaign_service.get_campaign_response(db=db, campaign_id=id)


@router.put(
    "/{id}",
    response_model=CampaignResponse,
    summary="Update an existing campaign",
)
def update_campaign(
    payload: CampaignUpdate,
    id: int = Path(..., ge=1, description="Campaign primary key ID"),
    current_user: User = Depends(require_role(CAMPAIGN_WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Update campaign metadata, schedule, channels, template, or segments.
    Enforces ownership permissions: Admins can update any campaign;
    Campaign Managers can only update campaigns they created.
    Editing core content is restricted to Draft or In Review states.
    """
    return campaign_service.update_campaign(
        db=db,
        campaign_id=id,
        data=payload,
        current_user=current_user,
    )


@router.patch(
    "/{id}/status",
    response_model=CampaignResponse,
    summary="Transition campaign lifecycle status",
)
def update_campaign_status(
    payload: CampaignStatusUpdate,
    id: int = Path(..., ge=1, description="Campaign primary key ID"),
    current_user: User = Depends(require_role(CAMPAIGN_WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Transition campaign lifecycle state according to state machine rules:
    Draft -> In Review / Approved / Archived
    In Review -> Approved / Draft
    Approved -> Scheduled / Draft
    Scheduled -> Draft
    Archived is terminal.
    Enforces ownership permissions: Admins can transition any campaign;
    Campaign Managers can only transition campaigns they created.
    """
    return campaign_service.transition_campaign_status(
        db=db,
        campaign_id=id,
        new_status=payload.status,
        current_user=current_user,
    )


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a campaign",
)
def delete_campaign(
    id: int = Path(..., ge=1, description="Campaign primary key ID"),
    current_user: User = Depends(require_role(CAMPAIGN_WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Permanently delete a campaign.
    Restricted to Draft or Archived status only.
    Enforces ownership permissions: Admins can delete any campaign;
    Campaign Managers can only delete campaigns they created.
    """
    campaign_service.delete_campaign(
        db=db,
        campaign_id=id,
        current_user=current_user,
    )
    return None

