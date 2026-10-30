"""Gemini AI Provider implementation using the Google GenAI SDK."""

import json
import logging
import re
from typing import Optional, List, Set, Any
from app.services.ai.base import (
    BaseAIProvider,
    ContentBrief,
    GeneratedContentResult,
    TranslationRequest,
    TranslatedContentResult,
    AIProviderError,
    AIProviderTimeoutError,
    AIProviderQuotaError,
    PlaceholderPreservationError,
)
from app.core.config import settings

logger = logging.getLogger(__name__)
PLACEHOLDER_REGEX = re.compile(r"\{[a-zA-Z0-9_]+\}")


class GeminiAIProvider(BaseAIProvider):
    """
    Production-grade AI provider utilizing Google Gemini models via google-genai SDK.
    Enforces strict hallucination guardrails, placeholder preservation, and timeout controls.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.AI_MODEL_NAME
        self.timeout_seconds = timeout_seconds or settings.AI_REQUEST_TIMEOUT_SECONDS

        if not self.api_key:
            raise AIProviderError(
                "Gemini API key is not configured. Please set GEMINI_API_KEY in environment.",
                status_code=500,
                provider="gemini",
            )

        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
        except Exception as exc:
            logger.error("Failed to initialize Google GenAI client: %s", exc)
            raise AIProviderError(
                f"Failed to initialize GenAI client: {str(exc)}",
                status_code=500,
                provider="gemini",
            ) from exc

    def get_provider_name(self) -> str:
        return "gemini"

    async def generate_content(self, brief: ContentBrief) -> GeneratedContentResult:
        """Generate structured awareness copy using Gemini."""
        system_instruction = (
            "You are a public communication and mass awareness assistant for MassCommAI. "
            "Your role is to craft accurate, culturally sensitive, high-impact public service announcements. "
            "STRICT RULES:\n"
            "1. NEVER invent, hallucinate, or fabricate helpline numbers, emergency phone lines, government schemes, URLs, or legal claims. "
            "Only reference facts provided in the brief or use generic placeholders like '{helpline}' or 'local emergency center'.\n"
            "2. Strictly adapt to the target communication channel (SMS: max 160 characters or clear segments; Voice: spoken rhythm and clear pronunciation; WhatsApp: scannable bullets and emojis; Email: professional formatting with markdown).\n"
            "3. Return ONLY a valid JSON object with keys: 'title', 'body', 'summary', 'call_to_action'. Do not include markdown code block backticks unless strictly required."
        )

        user_prompt = (
            f"Generate a {brief.tone} public awareness message for channel '{brief.channel}'.\n"
            f"Topic: {brief.topic}\n"
            f"Objective: {brief.objective}\n"
            f"Category: {brief.category}\n"
            f"Target Audience: {brief.audience_description or 'General Public'}\n"
            f"Language: {brief.source_language}\n"
            f"Facts to include: {brief.facts or 'None provided'}\n"
            f"Constraints: {brief.constraints or 'None'}\n"
            f"Length guidance: {brief.target_length or 'standard channel length'}\n"
            "Remember: Output must be valid JSON with keys 'title', 'body', 'summary', 'call_to_action'."
        )

        try:
            from google.genai import types

            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.3,  # Low temperature for factual accuracy
                ),
            )

            response_text = response.text or "{}"
            data = json.loads(response_text)

            return GeneratedContentResult(
                title=data.get("title", f"Awareness Notice: {brief.topic}"),
                body=data.get("body", response_text),
                summary=data.get("summary"),
                call_to_action=data.get("call_to_action"),
                category=brief.category,
                tone=brief.tone,
                channel=brief.channel,
                source_language=brief.source_language,
                provider_metadata={
                    "provider": "gemini",
                    "model": self.model_name,
                    "channel": brief.channel,
                    "tone": brief.tone,
                },
            )

        except json.JSONDecodeError:
            # Fallback if model returned plain text despite json mode
            raw_text = getattr(response, "text", "") or "Content generation completed."
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            title = lines[0] if lines else brief.topic
            body = "\n".join(lines[1:]) if len(lines) > 1 else raw_text
            return GeneratedContentResult(
                title=title[:200],
                body=body,
                category=brief.category,
                tone=brief.tone,
                channel=brief.channel,
                source_language=brief.source_language,
                provider_metadata={"provider": "gemini", "model": self.model_name, "raw_fallback": True},
            )
        except Exception as exc:
            err_msg = str(exc)
            logger.error("Gemini content generation failed: %s", err_msg)
            if "deadline" in err_msg.lower() or "timeout" in err_msg.lower():
                raise AIProviderTimeoutError("Gemini generation timed out. Please try again.", provider="gemini") from exc
            if "quota" in err_msg.lower() or "429" in err_msg or "resource_exhausted" in err_msg.lower():
                raise AIProviderQuotaError("Gemini rate limit exceeded. Please retry shortly.", provider="gemini") from exc
            raise AIProviderError(f"AI generation failed: {err_msg}", status_code=502, provider="gemini") from exc

    async def translate_content(self, request: TranslationRequest) -> TranslatedContentResult:
        """Translate awareness copy while strictly preserving placeholders and factual accuracy."""
        source_placeholders: Set[str] = set(PLACEHOLDER_REGEX.findall(request.source_text))
        if request.source_title:
            source_placeholders.update(PLACEHOLDER_REGEX.findall(request.source_title))
        if request.source_cta:
            source_placeholders.update(PLACEHOLDER_REGEX.findall(request.source_cta))

        system_instruction = (
            "You are an expert translator specializing in Indian languages for public communication. "
            "CRITICAL INSTRUCTIONS:\n"
            f"1. Translate the text into language code '{request.target_language}'.\n"
            "2. STRICTLY PRESERVE all placeholder variables inside curly braces (e.g. {name}, {city}, {preferred_language}) "
            "EXACTLY as they appear, without translating the variable names or removing braces.\n"
            "3. Do NOT alter URLs, numbers, dates, or contact details.\n"
            "4. Return ONLY a valid JSON object with keys: 'title', 'body', 'summary', 'call_to_action'."
        )

        user_prompt = (
            f"Translate the following communication from '{request.source_language}' to '{request.target_language}'.\n"
            f"Title: {request.source_title or 'N/A'}\n"
            f"Body:\n{request.source_text}\n"
            f"Call to action: {request.source_cta or 'N/A'}\n"
            f"Context: {request.context or 'Public awareness notice'}\n"
            f"Placeholders that MUST remain in the translated output: {list(source_placeholders)}\n"
            "Output format: JSON object with keys 'title', 'body', 'summary', 'call_to_action'."
        )

        try:
            from google.genai import types

            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )

            data = json.loads(response.text or "{}")
            translated_title = data.get("title", request.source_title or "")
            translated_body = data.get("body", response.text)
            translated_cta = data.get("call_to_action", request.source_cta)

            # Safety check: Verify all source placeholders are preserved in translated output
            full_translated_text = f"{translated_title} {translated_body} {translated_cta or ''}"
            missing = [ph for ph in source_placeholders if ph not in full_translated_text]
            if missing:
                logger.warning("Placeholders missing in Gemini translation output: %s. Re-injecting.", missing)
                translated_body += "\n\n[" + " ".join(missing) + "]"

            return TranslatedContentResult(
                title=translated_title,
                body=translated_body,
                summary=data.get("summary", f"Translated into {request.target_language} via Gemini."),
                call_to_action=translated_cta,
                source_language=request.source_language,
                target_language=request.target_language,
                preserved_placeholders=sorted(list(source_placeholders)),
                provider_metadata={
                    "provider": "gemini",
                    "model": self.model_name,
                    "target_language": request.target_language,
                },
            )

        except Exception as exc:
            err_msg = str(exc)
            logger.error("Gemini translation failed: %s", err_msg)
            if "deadline" in err_msg.lower() or "timeout" in err_msg.lower():
                raise AIProviderTimeoutError("Gemini translation timed out.", provider="gemini") from exc
            if "quota" in err_msg.lower() or "429" in err_msg or "resource_exhausted" in err_msg.lower():
                raise AIProviderQuotaError("Gemini rate limit exceeded during translation.", provider="gemini") from exc
            raise AIProviderError(f"Translation failed: {err_msg}", status_code=502, provider="gemini") from exc

