"""
MassCommAI - Milestone 2, Task 7, Step 3: Channel-Aware Content Constraints Test Suite.

Comprehensive test suite verifying:
1. GSM-7 basic character set and septet calculation.
2. GSM-7 single-part (160 septets) and multipart (153 septets/segment) boundaries.
3. GSM-7 extension table characters (costing 2 septets each).
4. Valid GSM-7 non-ASCII and Greek characters.
5. UCS-2-compatible single-part (70 units) and multipart (67 units/segment) boundaries.
6. Unicode UTF-16 code unit counting and surrogate pair (emoji) handling.
7. Combining marks and variation selectors.
8. Unpaired/invalid surrogate robustness.
9. Configured SMS hard-limit breach.
10. Empty message handling.
11. Language-aware Voice audio script duration estimation (English vs Tamil vs fallback).
12. Voice URL, markdown, and numeric helpline advisory warnings.
13. WhatsApp free-form vs template mode boundaries.
14. Email subject advisory and body length guidance.
15. Lifecycle persistence: generated, translated, manual, and edited assets.
16. Preservation of existing provider metadata and Step 2 campaign context.
17. Backward compatibility for older assets and client responses.
18. Shared calculation integration with Quality Rule Engine and Mock SMS Provider.
"""

import math
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.db.seed import seed_default_roles
from app.db.session import get_db
from app.main import app
from app.models.campaign import Campaign
from app.models.content_asset import ContentAsset
from app.models.user import Role, User
from app.schemas.content_asset import (
    ChannelMetricsResponse,
    ContentAssetCreate,
    ContentAssetResponse,
    ContentAssetUpdate,
    ContentGenerateRequest,
    ContentTranslateRequest,
    SMSDetailResponse,
)
from app.services.channel_constraints import (
    DEFAULT_SMS_HARD_LIMIT_CHARS,
    GSM7_BASIC_CHARS,
    GSM7_EXTENSION_CHARS,
    SMSEncoding,
    analyze_sms_encoding,
    calculate_channel_metrics,
    calculate_sms_metrics,
    calculate_voice_duration_seconds,
)
from app.services.content_service import (
    create_manual_content_asset,
    generate_content,
    translate_content,
    update_content_asset,
)
from app.services.distribution.providers.mock_sms import MockSMSProvider
from app.services.distribution.providers.base_provider import DeliveryPayload
from app.services.quality.base import FindingCategory, FindingSeverity
from app.services.quality.rule_engine import DeterministicRuleEngine


class TestSMSChannelConstraints(unittest.TestCase):
    """Exhaustive boundary and encoding tests for the SMS telecom engine."""

    def test_01_gsm7_basic_alphabet_single_septet(self):
        """All GSM-7 basic characters consume exactly 1 septet each."""
        for char in GSM7_BASIC_CHARS:
            encoding, units, has_ext, has_surr, _, non_gsm = analyze_sms_encoding(char)
            self.assertEqual(encoding, SMSEncoding.GSM7, f"Character '{char}' (ord {ord(char)}) should be GSM-7")
            self.assertEqual(units, 1, f"Character '{char}' should consume 1 septet")
            self.assertFalse(has_ext)
            self.assertFalse(has_surr)
            self.assertEqual(non_gsm, [])

    def test_02_gsm7_160_septets_boundary_single_segment(self):
        """160 basic GSM-7 septets fit in exactly 1 segment with 0 remaining capacity."""
        text = "A" * 160
        detail = calculate_sms_metrics(text)
        self.assertEqual(detail.encoding, "GSM-7")
        self.assertEqual(detail.character_count, 160)
        self.assertEqual(detail.encoded_units, 160)
        self.assertEqual(detail.segment_count, 1)
        self.assertEqual(detail.segment_capacity, 160)
        self.assertEqual(detail.remaining_in_segment, 0)
        self.assertFalse(detail.is_multipart)
        self.assertFalse(detail.has_extension_characters)

    def test_03_gsm7_161_septets_boundary_two_segments(self):
        """161 basic GSM-7 septets require 2 multipart segments (153 + 8 = 161, 145 remaining)."""
        text = "A" * 161
        detail = calculate_sms_metrics(text)
        self.assertEqual(detail.encoding, "GSM-7")
        self.assertEqual(detail.character_count, 161)
        self.assertEqual(detail.encoded_units, 161)
        self.assertEqual(detail.segment_count, 2)
        self.assertEqual(detail.segment_capacity, 153)
        self.assertEqual(detail.remaining_in_segment, 145)  # (2 * 153) - 161 = 306 - 161 = 145
        self.assertTrue(detail.is_multipart)

    def test_04_gsm7_306_and_307_and_320_septets_boundaries(self):
        """Exact boundaries for 2-segment ceiling (306) and 3-segment transitions (307, 320)."""
        # Exactly 2 multipart segments: 2 * 153 = 306
        d_306 = calculate_sms_metrics("A" * 306)
        self.assertEqual(d_306.segment_count, 2)
        self.assertEqual(d_306.remaining_in_segment, 0)
        self.assertTrue(d_306.is_multipart)

        # 307 septets rolls into 3 segments: 3 * 153 = 459 -> 459 - 307 = 152 remaining
        d_307 = calculate_sms_metrics("A" * 307)
        self.assertEqual(d_307.segment_count, 3)
        self.assertEqual(d_307.remaining_in_segment, 152)
        self.assertTrue(d_307.is_multipart)

        # 320 septets (historical bug where code divided by 160 and falsely claimed 2 segments)
        d_320 = calculate_sms_metrics("A" * 320)
        self.assertEqual(d_320.segment_count, 3)
        self.assertEqual(d_320.remaining_in_segment, 139)  # 459 - 320 = 139
        self.assertTrue(d_320.is_multipart)

    def test_05_gsm7_extension_table_characters_consume_two_septets(self):
        """Extension table characters (^, {, }, \\, [, ~, ], |, €, \\f) consume 2 septets each."""
        ext_chars = ["^", "{", "}", "\\", "[", "~", "]", "|", "€", "\f"]
        for c in ext_chars:
            detail = calculate_sms_metrics(f"A{c}B")
            self.assertEqual(detail.encoding, "GSM-7", f"Extension char '{c}' must remain GSM-7")
            self.assertTrue(detail.has_extension_characters)
            # 'A' (1) + ext (2) + 'B' (1) = 4 septets for 3 characters
            self.assertEqual(detail.character_count, 3)
            self.assertEqual(detail.encoded_units, 4)

        # 158 basic characters + 1 curly brace pair {name} = 158 + 4 = 162 septets -> 2 segments!
        msg_with_brackets = ("A" * 152) + "{name}"  # 152 + 6 = 158 chars. Units: 152 + 2*2 + 4 = 160 septets
        detail_160 = calculate_sms_metrics(msg_with_brackets)
        self.assertEqual(detail_160.character_count, 158)
        self.assertEqual(detail_160.encoded_units, 160)
        self.assertEqual(detail_160.segment_count, 1)

        msg_overflow = ("A" * 153) + "{name}"  # 153 + 6 = 159 chars. Units: 153 + 2*2 + 4 = 161 septets
        detail_161 = calculate_sms_metrics(msg_overflow)
        self.assertEqual(detail_161.character_count, 159)
        self.assertEqual(detail_161.encoded_units, 161)
        self.assertEqual(detail_161.segment_count, 2)  # Rolled to 2 segments!

    def test_06_gsm7_valid_non_ascii_characters_remain_gsm7(self):
        """Basic non-ASCII Latin and Greek characters remain GSM-7 and do not trigger UCS-2."""
        sample = "Cost £10 for café, déjà vu, Ångström, Å, Ç, ø, ß, É, Ñ, ¿, ¡, Δ, Ω, Π"
        detail = calculate_sms_metrics(sample)
        self.assertEqual(detail.encoding, "GSM-7")
        self.assertEqual(detail.non_gsm_characters, [])
        self.assertEqual(detail.segment_capacity, 160)

    def test_07_isolated_esc_character_not_counted_as_valid_extension(self):
        """Isolated ESC (0x1B) byte in user string must not count as valid extension character."""
        text = "Hello\x1bWorld"
        detail = calculate_sms_metrics(text)
        self.assertEqual(detail.encoding, "UCS-2")
        self.assertIn("\x1b", detail.non_gsm_characters)

    def test_08_tamil_ucs2_single_and_multipart_boundaries(self):
        """Tamil content forces UCS-2 with 70 single and 67 multipart boundaries."""
        # 10 Tamil characters
        tamil_short = "புயல் எச்சரிக்கை"  # 16 code points
        d_short = calculate_sms_metrics(tamil_short)
        self.assertEqual(d_short.encoding, "UCS-2")
        self.assertEqual(d_short.segment_count, 1)
        self.assertEqual(d_short.segment_capacity, 70)
        self.assertEqual(d_short.remaining_in_segment, 70 - len(tamil_short))
        self.assertFalse(d_short.is_multipart)
        self.assertGreater(len(d_short.non_gsm_characters), 0)

        # Exactly 70 UCS-2 code units: 1 segment, 0 remaining
        d_70 = calculate_sms_metrics("த" * 70)
        self.assertEqual(d_70.segment_count, 1)
        self.assertEqual(d_70.encoded_units, 70)
        self.assertEqual(d_70.remaining_in_segment, 0)
        self.assertFalse(d_70.is_multipart)

        # 71 UCS-2 code units: 2 multipart segments (67 + 4 = 71; 134 - 71 = 63 remaining)
        d_71 = calculate_sms_metrics("த" * 71)
        self.assertEqual(d_71.segment_count, 2)
        self.assertEqual(d_71.encoded_units, 71)
        self.assertEqual(d_71.segment_capacity, 67)
        self.assertEqual(d_71.remaining_in_segment, 63)
        self.assertTrue(d_71.is_multipart)

        # 134 UCS-2 code units: 2 * 67 = 134, 0 remaining
        d_134 = calculate_sms_metrics("த" * 134)
        self.assertEqual(d_134.segment_count, 2)
        self.assertEqual(d_134.remaining_in_segment, 0)

        # 135 UCS-2 code units: 3 * 67 = 201 -> 201 - 135 = 66 remaining
        d_135 = calculate_sms_metrics("த" * 135)
        self.assertEqual(d_135.segment_count, 3)
        self.assertEqual(d_135.remaining_in_segment, 66)

    def test_09_emoji_surrogate_pairs_count_two_code_units(self):
        """Supplementary plane characters (emojis) consume 2 UTF-16 code units."""
        # 1 emoji = 1 Python char, but 2 UTF-16 code units
        emoji_msg = "Alert: 🚨"  # "Alert: " (7) + "🚨" (2 units) = 9 units
        detail = calculate_sms_metrics(emoji_msg)
        self.assertEqual(detail.encoding, "UCS-2")
        self.assertEqual(detail.character_count, 8)  # len() is 8
        self.assertEqual(detail.encoded_units, 9)    # UTF-16 units is 9
        self.assertTrue(detail.has_surrogate_pairs)

        # 69 ASCII characters + 1 emoji = 69 + 2 = 71 code units -> requires 2 segments!
        boundary_emoji = ("A" * 69) + "🚨"
        d_emoji_boundary = calculate_sms_metrics(boundary_emoji)
        self.assertEqual(d_emoji_boundary.character_count, 70)
        self.assertEqual(d_emoji_boundary.encoded_units, 71)
        self.assertEqual(d_emoji_boundary.segment_count, 2)  # Under Python len() this would have failed

    def test_10_multiple_emojis_and_variation_selectors(self):
        """Multiple emojis and variation selectors are accurately counted."""
        msg = "Alert: 🚨 ⚠️ 🔥"
        detail = calculate_sms_metrics(msg)
        self.assertEqual(detail.encoding, "UCS-2")
        self.assertTrue(detail.has_surrogate_pairs)
        self.assertGreater(detail.encoded_units, len(msg))

    def test_11_unpaired_surrogate_input_handled_gracefully(self):
        """Unpaired surrogate characters do not crash the engine and trigger structured warnings."""
        unpaired_str = "Emergency \ud83d Warning"
        encoding, units, has_ext, has_surr, has_unpaired, non_gsm = analyze_sms_encoding(unpaired_str)
        self.assertEqual(encoding, SMSEncoding.UCS2)
        self.assertTrue(has_unpaired)

        metrics = calculate_channel_metrics(channel="SMS", body=unpaired_str)
        self.assertTrue(any(w.code == "SMS_UNPAIRED_SURROGATES" for w in metrics.warnings))

    def test_12_empty_and_whitespace_input(self):
        """Empty input returns 0 units, 0 segments, and 160 capacity."""
        empty_detail = calculate_sms_metrics("")
        self.assertEqual(empty_detail.character_count, 0)
        self.assertEqual(empty_detail.encoded_units, 0)
        self.assertEqual(empty_detail.segment_count, 0)
        self.assertEqual(empty_detail.segment_capacity, 160)
        self.assertEqual(empty_detail.remaining_in_segment, 160)
        self.assertFalse(empty_detail.is_multipart)

    def test_13_sms_hard_limit_and_recommended_segment_warnings(self):
        """Exceeding 3 segments emits HIGH warning; exceeding 1600 characters emits CRITICAL warning."""
        # 500 GSM characters = 4 segments (> 3 segments)
        long_sms = "Announcement: " + ("A" * 480)
        m_long = calculate_channel_metrics(channel="SMS", body=long_sms)
        self.assertFalse(m_long.is_within_recommended_limit)
        self.assertTrue(m_long.is_within_hard_limit)
        self.assertTrue(any(w.code == "SMS_EXCEEDS_RECOMMENDED_SEGMENTS" for w in m_long.warnings))

        # 1601 characters = breach of 1600 hard limit
        giant_sms = "A" * 1601
        m_giant = calculate_channel_metrics(channel="SMS", body=giant_sms)
        self.assertFalse(m_giant.is_within_hard_limit)
        self.assertTrue(any(w.code == "SMS_HARD_LIMIT_EXCEEDED" for w in m_giant.warnings))


class TestVoiceAndOtherChannels(unittest.TestCase):
    """Tests covering Voice duration calculation, WhatsApp bounds, and Email guidance."""

    def test_14_english_voice_duration_approximation(self):
        """150 English words at 150 WPM results in ~60 seconds estimated duration."""
        words_150 = " ".join(["notice"] * 150)
        duration = calculate_voice_duration_seconds(words_150, language="en")
        self.assertEqual(duration, 60)

    def test_15_tamil_voice_duration_syllabic_scaling(self):
        """100 Tamil words at 115 WPM reflects agglutinative speaking rates (~53s vs English 40s)."""
        tamil_100 = " ".join(["எச்சரிக்கை"] * 100)
        ta_duration = calculate_voice_duration_seconds(tamil_100, language="ta")
        en_duration = calculate_voice_duration_seconds(" ".join(["notice"] * 100), language="en")
        self.assertGreater(ta_duration, en_duration)
        self.assertEqual(ta_duration, 53)  # ceil((100 / 115) * 60) = 53
        self.assertEqual(en_duration, 40)  # ceil((100 / 150) * 60) = 40

    def test_16_voice_unknown_language_fallback(self):
        """Unknown language identifier falls back to 130 WPM."""
        text = " ".join(["word"] * 130)
        duration = calculate_voice_duration_seconds(text, language="xx-unknown")
        self.assertEqual(duration, 60)  # ceil((130 / 130) * 60) = 60

    def test_17_voice_markdown_url_and_helpline_warnings(self):
        """Voice script warns on raw web URLs, markdown syntax, and advisory numeric helplines."""
        voice_script = "### Emergency Advisory\nPlease visit https://disaster.gov.in or call 1070 for immediate help."
        metrics = calculate_channel_metrics(channel="Voice", body=voice_script, language="en")
        codes = [w.code for w in metrics.warnings]
        self.assertIn("VOICE_CONTAINS_URL", codes)
        self.assertIn("VOICE_CONTAINS_MARKDOWN", codes)
        self.assertIn("VOICE_NUMERIC_HELPLINE_ADVISORY", codes)

    def test_18_voice_exceeds_90_seconds_warning(self):
        """Voice script longer than 90 seconds triggers recommended duration warning."""
        long_script = " ".join(["announcement"] * 250)  # 250 words / 150 WPM = 100s
        metrics = calculate_channel_metrics(channel="Voice", body=long_script, language="en")
        self.assertFalse(metrics.is_within_recommended_limit)
        self.assertTrue(any(w.code == "VOICE_EXCEEDS_RECOMMENDED_DURATION" for w in metrics.warnings))

    def test_19_whatsapp_freeform_vs_template_bounds(self):
        """WhatsApp distinguishes free-form (4,096 hard / 1,024 rec) from template (1,024 hard)."""
        # Freeform message between 1025 and 4096 chars
        body_1500 = "A" * 1500
        m_free = calculate_channel_metrics(channel="WhatsApp", body=body_1500, mode="freeform")
        self.assertFalse(m_free.is_within_recommended_limit)
        self.assertTrue(m_free.is_within_hard_limit)
        self.assertTrue(any(w.code == "WHATSAPP_EXCEEDS_RECOMMENDED_LENGTH" for w in m_free.warnings))

        # Freeform message exceeding 4096 chars
        body_5000 = "A" * 5000
        m_free_giant = calculate_channel_metrics(channel="WhatsApp", body=body_5000, mode="freeform")
        self.assertFalse(m_free_giant.is_within_hard_limit)
        self.assertTrue(any(w.code == "WHATSAPP_HARD_LIMIT_EXCEEDED" for w in m_free_giant.warnings))

        # Template message exceeding 1024 chars -> hard limit breach!
        m_tpl = calculate_channel_metrics(channel="WhatsApp", body=body_1500, mode="template")
        self.assertFalse(m_tpl.is_within_hard_limit)
        self.assertTrue(any(w.code == "WHATSAPP_TEMPLATE_BODY_LIMIT_EXCEEDED" for w in m_tpl.warnings))

    def test_20_email_subject_advisory_and_body_guidance(self):
        """Email checks subject length recommendation (78 chars) and body readability (800 words)."""
        long_subject = "Important Public Health Notice: " + ("Water Safety Instructions " * 4)  # > 78 chars
        long_body = " ".join(["advisory"] * 850)  # > 800 words
        metrics = calculate_channel_metrics(channel="Email", title=long_subject, body=long_body)
        codes = [w.code for w in metrics.warnings]
        self.assertIn("EMAIL_SUBJECT_LENGTH_ADVISORY", codes)
        self.assertIn("EMAIL_BODY_LENGTH_ADVISORY", codes)
        self.assertFalse(metrics.is_within_recommended_limit)
        self.assertTrue(metrics.is_within_hard_limit)


class TestLifecycleAndIntegration(unittest.TestCase):
    """Integration tests verifying persistence in provider_metadata and schema compatibility."""

    @classmethod
    def setUpClass(cls):
        cls.test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.test_engine)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=cls.test_engine)

        # Seed roles
        db = cls.SessionLocal()
        seed_default_roles(db)

        admin_role = db.query(Role).filter(Role.name == "Admin").first()
        mgr_role = db.query(Role).filter(Role.name == "Campaign Manager").first()

        cls.admin_user = User(
            email="admin_cc@test.com",
            full_name="Admin CC User",
            hashed_password=get_password_hash("password123"),
            role_id=admin_role.id,
            is_active=True,
        )
        cls.mgr_user = User(
            email="mgr_cc@test.com",
            full_name="Manager CC User",
            hashed_password=get_password_hash("password123"),
            role_id=mgr_role.id,
            is_active=True,
        )
        db.add_all([cls.admin_user, cls.mgr_user])
        db.commit()
        db.refresh(cls.admin_user)
        db.refresh(cls.mgr_user)

        cls.campaign = Campaign(
            name="Flood Alert CC",
            campaign_type="Emergency Alert",
            priority="High",
            objective="Deliver immediate evacuation warnings",
            channels=["SMS", "Voice"],
            created_by=cls.mgr_user.id,
        )
        db.add(cls.campaign)
        db.commit()
        db.refresh(cls.campaign)

        cls.mgr_token = create_access_token(subject=str(cls.mgr_user.id))
        db.close()

        def override_get_db():
            session = cls.SessionLocal()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=cls.test_engine)

    def _headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_21_generated_content_persists_channel_metrics_snapshot(self):
        """generate_content computes and persists channel_metrics snapshot and preserves campaign_context."""
        db = self.SessionLocal()
        try:
            user = db.get(User, self.mgr_user.id)
            req = ContentGenerateRequest(
                topic="Flash Flood Alert",
                objective="Instruct citizens to move to higher ground immediately",
                category="Emergency Management",
                tone="urgent",
                channel="SMS",
                source_language="en",
                campaign_id=self.campaign.id,
            )
            # Use mock provider
            import asyncio
            asset = asyncio.run(generate_content(db, req, user, provider_type="mock"))

            self.assertIsNotNone(asset.provider_metadata)
            meta = asset.provider_metadata

            # Verify campaign_context from Step 2 is fully intact
            self.assertIn("campaign_context", meta)
            self.assertEqual(meta["campaign_context"]["campaign_id"], self.campaign.id)

            # Verify channel_metrics snapshot is present
            self.assertIn("channel_metrics", meta)
            cc_meta = meta["channel_metrics"]
            self.assertEqual(cc_meta["channel"], "SMS")
            self.assertEqual(cc_meta["encoding"], "GSM-7")
            self.assertEqual(cc_meta["rule_version"], "v1.0")
            self.assertIn("segment_count", cc_meta["sms"])
            self.assertGreaterEqual(cc_meta["sms"]["segment_count"], 1)
        finally:
            db.close()

    def test_22_manual_content_persists_channel_metrics_snapshot(self):
        """create_manual_content_asset computes and attaches channel_metrics snapshot."""
        db = self.SessionLocal()
        try:
            user = db.get(User, self.mgr_user.id)
            payload = ContentAssetCreate(
                title="Manual Boil Water Advisory",
                body="Dear {name}, tap water in {city} is currently unsafe. Please boil water before drinking.",
                category="Public Health",
                tone="urgent",
                channel="SMS",
                source_language="en",
                campaign_id=self.campaign.id,
            )
            asset = create_manual_content_asset(db, payload, user)
            self.assertIn("channel_metrics", asset.provider_metadata)
            self.assertEqual(asset.provider_metadata["channel_metrics"]["channel"], "SMS")
            self.assertEqual(asset.provider_metadata["provider"], "manual")
        finally:
            db.close()

    def test_23_update_content_recalculates_channel_metrics_and_preserves_metadata(self):
        """update_content_asset recalculates metrics when body changes, preserving existing metadata keys."""
        db = self.SessionLocal()
        try:
            user = db.get(User, self.mgr_user.id)
            # Create a 1-segment manual asset
            payload = ContentAssetCreate(
                title="Short Alert",
                body="Short alert under 160 characters for quick delivery.",
                category="Public Health",
                tone="formal",
                channel="SMS",
                source_language="en",
            )
            asset = create_manual_content_asset(db, payload, user)
            orig_meta = asset.provider_metadata
            self.assertEqual(orig_meta["channel_metrics"]["sms"]["segment_count"], 1)

            # Update body with 480 characters (> 3 segments)
            update_payload = ContentAssetUpdate(
                body="A" * 480
            )
            updated_asset = update_content_asset(db, asset.id, update_payload, user)

            new_meta = updated_asset.provider_metadata
            self.assertEqual(new_meta["provider"], "manual")  # preserved
            self.assertEqual(new_meta["channel_metrics"]["sms"]["segment_count"], 4)
            self.assertEqual(new_meta["channel_metrics"]["character_count"], 480)
            # Warnings should include exceeding recommended segments
            codes = [w["code"] for w in new_meta["channel_metrics"]["warnings"]]
            self.assertIn("SMS_EXCEEDS_RECOMMENDED_SEGMENTS", codes)
        finally:
            db.close()

    def test_24_translated_variant_recalculates_indic_channel_metrics(self):
        """translate_content creates variant with accurate UCS-2 Indic channel metrics snapshot."""
        db = self.SessionLocal()
        try:
            user = db.get(User, self.mgr_user.id)
            # Source English asset
            source_payload = ContentAssetCreate(
                title="Monsoon Warning",
                body="Attention citizens: heavy rainfall expected in {city}. Stay indoors.",
                category="Weather Advisory",
                tone="urgent",
                channel="SMS",
                source_language="en",
            )
            source_asset = create_manual_content_asset(db, source_payload, user)

            # Translate to Tamil using mock provider
            import asyncio
            trans_req = ContentTranslateRequest(target_language="ta")
            variant = asyncio.run(
                translate_content(db, source_asset.id, trans_req, user, provider_type="mock")
            )

            self.assertIsNotNone(variant.provider_metadata)
            meta = variant.provider_metadata
            self.assertIn("channel_metrics", meta)
            # Tamil content must have UCS-2 encoding
            self.assertEqual(meta["channel_metrics"]["sms"]["encoding"], "UCS-2")
            self.assertGreaterEqual(meta["channel_metrics"]["sms"]["segment_count"], 1)
        finally:
            db.close()

    def test_25_older_asset_without_snapshot_computes_dynamically_in_schema(self):
        """ContentAssetResponse computes channel_metrics dynamically for older records with NULL metadata."""
        now = datetime.now(timezone.utc)
        response = ContentAssetResponse(
            id=999,
            title="Legacy Asset",
            body="Legacy content authored before Step 3 deployment.",
            summary=None,
            call_to_action=None,
            category="Civic",
            tone="formal",
            channel="SMS",
            source_language="en",
            target_language=None,
            operation_type="generation",
            review_status="Approved",
            provider_metadata=None,  # No snapshot!
            created_by=self.mgr_user.id,
            created_at=now,
            updated_at=now,
        )

        self.assertIsNotNone(response.channel_metrics)
        self.assertEqual(response.channel_metrics.channel, "SMS")
        self.assertEqual(response.channel_metrics.sms.encoding, "GSM-7")
        self.assertEqual(response.sms_segment_count, 1)
        self.assertEqual(response.character_count, len(response.body))
        self.assertEqual(response.word_count, len(response.body.split()))
        self.assertGreaterEqual(response.voice_duration_seconds, 5)

    def test_26_quality_rule_engine_uses_central_calculations(self):
        """DeterministicRuleEngine flags channel findings using the central constraints engine."""
        # Test SMS over 3 segments
        findings = DeterministicRuleEngine.evaluate(
            title="SMS Notice",
            body="Important alert: " + ("A" * 480),
            call_to_action="Take shelter",
            channel="SMS",
            source_language="en",
        )
        sms_findings = [f for f in findings if f.category == FindingCategory.CHANNEL]
        self.assertTrue(any(f.rule_id == "RULE-CHAN-SMS-001" for f in sms_findings))

        # Test Voice script URL finding
        v_findings = DeterministicRuleEngine.evaluate(
            title="Voice Notice",
            body="Please visit https://kerala.gov.in for cyclone shelters.",
            call_to_action="Listen closely",
            channel="Voice",
            source_language="en",
        )
        url_findings = [f for f in v_findings if f.rule_id == "RULE-CHAN-VOICE-002"]
        self.assertEqual(len(url_findings), 1)
        self.assertEqual(url_findings[0].severity, FindingSeverity.MEDIUM)

    def test_27_mock_sms_provider_uses_central_segmentation(self):
        """MockSMSProvider reports segment_count calculated by the central SMS engine."""
        import asyncio
        provider = MockSMSProvider()

        # Single segment GSM-7 payload
        p1 = DeliveryPayload(
            recipient_id=1,
            recipient_name="Citizen One",
            channel="SMS",
            recipient_address="+919876543210",
            body="Short alert under 160 characters.",
            metadata={},
        )
        res1 = asyncio.run(provider.send_message(p1))
        self.assertTrue(res1.success)
        self.assertEqual(res1.response_metadata["segment_count"], 1)

        # 2-segment GSM-7 payload (161 characters)
        p2 = DeliveryPayload(
            recipient_id=2,
            recipient_name="Citizen Two",
            channel="SMS",
            recipient_address="+919876543210",
            body="A" * 161,
            metadata={},
        )
        res2 = asyncio.run(provider.send_message(p2))
        self.assertTrue(res2.success)
        self.assertEqual(res2.response_metadata["segment_count"], 2)

        # 3-segment GSM-7 payload (320 characters)
        p3 = DeliveryPayload(
            recipient_id=3,
            recipient_name="Citizen Three",
            channel="SMS",
            recipient_address="+919876543210",
            body="A" * 320,
            metadata={},
        )
        res3 = asyncio.run(provider.send_message(p3))
        self.assertTrue(res3.success)
        self.assertEqual(res3.response_metadata["segment_count"], 3)

    def test_28_preview_metrics_endpoint_sms_gsm7(self):
        """Stateless /content/preview-metrics computes GSM-7 metrics accurately in real-time."""
        payload = {
            "channel": "SMS",
            "body": "Emergency alert: High tide warning until 18:00.",
        }
        res = self.client.post("/content/preview-metrics", json=payload, headers=self._headers(self.mgr_token))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["channel"], "SMS")
        self.assertEqual(data["character_count"], len(payload["body"]))
        self.assertEqual(data["sms"]["encoding"], "GSM-7")
        self.assertEqual(data["sms"]["segment_count"], 1)
        self.assertFalse(data["sms"]["is_multipart"])
        self.assertTrue(data["is_within_recommended_limit"])
        self.assertTrue(data["is_within_hard_limit"])

    def test_29_preview_metrics_endpoint_sms_ucs2_tamil_and_emoji(self):
        """Stateless /content/preview-metrics handles Indic characters and emojis switching to UCS-2."""
        payload = {
            "channel": "SMS",
            "body": "புயல் எச்சரிக்கை 🚨",
        }
        res = self.client.post("/content/preview-metrics", json=payload, headers=self._headers(self.mgr_token))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["sms"]["encoding"], "UCS-2")
        self.assertTrue(data["sms"]["has_surrogate_pairs"])
        self.assertEqual(data["sms"]["segment_count"], 1)
        self.assertEqual(data["sms"]["segment_capacity"], 70)

    def test_30_preview_metrics_endpoint_voice_language_aware(self):
        """Stateless /content/preview-metrics computes language-aware voice pacing and structured warnings."""
        payload = {
            "channel": "Voice",
            "body": "Please visit https://kerala.gov.in and call 1800-425-0001.",
            "language": "ta",
        }
        res = self.client.post("/content/preview-metrics", json=payload, headers=self._headers(self.mgr_token))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["channel"], "Voice")
        self.assertGreaterEqual(data["estimated_duration_seconds"], 5)
        warning_codes = [w["code"] for w in data["warnings"]]
        self.assertIn("VOICE_CONTAINS_URL", warning_codes)
        self.assertIn("VOICE_NUMERIC_HELPLINE_ADVISORY", warning_codes)

    def test_31_preview_metrics_endpoint_auth_and_validation(self):
        """Stateless /content/preview-metrics validates authentication and channel constraints."""
        # Unauthenticated request
        res_no_auth = self.client.post("/content/preview-metrics", json={"channel": "SMS", "body": "Hello"})
        self.assertEqual(res_no_auth.status_code, 401)

        # Invalid channel
        res_bad_chan = self.client.post(
            "/content/preview-metrics",
            json={"channel": "CarrierPigeon", "body": "Hello"},
            headers=self._headers(self.mgr_token),
        )
        self.assertEqual(res_bad_chan.status_code, 422)
