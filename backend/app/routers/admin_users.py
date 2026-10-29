"""Admin-only User Management endpoints for listing users, changing roles, and managing activation state."""

import math
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.user import User, Role
from app.core.dependencies import require_role
from app.schemas.user import (
    UserRead,
    UserRoleUpdateRequest,
    UserStatusUpdateRequest,
    PaginatedUsersResponse,
)

logger = logging.getLogger("masscommai.routers.admin_users")

router = APIRouter(
    prefix="/admin/users",
    tags=["Admin User Management"],
    dependencies=[Depends(require_role("Admin"))],
)


@router.get(
    "",
    response_model=PaginatedUsersResponse,
    summary="List all users (Admin only)",
    description="Returns a paginated list of registered users with optional search and role filtering.",
)
def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search query matching name, email, or organization"),
    role: Optional[str] = Query(None, description="Filter by role name"),
    db: Session = Depends(get_db),
):
    """Admin endpoint to retrieve paginated users."""
    base_query = select(User).join(User.role)

    if search:
        search_term = f"%{search.strip().lower()}%"
        base_query = base_query.where(
            or_(
                func.lower(User.full_name).like(search_term),
                func.lower(User.email).like(search_term),
                func.lower(User.organization).like(search_term),
            )
        )

    if role:
        base_query = base_query.where(Role.name == role.strip())

    # Count total matching rows
    count_query = select(func.count()).select_from(base_query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Fetch paginated slice with joinedload
    offset = (page - 1) * page_size
    items_query = (
        base_query.options(joinedload(User.role))
        .order_by(User.id.asc())
        .offset(offset)
        .limit(page_size)
    )
    users = db.execute(items_query).scalars().all()

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return PaginatedUsersResponse(
        items=[
            UserRead(
                id=u.id,
                full_name=u.full_name,
                email=u.email,
                phone=u.phone,
                organization=u.organization,
                role_id=u.role_id,
                role_name=u.role.name,
                is_active=u.is_active,
                created_at=u.created_at,
            )
            for u in users
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.put(
    "/{user_id}/role",
    response_model=UserRead,
    summary="Update a user's role (Admin only)",
    description="Assigns a new role to the target user. Protects against self-demotion and removal of the final Administrator.",
    responses={
        200: {"description": "Role successfully updated."},
        400: {"description": "Invalid role or prohibited self-demotion."},
        404: {"description": "User or role not found."},
        409: {"description": "Conflict: Cannot demote the final remaining Administrator."},
    },
)
def update_user_role(
    user_id: int = Path(..., ge=1, description="ID of the target user"),
    request: UserRoleUpdateRequest = ...,
    current_admin: User = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    """Updates target user's role with administrative safeguards."""
    target_user = (
        db.execute(
            select(User)
            .options(joinedload(User.role))
            .where(User.id == user_id)
        )
        .scalar_one_or_none()
    )

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # Validate target role existence
    target_role = db.execute(
        select(Role).where(Role.name == request.role_name)
    ).scalar_one_or_none()

    if not target_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role '{request.role_name}' does not exist.",
        )

    # Safeguard 1: Prevent self-demotion
    if current_admin.id == target_user.id and target_role.name != "Admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot demote their own account. Another administrator must perform this action.",
        )

    # Safeguard 2: Prevent demoting the final active Administrator
    if target_user.role.name == "Admin" and target_role.name != "Admin":
        active_admin_count = db.execute(
            select(func.count(User.id))
            .join(Role)
            .where(Role.name == "Admin", User.is_active == True)
        ).scalar() or 0

        if active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot demote the only remaining active Administrator in the system.",
            )

    # Apply role update
    target_user.role_id = target_role.id
    target_user.role = target_role
    db.commit()
    db.refresh(target_user)

    logger.info(
        "Admin user_id=%d changed role of user_id=%d to '%s'",
        current_admin.id,
        target_user.id,
        target_role.name,
    )

    return UserRead(
        id=target_user.id,
        full_name=target_user.full_name,
        email=target_user.email,
        phone=target_user.phone,
        organization=target_user.organization,
        role_id=target_user.role_id,
        role_name=target_user.role.name,
        is_active=target_user.is_active,
        created_at=target_user.created_at,
    )


@router.patch(
    "/{user_id}/status",
    response_model=UserRead,
    summary="Activate or deactivate a user (Admin only)",
    description="Toggles the active state of a user. Protects against self-deactivation and deactivating the final Administrator.",
    responses={
        200: {"description": "User status successfully updated."},
        400: {"description": "Prohibited self-deactivation."},
        404: {"description": "User not found."},
        409: {"description": "Conflict: Cannot deactivate the final remaining Administrator."},
    },
)
def update_user_status(
    user_id: int = Path(..., ge=1, description="ID of the target user"),
    request: UserStatusUpdateRequest = ...,
    current_admin: User = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    """Updates target user's active/deactivated status with safeguards."""
    target_user = (
        db.execute(
            select(User)
            .options(joinedload(User.role))
            .where(User.id == user_id)
        )
        .scalar_one_or_none()
    )

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # Safeguard 1: Prevent self-deactivation
    if current_admin.id == target_user.id and not request.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account.",
        )

    # Safeguard 2: Prevent deactivating the final active Administrator
    if target_user.role.name == "Admin" and not request.is_active:
        active_admin_count = db.execute(
            select(func.count(User.id))
            .join(Role)
            .where(Role.name == "Admin", User.is_active == True)
        ).scalar() or 0

        if active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot deactivate the only remaining active Administrator in the system.",
            )

    target_user.is_active = request.is_active
    db.commit()
    db.refresh(target_user)

    logger.info(
        "Admin user_id=%d changed active status of user_id=%d to %s",
        current_admin.id,
        target_user.id,
        target_user.is_active,
    )

    return UserRead(
        id=target_user.id,
        full_name=target_user.full_name,
        email=target_user.email,
        phone=target_user.phone,
        organization=target_user.organization,
        role_id=target_user.role_id,
        role_name=target_user.role.name,
        is_active=target_user.is_active,
        created_at=target_user.created_at,
    )

