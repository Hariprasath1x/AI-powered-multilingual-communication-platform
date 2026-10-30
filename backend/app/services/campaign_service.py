"""Service layer for Campaign Creation, Configuration, Audience Reach, and Lifecycle Management."""

import logging
import math
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy import select, func, desc, or_, and_, distinct
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.campaign import Campaign
from app.models.template import Template
from app.models.segment import Segment
from app.models.audience import AudienceMember
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    PaginatedCampaignResponse,
    CampaignSegmentSummary,
    CampaignPreviewResponse,
    ChannelPreviewDetail,
    SUPPORTED_CAMPAIGN_STATUSES,
)
from app.schemas.segment import RuleGroup
from app.services.segment_service import compile_rule_group

logger = logging.getLogger("masscommai.campaign_service")

# Permitted state machine transitions
VALID_STATUS_TRANSITIONS: Dict[str, List[str]] = {
    "Draft": ["In Review", "Approved", "Archived"],
    "In Review": ["Approved", "Draft"],
    "Approved": ["Scheduled", "Draft"],
    "Scheduled": ["Draft"],
    "Archived": [],  # Terminal state
}

# Mapping allowed placeholders to AudienceMember model attribute names
PLACEHOLDER_FIELD_MAP: Dict[str, str] = {
    "{name}": "name",
    "{email}": "email",
    "{phone}": "phone",
    "{city}": "city",
    "{state}": "state",
    "{preferred_language}": "preferred_language",
    "{occupation}": "occupation",
    "{organization_department}": "organization_department",
}


def get_campaign_by_id(db: Session, campaign_id: int) -> Campaign:
    """Retrieve Campaign entity by primary key with relations eager-loaded, or raise HTTP 404."""
    stmt = (
        select(Campaign)
        .options(
            joinedload(Campaign.creator),
            joinedload(Campaign.template),
            joinedload(Campaign.segments),
        )
        .where(Campaign.id == campaign_id)
    )
    campaign = db.execute(stmt).unique().scalar_one_or_none()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign with ID {campaign_id} not found.",
        )
    return campaign


def calculate_campaign_reach(db: Session, campaign: Campaign) -> Tuple[int, int]:
    """
    Calculates deduplicated total audience reach and confirmed-consent audience reach
    across all segments attached to the campaign using OR semantics.
    
    Guarantees:
    - Counts each audience member only once (DISTINCT) across overlapping segments.
    - Confirmed consent counts strictly require consent_status IS TRUE.
    - Preserves tri-state consent semantics: null (unconfirmed) and false (revoked) are excluded from confirmed reach.
    """
    if not campaign.segments:
        return 0, 0

    segment_exprs = []
    for seg in campaign.segments:
        rules_dict = seg.filter_rules if isinstance(seg.filter_rules, dict) else {}
        if rules_dict:
            try:
                rule_grp = RuleGroup.model_validate(rules_dict)
                compiled = compile_rule_group(rule_grp)
                segment_exprs.append(compiled)
            except Exception as exc:
                logger.warning("Could not compile rules for segment ID %s: %s", seg.id, exc)

    if not segment_exprs:
        return 0, 0

    # Combine with OR: a member qualifying for ANY attached segment is in the campaign's reach
    combined_or = or_(*segment_exprs)

    # Total distinct audience in combined segments
    total_stmt = select(func.count(distinct(AudienceMember.id))).where(combined_or)
    total_count = db.scalar(total_stmt) or 0

    # Confirmed opt-in audience (consent_status == True only)
    consent_stmt = select(func.count(distinct(AudienceMember.id))).where(
        and_(combined_or, AudienceMember.consent_status.is_(True))
    )
    confirmed_count = db.scalar(consent_stmt) or 0

    return total_count, confirmed_count


def build_campaign_response(db: Session, campaign: Campaign) -> CampaignResponse:
    """Constructs CampaignResponse with segments, creator metadata, and live reach metrics."""
    creator_name = campaign.creator.full_name if campaign.creator else f"User #{campaign.created_by}"
    creator_email = campaign.creator.email if campaign.creator else None

    template_title = campaign.template.title if campaign.template else None
    template_body = campaign.template.body if campaign.template else None

    segment_summaries = [
        CampaignSegmentSummary(id=s.id, name=s.name, description=s.description)
        for s in campaign.segments
    ]

    total_reach, confirmed_reach = calculate_campaign_reach(db, campaign)

    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        campaign_type=campaign.campaign_type,
        objective=campaign.objective,
        priority=campaign.priority,
        status=campaign.status,
        channels=list(campaign.channels or []),
        template_id=campaign.template_id,
        template_title=template_title,
        template_body=template_body,
        segments=segment_summaries,
        total_target_audience=total_reach,
        confirmed_consent_audience=confirmed_reach,
        start_date=campaign.start_date,
        end_date=campaign.end_date,
        created_by=campaign.created_by,
        creator_name=creator_name,
        creator_email=creator_email,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


def get_campaign_response(db: Session, campaign_id: int) -> CampaignResponse:
    """Retrieves single campaign response."""
    campaign = get_campaign_by_id(db, campaign_id)
    return build_campaign_response(db, campaign)


def create_campaign(
    db: Session,
    data: CampaignCreate,
    current_user: User,
) -> CampaignResponse:
    """
    Creates a new campaign in Draft status and associates target segments.
    """
    clean_name = data.name.strip()
    existing_stmt = select(Campaign).where(func.lower(Campaign.name) == clean_name.lower())
    if db.execute(existing_stmt).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A campaign named '{clean_name}' already exists.",
        )

    # Validate template existence if supplied
    if data.template_id:
        template = db.execute(select(Template).where(Template.id == data.template_id)).scalar_one_or_none()
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Referenced template ID {data.template_id} does not exist.",
            )

    # Validate and resolve segments
    resolved_segments: List[Segment] = []
    if data.segment_ids:
        seg_stmt = select(Segment).where(Segment.id.in_(data.segment_ids))
        resolved_segments = db.execute(seg_stmt).scalars().all()
        found_ids = {s.id for s in resolved_segments}
        missing_ids = set(data.segment_ids) - found_ids
        if missing_ids:
            missing_str = ", ".join(map(str, sorted(missing_ids)))
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"The following target segment IDs do not exist: {missing_str}",
            )

    campaign = Campaign(
        name=clean_name,
        campaign_type=data.campaign_type,
        objective=data.objective.strip() if data.objective else None,
        priority=data.priority,
        status="Draft",
        channels=data.channels,
        template_id=data.template_id,
        start_date=data.start_date,
        end_date=data.end_date,
        created_by=current_user.id,
    )
    campaign.segments = resolved_segments
    db.add(campaign)

    try:
        db.commit()
        db.refresh(campaign)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A campaign named '{clean_name}' already exists.",
        )

    logger.info("Created campaign ID %s ('%s') by user ID %s", campaign.id, campaign.name, current_user.id)
    return get_campaign_response(db, campaign.id)


def list_campaigns(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    campaign_type: Optional[str] = None,
    priority: Optional[str] = None,
) -> PaginatedCampaignResponse:
    """
    Returns paginated campaigns matching optional search, status, type, and priority filters.
    """
    query = select(Campaign).options(
        joinedload(Campaign.creator),
        joinedload(Campaign.template),
        joinedload(Campaign.segments),
    )

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Campaign.name.ilike(term),
                Campaign.objective.ilike(term),
            )
        )

    if status_filter and status_filter.strip():
        query = query.where(func.lower(Campaign.status) == status_filter.strip().lower())

    if campaign_type and campaign_type.strip():
        query = query.where(func.lower(Campaign.campaign_type) == campaign_type.strip().lower())

    if priority and priority.strip():
        query = query.where(func.lower(Campaign.priority) == priority.strip().lower())

    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = db.scalar(count_query) or 0

    offset = (page - 1) * page_size
    query = query.order_by(desc(Campaign.created_at)).offset(offset).limit(page_size)
    campaigns = db.execute(query).unique().scalars().all()

    items = [build_campaign_response(db, c) for c in campaigns]
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedCampaignResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def update_campaign(
    db: Session,
    campaign_id: int,
    data: CampaignUpdate,
    current_user: User,
) -> CampaignResponse:
    """
    Updates campaign configuration, metadata, and segment associations.
    Enforces creator ownership: Admins can update any campaign;
    Campaign Managers can only update their own campaigns.
    Only campaigns in 'Draft' or 'In Review' can have core attributes edited.
    """
    campaign = get_campaign_by_id(db, campaign_id)

    # Ownership check
    is_admin = current_user.role and current_user.role.name == "Admin"
    if not is_admin and campaign.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify campaigns created by other users. Campaign Managers can only update or delete their own campaigns.",
        )

    # State restriction: core metadata cannot be modified once Approved or Scheduled
    if campaign.status in ("Approved", "Scheduled", "Archived"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit campaign in '{campaign.status}' status. Move it back to Draft first.",
        )

    if data.name is not None:
        clean_name = data.name.strip()
        collision_stmt = select(Campaign).where(
            func.lower(Campaign.name) == clean_name.lower(),
            Campaign.id != campaign_id,
        )
        if db.execute(collision_stmt).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another campaign named '{clean_name}' already exists.",
            )
        campaign.name = clean_name

    if data.campaign_type is not None:
        campaign.campaign_type = data.campaign_type

    if data.objective is not None:
        campaign.objective = data.objective.strip() if data.objective else None

    if data.priority is not None:
        campaign.priority = data.priority

    if data.channels is not None:
        campaign.channels = data.channels

    if data.template_id is not None:
        if data.template_id != 0:
            template = db.execute(select(Template).where(Template.id == data.template_id)).scalar_one_or_none()
            if not template:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Referenced template ID {data.template_id} does not exist.",
                )
            campaign.template_id = data.template_id
        else:
            campaign.template_id = None

    if data.segment_ids is not None:
        if data.segment_ids:
            seg_stmt = select(Segment).where(Segment.id.in_(data.segment_ids))
            resolved = db.execute(seg_stmt).scalars().all()
            found_ids = {s.id for s in resolved}
            missing_ids = set(data.segment_ids) - found_ids
            if missing_ids:
                missing_str = ", ".join(map(str, sorted(missing_ids)))
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"The following target segment IDs do not exist: {missing_str}",
                )
            campaign.segments = resolved
        else:
            campaign.segments = []

    # Effective dates validation against current + incoming values
    effective_start = data.start_date if data.start_date is not None else campaign.start_date
    effective_end = data.end_date if data.end_date is not None else campaign.end_date
    if effective_start and effective_end and effective_end < effective_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Campaign end date must be greater than or equal to start date.",
        )

    if data.start_date is not None:
        campaign.start_date = data.start_date
    if data.end_date is not None:
        campaign.end_date = data.end_date

    try:
        db.commit()
        db.refresh(campaign)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A campaign with this name already exists.",
        )

    logger.info("Updated campaign ID %s by user ID %s", campaign.id, current_user.id)
    return get_campaign_response(db, campaign.id)


def transition_campaign_status(
    db: Session,
    campaign_id: int,
    new_status: str,
    current_user: User,
) -> CampaignResponse:
    """
    Executes a lifecycle status transition.
    Enforces state machine rules and creator ownership.
    """
    campaign = get_campaign_by_id(db, campaign_id)

    # Ownership check
    is_admin = current_user.role and current_user.role.name == "Admin"
    if not is_admin and campaign.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to transition status of campaigns created by other users.",
        )

    current_status = campaign.status
    if current_status == new_status:
        return get_campaign_response(db, campaign.id)

    allowed_targets = VALID_STATUS_TRANSITIONS.get(current_status, [])
    if new_status not in allowed_targets:
        allowed_str = ", ".join(allowed_targets) if allowed_targets else "None (terminal state)"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid status transition from '{current_status}' to '{new_status}'. "
                f"Permitted next states from '{current_status}': {allowed_str}."
            ),
        )

    # Business rule: to move to In Review, Approved, or Scheduled, campaign must have at least 1 segment and a template
    if new_status in ("In Review", "Approved", "Scheduled"):
        if not campaign.segments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot transition campaign to '{new_status}': at least one target audience segment must be attached.",
            )
        if not campaign.template_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot transition campaign to '{new_status}': a content template must be linked.",
            )

    # Business rule: to move to Scheduled, start_date must be set
    if new_status == "Scheduled" and not campaign.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot schedule campaign without a planned start_date.",
        )

    campaign.status = new_status
    db.commit()
    db.refresh(campaign)

    logger.info(
        "Transitioned campaign ID %s status: '%s' -> '%s' by user ID %s",
        campaign.id,
        current_status,
        new_status,
        current_user.id,
    )
    return get_campaign_response(db, campaign.id)


def delete_campaign(
    db: Session,
    campaign_id: int,
    current_user: User,
) -> None:
    """
    Deletes an eligible campaign.
    Enforces ownership and state restriction: only Draft or Archived campaigns may be deleted.
    """
    campaign = get_campaign_by_id(db, campaign_id)

    # Ownership check
    is_admin = current_user.role and current_user.role.name == "Admin"
    if not is_admin and campaign.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete campaigns created by other users. Campaign Managers can only update or delete their own campaigns.",
        )

    if campaign.status not in ("Draft", "Archived"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot delete campaign in '{campaign.status}' status. "
                "Only Draft or Archived campaigns may be deleted."
            ),
        )

    db.delete(campaign)
    db.commit()
    logger.info("Deleted campaign ID %s by user ID %s", campaign_id, current_user.id)


def render_campaign_preview(
    db: Session,
    campaign_id: int,
    audience_member_id: Optional[int] = None,
    custom_placeholders: Optional[Dict[str, str]] = None,
) -> CampaignPreviewResponse:
    """
    Renders safe, simulated multi-channel previews for a campaign without executing dispatch.
    Substitutes approved placeholders using real recipient data from the attached segments.
    """
    campaign = get_campaign_by_id(db, campaign_id)
    if not campaign.template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign has no content template associated for preview.",
        )

    template = campaign.template

    # Resolve recipient
    recipient: Optional[AudienceMember] = None
    if audience_member_id:
        recipient = db.execute(
            select(AudienceMember).where(AudienceMember.id == audience_member_id)
        ).scalar_one_or_none()
        if not recipient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audience member with ID {audience_member_id} not found.",
            )
    else:
        # Pick first matching member from campaign segments
        if campaign.segments:
            segment_exprs = []
            for seg in campaign.segments:
                rules_dict = seg.filter_rules if isinstance(seg.filter_rules, dict) else {}
                if rules_dict:
                    try:
                        rule_grp = RuleGroup.model_validate(rules_dict)
                        segment_exprs.append(compile_rule_group(rule_grp))
                    except Exception:
                        pass
            if segment_exprs:
                recipient = db.execute(
                    select(AudienceMember).where(or_(*segment_exprs)).limit(1)
                ).scalar_one_or_none()

    # Construct recipient dict representation (fallback to representative demo data)
    recipient_dict: Dict[str, Any] = {}
    if recipient:
        recipient_dict = {
            "name": recipient.name,
            "email": recipient.email or "sample.recipient@example.gov.in",
            "phone": recipient.phone or "+919876543210",
            "city": recipient.city or "New Delhi",
            "state": recipient.state or "Delhi",
            "preferred_language": recipient.preferred_language or "en",
            "occupation": recipient.occupation or "Resident",
            "organization_department": recipient.organization_department or "Public Health",
        }
    else:
        recipient_dict = {
            "name": "Aarav Sharma",
            "email": "aarav.sharma@example.gov.in",
            "phone": "+919876543210",
            "city": "New Delhi",
            "state": "Delhi",
            "preferred_language": "en",
            "occupation": "Civilian",
            "organization_department": "Public Health Department",
        }

    # Safe placeholder substitution (literal string replacement, no eval/code execution)
    rendered_body = template.body
    placeholders_found = []

    for ph, field_key in PLACEHOLDER_FIELD_MAP.items():
        if ph in rendered_body:
            placeholders_found.append(ph)
            replacement_val = ""
            if custom_placeholders and ph in custom_placeholders:
                replacement_val = custom_placeholders[ph]
            else:
                replacement_val = str(recipient_dict.get(field_key, f"[{field_key}]"))
            rendered_body = rendered_body.replace(ph, replacement_val)

    # Generate Channel-specific formatting & metrics
    channel_previews: Dict[str, ChannelPreviewDetail] = {}
    word_count = len(rendered_body.split())

    for ch in campaign.channels:
        ch_lower = ch.lower()
        if ch_lower == "email":
            channel_previews[ch] = ChannelPreviewDetail(
                channel=ch,
                title_or_subject=f"[{campaign.priority.upper()}] {campaign.name} — {template.title}",
                rendered_body=rendered_body,
                metrics={
                    "format": "HTML / Multipart",
                    "word_count": word_count,
                    "estimated_read_time_seconds": max(10, round((word_count / 200) * 60)),
                },
            )
        elif ch_lower == "sms":
            char_count = len(rendered_body)
            # GSM-7 segments calculation
            segments_count = 1 if char_count <= 160 else math.ceil(char_count / 153)
            channel_previews[ch] = ChannelPreviewDetail(
                channel=ch,
                title_or_subject=None,
                rendered_body=rendered_body,
                metrics={
                    "character_count": char_count,
                    "segment_count": segments_count,
                    "encoding": "GSM-7 / Unicode",
                },
            )
        elif ch_lower == "whatsapp":
            channel_previews[ch] = ChannelPreviewDetail(
                channel=ch,
                title_or_subject=None,
                rendered_body=rendered_body,
                metrics={
                    "format": "Interactive WhatsApp Template",
                    "has_header": True,
                    "header_text": campaign.name,
                },
            )
        elif ch_lower == "voice":
            channel_previews[ch] = ChannelPreviewDetail(
                channel=ch,
                title_or_subject="Automated Voice Broadcast Script",
                rendered_body=rendered_body,
                metrics={
                    "word_count": word_count,
                    "estimated_duration_seconds": max(5, round((word_count / 130) * 60)),
                    "pacing": "130 words per minute",
                },
            )

    return CampaignPreviewResponse(
        campaign_id=campaign.id,
        campaign_name=campaign.name,
        template_id=template.id,
        template_title=template.title,
        sample_recipient=recipient_dict,
        rendered_content=rendered_body,
        placeholders_used=sorted(list(set(placeholders_found))),
        channel_previews=channel_previews,
    )

