"""Pydantic v2 schemas for User, Authentication, and Role governance."""

from __future__ import annotations
import re
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator


# Strictly enforce Communication Team as the sole role for public registration
DEFAULT_REGISTRATION_ROLE = "Communication Team"
ALLOWED_REGISTRATION_ROLES = {DEFAULT_REGISTRATION_ROLE}

# Valid roles in the platform
ALL_SYSTEM_ROLES = {"Admin", "Campaign Manager", "Communication Team"}


class RoleRead(BaseModel):
    """Schema for serializing role metadata."""

    id: int
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserRegisterRequest(BaseModel):
    """Registration request schema with normalization, byte-limit validation, and role security."""

    full_name: str = Field(
        ...,
        min_length=2,
        max_length=120,
        description="Full name of the registrant",
        examples=["Priya Sharma"],
    )
    email: EmailStr = Field(
        ...,
        max_length=255,
        description="Unique email address",
        examples=["priya.sharma@dept.gov.in"],
    )
    phone: Optional[str] = Field(
        None,
        max_length=30,
        description="Optional contact phone number",
        examples=["+919876543210"],
    )
    organization: Optional[str] = Field(
        None,
        max_length=150,
        description="Organization, agency, or department name",
        examples=["Health Services Directorate"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (min 8 characters, max 72 UTF-8 bytes, with letters and numbers)",
        examples=["Secur3P@ssw0rd!"],
    )
    role_request: Optional[str] = Field(
        DEFAULT_REGISTRATION_ROLE,
        description="Target role (strictly restricted to Communication Team for public registration)",
        examples=["Communication Team"],
    )

    @model_validator(mode="before")
    @classmethod
    def intercept_role_tampering_and_aliases(cls, data: any) -> any:
        """Reject client attempts to supply elevated role fields and handle aliases."""
        if isinstance(data, dict):
            for forbidden in ("role", "role_id", "role_name"):
                if forbidden in data:
                    raise ValueError(
                        f"Field '{forbidden}' cannot be specified during public registration. "
                        "Role assignments are server-controlled."
                    )
            if "name" in data and "full_name" not in data:
                data["full_name"] = data["name"]
        return data

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email address to lowercase and strip whitespace."""
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength_and_byte_length(cls, v: str) -> str:
        """Enforce password complexity and bcrypt's strict 72-byte limit."""
        encoded_bytes = v.encode("utf-8")
        if len(encoded_bytes) > 72:
            raise ValueError(
                "Password cannot exceed 72 bytes when UTF-8 encoded. "
                "If using non-ASCII or multibyte characters, please use a shorter password."
            )
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter.")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number.")
        return v

    @field_validator("role_request")
    @classmethod
    def validate_least_privileged_role(cls, v: Optional[str]) -> str:
        """Ensure public self-registration receives only Communication Team."""
        if not v:
            return DEFAULT_REGISTRATION_ROLE
        cleaned = v.strip()
        if cleaned != DEFAULT_REGISTRATION_ROLE:
            raise ValueError(
                f"Public self-registration is restricted to the '{DEFAULT_REGISTRATION_ROLE}' role. "
                "Campaign Manager and Admin privileges must be assigned by a system administrator."
            )
        return cleaned


class UserLoginRequest(BaseModel):
    """Schema for authenticating existing users."""

    email: EmailStr = Field(..., description="Account email address")
    password: str = Field(..., min_length=1, description="Account password")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserRead(BaseModel):
    """Safe user profile response schema (never exposes hashed_password)."""

    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    organization: Optional[str] = None
    role_id: int
    role_name: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserRegisterResponse(BaseModel):
    """Standardized response schema for successful registration."""

    status: str = "success"
    message: str
    user: UserRead


class TokenResponse(BaseModel):
    """JWT authentication response schema."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class UserRoleUpdateRequest(BaseModel):
    """Administrator schema for updating a target user's role."""

    role_name: str = Field(
        ...,
        description="New role name (Admin, Campaign Manager, Communication Team)",
        examples=["Campaign Manager"],
    )

    @field_validator("role_name")
    @classmethod
    def validate_role_name(cls, v: str) -> str:
        cleaned = v.strip()
        if cleaned not in ALL_SYSTEM_ROLES:
            raise ValueError(
                f"Invalid role '{cleaned}'. Allowed roles: {', '.join(sorted(ALL_SYSTEM_ROLES))}."
            )
        return cleaned


class UserStatusUpdateRequest(BaseModel):
    """Administrator schema for activating or deactivating a target user."""

    is_active: bool = Field(
        ...,
        description="Active status flag (True to activate, False to deactivate)",
    )


class PaginatedUsersResponse(BaseModel):
    """Paginated user directory response."""

    items: List[UserRead]
    total: int
    page: int
    page_size: int
    total_pages: int
