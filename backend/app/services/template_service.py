"""Service layer for Template Library management and placeholder handling."""

import logging
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy import select, func, desc, or_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.template import Template
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    PaginatedTemplateResponse,
    extract_placeholders,
    validate_placeholders,
)

logger = logging.getLogger("masscommai.template_service")


def get_template_by_id(db: Session, template_id: int) -> Template:
    """Retrieve template ORM entity by primary key ID or raise HTTP 404."""
    stmt = (
        select(Template)
        .options(joinedload(Template.creator))
        .where(Template.id == template_id)
    )
    template = db.execute(stmt).scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with ID {template_id} not found.",
        )
    return template


def build_template_response(template: Template) -> TemplateResponse:
    """Construct TemplateResponse including creator metadata and extracted placeholders."""
    creator_name = template.creator.full_name if template.creator else f"User #{template.created_by}"
    creator_email = template.creator.email if template.creator else None
    placeholders = extract_placeholders(template.body)

    return TemplateResponse(
        id=template.id,
        title=template.title,
        category=template.category,
        body=template.body,
        language=template.language,
        tags=template.tags,
        created_by=template.created_by,
        creator_name=creator_name,
        creator_email=creator_email,
        placeholders=sorted(list(set(placeholders))),
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def get_template_response(db: Session, template_id: int) -> TemplateResponse:
    """Retrieve template and return public response schema."""
    template = get_template_by_id(db, template_id)
    return build_template_response(template)


def create_template(
    db: Session,
    data: TemplateCreate,
    current_user: User,
) -> TemplateResponse:
    """
    Creates a new communication template.
    Enforces case-insensitive title uniqueness and placeholder syntax correctness.
    """
    clean_title = data.title.strip()
    existing_stmt = select(Template).where(func.lower(Template.title) == clean_title.lower())
    if db.execute(existing_stmt).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A template titled '{clean_title}' already exists.",
        )

    # Validate placeholders explicitly
    validate_placeholders(data.body)

    template = Template(
        title=clean_title,
        category=data.category,
        body=data.body.strip(),
        language=data.language.strip().lower(),
        tags=data.tags.strip() if data.tags else None,
        created_by=current_user.id,
    )
    db.add(template)
    try:
        db.commit()
        db.refresh(template)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A template titled '{clean_title}' already exists.",
        )

    logger.info("Created template ID %s ('%s') by user ID %s", template.id, template.title, current_user.id)
    return build_template_response(template)


def list_templates(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
    category: Optional[str] = None,
    language: Optional[str] = None,
) -> PaginatedTemplateResponse:
    """
    Returns paginated templates filtered by search term, category, and language.
    """
    query = select(Template).options(joinedload(Template.creator))

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Template.title.ilike(term),
                Template.body.ilike(term),
                Template.tags.ilike(term),
            )
        )

    if category and category.strip():
        query = query.where(func.lower(Template.category) == category.strip().lower())

    if language and language.strip():
        query = query.where(func.lower(Template.language) == language.strip().lower())

    # Count total matching rows
    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = db.scalar(count_query) or 0

    # Paginate and order by newest first
    offset = (page - 1) * page_size
    query = query.order_by(desc(Template.created_at)).offset(offset).limit(page_size)
    templates = db.execute(query).scalars().all()

    items = [build_template_response(t) for t in templates]
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedTemplateResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def update_template(
    db: Session,
    template_id: int,
    data: TemplateUpdate,
    current_user: User,
) -> TemplateResponse:
    """
    Updates an existing template.
    Enforces creator ownership: Admins can update any template;
    Campaign Managers can only update their own templates.
    """
    template = get_template_by_id(db, template_id)

    # Ownership check
    is_admin = current_user.role and current_user.role.name == "Admin"
    if not is_admin and template.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify templates created by other users. Campaign Managers can only update or delete their own templates.",
        )

    if data.title is not None:
        clean_title = data.title.strip()
        collision_stmt = select(Template).where(
            func.lower(Template.title) == clean_title.lower(),
            Template.id != template_id,
        )
        if db.execute(collision_stmt).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another template titled '{clean_title}' already exists.",
            )
        template.title = clean_title

    if data.category is not None:
        template.category = data.category

    if data.body is not None:
        validate_placeholders(data.body)
        template.body = data.body.strip()

    if data.language is not None:
        template.language = data.language.strip().lower()

    if data.tags is not None:
        template.tags = data.tags.strip() if data.tags else None

    try:
        db.commit()
        db.refresh(template)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A template with this title already exists.",
        )

    logger.info("Updated template ID %s by user ID %s", template.id, current_user.id)
    return build_template_response(template)


def delete_template(
    db: Session,
    template_id: int,
    current_user: User,
) -> None:
    """
    Permanently deletes a template.
    Enforces creator ownership: Admins can delete any template;
    Campaign Managers can only delete their own templates.
    """
    template = get_template_by_id(db, template_id)

    # Ownership check
    is_admin = current_user.role and current_user.role.name == "Admin"
    if not is_admin and template.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete templates created by other users. Campaign Managers can only update or delete their own templates.",
        )

    db.delete(template)
    db.commit()
    logger.info("Deleted template ID %s by user ID %s", template_id, current_user.id)

