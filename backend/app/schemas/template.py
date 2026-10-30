"""Pydantic v2 schemas for Reusable Communication Templates and Placeholder Validation."""

from datetime import datetime
import re
from typing import List, Optional, Set
from pydantic import BaseModel, Field, field_validator


SUPPORTED_TEMPLATE_CATEGORIES: Set[str] = {
    "Healthcare",
    "Disaster Management",
    "Civic Education",
    "Public Governance",
    "Emergency Alert",
    "Community Outreach",
}

ALLOWED_PLACEHOLDERS: Set[str] = {
    "{name}",
    "{email}",
    "{phone}",
    "{city}",
    "{state}",
    "{preferred_language}",
    "{occupation}",
    "{organization_department}",
}


def extract_placeholders(text: str) -> List[str]:
    """Extract all placeholder tokens matching {token} pattern."""
    return re.findall(r"\{[a-zA-Z0-9_]+\}", text)


def validate_placeholders(text: str) -> List[str]:
    """
    Validates that any placeholders in text match the allowed set.
    Detects unclosed or empty placeholders like '{}'.
    Raises ValueError on invalid or unsupported placeholders.
    Returns list of valid placeholders found.
    """
    if "{}" in text:
        raise ValueError("Malformed empty placeholder '{}' detected in template body.")

    open_count = text.count("{")
    close_count = text.count("}")
    if open_count != close_count:
        raise ValueError(
            f"Mismatched placeholder braces in template body: {open_count} opening '{{' and {close_count} closing '}}'."
        )

    # Detect braces with spaces or invalid characters e.g. {foo-bar} or {foo bar}
    all_braces = re.findall(r"\{[^{}]*\}", text)
    clean_placeholders = extract_placeholders(text)
    for b in all_braces:
        if b not in clean_placeholders and b != "":
            raise ValueError(f"Malformed placeholder syntax '{b}' in template body.")

    unsupported = [p for p in clean_placeholders if p.lower() not in ALLOWED_PLACEHOLDERS]
    if unsupported:
        allowed_str = ", ".join(sorted(ALLOWED_PLACEHOLDERS))
        raise ValueError(
            f"Unsupported placeholder(s) {unsupported} in template body. Allowed placeholders: {allowed_str}"
        )

    return sorted(list(set(clean_placeholders)))


class TemplateBase(BaseModel):
    """Base template payload."""

    title: str = Field(..., min_length=2, max_length=150, description="Template headline title")
    category: str = Field(..., description="Thematic domain category")
    body: str = Field(..., min_length=5, description="Template message body with {name} placeholders")
    language: str = Field(default="en", max_length=30, description="Template language code e.g. en, hi, ta")
    tags: Optional[str] = Field(default=None, max_length=255, description="Comma-separated keyword tags")

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        clean = v.strip()
        if len(clean) < 2:
            raise ValueError("Template title must be at least 2 characters long.")
        return clean

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        clean = v.strip()
        matched = {c.lower(): c for c in SUPPORTED_TEMPLATE_CATEGORIES}
        if clean.lower() not in matched:
            allowed = ", ".join(sorted(SUPPORTED_TEMPLATE_CATEGORIES))
            raise ValueError(f"Invalid category '{v}'. Allowed categories: {allowed}")
        return matched[clean.lower()]

    @field_validator("body")
    @classmethod
    def validate_body_placeholders(cls, v: str) -> str:
        clean = v.strip()
        if len(clean) < 5:
            raise ValueError("Template body must be at least 5 characters long.")
        validate_placeholders(clean)
        return clean

    @field_validator("language")
    @classmethod
    def clean_language(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            return clean if clean else None
        return None


class TemplateCreate(TemplateBase):
    """Payload to create a new content template."""
    pass


class TemplateUpdate(BaseModel):
    """Payload to update an existing content template (all fields optional)."""

    title: Optional[str] = Field(default=None, min_length=2, max_length=150)
    category: Optional[str] = None
    body: Optional[str] = Field(default=None, min_length=5)
    language: Optional[str] = Field(default=None, max_length=30)
    tags: Optional[str] = Field(default=None, max_length=255)

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if len(clean) < 2:
                raise ValueError("Template title must be at least 2 characters long.")
            return clean
        return None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            matched = {c.lower(): c for c in SUPPORTED_TEMPLATE_CATEGORIES}
            if clean.lower() not in matched:
                allowed = ", ".join(sorted(SUPPORTED_TEMPLATE_CATEGORIES))
                raise ValueError(f"Invalid category '{v}'. Allowed categories: {allowed}")
            return matched[clean.lower()]
        return None

    @field_validator("body")
    @classmethod
    def validate_body_placeholders(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if len(clean) < 5:
                raise ValueError("Template body must be at least 5 characters long.")
            validate_placeholders(clean)
            return clean
        return None

    @field_validator("language")
    @classmethod
    def clean_language(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip().lower()
        return None


class TemplateResponse(BaseModel):
    """Public serialization of a content template."""

    id: int
    title: str
    category: str
    body: str
    language: str
    tags: Optional[str] = None
    created_by: int
    creator_name: Optional[str] = None
    creator_email: Optional[str] = None
    placeholders: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PaginatedTemplateResponse(BaseModel):
    """Paginated collection of content templates."""

    items: List[TemplateResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

