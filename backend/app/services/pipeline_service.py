"""End-to-End Content Generation Pipeline Orchestrator (Milestone 2, Task 12).

Orchestrates the 5-stage automated workflow:
Stage 1: Content Generation (LLM brief synthesis)
Stage 2: Multilingual Translation (batch Indian languages)
Stage 3: Audience Personalization (segment demographic variants)
Stage 4: Tone Optimization (factual anchor preservation & readability)
Stage 5: Quality Review & Submission (compliance audit & review queue)
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.models.user import User
from app.models.campaign import Campaign
from app.models.content_asset import ContentAsset
from app.models.content_variant import ContentVariant
from app.models.pipeline_run import ContentPipelineRun
from app.schemas.pipeline import (
    ContentPipelineRequest,
    ContentPipelineRunResponse,
    ContentPipelineResumeRequest,
)
from app.schemas.content_asset import ContentGenerateRequest, ContentReviewStatusUpdate
from app.schemas.content_variant import ContentPersonalizeRequest, ContentVariantUpdate
from app.schemas.tone import ToneImproveRequest
from app.services.content_service import generate_content, update_review_status
from app.services.translation_service import translate_batch_languages
from app.services.personalization_service import personalize_content_asset, update_content_variant
from app.services.tone_service import improve_content_tone, analyze_content_tone
from app.services.quality_service import evaluate_content_asset, evaluate_content_variant

logger = logging.getLogger("masscommai.pipeline_service")

PIPELINE_STAGES = ["generate", "translate", "personalize", "tone_optimize", "review"]
CAMPAIGN_WRITE_ROLES = {"Admin", "Campaign Manager"}


def _check_pipeline_permissions(campaign: Campaign, current_user: User) -> None:
    """Verifies that the user has write permissions and belongs to the campaign's organization."""
    user_role = current_user.role.name if current_user.role else "Viewer"
    if user_role not in CAMPAIGN_WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only Admin and Campaign Manager roles can execute content pipelines.",
        )

    # Campaign Manager ownership / organization boundary
    is_admin = (user_role == "Admin")
    if not is_admin and campaign.created_by != current_user.id:
        user_org = getattr(current_user, "organization", None)
        campaign_creator_org = getattr(campaign.creator, "organization", None) if campaign.creator else None
        if user_org and campaign_creator_org and user_org != campaign_creator_org:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Campaign belongs to another organization.",
            )


def _build_run_response(run: ContentPipelineRun) -> ContentPipelineRunResponse:
    """Constructs a validated ContentPipelineRunResponse with computed progress."""
    progress = 0.0
    if run.total_stages > 0:
        progress = round((run.completed_stages / run.total_stages) * 100.0, 1)

    return ContentPipelineRunResponse(
        id=run.id,
        campaign_id=run.campaign_id,
        status=run.status,
        current_stage=run.current_stage,
        total_stages=run.total_stages,
        completed_stages=run.completed_stages,
        progress_percent=progress,
        idempotency_key=run.idempotency_key,
        config=run.config or {},
        stage_outputs=run.stage_outputs or {},
        generated_asset_ids=run.generated_asset_ids or [],
        generated_variant_ids=run.generated_variant_ids or [],
        error_message=run.error_message,
        created_by=run.created_by,
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
    )


async def initiate_and_run_pipeline(
    db: Session,
    campaign_id: int,
    request: ContentPipelineRequest,
    current_user: User,
) -> ContentPipelineRunResponse:
    """
    Validates campaign state, checks idempotency, creates a persistent pipeline run,
    and executes all stages incrementally.
    """
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign #{campaign_id} not found.",
        )

    _check_pipeline_permissions(campaign, current_user)

    # Restrict pipeline execution to editable campaigns
    if campaign.status in ("Approved", "Scheduled", "Archived"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot run content pipeline on a campaign with status '{campaign.status}'. Only Draft or In Review campaigns can be processed.",
        )

    # 1. Idempotency Check
    if request.idempotency_key:
        stmt = select(ContentPipelineRun).where(
            ContentPipelineRun.campaign_id == campaign_id,
            ContentPipelineRun.idempotency_key == request.idempotency_key,
        )
        existing = db.execute(stmt).scalars().first()
        if existing:
            if existing.status == "in_progress":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A pipeline execution with idempotency key '{request.idempotency_key}' is currently in progress.",
                )
            if existing.status == "completed":
                logger.info("Returning completed pipeline run #%d for idempotency key %s", existing.id, request.idempotency_key)
                return _build_run_response(existing)
            # If previously failed, resume it
            return await execute_pipeline_stages(
                db=db,
                run=existing,
                current_user=current_user,
            )

    # 2. Resolve default channels and segments
    channels = request.channels or campaign.channels or ["SMS"]
    segment_ids = request.segment_ids
    if segment_ids is None and campaign.segments:
        segment_ids = [s.id for s in campaign.segments]
    elif segment_ids is None:
        segment_ids = []

    topic = request.topic or campaign.name
    objective = request.objective or campaign.objective or f"Deliver public communications for {campaign.name}"

    config_dict = {
        "topic": topic,
        "objective": objective,
        "category": request.category,
        "channels": channels,
        "source_language": request.source_language,
        "target_languages": request.target_languages,
        "segment_ids": segment_ids,
        "target_tone": request.target_tone,
        "tone_instruction": request.tone_instruction,
        "facts": request.facts,
        "constraints": request.constraints,
        "submit_for_review": request.submit_for_review,
    }

    # 3. Create persistent ContentPipelineRun
    run = ContentPipelineRun(
        campaign_id=campaign_id,
        status="pending",
        current_stage="generate",
        total_stages=len(PIPELINE_STAGES),
        completed_stages=0,
        idempotency_key=request.idempotency_key,
        config=config_dict,
        stage_outputs={},
        generated_asset_ids=[],
        generated_variant_ids=[],
        created_by=current_user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # 4. Execute pipeline stages
    return await execute_pipeline_stages(
        db=db,
        run=run,
        current_user=current_user,
    )


async def execute_pipeline_stages(
    db: Session,
    run: ContentPipelineRun,
    current_user: User,
    force_stage: Optional[str] = None,
) -> ContentPipelineRunResponse:
    """
    Executes the 5 stages sequentially with per-stage transaction boundaries and recovery.
    Skips previously completed stages unless force_stage is requested.
    """
    campaign = db.get(Campaign, run.campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign #{run.campaign_id} not found.",
        )

    config = run.config or {}
    stage_outputs = dict(run.stage_outputs or {})
    generated_asset_ids = list(run.generated_asset_ids or [])
    generated_variant_ids = list(run.generated_variant_ids or [])

    run.status = "in_progress"
    run.error_message = None
    db.commit()

    try:
        # -------------------------------------------------------------
        # STAGE 1: Content Generation (LLM Brief Synthesis)
        # -------------------------------------------------------------
        should_run_stage_1 = (
            force_stage == "generate"
            or "generate" not in stage_outputs
            or stage_outputs["generate"].get("status") != "completed"
        )
        if should_run_stage_1:
            run.current_stage = "generate"
            db.commit()

            channels = config.get("channels", ["SMS"])
            stage_1_assets: List[Dict[str, Any]] = []

            for ch in channels:
                # Check if asset for this channel already exists in this run
                existing_asset = None
                for a_id in generated_asset_ids:
                    cand = db.get(ContentAsset, a_id)
                    if cand and cand.channel.lower() == ch.lower() and cand.parent_id is None:
                        existing_asset = cand
                        break

                if existing_asset:
                    asset = existing_asset
                else:
                    facts_val = config.get("facts")
                    if isinstance(facts_val, list):
                        facts_str = "; ".join(facts_val) if facts_val else None
                    elif isinstance(facts_val, str):
                        facts_str = facts_val
                    else:
                        facts_str = None

                    constraints_val = config.get("constraints")
                    if isinstance(constraints_val, list):
                        constraints_str = "; ".join(constraints_val) if constraints_val else None
                    elif isinstance(constraints_val, str):
                        constraints_str = constraints_val
                    else:
                        constraints_str = None

                    raw_tone = (config.get("target_tone") or "informative").lower().strip()
                    tone_map = {
                        "friendly": "friendly",
                        "formal": "formal",
                        "urgent": "urgent",
                        "empathetic": "empathetic",
                        "informative": "informative",
                        "neutral": "informative",
                        "harsh": "urgent",
                    }
                    gen_tone = tone_map.get(raw_tone, "informative")

                    brief_req = ContentGenerateRequest(
                        topic=config.get("topic", campaign.name),
                        objective=config.get("objective", campaign.objective or "Public awareness broadcast"),
                        audience_description=None,
                        category=config.get("category", "Public Awareness"),
                        tone=gen_tone,
                        channel=ch,
                        source_language=config.get("source_language", "en"),
                        facts=facts_str,
                        constraints=constraints_str,
                        campaign_id=campaign.id,
                    )
                    asset = await generate_content(db=db, request=brief_req, current_user=current_user)
                    if asset.id not in generated_asset_ids:
                        generated_asset_ids.append(asset.id)

                stage_1_assets.append({
                    "asset_id": asset.id,
                    "channel": asset.channel,
                    "title": asset.title,
                    "source_language": asset.source_language,
                    "review_status": asset.review_status,
                })

            stage_outputs["generate"] = {
                "status": "completed",
                "summary": f"Generated {len(stage_1_assets)} core content asset(s) across channel(s): {', '.join(channels)}.",
                "item_count": len(stage_1_assets),
                "assets": stage_1_assets,
            }
            run.stage_outputs = stage_outputs
            run.generated_asset_ids = generated_asset_ids
            run.completed_stages = 1
            run.current_stage = "translate"
            db.commit()
            logger.info("Pipeline #%d: Stage 1 (Generate) completed successfully.", run.id)

        # -------------------------------------------------------------
        # STAGE 2: Multilingual Translation
        # -------------------------------------------------------------
        should_run_stage_2 = (
            force_stage in ("generate", "translate")
            or "translate" not in stage_outputs
            or stage_outputs["translate"].get("status") != "completed"
        )
        if should_run_stage_2:
            run.current_stage = "translate"
            db.commit()

            target_languages = config.get("target_languages", [])
            stage_2_translations: List[Dict[str, Any]] = []

            if target_languages:
                # Find root assets from Stage 1
                root_assets = [
                    db.get(ContentAsset, a_id)
                    for a_id in generated_asset_ids
                    if db.get(ContentAsset, a_id) and db.get(ContentAsset, a_id).parent_id is None
                ]

                for root_a in root_assets:
                    # Filter out source language
                    langs_to_translate = [
                        lang for lang in target_languages
                        if lang.lower() != (root_a.source_language or "en").lower()
                    ]
                    if langs_to_translate:
                        batch_res = await translate_batch_languages(
                            db=db,
                            source_asset_id=root_a.id,
                            target_languages=langs_to_translate,
                            current_user=current_user,
                            notes=f"Auto-generated via Pipeline #{run.id}",
                        )
                        for item in batch_res.successes:
                            if item.id not in generated_asset_ids:
                                generated_asset_ids.append(item.id)
                            stage_2_translations.append({
                                "translation_asset_id": item.id,
                                "parent_asset_id": root_a.id,
                                "language": item.target_language,
                                "channel": item.channel,
                                "title": item.title,
                            })

            stage_outputs["translate"] = {
                "status": "completed",
                "summary": f"Translated into {len(stage_2_translations)} language variant(s).",
                "item_count": len(stage_2_translations),
                "translations": stage_2_translations,
            }
            run.stage_outputs = stage_outputs
            run.generated_asset_ids = generated_asset_ids
            run.completed_stages = 2
            run.current_stage = "personalize"
            db.commit()
            logger.info("Pipeline #%d: Stage 2 (Translate) completed successfully.", run.id)

        # -------------------------------------------------------------
        # STAGE 3: Audience-Specific Personalization
        # -------------------------------------------------------------
        should_run_stage_3 = (
            force_stage in ("generate", "translate", "personalize")
            or "personalize" not in stage_outputs
            or stage_outputs["personalize"].get("status") != "completed"
        )
        if should_run_stage_3:
            run.current_stage = "personalize"
            db.commit()

            segment_ids = config.get("segment_ids", [])
            stage_3_variants: List[Dict[str, Any]] = []

            if segment_ids:
                root_assets = [
                    db.get(ContentAsset, a_id)
                    for a_id in generated_asset_ids
                    if db.get(ContentAsset, a_id) and db.get(ContentAsset, a_id).parent_id is None
                ]

                for root_a in root_assets:
                    pers_req = ContentPersonalizeRequest(
                        segment_ids=segment_ids,
                        channel=root_a.channel,
                        language=root_a.source_language or "en",
                    )
                    pers_res = personalize_content_asset(
                        db=db,
                        asset_id=root_a.id,
                        payload=pers_req,
                        current_user=current_user,
                    )
                    for item in pers_res.variants:
                        if item.status == "success" and item.variant:
                            if item.variant.id not in generated_variant_ids:
                                generated_variant_ids.append(item.variant.id)
                            stage_3_variants.append({
                                "variant_id": item.variant.id,
                                "source_content_id": root_a.id,
                                "segment_id": item.segment_id,
                                "segment_name": item.segment_name,
                                "title": item.variant.variant_title,
                            })

            stage_outputs["personalize"] = {
                "status": "completed",
                "summary": f"Generated {len(stage_3_variants)} demographic personalization variant(s).",
                "item_count": len(stage_3_variants),
                "variants": stage_3_variants,
            }
            run.stage_outputs = stage_outputs
            run.generated_variant_ids = generated_variant_ids
            run.completed_stages = 3
            run.current_stage = "tone_optimize"
            db.commit()
            logger.info("Pipeline #%d: Stage 3 (Personalize) completed successfully.", run.id)

        # -------------------------------------------------------------
        # STAGE 4: Sentiment-Aware Tone Optimization
        # -------------------------------------------------------------
        should_run_stage_4 = (
            force_stage in ("generate", "translate", "personalize", "tone_optimize")
            or "tone_optimize" not in stage_outputs
            or stage_outputs["tone_optimize"].get("status") != "completed"
        )
        if should_run_stage_4:
            run.current_stage = "tone_optimize"
            db.commit()

            target_tone = config.get("target_tone", "Informative")
            tone_instruction = config.get("tone_instruction")
            stage_4_results: List[Dict[str, Any]] = []

            root_assets = [
                db.get(ContentAsset, a_id)
                for a_id in generated_asset_ids
                if db.get(ContentAsset, a_id) and db.get(ContentAsset, a_id).parent_id is None
            ]

            for root_a in root_assets:
                improve_req = ToneImproveRequest(
                    target_tone=target_tone,
                    adjustment_instruction=tone_instruction,
                    channel=root_a.channel,
                )
                improve_res = await improve_content_tone(
                    db=db,
                    asset_id=root_a.id,
                    payload=improve_req,
                    current_user=current_user,
                )

                # Apply tone-optimized copy to draft asset
                root_a.body = improve_res.improved_content
                db.commit()
                db.refresh(root_a)

                # Analyze final tone alignment
                analysis = analyze_content_tone(
                    db=db,
                    asset_id=root_a.id,
                    target_tone_override=target_tone,
                    current_user=current_user,
                )

                stage_4_results.append({
                    "asset_id": root_a.id,
                    "target_tone": target_tone,
                    "detected_tone": analysis.detected_tone,
                    "sentiment_polarity": analysis.sentiment_polarity,
                    "readability_score": analysis.readability_score,
                    "clarity_score": analysis.clarity_score,
                    "words_added": improve_res.diff.added_words_count,
                    "words_deleted": improve_res.diff.deleted_words_count,
                })

            stage_outputs["tone_optimize"] = {
                "status": "completed",
                "summary": f"Tone-optimized {len(stage_4_results)} content asset(s) to '{target_tone}'.",
                "item_count": len(stage_4_results),
                "optimizations": stage_4_results,
            }
            run.stage_outputs = stage_outputs
            run.completed_stages = 4
            run.current_stage = "review"
            db.commit()
            logger.info("Pipeline #%d: Stage 4 (Tone Optimize) completed successfully.", run.id)

        # -------------------------------------------------------------
        # STAGE 5: Quality Review & Submission
        # -------------------------------------------------------------
        should_run_stage_5 = (
            force_stage is not None
            or "review" not in stage_outputs
            or stage_outputs["review"].get("status") != "completed"
        )
        if should_run_stage_5:
            run.current_stage = "review"
            db.commit()

            submit_for_review = config.get("submit_for_review", True)
            audited_assets: List[Dict[str, Any]] = []
            audited_variants: List[Dict[str, Any]] = []

            # 1. Audit and optionally transition ContentAsset records
            for a_id in generated_asset_ids:
                asset = db.get(ContentAsset, a_id)
                if not asset:
                    continue

                # Run quality evaluation
                assessment = await evaluate_content_asset(
                    db=db,
                    asset_id=asset.id,
                    current_user=current_user,
                )

                # Transition to In Review if requested
                new_status = asset.review_status
                if submit_for_review and asset.review_status in ("Draft", "Generated"):
                    update_review_status(
                        db=db,
                        asset_id=asset.id,
                        payload=ContentReviewStatusUpdate(
                            review_status="In Review",
                            review_notes="Automated pipeline submission for human editorial sign-off.",
                        ),
                        current_user=current_user,
                    )
                    db.refresh(asset)
                    new_status = asset.review_status

                audited_assets.append({
                    "asset_id": asset.id,
                    "title": asset.title,
                    "channel": asset.channel,
                    "overall_score": assessment.overall_score,
                    "critical_issues": assessment.critical_issues_count,
                    "review_status": new_status,
                })

            # 2. Audit and optionally transition ContentVariant records
            for v_id in generated_variant_ids:
                variant = db.get(ContentVariant, v_id)
                if not variant:
                    continue

                # Run variant quality evaluation
                var_assessment = evaluate_content_variant(
                    db=db,
                    variant_id=variant.id,
                    current_user=current_user,
                )

                new_var_status = variant.review_status
                if submit_for_review and variant.review_status == "Draft":
                    update_content_variant(
                        db=db,
                        variant_id=variant.id,
                        payload=ContentVariantUpdate(
                            review_status="In_Review",
                            review_notes="Automated pipeline submission for demographic variant review.",
                        ),
                        current_user=current_user,
                    )
                    db.refresh(variant)
                    new_var_status = variant.review_status

                audited_variants.append({
                    "variant_id": variant.id,
                    "title": variant.variant_title,
                    "overall_score": var_assessment.overall_score,
                    "critical_issues": var_assessment.critical_issues_count,
                    "review_status": new_var_status,
                })

            stage_outputs["review"] = {
                "status": "completed",
                "summary": f"Audited {len(audited_assets)} asset(s) and {len(audited_variants)} variant(s). Submitted to 'In Review' queue: {submit_for_review}.",
                "item_count": len(audited_assets) + len(audited_variants),
                "assets": audited_assets,
                "variants": audited_variants,
            }
            run.stage_outputs = stage_outputs
            run.completed_stages = 5
            run.current_stage = "completed"
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info("Pipeline #%d: Stage 5 (Review) completed successfully. Full pipeline complete.", run.id)

    except HTTPException as http_exc:
        db.rollback()
        run.status = "failed"
        run.error_message = f"HTTP {http_exc.status_code}: {http_exc.detail}"
        db.commit()
        logger.error("Pipeline #%d failed at stage '%s': %s", run.id, run.current_stage, http_exc.detail)
        raise http_exc
    except Exception as exc:
        db.rollback()
        run.status = "failed"
        run.error_message = f"Internal error during stage '{run.current_stage}': {str(exc)}"
        db.commit()
        logger.exception("Pipeline #%d unexpected failure at stage '%s': %s", run.id, run.current_stage, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Content pipeline execution failed at stage '{run.current_stage}': {str(exc)}",
        )

    db.refresh(run)
    return _build_run_response(run)


def get_pipeline_run_response(
    db: Session,
    campaign_id: int,
    run_id: int,
    current_user: User,
) -> ContentPipelineRunResponse:
    """Retrieves pipeline run status and stage outputs with RBAC boundary enforcement."""
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign #{campaign_id} not found.",
        )

    run = db.get(ContentPipelineRun, run_id)
    if not run or run.campaign_id != campaign_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run #{run_id} not found for campaign #{campaign_id}.",
        )

    _check_pipeline_permissions(campaign, current_user)
    return _build_run_response(run)


def list_pipeline_runs(
    db: Session,
    campaign_id: int,
    current_user: User,
    limit: int = 20,
) -> List[ContentPipelineRunResponse]:
    """Lists historical and active pipeline runs for a campaign."""
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign #{campaign_id} not found.",
        )

    _check_pipeline_permissions(campaign, current_user)

    stmt = (
        select(ContentPipelineRun)
        .where(ContentPipelineRun.campaign_id == campaign_id)
        .order_by(desc(ContentPipelineRun.created_at))
        .limit(limit)
    )
    runs = db.execute(stmt).scalars().all()
    return [_build_run_response(r) for r in runs]


async def resume_pipeline_run(
    db: Session,
    campaign_id: int,
    run_id: int,
    payload: ContentPipelineResumeRequest,
    current_user: User,
) -> ContentPipelineRunResponse:
    """Resumes an incomplete or failed pipeline execution from the earliest uncompleted stage."""
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign #{campaign_id} not found.",
        )

    run = db.get(ContentPipelineRun, run_id)
    if not run or run.campaign_id != campaign_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run #{run_id} not found for campaign #{campaign_id}.",
        )

    _check_pipeline_permissions(campaign, current_user)

    if run.status == "completed" and not payload.force_stage:
        return _build_run_response(run)

    return await execute_pipeline_stages(
        db=db,
        run=run,
        current_user=current_user,
        force_stage=payload.force_stage,
    )
