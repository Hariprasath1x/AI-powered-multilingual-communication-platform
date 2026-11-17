"""Abstract base classes and contracts for AI content generation and translation."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


def escape_xml(text: Optional[str]) -> str:
    """
    Escapes XML special characters (&, <, >, ", ') to prevent prompt injection
    and structural tag breakout within LLM prompts (defense-in-depth).
    """
    if not text:
        return ""
    # Order matters: replace & first so &amp; isn't replaced again
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


class ContentBrief(BaseModel):
    """Structured brief for generating public-awareness content."""

    topic: str = Field(..., min_length=3, max_length=200, description="Campaign topic or focus area")
    objective: str = Field(..., min_length=5, max_length=500, description="Primary communication goal")
    audience_description: Optional[str] = Field(None, max_length=500, description="Target demographic summary")
    category: str = Field(..., description="Healthcare, Disaster Preparedness, Education, Civic Services, Environment, etc.")
    tone: str = Field("informative", description="formal, informative, friendly, urgent, empathetic")
    channel: str = Field("Email", description="Email, SMS, WhatsApp, Voice")
    source_language: str = Field("en", description="Source language code (e.g., en, hi, ta)")
    facts: Optional[str] = Field(None, max_length=2000, description="Factual bullets, verified contact numbers, dates, official links")
    constraints: Optional[str] = Field(None, max_length=500, description="Channel constraints, mandatory phrases, formatting rules")
    target_length: Optional[str] = Field(None, description="short, medium, long, or channel-guideline")

    # Campaign-aware enrichment fields (backward-compatible, optional)
    campaign_id: Optional[int] = Field(None, description="Associated campaign identifier")
    campaign_name: Optional[str] = Field(None, description="Campaign title or focus area")
    campaign_type: Optional[str] = Field(None, description="Awareness, Emergency Alert, Educational, etc.")
    campaign_priority: Optional[str] = Field(None, description="Low, Medium, High")
    campaign_objective: Optional[str] = Field(None, max_length=500, description="Overarching strategic campaign objective")
    target_segments: List[str] = Field(default_factory=list, description="Target demographic segment names/summaries")


class GeneratedContentResult(BaseModel):
    """Structured result returned by the AI provider upon content generation."""

    title: str
    body: str
    summary: Optional[str] = None
    call_to_action: Optional[str] = None
    category: str
    tone: str
    channel: str
    source_language: str
    provider_metadata: Dict[str, Any] = Field(default_factory=dict)


class TranslationRequest(BaseModel):
    """Request payload for translating content into a target Indian language."""

    source_text: str = Field(..., min_length=1, description="Source body text to translate")
    source_title: Optional[str] = Field(None, description="Optional headline or title to translate")
    source_cta: Optional[str] = Field(None, description="Optional call to action to translate")
    source_language: str = Field("en", description="Original language code")
    target_language: str = Field(..., description="Target language code: hi, kn, ta, te, mr, bn, gu, ml, pa, ur, en")
    channel: Optional[str] = Field("Email", description="Target communication channel for pacing/formatting")
    context: Optional[str] = Field(None, description="Contextual guidance for the translator")


class TranslatedContentResult(BaseModel):
    """Structured result returned after translation."""

    title: str
    body: str
    summary: Optional[str] = None
    call_to_action: Optional[str] = None
    source_language: str
    target_language: str
    preserved_placeholders: List[str] = Field(default_factory=list)
    provider_metadata: Dict[str, Any] = Field(default_factory=dict)


class AIProviderError(Exception):
    """Base exception for AI provider operations."""

    def __init__(self, message: str, status_code: int = 502, provider: str = "ai_provider"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.provider = provider


class AIProviderTimeoutError(AIProviderError):
    """Raised when the AI provider times out."""

    def __init__(self, message: str = "AI generation timed out. Please try again.", provider: str = "ai_provider"):
        super().__init__(message=message, status_code=504, provider=provider)


class AIProviderQuotaError(AIProviderError):
    """Raised when rate limits or quotas are exceeded."""

    def __init__(self, message: str = "AI provider rate limit reached. Please retry in a few moments.", provider: str = "ai_provider"):
        super().__init__(message=message, status_code=429, provider=provider)


class PlaceholderPreservationError(AIProviderError):
    """Raised when critical dynamic placeholders are lost or altered during translation."""

    def __init__(self, missing_placeholders: List[str], provider: str = "ai_provider"):
        super().__init__(
            message=f"Translation failed safety check: missing placeholders {missing_placeholders}",
            status_code=422,
            provider=provider,
        )
        self.missing_placeholders = missing_placeholders


class ContentEvaluationRequest(BaseModel):
    """Request payload for AI-assisted editorial quality and compliance evaluation."""

    title: str
    body: str
    call_to_action: Optional[str] = None
    category: str
    tone: str
    channel: str
    source_language: str
    target_language: Optional[str] = None
    reference_facts: Optional[str] = None
    constraints: Optional[str] = None
    parent_title: Optional[str] = None
    parent_body: Optional[str] = None
    parent_cta: Optional[str] = None


class AIEvaluationFinding(BaseModel):
    """Individual finding reported by AI evaluator."""

    category: str = Field(..., description="grammar, readability, tone, translation, factual, channel, safety_sensitive")
    severity: str = Field(..., description="critical, high, medium, low, informational")
    title: str
    explanation: str
    affected_text: Optional[str] = None
    suggested_correction: Optional[str] = None
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class ContentEvaluationResponse(BaseModel):
    """Structured quality assessment output from AI provider."""

    findings: List[AIEvaluationFinding] = Field(default_factory=list)
    dimension_scores: Dict[str, float] = Field(default_factory=dict)
    summary: str
    provider_metadata: Dict[str, Any] = Field(default_factory=dict)


class SentimentAnalysisResult(BaseModel):
    """Structured output from model-based sentiment analysis."""

    sentiment: str = Field(..., description="Positive, Neutral, or Negative")
    score: float = Field(default=0.0, description="Polarity score between -1.0 and 1.0")
    confidence: float = Field(default=1.0, description="Model confidence between 0.0 and 1.0")
    method: str = Field(default="model", description="Identifier of the method or model used")
    raw_response: Optional[str] = Field(None, description="Raw model response for auditing")

    def __iter__(self):
        return iter((self.sentiment, self.score))

    def __len__(self):
        return 2

    def __getitem__(self, item):
        return (self.sentiment, self.score, self.method, self.confidence)[item]


class BaseAIProvider(ABC):
    """Abstract interface for AI content generation, translation, evaluation, and sentiment engines."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider identifier (e.g. 'gemini', 'mock')."""
        pass

    def get_model_name(self) -> str:
        """Return model identifier (e.g. 'gemini-1.5-flash', 'mock-translator-v1')."""
        return "default"

    @abstractmethod
    async def generate_content(self, brief: ContentBrief) -> GeneratedContentResult:
        """Generate awareness campaign content from a structured brief."""
        pass

    @abstractmethod
    async def translate_content(self, request: TranslationRequest) -> TranslatedContentResult:
        """Translate content into target language while strictly preserving placeholders and factual integrity."""
        pass

    @abstractmethod
    async def evaluate_content(self, request: ContentEvaluationRequest) -> ContentEvaluationResponse:
        """Evaluate public awareness copy for tone, grammar, factual consistency, and safety."""
        pass

    @abstractmethod
    async def analyze_sentiment(
        self, text: str, language: Optional[str] = "en"
    ) -> SentimentAnalysisResult:
        """Analyze sentiment of citizen feedback or inbound reply using AI model."""
        pass
