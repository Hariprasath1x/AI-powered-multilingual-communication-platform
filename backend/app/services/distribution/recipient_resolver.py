"""Audience segment resolution, deduplication, and eligibility classification."""

import logging
from typing import List, Tuple
from sqlalchemy import select, or_, distinct
from sqlalchemy.orm import Session
from app.models.campaign import Campaign
from app.models.audience import AudienceMember
from app.schemas.segment import RuleGroup
from app.services.segment_service import compile_rule_group
from app.services.distribution.base import ResolvedRecipient
from app.services.distribution.consent_validator import validate_recipient_consent

logger = logging.getLogger("masscommai.recipient_resolver")


def resolve_campaign_recipients(
    db: Session,
    campaign: Campaign,
    channel: str,
) -> Tuple[List[ResolvedRecipient], List[ResolvedRecipient]]:
    """
    Resolves audience members targeted by all attached segments of a campaign.
    Guarantees:
    1. Cross-segment union: Recipient matching any segment is included.
    2. Recipient deduplication: Each physical audience member is processed at most once.
    3. Consent & contact validation: Classifies into eligible vs ineligible recipients.

    Returns:
        Tuple of (eligible_recipients, ineligible_recipients)
    """
    if not campaign.segments:
        return [], []

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
        return [], []

    # Combine with OR to encompass all members belonging to any attached segment
    combined_filter = or_(*segment_exprs)

    # Fetch unique audience members
    stmt = (
        select(AudienceMember)
        .where(combined_filter)
        .order_by(AudienceMember.id)
    )
    members = db.execute(stmt).scalars().all()

    # Deduplicate in Python to ensure single instance even if joins duplicated rows
    seen_ids = set()
    eligible_list: List[ResolvedRecipient] = []
    ineligible_list: List[ResolvedRecipient] = []

    for member in members:
        if member.id in seen_ids:
            continue
        seen_ids.add(member.id)

        # Resolve channel address
        if channel == "Email":
            address = (member.email or "").strip()
        elif channel in ("SMS", "WhatsApp", "Voice"):
            address = (member.phone or "").strip()
        elif channel == "Web":
            address = (member.email or member.phone or f"citizen_{member.id}").strip()
        else:
            address = ""

        is_valid, reason = validate_recipient_consent(member, channel)

        recipient_dto = ResolvedRecipient(
            audience_member_id=member.id,
            name=member.name,
            preferred_language=member.preferred_language or "en",
            channel=channel,
            address=address,
            consent_status=member.consent_status,
            is_eligible=is_valid,
            ineligibility_reason=reason,
        )

        if is_valid:
            eligible_list.append(recipient_dto)
        else:
            ineligible_list.append(recipient_dto)

    return eligible_list, ineligible_list

