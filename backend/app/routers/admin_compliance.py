"""Admin-only Dynamic Compliance Rules management endpoints."""

import math
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, HTTPException, status
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.compliance_rule import ComplianceRule
from app.core.dependencies import require_role
from app.schemas.compliance_rule import (
    ComplianceRuleCreate,
    ComplianceRuleUpdate,
    ComplianceRuleResponse,
    PaginatedComplianceRulesResponse,
    SUPPORTED_RULE_TYPES,
    SUPPORTED_SEVERITIES,
)

logger = logging.getLogger("masscommai.routers.admin_compliance")

router = APIRouter(
    prefix="/admin/compliance-rules",
    tags=["Admin Compliance Rules"],
    dependencies=[Depends(require_role("Admin"))],
)


def _generate_rule_code(rule_type: str) -> str:
    """Generate a readable, unique compliance rule code."""
    type_abbr = {
        "banned_word": "BW",
        "mandatory_phrase": "MP",
        "regex_pattern": "RX",
    }.get(rule_type, "GEN")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"COMP-{type_abbr}-{suffix}"


def _verify_tenant_access(current_user: User, rule: ComplianceRule) -> None:
    """Ensure user belongs to same organization or is platform super-admin."""
    if current_user.organization and not rule.is_global and rule.organization:
        if rule.organization != current_user.organization:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You cannot access compliance rules belonging to another organization.",
            )


@router.post(
    "",
    response_model=ComplianceRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create compliance rule (Admin only)",
    description="Creates a new dynamic compliance rule for banned vocabulary, mandatory disclaimers, or pattern enforcement.",
)
def create_compliance_rule(
    payload: ComplianceRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Admin")),
) -> ComplianceRule:
    """Create a new compliance rule with tenant and uniqueness validation."""
    # Tenant assignment & boundary validation
    target_org = payload.organization
    is_global = payload.is_global

    if current_user.organization:
        # User is tenant-scoped
        if target_org and target_org != current_user.organization:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot create rules for organization '{target_org}'. Your account belongs to '{current_user.organization}'.",
            )
        # Non-global admins create rules for their organization unless explicit global permission
        if not is_global:
            target_org = current_user.organization
    else:
        # Platform admin: respect payload settings
        if not target_org and not is_global:
            is_global = True

    # Rule code resolution
    rule_code = payload.rule_code.strip() if payload.rule_code else _generate_rule_code(payload.rule_type)

    # Check rule code uniqueness
    existing_code = db.execute(
        select(ComplianceRule).where(func.lower(ComplianceRule.rule_code) == rule_code.lower())
    ).scalar_one_or_none()
    if existing_code:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Compliance rule with code '{rule_code}' already exists.",
        )

    # Check duplicate pattern in the same scope
    dup_stmt = select(ComplianceRule).where(
        ComplianceRule.rule_type == payload.rule_type,
        func.lower(ComplianceRule.pattern) == payload.pattern.strip().lower(),
        ComplianceRule.is_global == is_global,
        ComplianceRule.organization == target_org,
        ComplianceRule.channel == payload.channel,
        ComplianceRule.language == payload.language,
    )
    if db.execute(dup_stmt).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A compliance rule with identical pattern, type, and target scope already exists.",
        )

    rule = ComplianceRule(
        rule_code=rule_code,
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        rule_type=payload.rule_type,
        pattern=payload.pattern.strip(),
        severity=payload.severity,
        organization=target_org,
        is_global=is_global,
        channel=payload.channel,
        language=payload.language.strip() if payload.language else None,
        suggested_action=payload.suggested_action.strip() if payload.suggested_action else None,
        is_active=payload.is_active,
        created_by=current_user.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    logger.info("Created compliance rule %s (%s) by user %s", rule.rule_code, rule.rule_type, current_user.email)
    return rule


@router.get(
    "",
    response_model=PaginatedComplianceRulesResponse,
    summary="List compliance rules (Admin only)",
    description="Returns a paginated list of compliance rules with optional filters for rule type, severity, channel, and organization.",
)
def list_compliance_rules(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    rule_type: Optional[str] = Query(None, description="banned_word, mandatory_phrase, regex_pattern"),
    severity: Optional[str] = Query(None, description="critical, high, medium, low, info"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    channel: Optional[str] = Query(None, description="Filter by communication channel"),
    language: Optional[str] = Query(None, description="Filter by language code"),
    organization: Optional[str] = Query(None, description="Filter by organization"),
    search: Optional[str] = Query(None, description="Search across name, description, rule_code, and pattern"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Admin")),
) -> PaginatedComplianceRulesResponse:
    """Retrieve filtered, paginated compliance rules respecting tenant isolation."""
    stmt = select(ComplianceRule)

    # Enforce tenant isolation
    if current_user.organization:
        stmt = stmt.where(
            or_(
                ComplianceRule.is_global == True,
                ComplianceRule.organization.is_(None),
                ComplianceRule.organization == current_user.organization,
            )
        )
        if organization and organization != current_user.organization:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot view rules for organization '{organization}'.",
            )
    elif organization:
        stmt = stmt.where(ComplianceRule.organization == organization)

    # Query filters
    if rule_type:
        clean_type = rule_type.lower().strip()
        if clean_type in SUPPORTED_RULE_TYPES:
            stmt = stmt.where(ComplianceRule.rule_type == clean_type)

    if severity:
        clean_sev = severity.lower().strip()
        if clean_sev in SUPPORTED_SEVERITIES:
            stmt = stmt.where(ComplianceRule.severity == clean_sev)

    if is_active is not None:
        stmt = stmt.where(ComplianceRule.is_active == is_active)

    if channel:
        stmt = stmt.where(func.lower(ComplianceRule.channel) == channel.strip().lower())

    if language:
        stmt = stmt.where(func.lower(ComplianceRule.language) == language.strip().lower())

    if search:
        search_pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(ComplianceRule.name).like(search_pattern),
                func.lower(ComplianceRule.rule_code).like(search_pattern),
                func.lower(ComplianceRule.pattern).like(search_pattern),
                func.lower(ComplianceRule.description).like(search_pattern),
            )
        )

    # Total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    # Pagination & Ordering
    offset = (page - 1) * size
    pages = math.ceil(total / size) if total > 0 else 1
    items = db.execute(
        stmt.order_by(ComplianceRule.created_at.desc()).offset(offset).limit(size)
    ).scalars().all()

    return PaginatedComplianceRulesResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get(
    "/{rule_id}",
    response_model=ComplianceRuleResponse,
    summary="Get compliance rule by ID (Admin only)",
)
def get_compliance_rule(
    rule_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Admin")),
) -> ComplianceRule:
    """Retrieve details of a single compliance rule by primary key."""
    rule = db.get(ComplianceRule, rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Compliance rule with ID {rule_id} not found.",
        )
    _verify_tenant_access(current_user, rule)
    return rule


@router.patch(
    "/{rule_id}",
    response_model=ComplianceRuleResponse,
    summary="Update compliance rule (Admin only)",
)
def update_compliance_rule(
    payload: ComplianceRuleUpdate,
    rule_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Admin")),
) -> ComplianceRule:
    """Update fields on an existing compliance rule."""
    rule = db.get(ComplianceRule, rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Compliance rule with ID {rule_id} not found.",
        )
    _verify_tenant_access(current_user, rule)

    update_data = payload.model_dump(exclude_unset=True)

    # Check tenant boundary if updating organization
    if "organization" in update_data and current_user.organization:
        new_org = update_data["organization"]
        if new_org and new_org != current_user.organization:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot transfer rule to organization '{new_org}'.",
            )

    for field, value in update_data.items():
        if field in ("name", "pattern", "description", "suggested_action", "language") and isinstance(value, str):
            value = value.strip()
        setattr(rule, field, value)

    rule.updated_by = current_user.id
    db.commit()
    db.refresh(rule)

    logger.info("Updated compliance rule %s by user %s", rule.rule_code, current_user.email)
    return rule


@router.delete(
    "/{rule_id}",
    summary="Delete compliance rule (Admin only)",
)
def delete_compliance_rule(
    rule_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Admin")),
) -> dict:
    """Permanently delete a compliance rule."""
    rule = db.get(ComplianceRule, rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Compliance rule with ID {rule_id} not found.",
        )
    _verify_tenant_access(current_user, rule)

    code = rule.rule_code
    db.delete(rule)
    db.commit()

    logger.info("Deleted compliance rule %s by user %s", code, current_user.email)
    return {"detail": f"Compliance rule '{code}' successfully deleted."}


@router.patch(
    "/{rule_id}/toggle-active",
    response_model=ComplianceRuleResponse,
    summary="Toggle compliance rule active state (Admin only)",
)
def toggle_compliance_rule_active(
    rule_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Admin")),
) -> ComplianceRule:
    """Toggle a compliance rule between active and inactive state."""
    rule = db.get(ComplianceRule, rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Compliance rule with ID {rule_id} not found.",
        )
    _verify_tenant_access(current_user, rule)

    rule.is_active = not rule.is_active
    rule.updated_by = current_user.id
    db.commit()
    db.refresh(rule)

    logger.info("Toggled compliance rule %s active=%s by user %s", rule.rule_code, rule.is_active, current_user.email)
    return rule

