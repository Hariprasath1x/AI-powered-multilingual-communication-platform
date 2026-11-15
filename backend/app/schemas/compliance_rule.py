"""Pydantic schemas and validators for Administrator-Managed Compliance Rules."""

import re
from datetime import datetime
from typing import List, Optional, Set
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

SUPPORTED_RULE_TYPES: Set[str] = {"banned_word", "mandatory_phrase", "regex_pattern"}
SUPPORTED_SEVERITIES: Set[str] = {"critical", "high", "medium", "low", "info"}
SUPPORTED_CHANNELS: Set[str] = {"Email", "SMS", "WhatsApp", "Voice"}

# Suspicious ReDoS nested quantifier detection pattern
REDOS_DANGEROUS_PATTERN = re.compile(r"(\([^\)]*[\+\*][^\)]*\)[\+\*])|([\+\*]\s*[\+\*])")


def validate_safe_regex_pattern(pattern: str) -> None:
    """Validate regex syntax and protect against catastrophic backtracking (ReDoS)."""
    if len(pattern) > 255:
        raise ValueError("Regex pattern exceeds maximum length of 255 characters.")
    if REDOS_DANGEROUS_PATTERN.search(pattern):
        raise ValueError("Pattern contains nested or stacked quantifiers susceptible to catastrophic backtracking.")
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid regular expression syntax: {e}")


class ComplianceRuleCreate(BaseModel):
    """Schema for creating a new compliance rule."""

    rule_code: Optional[str] = Field(
        None,
        max_length=50,
        description="Unique rule code (e.g. COMP-BW-001). Auto-generated if omitted.",
    )
    name: str = Field(..., min_length=2, max_length=255, description="Descriptive rule name")
    description: Optional[str] = Field(None, description="Detailed explanation of compliance policy")
    rule_type: str = Field(..., description="banned_word, mandatory_phrase, regex_pattern")
    pattern: str = Field(..., min_length=1, max_length=1000, description="Word, phrase, or bounded regex")
    severity: str = Field("critical", description="critical, high, medium, low, info")
    organization: Optional[str] = Field(None, max_length=150, description="Target organization scope or null")
    is_global: bool = Field(False, description="Whether rule applies across all organizations")
    channel: Optional[str] = Field(None, max_length=30, description="Email, SMS, WhatsApp, Voice, or null")
    language: Optional[str] = Field(None, max_length=10, description="Language code like 'en', 'hi', or null")
    suggested_action: Optional[str] = Field(None, description="Guidance or correction advice for reviewers")
    is_active: bool = Field(True, description="Whether rule is active")

    @field_validator("rule_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        clean = v.lower().strip()
        if clean not in SUPPORTED_RULE_TYPES:
            raise ValueError(f"rule_type must be one of: {', '.join(sorted(SUPPORTED_RULE_TYPES))}")
        return clean

    @field_validator("severity")
    @classmethod
    def validate_sev(cls, v: str) -> str:
        clean = v.lower().strip()
        if clean not in SUPPORTED_SEVERITIES:
            raise ValueError(f"severity must be one of: {', '.join(sorted(SUPPORTED_SEVERITIES))}")
        return clean

    @field_validator("channel")
    @classmethod
    def validate_chan(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        # Match case-insensitively to supported channels
        for chan in SUPPORTED_CHANNELS:
            if chan.lower() == v.strip().lower():
                return chan
        raise ValueError(f"channel must be one of: {', '.join(sorted(SUPPORTED_CHANNELS))}")

    @field_validator("pattern")
    @classmethod
    def validate_pat(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Pattern cannot be empty or whitespace only.")
        return clean

    @model_validator(mode="after")
    def validate_pattern_rules(self) -> "ComplianceRuleCreate":
        if self.rule_type == "regex_pattern":
            validate_safe_regex_pattern(self.pattern)
        if self.is_global and self.organization:
            # If marked global, clear specific organization to avoid conflicting semantics
            self.organization = None
        elif not self.is_global and not self.organization:
            # If no organization provided, rule defaults to global
            self.is_global = True
        return self


class ComplianceRuleUpdate(BaseModel):
    """Schema for updating an existing compliance rule."""

    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    rule_type: Optional[str] = None
    pattern: Optional[str] = Field(None, min_length=1, max_length=1000)
    severity: Optional[str] = None
    organization: Optional[str] = Field(None, max_length=150)
    is_global: Optional[bool] = None
    channel: Optional[str] = Field(None, max_length=30)
    language: Optional[str] = Field(None, max_length=10)
    suggested_action: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("rule_type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.lower().strip()
        if clean not in SUPPORTED_RULE_TYPES:
            raise ValueError(f"rule_type must be one of: {', '.join(sorted(SUPPORTED_RULE_TYPES))}")
        return clean

    @field_validator("severity")
    @classmethod
    def validate_sev(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.lower().strip()
        if clean not in SUPPORTED_SEVERITIES:
            raise ValueError(f"severity must be one of: {', '.join(sorted(SUPPORTED_SEVERITIES))}")
        return clean

    @field_validator("channel")
    @classmethod
    def validate_chan(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        for chan in SUPPORTED_CHANNELS:
            if chan.lower() == v.strip().lower():
                return chan
        raise ValueError(f"channel must be one of: {', '.join(sorted(SUPPORTED_CHANNELS))}")

    @model_validator(mode="after")
    def validate_update_rules(self) -> "ComplianceRuleUpdate":
        if self.rule_type == "regex_pattern" and self.pattern:
            validate_safe_regex_pattern(self.pattern)
        return self


class ComplianceRuleResponse(BaseModel):
    """Full schema for a compliance rule entity."""

    id: int
    rule_code: str
    name: str
    description: Optional[str] = None
    rule_type: str
    pattern: str
    severity: str
    organization: Optional[str] = None
    is_global: bool
    channel: Optional[str] = None
    language: Optional[str] = None
    suggested_action: Optional[str] = None
    is_active: bool
    created_by: int
    updated_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedComplianceRulesResponse(BaseModel):
    """Paginated collection of compliance rules."""

    items: List[ComplianceRuleResponse]
    total: int
    page: int
    size: int
    pages: int

