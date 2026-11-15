"""
MassCommAI - Deterministic, Occurrence-Aware Placeholder Validation Engine.

Provides strict multiset (Counter) placeholder verification to guarantee that:
- Placeholders like {name}, {city}, {phone} are preserved exactly in spelling and syntax.
- Repeated placeholders (e.g. {name} occurring twice) preserve their exact occurrence count.
- Missing, extra, duplicated, or corrupted/translated placeholder tokens are detected.
"""

from collections import Counter
from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional, Set, Tuple


# Strict valid placeholder format: {var_name} (single braces only, not double/nested)
STRICT_PLACEHOLDER_REGEX = re.compile(r"(?<!\{)\{[a-zA-Z0-9_]+\}(?!\})")

# Catch-all brace token regex for detecting malformed/translated braces like {பெயர்}, { नाम }, {123-abc}
ANY_BRACE_TOKEN_REGEX = re.compile(r"\{[^{}\n\r]+\}")


@dataclass
class PlaceholderValidationResult:
    """Detailed result of occurrence-aware placeholder validation."""

    is_valid: bool
    source_counts: Dict[str, int] = field(default_factory=dict)
    translated_counts: Dict[str, int] = field(default_factory=dict)
    missing: Dict[str, int] = field(default_factory=dict)
    extra: Dict[str, int] = field(default_factory=dict)
    corrupted: List[str] = field(default_factory=list)
    error_message: Optional[str] = None

    @property
    def total_source_placeholders(self) -> int:
        return sum(self.source_counts.values())

    @property
    def total_translated_placeholders(self) -> int:
        return sum(self.translated_counts.values())


def extract_placeholders(text: Optional[str]) -> List[str]:
    """Extract all valid placeholder tokens preserving order and duplicates."""
    if not text:
        return []
    return STRICT_PLACEHOLDER_REGEX.findall(text)


def extract_all_brace_tokens(text: Optional[str]) -> List[str]:
    """Extract all brace tokens including non-ASCII or spaced tokens."""
    if not text:
        return []
    return ANY_BRACE_TOKEN_REGEX.findall(text)


def validate_placeholders(
    source_title: Optional[str] = None,
    source_body: Optional[str] = None,
    source_cta: Optional[str] = None,
    translated_title: Optional[str] = None,
    translated_body: Optional[str] = None,
    translated_cta: Optional[str] = None,
) -> PlaceholderValidationResult:
    """
    Occurrence-aware (multiset) validation across title, body, and call_to_action.

    Verifies:
    1. Every placeholder in source appears in translated output with exact frequency.
    2. No extra, hallucinated, or duplicate placeholders appear in translated output.
    3. No translated or malformed placeholder tokens (e.g. Indic script inside braces) exist.
    """
    source_texts = [t for t in (source_title, source_body, source_cta) if t]
    translated_texts = [t for t in (translated_title, translated_body, translated_cta) if t]

    source_tokens: List[str] = []
    for st in source_texts:
        source_tokens.extend(extract_placeholders(st))

    translated_tokens: List[str] = []
    for tt in translated_texts:
        translated_tokens.extend(extract_placeholders(tt))

    source_counter = Counter(source_tokens)
    translated_counter = Counter(translated_tokens)

    # Detect missing occurrences
    missing: Dict[str, int] = {}
    for token, src_count in source_counter.items():
        tgt_count = translated_counter.get(token, 0)
        if tgt_count < src_count:
            missing[token] = src_count - tgt_count

    # Detect extra / unexpected occurrences
    extra: Dict[str, int] = {}
    for token, tgt_count in translated_counter.items():
        src_count = source_counter.get(token, 0)
        if tgt_count > src_count:
            extra[token] = tgt_count - src_count

    # Detect corrupted / translated brace tokens (e.g. {பெயர்}, { नाम })
    all_translated_braces: List[str] = []
    for tt in translated_texts:
        all_translated_braces.extend(extract_all_brace_tokens(tt))

    valid_set = set(translated_tokens)
    corrupted: List[str] = [
        token for token in all_translated_braces if token not in valid_set
    ]

    # Detect nested or double braces (e.g. {{name}}) not present in source (AUDIT-T8-06)
    source_nested: Set[str] = set()
    for st in source_texts:
        for nt in re.findall(r"\{\{[^{}\n\r]*\}\}", st):
            source_nested.add(nt)

    for tt in translated_texts:
        nested_tokens = re.findall(r"\{\{[^{}\n\r]*\}\}", tt)
        for nt in nested_tokens:
            if nt not in source_nested and nt not in corrupted:
                corrupted.append(nt)
        if re.search(r"\{\{|\}\}", tt) and not any(re.search(r"\{\{|\}\}", st) for st in source_texts):
            for stray in ("{{", "}}"):
                if stray in tt and not any(stray in c for c in corrupted):
                    corrupted.append(stray)
        if tt.count("{") != tt.count("}"):
            if "unbalanced_braces" not in corrupted:
                corrupted.append("unbalanced_braces")

    is_valid = len(missing) == 0 and len(extra) == 0 and len(corrupted) == 0

    error_parts = []
    if missing:
        missing_desc = ", ".join(f"{k} (missing {v})" for k, v in missing.items())
        error_parts.append(f"Missing placeholders: {missing_desc}")
    if extra:
        extra_desc = ", ".join(f"{k} (extra {v})" for k, v in extra.items())
        error_parts.append(f"Unexpected extra placeholders: {extra_desc}")
    if corrupted:
        error_parts.append(f"Corrupted or translated placeholders: {', '.join(corrupted)}")

    error_message = "; ".join(error_parts) if error_parts else None

    return PlaceholderValidationResult(
        is_valid=is_valid,
        source_counts=dict(source_counter),
        translated_counts=dict(translated_counter),
        missing=missing,
        extra=extra,
        corrupted=corrupted,
        error_message=error_message,
    )

