"""Service layer for AI content generation, translation, review workflows, and persistence."""

import logging
import re
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any, Set
from fastapi import HTTPException, status
from sqlalchemy import select, func, desc, or_
from sqlalchemy.orm import Session, joinedload

from app.models.user import User
from app.models.campaign import Campaign
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

logger = logging.getLogger("masscommai.content_service")
PLACEHOLDER_REGEX = re.compile(r"\{[a-zA-Z0-9_]+\}")

VALID_REVIEW_TRANSITIONS: Dict[str, List[str]] = {
    "Draft": ["In Review", "Approved"],
    "In Review": ["Approved", "Rejected", "Draft"],
    "Approved": ["Draft"],  # Reopening for edit resets approval
    "Rejected": ["Draft"],
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

    # Optional campaign link check
    if request.campaign_id:
        campaign = db.get(Campaign, request.campaign_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Associated campaign with ID {request.campaign_id} not found.",
            )

    # Optional template link check
    if request.template_id:
        template = db.get(Template, request.template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Associated template with ID {request.template_id} not found.",
            )

    # Build brief
    brief = ContentBrief(
        topic=request.topic,
        objective=request.objective,
        audience_description=request.audience_description,
        category=request.category,
        tone=request.tone,
        channel=request.channel,
        source_language=request.source_language,
        facts=request.facts,
        constraints=request.constraints,
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

    # Persist as ContentAsset in Draft review status
    asset = ContentAsset(
        title=result.title,
        body=result.body,
        summary=result.summary,
        call_to_action=result.call_to_action,
        category=request.category,
        tone=request.tone,
        channel=request.channel,
        source_language=request.source_language,
        target_language=None,
        operation_type="generation",
        parent_id=None,
        campaign_id=request.campaign_id,
        template_id=request.template_id,
        review_status="Draft",
        provider_metadata=result.provider_metadata,
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
    Strictly verifies placeholder preservation and creates a traceable variant linked to root asset.
    """
    _check_authoring_permission(current_user)

    source_asset = get_content_asset_by_id(db, asset_id)

    # Disallow translating to the same active language
    current_lang = source_asset.target_language or source_asset.source_language
    if request.target_language.lower() == current_lang.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target language '{request.target_language}' is identical to the current content language.",
        )

    # Extract placeholders from source text
    source_placeholders: Set[str] = set(PLACEHOLDER_REGEX.findall(source_asset.body))
    if source_asset.title:
        source_placeholders.update(PLACEHOLDER_REGEX.findall(source_asset.title))
    if source_asset.call_to_action:
        source_placeholders.update(PLACEHOLDER_REGEX.findall(source_asset.call_to_action))

    trans_req = TranslationRequest(
        source_text=source_asset.body,
        source_title=source_asset.title,
        source_cta=source_asset.call_to_action,
        source_language=current_lang,
        target_language=request.target_language,
        channel=source_asset.channel,
        context=request.notes,
    )

    provider = get_ai_provider(provider_type)

    try:
        result = await provider.translate_content(trans_req)
    except AIProviderTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Translation timed out. Please try again.",
        ) from exc
    except AIProviderQuotaError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Translation rate limit exceeded. Please retry shortly.",
        ) from exc
    except AIProviderError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=f"Translation failed: {exc.message}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during translation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="An unexpected error occurred during translation.",
        ) from exc

    # Placeholder Preservation Safety Guard
    translated_full = f"{result.title} {result.body} {result.call_to_action or ''}"
    missing_phs = [ph for ph in source_placeholders if ph not in translated_full]
    if missing_phs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Translation safety violation: required placeholders {missing_phs} were dropped or corrupted by the translator.",
        )

    # Determine root parent for clean variant chaining
    root_id = source_asset.parent_id if source_asset.parent_id else source_asset.id

    # Create new ContentAsset for the translated variant (source remains intact)
    variant_asset = ContentAsset(
        title=result.title,
        body=result.body,
        summary=result.summary,
        call_to_action=result.call_to_action,
        category=source_asset.category,
        tone=source_asset.tone,
        channel=source_asset.channel,
        source_language=source_asset.source_language,
        target_language=request.target_language,
        operation_type="translation",
        parent_id=root_id,
        campaign_id=source_asset.campaign_id,
        template_id=source_asset.template_id,
        review_status="Draft",  # Requires human review
        provider_metadata=result.provider_metadata,
        created_by=current_user.id,
    )

    try:
        db.add(variant_asset)
        db.commit()
        db.refresh(variant_asset)
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to persist translated content asset: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save translated content asset.",
        ) from exc

    return variant_asset


def create_manual_content_asset(
    db: Session,
    payload: ContentAssetCreate,
    current_user: User,
) -> ContentAsset:
    """Manually author a draft content asset in the studio."""
    _check_authoring_permission(current_user)

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
        provider_metadata={"provider": "manual", "author": current_user.full_name},
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
    """Update editable draft content. Marks operation_type as human_edit and resets approval if modified."""
    asset = get_content_asset_by_id(db, asset_id)
    _check_asset_ownership(asset, current_user)

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
        asset.operation_type = "human_edit"
        # If asset was already Approved, human edit resets it back to In Review
        if asset.review_status == "Approved":
            asset.review_status = "In Review"

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

    asset.review_status = target_status
    asset.review_notes = payload.review_notes
    asset.reviewed_by = current_user.id
    asset.reviewed_at = datetime.now(timezone.utc)

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
