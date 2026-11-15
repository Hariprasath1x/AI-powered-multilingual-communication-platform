"""FastAPI router for AI Content Studio, Multilingual Translation, and Review Lifecycle."""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Path, Body, status
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
    ContentPreviewMetricsRequest,
    ChannelMetricsResponse,
    ContentAssetResponse,
    ContentVariantSummaryResponse,
    PaginatedContentAssetResponse,
    ContentBatchTranslateRequest,
    ContentBatchTranslateResponse,
    TranslationReviewHistoryResponse,
    SUPPORTED_CHANNELS,
    SUPPORTED_TONES,
)
from app.services import content_service, translation_service, tone_service, personalization_service
from app.services.channel_constraints import calculate_channel_metrics
from app.schemas.tone import (
    ToneAnalyzeRequest,
    ToneAnalyzeResponse,
    ToneImproveRequest,
    ToneImproveResponse,
)
from app.schemas.content_variant import (
    ContentVariantResponse,
    ContentVariantUpdate,
    ContentPersonalizeRequest,
    ContentPersonalizeResponse,
    RecipientPreviewRequest,
    RecipientPreviewResponse,
)
from app.schemas.content_quality import ContentQualityAssessmentResponse

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
    "/preview-metrics",
    response_model=ChannelMetricsResponse,
    summary="Simulate channel constraints and telecommunications metrics in real-time",
)
def preview_channel_metrics_endpoint(
    payload: ContentPreviewMetricsRequest,
    current_user: User = Depends(require_role(CONTENT_READ_ROLES)),
) -> Any:
    """
    Stateless, low-latency telecommunications constraint calculator.

    Analyzes draft copy in memory without database persistence or AI invocation.
    Returns GSM-7/UCS-2 segmentation, voice duration estimates, and structured warnings.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    metrics = calculate_channel_metrics(
        channel=payload.channel,
        title=payload.title,
        body=payload.body,
        call_to_action=payload.call_to_action,
        language=payload.language,
        mode=payload.mode or "freeform",
    )
    return ChannelMetricsResponse.model_validate(metrics.to_dict())


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


@router.post(
    "/{id}/translate/batch",
    response_model=ContentBatchTranslateResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch translate a content asset into multiple Indian languages with failure isolation",
)
async def batch_translate_content_endpoint(
    id: int = Path(..., ge=1, description="Source Content Asset ID"),
    payload: ContentBatchTranslateRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_AUTHOR_ROLES)),
) -> Any:
    """
    Translates source content into multiple target Indian languages independently.
    Failures in one language do not discard or fail translations in other languages.
    Accessible to Admin and Campaign Manager.
    """
    return await translation_service.translate_batch_languages(
        db=db,
        source_asset_id=id,
        target_languages=payload.target_languages,
        current_user=current_user,
        notes=payload.notes,
        provider_type=payload.provider_type,
    )


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


@router.get(
    "/{id}/review-history",
    response_model=List[TranslationReviewHistoryResponse],
    summary="Get full translation review and audit history for an asset",
)
def get_content_review_history_endpoint(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_READ_ROLES)),
) -> Any:
    """Returns chronological audit trail of all review status transitions for this asset."""
    return translation_service.get_translation_review_history(
        db=db,
        asset_id=id,
        current_user=current_user,
    )


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


@router.post(
    "/{id}/tone/analyze",
    response_model=ToneAnalyzeResponse,
    summary="Analyze sentiment polarity, readability, clarity, and five-way tone",
)
def analyze_content_tone_endpoint(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    payload: Optional[ToneAnalyzeRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_READ_ROLES)),
) -> ToneAnalyzeResponse:
    """Computes explainable tone classification, sentiment polarity, and readability metrics."""
    return tone_service.analyze_content_tone(
        db=db,
        asset_id=id,
        current_user=current_user,
        text_override=payload.text_override if payload else None,
        target_tone_override=payload.target_tone if payload else None,
        channel_override=payload.channel if payload else None,
    )


@router.post(
    "/{id}/tone/improve",
    response_model=ToneImproveResponse,
    summary="Generate tone-optimized rewrite with factual anchor preservation",
)
async def improve_content_tone_endpoint(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    payload: ToneImproveRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_AUTHOR_ROLES)),
) -> ToneImproveResponse:
    """Generates revised copy adhering to requested tone while strictly preserving all facts, dates, and helplines."""
    return await tone_service.improve_content_tone(
        db=db,
        asset_id=id,
        payload=payload,
        current_user=current_user,
    )


# ---------------------------------------------------------------------------
# Task 9.A: Audience-Specific Content Personalization Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{id}/personalize",
    response_model=ContentPersonalizeResponse,
    summary="Generate audience segment-specific variants from root content asset",
)
def personalize_content_endpoint(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    payload: ContentPersonalizeRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_AUTHOR_ROLES)),
) -> ContentPersonalizeResponse:
    """Generates tailored demographic variants for selected segments while preserving facts and placeholders."""
    return personalization_service.personalize_content_asset(
        db=db,
        asset_id=id,
        payload=payload,
        current_user=current_user,
    )


@router.get(
    "/{id}/personalize/variants",
    response_model=List[ContentVariantResponse],
    summary="List all demographic variants under a content asset",
)
def list_content_variants_endpoint(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_READ_ROLES)),
) -> List[ContentVariantResponse]:
    """Retrieves all demographic variants created under the specified content asset."""
    return personalization_service.list_content_variants(
        db=db,
        asset_id=id,
        current_user=current_user,
    )


@router.patch(
    "/variants/{variant_id}",
    response_model=ContentVariantResponse,
    summary="Update content variant attributes or review status",
)
def update_content_variant_endpoint(
    variant_id: int = Path(..., ge=1, description="Content Variant ID"),
    payload: ContentVariantUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_READ_ROLES)),
) -> ContentVariantResponse:
    """Updates variant copy or review status. Approval requires valid quality evaluation without critical findings."""
    return personalization_service.update_content_variant(
        db=db,
        variant_id=variant_id,
        payload=payload,
        current_user=current_user,
    )


@router.delete(
    "/variants/{variant_id}",
    summary="Delete a content variant",
)
def delete_content_variant_endpoint(
    variant_id: int = Path(..., ge=1, description="Content Variant ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_AUTHOR_ROLES)),
) -> Dict[str, str]:
    """Deletes an audience content variant."""
    personalization_service.delete_content_variant(
        db=db,
        variant_id=variant_id,
        current_user=current_user,
    )
    return {"status": "success", "message": f"Content variant {variant_id} deleted successfully."}


@router.post(
    "/variants/{variant_id}/quality/evaluate",
    response_model=ContentQualityAssessmentResponse,
    summary="Evaluate content quality and compliance for a demographic variant",
)
def evaluate_content_variant_endpoint(
    variant_id: int = Path(..., ge=1, description="Content Variant ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_AUTHOR_ROLES)),
) -> ContentQualityAssessmentResponse:
    """Evaluates dynamic compliance rules and creates a persistent quality assessment for the variant."""
    from app.services.quality_service import evaluate_content_variant, _build_assessment_response
    from app.models.content_variant import ContentVariant
    assessment = evaluate_content_variant(db=db, variant_id=variant_id, current_user=current_user)
    variant = db.get(ContentVariant, variant_id)
    return _build_assessment_response(assessment, asset=assessment.content_asset, variant=variant)


@router.post(
    "/{id}/personalize/preview-recipient",
    response_model=RecipientPreviewResponse,
    summary="Preview personalized message rendering for a specific recipient (POST)",
)
def preview_recipient_post_endpoint(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    payload: RecipientPreviewRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_READ_ROLES)),
) -> RecipientPreviewResponse:
    """Simulates delivery rendering with segment variant resolution and placeholder substitution."""
    return personalization_service.preview_recipient_message(
        db=db,
        asset_id=id,
        payload=payload,
        current_user=current_user,
    )


@router.get(
    "/{id}/personalize/preview-recipient",
    response_model=RecipientPreviewResponse,
    summary="Preview personalized message rendering for a specific recipient (GET)",
)
def preview_recipient_get_endpoint(
    id: int = Path(..., ge=1, description="Content Asset ID"),
    recipient_id: int = Query(..., ge=1, description="Audience Member ID"),
    channel: Optional[str] = Query(None, description="Delivery channel override"),
    preferred_language: Optional[str] = Query(None, description="Language override"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(CONTENT_READ_ROLES)),
) -> RecipientPreviewResponse:
    """Simulates delivery rendering with segment variant resolution and placeholder substitution via GET query parameters."""
    req = RecipientPreviewRequest(
        recipient_id=recipient_id,
        channel=channel,
        preferred_language=preferred_language,
    )
    return personalization_service.preview_recipient_message(
        db=db,
        asset_id=id,
        payload=req,
        current_user=current_user,
    )



