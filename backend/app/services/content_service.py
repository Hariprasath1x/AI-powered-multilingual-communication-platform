"""Service layer for AI content generation, translation, review workflows, and persistence."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any, Set
from fastapi import HTTPException, status
from sqlalchemy import select, func, desc, or_
from sqlalchemy.orm import Session, joinedload, load_only
from sqlalchemy.orm.attributes import flag_modified

from app.models.user import User
from app.models.campaign import Campaign
from app.models.segment import Segment, campaign_segments
from app.models.template import Template
from app.models.content_asset import ContentAsset
from app.schemas.content_asset import (
    ContentGenerateRequest,
    ContentTranslateRequest,
    ContentAssetCreate,
    ContentAssetUpdate,
    ContentReviewStatusUpdate,
    ContentAttachRequest,
    ContentAssetResponse,
    PaginatedContentAssetResponse,
)
from app.services.ai.base import (
    ContentBrief,
    TranslationRequest,
    AIProviderError,
    AIProviderTimeoutError,
    AIProviderQuotaError,
    PlaceholderPreservationError,
)
from app.services.ai.factory import get_ai_provider
from app.services.channel_constraints import calculate_channel_metrics

logger = logging.getLogger("masscommai.content_service")
PLACEHOLDER_REGEX = re.compile(r"\{[a-zA-Z0-9_]+\}")

VALID_REVIEW_TRANSITIONS: Dict[str, List[str]] = {
    "Draft": ["In Review", "Approved", "Needs Review", "Generated"],
    "Pending": ["Generated"],
    "Generated": ["Needs Review", "Approved", "In Review"],
    "Needs Review": ["Approved", "Rejected"],
    "In Review": ["Approved", "Rejected", "Draft", "Needs Review"],
    "Approved": ["Draft", "Needs Review"],  # Reopening for edit resets approval
    "Rejected": ["Draft", "Needs Review"],
}


def _check_authoring_permission(current_user: User) -> None:
    """Ensure user has Admin or Campaign Manager role for authoring operations."""
    role_name = current_user.role.name if current_user.role else ""
    if role_name not in ("Admin", "Campaign Manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins and Campaign Managers have permission to generate, translate, or author content.",
        )


def _check_review_permission(current_user: User) -> None:
    """Ensure user has Admin or Campaign Manager role for reviewing and approving content."""
    role_name = current_user.role.name if current_user.role else ""
    if role_name not in ("Admin", "Campaign Manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins and Campaign Managers can perform human review or approve content.",
        )


def _check_asset_ownership(asset: ContentAsset, current_user: User) -> None:
    """Ensure current user is Admin or the creator of the asset."""
    role_name = current_user.role.name if current_user.role else ""
    if role_name != "Admin" and asset.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify or delete content assets created by another user.",
        )


def get_content_asset_by_id(db: Session, asset_id: int) -> ContentAsset:
    """Retrieve ContentAsset ORM entity by ID or raise 404."""
    stmt = (
        select(ContentAsset)
        .options(
            joinedload(ContentAsset.creator),
            joinedload(ContentAsset.reviewer),
            joinedload(ContentAsset.campaign),
            joinedload(ContentAsset.template),
        )
        .where(ContentAsset.id == asset_id)
    )
    asset = db.execute(stmt).scalar_one_or_none()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content asset with ID {asset_id} not found.",
        )
    return asset


@dataclass
class ResolvedCampaignContext:
    campaign_id: int
    campaign_name: str
    campaign_type: str
    campaign_priority: str
    campaign_objective: Optional[str]
    configured_campaign_channels: List[str]
    included_segment_names: List[str]
    segment_summaries: List[str]
    omitted_segment_count: int
    requested_tone: str
    effective_tone: str
    requested_channel: str
    channel_mismatch: bool
    warning: Optional[str] = None


def _resolve_campaign_context(
    db: Session,
    campaign_id: int,
    current_user: User,
    request: Optional[ContentGenerateRequest] = None,
) -> ResolvedCampaignContext:
    """
    Retrieve and validate campaign context for AI prompt ingestion.
    Enforces authorization: Admin can access any campaign; Campaign Managers can
    only access campaigns they created.
    Segment details are deferred and queried strictly AFTER authorization succeeds.
    Segment query selects only id, name, and description; explicitly excludes
    filter_rules, other mapped columns, and audience members (PII isolation).
    Applies tone escalation for Emergency Alerts and detects channel mismatches.
    """
    # 1. Fetch only campaign columns needed for authorization and context.
    # Do NOT eager-load segments or creator prior to authorization.
    stmt = (
        select(Campaign)
        .options(
            load_only(
                Campaign.id,
                Campaign.name,
                Campaign.campaign_type,
                Campaign.priority,
                Campaign.objective,
                Campaign.channels,
                Campaign.created_by,
            )
        )
        .where(Campaign.id == campaign_id)
    )
    campaign = db.execute(stmt).scalar_one_or_none()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Associated campaign with ID {campaign_id} not found.",
        )

    # 2. Authorization enforcement: Admin or creator ownership.
    # Blocks unauthorized access before any segment details are loaded.
    is_admin = bool(current_user.role and current_user.role.name == "Admin")
    if not is_admin and campaign.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access or generate content for campaigns created by other users.",
        )

    # 3. Post-authorization segment loading:
    # Explicitly select only Segment.id, Segment.name, and Segment.description.
    # Excludes Segment.filter_rules, created_by, timestamps, and audience_members.
    seg_stmt = (
        select(Segment.id, Segment.name, Segment.description)
        .join(campaign_segments, campaign_segments.c.segment_id == Segment.id)
        .where(campaign_segments.c.campaign_id == campaign_id)
        .order_by(Segment.id, func.lower(Segment.name))
    )
    raw_segments = db.execute(seg_stmt).all()

    # Deterministic segment processing (max 5 segments, sorted by ID then name)
    max_segments = 5
    included_segments = raw_segments[:max_segments]
    omitted_count = max(0, len(raw_segments) - max_segments)

    included_segment_names = [r.name for r in included_segments]
    segment_summaries = [
        f"{r.name}: {r.description.strip()}" if r.description and r.description.strip() else r.name
        for r in included_segments
    ]

    # Precedence: Tone and Urgency
    req_tone = request.tone if request else "informative"
    if campaign.campaign_type == "Emergency Alert":
        effective_tone = "urgent"
    else:
        effective_tone = req_tone

    # Channel mismatch check
    req_channel = request.channel if request else "Email"
    raw_channels = campaign.channels if isinstance(campaign.channels, list) else []
    configured_channels = [str(c).strip() for c in raw_channels]

    channel_mismatch = False
    warning = None
    if configured_channels:
        matched = any(c.lower() == req_channel.strip().lower() for c in configured_channels)
        if not matched:
            channel_mismatch = True
            warning = (
                f"Requested channel '{req_channel}' is not configured in campaign channels "
                f"({', '.join(configured_channels)}). Generated asset is saved as Draft but is not authorized for distribution."
            )

    # Strategic campaign objective (limit to 500 chars)
    campaign_obj = campaign.objective.strip()[:500] if campaign.objective and campaign.objective.strip() else None

    return ResolvedCampaignContext(
        campaign_id=campaign.id,
        campaign_name=campaign.name,
        campaign_type=campaign.campaign_type,
        campaign_priority=campaign.priority,
        campaign_objective=campaign_obj,
        configured_campaign_channels=configured_channels,
        included_segment_names=included_segment_names,
        segment_summaries=segment_summaries,
        omitted_segment_count=omitted_count,
        requested_tone=req_tone,
        effective_tone=effective_tone,
        requested_channel=req_channel,
        channel_mismatch=channel_mismatch,
        warning=warning,
    )


async def generate_content(
    db: Session,
    request: ContentGenerateRequest,
    current_user: User,
    provider_type: Optional[str] = None,
) -> ContentAsset:
    """
    Generate public awareness content from a structured brief via AI provider.
    Saves generated copy in Draft status for human review.
    """
    _check_authoring_permission(current_user)

    # Optional campaign link check & context resolution
    campaign_ctx: Optional[ResolvedCampaignContext] = None
    if request.campaign_id:
        campaign_ctx = _resolve_campaign_context(
            db=db,
            campaign_id=request.campaign_id,
            current_user=current_user,
            request=request,
        )

    # Optional template link check
    if request.template_id:
        template = db.get(Template, request.template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Associated template with ID {request.template_id} not found.",
            )

    effective_tone = campaign_ctx.effective_tone if campaign_ctx else request.tone

    # Synthesize audience context
    if campaign_ctx and campaign_ctx.segment_summaries:
        seg_text = "; ".join(campaign_ctx.segment_summaries)
        if request.audience_description and request.audience_description.strip():
            combined_audience = f"{request.audience_description.strip()} (Target Segments: {seg_text})"
        else:
            combined_audience = f"Target Segments: {seg_text}"
        combined_audience = combined_audience[:500]
    else:
        combined_audience = request.audience_description

    # Build brief
    brief = ContentBrief(
        topic=request.topic,
        objective=request.objective,
        audience_description=combined_audience,
        category=request.category,
        tone=effective_tone,
        channel=request.channel,
        source_language=request.source_language,
        facts=request.facts,
        constraints=request.constraints,
        campaign_id=campaign_ctx.campaign_id if campaign_ctx else None,
        campaign_name=campaign_ctx.campaign_name if campaign_ctx else None,
        campaign_type=campaign_ctx.campaign_type if campaign_ctx else None,
        campaign_priority=campaign_ctx.campaign_priority if campaign_ctx else None,
        campaign_objective=campaign_ctx.campaign_objective if campaign_ctx else None,
        target_segments=campaign_ctx.included_segment_names if campaign_ctx else [],
    )

    provider = get_ai_provider(provider_type)

    try:
        result = await provider.generate_content(brief)
    except AIProviderTimeoutError as exc:
        logger.error("AI provider timeout: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI generation timed out. Please try again or simplify the brief.",
        ) from exc
    except AIProviderQuotaError as exc:
        logger.error("AI provider quota exceeded: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI provider quota or rate limit exceeded. Please retry in a few moments.",
        ) from exc
    except AIProviderError as exc:
        logger.error("AI provider error: %s", exc)
        raise HTTPException(
            status_code=exc.status_code,
            detail=f"Content generation failed: {exc.message}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during AI generation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="An unexpected error occurred while communicating with the AI service.",
        ) from exc

    # Prepare comprehensive provider metadata with campaign audit trail
    provider_meta = dict(result.provider_metadata or {})
    if campaign_ctx:
        provider_meta["campaign_context"] = {
            "campaign_id": campaign_ctx.campaign_id,
            "campaign_name": campaign_ctx.campaign_name,
            "campaign_type": campaign_ctx.campaign_type,
            "campaign_priority": campaign_ctx.campaign_priority,
            "included_segment_names": campaign_ctx.included_segment_names,
            "omitted_segment_count": campaign_ctx.omitted_segment_count,
            "requested_tone": campaign_ctx.requested_tone,
            "effective_tone": campaign_ctx.effective_tone,
            "requested_channel": campaign_ctx.requested_channel,
            "configured_campaign_channels": campaign_ctx.configured_campaign_channels,
            "channel_mismatch": campaign_ctx.channel_mismatch,
            "prompt_version": "v2.0-campaign-aware",
        }
        if campaign_ctx.warning:
            provider_meta["campaign_context"]["warning"] = campaign_ctx.warning
    else:
        provider_meta["standalone_generation"] = True
        provider_meta["prompt_version"] = "v2.0-campaign-aware"

    # Calculate and attach deterministic channel metrics snapshot
    metrics_snapshot = calculate_channel_metrics(
        channel=request.channel,
        title=result.title,
        body=result.body,
        call_to_action=result.call_to_action,
        language=request.source_language,
    )
    provider_meta["channel_metrics"] = metrics_snapshot.to_dict()

    # Persist as ContentAsset in Draft review status
    asset = ContentAsset(
        title=result.title,
        body=result.body,
        summary=result.summary,
        call_to_action=result.call_to_action,
        category=request.category,
        tone=effective_tone,
        channel=request.channel,
        source_language=request.source_language,
        target_language=None,
        operation_type="generation",
        parent_id=None,
        campaign_id=request.campaign_id,
        template_id=request.template_id,
        review_status="Draft",
        provider_metadata=provider_meta,
        created_by=current_user.id,
    )

    try:
        db.add(asset)
        db.commit()
        db.refresh(asset)
    except Exception as exc:
        db.rollback()
        logger.exception("Database error persisting generated content asset: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save generated content asset to database.",
        ) from exc

    return asset


async def translate_content(
    db: Session,
    asset_id: int,
    request: ContentTranslateRequest,
    current_user: User,
    provider_type: Optional[str] = None,
) -> ContentAsset:
    """
    Translate an existing content asset into a target Indian language.
    Strictly verifies placeholder preservation, utilizes cache, and creates a traceable variant linked to root asset.
    """
    _check_authoring_permission(current_user)

    from app.services.translation_service import translate_single_language
    source_asset = get_content_asset_by_id(db, asset_id)

    return await translate_single_language(
        db=db,
        source_asset=source_asset,
        target_language=request.target_language,
        current_user=current_user,
        notes=request.notes,
        provider_type=provider_type,
    )


def create_manual_content_asset(
    db: Session,
    payload: ContentAssetCreate,
    current_user: User,
) -> ContentAsset:
    """Manually author a draft content asset in the studio."""
    _check_authoring_permission(current_user)

    provider_meta = {"provider": "manual", "author": current_user.full_name}
    metrics_snapshot = calculate_channel_metrics(
        channel=payload.channel,
        title=payload.title,
        body=payload.body,
        call_to_action=payload.call_to_action,
        language=payload.source_language,
    )
    provider_meta["channel_metrics"] = metrics_snapshot.to_dict()

    asset = ContentAsset(
        title=payload.title,
        body=payload.body,
        summary=payload.summary,
        call_to_action=payload.call_to_action,
        category=payload.category,
        tone=payload.tone,
        channel=payload.channel,
        source_language=payload.source_language,
        target_language=None,
        operation_type="human_edit",
        parent_id=None,
        campaign_id=payload.campaign_id,
        template_id=payload.template_id,
        review_status="Draft",
        provider_metadata=provider_meta,
        created_by=current_user.id,
    )

    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def update_content_asset(
    db: Session,
    asset_id: int,
    payload: ContentAssetUpdate,
    current_user: User,
) -> ContentAsset:
    """Update editable draft content. Marks operation_type as human_edit, invalidates cache if source, and resets approval if modified."""
    asset = get_content_asset_by_id(db, asset_id)
    _check_asset_ownership(asset, current_user)

    old_title = asset.title
    old_body = asset.body
    old_cta = asset.call_to_action

    changed = False
    if payload.title is not None and payload.title != asset.title:
        asset.title = payload.title
        changed = True
    if payload.body is not None and payload.body != asset.body:
        asset.body = payload.body
        changed = True
    if payload.summary is not None:
        asset.summary = payload.summary
        changed = True
    if payload.call_to_action is not None:
        asset.call_to_action = payload.call_to_action
        changed = True
    if payload.category is not None:
        asset.category = payload.category
        changed = True
    if payload.tone is not None:
        asset.tone = payload.tone
        changed = True
    if payload.channel is not None:
        asset.channel = payload.channel
        changed = True

    if changed:
        # Invalidate translation cache for source content modifications
        if asset.parent_id is None:
            from app.services.translation_cache_service import (
                compute_source_content_hash,
                invalidate_source_cache,
            )
            old_hash = compute_source_content_hash(
                title=old_title,
                body=old_body,
                call_to_action=old_cta,
            )
            try:
                invalidate_source_cache(db, old_hash)
            except Exception as exc:
                logger.warning("Failed to invalidate translation cache on content update: %s", exc)

            # AUDIT-T8-04: Reset approved child translation variants and flag source_outdated
            child_variants = db.execute(
                select(ContentAsset).where(ContentAsset.parent_id == asset.id)
            ).scalars().all()

            for child in child_variants:
                child_meta = dict(child.provider_metadata or {})
                child_meta["source_outdated"] = True
                child.provider_metadata = child_meta
                flag_modified(child, "provider_metadata")

                if child.review_status == "Approved":
                    prev_child_status = child.review_status
                    child.review_status = "Needs Review"
                    try:
                        from app.services.translation_service import record_review_transition
                        record_review_transition(
                            db=db,
                            content_asset_id=child.id,
                            from_status=prev_child_status,
                            to_status="Needs Review",
                            reviewer_id=current_user.id,
                            review_notes="Approval reset: root source content modified by editor",
                        )
                    except Exception as exc:
                        logger.warning("Failed to record review transition for outdated child asset %d: %s", child.id, exc)

        asset.operation_type = "human_edit"
        current_meta = dict(asset.provider_metadata or {})
        if asset.parent_id is not None or asset.target_language:
            current_meta["is_human_edited"] = True

        # If asset was already Approved, human edit resets it back to In Review / Needs Review
        if asset.review_status == "Approved":
            prev_status = asset.review_status
            asset.review_status = "Needs Review" if asset.parent_id else "In Review"
            if asset.parent_id or asset.target_language:
                try:
                    from app.services.translation_service import record_review_transition
                    record_review_transition(
                        db=db,
                        content_asset_id=asset.id,
                        from_status=prev_status,
                        to_status=asset.review_status,
                        reviewer_id=current_user.id,
                        review_notes="Approval reset due to human edit",
                    )
                except Exception as exc:
                    logger.warning("Failed to record review transition on human edit: %s", exc)

        # Recalculate channel metrics snapshot while preserving existing provider metadata
        metrics_snapshot = calculate_channel_metrics(
            channel=asset.channel,
            title=asset.title,
            body=asset.body,
            call_to_action=asset.call_to_action,
            language=asset.target_language or asset.source_language,
        )
        current_meta["channel_metrics"] = metrics_snapshot.to_dict()
        asset.provider_metadata = current_meta
        flag_modified(asset, "provider_metadata")

    db.commit()
    db.refresh(asset)
    return asset


def update_review_status(
    db: Session,
    asset_id: int,
    payload: ContentReviewStatusUpdate,
    current_user: User,
) -> ContentAsset:
    """
    Update review status with human reviewer traceability.
    Enforces review state machine transitions and audit metadata.
    """
    _check_review_permission(current_user)
    asset = get_content_asset_by_id(db, asset_id)

    target_status = payload.review_status
    current_status = asset.review_status

    if target_status != current_status:
        allowed_next = VALID_REVIEW_TRANSITIONS.get(current_status, [])
        if target_status not in allowed_next:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot transition content review status from '{current_status}' to '{target_status}'. Allowed: {allowed_next}",
            )

    # Phase 1A Security Invariant: Content must undergo successful quality assessment before approval
    if target_status == "Approved":
        from app.services.quality_service import validate_content_approval_readiness
        is_ready, err_code, blocking_reasons = validate_content_approval_readiness(db, asset_id)
        if not is_ready:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve content asset: {'; '.join(blocking_reasons)}",
            )

    # AUDIT-T8-02: Enforce mandatory review notes when rejecting content to document editorial issues
    if target_status == "Rejected":
        if not payload.review_notes or not payload.review_notes.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Review notes are mandatory when rejecting content to document editorial issues.",
            )

    asset.review_status = target_status
    asset.review_notes = payload.review_notes
    asset.reviewed_by = current_user.id
    asset.reviewed_at = datetime.now(timezone.utc)

    # Persist translation review history for translation variants
    if asset.parent_id or asset.target_language:
        try:
            from app.services.translation_service import record_review_transition
            record_review_transition(
                db=db,
                content_asset_id=asset.id,
                from_status=current_status,
                to_status=target_status,
                reviewer_id=current_user.id,
                review_notes=payload.review_notes,
            )
        except Exception as exc:
            logger.warning("Failed to record review transition in history: %s", exc)

    db.commit()
    db.refresh(asset)
    return asset


def list_content_assets(
    db: Session,
    current_user: User,
    page: int = 1,
    size: int = 10,
    search: Optional[str] = None,
    category: Optional[str] = None,
    channel: Optional[str] = None,
    language: Optional[str] = None,
    review_status: Optional[str] = None,
    operation_type: Optional[str] = None,
) -> Tuple[List[ContentAsset], int]:
    """List content assets with filtering, search, and role-based visibility."""
    page = max(1, page)
    size = max(1, min(100, size))

    query = select(ContentAsset)

    # Filters
    filters = []

    # Role visibility: Admin sees all; Campaign Manager & Comm Team see all published/drafts in system
    # (Content assets are shared library assets for awareness messaging)

    if search:
        search_term = f"%{search.strip()}%"
        filters.append(
            or_(
                ContentAsset.title.ilike(search_term),
                ContentAsset.body.ilike(search_term),
                ContentAsset.summary.ilike(search_term),
            )
        )

    if category:
        filters.append(ContentAsset.category == category)

    if channel:
        filters.append(ContentAsset.channel == channel)

    if language:
        filters.append(
            or_(
                ContentAsset.source_language == language,
                ContentAsset.target_language == language,
            )
        )

    if review_status:
        filters.append(ContentAsset.review_status == review_status)

    if operation_type:
        filters.append(ContentAsset.operation_type == operation_type)

    if filters:
        query = query.where(*filters)

    # Count total
    count_stmt = select(func.count()).select_from(query.subquery())
    total = db.execute(count_stmt).scalar() or 0

    # Paginated results ordered by newest first
    stmt = (
        query.options(
            joinedload(ContentAsset.creator),
            joinedload(ContentAsset.reviewer),
            joinedload(ContentAsset.campaign),
            joinedload(ContentAsset.template),
        )
        .order_by(desc(ContentAsset.created_at))
        .offset((page - 1) * size)
        .limit(size)
    )

    items = db.execute(stmt).scalars().all()
    return list(items), total


def get_variants(
    db: Session,
    asset_id: int,
    current_user: User,
) -> List[ContentAsset]:
    """Retrieve all translated variants and revisions belonging to the same lineage."""
    target_asset = get_content_asset_by_id(db, asset_id)
    root_id = target_asset.parent_id if target_asset.parent_id else target_asset.id

    stmt = (
        select(ContentAsset)
        .options(
            joinedload(ContentAsset.creator),
            joinedload(ContentAsset.reviewer),
        )
        .where(
            or_(
                ContentAsset.id == root_id,
                ContentAsset.parent_id == root_id,
            )
        )
        .order_by(ContentAsset.created_at.asc())
    )

    return list(db.execute(stmt).scalars().all())


def attach_to_campaign_or_template(
    db: Session,
    asset_id: int,
    payload: ContentAttachRequest,
    current_user: User,
) -> Dict[str, Any]:
    """
    Associate content asset with an existing campaign or save as reusable template.
    Preserves campaign approval rules and message dispatch safety boundaries.
    """
    _check_authoring_permission(current_user)
    asset = get_content_asset_by_id(db, asset_id)

    response_data: Dict[str, Any] = {"asset_id": asset.id}

    # Attach to existing Campaign
    if payload.campaign_id:
        campaign = db.get(Campaign, payload.campaign_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign with ID {payload.campaign_id} not found.",
            )
        # Check campaign ownership if not Admin
        is_admin = current_user.role and current_user.role.name == "Admin"
        if not is_admin and campaign.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot attach content to a campaign created by another user.",
            )

        # Associate content asset with campaign
        asset.campaign_id = campaign.id
        asset.campaign_id = campaign.id
        response_data["attached_campaign_id"] = campaign.id
        response_data["campaign_name"] = campaign.name

    # Save as Reusable Template
    if payload.save_as_template:
        template_title = payload.template_name or f"Template from {asset.title}"
        template_cat = payload.template_category or asset.category
        lang = asset.target_language or asset.source_language

        template = Template(
            title=template_title[:150],
            category=template_cat[:50],
            body=asset.body,
            language=lang,
            tags="ai-generated,content-studio",
            created_by=current_user.id,
        )
        db.add(template)
        db.flush()  # obtain template.id

        asset.template_id = template.id
        if payload.campaign_id and "attached_campaign_id" in response_data:
            campaign = db.get(Campaign, payload.campaign_id)
            if campaign:
                campaign.template_id = template.id

        response_data["saved_template_id"] = template.id
        response_data["template_title"] = template.title

    db.commit()
    db.refresh(asset)
    return response_data


def delete_content_asset(
    db: Session,
    asset_id: int,
    current_user: User,
) -> bool:
    """Delete draft content asset. Admin can delete any; creators can delete own."""
    asset = get_content_asset_by_id(db, asset_id)
    _check_asset_ownership(asset, current_user)

    db.delete(asset)
    db.commit()
    return True
