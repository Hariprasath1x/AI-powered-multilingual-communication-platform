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
    ContentEvaluationRequest,
    ContentEvaluationResponse,
    AIEvaluationFinding,
    AIProviderError,
    AIProviderTimeoutError,
    PlaceholderPreservationError,
)

# Supported language codes & labels (10 Indian Languages + English)
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "kn": "Kannada",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "bn": "Bengali",
    "gu": "Gujarati",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ur": "Urdu",
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

    def get_model_name(self) -> str:
        return "mock-translator-v1"

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

        meta: Dict[str, Any] = {
            "provider": "mock",
            "model": "mock-llm-v1",
            "channel": channel,
            "tone": tone,
            "simulated": True,
        }
        if brief.campaign_name or brief.campaign_id:
            meta["campaign_context"] = {
                "campaign_id": brief.campaign_id,
                "campaign_name": brief.campaign_name,
                "campaign_type": brief.campaign_type,
                "campaign_priority": brief.campaign_priority,
                "target_segments": brief.target_segments,
            }
            if brief.campaign_priority == "High" and brief.campaign_type != "Emergency Alert":
                meta["pacing_instruction"] = "time-sensitive and action-oriented"
            if summary and brief.campaign_name:
                pacing_suffix = " (Pacing: time-sensitive and action-oriented)" if (brief.campaign_priority == "High" and brief.campaign_type != "Emergency Alert") else ""
                summary = f"{summary} [Campaign: {brief.campaign_name}]{pacing_suffix}"

        return GeneratedContentResult(
            title=title,
            body=body,
            summary=summary,
            call_to_action=cta,
            category=category,
            tone=tone,
            channel=channel,
            source_language=brief.source_language,
            provider_metadata=meta,
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

        # Specialized multilingual translation mappings for 10 supported Indian languages
        translations = {
            "ta": {
                "prefix_title": "பொது விழிப்புணர்வு",
                "urgent_title": "அவசர அறிவிப்பு",
                "greeting": "அன்புள்ள {name}",
                "greeting_generic": "அன்புள்ள குடிமக்களே",
                "body_lead": "{city} பகுதி மக்களுக்கான முக்கிய தகவல்:",
                "body_lead_generic": "பொதுமக்களுக்கான முக்கிய விழிப்புணர்வு தகவல்:",
                "guidelines": "அதிகாரப்பூர்வ வழிகாட்டுதல்களைப் பின்பற்றவும்.",
                "sign_off": "நன்றி, மக்கள் தொடர்பு குழு.",
                "cta": "மேலும் அறிய மற்றும் பின்தொடரவும்",
            },
            "hi": {
                "prefix_title": "सार्वजनिक जागरूकता",
                "urgent_title": "आपातकालीन सूचना",
                "greeting": "प्रिय {name}",
                "greeting_generic": "प्रिय नागरिक",
                "body_lead": "{city} के नागरिकों के लिए महत्वपूर्ण सूचना:",
                "body_lead_generic": "नागरिकों के लिए महत्वपूर्ण जन-जागरूकता संदेश:",
                "guidelines": "कृपया आधिकारिक दिशानिर्देशों का पालन करें।",
                "sign_off": "धन्यवाद, जन संपर्क विभाग।",
                "cta": "विस्तृत जानकारी हेतु संपर्क करें",
            },
            "kn": {
                "prefix_title": "ಸಾರ್ವಜನಿಕ ಜಾಗೃತಿ",
                "urgent_title": "ತುರ್ತು ಪ್ರಕಟಣೆ",
                "greeting": "ಆತ್ಮೀಯ {name}",
                "greeting_generic": "ಆತ್ಮೀಯ ನಾಗರಿಕರೇ",
                "body_lead": "{city} ನಿವಾಸಿಗಳಿಗೆ ಪ್ರಮುಖ ಮಾಹಿತಿ:",
                "body_lead_generic": "ಸಾರ್ವಜನಿಕರಿಗೆ ಪ್ರಮುಖ ಮಾಹಿತಿ:",
                "guidelines": "ದಯವಿಟ್ಟು ಅಧಿಕೃತ ಮಾರ್ಗಸೂಚಿಗಳನ್ನು ಪಾಲಿಸಿ.",
                "sign_off": "ಧನ್ಯವಾದಗಳೊಂದಿಗೆ, ಸಾರ್ವಜನಿಕ ಸಂಪರ್ಕ ತಂಡ.",
                "cta": "ಹೆಚ್ಚಿನ ವಿವರಗಳಿಗಾಗಿ ಸಂಪರ್ಕಿಸಿ",
            },
            "te": {
                "prefix_title": "ప్రజా చైతన్యం",
                "urgent_title": "అత్యవసర ప్రకటన",
                "greeting": "ప్రియమైన {name}",
                "greeting_generic": "గౌరవనీయ పౌరులారా",
                "body_lead": "{city} ప్రజల కోసం ముఖ్యమైన సమాచారం:",
                "body_lead_generic": "ప్రజా అవగాహన కోసం ముఖ్యమైన సమాచారం:",
                "guidelines": "దయచేసి అధికారిక మార్గదర్శకాలను పాటించండి.",
                "sign_off": "భవదీయుడు, సమాచార విభాగం.",
                "cta": "మరిన్ని వివరాలు తెలుసుకోండి",
            },
            "mr": {
                "prefix_title": "सार्वजनिक जनजागृती",
                "urgent_title": "तातडीची सूचना",
                "greeting": "प्रिय {name}",
                "greeting_generic": "प्रिय नागरिक बंधू-भगिनींनो",
                "body_lead": "{city} मधील नागरिकांसाठी महत्त्वाची माहिती:",
                "body_lead_generic": "नागरिकांसाठी महत्त्वाची माहिती:",
                "guidelines": "कृपया अधिकृत मार्गदर्शक तत्त्वांचे पालन करा.",
                "sign_off": "आपला नम्र, जनसंपर्क विभाग.",
                "cta": "अधिक माहितीसाठी संपर्क साधा",
            },
            "bn": {
                "prefix_title": "জনসচেতনতা বার্তা",
                "urgent_title": "জরুরি বিজ্ঞপ্তি",
                "greeting": "প্রিয় {name}",
                "greeting_generic": "প্রিয় নাগরিকবৃন্দ",
                "body_lead": "{city} অঞ্চলের নাগরিকদের জন্য গুরুত্বপূর্ণ তথ্য:",
                "body_lead_generic": "সকল নাগরিকদের জন্য গুরুত্বপূর্ণ তথ্য:",
                "guidelines": "অনুগ্রহ করে সরকারি নির্দেশাবলী মেনে চলুন।",
                "sign_off": "ধন্যবাদান্তে, জনসেবা দল।",
                "cta": "বিস্তারিত জানতে এখানে দেখুন",
            },
            "gu": {
                "prefix_title": "જાહેર જાગૃતિ",
                "urgent_title": "તાકીદની સૂચના",
                "greeting": "પ્રિય {name}",
                "greeting_generic": "પ્રિય નાગરિકો",
                "body_lead": "{city} ના નાગરિકો માટે મહત્વપૂર્ણ માહિતી:",
                "body_lead_generic": "સર્વે નાગરિકો માટે મહત્વપૂર્ણ માહિતી:",
                "guidelines": "કૃપા કરીને સત્તાવાર માર્ગદર્શિકાનું પાલન કરો.",
                "sign_off": "આભાર, જનસંપર્ક વિભાગ.",
                "cta": "વધુ માહિતી માટે સંપર્ક કરો",
            },
            "ml": {
                "prefix_title": "പൊതുജന ബോധവൽക്കരണം",
                "urgent_title": "അടിയന്തര അറിയിപ്പ്",
                "greeting": "പ്രിയ {name}",
                "greeting_generic": "പ്രിയ പൗരന്മാരേ",
                "body_lead": "{city} നിവാസികൾക്കുള്ള പ്രധാന അറിയിപ്പ്:",
                "body_lead_generic": "പൊതുജനങ്ങൾക്കുള്ള പ്രധാന അറിയിപ്പ്:",
                "guidelines": "ദയവായി ഔദ്യോഗിക നിർദ്ദേശങ്ങൾ പാലിക്കുക.",
                "sign_off": "നന്ദി, പബ്ലിക് റിലേഷൻസ് ടീം.",
                "cta": "കൂടുതൽ വിവരങ്ങൾക്ക് ബന്ധപ്പെടുക",
            },
            "pa": {
                "prefix_title": "ਜਨਤਕ ਜਾਗਰੂਕਤਾ",
                "urgent_title": "ਜ਼ਰੂਰੀ ਸੂਚਨਾ",
                "greeting": "ਪਿਆਰੇ {name}",
                "greeting_generic": "ਪਿਆਰੇ ਨਾਗਰਿਕੋ",
                "body_lead": "{city} ਦੇ ਨਿਵਾਸੀਆਂ ਲਈ ਜ਼ਰੂਰੀ ਜਾਣਕਾਰੀ:",
                "body_lead_generic": "ਸਾਰੇ ਨਾਗਰਿਕਾਂ ਲਈ ਜ਼ਰੂਰੀ ਜਾਣਕਾਰੀ:",
                "guidelines": "ਕਿਰਪਾ ਕਰਕੇ ਅਧਿਕਾਰਤ ਦਿਸ਼ਾ-ਨਿਰਦੇਸ਼ਾਂ ਦੀ ਪਾਲਣਾ ਕਰੋ।",
                "sign_off": "ਧੰਨਵਾਦ ਸਹਿਤ, ਲੋਕ ਸੰਪਰਕ ਵਿਭਾਗ।",
                "cta": "ਹੋਰ ਜਾਣਕਾਰੀ ਲਈ ਸੰਪਰਕ ਕਰੋ",
            },
            "ur": {
                "prefix_title": "عوامی آگاہی",
                "urgent_title": "ضروری اطلاع",
                "greeting": "محترم {name}",
                "greeting_generic": "معزز شہری",
                "body_lead": "{city} کے شہریوں کے لیے اہم پیغام:",
                "body_lead_generic": "عوام الناس کے لیے اہم پیغام:",
                "guidelines": "براہ کرم سرکاری ہدایات پر عمل کریں۔",
                "sign_off": "شکریہ، تعلقات عامہ ٹیم۔",
                "cta": "مزید معلومات کے لیے رابطہ کریں",
            },
            "en": {
                "prefix_title": "Public Awareness",
                "urgent_title": "Urgent Advisory",
                "greeting": "Dear {name}",
                "greeting_generic": "Dear Citizen",
                "body_lead": "Important update for residents of {city}:",
                "body_lead_generic": "Important public awareness update:",
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

        # Occurrence-aware source placeholder extraction
        from collections import Counter
        from app.services.placeholder_service import extract_placeholders

        source_title_tokens = extract_placeholders(request.source_title)
        source_body_tokens = extract_placeholders(request.source_text)
        source_cta_tokens = extract_placeholders(request.source_cta)
        all_source_tokens = source_title_tokens + source_body_tokens + source_cta_tokens
        source_counts = Counter(all_source_tokens)

        # Contextual greeting and lead respecting whether placeholders were in source
        greeting_text = lang_data["greeting"] if "{name}" in source_counts else lang_data["greeting_generic"]
        lead_text = lang_data["body_lead"] if "{city}" in source_counts else lang_data["body_lead_generic"]

        body_lines = [
            f"{greeting_text},",
            "",
            lead_text,
            "",
            f"[{SUPPORTED_LANGUAGES[target_lang]} Translation]",
        ]

        # Extract factual points or bullet points from source
        source_lines = [line.strip() for line in request.source_text.split("\n") if line.strip()]
        for line in source_lines:
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
        translated_cta = request.source_cta or lang_data["cta"]

        # Occurrence-aware placeholder preservation reconciliation
        combined_output_tokens = (
            extract_placeholders(translated_title)
            + extract_placeholders(translated_body)
            + extract_placeholders(translated_cta)
        )
        output_counts = Counter(combined_output_tokens)

        deficit_tokens = []
        for ph, req_count in source_counts.items():
            got_count = output_counts.get(ph, 0)
            if got_count < req_count:
                deficit_tokens.extend([ph] * (req_count - got_count))

        if deficit_tokens:
            translated_body += "\n\n[" + " ".join(deficit_tokens) + "]"

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

    async def evaluate_content(self, request: ContentEvaluationRequest) -> ContentEvaluationResponse:
        """Evaluate public awareness copy for tone, grammar, factual consistency, and safety."""
        trigger = f"{request.title} {request.body} {request.constraints or ''} {request.reference_facts or ''}"
        await self._handle_simulated_delays_and_errors(trigger)

        findings: List[AIEvaluationFinding] = []
        tone = request.tone.lower()
        body = request.body
        body_lower = body.lower()

        dim_scores = {
            "language_grammar": 95.0,
            "readability": 90.0,
            "tone_consistency": 95.0,
            "factual_consistency": 90.0,
            "channel_compliance": 95.0,
        }
        if request.target_language:
            dim_scores["translation_consistency"] = 92.0

        # AI Tone Check
        if tone == "urgent":
            urgent_keywords = ["urgent", "alert", "immediate", "emergency", "warning", "critical", "attention", "danger"]
            if not any(k in body_lower for k in urgent_keywords):
                findings.append(
                    AIEvaluationFinding(
                        category="tone",
                        severity="medium",
                        title="Insufficient Tone of Urgency for Emergency Context",
                        explanation="The campaign objective specifies an 'urgent' tone, but the drafted message uses passive, non-urgent terminology.",
                        affected_text=body[:70] + "...",
                        suggested_correction="Open with clear, action-oriented alerting words (e.g., 'URGENT NOTICE: Take immediate precautionary steps').",
                        confidence=0.88,
                    )
                )
                dim_scores["tone_consistency"] = 75.0
        elif tone == "formal":
            informal_slang = ["hey guys", "check it out", "super cool", "don't miss out", "awesome"]
            if any(s in body_lower for s in informal_slang):
                findings.append(
                    AIEvaluationFinding(
                        category="tone",
                        severity="medium",
                        title="Casual Slang in Formal Civic Communication",
                        explanation="Colloquial phrases weaken the official authority and neutrality of public sector advisories.",
                        affected_text="Informal phrasing detected",
                        suggested_correction="Adopt respectful, authoritative phrasing appropriate for civic administration.",
                        confidence=0.92,
                    )
                )
                dim_scores["tone_consistency"] = 78.0

        # AI Repetition / Clarity Check
        sentences = [s.strip() for s in body.split(".") if s.strip()]
        if len(sentences) > 2 and sentences[0].lower() == sentences[1].lower():
            findings.append(
                AIEvaluationFinding(
                    category="grammar",
                    severity="low",
                    title="Redundant Consecutive Sentences",
                    explanation="Consecutive sentences repeat identical phrasing, reducing citizen engagement.",
                    affected_text=sentences[0],
                    suggested_correction="Consolidate duplicate statements into a single clear instruction.",
                    confidence=0.95,
                )
            )
            dim_scores["language_grammar"] = 85.0

        # AI Factual Verification Advisory
        if request.reference_facts and ("vaccine" in body_lower or "curfew" in body_lower or "shelter" in body_lower):
            if "helpline" not in body_lower and "contact" not in body_lower:
                findings.append(
                    AIEvaluationFinding(
                        category="factual",
                        severity="low",
                        title="Factual Verification Recommendation",
                        explanation="Operational directives mentioned in the body should provide contact verification for citizens seeking confirmation.",
                        affected_text="Operational instructions",
                        suggested_correction="Include verified municipal helpline or department website alongside public directives.",
                        confidence=0.82,
                    )
                )

        # AI Translation Consistency Check (when evaluating translation against parent)
        if request.target_language and request.parent_body:
            parent_lower = request.parent_body.lower()
            if "helpline" in parent_lower and "helpline" not in body_lower and "10" not in body_lower:
                findings.append(
                    AIEvaluationFinding(
                        category="translation",
                        severity="high",
                        title="Assistance Guidance Altered During Translation",
                        explanation="The original copy offered official assistance guidance that appears diminished or altered in the translated variant.",
                        affected_text=body[-80:],
                        suggested_correction="Ensure the helpline and assistance clause is clearly stated in the target language.",
                        confidence=0.9,
                    )
                )
                if "translation_consistency" in dim_scores:
                    dim_scores["translation_consistency"] = 70.0

        summary = (
            f"Quality evaluation completed via mock AI evaluator ({len(findings)} editorial findings identified). "
            f"Tone assessed for '{request.tone}', channel '{request.channel}'."
        )

        return ContentEvaluationResponse(
            findings=findings,
            dimension_scores=dim_scores,
            summary=summary,
            provider_metadata={
                "provider": "mock",
                "model": "mock-quality-evaluator-v1",
                "simulated": True,
            },
        )

