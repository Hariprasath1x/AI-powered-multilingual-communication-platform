"""Pydantic schemas package."""

from app.schemas.user import (
    RoleRead,
    UserRegisterRequest,
    UserLoginRequest,
    UserRead,
    UserRegisterResponse,
    TokenResponse,
    UserRoleUpdateRequest,
    UserStatusUpdateRequest,
    PaginatedUsersResponse,
    DEFAULT_REGISTRATION_ROLE,
    ALLOWED_REGISTRATION_ROLES,
    ALL_SYSTEM_ROLES,
)

__all__ = [
    "RoleRead",
    "UserRegisterRequest",
    "UserLoginRequest",
    "UserRead",
    "UserRegisterResponse",
    "TokenResponse",
    "UserRoleUpdateRequest",
    "UserStatusUpdateRequest",
    "PaginatedUsersResponse",
    "DEFAULT_REGISTRATION_ROLE",
    "ALLOWED_REGISTRATION_ROLES",
    "ALL_SYSTEM_ROLES",
]
