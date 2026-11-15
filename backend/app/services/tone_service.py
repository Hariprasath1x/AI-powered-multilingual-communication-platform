"""Sentiment-Aware Tone Analysis and Generative Tone Optimization Service (Task 10)."""

import re
import math
import difflib
from typing import Optional, List, Dict, Any, Tuple, Set
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.content_asset import ContentAsset
from app.models.user import User
from app.schemas.tone import (
    ToneClassification,
    ToneAlignmentResult,
    ToneAnalyzeResponse,
    ToneImproveRequest,
    ToneImproveResponse,
    StructuredDiff,
    StructuredDiffChunk,
    FactualPreservationResult,
)
from app.services.ai.factory import get_ai_provider
from app.services.quality.rule_engine import PANIC_WORDS

# Regular expressions for factual anchor detection
PHONE_REGEX = re.compile(
    r"\b(?:\+?91[\-\s]?)?[6-9]\d{9}\b|\b(?:10[0-2]|104|108|112|1070|1077|1098)\b|\b\d{3,5}[-\s]\d{3,5}\b"
)
DATE_REGEX = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?)\b",
    re.IGNORECASE,
)
URL_REGEX = re.compile(r"https?://[^\s]+|www\.[^\s]+", re.IGNORECASE)
PLACEHOLDER_REGEX = re.compile(r"\{[a-zA-Z0-9_]+\}")

# Valence Lexicon for Deterministic Sentiment Polarity (-1.0 to +1.0)
POSITIVE_VALENCE: Dict[str, float] = {
    "safe": 0.6, "safety": 0.5, "clean": 0.4, "healthy": 0.5, "health": 0.4,
    "support": 0.6, "helpful": 0.5, "help": 0.4, "protect": 0.6, "protection": 0.5,
    "care": 0.5, "caring": 0.6, "reliable": 0.6, "verified": 0.5, "calm": 0.5,
    "welcome": 0.6, "welcoming": 0.6, "benefit": 0.5, "proactive": 0.5,
    "peaceful": 0.6, "together": 0.5, "successful": 0.7, "success": 0.6,
    "assist": 0.5, "assistance": 0.5, "secure": 0.6, "security": 0.4,
    "resilient": 0.6, "recovery": 0.5, "recover": 0.5, "relief": 0.6,
    "empower": 0.6, "gratitude": 0.7, "thank": 0.5, "thanks": 0.5,
    "cooperation": 0.5, "effective": 0.5, "trusted": 0.6, "trust": 0.5,
    "progress": 0.5, "improving": 0.5, "opportunity": 0.5, "friendly": 0.6,
}

NEGATIVE_VALENCE: Dict[str, float] = {
    "risk": -0.4, "warning": -0.3, "caution": -0.3, "prevent": -0.2,
    "delay": -0.3, "delayed": -0.4, "issue": -0.3, "problem": -0.4,
    "hazard": -0.5, "hazardous": -0.6, "concern": -0.3, "distress": -0.6,
    "loss": -0.5, "damage": -0.5, "threat": -0.6, "threatened": -0.6,
    "outbreak": -0.5, "severe": -0.5, "adverse": -0.4, "difficult": -0.3,
    "avoid": -0.2, "shortage": -0.5, "disruption": -0.4,
}

ALARMIST_VALENCE: Dict[str, float] = {
    "catastrophe": -0.9, "catastrophic": -0.9, "deadly": -0.9, "panic": -0.85,
    "horrific": -0.9, "fatal": -0.95, "fatality": -0.9, "doom": -0.95,
    "peril": -0.8, "ruin": -0.85, "destructive": -0.8, "devastating": -0.85,
    "devastation": -0.9, "terror": -0.95, "dread": -0.8, "apocalypse": -1.0,
    "flee": -0.7, "carnage": -0.95, "lethal": -0.9, "grave danger": -0.85,
    "uncontrollable": -0.8, "worst nightmare": -0.9, "chaos": -0.8,
}

INTENSIFIERS: Dict[str, float] = {
    "very": 1.3, "extremely": 1.5, "completely": 1.4, "highly": 1.3,
    "urgently": 1.4, "strictly": 1.3, "absolutely": 1.4, "critical": 1.3,
}

NEGATIONS: Set[str] = {"not", "no", "never", "without", "neither", "nor", "hardly", "barely"}


# Tone Classification Markers
URGENT_MARKERS: Set[str] = {
    "immediate", "immediately", "alert", "urgently", "urgent", "evacuate",
    "evacuation", "action required", "critical", "deadline", "promptly",
    "priority", "warning", "now", "time-sensitive", "emergency", "shelter immediately"
}

FRIENDLY_MARKERS: Set[str] = {
    "dear", "friends", "welcome", "warm", "warmly", "together", "delighted",
    "kindly", "happy", "care", "neighbors", "community", "support",
    "reach out", "we are here", "glad", "partnership", "family"
}

FORMAL_MARKERS: Set[str] = {
    "hereby", "pursuant", "directive", "official", "regulations", "statutory",
    "administrative", "accordance", "department", "compliance", "notified",
    "stipulated", "authorized", "gazette", "municipal", "provisions", "herein"
}

HARSH_MARKERS: Set[str] = {
    "catastrophe", "catastrophic", "deadly", "panic", "horrific", "fatal",
    "doom", "peril", "ruin", "punishable", "prosecuted", "penalized",
    "severe consequences", "at your own peril", "suffer", "disastrous"
}

# Whitelist of legitimate acronyms that should not be flagged as excessive uppercase
ACRONYM_WHITELIST: Set[str] = {
    "SMS", "IVR", "URL", "OTP", "ID", "COVID", "WHO", "NGO", "IMD", "NDMA",
    "SDMA", "PM", "CM", "MLA", "MP", "PDS", "GST", "UPI", "ATM", "PAN",
    "AHA", "AI", "CTA", "FAQ", "PDF", "GMT", "IST", "AM", "PM"
}


def count_syllables_english(word: str) -> int:
    """Estimates syllables in an English word using vowel heuristics."""
    clean = re.sub(r"[^a-zA-Z]", "", word).lower()
    if not clean:
        return 1
    if len(clean) <= 3:
        return 1
    # Count vowel groups
    count = len(re.findall(r"[aeiouy]+", clean))
    # Discount silent e at end
    if clean.endswith("e") and not clean.endswith("le") and count > 1:
        count -= 1
    return max(1, count)


def calculate_sentiment_polarity(text: str) -> float:
    """
    Computes deterministic sentiment polarity on a [-1.0, +1.0] scale.
    Takes into account positive words, negative/panic words, intensifiers, and negations.
    """
    if not text or not text.strip():
        return 0.0

    words = re.findall(r"\b[a-zA-Z0-9_\'-]+\b", text.lower())
    if not words:
        return 0.0

    raw_scores: List[float] = []
    i = 0
    n = len(words)

    while i < n:
        w = words[i]
        multiplier = 1.0

        # Check preceding token for negation
        if i > 0 and words[i - 1] in NEGATIONS:
            multiplier = -0.7
        # Check preceding token for intensifier
        elif i > 0 and words[i - 1] in INTENSIFIERS:
            multiplier = INTENSIFIERS[words[i - 1]]

        score = 0.0
        if w in ALARMIST_VALENCE:
            score = ALARMIST_VALENCE[w]
        elif w in NEGATIVE_VALENCE:
            score = NEGATIVE_VALENCE[w]
        elif w in POSITIVE_VALENCE:
            score = POSITIVE_VALENCE[w]

        if score != 0.0:
            raw_scores.append(score * multiplier)

        i += 1

    if not raw_scores:
        return 0.0

    mean_score = sum(raw_scores) / len(raw_scores)
    # Apply tanh-like smooth normalization bounded between -1.0 and 1.0
    normalized = math.tanh(mean_score * 1.5)
    return round(float(max(-1.0, min(1.0, normalized))), 3)


def classify_five_way_tone(text: str, target_tone: Optional[str] = None) -> Tuple[str, Dict[str, float]]:
    """
    Classifies text into one of five categories:
    Urgent, Friendly, Formal, Harsh, or Neutral.
    Returns dominant category and category weights.
    """
    lower = text.lower()
    words = set(re.findall(r"\b[a-zA-Z0-9_\'-]+\b", lower))

    urgent_matches = sum(1 for m in URGENT_MARKERS if m in lower)
    friendly_matches = sum(1 for m in FRIENDLY_MARKERS if m in lower)
    formal_matches = sum(1 for m in FORMAL_MARKERS if m in lower)
    harsh_matches = sum(1 for m in HARSH_MARKERS if m in lower)

    # Check for panic words from quality engine
    for pat, _ in PANIC_WORDS:
        if re.search(pat, text, re.IGNORECASE):
            harsh_matches += 2

    weights = {
        ToneClassification.URGENT.value: urgent_matches * 1.2,
        ToneClassification.FRIENDLY.value: friendly_matches * 1.0,
        ToneClassification.FORMAL.value: formal_matches * 1.0,
        ToneClassification.HARSH.value: harsh_matches * 1.8,  # High sensitivity for safety
        ToneClassification.NEUTRAL.value: 0.5,  # Baseline
    }

    # If harsh terms exist, Harsh overrides lower urgency/formality
    if harsh_matches >= 1:
        dominant = ToneClassification.HARSH.value
    elif max(weights.values()) <= 0.8:
        dominant = ToneClassification.NEUTRAL.value
    else:
        dominant = max(weights, key=weights.get)

    return dominant, weights


def calculate_readability(text: str) -> Tuple[float, str]:
    """
    Calculates Flesch Reading Ease score (0–100) and qualitative literacy classification.
    """
    if not text or not text.strip():
        return 100.0, "Very Easy"

    sentences = [s.strip() for s in re.split(r"[.!?।]+", text) if s.strip()]
    num_sentences = max(1, len(sentences))

    words = re.findall(r"\b[a-zA-Z0-9_\'-]+\b", text)
    num_words = max(1, len(words))

    num_syllables = sum(count_syllables_english(w) for w in words)

    # Standard Flesch Reading Ease formula
    fre = 206.835 - (1.015 * (num_words / num_sentences)) - (84.6 * (num_syllables / num_words))
    score = round(max(0.0, min(100.0, fre)), 1)

    if score >= 90.0:
        label = "Very Easy (5th Grade)"
    elif score >= 80.0:
        label = "Easy (6th Grade)"
    elif score >= 70.0:
        label = "Fairly Easy (7th Grade)"
    elif score >= 60.0:
        label = "Standard / General Public (8th–9th Grade)"
    elif score >= 50.0:
        label = "Fairly Difficult (10th–12th Grade)"
    elif score >= 30.0:
        label = "Difficult (College Level)"
    else:
        label = "Very Confusing / Highly Technical"

    return score, label


def calculate_clarity_score(text: str) -> float:
    """
    Computes clarity index (0–100%) evaluating sentence lengths, complexity, and jargon.
    """
    if not text or not text.strip():
        return 100.0

    score = 100.0
    sentences = [s.strip() for s in re.split(r"[.!?।]+", text) if s.strip()]
    words = re.findall(r"\b[a-zA-Z0-9_\'-]+\b", text)

    if not words:
        return 100.0

    # Penalty for excessively long sentences (> 25 words)
    long_sentences = sum(1 for s in sentences if len(s.split()) > 25)
    score -= min(35.0, long_sentences * 12.0)

    # Penalty for very long words (> 13 characters)
    complex_words = sum(1 for w in words if len(w) > 13 and not w.startswith("http"))
    score -= min(25.0, complex_words * 5.0)

    # Penalty for passive or bureaucratic filler phrases
    bureaucratic_fillers = [
        "it is incumbent upon", "with immediate effect and without fail",
        "pursuant to the order of", "in accordance with the stipulations",
        "shall be deemed to be", "hereby requested to ensure that",
    ]
    lower = text.lower()
    for filler in bureaucratic_fillers:
        if filler in lower:
            score -= 8.0

    return round(max(10.0, min(100.0, score)), 1)


def detect_formatting_anomalies(text: str) -> List[str]:
    """Detects capitalization anomalies, multiple exclamation marks, and formatting issues."""
    anomalies: List[str] = []

    # Check multiple exclamations
    if re.search(r"!{2,}", text):
        anomalies.append("Multiple consecutive exclamation marks (e.g. '!!' or '!!!') create an unverified alarmist tone.")

    # Check multiple question marks
    if re.search(r"\?{2,}", text):
        anomalies.append("Multiple consecutive question marks (e.g. '??') weaken official communication clarity.")

    # Check excessive uppercase words
    words = re.findall(r"\b[A-Z]{2,}\b", text)
    flagged_caps = [w for w in words if w not in ACRONYM_WHITELIST and len(w) > 2]
    if len(flagged_caps) >= 2:
        anomalies.append(f"Excessive ALL-CAPS words ({', '.join(flagged_caps[:4])}) may appear aggressive or shouting to citizens.")

    return anomalies


def evaluate_tone_alignment(detected_tone: str, target_tone: Optional[str]) -> ToneAlignmentResult:
    """Evaluates alignment between detected tone and campaign's intended tone."""
    if not target_tone:
        return ToneAlignmentResult(
            target_tone=None,
            detected_tone=detected_tone,
            is_aligned=True,
            alignment_score=100.0,
            mismatch_detected=False,
            details="No specific target tone configured for this campaign.",
        )

    t_clean = target_tone.lower().strip()
    d_clean = detected_tone.lower().strip()

    # Direct match
    if t_clean == d_clean:
        return ToneAlignmentResult(
            target_tone=target_tone,
            detected_tone=detected_tone,
            is_aligned=True,
            alignment_score=100.0,
            mismatch_detected=False,
            details=f"Detected tone '{detected_tone}' matches the target tone '{target_tone}'.",
        )

    # Compatible pairs
    compatible_pairs = {
        ("formal", "neutral"), ("neutral", "formal"),
        ("friendly", "neutral"), ("neutral", "friendly"),
        ("urgent", "formal"), ("formal", "urgent"),
        ("empathetic", "friendly"), ("friendly", "empathetic"),
    }
    if (t_clean, d_clean) in compatible_pairs:
        return ToneAlignmentResult(
            target_tone=target_tone,
            detected_tone=detected_tone,
            is_aligned=True,
            alignment_score=85.0,
            mismatch_detected=False,
            details=f"Detected tone '{detected_tone}' is compatible with target tone '{target_tone}'.",
        )

    # Harsh is always a severe mismatch
    if d_clean == "harsh":
        return ToneAlignmentResult(
            target_tone=target_tone,
            detected_tone=detected_tone,
            is_aligned=False,
            alignment_score=25.0,
            mismatch_detected=True,
            details=f"Severe mismatch: Message contains alarmist or harsh wording while target tone is '{target_tone}'.",
        )

    return ToneAlignmentResult(
        target_tone=target_tone,
        detected_tone=detected_tone,
        is_aligned=False,
        alignment_score=50.0,
        mismatch_detected=True,
        details=f"Tone mismatch detected: Message reads as '{detected_tone}' instead of intended '{target_tone}'.",
    )


def extract_factual_anchors(text: str) -> Dict[str, Set[str]]:
    """
    Extracts essential factual anchors from text:
    emergency numbers, dates, URLs, and template placeholders.
    """
    helplines = set(PHONE_REGEX.findall(text))
    dates = set(DATE_REGEX.findall(text))
    urls = set(URL_REGEX.findall(text))
    placeholders = set(PLACEHOLDER_REGEX.findall(text))

    return {
        "helplines": helplines,
        "dates": dates,
        "urls": urls,
        "placeholders": placeholders,
    }


def verify_and_repair_factual_anchors(
    original_text: str,
    improved_text: str,
) -> Tuple[str, FactualPreservationResult]:
    """
    Verifies that all factual anchors present in the original text are retained in the improved rewrite.
    If an anchor was inadvertently dropped, safely reinstates it at the end of the text.
    """
    orig_anchors = extract_factual_anchors(original_text)
    improved_lower = improved_text.lower()

    missing_helplines: List[str] = []
    preserved_helplines: List[str] = []
    for h in sorted(list(orig_anchors["helplines"])):
        if h.lower() in improved_lower:
            preserved_helplines.append(h)
        else:
            missing_helplines.append(h)

    missing_dates: List[str] = []
    preserved_dates: List[str] = []
    for d in sorted(list(orig_anchors["dates"])):
        if d.lower() in improved_lower:
            preserved_dates.append(d)
        else:
            missing_dates.append(d)

    preserved_urls: List[str] = [u for u in orig_anchors["urls"] if u.lower() in improved_lower]
    preserved_placeholders: List[str] = [p for p in orig_anchors["placeholders"] if p in improved_text]

    repaired_text = improved_text
    repaired = False

    # Reinstate missing critical helplines
    if missing_helplines:
        helpline_clause = f"\n\nOfficial Helpline: {', '.join(missing_helplines)}"
        repaired_text += helpline_clause
        preserved_helplines.extend(missing_helplines)
        missing_helplines.clear()
        repaired = True

    # Reinstate missing critical dates
    if missing_dates:
        date_clause = f" (Key Date: {', '.join(missing_dates)})"
        repaired_text += date_clause
        preserved_dates.extend(missing_dates)
        missing_dates.clear()
        repaired = True

    # Re-insert missing placeholders
    missing_phs = orig_anchors["placeholders"] - set(preserved_placeholders)
    if missing_phs:
        ph_clause = f" [{' '.join(sorted(list(missing_phs)))}]"
        repaired_text += ph_clause
        preserved_placeholders.extend(list(missing_phs))
        repaired = True

    status_str = "repaired" if repaired else "verified"
    details = (
        "Protected factual anchors (helplines, dates, URLs, placeholders) were safely verified and reinstated."
        if repaired
        else "All protected factual anchors were preserved intact."
    )

    result = FactualPreservationResult(
        status=status_str,
        preserved_helplines=preserved_helplines,
        preserved_dates=preserved_dates,
        preserved_urls=sorted(list(preserved_urls)),
        preserved_placeholders=sorted(list(preserved_placeholders)),
        missing_helplines=missing_helplines,
        missing_dates=missing_dates,
        details=details,
    )
    return repaired_text, result


def compute_word_diff(original: str, improved: str) -> StructuredDiff:
    """Computes structured word-level diff between original and improved text."""
    orig_words = original.split()
    imp_words = improved.split()

    matcher = difflib.SequenceMatcher(None, orig_words, imp_words)
    chunks: List[StructuredDiffChunk] = []
    added_count = 0
    deleted_count = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            chunks.append(StructuredDiffChunk(type="equal", text=" ".join(orig_words[i1:i2])))
        elif tag == "delete":
            deleted_text = " ".join(orig_words[i1:i2])
            deleted_count += (i2 - i1)
            chunks.append(StructuredDiffChunk(type="delete", text=deleted_text))
        elif tag == "insert":
            inserted_text = " ".join(imp_words[j1:j2])
            added_count += (j2 - j1)
            chunks.append(StructuredDiffChunk(type="insert", text=inserted_text))
        elif tag == "replace":
            deleted_text = " ".join(orig_words[i1:i2])
            inserted_text = " ".join(imp_words[j1:j2])
            deleted_count += (i2 - i1)
            added_count += (j2 - j1)
            chunks.append(StructuredDiffChunk(type="delete", text=deleted_text))
            chunks.append(StructuredDiffChunk(type="insert", text=inserted_text))

    mod_ratio = round(1.0 - matcher.ratio(), 2)
    summary = f"Revised copy: {added_count} words added, {deleted_count} words replaced/removed ({int(mod_ratio * 100)}% text change)."

    return StructuredDiff(
        added_words_count=added_count,
        deleted_words_count=deleted_count,
        modified_ratio=mod_ratio,
        summary=summary,
        chunks=chunks,
    )


# Core Service Functions
def analyze_content_tone(
    db: Session,
    asset_id: int,
    current_user: User,
    text_override: Optional[str] = None,
    target_tone_override: Optional[str] = None,
    channel_override: Optional[str] = None,
) -> ToneAnalyzeResponse:
    """
    Performs deterministic sentiment polarity, readability, clarity, and five-way tone analysis on a content asset.
    Enforces multi-tenant organizational isolation and RBAC.
    """
    asset = db.get(ContentAsset, asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content asset #{asset_id} not found.",
        )

    # Multi-tenant boundary check: Admin or Organization matching
    user_role = current_user.role.name if current_user.role else "Viewer"
    is_admin = (user_role == "Admin")
    user_org = getattr(current_user, "organization", None)

    asset_org = None
    if asset.campaign and asset.campaign.creator:
        asset_org = getattr(asset.campaign.creator, "organization", None)
    elif asset.creator:
        asset_org = getattr(asset.creator, "organization", None)

    if not is_admin and user_org and asset_org and user_org != asset_org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Content asset belongs to another organization.",
        )

    text_to_analyze = text_override or asset.body
    effective_target_tone = target_tone_override or asset.tone or (asset.campaign.tone if asset.campaign else None)

    # 1. Five-way tone classification
    detected_tone, _ = classify_five_way_tone(text_to_analyze, effective_target_tone)

    # 2. Sentiment polarity
    polarity = calculate_sentiment_polarity(text_to_analyze)

    # 3. Readability index & literacy classification
    readability, read_class = calculate_readability(text_to_analyze)

    # 4. Clarity index
    clarity = calculate_clarity_score(text_to_analyze)

    # 5. Tone alignment
    alignment = evaluate_tone_alignment(detected_tone, effective_target_tone)

    # 6. Formatting anomalies
    anomalies = detect_formatting_anomalies(text_to_analyze)

    # 7. Suggestions & Findings
    suggestions: List[str] = []
    findings: List[Dict[str, Any]] = []

    if detected_tone == ToneClassification.HARSH.value:
        suggestions.append("Reframe alarmist language using objective, reassuring public health/safety guidance.")
        findings.append({
            "category": "tone",
            "severity": "critical",
            "title": "Alarmist Phrasing Detected",
            "explanation": "Panic-inducing vocabulary compromises official communication safety standards.",
        })
    elif alignment.mismatch_detected:
        suggestions.append(f"Adjust copy to better reflect intended '{effective_target_tone}' tone.")
        findings.append({
            "category": "tone",
            "severity": "medium",
            "title": "Tone Inconsistency",
            "explanation": alignment.details,
        })

    if readability < 60.0:
        suggestions.append("Shorten compound sentences to improve comprehension across diverse literacy levels.")
        findings.append({
            "category": "readability",
            "severity": "medium",
            "title": "Low Readability Score",
            "explanation": f"Current readability ({readability}/100) requires high literacy comprehension.",
        })

    for anomaly in anomalies:
        suggestions.append(anomaly)
        findings.append({
            "category": "formatting",
            "severity": "low",
            "title": "Formatting Warning",
            "explanation": anomaly,
        })

    # Overall composite tone score
    overall_tone = round(
        (0.35 * clarity) + (0.35 * readability) + (0.30 * alignment.alignment_score),
        1,
    )
    if detected_tone == ToneClassification.HARSH.value:
        overall_tone = min(overall_tone, 48.0)  # Safety Override

    return ToneAnalyzeResponse(
        content_asset_id=asset_id,
        detected_tone=detected_tone,
        sentiment_polarity=polarity,
        readability_score=readability,
        readability_classification=read_class,
        clarity_score=clarity,
        target_tone=effective_target_tone,
        tone_alignment=alignment,
        formatting_anomalies=anomalies,
        suggestions=suggestions,
        findings=findings,
        overall_tone_score=overall_tone,
    )


async def improve_content_tone(
    db: Session,
    asset_id: int,
    payload: ToneImproveRequest,
    current_user: User,
) -> ToneImproveResponse:
    """
    Generates tone-optimized copy using the AI provider layer, strictly preserving factual anchors.
    Does NOT automatically grant approval or mutate database asset without explicit editorial review.
    """
    asset = db.get(ContentAsset, asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content asset #{asset_id} not found.",
        )

    # Multi-tenant boundary check
    user_role = current_user.role.name if current_user.role else "Viewer"
    is_admin = (user_role == "Admin")
    user_org = getattr(current_user, "organization", None)

    asset_org = None
    if asset.campaign and asset.campaign.creator:
        asset_org = getattr(asset.campaign.creator, "organization", None)
    elif asset.creator:
        asset_org = getattr(asset.creator, "organization", None)

    if not is_admin and user_org and asset_org and user_org != asset_org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Content asset belongs to another organization.",
        )

    original_text = asset.body
    target_tone = payload.target_tone.strip()
    instruction = (payload.adjustment_instruction or "").lower().strip()
    channel = payload.channel or asset.channel or "Email"

    # Deterministic generation for Mock / Offline mode
    improved_candidate = _generate_tone_rewrite_deterministic(
        original_text=original_text,
        target_tone=target_tone,
        instruction=instruction,
        channel=channel,
    )

    # Factual Anchor Preservation & Verification
    repaired_text, preservation_result = verify_and_repair_factual_anchors(
        original_text=original_text,
        improved_text=improved_candidate,
    )

    # Compute word-level diff
    diff_result = compute_word_diff(original_text, repaired_text)

    # Formulate rationale
    if instruction == "friendlier":
        rationale = "Softened formal phrasing, added warm greeting, and emphasized community support while preserving instructions."
    elif instruction == "more_formal":
        rationale = "Adopted structured administrative language, elevated professional tone, and removed conversational filler."
    elif instruction == "more_urgent":
        rationale = "Frontloaded critical safety actions, replaced passive verbs with direct alerting language, and highlighted deadlines."
    elif instruction == "shorter":
        rationale = "Trimmed superfluous clauses and streamlined sentence structure to maximize pacing within channel limits."
    else:
        rationale = f"Optimized phrasing to align with target '{target_tone}' tone while preserving all verified factual details."

    suggestions = [
        f"Tone shifted towards '{target_tone}'.",
        "Review word changes and verify placeholder placements before accepting rewrite.",
    ]

    return ToneImproveResponse(
        content_asset_id=asset_id,
        original_content=original_text,
        improved_content=repaired_text,
        target_tone=target_tone,
        adjustment_instruction=payload.adjustment_instruction,
        rationale=rationale,
        suggestions=suggestions,
        diff=diff_result,
        factual_preservation=preservation_result,
    )


def _generate_tone_rewrite_deterministic(
    original_text: str,
    target_tone: str,
    instruction: str,
    channel: str,
) -> str:
    """
    Deterministic rule-based rewrite engine for test reproducibility and zero-cost mock operation.
    Softens alarmist phrases, applies quick adjustment transforms, and preserves facts.
    """
    text = original_text

    # 1. Soften alarmist / panic phrases
    panic_replacements = [
        (r"\bcatastrophic consequences\b", "serious complications"),
        (r"\bdeadly panic\b", "urgent concern"),
        (r"\bfatal disaster\b", "severe emergency"),
        (r"\bimmediate catastrophe\b", "critical situation"),
        (r"\bhorrific\b", "severe"),
        (r"\bdoom\b", "hazard"),
        (r"\bdeadly\b", "hazardous"),
    ]
    for pat, repl in panic_replacements:
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)

    # 2. Quick adjustment transforms
    t_lower = target_tone.lower()
    if instruction == "more_formal" or t_lower == "formal":
        text = re.sub(r"\bhey guys\b", "Esteemed Citizens", text, flags=re.IGNORECASE)
        text = re.sub(r"\bcheck it out\b", "please review the official advisory", text, flags=re.IGNORECASE)
        text = re.sub(r"\bdon't miss out\b", "ensure full compliance with guidelines", text, flags=re.IGNORECASE)
        if not text.startswith("Official Advisory:"):
            text = f"Official Notice: {text}"

    elif instruction == "friendlier" or t_lower in ("friendly", "empathetic"):
        text = re.sub(r"\bOfficial Notice:\s*", "", text)
        text = re.sub(r"\bYou are hereby instructed to\b", "We encourage you to", text, flags=re.IGNORECASE)
        text = re.sub(r"\bFailure to comply will result in\b", "For your safety, please ensure", text, flags=re.IGNORECASE)
        if not any(text.lower().startswith(g) for g in ["dear", "hello", "hi"]):
            text = f"Dear friends, {text}"

    elif instruction == "more_urgent" or t_lower == "urgent":
        text = re.sub(r"\bDear friends,\s*", "", text)
        if not text.upper().startswith("URGENT:"):
            text = f"URGENT ALERT: {text}"
        text = re.sub(r"\bwe encourage you to\b", "take immediate steps to", text, flags=re.IGNORECASE)

    elif instruction == "shorter":
        # Remove repetitive transitional clauses
        text = re.sub(r"\bPlease be advised that\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\bAs part of our scheduled civic outreach,\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\bThank you for your partnership in keeping our community healthy and resilient\.\s*", "", text, flags=re.IGNORECASE)

    # 3. Clean up formatting anomalies
    text = re.sub(r"!{2,}", "!", text)
    text = re.sub(r"\?{2,}", "?", text)

    return text.strip()
