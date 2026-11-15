"""Consent eligibility validation and Just-In-Time (JIT) consent re-verification."""

import re
import logging
from typing import Tuple, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.audience import AudienceMember

logger = logging.getLogger("masscommai.consent_validator")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_REGEX = re.compile(r"^\+?[0-9]{10,15}$")


def validate_recipient_consent(member: AudienceMember, channel: str) -> Tuple[bool, Optional[str]]:
    """
    Validates whether an audience member holds affirmative consent and
    valid contact credentials for the target channel.

    Enforces tri-state consent rules:
    - consent_status IS TRUE: Valid consent granted.
    - consent_status IS FALSE: Explicitly revoked / opted out.
    - consent_status IS NONE: Unconfirmed / omitted consent. Never assumed as True.
    """
    if member.consent_status is False:
        return False, "Recipient has explicitly opted out of communications (consent_status=False)."

    if member.consent_status is None:
        return False, "Recipient has unconfirmed consent (consent_status=None). Affirmative opt-in required."

    if member.consent_status is not True:
        return False, "Recipient lacks affirmative consent."

    # Validate destination address presence based on requested communication channel
    if channel == "Email":
        if not member.email or not EMAIL_REGEX.match(member.email.strip()):
            return False, f"Missing or invalid email address for Email delivery: '{member.email}'."
    elif channel in ("SMS", "WhatsApp", "Voice"):
        if not member.phone:
            return False, f"Missing phone number for {channel} delivery."
        clean_phone = member.phone.strip().replace(" ", "").replace("-", "")
        if not PHONE_REGEX.match(clean_phone):
            return False, f"Invalid phone number format for {channel} delivery: '{member.phone}'."
    elif channel == "Web":
        if not member.email and not member.phone and not member.id:
            return False, "No valid destination or identifier found for Web notification."

    return True, None


def revalidate_jit_consent(db: Session, member_id: int) -> bool:
    """
    Performs Just-In-Time (JIT) consent revalidation directly against the database
    immediately prior to message dispatch.
    Catches consent revocations that occurred between job creation and worker processing.
    """
    stmt = select(AudienceMember.consent_status).where(AudienceMember.id == member_id)
    consent = db.execute(stmt).scalar_one_or_none()
    return consent is True


def revalidate_jit_eligibility(
    db: Session,
    member_id: int,
    channel: str,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Full Just-In-Time (JIT) revalidation directly from the database immediately prior
    to invoking a delivery provider.
    Verifies:
    1. Recipient still exists in the database.
    2. Affirmative consent is active (consent_status IS True).
    3. Contact credentials for the target channel remain present and valid.

    Returns:
        (is_eligible, error_code, error_message)
    """
    stmt = select(AudienceMember).where(AudienceMember.id == member_id)
    member = db.execute(stmt).scalar_one_or_none()
    if not member:
        return False, "RECIPIENT_DELETED", "Audience member record was deleted prior to dispatch execution."

    if member.consent_status is False:
        return False, "CONSENT_WITHDRAWN_POST_JOB", "Recipient revoked affirmative consent after distribution job was queued."

    if member.consent_status is None:
        return False, "CONSENT_UNCONFIRMED_POST_JOB", "Recipient consent is unconfirmed (consent_status=None)."

    if member.consent_status is not True:
        return False, "LACKS_AFFIRMATIVE_CONSENT", "Recipient lacks affirmative consent."

    is_valid, reason = validate_recipient_consent(member, channel)
    if not is_valid:
        return False, "MISSING_CONTACT_INFO", reason

    return True, None, None


