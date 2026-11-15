"""Distribution Job management, readiness evaluation, audience resolution, and delivery record staging."""

import logging
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, desc, func, or_
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app.models.campaign import Campaign
from app.models.template import Template
from app.models.content_asset import ContentAsset
from app.models.audience import AudienceMember
from app.models.user import User
from app.models.distribution import DistributionJob, DeliveryRecord, DeliveryAttempt
from app.services.quality_service import get_editorial_readiness
from app.services.channel_constraints import (
    calculate_channel_metrics,
    WarningSeverity,
    ChannelMetrics,
)
from app.services.distribution.base import (
    JobStatus,
    DeliveryStatus,
    ReadinessCheckResult,
    ResolvedRecipient,
)
from app.services.distribution.recipient_resolver import resolve_campaign_recipients

logger = logging.getLogger("masscommai.job_service")

# Map of supported placeholder tags to AudienceMember attributes
PLACEHOLDER_FIELD_MAP = {
    "{name}": "name",
    "{email}": "email",
    "{phone}": "phone",
    "{city}": "city",
    "{state}": "state",
    "{area}": "area",
    "{preferred_language}": "preferred_language",
    "{occupation}": "occupation",
    "{organization_department}": "organization_department",
}

# Mapping of common language names to ISO 639-1 language codes
LANGUAGE_NAME_TO_CODE = {
    "english": "en",
    "hindi": "hi",
    "tamil": "ta",
    "telugu": "te",
    "kannada": "kn",
    "marathi": "mr",
    "bengali": "bn",
    "gujarati": "gu",
    "malayalam": "ml",
    "punjabi": "pa",
    "urdu": "ur",
}


def normalize_language_code(lang: Optional[str]) -> str:
    """
    Normalizes language codes and names (e.g. 'ta-IN', 'Tamil', 'HI', 'hindi')
    into standardized 2-letter codes ('ta', 'hi', 'en'). Defaults to 'en'.
    """
    if not lang:
        return "en"
    clean = lang.lower().strip()
    if "-" in clean:
        clean = clean.split("-")[0].strip()
    if "_" in clean:
        clean = clean.split("_")[0].strip()
    return LANGUAGE_NAME_TO_CODE.get(clean, clean)


def render_personalized_content(template_text: str, member: AudienceMember) -> str:
    """Replaces dynamic template placeholders with safe recipient attributes."""
    content = template_text
    city_val = member.city.strip() if member.city and member.city.strip() else None
    state_val = member.state.strip() if member.state and member.state.strip() else None
    area_val = city_val or state_val or ""

    for placeholder, attr in PLACEHOLDER_FIELD_MAP.items():
        if placeholder == "{area}":
            val = area_val
        else:
            val = getattr(member, attr, None)
        replacement = str(val) if val is not None else ""
        content = content.replace(placeholder, replacement)
    return content


def resolve_campaign_content_assets(
    db: Session,
    campaign: Campaign,
    channel: str,
) -> Tuple[Optional[ContentAsset], Dict[str, ContentAsset]]:
    """
    Resolves the approved root content asset and all approved translation variants
    for the specified campaign and channel.

    Enforces strict rules:
    1. Channel matching: only assets matching the requested channel (case-insensitive) are eligible.
    2. Approval gate: only assets with review_status == 'Approved' are included.
       Unapproved (Draft, Generated, Needs Review, Rejected) variants are strictly excluded.
    3. Hierarchy: searches both direct campaign content assets and child translation variants
       linked via parent_id.

    Returns:
        Tuple of:
        - root_asset: The approved base ContentAsset for this channel (or fallback)
        - approved_variants_by_lang: Dict mapping normalized language codes (e.g. 'en', 'hi', 'ta')
          to their approved ContentAsset instances.
    """
    channel_clean = channel.lower().strip()

    # 1. Gather all candidate ContentAssets linked to the campaign
    campaign_assets = list(campaign.content_assets or [])
    root_ids = [ca.id for ca in campaign_assets if ca.id is not None]

    # Also query any child variants whose parent is a campaign asset
    candidate_assets: List[ContentAsset] = []
    if root_ids:
        extra_stmt = select(ContentAsset).where(
            or_(
                ContentAsset.campaign_id == campaign.id,
                ContentAsset.parent_id.in_(root_ids),
            )
        ).order_by(ContentAsset.id.asc())
        candidate_assets = list(db.execute(extra_stmt).scalars().all())
    elif campaign.id is not None:
        extra_stmt = select(ContentAsset).where(
            ContentAsset.campaign_id == campaign.id
        ).order_by(ContentAsset.id.asc())
        candidate_assets = list(db.execute(extra_stmt).scalars().all())

    # Merge and deduplicate candidate assets preserving order
    seen_ids = set()
    all_assets: List[ContentAsset] = []
    for asset in candidate_assets + campaign_assets:
        if asset.id not in seen_ids:
            seen_ids.add(asset.id)
            all_assets.append(asset)

    # 2. Filter strictly for this channel
    channel_assets = [
        a for a in all_assets
        if a.channel and a.channel.lower().strip() == channel_clean
    ]

    # 3. Find the approved root asset for this channel
    # Preferred: parent_id IS NULL and review_status == 'Approved' and source_language == 'en' (or target_language is None or 'en')
    root_candidates = [
        a for a in channel_assets
        if a.review_status == "Approved" and a.parent_id is None
    ]
    if not root_candidates:
        root_candidates = [
            a for a in channel_assets
            if a.review_status == "Approved" and (a.target_language is None or normalize_language_code(a.target_language) == "en")
        ]
    if not root_candidates:
        root_candidates = [
            a for a in channel_assets
            if a.review_status == "Approved"
        ]
    if not root_candidates and all_assets:
        root_candidates = [
            a for a in all_assets
            if a.review_status == "Approved"
        ]

    root_asset = root_candidates[0] if root_candidates else None

    # 4. Index approved variants by normalized language code
    # CRITICAL: Only assets with review_status == "Approved" and valid editorial readiness are eligible!
    approved_variants_by_lang: Dict[str, ContentAsset] = {}
    for a in channel_assets:
        if a.review_status != "Approved":
            continue

        # Invariant E: Exclude translation variants lacking a valid quality assessment or with blocking issues
        try:
            readiness = get_editorial_readiness(db, a.id)
            if not readiness.has_assessment or readiness.is_approval_blocked:
                logger.warning(
                    "Variant #%d (%s) is not editorially ready; excluding from distribution staging",
                    a.id,
                    a.target_language,
                )
                continue
        except Exception as exc:
            logger.warning("Error checking readiness for variant #%d: %s; excluding", a.id, exc)
            continue

        if a.target_language:
            lang_key = normalize_language_code(a.target_language)
            approved_variants_by_lang[lang_key] = a
        if a.source_language:
            lang_key = normalize_language_code(a.source_language)
            if lang_key not in approved_variants_by_lang:
                approved_variants_by_lang[lang_key] = a

    # Ensure English mapping points to the approved root asset if available
    if root_asset and "en" not in approved_variants_by_lang:
        approved_variants_by_lang["en"] = root_asset

    return root_asset, approved_variants_by_lang


def resolve_recipient_content_variant(
    preferred_language: Optional[str],
    approved_variants_by_lang: Dict[str, ContentAsset],
    root_asset: Optional[ContentAsset],
    fallback_template: Optional[str] = None,
    segment_id: Optional[int] = None,
    approved_segment_variants: Optional[Dict[Tuple[int, str], Any]] = None,
) -> Tuple[str, Optional[Any], str, bool]:
    """
    Resolves the content body, selected asset/variant, effective language, and fallback flag for a recipient.
    Supports segment-tailored variants (Task 9.A) when available, falling back to language variants (Task 8)
    and root assets (Task 7).

    Returns:
        Tuple of:
        - body_template (str): The body text to personalize
        - selected_asset (Optional[Any]): The selected ContentAsset or ContentVariant ORM instance
        - resolved_language (str): Normalized language code ('en', 'ta', etc.)
        - is_fallback (bool): True if recipient's preferred language did not match an approved variant
    """
    clean_pref = normalize_language_code(preferred_language)

    # 1. Segment-tailored demographic variant match (Task 9.A)
    if segment_id is not None and approved_segment_variants:
        # Check target language segment variant
        if (segment_id, clean_pref) in approved_segment_variants:
            var = approved_segment_variants[(segment_id, clean_pref)]
            return var.variant_body, var, clean_pref, False
        # Check English fallback segment variant
        if (segment_id, "en") in approved_segment_variants:
            var = approved_segment_variants[(segment_id, "en")]
            return var.variant_body, var, "en", (clean_pref != "en")

    # 2. Exact match with approved variant for this language (Task 8)
    if clean_pref in approved_variants_by_lang:
        asset = approved_variants_by_lang[clean_pref]
        return asset.body, asset, clean_pref, False

    # 3. Graceful fallback to root English content (Task 7)
    fallback_asset = approved_variants_by_lang.get("en") or root_asset
    if fallback_asset:
        return fallback_asset.body, fallback_asset, "en", (clean_pref != "en")

    # 4. Graceful fallback to campaign template if no root asset
    return fallback_template or "", None, "en", (clean_pref != "en")


def check_campaign_readiness(
    db: Session,
    campaign_id: int,
    channel: str,
) -> ReadinessCheckResult:
    """
    Evaluates whether a campaign fulfills all server-side safeguards for distribution.
    Checks:
    1. Campaign existence and lifecycle status (must be 'Approved', 'Scheduled', or 'Running').
    2. Target channel support in campaign configuration.
    3. Approved, fresh content or valid template link.
    4. Audience segment attachment and non-empty confirmed consent reach.
    """
    stmt = (
        select(Campaign)
        .options(
            joinedload(Campaign.template),
            joinedload(Campaign.segments),
            joinedload(Campaign.content_assets),
        )
        .where(Campaign.id == campaign_id)
    )
    campaign = db.execute(stmt).unique().scalar_one_or_none()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign with ID {campaign_id} not found.",
        )

    blocking_reasons: List[str] = []
    warnings: List[str] = []

    # 1. Campaign lifecycle status check
    # Eligible states for distribution: Approved, Scheduled, Running
    status_valid = campaign.status in ("Approved", "Scheduled", "Running")
    if not status_valid:
        blocking_reasons.append(
            f"Campaign lifecycle status is '{campaign.status}'. Only campaigns in 'Approved' or 'Scheduled' status can be distributed."
        )

    # 2. Target channel check
    campaign_channels = list(campaign.channels or [])
    channel_supported = channel in campaign_channels
    if not channel_supported:
        supported_str = ", ".join(campaign_channels) if campaign_channels else "None"
        blocking_reasons.append(
            f"Channel '{channel}' is not configured for this campaign. Permitted channels: [{supported_str}]."
        )

    # 3. Content and Template check
    has_template_or_content = False
    content_approved = False
    content_is_outdated = False

    # Check for linked ContentAsset first
    target_asset: Optional[ContentAsset] = None
    root_asset, approved_variants_by_lang = resolve_campaign_content_assets(db, campaign, channel)
    if root_asset:
        target_asset = root_asset
    elif campaign.content_assets:
        # Fall back to channel-matching asset if available, else first attached asset
        for ca in campaign.content_assets:
            if ca.channel.lower() == channel.lower():
                target_asset = ca
                break
        if not target_asset and campaign.content_assets:
            target_asset = campaign.content_assets[0]

    if target_asset:
        has_template_or_content = True
        content_approved = (target_asset.review_status == "Approved")
        if not content_approved:
            blocking_reasons.append(
                f"Associated content asset #{target_asset.id} has review status '{target_asset.review_status}'. Only 'Approved' content can be broadcast."
            )
        try:
            readiness = get_editorial_readiness(db, target_asset.id)
            if not readiness.has_assessment:
                blocking_reasons.append(
                    f"Content asset #{target_asset.id} has no quality assessment. Mandatory quality assessment is required before distribution."
                )
            elif readiness.is_outdated:
                content_is_outdated = True
                blocking_reasons.append(
                    f"Content asset #{target_asset.id} was modified after its quality audit. Re-evaluation required before distribution."
                )
            elif readiness.critical_unresolved_count > 0 or readiness.is_approval_blocked:
                blocking_reasons.append(
                    f"Content asset #{target_asset.id} has {readiness.critical_unresolved_count} unresolved critical compliance findings."
                )
        except Exception as exc:
            logger.error("Could not assess editorial readiness for asset ID %s: %s", target_asset.id, exc)
            blocking_reasons.append(
                f"Content asset #{target_asset.id} quality readiness check failed: {exc}"
            )
    elif campaign.template:
        has_template_or_content = True
        content_approved = True  # Templates approved during creation
    else:
        blocking_reasons.append("Campaign has no linked message template or content asset.")

    # 4. Audience and Consent checks
    if not campaign.segments:
        blocking_reasons.append("Campaign has no attached audience segments.")

    eligible, ineligible = resolve_campaign_recipients(db, campaign, channel)
    total_audience = len(eligible) + len(ineligible)
    eligible_count = len(eligible)

    if total_audience > 0 and eligible_count == 0:
        blocking_reasons.append(
            f"None of the {total_audience} targeted recipients hold confirmed consent and valid contact credentials for {channel}."
        )
    elif total_audience == 0 and campaign.segments:
        blocking_reasons.append("Attached audience segments resolved to zero audience members.")

    # 5. Channel Constraints & Multilingual Audience Evaluation
    valid_recipients_count = 0
    warning_recipients_count = 0
    blocked_recipients_count = 0
    total_estimated_segments = 0 if channel.upper() == "SMS" else None
    max_segments_per_recipient = 0 if channel.upper() == "SMS" else None
    max_duration_seconds = 0 if channel.upper() == "VOICE" else None
    channel_metrics_summary: Optional[Dict[str, Any]] = None
    language_breakdown: Dict[str, Any] = {}

    base_body_text = target_asset.body if target_asset else (campaign.template.body if campaign.template else "")
    base_title_text = target_asset.title if target_asset else (campaign.template.title if campaign.template and campaign.template.title else campaign.name)

    is_template_campaign = bool(campaign.template_id or campaign.template or (target_asset and getattr(target_asset, "operation_type", None) == "template"))

    if has_template_or_content and base_body_text:
        # Pre-check base template against hard limits even before recipient binding
        base_metrics = calculate_channel_metrics(
            channel=channel,
            title=base_title_text,
            body=base_body_text,
            language=target_asset.source_language if target_asset else "en",
            is_template=is_template_campaign,
        )
        if not base_metrics.is_within_hard_limit:
            for w in base_metrics.warnings:
                if w.severity == WarningSeverity.CRITICAL.value:
                    blocking_reasons.append(f"Content template exceeds {channel} hard limit: {w.message}")

    if eligible and has_template_or_content and base_body_text:
        member_ids = [r.audience_member_id for r in eligible]
        member_stmt = select(AudienceMember).where(AudienceMember.id.in_(member_ids))
        members_by_id = {m.id: m for m in db.execute(member_stmt).scalars().all()}

        metrics_cache: Dict[Tuple[str, str, str, str], ChannelMetrics] = {}
        lang_groups: Dict[str, Dict[str, Any]] = {}

        # Stage Task 9.A segment variant lookup
        approved_segment_variants: Dict[Tuple[int, str], Any] = {}
        member_to_segment_id: Dict[int, int] = {}
        try:
            from app.models.content_variant import ContentVariant
            from app.schemas.segment import RuleGroup
            from app.services.segment_service import compile_rule_group
            v_stmt = select(ContentVariant).where(
                ContentVariant.campaign_id == campaign.id,
                ContentVariant.review_status == "Approved",
                func.lower(ContentVariant.channel) == channel.lower(),
            )
            from app.services.quality_service import validate_variant_dispatch_eligibility
            for v in db.execute(v_stmt).scalars().all():
                if v.segment_id is not None:
                    is_valid, err_c, err_m = validate_variant_dispatch_eligibility(db, v)
                    if is_valid:
                        approved_segment_variants[(v.segment_id, normalize_language_code(v.language))] = v
                    else:
                        logger.warning(
                            "Variant #%d (%s) excluded from readiness staging: %s (%s)",
                            v.id,
                            v.variant_title,
                            err_c,
                            err_m,
                        )

            if approved_segment_variants and campaign.segments:
                for seg in campaign.segments:
                    if seg.filter_rules:
                        rule_grp = RuleGroup.model_validate(seg.filter_rules)
                        compiled = compile_rule_group(rule_grp)
                        matching_ids = db.execute(
                            select(AudienceMember.id).where(
                                AudienceMember.id.in_(member_ids),
                                compiled,
                            )
                        ).scalars().all()
                        for mid in matching_ids:
                            if mid not in member_to_segment_id:
                                member_to_segment_id[mid] = seg.id
        except Exception as exc:
            logger.debug("Segment variant preflight lookup bypassed: %s", exc)

        for rec in eligible:
            member = members_by_id.get(rec.audience_member_id)
            pref_lang = rec.preferred_language or (member.preferred_language if member else None)

            seg_id = member_to_segment_id.get(rec.audience_member_id) if member_to_segment_id else None
            body_template, selected_asset, resolved_lang, is_fallback = resolve_recipient_content_variant(
                preferred_language=pref_lang,
                approved_variants_by_lang=approved_variants_by_lang,
                root_asset=root_asset,
                fallback_template=base_body_text,
                segment_id=seg_id,
                approved_segment_variants=approved_segment_variants,
            )

            if selected_asset:
                title_template = (
                    getattr(selected_asset, "variant_title", None)
                    or getattr(selected_asset, "title", None)
                    or base_title_text
                )
            else:
                title_template = base_title_text
            rendered_body = render_personalized_content(body_template, member) if member else body_template
            rendered_title = render_personalized_content(title_template, member) if member else title_template

            cache_key = (channel, rendered_title, rendered_body, resolved_lang, is_template_campaign)
            if cache_key not in metrics_cache:
                metrics_cache[cache_key] = calculate_channel_metrics(
                    channel=channel,
                    title=rendered_title,
                    body=rendered_body,
                    language=resolved_lang,
                    is_template=is_template_campaign,
                )
            c_metrics = metrics_cache[cache_key]

            if resolved_lang not in lang_groups:
                lang_groups[resolved_lang] = {
                    "language": resolved_lang,
                    "recipient_count": 0,
                    "fallback_count": 0,
                    "character_count": c_metrics.character_count,
                    "word_count": c_metrics.word_count,
                    "encoding": c_metrics.sms.encoding if c_metrics.sms else None,
                    "segment_count": c_metrics.sms.segment_count if c_metrics.sms else None,
                    "total_segments": 0 if c_metrics.sms else None,
                    "max_segments": c_metrics.sms.segment_count if c_metrics.sms else None,
                    "estimated_duration_seconds": c_metrics.estimated_duration_seconds,
                    "max_duration_seconds": c_metrics.estimated_duration_seconds or 0,
                    "is_within_hard_limit": True,
                    "is_within_recommended_limit": True,
                    "warnings": [],
                }

            grp = lang_groups[resolved_lang]
            grp["recipient_count"] += 1
            if is_fallback:
                grp["fallback_count"] += 1

            if c_metrics.sms:
                seg_cnt = c_metrics.sms.segment_count
                grp["total_segments"] = (grp["total_segments"] or 0) + seg_cnt
                if seg_cnt > (grp["max_segments"] or 0):
                    grp["max_segments"] = seg_cnt
                    grp["character_count"] = c_metrics.character_count
                    grp["encoding"] = c_metrics.sms.encoding
                if seg_cnt > (max_segments_per_recipient or 0):
                    max_segments_per_recipient = seg_cnt
                total_estimated_segments = (total_estimated_segments or 0) + seg_cnt

            if c_metrics.estimated_duration_seconds:
                dur = c_metrics.estimated_duration_seconds
                if dur > (grp["max_duration_seconds"] or 0):
                    grp["max_duration_seconds"] = dur
                if dur > (max_duration_seconds or 0):
                    max_duration_seconds = dur

            if not c_metrics.is_within_hard_limit:
                blocked_recipients_count += 1
                grp["is_within_hard_limit"] = False
                for w in c_metrics.warnings:
                    if w.severity == WarningSeverity.CRITICAL.value:
                        crit_msg = f"[{resolved_lang.upper()}] Content exceeds channel hard limit: {w.message}"
                        if crit_msg not in grp["warnings"]:
                            grp["warnings"].append(crit_msg)
            elif not c_metrics.is_within_recommended_limit:
                warning_recipients_count += 1
                grp["is_within_recommended_limit"] = False
                for w in c_metrics.warnings:
                    if w.severity in (WarningSeverity.HIGH.value, WarningSeverity.MEDIUM.value, WarningSeverity.LOW.value):
                        msg = f"[{resolved_lang.upper()}] {w.message}"
                        if msg not in warnings:
                            warnings.append(msg)
            else:
                valid_recipients_count += 1
                for w in c_metrics.warnings:
                    if w.severity == WarningSeverity.INFO.value:
                        msg = f"[{resolved_lang.upper()}] {w.message}"
                        if msg not in warnings:
                            warnings.append(msg)

        # If all eligible recipients breach hard limits, block readiness completely.
        # If a subset breaches hard limits due to personalization but valid recipients exist,
        # surface as warnings so valid recipients can still be dispatched (invalid staged as FAILED).
        dispatchable_recipients_count = valid_recipients_count + warning_recipients_count
        for lang_code, grp in lang_groups.items():
            for crit_msg in grp.get("warnings", []):
                if dispatchable_recipients_count == 0 and blocked_recipients_count > 0:
                    if crit_msg not in blocking_reasons:
                        blocking_reasons.append(crit_msg)
                else:
                    warn_msg = f"{crit_msg} (Affected recipients will be excluded during job staging)"
                    if warn_msg not in warnings:
                        warnings.append(warn_msg)

        language_breakdown = lang_groups

        if metrics_cache:
            first_m = next(iter(metrics_cache.values())).to_dict()
            if channel.upper() == "SMS":
                first_m["total_estimated_segments"] = total_estimated_segments
                first_m["max_segments_per_recipient"] = max_segments_per_recipient
            elif channel.upper() == "VOICE":
                first_m["estimated_duration_seconds"] = max_duration_seconds
            channel_metrics_summary = first_m

    is_ready = len(blocking_reasons) == 0

    return ReadinessCheckResult(
        is_ready=is_ready,
        campaign_id=campaign.id,
        campaign_status=campaign.status,
        campaign_status_valid=status_valid,
        channel=channel,
        channel_supported=channel_supported,
        has_template_or_content=has_template_or_content,
        content_approved=content_approved,
        content_is_outdated=content_is_outdated,
        total_target_audience=total_audience,
        confirmed_consent_audience=eligible_count,
        eligible_recipients_count=eligible_count,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        valid_recipients_count=valid_recipients_count,
        warning_recipients_count=warning_recipients_count,
        blocked_recipients_count=blocked_recipients_count,
        total_estimated_segments=total_estimated_segments,
        max_segments_per_recipient=max_segments_per_recipient,
        estimated_duration_seconds=max_duration_seconds,
        channel_metrics=channel_metrics_summary,
        language_breakdown=language_breakdown,
    )


def create_distribution_job(
    db: Session,
    campaign_id: int,
    channel: str,
    current_user: User,
) -> DistributionJob:
    """
    Creates a persistent DistributionJob and stages individual DeliveryRecords for all eligible recipients.
    Enforces RBAC, campaign readiness, consent eligibility, and at-most-once delivery constraints.
    """
    stmt = (
        select(Campaign)
        .options(
            joinedload(Campaign.template),
            joinedload(Campaign.segments),
            joinedload(Campaign.content_assets),
        )
        .where(Campaign.id == campaign_id)
    )
    campaign = db.execute(stmt).unique().scalar_one_or_none()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign with ID {campaign_id} not found.",
        )

    # Ownership check: Admin or Campaign Creator
    is_admin = current_user.role and current_user.role.name == "Admin"
    if not is_admin and campaign.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to distribute campaigns created by other users.",
        )

    # Validate readiness
    readiness = check_campaign_readiness(db, campaign_id, channel)
    if not readiness.is_ready:
        reasons_str = "; ".join(readiness.blocking_reasons)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot create distribution job: {reasons_str}",
        )

    # Prevent concurrent duplicate job creation for the same campaign and channel
    active_job_stmt = select(DistributionJob).where(
        DistributionJob.campaign_id == campaign.id,
        DistributionJob.channel == channel,
        DistributionJob.status.in_([JobStatus.QUEUED.value, JobStatus.PROCESSING.value]),
    )
    active_job = db.execute(active_job_stmt).scalar_one_or_none()
    if active_job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An active distribution job #{active_job.job_id} is already '{active_job.status}' for channel '{channel}'. Wait for completion or cancel it before dispatching again.",
        )

    # Resolve eligible audience members
    eligible_recipients, ineligible_recipients = resolve_campaign_recipients(db, campaign, channel)
    if not eligible_recipients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No eligible recipients found for channel '{channel}'. Affirmative consent and valid contact address are required.",
        )

    # Determine base content copy and multilingual translation variants
    root_asset, approved_variants_by_lang = resolve_campaign_content_assets(db, campaign, channel)
    content_asset_id: Optional[int] = root_asset.id if root_asset else None
    template_id: Optional[int] = campaign.template_id
    base_body: str = root_asset.body if root_asset else ""
    base_title: str = root_asset.title if root_asset else campaign.name

    if not base_body and campaign.template:
        base_body = campaign.template.body
        base_title = campaign.template.title or campaign.name

    # Create DistributionJob entity
    job = DistributionJob(
        campaign_id=campaign.id,
        content_asset_id=content_asset_id,
        template_id=template_id,
        channel=channel,
        status=JobStatus.QUEUED.value,
        total_recipients=len(eligible_recipients) + len(ineligible_recipients),
        eligible_recipients=len(eligible_recipients),
        queued_recipients=len(eligible_recipients),
        created_by=current_user.id,
    )
    db.add(job)
    db.flush()  # Generate job.id

    # Fetch physical AudienceMember instances for personalized substitution
    member_ids = [r.audience_member_id for r in eligible_recipients]
    member_stmt = select(AudienceMember).where(AudienceMember.id.in_(member_ids))
    members_by_id = {m.id: m for m in db.execute(member_stmt).scalars().all()}

    # Stage DeliveryRecord for each eligible recipient
    delivery_records: List[DeliveryRecord] = []
    blocked_records: List[DeliveryRecord] = []

    # Task 9.A segment variant lookup
    approved_segment_variants: Dict[Tuple[int, str], Any] = {}
    member_to_segment_id: Dict[int, int] = {}
    try:
        from app.models.content_variant import ContentVariant
        from app.schemas.segment import RuleGroup
        from app.services.segment_service import compile_rule_group
        v_stmt = select(ContentVariant).where(
            ContentVariant.campaign_id == campaign.id,
            ContentVariant.review_status == "Approved",
            func.lower(ContentVariant.channel) == channel.lower(),
        )
        from app.services.quality_service import validate_variant_dispatch_eligibility
        for v in db.execute(v_stmt).scalars().all():
            if v.segment_id is not None:
                is_valid, err_c, err_m = validate_variant_dispatch_eligibility(db, v)
                if is_valid:
                    approved_segment_variants[(v.segment_id, normalize_language_code(v.language))] = v
                else:
                    logger.warning(
                        "Variant #%d (%s) excluded from job dispatch staging: %s (%s)",
                        v.id,
                        v.variant_title,
                        err_c,
                        err_m,
                    )

        if approved_segment_variants and campaign.segments:
            for seg in campaign.segments:
                if seg.filter_rules:
                    rule_grp = RuleGroup.model_validate(seg.filter_rules)
                    compiled = compile_rule_group(rule_grp)
                    matching_ids = db.execute(
                        select(AudienceMember.id).where(
                            AudienceMember.id.in_(member_ids),
                            compiled,
                        )
                    ).scalars().all()
                    for mid in matching_ids:
                        if mid not in member_to_segment_id:
                            member_to_segment_id[mid] = seg.id
    except Exception as exc:
        logger.debug("Segment variant job staging lookup bypassed: %s", exc)

    for rec in eligible_recipients:
        member = members_by_id.get(rec.audience_member_id)
        if not member:
            continue

        pref_lang = rec.preferred_language or (member.preferred_language if member else None)
        seg_id = member_to_segment_id.get(rec.audience_member_id) if member_to_segment_id else None
        body_template, selected_asset, resolved_lang, is_fallback = resolve_recipient_content_variant(
            preferred_language=pref_lang,
            approved_variants_by_lang=approved_variants_by_lang,
            root_asset=root_asset,
            fallback_template=base_body,
            segment_id=seg_id,
            approved_segment_variants=approved_segment_variants,
        )

        rendered_body = render_personalized_content(body_template, member)
        if selected_asset:
            title_template = (
                getattr(selected_asset, "variant_title", None)
                or getattr(selected_asset, "title", None)
                or base_title
            )
        else:
            title_template = base_title
        rendered_title = render_personalized_content(title_template, member)

        idempotency_key = f"{job.id}:{member.id}:{channel}"

        # Phase C: Validate exact personalized content against channel constraints
        metrics = calculate_channel_metrics(
            channel=channel,
            title=rendered_title,
            body=rendered_body,
            language=resolved_lang,
            is_template=bool(campaign.template_id or campaign.template or (selected_asset and getattr(selected_asset, "operation_type", None) == "template")),
        )

        if not metrics.is_within_hard_limit:
            err_msg = "; ".join(w.message for w in metrics.warnings if w.severity == WarningSeverity.CRITICAL.value)
            if not err_msg:
                err_msg = f"Personalized content exceeds {channel} technical hard limit."

            logger.warning(
                "Recipient ID %s excluded from queued dispatch: %s",
                member.id,
                err_msg,
            )
            rec_blocked = DeliveryRecord(
                job_id=job.id,
                audience_member_id=member.id,
                channel=channel,
                recipient_address=rec.address,
                rendered_content=rendered_body,
                delivery_status=DeliveryStatus.FAILED.value,
                error_code="PAYLOAD_EXCEEDS_CHANNEL_HARD_LIMIT",
                error_message=err_msg,
                idempotency_key=idempotency_key,
            )
            blocked_records.append(rec_blocked)
        else:
            record = DeliveryRecord(
                job_id=job.id,
                audience_member_id=member.id,
                channel=channel,
                recipient_address=rec.address,
                rendered_content=rendered_body,
                delivery_status=DeliveryStatus.PENDING.value,
                idempotency_key=idempotency_key,
            )
            delivery_records.append(record)

    all_staged = delivery_records + blocked_records
    if not all_staged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No delivery records could be staged for this job.",
        )

    # Maintain consistent job aggregate counters
    job.queued_recipients = len(delivery_records)
    job.failed_recipients = len(blocked_records)
    if not delivery_records and blocked_records:
        job.status = JobStatus.FAILED.value
        job.error_summary = f"All {len(blocked_records)} eligible recipient(s) exceeded channel hard limits."
    elif blocked_records:
        job.error_summary = f"{len(blocked_records)} recipient(s) excluded due to channel hard limit violations."

    db.add_all(all_staged)
    db.commit()
    db.refresh(job)

    logger.info(
        "Created DistributionJob ID %s (UUID: %s) for Campaign %s across channel %s with %s queued recipients.",
        job.id,
        job.job_id,
        campaign.id,
        channel,
        len(delivery_records),
    )
    return job


def get_distribution_job_by_uuid(db: Session, job_uuid: str, current_user: User) -> DistributionJob:
    """Retrieves distribution job by UUID string with permission check."""
    stmt = (
        select(DistributionJob)
        .options(
            joinedload(DistributionJob.campaign),
            joinedload(DistributionJob.creator),
        )
        .where(DistributionJob.job_id == job_uuid)
    )
    job = db.execute(stmt).unique().scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Distribution job with ID '{job_uuid}' not found.",
        )

    is_admin = current_user.role and current_user.role.name == "Admin"
    if not is_admin and job.created_by != current_user.id and job.campaign.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this distribution job.",
        )
    return job


def list_distribution_jobs(
    db: Session,
    page: int = 1,
    size: int = 10,
    campaign_id: Optional[int] = None,
    channel: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: Optional[User] = None,
) -> Tuple[List[DistributionJob], int]:
    """Lists distribution jobs with filtering, pagination, and ownership isolation."""
    query = select(DistributionJob).options(
        joinedload(DistributionJob.campaign),
        joinedload(DistributionJob.creator),
    )

    if campaign_id:
        query = query.where(DistributionJob.campaign_id == campaign_id)
    if channel:
        query = query.where(DistributionJob.channel == channel)
    if status_filter:
        query = query.where(DistributionJob.status == status_filter)

    # Ownership filtering for Campaign Managers
    if current_user and current_user.role and current_user.role.name == "Campaign Manager":
        query = query.where(DistributionJob.created_by == current_user.id)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    query = query.order_by(desc(DistributionJob.created_at)).offset((page - 1) * size).limit(size)
    jobs = db.execute(query).unique().scalars().all()

    return list(jobs), total


def list_job_delivery_records(
    db: Session,
    job_uuid: str,
    page: int = 1,
    size: int = 20,
    delivery_status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: Optional[User] = None,
) -> Tuple[List[DeliveryRecord], int]:
    """Retrieves recipient delivery records for a job with filtering and pagination."""
    job = get_distribution_job_by_uuid(db, job_uuid, current_user)

    query = (
        select(DeliveryRecord)
        .options(
            joinedload(DeliveryRecord.audience_member),
            joinedload(DeliveryRecord.attempts),
        )
        .where(DeliveryRecord.job_id == job.id)
    )

    if delivery_status:
        query = query.where(DeliveryRecord.delivery_status == delivery_status)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                DeliveryRecord.recipient_address.ilike(term),
                DeliveryRecord.rendered_content.ilike(term),
            )
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    query = query.order_by(DeliveryRecord.id).offset((page - 1) * size).limit(size)
    records = db.execute(query).unique().scalars().all()

    return list(records), total


def cancel_distribution_job(db: Session, job_uuid: str, current_user: User) -> DistributionJob:
    """Cancels a pending or queued distribution job."""
    job = get_distribution_job_by_uuid(db, job_uuid, current_user)

    if job.status in (JobStatus.COMPLETED.value, JobStatus.COMPLETED_WITH_ERRORS.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a completed distribution job.",
        )
    if job.status == JobStatus.CANCELLED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Distribution job is already cancelled.",
        )
    if job.status == JobStatus.FAILED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a failed distribution job.",
        )

    # Cancel only pending or retrying records
    pending_records_stmt = (
        select(DeliveryRecord)
        .where(
            DeliveryRecord.job_id == job.id,
            DeliveryRecord.delivery_status.in_([DeliveryStatus.PENDING.value, DeliveryStatus.RETRYING.value]),
        )
    )
    pending_records = db.execute(pending_records_stmt).scalars().all()
    for rec in pending_records:
        rec.delivery_status = DeliveryStatus.CANCELLED.value

    job.status = JobStatus.CANCELLED.value
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job

