"""Unit tests for Task 9 Checkpoint 1: Distribution Foundation, Mock Providers, Consent, and Deduplication."""

import unittest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.audience import AudienceMember
from app.models.campaign import Campaign
from app.models.segment import Segment
from app.models.template import Template
from app.models.user import User
from app.models.content_asset import ContentAsset
from app.models.distribution import DistributionJob, DeliveryRecord, DeliveryAttempt
from app.core.security import get_password_hash
from app.db.seed import seed_default_roles
from app.services.distribution.providers import (
    MockEmailProvider,
    MockSMSProvider,
    MockWhatsAppProvider,
    MockVoiceProvider,
    MockWebNotificationProvider,
    get_provider,
    DeliveryPayload,
)
from app.services.distribution.consent_validator import (
    validate_recipient_consent,
    revalidate_jit_consent,
)
from app.services.distribution.recipient_resolver import resolve_campaign_recipients
from app.services.distribution.job_service import (
    render_personalized_content,
    create_distribution_job,
    resolve_campaign_content_assets,
    resolve_recipient_content_variant,
    normalize_language_code,
)
from app.services.distribution.delivery_service import process_distribution_job


class TestDistributionFoundation(unittest.TestCase):
    """Unit test suite for provider adapters, consent safety, recipient resolution, and deduplication."""

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    def setUp(self):
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    # -------------------------------------------------------------------------
    # 1. Provider Adapter Tests for All 5 Channels
    # -------------------------------------------------------------------------

    def test_mock_email_provider_outcomes(self):
        """MockEmailProvider handles valid dispatch, format errors, and simulated failure modes."""
        provider = MockEmailProvider()
        self.assertEqual(provider.get_channel(), "Email")
        self.assertTrue(provider.validate_address("citizen@example.gov.in"))
        self.assertFalse(provider.validate_address("invalid-email-address"))

        # Valid delivery
        payload = DeliveryPayload(
            recipient_id=1,
            recipient_address="citizen@example.gov.in",
            recipient_name="John Doe",
            channel="Email",
            body="Important public advisory.",
        )
        res = asyncio.run(provider.send_message(payload))
        self.assertTrue(res.success)
        self.assertEqual(res.status, "delivered")
        self.assertTrue(res.provider_reference.startswith("mock-msg-"))

        # Format error
        bad_payload = DeliveryPayload(
            recipient_id=1,
            recipient_address="no-at-sign.com",
            recipient_name="Bad Email",
            channel="Email",
            body="Advisory",
        )
        res_bad = asyncio.run(provider.send_message(bad_payload))
        self.assertFalse(res_bad.success)
        self.assertEqual(res_bad.error_code, "INVALID_EMAIL_FORMAT")
        self.assertFalse(res_bad.is_retryable)

        # Permanent failure (non-retryable)
        perm_payload = DeliveryPayload(
            recipient_id=2,
            recipient_address="fail_perm@example.com",
            recipient_name="Invalid Recipient",
            channel="Email",
            body="Advisory",
        )
        res_perm = asyncio.run(provider.send_message(perm_payload))
        self.assertFalse(res_perm.success)
        self.assertEqual(res_perm.error_code, "RECIPIENT_MAILBOX_NOT_FOUND")
        self.assertFalse(res_perm.is_retryable)

        # Temporary failure (retryable)
        temp_payload = DeliveryPayload(
            recipient_id=3,
            recipient_address="fail_temp@example.com",
            recipient_name="Busy Recipient",
            channel="Email",
            body="Advisory",
        )
        res_temp = asyncio.run(provider.send_message(temp_payload))
        self.assertFalse(res_temp.success)
        self.assertEqual(res_temp.error_code, "SMTP_421_SERVICE_BUSY")
        self.assertTrue(res_temp.is_retryable)

    def test_mock_sms_provider_outcomes(self):
        """MockSMSProvider validates E.164 phone numbers and handles retryable carrier throttling."""
        provider = MockSMSProvider()
        self.assertEqual(provider.get_channel(), "SMS")
        self.assertTrue(provider.validate_address("+919876543210"))
        self.assertFalse(provider.validate_address("12345"))  # Too short

        payload = DeliveryPayload(
            recipient_id=1,
            recipient_address="+919876543210",
            recipient_name="Aarav Sharma",
            channel="SMS",
            body="SMS alert test body.",
        )
        res = asyncio.run(provider.send_message(payload))
        self.assertTrue(res.success)
        self.assertEqual(res.status, "delivered")

        # Retryable carrier throttle
        temp_payload = DeliveryPayload(
            recipient_id=2,
            recipient_address="+9198765fail_temp",
            recipient_name="Throttled Recipient",
            channel="SMS",
            body="Advisory",
        )
        res_temp = asyncio.run(provider.send_message(temp_payload))
        self.assertFalse(res_temp.success)
        self.assertEqual(res_temp.error_code, "CARRIER_RATE_LIMIT_EXCEEDED")
        self.assertTrue(res_temp.is_retryable)

    def test_mock_whatsapp_provider_outcomes(self):
        """MockWhatsAppProvider validates phone numbers and returns wamid references."""
        provider = MockWhatsAppProvider()
        self.assertEqual(provider.get_channel(), "WhatsApp")

        payload = DeliveryPayload(
            recipient_id=1,
            recipient_address="+919876543210",
            recipient_name="Priya Patel",
            channel="WhatsApp",
            body="WhatsApp public awareness broadcast.",
        )
        res = asyncio.run(provider.send_message(payload))
        self.assertTrue(res.success)
        self.assertTrue(res.provider_reference.startswith("mock-wamid-"))

        # Permanent failure
        perm_payload = DeliveryPayload(
            recipient_id=2,
            recipient_address="+9198765fail_perm",
            recipient_name="No WhatsApp",
            channel="WhatsApp",
            body="Advisory",
        )
        res_perm = asyncio.run(provider.send_message(perm_payload))
        self.assertFalse(res_perm.success)
        self.assertEqual(res_perm.error_code, "USER_NOT_REGISTERED_ON_WHATSAPP")
        self.assertFalse(res_perm.is_retryable)

    def test_mock_voice_provider_outcomes(self):
        """MockVoiceProvider calculates simulated audio duration and handles busy lines."""
        provider = MockVoiceProvider()
        self.assertEqual(provider.get_channel(), "Voice")

        payload = DeliveryPayload(
            recipient_id=1,
            recipient_address="+919876543210",
            recipient_name="Ramesh Kumar",
            channel="Voice",
            body="This is a public service voice advisory from the municipal health department.",
        )
        res = asyncio.run(provider.send_message(payload))
        self.assertTrue(res.success)
        self.assertGreaterEqual(res.response_metadata.get("call_duration_seconds", 0), 5)

        # Busy line (retryable)
        temp_payload = DeliveryPayload(
            recipient_id=2,
            recipient_address="+9198765fail_temp",
            recipient_name="Busy Caller",
            channel="Voice",
            body="Advisory",
        )
        res_temp = asyncio.run(provider.send_message(temp_payload))
        self.assertFalse(res_temp.success)
        self.assertEqual(res_temp.error_code, "TELEPHONY_LINE_BUSY")
        self.assertTrue(res_temp.is_retryable)

    def test_mock_web_notification_provider_outcomes(self):
        """MockWebNotificationProvider handles push tokens and timeout simulation."""
        provider = MockWebNotificationProvider()
        self.assertEqual(provider.get_channel(), "Web")

        payload = DeliveryPayload(
            recipient_id=1,
            recipient_address="device_token_xyz_123",
            recipient_name="Web Citizen",
            channel="Web",
            body="Web portal civic notice.",
        )
        res = asyncio.run(provider.send_message(payload))
        self.assertTrue(res.success)
        self.assertTrue(res.provider_reference.startswith("mock-push-"))

    def test_get_provider_fails_closed_on_invalid_channel(self):
        """get_provider raises ValueError for unknown channels without falling back to external calls."""
        with self.assertRaises(ValueError):
            get_provider("CarrierPigeon")

    # -------------------------------------------------------------------------
    # 2. Consent Validation & JIT Re-Verification Tests
    # -------------------------------------------------------------------------

    def test_tri_state_consent_validation(self):
        """Only consent_status == True is accepted. Null or False are strictly rejected."""
        # Member 1: Explicit True -> Eligible
        m_true = AudienceMember(
            name="Alice",
            email="alice@example.gov.in",
            phone="+919876543210",
            consent_status=True,
        )
        valid_true, reason = validate_recipient_consent(m_true, "Email")
        self.assertTrue(valid_true)
        self.assertIsNone(reason)

        # Member 2: Explicit False (opt-out) -> Ineligible
        m_false = AudienceMember(
            name="Bob",
            email="bob@example.gov.in",
            phone="+919876543211",
            consent_status=False,
        )
        valid_false, reason = validate_recipient_consent(m_false, "Email")
        self.assertFalse(valid_false)
        self.assertIn("opted out", reason)

        # Member 3: Null / Unconfirmed -> Ineligible (Never assume true)
        m_null = AudienceMember(
            name="Charlie",
            email="charlie@example.gov.in",
            phone="+919876543212",
            consent_status=None,
        )
        valid_null, reason = validate_recipient_consent(m_null, "Email")
        self.assertFalse(valid_null)
        self.assertIn("unconfirmed", reason)

    def test_channel_specific_contact_requirement(self):
        """Consented member missing required channel credentials is marked ineligible."""
        # Member has email but NO phone
        m_email_only = AudienceMember(
            name="Diana",
            email="diana@example.gov.in",
            phone=None,
            consent_status=True,
        )
        # Email delivery is valid
        valid_email, _ = validate_recipient_consent(m_email_only, "Email")
        self.assertTrue(valid_email)

        # SMS delivery fails because phone is missing
        valid_sms, reason_sms = validate_recipient_consent(m_email_only, "SMS")
        self.assertFalse(valid_sms)
        self.assertIn("Missing phone number", reason_sms)

    def test_jit_consent_revalidation(self):
        """revalidate_jit_consent directly detects revocation in the database."""
        m = AudienceMember(
            name="Eve",
            email="eve@example.gov.in",
            phone="+919876543219",
            consent_status=True,
        )
        self.db.add(m)
        self.db.commit()
        self.db.refresh(m)

        # Initially consented
        self.assertTrue(revalidate_jit_consent(self.db, m.id))

        # Member withdraws consent
        m.consent_status = False
        self.db.commit()

        # JIT check immediately detects revocation
        self.assertFalse(revalidate_jit_consent(self.db, m.id))

    # -------------------------------------------------------------------------
    # 3. Audience Resolution & Deduplication
    # -------------------------------------------------------------------------

    def test_audience_resolution_deduplication_across_overlapping_segments(self):
        """A recipient qualifying for multiple attached segments is resolved exactly once."""
        # Create audience members
        m1 = AudienceMember(name="Member 1", email="m1@gov.in", phone="+919111111111", city="Chennai", consent_status=True)
        m2 = AudienceMember(name="Member 2", email="m2@gov.in", phone="+919222222222", city="Coimbatore", consent_status=True)
        m3 = AudienceMember(name="Member 3", email="m3@gov.in", phone="+919333333333", city="Chennai", consent_status=False)
        self.db.add_all([m1, m2, m3])
        self.db.commit()

        # Segment 1: city == "Chennai" (matches m1, m3)
        seg1 = Segment(
            name="Chennai Citizens",
            filter_rules={
                "combinator": "AND",
                "rules": [{"field": "city", "operator": "equals", "value": "Chennai"}],
            },
            created_by=1,
        )
        # Segment 2: consent_status is true (matches m1, m2)
        seg2 = Segment(
            name="Opted In",
            filter_rules={
                "combinator": "AND",
                "rules": [{"field": "consent_status", "operator": "equals", "value": True}],
            },
            created_by=1,
        )
        self.db.add_all([seg1, seg2])
        self.db.commit()

        # Campaign with both segments attached
        campaign = Campaign(
            name="Southern Awareness",
            campaign_type="Awareness",
            status="Approved",
            channels=["Email"],
            created_by=1,
        )
        campaign.segments = [seg1, seg2]
        self.db.add(campaign)
        self.db.commit()

        eligible, ineligible = resolve_campaign_recipients(self.db, campaign, "Email")

        # m1 matches BOTH seg1 and seg2, but must only appear ONCE in eligible list!
        eligible_ids = [r.audience_member_id for r in eligible]
        self.assertEqual(len(eligible_ids), 2)
        self.assertIn(m1.id, eligible_ids)
        self.assertIn(m2.id, eligible_ids)

        # m3 matches seg1, but has consent_status=False -> in ineligible list
        ineligible_ids = [r.audience_member_id for r in ineligible]
        self.assertIn(m3.id, ineligible_ids)

    # -------------------------------------------------------------------------
    # 4. Personalized Template Rendering
    # -------------------------------------------------------------------------

    def test_render_personalized_content(self):
        """Placeholders like {name} and {city} are properly interpolated."""
        member = AudienceMember(
            name="Siddharth",
            email="sid@gov.in",
            city="Madurai",
            state="Tamil Nadu",
        )
        template_text = "Dear {name}, please be advised that civic operations in {city}, {state} are active."
        rendered = render_personalized_content(template_text, member)
        self.assertEqual(
            rendered,
            "Dear Siddharth, please be advised that civic operations in Madurai, Tamil Nadu are active.",
        )


class TestMultilingualDistributionResolution(unittest.TestCase):
    """
    Milestone 2 Task 9 Phase 1 Integration Tests:
    Multilingual Translation Variant Resolution & Staging.
    Verifies Indic language resolution (hi, ta, te, kn, mr, bn, gu, ml, pa, ur, en),
    approval state enforcement, channel constraints, placeholder interpolation,
    fallback behavior, deduplication, and attempt metadata auditing.
    """

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    def setUp(self):
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()

        roles = seed_default_roles(self.db)
        self.admin_user = User(
            full_name="Disaster Director",
            email="director@relief.gov.in",
            hashed_password=get_password_hash("Secret123!"),
            role_id=roles["Admin"].id,
            is_active=True,
        )
        self.db.add(self.admin_user)
        self.db.commit()

        # Create Root English Content Asset for Email channel
        self.root_email_asset = ContentAsset(
            title="Flood Advisory",
            body="Hello {name}, alert for {city}: please stay indoors and follow safety guidelines.",
            summary="Emergency flood alert",
            call_to_action="Call 1070 for emergency helpline",
            category="Disaster Preparedness",
            tone="urgent",
            channel="Email",
            source_language="en",
            target_language=None,
            operation_type="generation",
            review_status="Approved",
            created_by=self.admin_user.id,
        )
        self.db.add(self.root_email_asset)
        self.db.commit()

        # Create campaign and attach root asset
        self.campaign = Campaign(
            name="Monsoon Disaster Advisory",
            campaign_type="Emergency Alert",
            status="Approved",
            channels=["Email"],
            created_by=self.admin_user.id,
        )
        self.root_email_asset.campaign_id = self.campaign.id
        self.campaign.content_assets = [self.root_email_asset]
        self.db.add(self.campaign)
        self.db.commit()

        # Tamil Approved Child Variant
        self.tamil_variant = ContentAsset(
            title="வெள்ள எச்சரிக்கை",
            body="வணக்கம் {name}, {city}-ல் வெள்ள எச்சரிக்கை: தயவுசெய்து வீட்டிலேயே இருங்கள்.",
            category="Disaster Preparedness",
            tone="urgent",
            channel="Email",
            source_language="en",
            target_language="ta",
            operation_type="translation",
            parent_id=self.root_email_asset.id,
            campaign_id=self.campaign.id,
            review_status="Approved",
            created_by=self.admin_user.id,
        )

        # Hindi Approved Child Variant
        self.hindi_variant = ContentAsset(
            title="बाढ़ चेतावनी",
            body="नमस्ते {name}, {city} में बाढ़ की चेतावनी: कृपया घर के अंदर रहें और सुरक्षित रहें।",
            category="Disaster Preparedness",
            tone="urgent",
            channel="Email",
            source_language="en",
            target_language="hi",
            operation_type="translation",
            parent_id=self.root_email_asset.id,
            campaign_id=self.campaign.id,
            review_status="Approved",
            created_by=self.admin_user.id,
        )

        # Telugu Approved Child Variant
        self.telugu_variant = ContentAsset(
            title="వరద హెచ్చరిక",
            body="నమస్కారం {name}, {city}లో వరద హెచ్చరిక: దయచేసి ఇళ్లలోనే ఉండండి మరియు సురక్షితంగా ఉండండి.",
            category="Disaster Preparedness",
            tone="urgent",
            channel="Email",
            source_language="en",
            target_language="te",
            operation_type="translation",
            parent_id=self.root_email_asset.id,
            campaign_id=self.campaign.id,
            review_status="Approved",
            created_by=self.admin_user.id,
        )

        # Kannada Approved Child Variant
        self.kannada_variant = ContentAsset(
            title="ಪ್ರವಾಹ ಎಚ್ಚರಿಕೆ",
            body="ನಮಸ್ಕಾರ {name}, {city}ನಲ್ಲಿ ಪ್ರವಾಹ ಎಚ್ಚರಿಕೆ: ದಯವಿಟ್ಟು ಮನೆಯಲ್ಲೇ ಇರಿ ಮತ್ತು ಸುರಕ್ಷಿತವಾಗಿರಿ.",
            category="Disaster Preparedness",
            tone="urgent",
            channel="Email",
            source_language="en",
            target_language="kn",
            operation_type="translation",
            parent_id=self.root_email_asset.id,
            campaign_id=self.campaign.id,
            review_status="Approved",
            created_by=self.admin_user.id,
        )

        self.db.add_all([self.tamil_variant, self.hindi_variant, self.telugu_variant, self.kannada_variant])
        self.db.commit()

        # Phase 1A Security Requirement: Create valid assessments for approved assets
        for a in [self.root_email_asset, self.tamil_variant, self.hindi_variant, self.telugu_variant, self.kannada_variant]:
            self._create_clean_assessment(a)

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
            created_by=self.admin_user.id,
        )
        self.db.add(assessment)
        self.db.commit()
        return assessment

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def _create_audience_and_segment(self, members: list) -> Segment:
        self.db.add_all(members)
        self.db.commit()
        member_ids = [m.id for m in members]

        seg = Segment(
            name="Target Segment",
            filter_rules={
                "combinator": "AND",
                "rules": [{"field": "id", "operator": "in", "value": member_ids}],
            },
            created_by=self.admin_user.id,
        )
        self.db.add(seg)
        self.db.commit()
        self.campaign.segments = [seg]
        self.db.commit()
        return seg

    # -------------------------------------------------------------------------
    # 14 Comprehensive Phase 1 Test Cases
    # -------------------------------------------------------------------------

    def test_1_english_recipient_receives_root_english_content(self):
        """Test 1: English recipient receives root English content personalized with placeholders."""
        m = AudienceMember(
            name="Arun Kumar",
            email="arun@gov.in",
            preferred_language="en",
            city="Delhi",
            consent_status=True,
        )
        self._create_audience_and_segment([m])

        job = create_distribution_job(self.db, self.campaign.id, "Email", self.admin_user)
        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()

        self.assertEqual(len(records), 1)
        self.assertEqual(
            records[0].rendered_content,
            "Hello Arun Kumar, alert for Delhi: please stay indoors and follow safety guidelines.",
        )

    def test_2_tamil_recipient_receives_approved_tamil_translation(self):
        """Test 2: Tamil recipient receives approved Tamil translation."""
        m = AudienceMember(
            name="Priya Sundaram",
            email="priya@gov.in",
            preferred_language="ta",
            city="Chennai",
            consent_status=True,
        )
        self._create_audience_and_segment([m])

        job = create_distribution_job(self.db, self.campaign.id, "Email", self.admin_user)
        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()

        self.assertEqual(len(records), 1)
        self.assertEqual(
            records[0].rendered_content,
            "வணக்கம் Priya Sundaram, Chennai-ல் வெள்ள எச்சரிக்கை: தயவுசெய்து வீட்டிலேயே இருங்கள்.",
        )

    def test_3_hindi_recipient_receives_approved_hindi_translation(self):
        """Test 3: Hindi recipient receives approved Hindi translation."""
        m = AudienceMember(
            name="Rahul Sharma",
            email="rahul@gov.in",
            preferred_language="hi",
            city="Varanasi",
            consent_status=True,
        )
        self._create_audience_and_segment([m])

        job = create_distribution_job(self.db, self.campaign.id, "Email", self.admin_user)
        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()

        self.assertEqual(len(records), 1)
        self.assertEqual(
            records[0].rendered_content,
            "नमस्ते Rahul Sharma, Varanasi में बाढ़ की चेतावनी: कृपया घर के अंदर रहें और सुरक्षित रहें।",
        )

    def test_4_telugu_recipient_receives_approved_telugu_translation(self):
        """Test 4: Telugu recipient receives approved Telugu translation."""
        m = AudienceMember(
            name="Suresh Reddy",
            email="suresh@gov.in",
            preferred_language="te",
            city="Hyderabad",
            consent_status=True,
        )
        self._create_audience_and_segment([m])

        job = create_distribution_job(self.db, self.campaign.id, "Email", self.admin_user)
        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()

        self.assertEqual(len(records), 1)
        self.assertEqual(
            records[0].rendered_content,
            "నమస్కారం Suresh Reddy, Hyderabadలో వరద హెచ్చరిక: దయచేసి ఇళ్లలోనే ఉండండి మరియు సురక్షితంగా ఉండండి.",
        )

    def test_5_kannada_recipient_receives_approved_kannada_translation(self):
        """Test 5: Kannada recipient receives approved Kannada translation."""
        m = AudienceMember(
            name="Divya Gowda",
            email="divya@gov.in",
            preferred_language="kn",
            city="Bengaluru",
            consent_status=True,
        )
        self._create_audience_and_segment([m])

        job = create_distribution_job(self.db, self.campaign.id, "Email", self.admin_user)
        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()

        self.assertEqual(len(records), 1)
        self.assertEqual(
            records[0].rendered_content,
            "ನಮಸ್ಕಾರ Divya Gowda, Bengaluruನಲ್ಲಿ ಪ್ರವಾಹ ಎಚ್ಚರಿಕೆ: ದಯವಿಟ್ಟು ಮನೆಯಲ್ಲೇ ಇರಿ ಮತ್ತು ಸುರಕ್ಷಿತವಾಗಿರಿ.",
        )

    def test_6_remaining_supported_languages_resolve_correctly(self):
        """Test 6: Remaining supported Indic languages (mr, bn, gu, ml, pa, ur) resolve correctly."""
        lang_data = [
            ("mr", "Sachin", "Mumbai", "नमस्कार {name}, {city} मध्ये पूर सूचना."),
            ("bn", "Subhash", "Kolkata", "নমস্কার {name}, {city}-তে বন্যার সতর্কতা."),
            ("gu", "Amit", "Ahmedabad", "નમસ્તે {name}, {city}માં પૂર ચેતવણી."),
            ("ml", "Anu", "Kochi", "നമസ്കാരം {name}, {city}-ൽ പ്രളയ മുന്നറിയിപ്പ്."),
            ("pa", "Harpreet", "Amritsar", "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ {name}, {city} ਵਿੱਚ ਹੜ੍ਹ ਦੀ ਚੇਤਾਵਨੀ."),
            ("ur", "Faizan", "Lucknow", "آداب {name}، {city} میں سیلاب کی وارننگ۔"),
        ]

        members = []
        for code, name, city, template in lang_data:
            variant = ContentAsset(
                title=f"Alert {code}",
                body=template,
                category="Disaster Preparedness",
                channel="Email",
                source_language="en",
                target_language=code,
                operation_type="translation",
                parent_id=self.root_email_asset.id,
                campaign_id=self.campaign.id,
                review_status="Approved",
                created_by=self.admin_user.id,
            )
            self.db.add(variant)
            self.db.commit()
            self._create_clean_assessment(variant)
            members.append(
                AudienceMember(
                    name=name,
                    email=f"{name.lower()}@gov.in",
                    preferred_language=code,
                    city=city,
                    consent_status=True,
                )
            )
        self.db.commit()
        self._create_audience_and_segment(members)

        job = create_distribution_job(self.db, self.campaign.id, "Email", self.admin_user)
        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()
        self.assertEqual(len(records), 6)

        records_by_address = {r.recipient_address: r for r in records}
        for code, name, city, template in lang_data:
            rec = records_by_address[f"{name.lower()}@gov.in"]
            expected = template.replace("{name}", name).replace("{city}", city)
            self.assertEqual(rec.rendered_content, expected)

    def test_7_missing_translation_falls_back_to_english(self):
        """Test 7: Missing translation gracefully falls back to root English content."""
        m = AudienceMember(
            name="Marie Dupont",
            email="marie@gov.in",
            preferred_language="fr",  # French is not in approved translations
            city="Puducherry",
            consent_status=True,
        )
        self._create_audience_and_segment([m])

        job = create_distribution_job(self.db, self.campaign.id, "Email", self.admin_user)
        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()

        self.assertEqual(len(records), 1)
        self.assertEqual(
            records[0].rendered_content,
            "Hello Marie Dupont, alert for Puducherry: please stay indoors and follow safety guidelines.",
        )

    def test_8_pending_translation_is_never_selected(self):
        """Test 8: Unapproved/Pending translations (Draft, Needs Review) are strictly excluded and fall back to English."""
        # Create unapproved Malayalam variant with review_status="Needs Review"
        unapproved_malayalam = ContentAsset(
            title="പ്രളയ മുന്നറിയിപ്പ്",
            body="നമസ്കാരം {name}, {city}-ൽ അടിയന്തര മുന്നറിയിപ്പ്.",
            category="Disaster Preparedness",
            channel="Email",
            source_language="en",
            target_language="ml",
            operation_type="translation",
            parent_id=self.root_email_asset.id,
            campaign_id=self.campaign.id,
            review_status="Needs Review",  # NOT APPROVED!
            created_by=self.admin_user.id,
        )
        self.db.add(unapproved_malayalam)
        self.db.commit()

        m = AudienceMember(
            name="Rahul Nair",
            email="rahul.nair@gov.in",
            preferred_language="ml",
            city="Thiruvananthapuram",
            consent_status=True,
        )
        self._create_audience_and_segment([m])

        job = create_distribution_job(self.db, self.campaign.id, "Email", self.admin_user)
        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()

        self.assertEqual(len(records), 1)
        # Must NOT receive the unapproved Malayalam variant; falls back to root English
        self.assertEqual(
            records[0].rendered_content,
            "Hello Rahul Nair, alert for Thiruvananthapuram: please stay indoors and follow safety guidelines.",
        )

    def test_9_rejected_translation_is_never_selected(self):
        """Test 9: Rejected translations are strictly excluded and fall back to English."""
        # Create rejected Punjabi variant
        rejected_punjabi = ContentAsset(
            title="ਹੜ੍ਹ ਦੀ ਚੇਤਾਵਨੀ",
            body="ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ {name}, {city} ਵਿੱਚ ਚੇਤਾਵਨੀ.",
            category="Disaster Preparedness",
            channel="Email",
            source_language="en",
            target_language="pa",
            operation_type="translation",
            parent_id=self.root_email_asset.id,
            campaign_id=self.campaign.id,
            review_status="Rejected",  # REJECTED!
            created_by=self.admin_user.id,
        )
        self.db.add(rejected_punjabi)
        self.db.commit()

        m = AudienceMember(
            name="Simran Kaur",
            email="simran@gov.in",
            preferred_language="pa",
            city="Ludhiana",
            consent_status=True,
        )
        self._create_audience_and_segment([m])

        job = create_distribution_job(self.db, self.campaign.id, "Email", self.admin_user)
        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()

        self.assertEqual(len(records), 1)
        # Must NOT receive the rejected Punjabi variant; falls back to root English
        self.assertEqual(
            records[0].rendered_content,
            "Hello Simran Kaur, alert for Ludhiana: please stay indoors and follow safety guidelines.",
        )

    def test_10_translation_for_different_channel_is_never_selected(self):
        """Test 10: Translation variant for a different channel is never selected during distribution."""
        # Create SMS root asset and an approved Tamil variant for SMS only
        sms_root = ContentAsset(
            title="SMS Advisory",
            body="SMS Alert for {name} in {city}.",
            category="Disaster Preparedness",
            channel="SMS",
            source_language="en",
            review_status="Approved",
            created_by=self.admin_user.id,
            campaign_id=self.campaign.id,
        )
        sms_tamil = ContentAsset(
            title="SMS Tamil",
            body="SMS தமிழ் எச்சரிக்கை {name}, {city}.",
            category="Disaster Preparedness",
            channel="SMS",
            source_language="en",
            target_language="ta",
            operation_type="translation",
            review_status="Approved",
            created_by=self.admin_user.id,
            campaign_id=self.campaign.id,
        )
        self.db.add_all([sms_root, sms_tamil])
        self.campaign.channels = ["Email", "SMS"]
        self.db.commit()
        self._create_clean_assessment(sms_root)
        self._create_clean_assessment(sms_tamil)

        # Recipient has preferred_language='ta'
        m = AudienceMember(
            name="Karthik",
            email="karthik@gov.in",
            phone="+919888877777",
            preferred_language="ta",
            city="Madurai",
            consent_status=True,
        )
        self._create_audience_and_segment([m])

        # Dispatch an SMS job
        job_sms = create_distribution_job(self.db, self.campaign.id, "SMS", self.admin_user)
        records_sms = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job_sms.id).all()
        self.assertEqual(len(records_sms), 1)
        # SMS recipient receives SMS Tamil variant, NOT Email Tamil variant!
        self.assertEqual(records_sms[0].rendered_content, "SMS தமிழ் எச்சரிக்கை Karthik, Madurai.")

        # If we remove the SMS Tamil variant, SMS job falls back to SMS English root, NOT Email Tamil!
        self.db.delete(sms_tamil)
        self.db.commit()

        # Update job status so a new SMS job can be created
        job_sms.status = "completed"
        self.db.commit()

        job_sms_fallback = create_distribution_job(self.db, self.campaign.id, "SMS", self.admin_user)
        records_fallback = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job_sms_fallback.id).all()
        self.assertEqual(len(records_fallback), 1)
        self.assertEqual(records_fallback[0].rendered_content, "SMS Alert for Karthik in Madurai.")

    def test_11_personalization_placeholders_preserved_and_rendered_in_translations(self):
        """Test 11: Dynamic placeholders ({name}, {city}, {state}, {area}) are correctly rendered in translated copy."""
        self.tamil_variant.body = "வணக்கம் {name} அவர்களே, {city}, {state} பகுதியில் {area} எச்சரிக்கை விடுக்கப்பட்டுள்ளது."
        self.db.commit()
        self._create_clean_assessment(self.tamil_variant)

        m = AudienceMember(
            name="Kavitha",
            email="kavitha@gov.in",
            preferred_language="ta",
            city="Coimbatore",
            state="Tamil Nadu",
            consent_status=True,
        )
        self._create_audience_and_segment([m])

        job = create_distribution_job(self.db, self.campaign.id, "Email", self.admin_user)
        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()

        self.assertEqual(len(records), 1)
        self.assertEqual(
            records[0].rendered_content,
            "வணக்கம் Kavitha அவர்களே, Coimbatore, Tamil Nadu பகுதியில் Coimbatore எச்சரிக்கை விடுக்கப்பட்டுள்ளது.",
        )

    def test_12_mixed_language_recipients_receive_respective_individual_variants(self):
        """Test 12: In a single broadcast with multiple language speakers, each citizen receives their exact language copy."""
        m_en = AudienceMember(name="Arun", email="arun@gov.in", preferred_language="en", city="Delhi", consent_status=True)
        m_ta = AudienceMember(name="Priya", email="priya@gov.in", preferred_language="ta", city="Chennai", consent_status=True)
        m_hi = AudienceMember(name="Rahul", email="rahul@gov.in", preferred_language="hi", city="Lucknow", consent_status=True)

        self._create_audience_and_segment([m_en, m_ta, m_hi])

        job = create_distribution_job(self.db, self.campaign.id, "Email", self.admin_user)
        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()
        self.assertEqual(len(records), 3)

        records_by_address = {r.recipient_address: r for r in records}
        self.assertEqual(
            records_by_address["arun@gov.in"].rendered_content,
            "Hello Arun, alert for Delhi: please stay indoors and follow safety guidelines.",
        )
        self.assertEqual(
            records_by_address["priya@gov.in"].rendered_content,
            "வணக்கம் Priya, Chennai-ல் வெள்ள எச்சரிக்கை: தயவுசெய்து வீட்டிலேயே இருங்கள்.",
        )
        self.assertEqual(
            records_by_address["rahul@gov.in"].rendered_content,
            "नमस्ते Rahul, Lucknow में बाढ़ की चेतावनी: कृपया घर के अंदर रहें और सुरक्षित रहें।",
        )

    def test_13_recipient_deduplication_and_idempotency_remain_intact(self):
        """Test 13: Recipient deduplication across segments and idempotency constraints remain strictly enforced."""
        m = AudienceMember(name="Priya", email="priya@gov.in", preferred_language="ta", city="Chennai", consent_status=True)
        self.db.add(m)
        self.db.commit()

        # Two overlapping segments both matching Priya
        seg1 = Segment(
            name="Tamil Segment",
            filter_rules={"combinator": "AND", "rules": [{"field": "city", "operator": "equals", "value": "Chennai"}]},
            created_by=self.admin_user.id,
        )
        seg2 = Segment(
            name="Consent Segment",
            filter_rules={"combinator": "AND", "rules": [{"field": "consent_status", "operator": "equals", "value": True}]},
            created_by=self.admin_user.id,
        )
        self.db.add_all([seg1, seg2])
        self.campaign.segments = [seg1, seg2]
        self.db.commit()

        job = create_distribution_job(self.db, self.campaign.id, "Email", self.admin_user)
        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()

        # Priya matched both segments, but staged exactly ONCE
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].idempotency_key, f"{job.id}:{m.id}:Email")

    def test_14_fallback_metadata_correctly_identifies_deliveries_and_attempts(self):
        """Test 14: Fallback metadata correctly audits English fallback vs translated delivery in attempts and payload."""
        m_tamil = AudienceMember(
            name="Priya",
            email="priya@gov.in",
            preferred_language="ta",
            city="Chennai",
            consent_status=True,
        )
        m_fallback = AudienceMember(
            name="Pierre",
            email="pierre@gov.in",
            preferred_language="fr",  # French -> must fall back to English
            city="Puducherry",
            consent_status=True,
        )
        self._create_audience_and_segment([m_tamil, m_fallback])

        job = create_distribution_job(self.db, self.campaign.id, "Email", self.admin_user)

        # Process job deliveries
        asyncio.run(process_distribution_job(self.db, job.job_id))

        # Inspect DeliveryAttempts
        attempts = self.db.query(DeliveryAttempt).join(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()
        self.assertEqual(len(attempts), 2)

        attempts_by_addr = {a.delivery_record.recipient_address: a for a in attempts}

        # Tamil recipient attempt verification
        attempt_ta = attempts_by_addr["priya@gov.in"]
        self.assertEqual(attempt_ta.attempt_status, "success")
        self.assertIsNotNone(attempt_ta.response_metadata)
        self.assertEqual(attempt_ta.response_metadata.get("preferred_language"), "ta")
        self.assertEqual(attempt_ta.response_metadata.get("resolved_language"), "ta")
        self.assertFalse(attempt_ta.response_metadata.get("fallback_to_root"))
        self.assertEqual(attempt_ta.response_metadata.get("content_asset_id"), self.tamil_variant.id)

        # Fallback recipient attempt verification
        attempt_fr = attempts_by_addr["pierre@gov.in"]
        self.assertEqual(attempt_fr.attempt_status, "success")
        self.assertIsNotNone(attempt_fr.response_metadata)
        self.assertEqual(attempt_fr.response_metadata.get("preferred_language"), "fr")
        self.assertEqual(attempt_fr.response_metadata.get("resolved_language"), "en")
        self.assertTrue(attempt_fr.response_metadata.get("fallback_to_root"))
        self.assertEqual(attempt_fr.response_metadata.get("content_asset_id"), self.root_email_asset.id)


if __name__ == "__main__":
    unittest.main()

