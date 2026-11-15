"""Comprehensive test suite for Task 9 Phase 2: Channel Constraints Integration in Pre-Dispatch Readiness & Delivery Engine.

Covers all 33 required verification scenarios:
- Scenarios 1-5: SMS GSM-7 single vs multipart boundaries and segment counting in readiness.
- Scenarios 6-10: SMS UCS-2 single and multipart boundaries for Indic languages and surrogates/emojis.
- Scenarios 11-14: SMS aggregated segment calculations across mixed-language audiences and total projected segment counters.
- Scenarios 15-17: SMS hard-limit breach (> 1600 chars) causing is_ready = False, blocking job creation with HTTP 400.
- Scenarios 18-20: Partial audience hard-limit breach during staging: valid queued as PENDING, invalid staged as FAILED.
- Scenarios 21-23: Worker-level pre-flight guard in delivery_service.py: blocks oversized payload locally, does NOT invoke provider.
- Scenarios 24-25: WhatsApp template (> 1024) and freeform (> 4096) hard-limit blocking in readiness.
- Scenarios 26-28: Voice duration calculation for Indic languages, warning > 90s allows is_ready = True, URL/Markdown warnings.
- Scenarios 29-30: Email subject line > 255 chars blocks readiness; subject line > 78 chars warning allows is_ready = True.
- Scenarios 31-32: Web notification title (> 255) and body (> 4096) hard-limit validation blocking readiness.
- Scenario 33: Permanent constraint violations (PAYLOAD_EXCEEDS_CHANNEL_HARD_LIMIT) excluded from retry_failed_deliveries().
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from app.db.base import Base
from app.db.seed import seed_default_roles
from app.models.user import User
from app.models.campaign import Campaign
from app.models.segment import Segment
from app.models.template import Template
from app.models.content_asset import ContentAsset
from app.models.audience import AudienceMember
from app.models.distribution import DistributionJob, DeliveryRecord, DeliveryAttempt
from app.core.security import get_password_hash
from app.services.channel_constraints import (
    SMSEncoding,
    WarningSeverity,
    calculate_channel_metrics,
    calculate_sms_metrics,
    calculate_voice_duration_seconds,
)
from app.services.distribution.base import (
    DeliveryStatus,
    JobStatus,
    NON_RETRYABLE_ERROR_CODES,
)
from app.services.distribution.job_service import (
    check_campaign_readiness,
    create_distribution_job,
)
from app.services.distribution.delivery_service import (
    process_job_batch,
    retry_failed_deliveries,
)
from app.services.distribution.providers import get_provider


class BaseDistributionConstraintsTest(unittest.TestCase):
    """Common test fixture setting up an in-memory database and authenticated user roles."""

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    def setUp(self):
        Base.metadata.create_all(bind=self.engine)
        self.db = self.TestingSessionLocal()
        roles = seed_default_roles(self.db)
        self.admin_role = roles["Admin"]
        self.manager_role = roles["Campaign Manager"]

        self.admin_user = User(
            full_name="Director Admin",
            email="admin@agency.gov.in",
            hashed_password=get_password_hash("AdminPass123!"),
            role_id=self.admin_role.id,
            is_active=True,
        )
        self.manager_user = User(
            full_name="Manager Maya",
            email="maya@agency.gov.in",
            hashed_password=get_password_hash("ManagerPass123!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.db.add_all([self.admin_user, self.manager_user])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def _create_campaign_with_audience(
        self,
        channel: str,
        title: str,
        body: str,
        audience_members: list,
        variants: list = None,
        is_template: bool = False,
    ):
        """Helper to create a fully configured approved campaign with audience segment and assets."""
        self.db.add_all(audience_members)
        self.db.commit()

        seg = Segment(
            name=f"{channel} Audience Segment",
            filter_rules={"combinator": "AND", "rules": [{"field": "consent_status", "operator": "equals", "value": True}]},
            created_by=self.manager_user.id,
        )
        self.db.add(seg)
        self.db.commit()

        campaign = Campaign(
            name=f"{channel} Public Notice Campaign",
            campaign_type="Public Awareness",
            status="Approved",
            channels=[channel],
            created_by=self.manager_user.id,
        )
        self.db.add(campaign)
        self.db.flush()
        campaign.segments = [seg]

        tpl = None
        if is_template:
            tpl = Template(
                title=title,
                category="Public Advisory",
                body=body,
                created_by=self.manager_user.id,
            )
            self.db.add(tpl)
            self.db.flush()
            campaign.template_id = tpl.id

        self.db.flush()

        root_asset = ContentAsset(
            title=title,
            body=body,
            category="Public Advisory",
            channel=channel,
            source_language="en",
            target_language=None,
            operation_type="template" if is_template else "generation",
            review_status="Approved",
            campaign_id=campaign.id,
            created_by=self.manager_user.id,
        )
        self.db.add(root_asset)
        self.db.flush()

        if variants:
            for v in variants:
                v.parent_id = root_asset.id
                v.campaign_id = campaign.id
                v.review_status = "Approved"
                v.channel = channel
                v.category = root_asset.category or "Public Advisory"
                v.created_by = self.manager_user.id
                self.db.add(v)
            self.db.flush()

        self.db.commit()
        # Phase 1A Security Requirement: Assess approved assets before readiness/distribution
        self._create_clean_assessment(root_asset)
        if variants:
            for v in variants:
                self._create_clean_assessment(v)
        return campaign, root_asset

    def _create_clean_assessment(self, asset: ContentAsset):
        from app.services.quality_service import compute_content_version_hash
        from app.models.content_quality import ContentQualityAssessment
        assessment = ContentQualityAssessment(
            content_asset_id=asset.id,
            content_version_hash=compute_content_version_hash(asset.title, asset.body, asset.call_to_action),
            overall_score=95.0,
            status="completed",
            dimension_scores={
                "language_grammar": 95.0,
                "readability": 95.0,
                "tone_consistency": 95.0,
                "translation_consistency": 95.0,
                "factual_consistency": 95.0,
                "channel_compliance": 95.0,
            },
            evaluator_type="deterministic",
            critical_issues_count=0,
            high_issues_count=0,
            medium_issues_count=0,
            low_issues_count=0,
            info_issues_count=0,
            created_by=self.manager_user.id,
        )
        self.db.add(assessment)
        self.db.commit()
        return assessment


class TestSMSChannelConstraintsReadiness(BaseDistributionConstraintsTest):
    """Scenarios 1-14: SMS GSM-7 / UCS-2 segmentation, boundaries, and audience aggregations."""

    def test_01_sms_gsm7_160_boundary_single_segment(self):
        """Scenario 1: English SMS message of exactly 160 GSM-7 characters evaluates to 1 segment in readiness."""
        text_160 = "A" * 160
        m = AudienceMember(name="Aarav", phone="+919876543210", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("SMS", "Notice", text_160, [m])

        res = check_campaign_readiness(self.db, campaign.id, "SMS")
        self.assertTrue(res.is_ready)
        self.assertEqual(res.total_estimated_segments, 1)
        self.assertEqual(res.max_segments_per_recipient, 1)
        self.assertEqual(res.language_breakdown["en"]["encoding"], "GSM-7")
        self.assertEqual(res.language_breakdown["en"]["segment_count"], 1)

    def test_02_sms_gsm7_161_boundary_two_segments(self):
        """Scenario 2: GSM-7 message of 161 characters evaluates to 2 concatenated segments (153 + 8)."""
        text_161 = "B" * 161
        m = AudienceMember(name="Aarav", phone="+919876543210", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("SMS", "Notice", text_161, [m])

        res = check_campaign_readiness(self.db, campaign.id, "SMS")
        self.assertTrue(res.is_ready)
        self.assertEqual(res.total_estimated_segments, 2)
        self.assertEqual(res.max_segments_per_recipient, 2)
        self.assertEqual(res.language_breakdown["en"]["segment_count"], 2)

    def test_03_sms_gsm7_306_and_307_segment_boundaries(self):
        """Scenario 3: GSM-7 306 chars is exactly 2 segments (153*2), while 307 chars steps into 3 segments."""
        detail_306 = calculate_sms_metrics("C" * 306)
        self.assertEqual(detail_306.segment_count, 2)
        self.assertEqual(detail_306.remaining_in_segment, 0)

        detail_307 = calculate_sms_metrics("C" * 307)
        self.assertEqual(detail_307.segment_count, 3)
        self.assertEqual(detail_307.remaining_in_segment, 152)

    def test_04_sms_gsm7_extension_characters_consume_two_septets(self):
        """Scenario 4: GSM-7 extension characters (e.g. € [ ] { } ~ | ^) consume 2 septets each."""
        # 158 basic chars + 1 extension char (€) = 160 septets -> 1 segment
        text_160_septets = "A" * 158 + "€"
        detail_160 = calculate_sms_metrics(text_160_septets)
        self.assertEqual(detail_160.encoding, SMSEncoding.GSM7.value)
        self.assertEqual(detail_160.encoded_units, 160)
        self.assertEqual(detail_160.segment_count, 1)

        # 159 basic chars + 1 extension char (€) = 161 septets -> 2 segments
        text_161_septets = "A" * 159 + "€"
        detail_161 = calculate_sms_metrics(text_161_septets)
        self.assertEqual(detail_161.encoded_units, 161)
        self.assertEqual(detail_161.segment_count, 2)

    def test_05_sms_gsm7_non_ascii_basic_characters(self):
        """Scenario 5: Valid GSM-7 non-ASCII characters (e.g. £, ¥, è, é, ñ) remain GSM-7 without forcing UCS-2."""
        text_gsm_non_ascii = "Hello £10 payment received. Gracias Señor! été"
        detail = calculate_sms_metrics(text_gsm_non_ascii)
        self.assertEqual(detail.encoding, SMSEncoding.GSM7.value)
        self.assertFalse(detail.has_surrogate_pairs)
        self.assertEqual(len(detail.non_gsm_characters), 0)

    def test_06_sms_ucs2_tamil_70_units_boundary_single_segment(self):
        """Scenario 6: Tamil text of <= 70 code units is 1 UCS-2 segment."""
        # 35 Tamil characters (each in BMP = 1 UTF-16 code unit = 35 code units)
        tamil_35 = "வணக்கம் இது தமிழ்நாடு அரசின் எச்சரி"
        detail = calculate_sms_metrics(tamil_35)
        self.assertEqual(detail.encoding, SMSEncoding.UCS2.value)
        self.assertEqual(detail.segment_count, 1)

        # 70 code units in UCS-2
        tamil_70 = "அ" * 70
        detail_70 = calculate_sms_metrics(tamil_70)
        self.assertEqual(detail_70.segment_count, 1)
        self.assertEqual(detail_70.remaining_in_segment, 0)

    def test_07_sms_ucs2_tamil_71_units_multipart_boundary(self):
        """Scenario 7: Tamil text of 71 code units steps into 2 UCS-2 concatenated segments (67 per segment)."""
        tamil_71 = "அ" * 71
        detail_71 = calculate_sms_metrics(tamil_71)
        self.assertEqual(detail_71.encoding, SMSEncoding.UCS2.value)
        self.assertEqual(detail_71.segment_count, 2)
        # 71 units with 67/segment: 67 in seg 1, 4 in seg 2, remaining = 67 - 4 = 63
        self.assertEqual(detail_71.remaining_in_segment, 63)

    def test_08_sms_ucs2_indic_languages_hindi_telugu_kannada(self):
        """Scenario 8: Hindi, Telugu, and Kannada content variants accurately identified as UCS-2 with 70/67 boundaries."""
        hindi_text = "नमस्ते, यह एक महत्वपूर्ण नागरिक सूचना है।"
        telugu_text = "నమస్కారం, ఇది ముఖ్యమైన ప్రభుత్వ సమాచారం."
        kannada_text = "ನಮಸ್ಕಾರ, ಇದು ಸರ್ಕಾರದ ಪ್ರಮುಖ ಮಾಹಿತಿ."

        for txt, lang in [(hindi_text, "hi"), (telugu_text, "te"), (kannada_text, "kn")]:
            detail = calculate_sms_metrics(txt)
            self.assertEqual(detail.encoding, SMSEncoding.UCS2.value, f"Failed for {lang}")
            self.assertGreater(detail.segment_count, 0)

    def test_09_sms_ucs2_emojis_surrogate_pairs(self):
        """Scenario 9: Emojis count as 2 UTF-16 code units and surface SMS_SURROGATE_PAIRS advisory."""
        emoji_text = "Alert ⚠️ High flood risk 🌧️"
        detail = calculate_sms_metrics(emoji_text)
        self.assertEqual(detail.encoding, SMSEncoding.UCS2.value)
        self.assertTrue(detail.has_surrogate_pairs)

        metrics = calculate_channel_metrics(channel="SMS", body=emoji_text)
        self.assertTrue(metrics.is_within_hard_limit)
        codes = [w.code for w in metrics.warnings]
        self.assertIn("SMS_SURROGATE_PAIRS", codes)

    def test_10_sms_ucs2_unpaired_surrogates_safe_handling(self):
        """Scenario 10: Lone surrogate code point handled gracefully without crashing, flagged as high warning."""
        lone_surrogate_text = "Warning: \ud83d text"
        metrics = calculate_channel_metrics(channel="SMS", body=lone_surrogate_text)
        self.assertTrue(metrics.is_within_hard_limit)
        codes = [w.code for w in metrics.warnings]
        self.assertIn("SMS_UNPAIRED_SURROGATES", codes)

    def test_11_mixed_language_audience_segment_aggregation(self):
        """Scenario 11: Mixed-language audience aggregates segment counts accurately across English, Tamil, and Hindi."""
        # English: 140 chars GSM-7 -> 1 segment
        eng_body = "Public Advisory: Please stay indoors due to heavy rainfall across the municipal region. Helpline is 1070."
        # Tamil: 140 chars UCS-2 -> 3 segments (ceil(140 / 67) = 3)
        tamil_variant = ContentAsset(
            title="எச்சரிக்கை",
            body="வெள்ள அபாய எச்சரிக்கை: " + ("அ" * 120),  # > 134 units -> 3 segments
            source_language="en",
            target_language="ta",
            operation_type="translation",
        )
        # Hindi: 60 chars UCS-2 -> 1 segment (ceil(60 / 70) = 1)
        hindi_variant = ContentAsset(
            title="चेतावनी",
            body="नमस्ते, बाढ़ की चेतावनी: सुरक्षित स्थान पर रहें। डायल करें 1070.",
            source_language="en",
            target_language="hi",
            operation_type="translation",
        )

        m_en = AudienceMember(name="John", phone="+919876543210", preferred_language="en", consent_status=True)
        m_ta = AudienceMember(name="Murugan", phone="+919876543211", preferred_language="ta", consent_status=True)
        m_hi = AudienceMember(name="Rohan", phone="+919876543212", preferred_language="hi", consent_status=True)

        campaign, _ = self._create_campaign_with_audience(
            "SMS",
            "Notice",
            eng_body,
            [m_en, m_ta, m_hi],
            variants=[tamil_variant, hindi_variant],
        )

        res = check_campaign_readiness(self.db, campaign.id, "SMS")
        self.assertTrue(res.is_ready)
        self.assertEqual(res.valid_recipients_count + res.warning_recipients_count, 3)
        self.assertIsNotNone(res.total_estimated_segments)
        self.assertEqual(res.max_segments_per_recipient, 3)  # Tamil is 3
        # Total segments: English (1) + Tamil (3) + Hindi (1) = 5
        self.assertEqual(res.total_estimated_segments, 5)

    def test_12_readiness_language_breakdown_structure(self):
        """Scenario 12: Readiness response returns structured language_breakdown for each audience language."""
        eng_body = "Advisory notice for citizens."
        m_en = AudienceMember(name="Alice", phone="+919876543210", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("SMS", "Notice", eng_body, [m_en])

        res = check_campaign_readiness(self.db, campaign.id, "SMS")
        self.assertIn("en", res.language_breakdown)
        en_info = res.language_breakdown["en"]
        self.assertEqual(en_info["language"], "en")
        self.assertEqual(en_info["recipient_count"], 1)
        self.assertEqual(en_info["fallback_count"], 0)
        self.assertEqual(en_info["encoding"], "GSM-7")
        self.assertEqual(en_info["segment_count"], 1)

    def test_13_max_segments_per_recipient_tracking(self):
        """Scenario 13: max_segments_per_recipient correctly identifies the maximum across all recipients."""
        short_en = "Short notice."
        # Variant with 4 segments in Telugu (> 201 units -> ceil(202/67) = 4 segments)
        long_telugu = ContentAsset(
            title="హెచ్చరిక",
            body="ముఖ్యమైన సమాచారం: " + ("ఆ" * 210),
            source_language="en",
            target_language="te",
            operation_type="translation",
        )
        m_en = AudienceMember(name="Alice", phone="+919876543210", preferred_language="en", consent_status=True)
        m_te = AudienceMember(name="Krishna", phone="+919876543211", preferred_language="te", consent_status=True)

        campaign, _ = self._create_campaign_with_audience(
            "SMS", "Notice", short_en, [m_en, m_te], variants=[long_telugu]
        )

        res = check_campaign_readiness(self.db, campaign.id, "SMS")
        self.assertEqual(res.max_segments_per_recipient, 4)

    def test_14_english_fallback_segment_accounting(self):
        """Scenario 14: Recipient with missing translation falls back to English and is recorded in fallback_count."""
        eng_body = "Flood warning in municipal district."
        # French recipient -> no French translation variant
        m_fr = AudienceMember(name="Jean", phone="+919876543210", preferred_language="fr", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("SMS", "Notice", eng_body, [m_fr])

        res = check_campaign_readiness(self.db, campaign.id, "SMS")
        self.assertTrue(res.is_ready)
        # Resolved under 'en' fallback
        self.assertIn("en", res.language_breakdown)
        self.assertEqual(res.language_breakdown["en"]["fallback_count"], 1)


class TestHardLimitEnforcementAndStaging(BaseDistributionConstraintsTest):
    """Scenarios 15-20: SMS hard limits, blocking job creation, and partial-audience staging failure handling."""

    def test_15_sms_hard_limit_exceeded_base_template_blocks_readiness(self):
        """Scenario 15: SMS body exceeding 1600 characters marks readiness is_ready=False with blocking reasons."""
        oversized_sms = "A" * 1605
        m = AudienceMember(name="Aarav", phone="+919876543210", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("SMS", "Notice", oversized_sms, [m])

        res = check_campaign_readiness(self.db, campaign.id, "SMS")
        self.assertFalse(res.is_ready)
        self.assertGreater(len(res.blocking_reasons), 0)
        self.assertTrue(any("hard limit" in r.lower() or "1600" in r for r in res.blocking_reasons))

    def test_16_sms_hard_limit_exceeded_blocks_job_creation_http_400(self):
        """Scenario 16: Job creation is strictly rejected with HTTP 400 when SMS content exceeds 1600 chars."""
        oversized_sms = "X" * 1650
        m = AudienceMember(name="Aarav", phone="+919876543210", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("SMS", "Notice", oversized_sms, [m])

        with self.assertRaises(HTTPException) as ctx:
            create_distribution_job(self.db, campaign.id, "SMS", self.manager_user)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("hard limit", ctx.exception.detail.lower())

    def test_17_sms_under_1600_over_3_segments_warning_allows_readiness(self):
        """Scenario 17: SMS with > 3 segments but under 1600 chars emits warning while allowing is_ready=True."""
        # 500 chars GSM-7: ceil(500/153) = 4 segments. Over recommended (3), but within technical limit (1600).
        four_seg_sms = "Warning: " + ("A" * 490)
        m = AudienceMember(name="Aarav", phone="+919876543210", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("SMS", "Notice", four_seg_sms, [m])

        res = check_campaign_readiness(self.db, campaign.id, "SMS")
        self.assertTrue(res.is_ready)
        self.assertGreater(len(res.warnings), 0)
        self.assertTrue(any("segment" in w.lower() for w in res.warnings))

        # Job creation must succeed
        job = create_distribution_job(self.db, campaign.id, "SMS", self.manager_user)
        self.assertEqual(job.status, JobStatus.QUEUED.value)
        self.assertEqual(job.queued_recipients, 1)

    def test_18_partial_audience_hard_limit_breach_stages_failed_record(self):
        """Scenario 18: Recipient whose personalization expands beyond 1600 chars is staged as FAILED locally."""
        # Template has 1590 chars with {name} placeholder
        # Base template without placeholder is 1584 chars <= 1600 chars
        base_body = ("Alert: " + ("A" * 1575)) + " {name}"
        self.assertLessEqual(len(base_body) - 6, 1600)  # without placeholder <= 1600

        # Normal recipient: "Bob" -> 1582 + 3 = 1585 chars <= 1600 chars
        m_normal = AudienceMember(name="Bob", phone="+919876543210", preferred_language="en", consent_status=True)
        # Oversized recipient: 40 chars name -> 1582 + 40 = 1622 chars > 1600 chars
        m_giant = AudienceMember(
            name="Supercalifragilisticexpialidocious_Citizen",
            phone="+919876543211",
            preferred_language="en",
            consent_status=True,
        )

        campaign, _ = self._create_campaign_with_audience(
            "SMS", "Notice", base_body, [m_normal, m_giant]
        )

        job = create_distribution_job(self.db, campaign.id, "SMS", self.manager_user)
        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()
        records_by_name = {r.audience_member.name: r for r in records}

        # Giant citizen record must be staged as FAILED
        giant_rec = records_by_name["Supercalifragilisticexpialidocious_Citizen"]
        self.assertEqual(giant_rec.delivery_status, DeliveryStatus.FAILED.value)
        self.assertEqual(giant_rec.error_code, "PAYLOAD_EXCEEDS_CHANNEL_HARD_LIMIT")
        self.assertIn("1600", giant_rec.error_message)

    def test_19_partial_audience_hard_limit_preserves_valid_pending_records(self):
        """Scenario 19: Valid recipient in same batch is staged as PENDING, ready for dispatch."""
        base_body = ("Alert: " + ("B" * 1575)) + " {name}"
        m_normal = AudienceMember(name="Bob", phone="+919876543210", preferred_language="en", consent_status=True)
        m_giant = AudienceMember(
            name="Supercalifragilisticexpialidocious_Citizen",
            phone="+919876543211",
            preferred_language="en",
            consent_status=True,
        )

        campaign, _ = self._create_campaign_with_audience(
            "SMS", "Notice", base_body, [m_normal, m_giant]
        )

        job = create_distribution_job(self.db, campaign.id, "SMS", self.manager_user)
        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()
        records_by_name = {r.audience_member.name: r for r in records}

        # Normal citizen record must be staged as PENDING
        normal_rec = records_by_name["Bob"]
        self.assertEqual(normal_rec.delivery_status, DeliveryStatus.PENDING.value)
        self.assertIsNone(normal_rec.error_code)

    def test_20_partial_audience_hard_limit_job_counters_consistent(self):
        """Scenario 20: DistributionJob counters accurately record queued vs failed counts on partial breach."""
        base_body = ("Alert: " + ("C" * 1575)) + " {name}"
        m_normal = AudienceMember(name="Bob", phone="+919876543210", preferred_language="en", consent_status=True)
        m_giant = AudienceMember(
            name="Supercalifragilisticexpialidocious_Citizen",
            phone="+919876543211",
            preferred_language="en",
            consent_status=True,
        )

        campaign, _ = self._create_campaign_with_audience(
            "SMS", "Notice", base_body, [m_normal, m_giant]
        )

        job = create_distribution_job(self.db, campaign.id, "SMS", self.manager_user)
        self.assertEqual(job.total_recipients, 2)
        self.assertEqual(job.eligible_recipients, 2)
        self.assertEqual(job.queued_recipients, 1)
        self.assertEqual(job.failed_recipients, 1)


class TestWorkerPreFlightGuard(BaseDistributionConstraintsTest):
    """Scenarios 21-23: Worker pre-flight dispatch guard protecting against oversized payloads."""

    def test_21_worker_preflight_blocks_oversized_payload_locally(self):
        """Scenario 21: Worker identifies oversized payload immediately prior to dispatch and marks record FAILED."""
        m = AudienceMember(name="Aarav", phone="+919876543210", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("SMS", "Notice", "Initial short", [m])

        # Stage job normally
        job = create_distribution_job(self.db, campaign.id, "SMS", self.manager_user)
        rec = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).first()

        # Simulate post-staging data corruption or external tampering making payload oversized
        rec.rendered_content = "X" * 1700
        self.db.commit()

        # Execute worker batch
        processed_count, has_more = asyncio.run(
            process_job_batch(self.db, job.job_id, batch_size=10, worker_id="worker-test-1")
        )

        self.db.refresh(rec)
        self.assertEqual(rec.delivery_status, DeliveryStatus.FAILED.value)
        self.assertEqual(rec.error_code, "PAYLOAD_EXCEEDS_CHANNEL_HARD_LIMIT")
        self.assertIsNone(rec.next_retry_at)

    def test_22_worker_preflight_does_not_invoke_provider(self):
        """Scenario 22: Worker pre-flight guard strictly avoids calling provider.send_message for oversized payloads."""
        m = AudienceMember(name="Aarav", phone="+919876543210", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("SMS", "Notice", "Short", [m])

        job = create_distribution_job(self.db, campaign.id, "SMS", self.manager_user)
        rec = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).first()
        rec.rendered_content = "Z" * 1800
        self.db.commit()

        provider = get_provider("SMS")
        with patch.object(provider, "send_message", new_callable=AsyncMock) as mock_send:
            asyncio.run(process_job_batch(self.db, job.job_id, batch_size=10, worker_id="worker-test-2"))
            mock_send.assert_not_called()

    def test_23_worker_preflight_records_diagnostic_attempt(self):
        """Scenario 23: Worker pre-flight failure records DeliveryAttempt with hard_limit_violation metadata."""
        m = AudienceMember(name="Aarav", phone="+919876543210", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("SMS", "Notice", "Short", [m])

        job = create_distribution_job(self.db, campaign.id, "SMS", self.manager_user)
        rec = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).first()
        rec.rendered_content = "Y" * 1650
        self.db.commit()

        asyncio.run(process_job_batch(self.db, job.job_id, batch_size=10, worker_id="worker-test-3"))

        attempts = self.db.query(DeliveryAttempt).filter(DeliveryAttempt.delivery_record_id == rec.id).all()
        self.assertEqual(len(attempts), 1)
        att = attempts[0]
        self.assertEqual(att.attempt_status, "failure")
        self.assertEqual(att.error_code, "PAYLOAD_EXCEEDS_CHANNEL_HARD_LIMIT")
        self.assertTrue(att.response_metadata.get("hard_limit_violation"))


class TestWhatsAppChannelConstraints(BaseDistributionConstraintsTest):
    """Scenarios 24-25: WhatsApp template vs freeform boundaries."""

    def test_24_whatsapp_template_over_1024_blocks_readiness(self):
        """Scenario 24: WhatsApp template message exceeding 1024 chars triggers CRITICAL warning and blocks readiness."""
        oversized_tpl = "W" * 1050
        m = AudienceMember(name="Aarav", phone="+919876543210", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience(
            "WhatsApp", "WhatsApp Advisory", oversized_tpl, [m], is_template=True
        )

        res = check_campaign_readiness(self.db, campaign.id, "WhatsApp")
        self.assertFalse(res.is_ready)
        self.assertTrue(any("1,024" in r or "template" in r.lower() for r in res.blocking_reasons))

    def test_25_whatsapp_freeform_over_4096_blocks_readiness(self):
        """Scenario 25: WhatsApp freeform message exceeding 4096 chars triggers CRITICAL warning and blocks readiness."""
        oversized_freeform = "F" * 4150
        m = AudienceMember(name="Aarav", phone="+919876543210", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience(
            "WhatsApp", "WhatsApp Advisory", oversized_freeform, [m], is_template=False
        )

        res = check_campaign_readiness(self.db, campaign.id, "WhatsApp")
        self.assertFalse(res.is_ready)
        self.assertTrue(any("4096" in r or "hard limit" in r.lower() for r in res.blocking_reasons))


class TestVoiceChannelConstraints(BaseDistributionConstraintsTest):
    """Scenarios 26-28: Voice duration estimation, Indic syllabic rates, and warning behaviors."""

    def test_26_voice_duration_calculation_indic_languages(self):
        """Scenario 26: Voice duration calculation uses language-specific WPM (Tamil 115, Hindi 125, English 150)."""
        text_50_words = "word " * 50

        # English (150 WPM = 2.5 wps): 50 words / 2.5 = 20s
        dur_en = calculate_voice_duration_seconds(text_50_words, "en")
        # Tamil (115 WPM = ~1.92 wps): 50 words / 1.92 = ~26s
        dur_ta = calculate_voice_duration_seconds(text_50_words, "ta")
        # Malayalam (110 WPM = ~1.83 wps): 50 words / 1.83 = ~27s
        dur_ml = calculate_voice_duration_seconds(text_50_words, "ml")

        self.assertGreater(dur_ta, dur_en)
        self.assertGreater(dur_ml, dur_ta)

    def test_27_voice_over_90_seconds_warning_allows_readiness(self):
        """Scenario 27: Voice script running > 90 seconds emits HIGH warning but allows is_ready=True."""
        # 300 words in English (~150 WPM = 120 seconds > 90 seconds)
        long_voice_script = ("This is a long citizen advisory sentence with important details. ") * 30
        m = AudienceMember(name="Aarav", phone="+919876543210", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("Voice", "Voice Alert", long_voice_script, [m])

        res = check_campaign_readiness(self.db, campaign.id, "Voice")
        self.assertTrue(res.is_ready, f"Voice > 90s must not block readiness! Blocking reasons: {res.blocking_reasons}")
        self.assertGreater(res.estimated_duration_seconds, 90)
        self.assertTrue(any("90 seconds" in w for w in res.warnings))

    def test_28_voice_contains_urls_or_markdown_emits_warnings(self):
        """Scenario 28: Voice script containing URL or markdown syntax emits advisory warnings."""
        script_with_url = "Please visit https://kerala.gov.in/relief for detailed shelters. Dial **1070**."
        metrics = calculate_channel_metrics(channel="Voice", body=script_with_url)
        codes = [w.code for w in metrics.warnings]
        self.assertIn("VOICE_CONTAINS_URL", codes)
        self.assertIn("VOICE_CONTAINS_MARKDOWN", codes)


class TestEmailAndWebChannelConstraints(BaseDistributionConstraintsTest):
    """Scenarios 29-32: Email subject limits, Web notification title/body boundaries."""

    def test_29_email_subject_over_255_blocks_readiness(self):
        """Scenario 29: Email subject exceeding 255 chars triggers CRITICAL warning and blocks readiness."""
        oversized_subject = "Important Public Advisory: " + ("S" * 240)  # > 255 chars
        body = "Email body text"
        m = AudienceMember(name="Aarav", email="aarav@agency.gov.in", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("Email", oversized_subject, body, [m])

        res = check_campaign_readiness(self.db, campaign.id, "Email")
        self.assertFalse(res.is_ready)
        self.assertTrue(any("subject" in r.lower() and "255" in r for r in res.blocking_reasons))

    def test_30_email_subject_over_78_warning_allows_readiness(self):
        """Scenario 30: Email subject between 79 and 255 chars emits advisory warning while allowing is_ready=True."""
        subject_90 = "Notice: " + ("E" * 82)  # 90 chars
        body = "Email body text"
        m = AudienceMember(name="Aarav", email="aarav@agency.gov.in", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("Email", subject_90, body, [m])

        res = check_campaign_readiness(self.db, campaign.id, "Email")
        self.assertTrue(res.is_ready)
        self.assertTrue(any("subject" in w.lower() for w in res.warnings))

    def test_31_web_title_over_255_blocks_readiness(self):
        """Scenario 31: Web notification title exceeding 255 chars triggers CRITICAL warning and blocks readiness."""
        oversized_title = "Web Alert: " + ("W" * 250)
        body = "Web notification message body."
        m = AudienceMember(name="Aarav", email="aarav@agency.gov.in", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("Web", oversized_title, body, [m])

        res = check_campaign_readiness(self.db, campaign.id, "Web")
        self.assertFalse(res.is_ready)
        self.assertTrue(any("title" in r.lower() and "255" in r for r in res.blocking_reasons))

    def test_32_web_body_over_4096_blocks_readiness(self):
        """Scenario 32: Web notification body exceeding 4096 chars triggers CRITICAL warning and blocks readiness."""
        oversized_body = "B" * 4200
        m = AudienceMember(name="Aarav", email="aarav@agency.gov.in", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("Web", "Valid Title", oversized_body, [m])

        res = check_campaign_readiness(self.db, campaign.id, "Web")
        self.assertFalse(res.is_ready)
        self.assertTrue(any("body" in r.lower() and "4096" in r for r in res.blocking_reasons))


class TestPermanentFailureIsolation(BaseDistributionConstraintsTest):
    """Scenario 33: Permanent channel constraint violations excluded from retry_failed_deliveries()."""

    def test_33_retry_failed_deliveries_ignores_payload_hard_limit_failures(self):
        """Scenario 33: Records failed with PAYLOAD_EXCEEDS_CHANNEL_HARD_LIMIT are non-retryable."""
        self.assertIn("PAYLOAD_EXCEEDS_CHANNEL_HARD_LIMIT", NON_RETRYABLE_ERROR_CODES)

        m = AudienceMember(name="Aarav", phone="+919876543210", preferred_language="en", consent_status=True)
        campaign, _ = self._create_campaign_with_audience("SMS", "Notice", "Short message", [m])

        job = create_distribution_job(self.db, campaign.id, "SMS", self.manager_user)
        rec = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).first()

        # Mark record as failed with permanent hard-limit error code
        rec.delivery_status = DeliveryStatus.FAILED.value
        rec.error_code = "PAYLOAD_EXCEEDS_CHANNEL_HARD_LIMIT"
        rec.error_message = "SMS message length (1650 chars) exceeds hard limit of 1600 characters."
        rec.attempt_count = 1
        rec.max_attempts = 3
        job.status = JobStatus.FAILED.value
        job.failed_recipients = 1
        job.queued_recipients = 0
        self.db.commit()

        # Attempt to retry: must reject with HTTP 400 because there are zero eligible retryable records
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(retry_failed_deliveries(self.db, job.job_id, self.manager_user))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("No eligible failed records available for retry", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
