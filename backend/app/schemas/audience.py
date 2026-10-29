"""Pydantic v2 schemas for Audience Member management, pagination, stats, and bulk import."""

import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


def normalize_phone_number(v: Optional[str]) -> Optional[str]:
    """Clean and standardize phone numbers to digits and optional leading plus."""
    if v is None:
        return None
    val = v.strip()
    if not val:
        return None
    # Preserve leading + if present, remove common formatting characters: spaces, hyphens, parentheses, dots
    has_plus = val.startswith("+")
    digits = re.sub(r"[^\d]", "", val)
    if not digits:
        return None
    return f"+{digits}" if has_plus else digits


class AudienceMemberBase(BaseModel):
    """Core attributes for an audience member."""

    name: str = Field(..., min_length=1, max_length=120, description="Full recipient name")
    email: Optional[EmailStr] = Field(default=None, description="Primary email address")
    phone: Optional[str] = Field(default=None, max_length=30, description="Contact phone / mobile number")
    age: Optional[int] = Field(default=None, ge=1, le=120, description="Recipient age in years")
    gender: Optional[str] = Field(default=None, max_length=20, description="Gender identity")
    city: Optional[str] = Field(default=None, max_length=100, description="City / municipality")
    state: Optional[str] = Field(default=None, max_length=100, description="State / province / union territory")
    preferred_language: str = Field(default="en", max_length=50, description="Preferred language code or name (e.g., en, hi, ta)")
    occupation: Optional[str] = Field(default=None, max_length=100, description="Occupation or profession")
    organization_department: Optional[str] = Field(default=None, max_length=150, description="Associated department or institutional division")
    preferred_channel: str = Field(default="Email", max_length=30, description="Primary dispatch channel: Email, SMS, WhatsApp")
    consent_status: Optional[bool] = Field(
        default=None,
        description="Explicit communication consent: True=Opted In, False=Opted Out, None=Unknown/Unconfirmed",
    )

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Name cannot be blank.")
        return cleaned

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v.strip().lower()

    @field_validator("phone", mode="before")
    @classmethod
    def clean_phone(cls, v: Optional[str]) -> Optional[str]:
        norm = normalize_phone_number(v)
        if norm is not None:
            digits_only = re.sub(r"[^\d]", "", norm)
            if len(digits_only) < 7 or len(digits_only) > 15:
                raise ValueError("Phone number must contain between 7 and 15 digits.")
        return norm

    @field_validator("preferred_channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        clean = v.strip()
        valid = {"Email", "SMS", "WhatsApp", "Web"}
        for item in valid:
            if clean.lower() == item.lower():
                return item
        return clean

    @field_validator("preferred_language")
    @classmethod
    def clean_language(cls, v: str) -> str:
        clean = v.strip().lower()
        return clean or "en"

    @model_validator(mode="before")
    @classmethod
    def adjust_default_channel(cls, data: Any) -> Any:
        """Infer sensible default channel when caller provides only one contact method."""
        if isinstance(data, dict):
            channel = data.get("preferred_channel")
            if not channel:
                # If caller gave phone but no email, default to SMS
                if not data.get("email") and data.get("phone"):
                    data["preferred_channel"] = "SMS"
                else:
                    data["preferred_channel"] = "Email"
        return data

    @model_validator(mode="after")
    def validate_contact_and_channel(self) -> "AudienceMemberBase":
        # At least one contact handle must be provided
        if not self.email and not self.phone:
            raise ValueError("Audience member must have at least an email address or a phone number.")

        # Channel alignment validation
        channel_norm = self.preferred_channel.lower()
        if channel_norm == "email" and not self.email:
            raise ValueError("Email address is required when preferred channel is 'Email'.")
        if channel_norm in ("sms", "whatsapp") and not self.phone:
            raise ValueError(f"Phone number is required when preferred channel is '{self.preferred_channel}'.")

        return self


class AudienceMemberCreate(AudienceMemberBase):
    """Schema for creating a single audience member."""
    pass


class AudienceMemberUpdate(BaseModel):
    """Schema for updating an existing audience member (all fields optional)."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=30)
    age: Optional[int] = Field(default=None, ge=1, le=120)
    gender: Optional[str] = Field(default=None, max_length=20)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    preferred_language: Optional[str] = Field(default=None, max_length=50)
    occupation: Optional[str] = Field(default=None, max_length=100)
    organization_department: Optional[str] = Field(default=None, max_length=150)
    preferred_channel: Optional[str] = Field(default=None, max_length=30)
    consent_status: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            if not cleaned:
                raise ValueError("Name cannot be blank.")
            return cleaned
        return v

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and isinstance(v, str):
            cleaned = v.strip().lower()
            return cleaned if cleaned else None
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def clean_phone(cls, v: Optional[str]) -> Optional[str]:
        norm = normalize_phone_number(v)
        if norm is not None:
            digits_only = re.sub(r"[^\d]", "", norm)
            if len(digits_only) < 7 or len(digits_only) > 15:
                raise ValueError("Phone number must contain between 7 and 15 digits.")
        return norm


class AudienceMemberResponse(BaseModel):
    """Public serialization schema for an audience member entity."""

    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    preferred_language: str
    occupation: Optional[str] = None
    organization_department: Optional[str] = None
    preferred_channel: str
    consent_status: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedAudienceResponse(BaseModel):
    """Standard pagination wrapper for audience member queries."""

    items: List[AudienceMemberResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AudienceStatsResponse(BaseModel):
    """Aggregate statistics for the audience database."""

    total_members: int
    consented_count: int
    opt_out_count: int
    unspecified_consent_count: int
    active_consent_count: int  # alias for backwards compatibility
    language_distribution: Dict[str, int]
    channel_distribution: Dict[str, int]
    gender_distribution: Dict[str, int]


class ImportRowError(BaseModel):
    """Granular error representation for a rejected or unconfirmed import record."""

    row_number: int
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    reason: str
    error_type: str = "validation_error"  # "validation_error", "duplicate", or "missing_consent"


class AudienceImportSummary(BaseModel):
    """Comprehensive summary returned after processing a bulk CSV or Excel import."""

    total_rows: int
    successful_imports: int
    duplicate_count: int
    rejected_count: int
    unspecified_consent_count: int = 0
    errors: List[ImportRowError]
