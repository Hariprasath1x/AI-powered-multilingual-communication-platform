"""Audience-Specific Content Personalization Service (Milestone 2, Task 9.A)."""

import re
import hashlib
from typing import Optional, List, Dict, Any, Tuple, Set
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func
from fastapi import HTTPException, status

from app.models.content_asset import ContentAsset
from app.models.content_variant import ContentVariant
from app.models.segment import Segment
from app.models.audience import AudienceMember
from app.models.campaign import Campaign
from app.models.user import User
from app.models.content_quality import ContentQualityAssessment, ContentQualityFinding
from app.schemas.content_variant import (
    ContentVariantResponse,
    ContentVariantUpdate,
    ContentPersonalizeRequest,
    PersonalizeVariantItemResult,
    ContentPersonalizeResponse,
    RecipientPreviewRequest,
    RecipientPreviewResponse,
)
from app.services.quality.rule_engine import DeterministicRuleEngine
from app.services.quality.base import FindingSeverity
from app.services.distribution.job_service import render_personalized_content
from app.services.tone_service import extract_factual_anchors, verify_and_repair_factual_anchors

PLACEHOLDER_REGEX = re.compile(r"\{[a-zA-Z0-9_]+\}")


def compute_variant_hash(title: str, body: str, cta: Optional[str]) -> str:
    """Computes deterministic SHA-256 content version hash for variant integrity tracking."""
    raw = f"{title.strip()}|{body.strip()}|{(cta or '').strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compile_segment_persona(segment: Segment) -> Dict[str, Any]:
    """
    Analyzes segment filter rules and attributes to compile an actionable demographic persona.
    Does NOT infer or fabricate sensitive attributes; uses declared filter criteria.
    """
    rules = segment.filter_rules or {}
    name_lower = segment.name.lower()
    desc_lower = (segment.description or "").lower()

    # Default general demographic profile
    profile = {
        "persona_type": "General Public",
        "key_focus": "Clear, accessible, direct community guidance",
        "recommended_tone": "informative",
        "tailoring_guidance": "Use plain language and actionable bullet points.",
        "demographic_summary": segment.description or f"Citizens targeted under {segment.name}",
    }

    # Inspect Age Criteria
    age_min = rules.get("age_min")
    age_max = rules.get("age_max")
    age_range = rules.get("age_range")

    is_senior = (
        (isinstance(age_min, (int, float)) and age_min >= 55)
        or "senior" in name_lower
        or "elder" in name_lower
        or "pension" in name_lower
    )
    is_youth = (
        (isinstance(age_max, (int, float)) and age_max <= 30)
        or "youth" in name_lower
        or "student" in name_lower
        or "young" in name_lower
    )
    is_rural_or_farmer = (
        "farmer" in name_lower
        or "rural" in name_lower
        or "agriculture" in name_lower
        or "kisan" in name_lower
    )
    is_urban = (
        "urban" in name_lower
        or "metro" in name_lower
        or "city" in name_lower
    )

    if is_senior:
        profile["persona_type"] = "Senior Citizens (60+)"
        profile["recommended_tone"] = "empathetic"
        profile["key_focus"] = "Physical assistance, helpline availability, family safety, calm reassurance"
        profile["tailoring_guidance"] = (
            "Open with respectful, warm address. Prioritize physical comfort, direct phone assistance, "
            "and transport support. Avoid confusing technical abbreviations or dense web-only requirements."
        )
    elif is_youth:
        profile["persona_type"] = "Youth & Young Adults (18–29)"
        profile["recommended_tone"] = "friendly"
        profile["key_focus"] = "Fast action, mobile portals, digital coordination, peer community safety"
        profile["tailoring_guidance"] = (
            "Use active, energetic phrasing. Highlight mobile apps, rapid status links, and ways to assist "
            "vulnerable family members and neighbors."
        )
    elif is_rural_or_farmer:
        profile["persona_type"] = "Rural & Agricultural Communities"
        profile["recommended_tone"] = "informative"
        profile["key_focus"] = "Crop/livestock protection, local panchayat center contacts, rural transport"
        profile["tailoring_guidance"] = (
            "Focus on practical farm, livestock, and grain storage safety. Provide block development "
            "and agricultural extension helpline contacts."
        )
    elif is_urban:
        profile["persona_type"] = "Urban Residents & Commuters"
        profile["recommended_tone"] = "formal"
        profile["key_focus"] = "Transit disruptions, civic utilities, municipal ward offices"
        profile["tailoring_guidance"] = (
            "Provide concise ward-level routing, municipal helpline numbers, and digital utility alerts."
        )

    return profile


def _generate_segment_variant_deterministic(
    source_title: str,
    source_body: str,
    source_cta: Optional[str],
    segment: Segment,
    persona: Dict[str, Any],
    channel: str,
) -> Tuple[str, str, Optional[str], str]:
    """
    Deterministic demographic copy adapter.
    Adapts headline, body, and CTA to resonate with the segment persona while strictly preserving facts and placeholders.
    """
    p_type = persona["persona_type"]
    p_focus = persona["key_focus"]

    # Factual anchors extraction
    anchors = extract_factual_anchors(source_body)
    all_placeholders = sorted(list(anchors["placeholders"]))
    all_helplines = sorted(list(anchors["helplines"]))

    # 1. Adapt Title
    if "Senior" in p_type:
        var_title = f"{source_title} — Advisory for Senior Citizens & Families"
    elif "Youth" in p_type:
        var_title = f"{source_title} — Action Update for Youth & Students"
    elif "Rural" in p_type or "Farmer" in p_type:
        var_title = f"{source_title} — Rural & Community Advisory"
    elif "Urban" in p_type:
        var_title = f"{source_title} — Urban Transit & Civic Bulletin"
    else:
        var_title = f"{source_title} — {segment.name} Edition"

    # 2. Adapt Body Copy
    var_body = source_body

    if "Senior" in p_type:
        # Add respectful greeting and physical support clauses
        opening = "Dear Senior Citizens and Respected Families,\n\n"
        closing = (
            "\n\nSpecial Assistance Note: Priority physical support and transport arrangements are in place for elderly citizens. "
            "If you or an elderly family member need physical aid, please call our primary helpline."
        )
        # Adapt body
        var_body = opening + source_body + closing

    elif "Youth" in p_type:
        opening = "Attention Students and Young Citizens,\n\n"
        closing = (
            "\n\nCommunity Leadership: Help coordinate safety checks for younger children and elderly neighbors. "
            "Share verified information only via official channels."
        )
        var_body = opening + source_body + closing

    elif "Rural" in p_type or "Farmer" in p_type:
        opening = "Important Advisory for Farmers and Rural Households,\n\n"
        closing = (
            "\n\nRural Advisory: Secure livestock in elevated shelters and protect harvested stocks. "
            "Contact your local Gram Panchayat representative for immediate agricultural assistance."
        )
        var_body = opening + source_body + closing

    else:
        opening = f"Targeted Community Notice for {segment.name}:\n\n"
        var_body = opening + source_body

    # 3. Adapt CTA
    if "Senior" in p_type:
        var_cta = "Call For Free Senior Support" if all_helplines else (source_cta or "Contact Support")
    elif "Youth" in p_type:
        var_cta = "Join Community Action Team" if not source_cta else f"{source_cta} (Fast Track)"
    elif "Rural" in p_type or "Farmer" in p_type:
        var_cta = "Connect With Panchayat Coordinator"
    else:
        var_cta = source_cta or "Review Guidelines"

    # 4. Formulate Personalization Notes
    notes = (
        f"Personalized for demographic persona '{p_type}'. "
        f"Key focus: {p_focus}. Adapted opening framing and CTA while maintaining core facts."
    )

    # 5. Guarantee factual anchors and placeholders
    repaired_body, _ = verify_and_repair_factual_anchors(source_body, var_body)

    return var_title, repaired_body, var_cta, notes


def personalize_content_asset(
    db: Session,
    asset_id: int,
    payload: ContentPersonalizeRequest,
    current_user: User,
) -> ContentPersonalizeResponse:
    """
    Generates audience segment-specific content variants from a root content asset.
    Enforces multi-tenant scoping, RBAC, placeholder shielding, and dynamic compliance checking.
    """
    asset = db.get(ContentAsset, asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content asset #{asset_id} not found.",
        )

    # Multi-tenant boundary check
    user_role = current_user.role.name if current_user.role else "Viewer"
    is_admin = (user_role == "Admin")
    user_org = getattr(current_user, "organization", None)

    asset_org = None
    if asset.campaign and asset.campaign.creator:
        asset_org = getattr(asset.campaign.creator, "organization", None)
    elif asset.creator:
        asset_org = getattr(asset.creator, "organization", None)

    if not is_admin and user_org and asset_org and user_org != asset_org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Content asset belongs to another organization.",
        )

    campaign_id = asset.campaign_id
    if not campaign_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content asset must be attached to a campaign before generating audience segment variants.",
        )

    # Target language & channel
    target_lang = (payload.language or asset.source_language or "en").lower().strip()
    target_channel = payload.channel or asset.channel or "Email"

    item_results: List[PersonalizeVariantItemResult] = []
    success_count = 0
    failure_count = 0

    # Load active compliance rules for organization
    active_rules: List[Any] = []
    try:
        from app.models.compliance_rule import ComplianceRule
        rule_query = select(ComplianceRule).where(
            ComplianceRule.is_active.is_(True),
            or_(
                ComplianceRule.is_global.is_(True),
                ComplianceRule.organization.is_(None),
                ComplianceRule.organization == user_org,
            ),
        )
        active_rules = list(db.execute(rule_query).scalars().all())
    except Exception:
        active_rules = []

    for seg_id in payload.segment_ids:
        segment = db.get(Segment, seg_id)
        if not segment:
            item_results.append(
                PersonalizeVariantItemResult(
                    segment_id=seg_id,
                    segment_name=f"Segment #{seg_id}",
                    status="failed",
                    error=f"Segment #{seg_id} not found.",
                )
            )
            failure_count += 1
            continue

        # Check segment tenant isolation
        seg_org = getattr(segment.creator, "organization", None) if segment.creator else None
        if not is_admin and user_org and seg_org and user_org != seg_org:
            item_results.append(
                PersonalizeVariantItemResult(
                    segment_id=seg_id,
                    segment_name=segment.name,
                    status="failed",
                    error="Segment belongs to another organization.",
                )
            )
            failure_count += 1
            continue

        try:
            # 1. Compile persona
            persona = compile_segment_persona(segment)

            # 2. Generate demographic copy
            v_title, v_body, v_cta, v_notes = _generate_segment_variant_deterministic(
                source_title=asset.title,
                source_body=asset.body,
                source_cta=asset.call_to_action,
                segment=segment,
                persona=persona,
                channel=target_channel,
            )

            # 3. Dynamic compliance rule validation
            findings = DeterministicRuleEngine.evaluate(
                channel=target_channel,
                title=v_title,
                body=v_body,
                call_to_action=v_cta,
                source_language="en",
                target_language=target_lang,
                compliance_rules=active_rules,
            )

            # 4. Check for existing variant to support idempotent re-generation
            existing_stmt = select(ContentVariant).where(
                ContentVariant.source_content_id == asset.id,
                ContentVariant.segment_id == segment.id,
                func.lower(ContentVariant.language) == target_lang,
            )
            existing_variant = db.execute(existing_stmt).scalar_one_or_none()

            current_hash = compute_variant_hash(v_title, v_body, v_cta)

            if existing_variant:
                existing_variant.variant_title = v_title
                existing_variant.variant_body = v_body
                existing_variant.variant_cta = v_cta
                existing_variant.personalization_notes = v_notes
                existing_variant.channel = target_channel
                existing_variant.review_status = "Draft"  # Invalidate approval on new generation
                existing_variant.content_version_hash = current_hash
                variant_obj = existing_variant
            else:
                variant_obj = ContentVariant(
                    campaign_id=campaign_id,
                    source_content_id=asset.id,
                    segment_id=segment.id,
                    language=target_lang,
                    channel=target_channel,
                    variant_title=v_title,
                    variant_body=v_body,
                    variant_cta=v_cta,
                    personalization_notes=v_notes,
                    review_status="Draft",
                    content_version_hash=current_hash,
                    created_by=current_user.id,
                )
                db.add(variant_obj)

            db.flush()

            # Build response item
            resp_item = ContentVariantResponse(
                id=variant_obj.id,
                campaign_id=variant_obj.campaign_id,
                source_content_id=variant_obj.source_content_id,
                segment_id=variant_obj.segment_id,
                segment_name=segment.name,
                language=variant_obj.language,
                channel=variant_obj.channel,
                variant_title=variant_obj.variant_title,
                variant_body=variant_obj.variant_body,
                variant_cta=variant_obj.variant_cta,
                personalization_notes=variant_obj.personalization_notes,
                review_status=variant_obj.review_status,
                review_notes=variant_obj.review_notes,
                reviewed_by=variant_obj.reviewed_by,
                reviewed_at=variant_obj.reviewed_at,
                assessment_id=variant_obj.assessment_id,
                content_version_hash=variant_obj.content_version_hash,
                created_by=variant_obj.created_by,
                created_at=variant_obj.created_at or datetime.now(timezone.utc),
                updated_at=variant_obj.updated_at or datetime.now(timezone.utc),
            )

            item_results.append(
                PersonalizeVariantItemResult(
                    segment_id=segment.id,
                    segment_name=segment.name,
                    status="success",
                    variant=resp_item,
                )
            )
            success_count += 1

        except Exception as exc:
            item_results.append(
                PersonalizeVariantItemResult(
                    segment_id=segment.id,
                    segment_name=segment.name,
                    status="failed",
                    error=str(exc),
                )
            )
            failure_count += 1

    db.commit()

    return ContentPersonalizeResponse(
        source_content_id=asset.id,
        total_requested=len(payload.segment_ids),
        success_count=success_count,
        failure_count=failure_count,
        variants=item_results,
    )


def list_content_variants(
    db: Session,
    asset_id: int,
    current_user: User,
) -> List[ContentVariantResponse]:
    """Retrieves all demographic variants created under a source content asset."""
    asset = db.get(ContentAsset, asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content asset #{asset_id} not found.",
        )

    # Multi-tenant boundary check
    user_role = current_user.role.name if current_user.role else "Viewer"
    is_admin = (user_role == "Admin")
    user_org = getattr(current_user, "organization", None)

    asset_org = None
    if asset.campaign and asset.campaign.creator:
        asset_org = getattr(asset.campaign.creator, "organization", None)
    elif asset.creator:
        asset_org = getattr(asset.creator, "organization", None)

    if not is_admin and user_org and asset_org and user_org != asset_org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Content asset belongs to another organization.",
        )

    stmt = (
        select(ContentVariant)
        .where(ContentVariant.source_content_id == asset_id)
        .order_by(ContentVariant.id.asc())
    )
    variants = list(db.execute(stmt).scalars().all())

    results: List[ContentVariantResponse] = []
    for v in variants:
        seg_name = v.segment.name if v.segment else None
        results.append(
            ContentVariantResponse(
                id=v.id,
                campaign_id=v.campaign_id,
                source_content_id=v.source_content_id,
                segment_id=v.segment_id,
                segment_name=seg_name,
                language=v.language,
                channel=v.channel,
                variant_title=v.variant_title,
                variant_body=v.variant_body,
                variant_cta=v.variant_cta,
                personalization_notes=v.personalization_notes,
                review_status=v.review_status,
                review_notes=v.review_notes,
                reviewed_by=v.reviewed_by,
                reviewed_at=v.reviewed_at,
                assessment_id=v.assessment_id,
                content_version_hash=v.content_version_hash,
                created_by=v.created_by,
                created_at=v.created_at,
                updated_at=v.updated_at,
            )
        )
    return results


def update_content_variant(
    db: Session,
    variant_id: int,
    payload: ContentVariantUpdate,
    current_user: User,
) -> ContentVariantResponse:
    """
    Updates variant attributes or advances editorial review status.
    Enforces Invariant A–E: Approval requires a fresh, valid quality evaluation without critical findings.
    """
    variant = db.get(ContentVariant, variant_id)
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content variant #{variant_id} not found.",
        )

    # Multi-tenant boundary check
    user_role = current_user.role.name if current_user.role else "Viewer"
    is_admin = (user_role == "Admin")
    user_org = getattr(current_user, "organization", None)

    asset_org = None
    if variant.campaign and variant.campaign.creator:
        asset_org = getattr(variant.campaign.creator, "organization", None)
    elif variant.creator:
        asset_org = getattr(variant.creator, "organization", None)

    if not is_admin and user_org and asset_org and user_org != asset_org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Content variant belongs to another organization.",
        )

    material_change = False

    if payload.variant_title is not None and payload.variant_title != variant.variant_title:
        variant.variant_title = payload.variant_title
        material_change = True

    if payload.variant_body is not None and payload.variant_body != variant.variant_body:
        variant.variant_body = payload.variant_body
        material_change = True

    if payload.variant_cta is not None and payload.variant_cta != variant.variant_cta:
        variant.variant_cta = payload.variant_cta
        material_change = True

    if payload.personalization_notes is not None:
        variant.personalization_notes = payload.personalization_notes

    # Material content edit invalidates approval and version hash
    if material_change:
        variant.review_status = "Draft"
        variant.assessment_id = None
        variant.content_version_hash = compute_variant_hash(
            variant.variant_title, variant.variant_body, variant.variant_cta
        )
        variant.reviewed_by = None
        variant.reviewed_at = None

    # Handle Review Status Transitions
    if payload.review_status is not None:
        target_status = payload.review_status.strip()

        # RBAC: Only Admin and Campaign Manager can approve/reject
        if target_status in ("Approved", "Rejected") and user_role not in ("Admin", "Campaign Manager"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' cannot perform approval or rejection reviews.",
            )

        if target_status == "Rejected":
            notes = payload.review_notes or variant.review_notes
            if not notes or not notes.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Review notes are mandatory when rejecting content variants.",
                )
            variant.review_status = "Rejected"
            variant.review_notes = notes
            variant.reviewed_by = current_user.id
            variant.reviewed_at = datetime.now(timezone.utc)

        elif target_status == "Approved":
            # Check that content is not empty
            if len(variant.variant_body.strip()) < 10:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot approve empty or truncated content variant.",
                )

            from app.services.quality_service import (
                validate_variant_approval_readiness,
                evaluate_content_variant,
            )

            current_v_hash = compute_variant_hash(
                variant.variant_title, variant.variant_body, variant.variant_cta
            )

            # If variant has no linked assessment or is stale, evaluate it to create a fresh assessment
            if not variant.assessment_id or variant.content_version_hash != current_v_hash:
                evaluate_content_variant(db, variant.id, current_user)
                db.refresh(variant)

            # Enforce Invariants A, B, C: Assessment must be valid, for this exact variant, and clean of critical issues
            is_ready, err_code, reasons = validate_variant_approval_readiness(db, variant)
            if not is_ready:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot approve content variant: {'; '.join(reasons)}",
                )

            variant.review_status = "Approved"
            variant.reviewed_by = current_user.id
            variant.reviewed_at = datetime.now(timezone.utc)
            variant.content_version_hash = current_v_hash

        elif target_status == "In_Review":
            variant.review_status = "In_Review"
            if payload.review_notes:
                variant.review_notes = payload.review_notes

        elif target_status == "Draft":
            variant.review_status = "Draft"

    db.commit()
    db.refresh(variant)

    seg_name = variant.segment.name if variant.segment else None
    return ContentVariantResponse(
        id=variant.id,
        campaign_id=variant.campaign_id,
        source_content_id=variant.source_content_id,
        segment_id=variant.segment_id,
        segment_name=seg_name,
        language=variant.language,
        channel=variant.channel,
        variant_title=variant.variant_title,
        variant_body=variant.variant_body,
        variant_cta=variant.variant_cta,
        personalization_notes=variant.personalization_notes,
        review_status=variant.review_status,
        review_notes=variant.review_notes,
        reviewed_by=variant.reviewed_by,
        reviewed_at=variant.reviewed_at,
        assessment_id=variant.assessment_id,
        content_version_hash=variant.content_version_hash,
        created_by=variant.created_by,
        created_at=variant.created_at,
        updated_at=variant.updated_at,
    )


def delete_content_variant(
    db: Session,
    variant_id: int,
    current_user: User,
) -> None:
    """Deletes a content variant if authorized."""
    variant = db.get(ContentVariant, variant_id)
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content variant #{variant_id} not found.",
        )

    # Multi-tenant boundary check
    user_role = current_user.role.name if current_user.role else "Viewer"
    is_admin = (user_role == "Admin")
    user_org = getattr(current_user, "organization", None)

    asset_org = None
    if variant.campaign and variant.campaign.creator:
        asset_org = getattr(variant.campaign.creator, "organization", None)
    elif variant.creator:
        asset_org = getattr(variant.creator, "organization", None)

    if not is_admin and user_org and asset_org and user_org != asset_org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Content variant belongs to another organization.",
        )

    # Cannot delete if creator doesn't match and not admin
    if not is_admin and variant.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete content variants authored by other officers.",
        )

    db.delete(variant)
    db.commit()


def preview_recipient_message(
    db: Session,
    asset_id: int,
    payload: RecipientPreviewRequest,
    current_user: User,
) -> RecipientPreviewResponse:
    """
    Simulates how an individual recipient views their personalized copy.
    Resolves matching segment variant, preferred language, and dynamic placeholders.
    """
    asset = db.get(ContentAsset, asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content asset #{asset_id} not found.",
        )

    member = db.get(AudienceMember, payload.recipient_id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audience member #{payload.recipient_id} not found.",
        )

    # Multi-tenant boundary check
    user_role = current_user.role.name if current_user.role else "Viewer"
    is_admin = (user_role == "Admin")
    user_org = getattr(current_user, "organization", None)

    member_creator = getattr(member, "creator", None)
    member_org = getattr(member_creator, "organization", None) if member_creator else None
    if not is_admin and user_org and member_org and user_org != member_org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Audience member belongs to another organization.",
        )

    effective_channel = payload.channel or asset.channel or "Email"
    effective_lang = payload.preferred_language or member.preferred_language or asset.source_language or "en"

    # Match recipient to segment dynamically using compiled filter rules
    matched_segment = None
    if asset.campaign and asset.campaign.segments:
        from app.schemas.segment import RuleGroup
        from app.services.segment_service import compile_rule_group
        for seg in asset.campaign.segments:
            if seg.filter_rules:
                try:
                    rule_grp = RuleGroup.model_validate(seg.filter_rules)
                    expr = compile_rule_group(rule_grp)
                    is_match = db.execute(
                        select(AudienceMember.id).where(
                            AudienceMember.id == member.id,
                            expr,
                        )
                    ).scalar_one_or_none()
                    if is_match:
                        matched_segment = seg
                        break
                except Exception:
                    pass
            else:
                matched_segment = seg
                break

    # Look for matching approved content variant
    from app.services.quality_service import validate_variant_dispatch_eligibility
    variant = None
    is_fallback = False

    if matched_segment:
        # 1. Match target language variant for channel and segment
        v_stmt = select(ContentVariant).where(
            ContentVariant.source_content_id == asset.id,
            ContentVariant.segment_id == matched_segment.id,
            ContentVariant.review_status == "Approved",
            func.lower(ContentVariant.channel) == effective_channel.lower(),
            func.lower(ContentVariant.language) == effective_lang.lower(),
        )
        cand = db.execute(v_stmt).scalar_one_or_none()
        if cand:
            is_valid, _, _ = validate_variant_dispatch_eligibility(db, cand)
            if is_valid:
                variant = cand

        # 2. Fallback to English variant for same segment if preferred language not available
        if not variant and effective_lang.lower() != "en":
            v_stmt_en = select(ContentVariant).where(
                ContentVariant.source_content_id == asset.id,
                ContentVariant.segment_id == matched_segment.id,
                ContentVariant.review_status == "Approved",
                func.lower(ContentVariant.channel) == effective_channel.lower(),
                func.lower(ContentVariant.language) == "en",
            )
            cand_en = db.execute(v_stmt_en).scalar_one_or_none()
            if cand_en:
                is_valid, _, _ = validate_variant_dispatch_eligibility(db, cand_en)
                if is_valid:
                    variant = cand_en
                    is_fallback = True

    if variant:
        raw_title = variant.variant_title
        raw_body = variant.variant_body
        raw_cta = variant.variant_cta
        used_variant_id = variant.id
        seg_id = variant.segment_id
        seg_name = variant.segment.name if variant.segment else None
    else:
        # Fallback to master asset
        raw_title = asset.title
        raw_body = asset.body
        raw_cta = asset.call_to_action
        used_variant_id = None
        seg_id = None
        seg_name = None
        is_fallback = True

    # Render personalized placeholders
    rendered_title = render_personalized_content(raw_title, member)
    rendered_body = render_personalized_content(raw_body, member)
    rendered_cta = render_personalized_content(raw_cta, member) if raw_cta else None

    # Track substituted values
    sub_map: Dict[str, str] = {}
    member_display_name = getattr(member, "name", None) or getattr(member, "full_name", None) or "Citizen"
    if "{name}" in (raw_title + raw_body):
        sub_map["{name}"] = member_display_name
    if "{city}" in (raw_title + raw_body):
        sub_map["{city}"] = member.city or "your area"

    # Address
    address = member.email if effective_channel == "Email" else (member.phone or "Unknown")

    return RecipientPreviewResponse(
        recipient_id=member.id,
        recipient_name=member_display_name,
        recipient_address=address,
        matched_segment_id=seg_id,
        matched_segment_name=seg_name,
        used_variant_id=used_variant_id,
        is_fallback=is_fallback,
        channel=effective_channel,
        language=effective_lang,
        preview_title=rendered_title,
        preview_body=rendered_body,
        preview_cta=rendered_cta,
        substituted_placeholders=sub_map,
        is_simulation=True,
    )
