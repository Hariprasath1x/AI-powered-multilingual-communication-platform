"""Sentiment Analysis and Topic/Keyword Extraction Service.

Provides:
1. Multilingual sentiment classification (Positive, Neutral, Negative) and continuous polarity scoring [-1.0, 1.0].
2. High-performance deterministic lexicon fallback for tests, offline operation, and provider failure tolerance.
3. Topic clustering, keyword frequency extraction, common question identification, and citizen concern mining.
"""

from __future__ import annotations
import re
import math
import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("masscommai.sentiment")

# Multilingual valence dictionaries (English + transliterated & native Indian language tokens)
POSITIVE_VALENCE: Dict[str, float] = {
    # English
    "good": 0.6, "great": 0.8, "excellent": 0.9, "helpful": 0.7, "useful": 0.6,
    "clear": 0.5, "informative": 0.6, "satisfied": 0.7, "thanks": 0.6, "thank": 0.6,
    "appreciated": 0.8, "appreciate": 0.7, "timely": 0.6, "easy": 0.5, "quick": 0.5,
    "quickly": 0.5, "fast": 0.5, "speedy": 0.6, "prompt": 0.65, "promptly": 0.65,
    "professional": 0.7, "professionally": 0.7,
    "effective": 0.7, "wonderful": 0.85, "supportive": 0.7, "safe": 0.6, "peaceful": 0.6,
    "well": 0.5, "best": 0.85, "love": 0.8, "happy": 0.75, "smooth": 0.6,
    "organized": 0.65, "polite": 0.7, "caring": 0.7, "success": 0.7, "relief": 0.6,
    # Hindi / Romanized Hindi
    "accha": 0.6, "achha": 0.6, "shukriya": 0.7, "dhanyawad": 0.7, "dhanyavad": 0.7,
    "bahut accha": 0.8, "madadgar": 0.7, "sahi": 0.5, "theek": 0.4, "badhiya": 0.75,
    "sundar": 0.6, "khush": 0.7, "santan": 0.5, "acha": 0.6, "saral": 0.6,
    # Hindi Devanagari
    "अच्छा": 0.6, "धन्यवाद": 0.7, "मददगार": 0.7, "शानदार": 0.8, "बढ़िया": 0.75,
    "उत्कृष्ट": 0.85, "सरल": 0.6, "सुगम": 0.6, "संतोषजनक": 0.7, "सफल": 0.7,
    # Tamil / Romanized Tamil
    "nandri": 0.7, "nalla": 0.6, "migavum nalla": 0.8, "arputham": 0.85,
    "நன்றி": 0.7, "நல்லது": 0.6, "சிறந்த": 0.8,
}

NEGATIVE_VALENCE: Dict[str, float] = {
    # English
    "bad": -0.6, "poor": -0.7, "terrible": -0.85, "awful": -0.85, "horrible": -0.9,
    "rude": -0.8, "slow": -0.5, "delayed": -0.6, "confusing": -0.6, "unclear": -0.55,
    "useless": -0.75, "waste": -0.8, "failed": -0.7, "disappointed": -0.75, "problem": -0.5,
    "issue": -0.4, "error": -0.5, "crowded": -0.5, "long queue": -0.6, "queue": -0.4,
    "waiting": -0.4, "ignored": -0.7, "complaint": -0.6, "broken": -0.65, "unavailable": -0.5,
    "closed": -0.5, "hard": -0.4, "difficult": -0.5, "pain": -0.7, "struggle": -0.6,
    "scam": -0.9, "fraud": -0.9, "misleading": -0.8, "fake": -0.8, "unhelpful": -0.7,
    # Hindi / Romanized Hindi
    "kharab": -0.7, "bura": -0.6, "deri": -0.5, "samarthya": -0.4, "pareshani": -0.65,
    "shikayat": -0.6, "koshish": -0.3, "bheed": -0.5, "bekaar": -0.75, "bekar": -0.75,
    "nakara": -0.7, "galat": -0.6, "dhoka": -0.85, "nuksan": -0.7,
    # Hindi Devanagari
    "खराब": -0.7, "बुरा": -0.6, "परेशानी": -0.65, "शिकायत": -0.6, "देरी": -0.5,
    "भीड़": -0.5, "गलत": -0.6, "धोखा": -0.85, "बेकार": -0.75, "कठिन": -0.5,
    # Tamil / Romanized Tamil
    "mosam": -0.7, "kettathu": -0.7, "thamadham": -0.55, "sikkal": -0.6,
    "மோசம்": -0.7, "தாமதம்": -0.55, "சிக்கல்": -0.6,
}

NEGATIONS: set[str] = {
    "not", "no", "never", "neither", "hardly", "barely", "scarcely", "without",
    "nahi", "nahin", "nhi", "mat", "இல்லை", "இல்ல",
}

INTENSIFIERS: Dict[str, float] = {
    "very": 1.4, "extremely": 1.7, "highly": 1.5, "completely": 1.4, "totally": 1.4,
    "really": 1.3, "too": 1.3, "super": 1.4, "absolutely": 1.6,
    "bahut": 1.4, "zyada": 1.3, "jyada": 1.3, "மிகவும்": 1.4,
}

STOPWORDS: set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any",
    "are", "as", "at", "be", "because", "been", "before", "being", "below", "between",
    "both", "but", "by", "can", "did", "do", "does", "doing", "don", "down", "during",
    "each", "few", "for", "from", "further", "had", "has", "have", "having", "he",
    "her", "here", "hers", "herself", "him", "himself", "his", "how", "i", "if", "in",
    "into", "is", "it", "its", "itself", "just", "me", "more", "most", "my", "myself",
    "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or", "other", "our",
    "ours", "ourselves", "out", "over", "own", "s", "same", "she", "should", "so",
    "some", "such", "t", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "will", "with", "you", "your", "yours", "yourself",
    "aur", "hai", "hain", "ko", "ki", "ka", "ke", "se", "mein", "par", "ye", "woh",
}

TOPIC_SEEDS: Dict[str, List[str]] = {
    "Vaccination & Immunization": [
        "vaccine", "vaccination", "dose", "polio", "booth", "immunization", "drop",
        "teeka", "teekakaran", "tika", "injection", "dawa", "kendra", "centre", "center",
    ],
    "Timing & Scheduling": [
        "time", "timing", "hour", "hours", "delay", "wait", "waiting", "schedule",
        "morning", "evening", "sunday", "date", "samay", "deri", "tarikh", "ghante",
    ],
    "Location & Facility": [
        "booth", "center", "centre", "hospital", "clinic", "school", "address",
        "location", "room", "kendra", "jagah", "pata", "gate",
    ],
    "Staff & Service Quality": [
        "staff", "doctor", "nurse", "worker", "officer", "behavior", "rude",
        "polite", "helpful", "karmachari", "vyavahar", "seva",
    ],
    "Disaster & Emergency": [
        "cyclone", "flood", "storm", "warning", "rain", "shelter", "evacuation",
        "emergency", "help", "alert", "toofan", "baadh", "sahayata",
    ],
    "Inquiry & Helpline": [
        "helpline", "call", "number", "contact", "information", "details",
        "website", "portal", "janakari", "suchna", "phone",
    ],
}


def analyze_sentiment(text: Optional[str], language: Optional[str] = "en") -> Tuple[str, float]:
    """
    Computes sentiment label ('Positive', 'Neutral', 'Negative') and polarity score [-1.0, 1.0].
    Deterministic, robust against empty/malformed text, and safe for unit tests without network calls.
    """
    if not text or not text.strip():
        return "Neutral", 0.0

    clean_text = text.strip()
    words = [tok.strip(".,!?;:\"'()[]{}—–") for tok in clean_text.lower().split()]
    words = [t for t in words if t]
    if not words:
        return "Neutral", 0.0

    raw_scores: List[float] = []
    i = 0
    n = len(words)

    while i < n:
        w = words[i]
        multiplier = 1.0

        if i > 0 and words[i - 1] in NEGATIONS:
            multiplier = -0.7
        elif i > 0 and words[i - 1] in INTENSIFIERS:
            multiplier = INTENSIFIERS[words[i - 1]]

        score = 0.0
        if w in POSITIVE_VALENCE:
            score = POSITIVE_VALENCE[w]
        elif w in NEGATIVE_VALENCE:
            score = NEGATIVE_VALENCE[w]

        if score != 0.0:
            raw_scores.append(score * multiplier)

        i += 1

    if not raw_scores:
        # Check overall exclamation or question marks for slight nudge
        if "?" in clean_text:
            return "Neutral", 0.0
        return "Neutral", 0.0

    mean_score = sum(raw_scores) / len(raw_scores)
    # Tanh-like smoothing
    normalized = math.tanh(mean_score * 1.5)
    rounded_score = round(float(max(-1.0, min(1.0, normalized))), 3)

    if rounded_score > 0.15:
        label = "Positive"
    elif rounded_score < -0.15:
        label = "Negative"
    else:
        label = "Neutral"

    return label, rounded_score


def extract_topics_and_keywords(texts: List[str], max_keywords: int = 15) -> Dict[str, Any]:
    """
    Extracts high-frequency keywords, pre-defined civic topic clusters,
    common questions, and recurring negative concerns from a list of feedback/replies.
    """
    if not texts:
        return {
            "keywords": [],
            "topics": [],
            "common_questions": [],
            "concerns": [],
        }

    word_freq: Dict[str, int] = {}
    topic_scores: Dict[str, int] = {t: 0 for t in TOPIC_SEEDS}
    questions: List[str] = []
    concerns: List[str] = []

    seen_questions: set[str] = set()
    seen_concerns: set[str] = set()

    for item in texts:
        if not item or not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned:
            continue

        # Check for question
        is_question = False
        if "?" in cleaned or re.search(r"\b(how|when|where|what|why|who|kab|kahan|kaise|kyun|engu|eppadi)\b", cleaned, re.IGNORECASE):
            is_question = True
            norm_q = cleaned[:120].strip()
            if norm_q not in seen_questions:
                seen_questions.add(norm_q)
                questions.append(norm_q)

        # Check for concern / pain point
        label, score = analyze_sentiment(cleaned)
        if label == "Negative" or score < -0.1:
            norm_c = cleaned[:120].strip()
            if norm_c not in seen_concerns:
                seen_concerns.add(norm_c)
                concerns.append(norm_c)

        # Word frequency & topic matching
        tokens = [tok.strip(".,!?;:\"'()[]{}—–") for tok in cleaned.lower().split()]
        tokens = [t for t in tokens if t]
        for tok in tokens:
            if tok not in STOPWORDS and len(tok) > 2:
                word_freq[tok] = word_freq.get(tok, 0) + 1

            for topic, keywords in TOPIC_SEEDS.items():
                if tok in keywords:
                    topic_scores[topic] += 1

    # Sorted keywords
    sorted_keywords = sorted(word_freq.items(), key=lambda kv: kv[1], reverse=True)[:max_keywords]
    keywords_list = [{"keyword": kw, "count": cnt} for kw, cnt in sorted_keywords]

    # Active topics with count > 0
    active_topics = [
        {"topic": topic, "count": cnt}
        for topic, cnt in sorted(topic_scores.items(), key=lambda kv: kv[1], reverse=True)
        if cnt > 0
    ]
    if not active_topics and texts:
        active_topics = [{"topic": "General Civic Feedback", "count": len(texts)}]

    return {
        "keywords": keywords_list,
        "topics": active_topics[:6],
        "common_questions": questions[:5],
        "concerns": concerns[:5],
    }
