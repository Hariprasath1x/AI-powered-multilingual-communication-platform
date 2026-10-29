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

from app.schemas.audience import (
    AudienceMemberCreate,
    AudienceMemberUpdate,
    AudienceMemberResponse,
    PaginatedAudienceResponse,
    AudienceStatsResponse,
    ImportRowError,
    AudienceImportSummary,
)

from app.schemas.segment import (
    RuleCondition,
    RuleGroup,
    SegmentCreate,
    SegmentUpdate,
    SegmentResponse,
    PaginatedSegmentResponse,
    SegmentPreviewRequest,
    SegmentPreviewResponse,
    SUPPORTED_SEGMENT_FIELDS,
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
    "AudienceMemberCreate",
    "AudienceMemberUpdate",
    "AudienceMemberResponse",
    "PaginatedAudienceResponse",
    "AudienceStatsResponse",
    "ImportRowError",
    "AudienceImportSummary",
    "RuleCondition",
    "RuleGroup",
    "SegmentCreate",
    "SegmentUpdate",
    "SegmentResponse",
    "PaginatedSegmentResponse",
    "SegmentPreviewRequest",
    "SegmentPreviewResponse",
    "SUPPORTED_SEGMENT_FIELDS",
]
