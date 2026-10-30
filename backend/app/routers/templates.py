"""FastAPI router for Reusable Communication Templates and Content Library."""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.core.dependencies import require_role
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    PaginatedTemplateResponse,
    SUPPORTED_TEMPLATE_CATEGORIES,
    ALLOWED_PLACEHOLDERS,
)
from app.services import template_service

logger = logging.getLogger("masscommai.templates_router")

router = APIRouter(prefix="/templates", tags=["Templates"])

# RBAC Role Matrix:
# - Read & Categories access: Admin, Campaign Manager, Communication Team
# - Create access: Admin, Campaign Manager (Communication Team is restricted)
# - Update & Delete access: Admin (all), Campaign Manager (own created templates only)
TEMPLATE_READ_ROLES = ["Admin", "Campaign Manager", "Communication Team"]
TEMPLATE_WRITE_ROLES = ["Admin", "Campaign Manager"]


@router.get(
    "/categories",
    summary="Get supported template categories and allowed placeholders metadata",
)
def get_template_categories(
    current_user: User = Depends(require_role(TEMPLATE_READ_ROLES)),
) -> Dict[str, Any]:
    """
    Returns the server-enforced allowlist of communication domain categories
    and placeholder tokens ({name}, {email}, etc.) permitted in template message bodies.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    return {
        "categories": sorted(list(SUPPORTED_TEMPLATE_CATEGORIES)),
        "allowed_placeholders": sorted(list(ALLOWED_PLACEHOLDERS)),
    }


@router.get(
    "",
    response_model=PaginatedTemplateResponse,
    summary="List saved templates with pagination, search, category, and language filters",
)
def list_templates(
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term matching title, body, or tags"),
    category: Optional[str] = Query(None, description="Filter by domain category (e.g. Healthcare, Disaster Management)"),
    language: Optional[str] = Query(None, description="Filter by language code (e.g. en, hi, ta)"),
    current_user: User = Depends(require_role(TEMPLATE_READ_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Retrieve paginated templates with creator metadata and extracted placeholders.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    return template_service.list_templates(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        category=category,
        language=language,
    )


@router.post(
    "",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new communication template",
)
def create_template(
    payload: TemplateCreate,
    current_user: User = Depends(require_role(TEMPLATE_WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Creates a new communication template with placeholder validation.
    Enforces title uniqueness and records creator ID.
    Authorized for Admin and Campaign Manager roles only.
    """
    return template_service.create_template(
        db=db,
        data=payload,
        current_user=current_user,
    )


@router.get(
    "/{id}",
    response_model=TemplateResponse,
    summary="Retrieve a template by ID",
)
def get_template(
    id: int = Path(..., ge=1, description="Template primary key ID"),
    current_user: User = Depends(require_role(TEMPLATE_READ_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Get full template details, content body, creator metadata, and extracted placeholders.
    Accessible to Admin, Campaign Manager, and Communication Team.
    """
    return template_service.get_template_response(db=db, template_id=id)


@router.put(
    "/{id}",
    response_model=TemplateResponse,
    summary="Update an existing template",
)
def update_template(
    payload: TemplateUpdate,
    id: int = Path(..., ge=1, description="Template primary key ID"),
    current_user: User = Depends(require_role(TEMPLATE_WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Update template headline, category, content body, language, or tags.
    Enforces ownership permissions: Admins can update any template;
    Campaign Managers can only update templates they created.
    """
    return template_service.update_template(
        db=db,
        template_id=id,
        data=payload,
        current_user=current_user,
    )


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a template",
)
def delete_template(
    id: int = Path(..., ge=1, description="Template primary key ID"),
    current_user: User = Depends(require_role(TEMPLATE_WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """
    Permanently delete a template.
    Enforces ownership permissions: Admins can delete any template;
    Campaign Managers can only delete templates they created.
    """
    template_service.delete_template(
        db=db,
        template_id=id,
        current_user=current_user,
    )
    return None

