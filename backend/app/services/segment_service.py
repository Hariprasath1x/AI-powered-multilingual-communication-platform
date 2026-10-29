"""Audience segmentation service: dynamic rule compilation, validation, preview, and CRUD operations."""

import logging
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_, not_, desc, asc, literal
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.segment import Segment
from app.models.audience import AudienceMember
from app.models.user import User
from app.schemas.segment import (
    RuleCondition,
    RuleGroup,
    SegmentCreate,
    SegmentUpdate,
    SegmentResponse,
    PaginatedSegmentResponse,
    SegmentPreviewResponse,
    SUPPORTED_SEGMENT_FIELDS,
)
from app.schemas.audience import AudienceMemberResponse

logger = logging.getLogger("masscommai.segment_service")


def compile_rule_condition(cond: RuleCondition) -> ColumnElement[bool]:
    """
    Safely translates a single atomic RuleCondition into a SQLAlchemy boolean expression.
    Guarantees parameter binding and strictly prevents raw SQL injection.
    """
    field_meta = SUPPORTED_SEGMENT_FIELDS[cond.field]
    field_type = field_meta["type"]
    col = getattr(AudienceMember, cond.field)
    op = cond.operator.lower()
    val = cond.value

    # 1. Operators without value: is_empty / is_not_empty
    if op == "is_empty":
        if field_type in ("consent", "numeric"):
            return col.is_(None)
        return or_(col.is_(None), col == "")

    if op == "is_not_empty":
        if field_type in ("consent", "numeric"):
            return col.is_not(None)
        return and_(col.is_not(None), col != "")

    # 2. Field-type specific operators
    if field_type == "consent":
        # Tri-state consent matching
        if op == "equals":
            if val is True:
                return col.is_(True)
            elif val is False:
                return col.is_(False)
            elif val is None:
                return col.is_(None)
        elif op == "not_equals":
            if val is True:
                return or_(col.is_(False), col.is_(None))
            elif val is False:
                return or_(col.is_(True), col.is_(None))
            elif val is None:
                return col.is_not(None)
        raise ValueError(f"Unsupported operator '{op}' for consent_status")

    if field_type == "numeric":
        num_val = int(val)
        if op == "equals":
            return col == num_val
        elif op == "not_equals":
            return or_(col != num_val, col.is_(None))
        elif op == "greater_than":
            return col > num_val
        elif op == "less_than":
            return col < num_val
        elif op == "greater_than_or_equal":
            return col >= num_val
        elif op == "less_than_or_equal":
            return col <= num_val
        raise ValueError(f"Unsupported numeric operator '{op}'")

    if op == "in":
        # Categorical multi-value IN
        items = val if isinstance(val, list) else [str(val)]
        if not items:
            return literal(False)
        clauses = [col.ilike(str(item).strip()) for item in items if str(item).strip()]
        return or_(*clauses) if clauses else literal(False)

    str_val = str(val).strip()
    if op == "equals":
        return col.ilike(str_val)
    elif op == "not_equals":
        return or_(col.not_ilike(str_val), col.is_(None))
    elif op == "contains":
        return col.ilike(f"%{str_val}%")
    elif op == "starts_with":
        return col.ilike(f"{str_val}%")

    raise ValueError(f"Unrecognized operator '{op}' for field '{cond.field}'")


def compile_rule_group(group: RuleGroup) -> ColumnElement[bool]:
    """
    Recursively compiles a RuleGroup into a composite SQLAlchemy boolean expression.
    Preserves correct AND/OR precedence and short-circuits empty groups cleanly.
    """
    items = list(group.conditions)
    if hasattr(group, "groups") and group.groups:
        items.extend(group.groups)

    if not items:
        return literal(True)

    expressions: List[ColumnElement[bool]] = []
    for item in items:
        if isinstance(item, RuleGroup):
            sub_expr = compile_rule_group(item)
            expressions.append(sub_expr)
        elif isinstance(item, RuleCondition):
            cond_expr = compile_rule_condition(item)
            expressions.append(cond_expr)
        elif isinstance(item, dict):
            # Parse dict representation if passed unvalidated
            if "connector" in item:
                sub_group = RuleGroup.model_validate(item)
                expressions.append(compile_rule_group(sub_group))
            else:
                cond = RuleCondition.model_validate(item)
                expressions.append(compile_rule_condition(cond))

    if not expressions:
        return literal(True)

    if group.connector.upper() == "OR":
        return or_(*expressions)
    return and_(*expressions)


def preview_rules(
    db: Session,
    filter_rules: RuleGroup,
    page: int = 1,
    page_size: int = 10,
) -> SegmentPreviewResponse:
    """
    Evaluates a candidate or saved RuleGroup directly against the audience database.
    Returns total matching count and a paginated sample of audience records.
    """
    compiled_filter = compile_rule_group(filter_rules)

    # 1. Matching Count Calculation
    count_stmt = select(func.count(AudienceMember.id)).where(compiled_filter)
    total_matching = db.execute(count_stmt).scalar_one() or 0

    # 2. Paginated Sample Retrieval
    total_pages = (total_matching + page_size - 1) // page_size if total_matching > 0 else 0
    offset = (page - 1) * page_size

    sample_stmt = (
        select(AudienceMember)
        .where(compiled_filter)
        .order_by(AudienceMember.name.asc(), AudienceMember.id.asc())
        .offset(offset)
        .limit(page_size)
    )
    sample_items = list(db.execute(sample_stmt).scalars().all())

    return SegmentPreviewResponse(
        total_matching=total_matching,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        sample_members=[AudienceMemberResponse.model_validate(m) for m in sample_items],
    )


def compute_segment_matching_count(db: Session, filter_rules_dict: Dict[str, Any]) -> int:
    """Safely calculates the current audience count matching a segment's stored JSON rules."""
    try:
        rule_group = RuleGroup.model_validate(filter_rules_dict)
        compiled_filter = compile_rule_group(rule_group)
        count_stmt = select(func.count(AudienceMember.id)).where(compiled_filter)
        return db.execute(count_stmt).scalar_one() or 0
    except Exception as exc:
        logger.warning("Could not calculate matching count for rule definition: %s", exc)
        return 0


def list_segments(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
) -> PaginatedSegmentResponse:
    """List saved segments with pagination, search, creator metadata, and live matching audience counts."""
    query = select(Segment).options(joinedload(Segment.creator))

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Segment.name.ilike(term),
                Segment.description.ilike(term),
            )
        )

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar_one() or 0

    # Pagination & Ordering
    offset = (page - 1) * page_size
    query = query.order_by(desc(Segment.created_at)).offset(offset).limit(page_size)
    segments = list(db.execute(query).scalars().all())

    items: List[SegmentResponse] = []
    for s in segments:
        matching = compute_segment_matching_count(db, s.filter_rules)
        creator_name = s.creator.full_name if s.creator else f"User #{s.created_by}"
        creator_email = s.creator.email if s.creator else None
        items.append(
            SegmentResponse(
                id=s.id,
                name=s.name,
                description=s.description,
                filter_rules=s.filter_rules,
                created_by=s.created_by,
                creator_name=creator_name,
                creator_email=creator_email,
                matching_count=matching,
                matching_audience_count=matching,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedSegmentResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_segment_by_id(db: Session, segment_id: int) -> Segment:
    """Retrieve segment by primary key ID or raise HTTP 404."""
    stmt = (
        select(Segment)
        .options(joinedload(Segment.creator))
        .where(Segment.id == segment_id)
    )
    segment = db.execute(stmt).scalar_one_or_none()
    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audience segment with ID {segment_id} not found.",
        )
    return segment


def get_segment_response(db: Session, segment_id: int) -> SegmentResponse:
    """Retrieve detailed SegmentResponse including live matching count."""
    segment = get_segment_by_id(db, segment_id)
    matching = compute_segment_matching_count(db, segment.filter_rules)
    creator_name = segment.creator.full_name if segment.creator else f"User #{segment.created_by}"
    creator_email = segment.creator.email if segment.creator else None

    return SegmentResponse(
        id=segment.id,
        name=segment.name,
        description=segment.description,
        filter_rules=segment.filter_rules,
        created_by=segment.created_by,
        creator_name=creator_name,
        creator_email=creator_email,
        matching_count=matching,
        matching_audience_count=matching,
        created_at=segment.created_at,
        updated_at=segment.updated_at,
    )


def create_segment(
    db: Session,
    data: SegmentCreate,
    current_user: User,
) -> SegmentResponse:
    """
    Creates a new audience segment with validated dynamic JSON rules.
    Detects duplicate segment names and enforces unique naming.
    """
    # 1. Uniqueness check on segment name (case-insensitive)
    existing_stmt = select(Segment).where(func.lower(Segment.name) == data.name.strip().lower())
    if db.execute(existing_stmt).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An audience segment named '{data.name.strip()}' already exists.",
        )

    # 2. Persist segment
    segment = Segment(
        name=data.name.strip(),
        description=data.description.strip() if data.description else None,
        filter_rules=data.filter_rules.model_dump(),
        created_by=current_user.id,
    )
    db.add(segment)
    try:
        db.commit()
        db.refresh(segment)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A segment with this name already exists.",
        )

    logger.info("Created segment ID %s ('%s') by user ID %s", segment.id, segment.name, current_user.id)
    return get_segment_response(db, segment.id)


def update_segment(
    db: Session,
    segment_id: int,
    data: SegmentUpdate,
    current_user: User,
) -> SegmentResponse:
    """
    Updates segment properties and rule definitions.
    Enforces ownership permissions: Admins can update any segment;
    Campaign Managers can only update their own segments.
    """
    segment = get_segment_by_id(db, segment_id)

    # Ownership check: Admin or creator
    is_admin = current_user.role and current_user.role.name == "Admin"
    if not is_admin and segment.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify segments created by other users. Campaign Managers can only update or delete their own segments.",
        )

    # Name uniqueness check if name is changing
    if data.name:
        clean_name = data.name.strip()
        collision_stmt = select(Segment).where(
            func.lower(Segment.name) == clean_name.lower(),
            Segment.id != segment_id,
        )
        if db.execute(collision_stmt).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another audience segment named '{clean_name}' already exists.",
            )
        segment.name = clean_name

    if data.description is not None:
        segment.description = data.description.strip() if data.description else None

    if data.filter_rules is not None:
        segment.filter_rules = data.filter_rules.model_dump()

    try:
        db.commit()
        db.refresh(segment)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A segment with this name already exists.",
        )

    logger.info("Updated segment ID %s by user ID %s", segment.id, current_user.id)
    return get_segment_response(db, segment.id)


def delete_segment(
    db: Session,
    segment_id: int,
    current_user: User,
) -> None:
    """
    Permanently deletes a segment entity.
    Enforces ownership permissions: Admins can delete any segment;
    Campaign Managers can only delete their own segments.
    """
    segment = get_segment_by_id(db, segment_id)

    # Ownership check: Admin or creator
    is_admin = current_user.role and current_user.role.name == "Admin"
    if not is_admin and segment.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete segments created by other users. Campaign Managers can only update or delete their own segments.",
        )

    db.delete(segment)
    db.commit()
    logger.info("Deleted segment ID %s by user ID %s", segment_id, current_user.id)
