"""
MassCommAI - Multilingual Translation Pipeline Service.

Provides complete translation orchestration across 10 Indian languages:
- Occurrence-aware placeholder preservation and corruption detection
- Deterministic PostgreSQL-backed translation caching with invalidation
- Independent batch translation with isolated error handling
- Explicit review workflow state machine (Pending -> Generated -> Needs Review -> Approved / Rejected)
- Dedicated translation review audit trail persistence
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, or_, and_, desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.user import User
from app.models.content_asset import ContentAsset
from app.models.translation import TranslationCache, TranslationReviewHistory
from app.schemas.content_asset import (
    ContentAssetResponse,
    BatchTranslationFailure,
    ContentBatchTranslateResponse,
    TranslationReviewHistoryResponse,
    SUPPORTED_LANGUAGES,
)
from app.services.ai.base import (
    TranslationRequest,
    AIProviderError,
    AIProviderTimeoutError,
    AIProviderQuotaError,
    PlaceholderPreservationError,
)
from app.services.ai.factory import get_ai_provider
from app.services.channel_constraints import calculate_channel_metrics
from app.services.placeholder_service import (
    validate_placeholders,
    extract_placeholders,
    PlaceholderValidationResult,
)
from app.services.translation_cache_service import (
    compute_source_content_hash,
    compute_translation_cache_key,
    get_cached_translation,
    save_cached_translation,
    invalidate_source_cache,
)

logger = logging.getLogger("masscommai.translation_service")

# Explicit review state transitions for translation assets (delegated to centralized content service)
from app.services.content_service import VALID_REVIEW_TRANSITIONS as TRANSLATION_REVIEW_TRANSITIONS


def check_authoring_permission(current_user: User) -> None:
    """Ensure user has Admin or Campaign Manager role for translation authoring."""
    role_name = current_user.role.name if current_user.role else ""
    if role_name not in ("Admin", "Campaign Manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins and Campaign Managers have permission to translate content.",
        )


def check_review_permission(current_user: User) -> None:
    """Ensure user has Admin or Campaign Manager role for reviewing and approving translations."""
    role_name = current_user.role.name if current_user.role else ""
    if role_name not in ("Admin", "Campaign Manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins and Campaign Managers can review, approve, or reject translations.",
        )


def record_review_transition(
    db: Session,
    content_asset_id: int,
    from_status: str,
    to_status: str,
    reviewer_id: int,
    review_notes: Optional[str] = None,
) -> TranslationReviewHistory:
    """Create persistent audit history record for translation state transition."""
    history_entry = TranslationReviewHistory(
        content_asset_id=content_asset_id,
        from_status=from_status,
        to_status=to_status,
        reviewer_id=reviewer_id,
        review_notes=review_notes.strip() if review_notes else None,
    )
    db.add(history_entry)
    db.flush()
    return history_entry


async def translate_single_language(
    db: Session,
    source_asset: ContentAsset,
    target_language: str,
    current_user: User,
    notes: Optional[str] = None,
    provider_type: Optional[str] = None,
) -> ContentAsset:
    """
    Translate a content asset into a target Indian language.
    Guarantees:
    - Target language is one of 10 supported Indian languages.
    - Deterministic cache lookup (prevents redundant LLM calls).
    - Occurrence-aware placeholder preservation (multiset Counter comparison).
    - Prevents duplicate child ContentAssets for the same language variant under the root.
    - Persistent review history tracking starting in 'Generated' status.
    """
    check_authoring_permission(current_user)

    clean_tgt = target_language.lower().strip()
    if clean_tgt not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported target language '{target_language}'. Supported: {', '.join(sorted(SUPPORTED_LANGUAGES))}",
        )

    current_lang = (source_asset.target_language or source_asset.source_language or "en").lower().strip()
    if clean_tgt == current_lang:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target language '{target_language}' is identical to active language of content.",
        )

    root_id = source_asset.parent_id if source_asset.parent_id else source_asset.id

    provider = get_ai_provider(provider_type)

    # Compute source content hash and cache key (provider-scoped and prompt-versioned)
    source_hash = compute_source_content_hash(
        title=source_asset.title,
        body=source_asset.body,
        call_to_action=source_asset.call_to_action,
    )
    cache_key = compute_translation_cache_key(
        source_language=current_lang,
        target_language=clean_tgt,
        channel=source_asset.channel,
        source_content_hash=source_hash,
        context_notes=notes,
        provider_type=provider.get_provider_name(),
        model_name=provider.get_model_name() if hasattr(provider, "get_model_name") else None,
        prompt_version="v1.0",
    )

    # 1. Cache Check
    cached_entry = get_cached_translation(db, cache_key)
    translated_title: str
    translated_body: str
    translated_cta: Optional[str]
    summary_text: Optional[str]
    provider_meta: Dict[str, Any]
    is_from_cache: bool = False

    if cached_entry:
        # Validate that cached content still satisfies occurrence-aware placeholder preservation
        placeholder_check = validate_placeholders(
            source_title=source_asset.title,
            source_body=source_asset.body,
            source_cta=source_asset.call_to_action,
            translated_title=cached_entry.translated_title,
            translated_body=cached_entry.translated_body,
            translated_cta=cached_entry.translated_call_to_action,
        )
        if placeholder_check.is_valid:
            translated_title = cached_entry.translated_title
            translated_body = cached_entry.translated_body
            translated_cta = cached_entry.translated_call_to_action
            summary_text = cached_entry.summary
            provider_meta = dict(cached_entry.provider_metadata or {})
            provider_meta["cached"] = True
            provider_meta["hit_count"] = cached_entry.hit_count
            is_from_cache = True
            logger.info("Reusing verified cached translation for asset=%d, lang=%s", source_asset.id, clean_tgt)
        else:
            logger.warning("Cached translation for key=%s failed placeholder check; regenerating.", cache_key[:12])
            cached_entry = None

    if not cached_entry:
        # 2. Invoke AI Provider
        trans_req = TranslationRequest(
            source_text=source_asset.body,
            source_title=source_asset.title,
            source_cta=source_asset.call_to_action,
            source_language=current_lang,
            target_language=clean_tgt,
            channel=source_asset.channel,
            context=notes,
        )

        try:
            result = await provider.translate_content(trans_req)
        except AIProviderTimeoutError as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Translation into '{clean_tgt}' timed out. Please try again.",
            ) from exc
        except AIProviderQuotaError as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Translation rate limit reached for '{clean_tgt}'. Please retry shortly.",
            ) from exc
        except AIProviderError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=f"Translation failed for '{clean_tgt}': {exc.message}",
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error during translation into %s: %s", clean_tgt, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"An unexpected error occurred while translating into '{clean_tgt}'.",
            ) from exc

        translated_title = result.title
        translated_body = result.body
        translated_cta = result.call_to_action
        summary_text = result.summary
        provider_meta = dict(result.provider_metadata or {})
        provider_meta["cached"] = False

        # 3. Strict Occurrence-Aware Placeholder Validation
        placeholder_check = validate_placeholders(
            source_title=source_asset.title,
            source_body=source_asset.body,
            source_cta=source_asset.call_to_action,
            translated_title=translated_title,
            translated_body=translated_body,
            translated_cta=translated_cta,
        )

        if not placeholder_check.is_valid:
            logger.warning("Translation placeholder validation failed: %s", placeholder_check.error_message)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Translation placeholder safety violation for '{clean_tgt}': "
                    f"{placeholder_check.error_message}"
                ),
            )

        # 4. Save to Persistent Cache (never cache invalid translations)
        try:
            save_cached_translation(
                db=db,
                cache_key=cache_key,
                source_content_hash=source_hash,
                source_language=current_lang,
                target_language=clean_tgt,
                channel=source_asset.channel,
                translated_title=translated_title,
                translated_body=translated_body,
                translated_call_to_action=translated_cta,
                summary=summary_text,
                preserved_placeholders=extract_placeholders(f"{translated_title} {translated_body} {translated_cta or ''}"),
                provider_metadata=provider_meta,
            )
        except Exception as exc:
            logger.warning("Failed to save translation cache entry: %s", exc)

    # 5. Calculate Telecom Channel Metrics Snapshot
    metrics_snapshot = calculate_channel_metrics(
        channel=source_asset.channel,
        title=translated_title,
        body=translated_body,
        call_to_action=translated_cta,
        language=clean_tgt,
    )
    provider_meta["channel_metrics"] = metrics_snapshot.to_dict()

    # 6. Deduplication Check: Look for existing child asset for this target language under root_id
    existing_variant = db.execute(
        select(ContentAsset)
        .where(
            ContentAsset.parent_id == root_id,
            func.lower(ContentAsset.target_language) == clean_tgt,
        )
    ).scalar_one_or_none()

    if existing_variant:
        # If existing variant is already approved, do not overwrite without explicit human action; return it
        if existing_variant.review_status == "Approved":
            logger.info("Returning existing approved variant asset ID=%d for lang=%s", existing_variant.id, clean_tgt)
            return existing_variant

        # Update existing unapproved/draft variant to avoid duplicate rows
        prev_status = existing_variant.review_status
        provider_meta.pop("source_outdated", None)
        existing_variant.title = translated_title
        existing_variant.body = translated_body
        existing_variant.summary = summary_text
        existing_variant.call_to_action = translated_cta
        existing_variant.review_status = "Generated"
        existing_variant.provider_metadata = provider_meta
        existing_variant.updated_at = datetime.now(timezone.utc)

        record_review_transition(
            db=db,
            content_asset_id=existing_variant.id,
            from_status=prev_status,
            to_status="Generated",
            reviewer_id=current_user.id,
            review_notes="Regenerated translation updated",
        )
        db.commit()
        db.refresh(existing_variant)
        return existing_variant

    # 7. Create new ContentAsset for the translated variant
    new_variant = ContentAsset(
        title=translated_title,
        body=translated_body,
        summary=summary_text,
        call_to_action=translated_cta,
        category=source_asset.category,
        tone=source_asset.tone,
        channel=source_asset.channel,
        source_language=source_asset.source_language,
        target_language=clean_tgt,
        operation_type="translation",
        parent_id=root_id,
        campaign_id=source_asset.campaign_id,
        template_id=source_asset.template_id,
        review_status="Generated",
        provider_metadata=provider_meta,
        created_by=current_user.id,
    )

    try:
        db.add(new_variant)
        db.flush()

        record_review_transition(
            db=db,
            content_asset_id=new_variant.id,
            from_status="Pending",
            to_status="Generated",
            reviewer_id=current_user.id,
            review_notes="Initial AI translation generated",
        )

        db.commit()
        db.refresh(new_variant)
        logger.info("Persisted new translation variant ID=%d for target_lang=%s", new_variant.id, clean_tgt)
        return new_variant
    except IntegrityError as ie:
        db.rollback()
        logger.warning(
            "IntegrityError inserting translation variant for parent_id=%s, target_language=%s. Returning existing variant. Error: %s",
            root_id,
            clean_tgt,
            ie,
        )
        existing = db.execute(
            select(ContentAsset).where(
                ContentAsset.parent_id == root_id,
                func.lower(ContentAsset.target_language) == clean_tgt,
            )
        ).scalar_one_or_none()
        if existing:
            return existing
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Translation variant conflict for language {clean_tgt}.",
        )
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to persist translated content asset: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save translated content asset.",
        ) from exc


async def translate_batch_languages(
    db: Session,
    source_asset_id: int,
    target_languages: List[str],
    current_user: User,
    notes: Optional[str] = None,
    provider_type: Optional[str] = None,
) -> ContentBatchTranslateResponse:
    """
    Translate a source asset into multiple target Indian languages concurrently/independently.
    Ensures that a failure in one target language does NOT discard or rollback successes in other languages.
    """
    check_authoring_permission(current_user)

    from app.services.content_service import get_content_asset_by_id
    source_asset = get_content_asset_by_id(db, source_asset_id)

    successes: List[ContentAssetResponse] = []
    failures: List[BatchTranslationFailure] = []

    for tgt_lang in target_languages:
        try:
            variant = await translate_single_language(
                db=db,
                source_asset=source_asset,
                target_language=tgt_lang,
                current_user=current_user,
                notes=notes,
                provider_type=provider_type,
            )
            successes.append(ContentAssetResponse.model_validate(variant))
        except HTTPException as http_exc:
            failures.append(
                BatchTranslationFailure(
                    target_language=tgt_lang,
                    error=http_exc.detail,
                    status_code=http_exc.status_code,
                )
            )
        except Exception as exc:
            logger.exception("Batch translation error for lang %s: %s", tgt_lang, exc)
            failures.append(
                BatchTranslationFailure(
                    target_language=tgt_lang,
                    error=str(exc),
                    status_code=500,
                )
            )

    return ContentBatchTranslateResponse(
        source_asset_id=source_asset.id,
        successes=successes,
        failures=failures,
        total_requested=len(target_languages),
        total_succeeded=len(successes),
        total_failed=len(failures),
    )


def transition_translation_review(
    db: Session,
    asset_id: int,
    to_status: str,
    current_user: User,
    review_notes: Optional[str] = None,
) -> ContentAsset:
    """
    Delegate translation review transition to centralized content review service (AUDIT-T8-07).
    Eliminates duplicated state machine code and guarantees consistent audit logging and validation.
    """
    from app.services.content_service import update_review_status
    from app.schemas.content_asset import ContentReviewStatusUpdate

    payload = ContentReviewStatusUpdate(
        review_status=to_status,
        review_notes=review_notes,
    )
    return update_review_status(db, asset_id, payload, current_user)


def get_translation_review_history(
    db: Session,
    asset_id: int,
    current_user: User,
) -> List[TranslationReviewHistoryResponse]:
    """Retrieve full editorial review history for an asset."""
    from app.services.content_service import get_content_asset_by_id
    # Validates asset exists
    get_content_asset_by_id(db, asset_id)

    stmt = (
        select(TranslationReviewHistory)
        .options(joinedload(TranslationReviewHistory.reviewer))
        .where(TranslationReviewHistory.content_asset_id == asset_id)
        .order_by(TranslationReviewHistory.created_at.asc())
    )
    history_items = db.execute(stmt).scalars().all()

    results: List[TranslationReviewHistoryResponse] = []
    for item in history_items:
        results.append(
            TranslationReviewHistoryResponse(
                id=item.id,
                content_asset_id=item.content_asset_id,
                from_status=item.from_status,
                to_status=item.to_status,
                reviewer_id=item.reviewer_id,
                reviewer_name=item.reviewer.full_name if item.reviewer else None,
                review_notes=item.review_notes,
                created_at=item.created_at,
            )
        )
    return results
