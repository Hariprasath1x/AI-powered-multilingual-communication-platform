"""Service orchestrating campaign message distribution, content variant selection, and consent enforcement."""

from __future__ import annotations
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_

from app.models.user import User
from app.models.campaign import Campaign
from app.models.audience import AudienceMember
from app.models.communication import Message, DeliveryLog
from app.models.content_asset import ContentAsset
from app.models.content_variant import ContentVariant
from app.models.channel_config import ChannelConfiguration
from app.models.device_token import DeviceToken
from app.models.web_broadcast import WebBroadcast
from app.schemas.channel_config import (
    CampaignSendRequest,
    CampaignSendSummaryResponse,
    ChannelDeliverySummary,
    MessageSummary,
)
from app.services.channels import get_configured_channel, BaseChannel
from app.services.distribution.recipient_resolver import resolve_campaign_recipients
from app.services.distribution.job_service import (
    resolve_campaign_content_assets,
    resolve_recipient_content_variant,
    render_personalized_content,
    normalize_language_code,
)
from app.services.distribution.base import mask_recipient_address

logger = logging.getLogger("masscommai.campaign_sending_service")


async def send_campaign(
    db: Session,
    campaign_id: int,
    request: Optional[CampaignSendRequest],
    current_user: User,
) -> CampaignSendSummaryResponse:
    """
    Executes end-to-end distribution for an approved campaign:
    1. Verifies campaign existence and 'Approved' lifecycle status.
    2. Resolves targeted audience members across all attached segments.
    3. Identifies preferred channel per recipient.
    4. Selects approved language & demographic segment variants.
    5. Strictly validates affirmative recipient consent (rejecting opted-out/unconfirmed).
    6. Dispatches via EmailChannel or SMSChannel adapter.
    7. Persists individual Message tracking records and status transitions.
    8. Returns structured delivery summary.
    """
    # 1. Verify campaign exists
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    campaign = db.execute(stmt).scalar_one_or_none()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign with ID {campaign_id} does not exist.",
        )

    # Tenant isolation guard: non-superadmins must belong to the campaign's creator organization
    if not getattr(current_user, "is_superuser", False) and current_user.role != "Admin":
        if getattr(campaign.creator, "organization_id", None) != getattr(current_user, "organization_id", None):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot distribute campaigns belonging to another organization.",
            )

    # 2. Verify campaign approval status
    if campaign.status != "Approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Campaign #{campaign_id} ('{campaign.name}') cannot be launched. "
                f"Only campaigns with review status 'Approved' are permitted for broadcast. "
                f"Current status: '{campaign.status}'."
            ),
        )

    # Determine targeted channels
    allowed_channels: List[str] = []
    if request and request.channels:
        allowed_channels = [c.strip() for c in request.channels if c.strip()]
    elif campaign.channels and isinstance(campaign.channels, list):
        allowed_channels = [str(c).strip() for c in campaign.channels if str(c).strip()]
    if not allowed_channels:
        allowed_channels = ["Email", "SMS"]

    # Mark campaign as Running during dispatch
    campaign.status = "Running"
    db.commit()

    # Pre-fetch channel configs
    cfg_stmt = select(ChannelConfiguration)
    configs = {c.channel: c for c in db.execute(cfg_stmt).scalars().all()}

    # 3. Resolve audience members
    # Gather audience members matching any attached campaign segment
    target_members: List[AudienceMember] = []
    seen_member_ids = set()

    for seg in campaign.segments:
        # Resolve all eligible and ineligible members for segment
        eligible, ineligible = resolve_campaign_recipients(db, campaign, allowed_channels[0])
        for rec in eligible + ineligible:
            if rec.audience_member_id not in seen_member_ids:
                seen_member_ids.add(rec.audience_member_id)
                m = db.get(AudienceMember, rec.audience_member_id)
                if m:
                    target_members.append(m)

    # Fallback: if campaign has no segments attached, query all audience members in the org/system
    if not target_members:
        members_stmt = select(AudienceMember).order_by(AudienceMember.id.asc()).limit(100)
        target_members = list(db.execute(members_stmt).scalars().all())

    # Pre-fetch approved content assets and segment variants by channel
    channel_content_cache: Dict[str, Tuple[Optional[ContentAsset], Dict[str, ContentAsset]]] = {}
    channel_variant_cache: Dict[str, Dict[Tuple[int, str], ContentVariant]] = {}

    # Pre-fetch all approved content assets and segment variants by channel
    campaign_asset_ids = [ca.id for ca in campaign.content_assets if ca.id is not None]
    ca_filters = [ContentAsset.campaign_id == campaign.id]
    if campaign_asset_ids:
        ca_filters.append(ContentAsset.parent_id.in_(campaign_asset_ids))

    ca_stmt = select(ContentAsset).where(
        or_(*ca_filters),
        ContentAsset.review_status == "Approved",
    )
    all_approved_assets = list(db.execute(ca_stmt).scalars().all())

    for ch in ["Email", "SMS", "WhatsApp", "Voice", "Web"]:
        ch_lower = ch.lower().strip()
        ch_assets = [a for a in all_approved_assets if a.channel and a.channel.lower().strip() == ch_lower]
        root_ca = next((a for a in ch_assets if a.parent_id is None), ch_assets[0] if ch_assets else None)
        lang_variants: Dict[str, ContentAsset] = {}
        for a in ch_assets:
            if a.target_language:
                lang_variants[normalize_language_code(a.target_language)] = a
            if a.source_language:
                lang_variants.setdefault(normalize_language_code(a.source_language), a)
        if root_ca and "en" not in lang_variants:
            lang_variants["en"] = root_ca

        channel_content_cache[ch] = (root_ca, lang_variants)

        # Pre-fetch approved ContentVariants for segment personalization
        v_stmt = select(ContentVariant).where(
            ContentVariant.campaign_id == campaign.id,
            func.lower(ContentVariant.channel) == ch_lower,
            ContentVariant.review_status == "Approved",
        )
        variants = db.execute(v_stmt).scalars().all()
        v_dict = {}
        for v in variants:
            if v.segment_id is not None:
                v_dict[(v.segment_id, normalize_language_code(v.language))] = v
        channel_variant_cache[ch] = v_dict

    # Configure fallback sequence
    user_fallback = request.fallback_order if (request and request.fallback_order) else None

    if user_fallback:
        configured_fallback = [ch for ch in user_fallback if ch in allowed_channels]
        for ch in allowed_channels:
            if ch not in configured_fallback and ch != "Web":
                configured_fallback.append(ch)
        enable_fallback = request.enable_fallback if (request and request.enable_fallback is not None) else True
    else:
        configured_fallback = []
        enable_fallback = False

    total_recipients = len(target_members)
    eligible_count = 0
    opted_out_count = 0
    sent_count = 0
    delivered_count = 0
    failed_count = 0

    channel_stats: Dict[str, ChannelDeliverySummary] = {
        "Email": ChannelDeliverySummary(),
        "SMS": ChannelDeliverySummary(),
        "WhatsApp": ChannelDeliverySummary(),
        "Push": ChannelDeliverySummary(),
    }
    for ch in allowed_channels:
        if ch not in channel_stats:
            channel_stats[ch] = ChannelDeliverySummary()

    message_summaries: List[MessageSummary] = []

    # Iterate over each intended recipient
    for member in target_members:
        tracking_id = f"trk_{uuid.uuid4().hex}"
        recipient_lang = normalize_language_code(member.preferred_language or "en")

        # 5. Check recipient consent and opt-out status (Mandatory Compliance Check)
        if member.consent_status is not True:
            opted_out_count += 1
            failed_count += 1
            fallback_primary = member.preferred_channel if member.preferred_channel in allowed_channels else (configured_fallback[0] if configured_fallback else allowed_channels[0])
            ch_stat = channel_stats.setdefault(fallback_primary, ChannelDeliverySummary())
            ch_stat.total += 1
            ch_stat.failed += 1
            reason = "Recipient has explicitly opted out (consent_status=False)." if member.consent_status is False else "Recipient lacks affirmative opt-in consent (consent_status=None)."

            msg = Message(
                tracking_id=tracking_id,
                campaign_id=campaign.id,
                audience_member_id=member.id,
                channel=fallback_primary,
                language=recipient_lang,
                rendered_content=f"[BLOCKED] Delivery withheld: {reason}",
                status="Failed",
                failure_reason=reason,
                fallback_attempts=[{"channel": fallback_primary, "status": "Failed", "reason": reason}],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(msg)
            db.flush()

            message_summaries.append(
                MessageSummary(
                    id=msg.id,
                    tracking_id=tracking_id,
                    recipient_id=member.id,
                    recipient_name=member.name,
                    recipient_address=mask_recipient_address(member.email or member.phone or ""),
                    channel=fallback_primary,
                    language=recipient_lang,
                    status="Failed",
                    failure_reason=reason,
                    fallback_attempts=msg.fallback_attempts or [],
                    created_at=msg.created_at,
                )
            )
            continue

        eligible_count += 1

        # Build candidate channel order for this recipient
        if enable_fallback:
            candidate_channels = []
            if member.preferred_channel and member.preferred_channel in allowed_channels and member.preferred_channel != "Web":
                candidate_channels.append(member.preferred_channel)
            for ch in configured_fallback:
                if ch not in candidate_channels:
                    candidate_channels.append(ch)
            if not candidate_channels:
                non_web = [c for c in allowed_channels if c != "Web"]
                candidate_channels = non_web if non_web else [allowed_channels[0]]
        else:
            if member.preferred_channel and member.preferred_channel in allowed_channels:
                candidate_channels = [member.preferred_channel]
            elif "Email" in allowed_channels and member.email:
                candidate_channels = ["Email"]
            elif "SMS" in allowed_channels and member.phone:
                candidate_channels = ["SMS"]
            else:
                candidate_channels = [allowed_channels[0]]

        attempts: List[Dict[str, Any]] = []
        dispatch_succeeded = False
        last_error: Optional[str] = None
        final_channel: str = candidate_channels[0]
        final_asset_id: Optional[int] = None
        final_variant_id: Optional[int] = None
        final_rendered_body: str = ""
        final_status: str = "Failed"
        final_provider_msg_id: Optional[str] = None

        for cand_ch in candidate_channels:
            final_channel = cand_ch

            # Check if channel is globally enabled in ChannelConfiguration
            ch_cfg = configs.get(cand_ch)
            if ch_cfg and not ch_cfg.is_enabled:
                reason = f"Channel '{cand_ch}' is currently disabled by administrator."
                attempts.append({
                    "channel": cand_ch,
                    "status": "Failed",
                    "reason": reason,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                last_error = reason
                continue

            # Check if recipient has valid contact credentials for cand_ch
            channel_adapter: BaseChannel = get_configured_channel(db, cand_ch)
            is_valid, validation_err = channel_adapter.validate_recipient(member)
            if not is_valid:
                attempts.append({
                    "channel": cand_ch,
                    "status": "Failed",
                    "reason": validation_err or "Invalid or missing recipient contact details",
                    "timestamp": datetime.utcnow().isoformat(),
                })
                last_error = validation_err or "Invalid recipient contact info"
                continue

            # Resolve approved content for cand_ch
            root_ca, lang_variants = channel_content_cache.get(cand_ch, (None, {}))
            seg_variants = channel_variant_cache.get(cand_ch, {})
            first_seg_id = campaign.segments[0].id if campaign.segments else None

            body_tpl, selected_orm, resolved_lang, _ = resolve_recipient_content_variant(
                preferred_language=recipient_lang,
                approved_variants_by_lang=lang_variants,
                root_asset=root_ca,
                fallback_template=campaign.objective or f"Official update regarding {campaign.name}.",
                segment_id=first_seg_id,
                approved_segment_variants=seg_variants,
            )
            rendered_body = render_personalized_content(body_tpl, member)
            subject_line = getattr(selected_orm, "title", None) or getattr(selected_orm, "variant_title", None) or campaign.name
            asset_id = selected_orm.id if isinstance(selected_orm, ContentAsset) else None
            variant_id = selected_orm.id if isinstance(selected_orm, ContentVariant) else None

            final_asset_id = asset_id
            final_variant_id = variant_id
            final_rendered_body = rendered_body

            # Message DTO
            class _MsgDTO:
                pass
            msg_dto = _MsgDTO()
            msg_dto.id = 0
            msg_dto.tracking_id = tracking_id
            msg_dto.rendered_content = rendered_body
            msg_dto.subject = subject_line
            msg_dto.title = subject_line
            msg_dto.language = resolved_lang

            try:
                dispatch_res = await channel_adapter.send(msg_dto, member)
                if dispatch_res.success:
                    dispatch_succeeded = True
                    final_status = dispatch_res.status
                    final_provider_msg_id = dispatch_res.provider_message_id
                    attempts.append({
                        "channel": cand_ch,
                        "status": dispatch_res.status,
                        "provider_message_id": dispatch_res.provider_message_id,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    break
                else:
                    attempts.append({
                        "channel": cand_ch,
                        "status": "Failed",
                        "error_code": dispatch_res.error_code,
                        "reason": dispatch_res.error_message or "Gateway dispatch failure",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    last_error = dispatch_res.error_message or dispatch_res.error_code
                    # Automatic token deactivation for invalid push tokens
                    if cand_ch == "Push" and dispatch_res.error_code == "DEVICE_TOKEN_INVALID":
                        if hasattr(channel_adapter, "_resolve_token"):
                            tok_val = channel_adapter._resolve_token(member)
                            if tok_val:
                                dt_stmt = select(DeviceToken).where(DeviceToken.token == tok_val)
                                dt = db.execute(dt_stmt).scalar_one_or_none()
                                if dt:
                                    dt.is_active = False
            except Exception as exc:
                logger.error("Channel %s dispatch error for member %s: %s", cand_ch, member.id, exc)
                attempts.append({
                    "channel": cand_ch,
                    "status": "Failed",
                    "reason": str(exc),
                    "timestamp": datetime.utcnow().isoformat(),
                })
                last_error = str(exc)

        # Record message outcome and delivery logs
        ch_stat = channel_stats.setdefault(final_channel, ChannelDeliverySummary())
        ch_stat.total += 1
        sent_at_val = datetime.utcnow() if dispatch_succeeded else None
        delivered_at_val = datetime.utcnow() if (dispatch_succeeded and final_status == "Delivered") else None

        if dispatch_succeeded:
            if final_status == "Delivered":
                delivered_count += 1
                ch_stat.delivered += 1
            else:
                sent_count += 1
                ch_stat.sent += 1
        else:
            failed_count += 1
            ch_stat.failed += 1

        msg = Message(
            tracking_id=tracking_id,
            campaign_id=campaign.id,
            audience_member_id=member.id,
            content_asset_id=final_asset_id,
            content_variant_id=final_variant_id,
            channel=final_channel,
            language=recipient_lang,
            rendered_content=final_rendered_body or f"[FAILED] Delivery attempts failed: {last_error}",
            status=final_status if dispatch_succeeded else "Failed",
            provider_message_id=final_provider_msg_id,
            failure_reason=None if dispatch_succeeded else last_error,
            fallback_attempts=attempts,
            sent_at=sent_at_val,
            delivered_at=delivered_at_val,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(msg)
        db.flush()

        for att in attempts:
            d_log = DeliveryLog(
                message_id=msg.id,
                channel=att.get("channel", final_channel),
                status=att.get("status", "Failed"),
                error_message=att.get("reason"),
                retry_count=len(attempts) - 1,
                timestamp=datetime.utcnow(),
            )
            db.add(d_log)

        dest_addr = ""
        if final_channel == "Email":
            dest_addr = member.email or ""
        elif final_channel in ("SMS", "WhatsApp"):
            dest_addr = member.phone or ""
        elif final_channel == "Push":
            dest_addr = getattr(member, "token", None) or getattr(member, "device_token", None) or ""

        message_summaries.append(
            MessageSummary(
                id=msg.id,
                tracking_id=tracking_id,
                recipient_id=member.id,
                recipient_name=member.name,
                recipient_address=mask_recipient_address(dest_addr),
                channel=final_channel,
                language=recipient_lang,
                content_asset_id=final_asset_id,
                content_variant_id=final_variant_id,
                status=msg.status,
                provider_message_id=msg.provider_message_id,
                failure_reason=msg.failure_reason,
                fallback_attempts=attempts,
                sent_at=msg.sent_at,
                delivered_at=msg.delivered_at,
                created_at=msg.created_at,
            )
        )

    # If Web channel is enabled, dispatch public broadcast
    if "Web" in allowed_channels:
        web_adapter = get_configured_channel(db, "Web")
        web_root_ca, _ = channel_content_cache.get("Web", (None, {}))
        web_body = web_root_ca.body if web_root_ca else (campaign.objective or f"Public Notice: {campaign.name}")
        web_title = (web_root_ca.title if web_root_ca else None) or campaign.name

        class _WebMsgDTO:
            pass
        web_msg = _WebMsgDTO()
        web_msg.id = 0
        web_msg.campaign_id = campaign.id
        web_msg.tracking_id = f"bc_trk_{uuid.uuid4().hex[:12]}"
        web_msg.title = web_title
        web_msg.rendered_content = web_body
        web_msg.language = "en"
        web_msg.is_emergency = getattr(campaign, "is_emergency", False)
        web_msg.priority = "urgent" if getattr(campaign, "is_emergency", False) else "normal"

        web_res = await web_adapter.send(web_msg, None)
        clients_count = web_res.metadata.get("connected_clients", 0)

        web_bc = WebBroadcast(
            campaign_id=campaign.id,
            title=web_title,
            body=web_body,
            language="en",
            is_emergency=getattr(campaign, "is_emergency", False),
            priority="urgent" if getattr(campaign, "is_emergency", False) else "normal",
            channels_dispatched=["websocket", "sse", "web"],
            connected_clients_count=clients_count,
            broadcast_at=datetime.utcnow(),
        )
        db.add(web_bc)
        db.flush()

        web_stat = channel_stats.setdefault("Web", ChannelDeliverySummary())
        web_stat.total += 1
        web_stat.delivered += 1
        delivered_count += 1

    # Finalize campaign status
    campaign.status = "Completed" if (sent_count + delivered_count) > 0 or total_recipients == 0 else "Failed"
    db.commit()

    return CampaignSendSummaryResponse(
        campaign_id=campaign.id,
        campaign_name=campaign.name,
        campaign_status=campaign.status,
        total_intended_recipients=total_recipients,
        eligible_recipients=eligible_count,
        opted_out_recipients=opted_out_count,
        sent_messages=sent_count,
        delivered_messages=delivered_count,
        failed_messages=failed_count,
        channel_summary=channel_stats,
        messages=message_summaries,
        execution_timestamp=datetime.utcnow(),
    )


def get_campaign_send_summary(
    db: Session,
    campaign_id: int,
    current_user: User,
) -> CampaignSendSummaryResponse:
    """Retrieves live aggregate sending status and historical messages for a campaign."""
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    stmt = (
        select(Message)
        .where(Message.campaign_id == campaign_id)
        .order_by(Message.id.desc())
    )
    messages = list(db.execute(stmt).scalars().all())

    ch_stats: Dict[str, ChannelDeliverySummary] = {
        "Email": ChannelDeliverySummary(),
        "SMS": ChannelDeliverySummary(),
    }
    sent = 0
    delivered = 0
    failed = 0
    opted_out = 0

    summaries: List[MessageSummary] = []
    for m in messages:
        ch = m.channel or "Email"
        stat = ch_stats.setdefault(ch, ChannelDeliverySummary())
        stat.total += 1

        if m.status == "Delivered":
            delivered += 1
            stat.delivered += 1
        elif m.status == "Sent":
            sent += 1
            stat.sent += 1
        elif m.status == "Failed":
            failed += 1
            stat.failed += 1
            if m.failure_reason and "consent" in m.failure_reason.lower():
                opted_out += 1
        else:
            stat.pending += 1

        summaries.append(
            MessageSummary(
                id=m.id,
                tracking_id=m.tracking_id,
                recipient_id=m.audience_member_id,
                recipient_name=m.audience_member.name if m.audience_member else "Citizen",
                recipient_address=mask_recipient_address(
                    (m.audience_member.email if m.channel == "Email" else m.audience_member.phone)
                    if m.audience_member else ""
                ),
                channel=m.channel,
                language=m.language,
                content_asset_id=m.content_asset_id,
                content_variant_id=m.content_variant_id,
                status=m.status,
                provider_message_id=m.provider_message_id,
                failure_reason=m.failure_reason,
                fallback_attempts=m.fallback_attempts or [],
                sent_at=m.sent_at,
                delivered_at=m.delivered_at,
                created_at=m.created_at,
            )
        )

    return CampaignSendSummaryResponse(
        campaign_id=campaign.id,
        campaign_name=campaign.name,
        campaign_status=campaign.status,
        total_intended_recipients=len(messages),
        eligible_recipients=len(messages) - opted_out,
        opted_out_recipients=opted_out,
        sent_messages=sent,
        delivered_messages=delivered,
        failed_messages=failed,
        channel_summary=ch_stats,
        messages=summaries,
        execution_timestamp=datetime.utcnow(),
    )
