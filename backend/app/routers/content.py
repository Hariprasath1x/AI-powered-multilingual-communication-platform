"""FastAPI router for AI Content Studio, Multilingual Translation, and Review Lifecycle."""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.core.dependencies import require_role
from app.services.ai.mock_provider import SUPPORTED_LANGUAGES
from app.schemas.content_asset import (
    ContentGenerateRequest,
    ContentTranslateRequest,
    ContentAssetCreate,
    ContentAssetUpdate,
    ContentReviewStatusUpdate,
    ContentAttachRequest,
    ContentAssetResponse,
    ContentVariantSummaryResponse,
    PaginatedContentAssetResponse,
    SUPPORTED_CHANNELS,
    SUPPORTED_TONES,
)
from app.services import content_service

logger = logging.getLogger("masscommai.content_router")

router = APIRouter(prefix="/content", tags=["Content Studio"])

CONTENT_READ_ROLES = ["Admin", "Campaign Manager", "Communication Team"]
CONTENT_AUTHOR_ROLES = ["Admin", "Campaign Manager"]


@router.get(
    "/languages",
    summary="Get supported languages for content generation and translation",
)
def get_supported_languages(
    current_user: User = Depends(require_role(CONTENT_READ_ROLES)),
) -> Dict[str, Any]:
    """Returns the list of supported Indian languages and their display names."""
    return {
        "languages": [
            {"code": code, "name": name}
            for code, name in sorted(SUPPORTED_LANGUAGES.items())
        ]
    }


@router.get(
    "/tones",
    summary="Get supported content communication tones",
)
def get_supported_tones(
    current_user: User = Depends(require_role(CONTENT_READ_ROLES)),
) -> Dict[str, Any]:
    """Returns supported communication tones: formal, informative, friendly, urgent, empathetic."""
    return {"tones": sorted(list(SUPPORTED_TONES))}


@router.get(
    "/channels",
    summary="Get supported communication channels for AI content adaptation",
)
def get_supported_channels(
    current_user: User = Depends(require_role(CONTENT_READ_ROLES)),
) -> Dict[str, Any]:
    """Returns supported distribution channels: Email, SMS, WhatsApp, Voice."""
    return {"channels": sorted(list(SUPPORTED_CHANNELS))}


@router.post(
    "/generate",
    response_model=ContentAssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate public awareness copy from a structured brief via AI",
)
async def generate_content_endpoint(
    payload: ContentGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_AUTHOR_ROLES)),
) -> Any:
    """
    Generates channel-tailored awareness content from topic, objective, tone, channel, and facts.
    Saves output as an editable draft in review status 'Draft'.
    Accessible to Admin and Campaign Manager.
    """
    asset = await content_service.generate_content(
        db=db,
        request=payload,
        current_user=current_user,
    )
    return ContentAssetResponse.model_validate(asset)


@router.post(
    "/manual",
    response_model=ContentAssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Manually author a draft content asset in the studio",
)
def create_manual_content_endpoint(
    payload: ContentAssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_AUTHOR_ROLES)),
) -> Any:
    """Creates a manual draft content asset without invoking the AI engine."""
    asset = content_service.create_manual_content_asset(
        db=db,
        payload=payload,
        current_user=current_user,
    )
    return ContentAssetResponse.model_validate(asset)


@router.post(
    "/{id}/translate",
    response_model=ContentAssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Translate an existing content asset into a target Indian language",
)
async def translate_content_endpoint(
    id: int = Path(..., ge=1, description="Content Asset ID to translate"),
    payload: ContentTranslateRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_AUTHOR_ROLES)),
) -> Any:
    """
    Translates content into target language while strictly preserving placeholders like {name} and {city}.
    Creates a new linked variant asset without modifying the source asset.
    Accessible to Admin and Campaign Manager.
    """
    variant = await content_service.translate_content(
        db=db,
        asset_id=id,
        request=payload,
        current_user=current_user,
    )
    return ContentAssetResponse.model_validate(variant)


@router.get(
    "",
    response_model=PaginatedContentAssetResponse,
    summary="List content assets with search, filters, and pagination",
)
def list_content_assets_endpoint(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term for title, body, or summary"),
    category: Optional[str] = Query(None, description="Filter by domain category"),
    channel: Optional[str] = Query(None, description="Filter by communication channel"),
    language: Optional[str] = Query(None, description="Filter by language code (source or target)"),
    review_status: Optional[str] = Query(None, description="Filter by review status (Draft, In Review, Approved)"),
    operation_type: Optional[str] = Query(None, description="Filter by operation type (generation, translation, human_edit)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_READ_ROLES)),
) -> Any:
    """List saved content assets with pagination and metadata metrics."""
    items, total = content_service.list_content_assets(
        db=db,
        current_user=current_user,
        page=page,
        size=size,
        search=search,
        category=category,
        channel=channel,
        language=language,
        review_status=review_status,
        operation_type=operation_type,
    )

    pages = (total + size - 1) // size if total > 0 else 1
    return PaginatedContentAssetResponse(
        items=[ContentAssetResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get(
    "/{id}",
    response_model=ContentAssetResponse,
    summary="Retrieve single content asset by ID",
)
def get_content_asset_endpoint(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_READ_ROLES)),
) -> Any:
    """Retrieves a content asset including channel simulation metrics and detected placeholders."""
    asset = content_service.get_content_asset_by_id(db, id)
    return ContentAssetResponse.model_validate(asset)


@router.put(
    "/{id}",
    response_model=ContentAssetResponse,
    summary="Update an editable draft or human-edited copy",
)
def update_content_asset_endpoint(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    payload: ContentAssetUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_AUTHOR_ROLES)),
) -> Any:
    """
    Update copy fields (title, body, cta). Automatically tracks edit as 'human_edit'
    and resets approval if content was previously approved.
    Admin can edit any asset; Campaign Manager can edit own assets.
    """
    asset = content_service.update_content_asset(
        db=db,
        asset_id=id,
        payload=payload,
        current_user=current_user,
    )
    return ContentAssetResponse.model_validate(asset)


@router.get(
    "/{id}/variants",
    response_model=List[ContentVariantSummaryResponse],
    summary="Retrieve all language variants and revisions in this content lineage",
)
def get_content_variants_endpoint(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_READ_ROLES)),
) -> Any:
    """Returns all translation variants and version lineage linked to this asset."""
    variants = content_service.get_variants(db, id, current_user)
    return [ContentVariantSummaryResponse.model_validate(v) for v in variants]


@router.patch(
    "/{id}/review",
    response_model=ContentAssetResponse,
    summary="Transition review status with reviewer audit tracking",
)
def update_review_status_endpoint(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    payload: ContentReviewStatusUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_AUTHOR_ROLES)),
) -> Any:
    """
    Transitions review status (Draft -> In Review -> Approved / Rejected).
    Records human reviewer user ID and timestamp for audit compliance.
    """
    asset = content_service.update_review_status(
        db=db,
        asset_id=id,
        payload=payload,
        current_user=current_user,
    )
    return ContentAssetResponse.model_validate(asset)


@router.post(
    "/{id}/attach",
    summary="Associate content asset with existing campaign or save as reusable template",
)
def attach_to_campaign_or_template_endpoint(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    payload: ContentAttachRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_AUTHOR_ROLES)),
) -> Dict[str, Any]:
    """
    Associates content with a campaign (updating its draft message body) or saves it
    as a reusable communication template. Preserves campaign lifecycle and dispatch safety.
    """
    return content_service.attach_to_campaign_or_template(
        db=db,
        asset_id=id,
        payload=payload,
        current_user=current_user,
    )


@router.delete(
    "/{id}",
    summary="Delete a draft content asset",
)
def delete_content_asset_endpoint(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_AUTHOR_ROLES)),
) -> Dict[str, Any]:
    """Deletes draft content asset. Admin can delete any; creators can delete own."""
    content_service.delete_content_asset(db, id, current_user)
    return {"status": "success", "message": f"Content asset {id} deleted successfully."}

