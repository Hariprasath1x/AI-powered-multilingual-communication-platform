"""Abstract base classes and contracts for AI content generation and translation."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


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
    target_language: str = Field(..., description="Target language code: en, ta, hi, te, bn, mr")
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


class BaseAIProvider(ABC):
    """Abstract interface for AI content generation and translation engines."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider identifier (e.g. 'gemini', 'mock')."""
        pass

    @abstractmethod
    async def generate_content(self, brief: ContentBrief) -> GeneratedContentResult:
        """Generate awareness campaign content from a structured brief."""
        pass

    @abstractmethod
    async def translate_content(self, request: TranslationRequest) -> TranslatedContentResult:
        """Translate content into target language while strictly preserving placeholders and factual integrity."""
        pass

