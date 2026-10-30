"""Deterministic mock AI provider for development, testing, and offline operations."""

import re
import asyncio
from typing import Set, List
from app.services.ai.base import (
    BaseAIProvider,
    ContentBrief,
    GeneratedContentResult,
    TranslationRequest,
    TranslatedContentResult,
    AIProviderError,
    AIProviderTimeoutError,
    PlaceholderPreservationError,
)

# Supported language codes & labels
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "mr": "Marathi",
}

PLACEHOLDER_REGEX = re.compile(r"\{[a-zA-Z0-9_]+\}")


class MockAIProvider(BaseAIProvider):
    """
    Mock AI Provider producing realistic, deterministic, channel-adapted public awareness copy.
    Guarantees zero external network dependencies, strict placeholder preservation, and simulation hooks.
    """

    def __init__(self, simulate_latency_ms: int = 0):
        self.simulate_latency_ms = simulate_latency_ms

    def get_provider_name(self) -> str:
        return "mock"

    async def _handle_simulated_delays_and_errors(self, text_trigger: str) -> None:
        if "[SIMULATE_TIMEOUT]" in text_trigger:
            raise AIProviderTimeoutError("Mock provider simulated timeout.", provider="mock")
        if "[SIMULATE_ERROR]" in text_trigger:
            raise AIProviderError("Mock provider simulated upstream failure.", status_code=502, provider="mock")
        if self.simulate_latency_ms > 0:
            await asyncio.sleep(self.simulate_latency_ms / 1000.0)

    async def generate_content(self, brief: ContentBrief) -> GeneratedContentResult:
        """Generate structured awareness copy tailored to channel, tone, and brief."""
        trigger = f"{brief.topic} {brief.constraints or ''} {brief.facts or ''}"
        await self._handle_simulated_delays_and_errors(trigger)

        tone = brief.tone.lower()
        channel = brief.channel
        topic = brief.topic.strip()
        category = brief.category
        facts = f" Note: {brief.facts.strip()}" if brief.facts else ""

        # Channel-tailored generation
        if channel == "SMS":
            # SMS needs to be concise and fit within SMS bounds
            if tone == "urgent":
                title = f"URGENT: {topic}"
                body = f"ALERT: Important update regarding {topic} for {{name}} in {{city}}.{facts} Take immediate precautions. Info: Call helpline."
                cta = "Call helpline immediately"
            elif tone == "formal":
                title = f"Notice: {topic}"
                body = f"Official update regarding {topic} for citizen {{name}}.{facts} Please review official guidelines."
                cta = "Visit portal for details"
            elif tone == "empathetic":
                title = f"Support: {topic}"
                body = f"Dear {{name}}, support is available for {topic} in {{city}}.{facts} We are here to help."
                cta = "Reach out for support"
            else:
                title = f"Update: {topic}"
                body = f"Dear {{name}}, please note the latest advisory regarding {topic} in {{city}}.{facts}"
                cta = "Stay informed and share"
            summary = f"SMS advisory for {topic} targeted to {{city}}."

        elif channel == "WhatsApp":
            if tone == "urgent":
                title = f"🚨 URGENT ADVISORY: {topic}"
                body = (
                    f"⚠️ *URGENT NOTICE FOR {{city}}*\n\n"
                    f"Dear {{name}},\n"
                    f"Please be aware of this critical advisory regarding *{topic}*.\n\n"
                    f"📌 *Key Actions:*\n"
                    f"• Follow official health and safety instructions immediately\n"
                    f"• Assist elderly and vulnerable community members\n"
                    f"• Avoid rumors and share verified information only\n"
                    f"{facts}\n\n"
                    f"Stay safe and connected."
                )
                cta = "Forward to family and follow verified updates"
            else:
                title = f"📢 Community Update: {topic}"
                body = (
                    f"Hello {{name}},\n\n"
                    f"Here is an important public awareness update on *{topic}* for residents of {{city}}.\n\n"
                    f"💡 *What you need to know:*\n"
                    f"• Simple preventive measures protect our whole community\n"
                    f"• Verified guidance is available at your nearest local center\n"
                    f"{facts}\n\n"
                    f"Together, we build a healthier, safer neighborhood."
                )
                cta = "Tap to learn more and share with neighbors"
            summary = f"WhatsApp broadcast regarding {topic} for {{name}} in {{city}}."

        elif channel == "Voice":
            title = f"Audio Script: {topic}"
            if tone == "urgent":
                body = (
                    f"Attention residents of {{city}}. This is an urgent public safety announcement regarding {topic}. "
                    f"Citizen {{name}}, please listen carefully. Immediate precautionary measures are in effect across your district. "
                    f"{facts} Repeat: please stay calm, remain indoors if advised, and monitor official channels. Thank you."
                )
                cta = "Press 1 to repeat this emergency announcement"
            else:
                body = (
                    f"Namaste {{name}}. This is an informative public health message from your community team regarding {topic}. "
                    f"Residents of {{city}} are encouraged to take proactive steps today. "
                    f"{facts} For more information, visit your local primary center or call the district office. Have a safe day."
                )
                cta = "Press 1 to hear more details"
            summary = f"Spoken IVR script for {topic} with natural audio pacing."

        else:  # Email
            salutation = "Dear {name},"
            if tone == "urgent":
                title = f"URGENT ADVISORY: Immediate Action Required on {topic}"
                body = (
                    f"{salutation}\n\n"
                    f"This is an urgent public advisory regarding **{topic}** for residents of {{city}}.\n\n"
                    f"### Critical Overview\n"
                    f"The district communication office has issued high-priority guidance to ensure public safety.\n\n"
                    f"### Key Instructions and Facts\n"
                    f"- Remain alert and monitor verified communication channels.\n"
                    f"- Follow precautionary protocols without delay.\n"
                    f"{facts}\n\n"
                    f"### How to Get Immediate Assistance\n"
                    f"Local response teams are active in your area. Contact your primary district coordinator for urgent questions.\n\n"
                    f"Sincerely,\n"
                    f"Public Awareness & Safety Team"
                )
                cta = "Read Official Safety Directive"
            elif tone == "formal":
                title = f"Official Notice: Comprehensive Guidelines on {topic}"
                body = (
                    f"{salutation}\n\n"
                    f"You are receiving this official communication regarding **{topic}** as part of our scheduled civic outreach.\n\n"
                    f"### Purpose & Context\n"
                    f"{brief.objective}\n\n"
                    f"### Standard Operating Guidance\n"
                    f"1. Adhere strictly to the civic framework outlined for {{city}}.\n"
                    f"2. Ensure all household members are familiar with the recommendations.\n"
                    f"{facts}\n\n"
                    f"For complete administrative guidelines and documentation, consult your municipal portal.\n\n"
                    f"Regards,\n"
                    f"Department of Public Administration"
                )
                cta = "Access Official Documentation"
            else:
                title = f"Community Awareness: Staying Informed About {topic}"
                body = (
                    f"{salutation}\n\n"
                    f"We are reaching out to share helpful information regarding **{topic}** with our community members in {{city}}.\n\n"
                    f"### Why This Matters\n"
                    f"{brief.objective}\n\n"
                    f"### Practical Tips for You and Your Family\n"
                    f"- Stay proactive by adopting clean, responsible civic habits.\n"
                    f"- Support your neighbors and share accurate information.\n"
                    f"{facts}\n\n"
                    f"Thank you for your partnership in keeping our community healthy and resilient.\n\n"
                    f"Warm regards,\n"
                    f"Community Outreach Team"
                )
                cta = "Learn More and Get Involved"
            summary = f"Comprehensive awareness email on {topic} for citizens in {{city}}."

        return GeneratedContentResult(
            title=title,
            body=body,
            summary=summary,
            call_to_action=cta,
            category=category,
            tone=tone,
            channel=channel,
            source_language=brief.source_language,
            provider_metadata={
                "provider": "mock",
                "model": "mock-llm-v1",
                "channel": channel,
                "tone": tone,
                "simulated": True,
            },
        )

    async def translate_content(self, request: TranslationRequest) -> TranslatedContentResult:
        """Translate content into target language while strictly preserving placeholders and factual integrity."""
        trigger = f"{request.source_text} {request.context or ''}"
        await self._handle_simulated_delays_and_errors(trigger)

        target_lang = request.target_language.lower()
        if target_lang not in SUPPORTED_LANGUAGES:
            raise AIProviderError(
                f"Unsupported target language: {target_lang}. Supported: {list(SUPPORTED_LANGUAGES.keys())}",
                status_code=400,
                provider="mock",
            )

        # Detect placeholders in source
        detected_placeholders: Set[str] = set(PLACEHOLDER_REGEX.findall(request.source_text))
        if request.source_title:
            detected_placeholders.update(PLACEHOLDER_REGEX.findall(request.source_title))
        if request.source_cta:
            detected_placeholders.update(PLACEHOLDER_REGEX.findall(request.source_cta))

        # Specialized multilingual translation mappings for supported Indian languages
        translations = {
            "ta": {
                "prefix_title": "பொது விழிப்புணர்வு",
                "urgent_title": "அவசர அறிவிப்பு",
                "greeting": "அன்புள்ள {name}",
                "body_lead": "{city} பகுதி மக்களுக்கான முக்கிய பொது விழிப்புணர்வு தகவல்:",
                "guidelines": "அதிகாரப்பூர்வ வழிகாட்டுதல்களைப் பின்பற்றவும்.",
                "sign_off": "நன்றி, மக்கள் தொடர்பு குழு.",
                "cta": "மேலும் அறிய மற்றும் பின்தொடரவும்",
            },
            "hi": {
                "prefix_title": "सार्वजनिक जागरूकता",
                "urgent_title": "आपातकालीन सूचना",
                "greeting": "प्रिय {name}",
                "body_lead": "{city} के नागरिकों के लिए महत्वपूर्ण जन-जागरूकता संदेश:",
                "guidelines": "कृपया आधिकारिक दिशानिर्देशों का पालन करें।",
                "sign_off": "धन्यवाद, जन संपर्क विभाग।",
                "cta": "विस्तृत जानकारी हेतु संपर्क करें",
            },
            "te": {
                "prefix_title": "ప్రజా చైతన్యం",
                "urgent_title": "అత్యవసర ప్రకటన",
                "greeting": "ప్రియమైన {name}",
                "body_lead": "{city} ప్రజల కోసం ముఖ్యమైన ప్రజా అవగాహన సమాచారం:",
                "guidelines": "దయచేసి అధికారిక మార్గదర్శకాలను పాటించండి.",
                "sign_off": "భవదీయుడు, సమాచార విభాగం.",
                "cta": "మరిన్ని వివరాలు తెలుసుకోండి",
            },
            "bn": {
                "prefix_title": "জনসচেতনতা বার্তা",
                "urgent_title": "জরুরি বিজ্ঞপ্তি",
                "greeting": "প্রিয় {name}",
                "body_lead": "{city} অঞ্চলের নাগরিকদের জন্য গুরুত্বপূর্ণ তথ্য:",
                "guidelines": "অনুগ্রহ করে সরকারি নির্দেশাবলী মেনে চলুন।",
                "sign_off": "ধন্যবাদান্তে, জনসেবা দল।",
                "cta": "বিস্তারিত জানতে এখানে দেখুন",
            },
            "mr": {
                "prefix_title": "सार्वजनिक जनजागृती",
                "urgent_title": "तातडीची सूचना",
                "greeting": "प्रिय {name}",
                "body_lead": "{city} मधील नागरिकांसाठी महत्त्वाची माहिती:",
                "guidelines": "कृपया अधिकृत मार्गदर्शक तत्त्वांचे पालन करा.",
                "sign_off": "आपला नम्र, जनसंपर्क विभाग.",
                "cta": "अधिक माहितीसाठी येथे संपर्क साधा",
            },
            "en": {
                "prefix_title": "Public Awareness",
                "urgent_title": "Urgent Advisory",
                "greeting": "Dear {name}",
                "body_lead": "Important public awareness update for residents of {city}:",
                "guidelines": "Please adhere to official recommendations.",
                "sign_off": "Sincerely, Public Communication Team.",
                "cta": "Learn more and stay informed",
            },
        }

        lang_data = translations.get(target_lang, translations["en"])

        # Translate title
        raw_title = request.source_title or "Public Notice"
        is_urgent = "urgent" in raw_title.lower() or "alert" in raw_title.lower()
        title_prefix = lang_data["urgent_title"] if is_urgent else lang_data["prefix_title"]
        translated_title = f"{title_prefix}: {raw_title}"

        # Build translated body preserving placeholders
        # We ensure that whatever placeholders were present in source_text appear in translated body
        body_lines = [
            f"{lang_data['greeting']},",
            "",
            lang_data["body_lead"],
            "",
            f"[{SUPPORTED_LANGUAGES[target_lang]} Translation]",
        ]

        # Extract factual points or bullet points from source
        source_lines = [line.strip() for line in request.source_text.split("\n") if line.strip()]
        for line in source_lines:
            # If line has placeholders, keep them intact
            if "###" in line or "==" in line:
                body_lines.append(f"\n{line}")
            elif line.startswith(("-", "•", "*", "1.", "2.")):
                body_lines.append(f"• {line.lstrip('-•* 123456789.')}")
            elif "http" in line or "call" in line.lower() or "helpline" in line.lower():
                body_lines.append(line)

        # Append standard guidelines & sign-off
        body_lines.append("")
        body_lines.append(lang_data["guidelines"])
        body_lines.append("")
        body_lines.append(lang_data["sign_off"])

        translated_body = "\n".join(body_lines)

        # Check that all detected placeholders in source exist in translated body or title
        combined_translated = f"{translated_title} {translated_body}"
        missing_placeholders: List[str] = [
            ph for ph in detected_placeholders if ph not in combined_translated
        ]

        # If any placeholder was in source but didn't land in template, append contextually to preserve safety
        if missing_placeholders:
            # Safely re-inject missing placeholders into footer note
            translated_body += "\n\n[" + " ".join(missing_placeholders) + "]"
            missing_placeholders = []

        translated_cta = request.source_cta or lang_data["cta"]

        return TranslatedContentResult(
            title=translated_title,
            body=translated_body,
            summary=f"Translated into {SUPPORTED_LANGUAGES[target_lang]} ({target_lang}). Human review recommended.",
            call_to_action=translated_cta,
            source_language=request.source_language,
            target_language=target_lang,
            preserved_placeholders=sorted(list(detected_placeholders)),
            provider_metadata={
                "provider": "mock",
                "model": "mock-translator-v1",
                "source_language": request.source_language,
                "target_language": target_lang,
                "simulated": True,
            },
        )

