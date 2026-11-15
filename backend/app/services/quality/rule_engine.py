"""Deterministic rule engine for Content Quality, Safety, and Compliance validation."""

import re
import math
from typing import List, Set, Optional, Dict, Any, Tuple
from app.schemas.template import ALLOWED_PLACEHOLDERS
from app.services.quality.base import (
    FindingCategory,
    FindingSeverity,
    EvaluationSource,
    ContentQualityFindingDTO,
)
from app.services.channel_constraints import calculate_channel_metrics

PLACEHOLDER_REGEX = re.compile(r"\{[a-zA-Z0-9_]+\}")
MALFORMED_PLACEHOLDER_REGEX = re.compile(r"\{[^{}]*\}")
PHONE_REGEX = re.compile(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b|\b1\d{2,3}\b")  # Standard Indian mobile & emergency helplines like 1070, 104, 108, 112
DATE_REGEX = re.compile(r"\b\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b", re.IGNORECASE)
URL_REGEX = re.compile(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+")

# Safety & Sensitive vocabulary patterns
PANIC_WORDS = [
    (r"\b(apocalypse|apocalyptic|everyone will die|flee for your lives|run for your lives)\b", "Panic-inducing hysteria phrase"),
    (r"\b(100%\s+cure|miracle\s+cure|guaranteed\s+cure)\b", "Unverified absolute medical claim"),
    (r"\b(vote for|re-elect|political party|election campaign)\b", "Partisan political language in civic communication"),
    (r"\b(secret\s+cover-up|conspiracy|hoax)\b", "Conspiratorial disinformation phrasing"),
]


def extract_numbers_and_helplines(text: str) -> Set[str]:
    """Extract emergency phone numbers, helplines, and dates from text."""
    if not text:
        return set()
    numbers = set(PHONE_REGEX.findall(text))
    # Also grab isolated 3-4 digit shortcodes
    for match in re.finditer(r"\b\d{3,4}\b", text):
        numbers.add(match.group(0))
    return numbers


class DeterministicRuleEngine:
    """
    Executes fast, deterministic validation rules across placeholders,
    channel bounds, completeness, sensitive wording, and factual anchors.
    """

    @classmethod
    def evaluate(
        cls,
        title: str,
        body: str,
        call_to_action: Optional[str],
        channel: str,
        source_language: str,
        target_language: Optional[str] = None,
        reference_facts: Optional[str] = None,
        parent_title: Optional[str] = None,
        parent_body: Optional[str] = None,
        parent_cta: Optional[str] = None,
        compliance_rules: Optional[List[Any]] = None,
    ) -> List[ContentQualityFindingDTO]:
        findings: List[ContentQualityFindingDTO] = []

        combined_text = f"{title or ''}\n{body or ''}\n{call_to_action or ''}".strip()

        # 1. Completeness Checks
        cls._check_completeness(title, body, call_to_action, target_language, findings)

        # 2. Placeholder Integrity Checks
        cls._check_placeholders(
            combined_text=combined_text,
            parent_text=f"{parent_title or ''}\n{parent_body or ''}\n{parent_cta or ''}" if parent_body else None,
            findings=findings,
        )

        # 3. Channel Compliance Checks
        cls._check_channel_compliance(channel, title, body, findings, language=target_language or source_language)

        # 4. Factual Anchors & Reference Helplines Check
        cls._check_factual_anchors(
            body=body,
            reference_facts=reference_facts,
            parent_body=parent_body,
            findings=findings,
        )

        # 5. Sensitive & Panic Content Checks (Built-in)
        cls._check_sensitive_content(combined_text, findings)

        # 6. Readability & Structure Checks
        cls._check_readability(body, source_language, findings)

        # 7. Dynamic Database-Backed Compliance Rules
        cls._check_compliance_rules(
            combined_text=combined_text,
            channel=channel,
            effective_language=target_language or source_language,
            compliance_rules=compliance_rules,
            findings=findings,
        )

        # 8. Deduplicate: Admin-configured rules supersede built-in panic word checks on identical text
        dynamic_affected_texts = {
            f.affected_text.lower()
            for f in findings
            if f.rule_id and f.rule_id.startswith("COMP-") and f.affected_text
        }
        if dynamic_affected_texts:
            findings[:] = [
                f for f in findings
                if not (f.rule_id and f.rule_id.startswith("RULE-SAFE-") and f.affected_text and f.affected_text.lower() in dynamic_affected_texts)
            ]

        return findings

    @classmethod
    def _check_completeness(
        cls,
        title: str,
        body: str,
        call_to_action: Optional[str],
        target_language: Optional[str],
        findings: List[ContentQualityFindingDTO],
    ) -> None:
        if not title or len(title.strip()) < 3:
            findings.append(
                ContentQualityFindingDTO(
                    category=FindingCategory.COMPLETENESS,
                    severity=FindingSeverity.CRITICAL,
                    title="Missing or Truncated Title",
                    explanation="Every communication asset must have a concise, descriptive title (minimum 3 characters).",
                    affected_text=title,
                    suggested_correction="Provide a clear, domain-specific headline for this communication.",
                    evaluation_source=EvaluationSource.DETERMINISTIC,
                    confidence=1.0,
                    rule_id="RULE-COMP-001",
                )
            )

        if not body or len(body.strip()) < 10:
            findings.append(
                ContentQualityFindingDTO(
                    category=FindingCategory.COMPLETENESS,
                    severity=FindingSeverity.CRITICAL,
                    title="Empty or Incomplete Message Body",
                    explanation="The message body is empty or contains fewer than 10 characters.",
                    affected_text=body,
                    suggested_correction="Add full instructional message content before requesting editorial approval.",
                    evaluation_source=EvaluationSource.DETERMINISTIC,
                    confidence=1.0,
                    rule_id="RULE-COMP-002",
                )
            )

        if not call_to_action or not call_to_action.strip():
            findings.append(
                ContentQualityFindingDTO(
                    category=FindingCategory.COMPLETENESS,
                    severity=FindingSeverity.LOW,
                    title="Missing Call to Action",
                    explanation="A clear call to action (CTA) helps recipients take direct preventive or civic action.",
                    affected_text=None,
                    suggested_correction="Specify an actionable CTA (e.g. 'Call 104 for assistance', 'Visit official portal').",
                    evaluation_source=EvaluationSource.DETERMINISTIC,
                    confidence=0.85,
                    rule_id="RULE-COMP-003",
                )
            )

    @classmethod
    def _check_placeholders(
        cls,
        combined_text: str,
        parent_text: Optional[str],
        findings: List[ContentQualityFindingDTO],
    ) -> None:
        # Check for malformed braces e.g. {name or name}
        open_braces = combined_text.count("{")
        close_braces = combined_text.count("}")
        if open_braces != close_braces:
            findings.append(
                ContentQualityFindingDTO(
                    category=FindingCategory.PLACEHOLDER,
                    severity=FindingSeverity.CRITICAL,
                    title="Malformed Placeholder Syntax",
                    explanation=f"Mismatched curly braces detected ({open_braces} opening vs {close_braces} closing). Malformed syntax causes recipient message rendering failures.",
                    affected_text="{ ... }",
                    suggested_correction="Ensure all placeholder tags are balanced and correctly closed (e.g., '{name}', '{city}').",
                    evaluation_source=EvaluationSource.DETERMINISTIC,
                    confidence=1.0,
                    rule_id="RULE-PH-001",
                )
            )

        detected = set(PLACEHOLDER_REGEX.findall(combined_text))
        for ph in detected:
            if ph not in ALLOWED_PLACEHOLDERS:
                findings.append(
                    ContentQualityFindingDTO(
                        category=FindingCategory.PLACEHOLDER,
                        severity=FindingSeverity.HIGH,
                        title=f"Unsupported Placeholder Token: {ph}",
                        explanation=f"Placeholder '{ph}' is not in the system allowlist: {sorted(list(ALLOWED_PLACEHOLDERS))}.",
                        affected_text=ph,
                        suggested_correction=f"Use standard placeholders such as {', '.join(sorted(list(ALLOWED_PLACEHOLDERS))[:4])}.",
                        evaluation_source=EvaluationSource.DETERMINISTIC,
                        confidence=0.95,
                        rule_id="RULE-PH-002",
                    )
                )

        # Translation check: Ensure all parent placeholders are preserved
        if parent_text:
            parent_phs = set(PLACEHOLDER_REGEX.findall(parent_text))
            missing_in_child = parent_phs - detected
            if missing_in_child:
                missing_str = ", ".join(sorted(list(missing_in_child)))
                findings.append(
                    ContentQualityFindingDTO(
                        category=FindingCategory.TRANSLATION,
                        severity=FindingSeverity.CRITICAL,
                        title=f"Dropped Placeholders in Translation: {missing_str}",
                        explanation=f"The original source copy contained dynamic variable(s) {missing_str} which are missing from the translated variant. Dynamic recipient personalization will fail.",
                        affected_text=missing_str,
                        suggested_correction=f"Re-insert the exact placeholder token(s) {missing_str} into the translated message.",
                        evaluation_source=EvaluationSource.DETERMINISTIC,
                        confidence=1.0,
                        rule_id="RULE-PH-003",
                    )
                )

    @classmethod
    def _check_channel_compliance(
        cls,
        channel: str,
        title: str,
        body: str,
        findings: List[ContentQualityFindingDTO],
        language: Optional[str] = "en",
    ) -> None:
        metrics = calculate_channel_metrics(
            channel=channel,
            title=title,
            body=body,
            language=language or "en",
        )
        ch = metrics.channel

        if ch == "SMS" and metrics.sms:
            body_len = metrics.character_count
            segment_count = metrics.sms.segment_count

            if segment_count > 3:
                findings.append(
                    ContentQualityFindingDTO(
                        category=FindingCategory.CHANNEL,
                        severity=FindingSeverity.HIGH,
                        title=f"SMS Exceeds 3 Segments ({segment_count} segments / {body_len} chars)",
                        explanation="Multi-part SMS messages exceeding 3 segments suffer increased carrier delivery latency and recipient fragmentation on feature phones.",
                        affected_text=f"{body_len} characters ({segment_count} segments)",
                        suggested_correction="Condense SMS message copy to under 160 characters (1 segment) or maximum 320 characters (2 segments).",
                        evaluation_source=EvaluationSource.DETERMINISTIC,
                        confidence=1.0,
                        rule_id="RULE-CHAN-SMS-001",
                    )
                )
            if not metrics.is_within_hard_limit:
                findings.append(
                    ContentQualityFindingDTO(
                        category=FindingCategory.CHANNEL,
                        severity=FindingSeverity.CRITICAL,
                        title="SMS Exceeds Gateway Maximum Length",
                        explanation="Message exceeds telecom carrier hard limit of 1600 characters and will be rejected by SMS delivery gateways.",
                        affected_text=f"{body_len} characters",
                        suggested_correction="Shorten text drastically to fit SMS standards.",
                        evaluation_source=EvaluationSource.DETERMINISTIC,
                        confidence=1.0,
                        rule_id="RULE-CHAN-SMS-002",
                    )
                )

        elif ch == "Voice":
            words = metrics.word_count
            est_seconds = metrics.estimated_duration_seconds or 5

            if est_seconds > 90:
                findings.append(
                    ContentQualityFindingDTO(
                        category=FindingCategory.CHANNEL,
                        severity=FindingSeverity.HIGH,
                        title=f"Voice IVR Script Exceeds 90 Seconds (~{est_seconds}s)",
                        explanation="Citizen call dropout rates increase significantly for voice broadcast scripts exceeding 60-90 seconds in duration.",
                        affected_text=f"{words} words (~{est_seconds} seconds)",
                        suggested_correction="Trim script to 100-150 words (~40-60 seconds) focusing on core emergency actions.",
                        evaluation_source=EvaluationSource.DETERMINISTIC,
                        confidence=0.9,
                        rule_id="RULE-CHAN-VOICE-001",
                    )
                )

            # Check for unpronounceable URLs or raw markdown headers in voice text via engine warnings
            has_url_warning = any(w.code == "VOICE_CONTAINS_URL" for w in metrics.warnings)
            if has_url_warning:
                url_match = URL_REGEX.search(body or "")
                affected = url_match.group(0) if url_match else "URL detected"
                findings.append(
                    ContentQualityFindingDTO(
                        category=FindingCategory.CHANNEL,
                        severity=FindingSeverity.MEDIUM,
                        title="Raw Web URL in Spoken Audio Script",
                        explanation="Direct URLs cannot be spoken smoothly by IVR text-to-speech synthesizers. Citizens cannot click audio links.",
                        affected_text=affected,
                        suggested_correction="Replace raw web URLs with a spoken telephone helpline or state the official website name plainly (e.g., 'visit our state disaster website').",
                        evaluation_source=EvaluationSource.DETERMINISTIC,
                        confidence=0.95,
                        rule_id="RULE-CHAN-VOICE-002",
                    )
                )

            has_md_warning = any(w.code == "VOICE_CONTAINS_MARKDOWN" for w in metrics.warnings)
            if has_md_warning:
                findings.append(
                    ContentQualityFindingDTO(
                        category=FindingCategory.CHANNEL,
                        severity=FindingSeverity.LOW,
                        title="Markdown Formatting in Voice Audio Script",
                        explanation="Markdown syntax like '###' or '**' may be literally read aloud by speech synthesizers.",
                        affected_text="Markdown formatting detected",
                        suggested_correction="Remove markdown headings, bullets, and bold markers from voice scripts.",
                        evaluation_source=EvaluationSource.DETERMINISTIC,
                        confidence=0.9,
                        rule_id="RULE-CHAN-VOICE-003",
                    )
                )

    @classmethod
    def _check_factual_anchors(
        cls,
        body: str,
        reference_facts: Optional[str],
        parent_body: Optional[str],
        findings: List[ContentQualityFindingDTO],
    ) -> None:
        source_reference = reference_facts or parent_body
        if not source_reference or not body:
            return

        ref_helplines = extract_numbers_and_helplines(source_reference)
        body_helplines = extract_numbers_and_helplines(body)

        # Check if critical emergency numbers mentioned in facts are missing from body
        missing_helplines = ref_helplines - body_helplines
        # Only flag if there are numbers in facts that look like helpline numbers
        for num in missing_helplines:
            if num in ("1070", "104", "108", "112", "100", "101", "102", "1098"):
                findings.append(
                    ContentQualityFindingDTO(
                        category=FindingCategory.FACTUAL,
                        severity=FindingSeverity.CRITICAL,
                        title=f"Critical Emergency Helpline '{num}' Omitted",
                        explanation=f"Official helpline number '{num}' was specified in the reference facts but was dropped or omitted in the message copy.",
                        affected_text=num,
                        suggested_correction=f"Reinstate the verified emergency contact '{num}' directly into the message text.",
                        evaluation_source=EvaluationSource.DETERMINISTIC,
                        confidence=1.0,
                        rule_id="RULE-FACT-001",
                    )
                )

        # Check if translation altered any dates
        if parent_body:
            parent_dates = set(DATE_REGEX.findall(parent_body))
            body_dates = set(DATE_REGEX.findall(body))
            missing_dates = parent_dates - body_dates
            if missing_dates:
                findings.append(
                    ContentQualityFindingDTO(
                        category=FindingCategory.FACTUAL,
                        severity=FindingSeverity.HIGH,
                        title="Possible Date Alteration or Omission in Translation",
                        explanation=f"Dates found in original copy {list(missing_dates)} do not appear in the translated output.",
                        affected_text=", ".join(list(missing_dates)),
                        suggested_correction="Confirm that official deadlines, meeting dates, or schedule dates are preserved exactly.",
                        evaluation_source=EvaluationSource.DETERMINISTIC,
                        confidence=0.8,
                        rule_id="RULE-FACT-002",
                    )
                )

    @classmethod
    def _check_sensitive_content(
        cls,
        combined_text: str,
        findings: List[ContentQualityFindingDTO],
    ) -> None:
        for pattern, explanation in PANIC_WORDS:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                findings.append(
                    ContentQualityFindingDTO(
                        category=FindingCategory.SAFETY_SENSITIVE,
                        severity=FindingSeverity.CRITICAL,
                        title="Potential Panic-Inducing or Sensitive Phrasing Detected",
                        explanation=f"{explanation}: matched '{match.group(0)}'. Public awareness messages must inform citizens without inciting panic or making unverified claims.",
                        affected_text=match.group(0),
                        suggested_correction="Rephrase using objective, calm, and informative guidance.",
                        evaluation_source=EvaluationSource.DETERMINISTIC,
                        confidence=0.95,
                        rule_id="RULE-SAFE-001",
                    )
                )

    @classmethod
    def _check_readability(
        cls,
        body: str,
        source_language: str,
        findings: List[ContentQualityFindingDTO],
    ) -> None:
        if not body:
            return

        # Sentence length analysis
        # Sentences split by periods, exclamation, questions
        raw_sentences = [s.strip() for s in re.split(r"[.!?।]+", body) if s.strip()]
        for sentence in raw_sentences:
            words = sentence.split()
            if len(words) > 35:
                findings.append(
                    ContentQualityFindingDTO(
                        category=FindingCategory.READABILITY,
                        severity=FindingSeverity.MEDIUM,
                        title="Overly Long Sentence (Exceeds 35 words)",
                        explanation="Long compound sentences reduce reading comprehension among diverse citizen literacy levels.",
                        affected_text=sentence[:80] + "..." if len(sentence) > 80 else sentence,
                        suggested_correction="Split this compound sentence into two concise, direct statements.",
                        evaluation_source=EvaluationSource.DETERMINISTIC,
                        confidence=0.85,
                        rule_id="RULE-READ-001",
                    )
                )
                break  # Flag at most one to prevent noise

    @classmethod
    def _map_severity(cls, sev_str: str) -> FindingSeverity:
        clean = (sev_str or "critical").lower().strip()
        if clean in ("info", "informational"):
            return FindingSeverity.INFORMATIONAL
        try:
            return FindingSeverity(clean)
        except ValueError:
            return FindingSeverity.CRITICAL

    @classmethod
    def _check_compliance_rules(
        cls,
        combined_text: str,
        channel: str,
        effective_language: str,
        compliance_rules: Optional[List[Any]],
        findings: List[ContentQualityFindingDTO],
    ) -> None:
        if not compliance_rules or not combined_text:
            return

        for rule in compliance_rules:
            if getattr(rule, "is_active", True) is False:
                continue

            # Channel constraint check
            rule_chan = getattr(rule, "channel", None)
            if rule_chan and channel and rule_chan.lower() != channel.lower():
                continue

            # Language constraint check
            rule_lang = getattr(rule, "language", None)
            if rule_lang and effective_language and rule_lang.lower() != effective_language.lower():
                continue

            rule_type = getattr(rule, "rule_type", "banned_word").lower()
            pattern = getattr(rule, "pattern", "")
            rule_code = getattr(rule, "rule_code", "COMP-DYNAMIC")
            rule_name = getattr(rule, "name", "Compliance Rule")
            description = getattr(rule, "description", None)
            suggested_action = getattr(rule, "suggested_action", None)
            severity = cls._map_severity(getattr(rule, "severity", "critical"))

            if rule_type == "banned_word":
                clean_pattern = pattern.strip()
                if not clean_pattern:
                    continue
                # Word-boundary matching using \b and re.escape
                regex_str = rf"(?:\b|^){re.escape(clean_pattern)}(?:\b|$)"
                match = re.search(regex_str, combined_text, re.IGNORECASE)
                if match:
                    findings.append(
                        ContentQualityFindingDTO(
                            category=FindingCategory.SAFETY_SENSITIVE,
                            severity=severity,
                            title=f"Prohibited Vocabulary Detected: '{rule_name}'",
                            explanation=description or f"Content contains prohibited term '{match.group(0)}' in violation of compliance policy.",
                            affected_text=match.group(0),
                            suggested_correction=suggested_action or f"Remove or replace prohibited term '{clean_pattern}'.",
                            evaluation_source=EvaluationSource.DETERMINISTIC,
                            confidence=1.0,
                            rule_id=rule_code,
                        )
                    )

            elif rule_type == "mandatory_phrase":
                clean_pattern = pattern.strip()
                if not clean_pattern:
                    continue
                # Case-insensitive substring/phrase presence check
                if clean_pattern.lower() not in combined_text.lower():
                    findings.append(
                        ContentQualityFindingDTO(
                            category=FindingCategory.COMPLETENESS,
                            severity=severity,
                            title=f"Missing Mandatory Phrase: '{rule_name}'",
                            explanation=description or f"Required compliance phrase '{clean_pattern}' was not found in the content.",
                            affected_text=None,
                            suggested_correction=suggested_action or f"Include mandatory phrase: '{clean_pattern}'.",
                            evaluation_source=EvaluationSource.DETERMINISTIC,
                            confidence=1.0,
                            rule_id=rule_code,
                        )
                    )

            elif rule_type == "regex_pattern":
                clean_pattern = pattern.strip()
                if not clean_pattern:
                    continue
                try:
                    match = re.search(clean_pattern, combined_text, re.IGNORECASE)
                    if match:
                        findings.append(
                            ContentQualityFindingDTO(
                                category=FindingCategory.SAFETY_SENSITIVE,
                                severity=severity,
                                title=f"Compliance Pattern Match: '{rule_name}'",
                                explanation=description or f"Content matched prohibited pattern.",
                                affected_text=match.group(0),
                                suggested_correction=suggested_action or "Modify copy to comply with pattern requirements.",
                                evaluation_source=EvaluationSource.DETERMINISTIC,
                                confidence=1.0,
                                rule_id=rule_code,
                            )
                        )
                except re.error:
                    pass


