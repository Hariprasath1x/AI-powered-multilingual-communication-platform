"""
MassCommAI - Centralized Channel Constraints & Telecom Analysis Engine.

Provides deterministic, telecom-accurate channel constraint analysis:
- Full GSM 03.38 basic character set and extension table analysis
- Single-part and concatenated (multipart) SMS segmentation boundaries (160/153 and 70/67)
- Unicode UTF-16 code unit counting for UCS-2 compatible estimates and surrogate pair detection
- Language-aware Voice audio script duration estimation with punctuation pause factors
- Cross-channel constraint evaluation and structured warnings for SMS, Voice, WhatsApp, and Email
- Zero database, zero network, zero AI dependencies
"""

import math
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class SMSEncoding(str, Enum):
    """SMS PDU character encoding schemes."""
    GSM7 = "GSM-7"
    UCS2 = "UCS-2"


class WarningSeverity(str, Enum):
    """Standardized finding severities for channel constraint warnings."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


# =============================================================================
# GSM 03.38 Character Sets (Lookup Tables)
# =============================================================================

# GSM 03.38 Basic Character Set (127 characters, each consuming 1 septet).
# ESC (0x1B) is deliberately excluded from valid basic characters: an isolated
# escape byte in user copy does not represent a valid standalone character and
# forces UCS-2 analysis.
GSM7_BASIC_CHARS: frozenset[str] = frozenset(
    # Control / Line Feeds
    "\n\r "
    # Basic Latin Letters & Digits
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    # Punctuation & Standard ASCII Symbols in GSM-7
    "!\"#$%&'()*+,-./:;<=>?@"
    "_"
    # Greek Capital Letters with distinct GSM-7 code points
    "ΔΦΓΛΩΠΨΣΘΞ"
    # Non-ASCII Latin Characters & Currency Symbols in GSM-7 Basic Table
    "£¥èéùìòÇØøÅåÆæßÉ¤¡ÄÖÑÜ§¿äöñüà"
)

# GSM 03.38 Extension Table (10 characters, each requiring an 0x1B ESC prefix
# in telecom transmission, thus consuming 2 septets each).
GSM7_EXTENSION_CHARS: frozenset[str] = frozenset(
    "\f^{}\\[~]|€"
)

# Combined GSM-7 Alphabet
GSM7_ALL_CHARS: frozenset[str] = GSM7_BASIC_CHARS | GSM7_EXTENSION_CHARS

# Telecom Segmentation Constants (3GPP TS 23.038 / TS 23.040)
GSM7_SINGLE_SEGMENT_LIMIT = 160  # septets
GSM7_MULTIPART_SEGMENT_LIMIT = 153  # septets (160 - 7 octets for 6-byte UDH)

UCS2_SINGLE_SEGMENT_LIMIT = 70  # UTF-16 code units (140 octets / 2)
UCS2_MULTIPART_SEGMENT_LIMIT = 67  # UTF-16 code units (134 octets / 2, after 6-byte UDH)

# Default Policy Thresholds
DEFAULT_SMS_HARD_LIMIT_CHARS = 1600
DEFAULT_SMS_MAX_RECOMMENDED_SEGMENTS = 3
DEFAULT_VOICE_MAX_RECOMMENDED_SECONDS = 90
DEFAULT_WHATSAPP_FREEFORM_HARD_LIMIT_CHARS = 4096
DEFAULT_WHATSAPP_RECOMMENDED_LIMIT_CHARS = 1024
DEFAULT_WHATSAPP_TEMPLATE_LIMIT_CHARS = 1024
DEFAULT_EMAIL_SUBJECT_RECOMMENDED_LIMIT_CHARS = 78
DEFAULT_EMAIL_BODY_RECOMMENDED_WORDS = 800
DEFAULT_WEB_TITLE_HARD_LIMIT_CHARS = 255
DEFAULT_WEB_TITLE_RECOMMENDED_CHARS = 100
DEFAULT_WEB_BODY_HARD_LIMIT_CHARS = 4096
DEFAULT_WEB_BODY_RECOMMENDED_CHARS = 500

# Voice speaking rates (Words Per Minute)
DEFAULT_VOICE_WPM: Dict[str, int] = {
    "en": 150,  # ~2.5 words/second
    "hi": 125,  # ~2.08 words/second (Hindi)
    "ta": 115,  # ~1.92 words/second (Tamil agglutinative polysyllables)
    "te": 115,  # ~1.92 words/second (Telugu)
    "kn": 115,  # ~1.92 words/second (Kannada agglutinative cadence)
    "ml": 110,  # ~1.83 words/second (Malayalam compound words)
    "bn": 125,  # ~2.08 words/second (Bengali)
    "mr": 120,  # ~2.00 words/second (Marathi)
    "gu": 125,  # ~2.08 words/second (Gujarati)
    "pa": 125,  # ~2.08 words/second (Punjabi)
    "ur": 125,  # ~2.08 words/second (Urdu)
}
FALLBACK_VOICE_WPM = 130

# Voice punctuation pause markers
VOICE_MAJOR_PAUSE_CHARS: Set[str] = {".", "!", "?", "।"}  # Indic danda included
VOICE_MINOR_PAUSE_CHARS: Set[str] = {",", ";", ":"}

# Voice content inspection regexes
URL_REGEX = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MARKDOWN_REGEX = re.compile(r"(?:#{1,6}\s+|[*_~`]{1,3}|\[.*?\]\(.*?\))")
NUMERIC_HELPLINE_REGEX = re.compile(r"\b(?:\+?\d{1,4}[-.\s]?)?(?:\d{3,5}|\d{10,12})\b")


# =============================================================================
# Data Transfer Objects
# =============================================================================

@dataclass
class ChannelWarning:
    """Structured, machine-readable channel constraint warning."""
    code: str
    severity: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class SMSDetail:
    """
    Detailed SMS telecom encoding and segmentation metrics.

    Note: Encoding analysis uses UTF-16 code units for UCS-2 compatibility estimates.
    Supplementary characters (e.g., emojis) consume 2 code units. Strict UCS-2 gateways
    may not support supplementary characters; carrier delivery cannot be guaranteed.
    """
    encoding: str
    character_count: int
    encoded_units: int
    segment_count: int
    segment_capacity: int
    remaining_in_segment: int
    is_multipart: bool
    has_extension_characters: bool
    has_surrogate_pairs: bool
    non_gsm_characters: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChannelMetrics:
    """Complete channel simulation and constraint metrics."""
    channel: str
    character_count: int
    word_count: int
    estimated_duration_seconds: Optional[int]
    sms: Optional[SMSDetail]
    is_within_recommended_limit: bool
    is_within_hard_limit: bool
    warnings: List[ChannelWarning] = field(default_factory=list)
    rule_version: str = "v1.0"

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "channel": self.channel,
            "character_count": self.character_count,
            "word_count": self.word_count,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "sms": self.sms.to_dict() if self.sms else None,
            "is_within_recommended_limit": self.is_within_recommended_limit,
            "is_within_hard_limit": self.is_within_hard_limit,
            "warnings": [w.to_dict() for w in self.warnings],
            "rule_version": self.rule_version,
        }
        if self.sms:
            d["encoding"] = self.sms.encoding
            d["encoded_units"] = self.sms.encoded_units
            d["segment_count"] = self.sms.segment_count
        return d


# =============================================================================
# Core Calculation Functions
# =============================================================================

def analyze_sms_encoding(text: str) -> Tuple[SMSEncoding, int, bool, bool, bool, List[str]]:
    """
    Analyze text to determine whether it can be encoded in GSM-7 or requires UCS-2.

    Returns:
        (encoding, encoded_units, has_extension_chars, has_surrogate_pairs, has_unpaired_surrogates, non_gsm_characters)
    """
    if not text:
        return SMSEncoding.GSM7, 0, False, False, False, []

    is_gsm = True
    has_ext = False
    non_gsm_chars: List[str] = []

    # First pass: check whether all characters are in GSM-7 (basic or extension)
    for char in text:
        if char in GSM7_BASIC_CHARS:
            continue
        elif char in GSM7_EXTENSION_CHARS:
            has_ext = True
        else:
            is_gsm = False
            non_gsm_chars.append(char)

    if is_gsm:
        # Each basic char is 1 septet; each extension char is 2 septets
        encoded_units = sum(2 if c in GSM7_EXTENSION_CHARS else 1 for c in text)
        return SMSEncoding.GSM7, encoded_units, has_ext, False, False, []

    # Requires UCS-2-compatible encoding (UTF-16 code units)
    # Deduplicate non-GSM characters while preserving order (bounded to 20 items)
    deduped_non_gsm = list(dict.fromkeys(non_gsm_chars))[:20]

    code_units = 0
    has_surrogates = False
    has_unpaired = False

    for char in text:
        code = ord(char)
        if code >= 0x10000:
            # Supplementary plane (e.g. Emoji): requires 2 UTF-16 code units
            code_units += 2
            has_surrogates = True
        elif 0xD800 <= code <= 0xDFFF:
            # Lone / unpaired surrogate code point
            code_units += 1
            has_unpaired = True
        else:
            # Basic Multilingual Plane (BMP): 1 UTF-16 code unit
            code_units += 1

    return SMSEncoding.UCS2, code_units, has_ext, has_surrogates, has_unpaired, deduped_non_gsm


def calculate_sms_metrics(
    text: str,
    hard_limit_chars: Optional[int] = None,
    max_recommended_segments: Optional[int] = None,
) -> SMSDetail:
    """
    Calculate SMS telecom encoding, encoded units, segment count, and boundary capacities.

    Boundary rules:
    - GSM-7: Single segment = 160 septets. Multipart = 153 septets / segment.
    - UCS-2: Single segment = 70 code units. Multipart = 67 code units / segment.
    - If units <= single_cap: 1 segment.
    - If units > single_cap: ceil(units / multi_cap) segments.
    """
    if text is None:
        text = ""

    char_count = len(text)
    encoding, units, has_ext, has_surrogates, has_unpaired, non_gsm = analyze_sms_encoding(text)

    is_gsm = (encoding == SMSEncoding.GSM7)
    single_cap = GSM7_SINGLE_SEGMENT_LIMIT if is_gsm else UCS2_SINGLE_SEGMENT_LIMIT
    multi_cap = GSM7_MULTIPART_SEGMENT_LIMIT if is_gsm else UCS2_MULTIPART_SEGMENT_LIMIT

    if units == 0:
        segment_count = 0
        segment_capacity = single_cap
        remaining_in_segment = single_cap
        is_multipart = False
    elif units <= single_cap:
        segment_count = 1
        segment_capacity = single_cap
        remaining_in_segment = single_cap - units
        is_multipart = False
    else:
        segment_count = math.ceil(units / multi_cap)
        segment_capacity = multi_cap
        total_capacity = segment_count * multi_cap
        remaining_in_segment = total_capacity - units
        is_multipart = True

    return SMSDetail(
        encoding=encoding.value,
        character_count=char_count,
        encoded_units=units,
        segment_count=segment_count,
        segment_capacity=segment_capacity,
        remaining_in_segment=remaining_in_segment,
        is_multipart=is_multipart,
        has_extension_characters=has_ext,
        has_surrogate_pairs=has_surrogates,
        non_gsm_characters=non_gsm,
    )


def calculate_voice_duration_seconds(
    text: str,
    language: Optional[str] = "en",
    wpm_override: Optional[int] = None,
) -> int:
    """
    Estimate spoken audio duration in seconds based on language-specific speaking rates.

    Accounts for Indic agglutinative syllabic density and modest punctuation pauses.
    Preserves minimum duration floor of 5 seconds.
    """
    if not text or not text.strip():
        return 5

    words = len(text.split())
    if words == 0:
        return 5

    lang = (language or "en").lower().strip()
    wpm = wpm_override or DEFAULT_VOICE_WPM.get(lang, FALLBACK_VOICE_WPM)

    # Base duration from words per minute
    base_duration = (words / wpm) * 60.0

    # Punctuation pause factor (modest deterministic addition, capped at 30% of base)
    major_count = sum(text.count(p) for p in VOICE_MAJOR_PAUSE_CHARS)
    minor_count = sum(text.count(p) for p in VOICE_MINOR_PAUSE_CHARS)
    pause_duration = min(base_duration * 0.3, (major_count * 0.3) + (minor_count * 0.15))

    estimated = math.ceil(base_duration + pause_duration)
    return max(5, estimated)


def normalize_channel(channel: str) -> str:
    """Normalize raw channel string to standard casing."""
    clean = (channel or "").strip()
    low = clean.lower()
    if low == "sms":
        return "SMS"
    elif low == "whatsapp":
        return "WhatsApp"
    elif low == "voice":
        return "Voice"
    elif low == "email":
        return "Email"
    elif low in ("web", "web notification", "web_notification", "webnotification"):
        return "Web"
    return clean.title() if clean else "Unknown"


def calculate_channel_metrics(
    channel: str,
    title: Optional[str] = None,
    body: Optional[str] = None,
    call_to_action: Optional[str] = None,
    language: Optional[str] = "en",
    mode: Optional[str] = None,
    is_template: bool = False,
    sms_hard_limit: Optional[int] = None,
    sms_recommended_segments: Optional[int] = None,
    voice_recommended_seconds: Optional[int] = None,
    whatsapp_hard_limit: Optional[int] = None,
    whatsapp_recommended_chars: Optional[int] = None,
    email_subject_recommended_chars: Optional[int] = None,
    email_body_recommended_words: Optional[int] = None,
) -> ChannelMetrics:
    """
    Calculate comprehensive channel simulation and constraint metrics across channels.

    Returns structured metrics, boundary flags, and typed warnings.
    Does NOT alter, truncate, or normalize the input content.
    """
    norm_channel = normalize_channel(channel)
    clean_title = (title or "").strip()
    clean_body = body or ""
    clean_cta = (call_to_action or "").strip()

    char_count = len(clean_body)
    word_count = len(clean_body.split())

    is_within_recommended = True
    is_within_hard = True
    warnings: List[ChannelWarning] = []

    sms_detail: Optional[SMSDetail] = None
    estimated_duration: Optional[int] = None

    if norm_channel == "SMS":
        hard_limit = sms_hard_limit or DEFAULT_SMS_HARD_LIMIT_CHARS
        max_rec_segs = sms_recommended_segments or DEFAULT_SMS_MAX_RECOMMENDED_SEGMENTS

        sms_detail = calculate_sms_metrics(clean_body)

        # Hard limit check
        if char_count > hard_limit:
            is_within_hard = False
            warnings.append(
                ChannelWarning(
                    code="SMS_HARD_LIMIT_EXCEEDED",
                    severity=WarningSeverity.CRITICAL.value,
                    message=f"SMS message length ({char_count} chars) exceeds the configured application limit of {hard_limit} characters and will likely be rejected by SMS delivery gateways.",
                )
            )

        # Recommended segment check
        if sms_detail.segment_count > max_rec_segs:
            is_within_recommended = False
            warnings.append(
                ChannelWarning(
                    code="SMS_EXCEEDS_RECOMMENDED_SEGMENTS",
                    severity=WarningSeverity.HIGH.value,
                    message=f"Multi-part SMS requires {sms_detail.segment_count} segments (exceeds recommended {max_rec_segs} segments). High segment counts suffer delivery latency and recipient handset fragmentation.",
                )
            )

        # Multipart notice
        if sms_detail.is_multipart:
            warnings.append(
                ChannelWarning(
                    code="SMS_MULTIPART",
                    severity=WarningSeverity.INFO.value,
                    message=f"Message exceeds single-segment capacity and will be sent as a multipart message ({sms_detail.segment_count} segments) using a 6-byte User Data Header per segment.",
                )
            )

        # UCS-2 notice
        if sms_detail.encoding == SMSEncoding.UCS2.value and sms_detail.non_gsm_characters:
            sample = "".join(sms_detail.non_gsm_characters[:5])
            warnings.append(
                ChannelWarning(
                    code="SMS_UCS2_ENCODING",
                    severity=WarningSeverity.INFO.value,
                    message=f"Message contains non-GSM characters ('{sample}') requiring UCS-2 encoding (70 units/segment limit).",
                )
            )

        # Surrogate pairs notice
        if sms_detail.has_surrogate_pairs:
            warnings.append(
                ChannelWarning(
                    code="SMS_SURROGATE_PAIRS",
                    severity=WarningSeverity.LOW.value,
                    message="Message contains supplementary Unicode characters (e.g. emojis) requiring 2 UTF-16 code units. Note: Strict UCS-2 carrier gateways may not support supplementary characters.",
                )
            )

        # Unpaired surrogates warning
        _, _, _, _, has_unpaired, _ = analyze_sms_encoding(clean_body)
        if has_unpaired:
            warnings.append(
                ChannelWarning(
                    code="SMS_UNPAIRED_SURROGATES",
                    severity=WarningSeverity.HIGH.value,
                    message="Message contains invalid or unpaired Unicode surrogate code points.",
                )
            )

    elif norm_channel == "Voice":
        max_rec_seconds = voice_recommended_seconds or DEFAULT_VOICE_MAX_RECOMMENDED_SECONDS
        estimated_duration = calculate_voice_duration_seconds(clean_body, language=language)

        if estimated_duration > max_rec_seconds:
            is_within_recommended = False
            warnings.append(
                ChannelWarning(
                    code="VOICE_EXCEEDS_RECOMMENDED_DURATION",
                    severity=WarningSeverity.HIGH.value,
                    message=f"Voice script duration (~{estimated_duration}s) exceeds the recommended {max_rec_seconds} seconds. Citizen engagement drops significantly on longer IVR calls.",
                )
            )

        # URL check in spoken script
        url_match = URL_REGEX.search(clean_body)
        if url_match:
            warnings.append(
                ChannelWarning(
                    code="VOICE_CONTAINS_URL",
                    severity=WarningSeverity.MEDIUM.value,
                    message=f"Raw web URL detected in spoken audio script ('{url_match.group(0)}'). IVR speech synthesizers cannot speak URLs cleanly and citizens cannot click audio links.",
                )
            )

        # Markdown check
        if MARKDOWN_REGEX.search(clean_body) or "###" in clean_body or "**" in clean_body:
            warnings.append(
                ChannelWarning(
                    code="VOICE_CONTAINS_MARKDOWN",
                    severity=WarningSeverity.LOW.value,
                    message="Markdown formatting detected in voice script. TTS speech synthesizers may literally pronounce markdown syntax.",
                )
            )

        # Numeric helpline check (advisory review)
        helpline_matches = NUMERIC_HELPLINE_REGEX.findall(clean_body)
        if helpline_matches:
            sample_num = helpline_matches[0]
            warnings.append(
                ChannelWarning(
                    code="VOICE_NUMERIC_HELPLINE_ADVISORY",
                    severity=WarningSeverity.INFO.value,
                    message=f"Numeric helpline sequence ('{sample_num}') detected. Verify that TTS pronunciation reads numbers clearly (e.g. digit-by-digit) rather than as large numbers.",
                )
            )

    elif norm_channel == "WhatsApp":
        is_tpl = is_template or (mode == "template")
        hard_limit = whatsapp_hard_limit or DEFAULT_WHATSAPP_FREEFORM_HARD_LIMIT_CHARS
        rec_limit = whatsapp_recommended_chars or DEFAULT_WHATSAPP_RECOMMENDED_LIMIT_CHARS
        tpl_limit = DEFAULT_WHATSAPP_TEMPLATE_LIMIT_CHARS

        if is_tpl:
            if char_count > tpl_limit:
                is_within_hard = False
                is_within_recommended = False
                warnings.append(
                    ChannelWarning(
                        code="WHATSAPP_TEMPLATE_BODY_LIMIT_EXCEEDED",
                        severity=WarningSeverity.CRITICAL.value,
                        message=f"WhatsApp template message body ({char_count} chars) exceeds the Meta 1,024-character template limit.",
                    )
                )
        else:
            if char_count > hard_limit:
                is_within_hard = False
                warnings.append(
                    ChannelWarning(
                        code="WHATSAPP_HARD_LIMIT_EXCEEDED",
                        severity=WarningSeverity.CRITICAL.value,
                        message=f"WhatsApp message length ({char_count} chars) exceeds the configured application limit of {hard_limit} characters.",
                    )
                )
            if char_count > rec_limit:
                is_within_recommended = False
                warnings.append(
                    ChannelWarning(
                        code="WHATSAPP_EXCEEDS_RECOMMENDED_LENGTH",
                        severity=WarningSeverity.MEDIUM.value,
                        message=f"WhatsApp message length ({char_count} chars) exceeds the recommended {rec_limit} characters for optimal mobile readability.",
                    )
                )

    elif norm_channel == "Email":
        rec_subject = email_subject_recommended_chars or DEFAULT_EMAIL_SUBJECT_RECOMMENDED_LIMIT_CHARS
        rec_body_words = email_body_recommended_words or DEFAULT_EMAIL_BODY_RECOMMENDED_WORDS

        # Subject length check (title as subject)
        if len(clean_title) > 255:
            is_within_hard = False
            warnings.append(
                ChannelWarning(
                    code="EMAIL_SUBJECT_HARD_LIMIT_EXCEEDED",
                    severity=WarningSeverity.CRITICAL.value,
                    message=f"Email subject line exceeds database maximum of 255 characters ({len(clean_title)} chars).",
                )
            )
        elif len(clean_title) > rec_subject:
            is_within_recommended = False
            warnings.append(
                ChannelWarning(
                    code="EMAIL_SUBJECT_LENGTH_ADVISORY",
                    severity=WarningSeverity.LOW.value,
                    message=f"Email subject line ({len(clean_title)} chars) exceeds the recommended {rec_subject} characters and may be truncated on mobile viewports.",
                )
            )

        # Body word count check
        if word_count > rec_body_words:
            warnings.append(
                ChannelWarning(
                    code="EMAIL_BODY_LENGTH_ADVISORY",
                    severity=WarningSeverity.INFO.value,
                    message=f"Email body length ({word_count} words) is longer than typical public awareness recommendations (200-800 words). Consider concise formatting to maintain reader engagement.",
                )
            )

    elif norm_channel == "Web":
        rec_title = DEFAULT_WEB_TITLE_RECOMMENDED_CHARS
        hard_title = DEFAULT_WEB_TITLE_HARD_LIMIT_CHARS
        rec_body = DEFAULT_WEB_BODY_RECOMMENDED_CHARS
        hard_body = DEFAULT_WEB_BODY_HARD_LIMIT_CHARS

        # Title checks
        if len(clean_title) > hard_title:
            is_within_hard = False
            warnings.append(
                ChannelWarning(
                    code="WEB_TITLE_HARD_LIMIT_EXCEEDED",
                    severity=WarningSeverity.CRITICAL.value,
                    message=f"Web notification title exceeds maximum of {hard_title} characters ({len(clean_title)} chars).",
                )
            )
        elif len(clean_title) > rec_title:
            is_within_recommended = False
            warnings.append(
                ChannelWarning(
                    code="WEB_TITLE_LENGTH_ADVISORY",
                    severity=WarningSeverity.LOW.value,
                    message=f"Web notification title ({len(clean_title)} chars) exceeds recommended {rec_title} characters and may be truncated on notification popups.",
                )
            )

        # Body checks
        if char_count > hard_body:
            is_within_hard = False
            warnings.append(
                ChannelWarning(
                    code="WEB_BODY_HARD_LIMIT_EXCEEDED",
                    severity=WarningSeverity.CRITICAL.value,
                    message=f"Web notification body exceeds maximum payload limit of {hard_body} characters ({char_count} chars).",
                )
            )
        elif char_count > rec_body:
            is_within_recommended = False
            warnings.append(
                ChannelWarning(
                    code="WEB_BODY_LENGTH_ADVISORY",
                    severity=WarningSeverity.LOW.value,
                    message=f"Web notification body ({char_count} chars) exceeds recommended {rec_body} characters for optimal mobile push readability.",
                )
            )

    return ChannelMetrics(
        channel=norm_channel,
        character_count=char_count,
        word_count=word_count,
        estimated_duration_seconds=estimated_duration,
        sms=sms_detail,
        is_within_recommended_limit=is_within_recommended,
        is_within_hard_limit=is_within_hard,
        warnings=warnings,
        rule_version="v1.0",
    )
