"""Pydantic v2 schemas for Audience Segmentation Engine and Dynamic Rule Builder."""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.audience import AudienceMemberResponse

# Explicit allowlist of fields available on AudienceMember for segmentation
SUPPORTED_SEGMENT_FIELDS: Dict[str, Dict[str, Any]] = {
    "name": {
        "type": "text",
        "label": "Full Name",
        "operators": ["equals", "not_equals", "contains", "starts_with", "is_empty", "is_not_empty"],
    },
    "email": {
        "type": "text",
        "label": "Email Address",
        "operators": ["equals", "not_equals", "contains", "starts_with", "is_empty", "is_not_empty"],
    },
    "phone": {
        "type": "text",
        "label": "Phone Number",
        "operators": ["equals", "not_equals", "contains", "starts_with", "is_empty", "is_not_empty"],
    },
    "age": {
        "type": "numeric",
        "label": "Age",
        "operators": [
            "equals",
            "not_equals",
            "greater_than",
            "less_than",
            "greater_than_or_equal",
            "less_than_or_equal",
            "is_empty",
            "is_not_empty",
        ],
    },
    "gender": {
        "type": "categorical",
        "label": "Gender",
        "operators": ["equals", "not_equals", "in", "is_empty", "is_not_empty"],
        "options": ["Male", "Female", "Other", "Prefer not to say"],
    },
    "city": {
        "type": "text",
        "label": "City",
        "operators": ["equals", "not_equals", "contains", "starts_with", "is_empty", "is_not_empty"],
    },
    "state": {
        "type": "text",
        "label": "State",
        "operators": ["equals", "not_equals", "contains", "starts_with", "is_empty", "is_not_empty"],
    },
    "preferred_language": {
        "type": "categorical",
        "label": "Preferred Language",
        "operators": ["equals", "not_equals", "in", "is_empty", "is_not_empty"],
        "options": ["en", "hi", "ta", "te", "bn", "mr", "gu", "kn", "ml", "pa", "or", "as"],
    },
    "occupation": {
        "type": "text",
        "label": "Occupation",
        "operators": ["equals", "not_equals", "contains", "starts_with", "is_empty", "is_not_empty"],
    },
    "organization_department": {
        "type": "text",
        "label": "Department / Organization",
        "operators": ["equals", "not_equals", "contains", "starts_with", "is_empty", "is_not_empty"],
    },
    "preferred_channel": {
        "type": "categorical",
        "label": "Preferred Channel",
        "operators": ["equals", "not_equals", "in", "is_empty", "is_not_empty"],
        "options": ["Email", "SMS", "WhatsApp"],
    },
    "consent_status": {
        "type": "consent",
        "label": "Communication Consent",
        "operators": ["equals", "not_equals", "is_empty", "is_not_empty"],
        "options": ["true", "false", "unconfirmed"],
    },
}

MAX_CONDITIONS_LIMIT = 20
MAX_NESTING_DEPTH = 2


class RuleCondition(BaseModel):
    """Atomic rule condition comparing a single audience attribute against an operator and value."""

    field: str = Field(..., description="Target audience attribute from the supported allowlist")
    operator: str = Field(..., description="Comparison operator compatible with field type")
    value: Optional[Any] = Field(default=None, description="Operand value (omitted for is_empty / is_not_empty)")

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in SUPPORTED_SEGMENT_FIELDS:
            allowed = ", ".join(SUPPORTED_SEGMENT_FIELDS.keys())
            raise ValueError(f"Unsupported segmentation field '{v}'. Allowed fields: {allowed}")
        return clean

    @model_validator(mode="after")
    def validate_operator_and_value(self) -> "RuleCondition":
        field_meta = SUPPORTED_SEGMENT_FIELDS[self.field]
        allowed_operators = field_meta["operators"]
        field_type = field_meta["type"]

        clean_op = self.operator.strip().lower()
        if clean_op not in allowed_operators:
            raise ValueError(
                f"Operator '{self.operator}' is not valid for {field_type} field '{self.field}'. "
                f"Allowed operators: {', '.join(allowed_operators)}"
            )
        self.operator = clean_op

        # 1. Operators that require no value
        if clean_op in ("is_empty", "is_not_empty"):
            self.value = None
            return self

        # 2. Type-specific validations and value requirement
        if field_type == "consent":
            # Tri-state consent normalization (True, False, or None for unconfirmed)
            if isinstance(self.value, bool):
                pass
            elif self.value is None:
                pass
            elif isinstance(self.value, str):
                v_lower = self.value.strip().lower()
                if v_lower in ("true", "1", "opt_in", "consented"):
                    self.value = True
                elif v_lower in ("false", "0", "opt_out", "unsubscribed"):
                    self.value = False
                elif v_lower in ("null", "none", "unconfirmed", "unknown"):
                    self.value = None
                else:
                    raise ValueError(
                        f"Invalid consent value '{self.value}'. Allowed: true, false, unconfirmed"
                    )
            else:
                raise ValueError("Consent condition requires a boolean, None, or 'unconfirmed' value.")
        else:
            if self.value is None or (isinstance(self.value, str) and not self.value.strip()):
                raise ValueError(f"Value is required for operator '{self.operator}' on field '{self.field}'.")

        if field_type == "numeric":
            try:
                numeric_val = int(self.value)
                if numeric_val < 1 or numeric_val > 120:
                    raise ValueError(f"Age value must be between 1 and 120 (got {numeric_val}).")
                self.value = numeric_val
            except (ValueError, TypeError) as exc:
                if "Age value must be" in str(exc):
                    raise
                raise ValueError(f"Field '{self.field}' requires a valid integer value.")

        elif clean_op == "in":
            # Categorical IN list
            if isinstance(self.value, list):
                clean_list = [str(item).strip() for item in self.value if str(item).strip()]
                if not clean_list:
                    raise ValueError(f"Operator 'in' on '{self.field}' requires at least one non-empty value.")
                self.value = clean_list
            elif isinstance(self.value, str):
                clean_list = [item.strip() for item in self.value.split(",") if item.strip()]
                if not clean_list:
                    raise ValueError(f"Operator 'in' on '{self.field}' requires comma-separated values.")
                self.value = clean_list
            else:
                raise ValueError(f"Operator 'in' on '{self.field}' requires a list of values.")

        elif isinstance(self.value, str):
            self.value = self.value.strip()

        return self


class RuleGroup(BaseModel):
    """Composite rule group combining conditions or sub-groups with an AND / OR connector."""

    connector: Literal["AND", "OR"] = Field(
        default="AND",
        description="Logical connector combining all conditions in this group: AND (all match) or OR (any match)",
    )
    conditions: List[Union[RuleCondition, "RuleGroup"]] = Field(
        default_factory=list,
        description="List of atomic conditions or nested sub-groups",
    )
    groups: List["RuleGroup"] = Field(
        default_factory=list,
        description="Optional list of nested sub-groups",
    )

    @field_validator("connector", mode="before")
    @classmethod
    def clean_connector(cls, v: Any) -> str:
        if isinstance(v, str):
            clean = v.strip().upper()
            if clean in ("AND", "OR"):
                return clean
        return "AND"

    @model_validator(mode="after")
    def validate_group_constraints(self) -> "RuleGroup":
        def count_conditions(group: RuleGroup, depth: int = 1) -> int:
            if depth > MAX_NESTING_DEPTH:
                raise ValueError(
                    f"Rule group nesting exceeds maximum allowed depth of {MAX_NESTING_DEPTH} levels."
                )
            total = 0
            for item in group.conditions:
                if isinstance(item, RuleGroup):
                    total += count_conditions(item, depth + 1)
                else:
                    total += 1
            for sub_g in group.groups:
                total += count_conditions(sub_g, depth + 1)
            return total

        total = count_conditions(self)
        if total > MAX_CONDITIONS_LIMIT:
            raise ValueError(
                f"Rule group contains {total} conditions, which exceeds the maximum limit of {MAX_CONDITIONS_LIMIT}."
            )
        return self


class SegmentBase(BaseModel):
    """Base schema for an audience segment."""

    name: str = Field(..., min_length=2, max_length=120, description="Human-readable segment name")
    description: Optional[str] = Field(default=None, max_length=255, description="Optional segment purpose or description")
    filter_rules: RuleGroup = Field(..., description="Structured JSON rule definition")

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        clean = v.strip()
        if len(clean) < 2:
            raise ValueError("Segment name must be at least 2 characters long.")
        return clean

    @field_validator("description")
    @classmethod
    def clean_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            return clean if clean else None
        return None


class SegmentCreate(SegmentBase):
    """Payload for creating a new saved audience segment."""
    pass


class SegmentUpdate(BaseModel):
    """Payload for updating an existing audience segment (all fields optional)."""

    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=255)
    filter_rules: Optional[RuleGroup] = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if len(clean) < 2:
                raise ValueError("Segment name must be at least 2 characters long.")
            return clean
        return None


class SegmentResponse(BaseModel):
    """Public serialization of a saved segment entity."""

    id: int
    name: str
    description: Optional[str] = None
    filter_rules: Dict[str, Any]
    created_by: int
    creator_name: Optional[str] = None
    creator_email: Optional[str] = None
    matching_count: Optional[int] = None
    matching_audience_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class PaginatedSegmentResponse(BaseModel):
    """Paginated collection of audience segments."""

    items: List[SegmentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SegmentPreviewRequest(BaseModel):
    """Request payload to preview matching count and sample audience members for an unsaved rule definition."""

    filter_rules: RuleGroup
    page: int = Field(default=1, ge=1, description="Sample pagination page index")
    page_size: int = Field(default=10, ge=1, le=50, description="Sample page size (max 50)")


class SegmentPreviewResponse(BaseModel):
    """Live preview result with total matching audience count and paginated sample records."""

    total_matching: int
    page: int
    page_size: int
    total_pages: int
    sample_members: List[AudienceMemberResponse]
