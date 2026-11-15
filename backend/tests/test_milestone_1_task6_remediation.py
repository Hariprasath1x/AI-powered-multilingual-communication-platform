"""Targeted test suite for Milestone 1 Task 6 Remediation:
- D-01: Campaign Cloning (POST /campaigns/{id}/clone)
- D-02: {area} Placeholder Support and Location Resolution
- D-03: Emergency Alert Automatic High Priority Enforcement
"""

import unittest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.seed import seed_default_roles
from app.models.user import User
from app.models.audience import AudienceMember
from app.models.segment import Segment
from app.models.template import Template
from app.models.campaign import Campaign
from app.models.communication import Message
from app.core.security import get_password_hash, create_access_token
from app.services.distribution.job_service import render_personalized_content


class TestTask6Remediation(unittest.TestCase):
    """Integration and unit tests verifying the three Task 6 defect remediations."""

    @classmethod
    def setUpClass(cls):
        cls.test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=cls.test_engine
        )

    def setUp(self):
        Base.metadata.create_all(bind=self.test_engine)
        self.db = self.TestingSessionLocal()
        roles = seed_default_roles(self.db)
        self.admin_role = roles["Admin"]
        self.manager_role = roles["Campaign Manager"]
        self.comm_role = roles["Communication Team"]

        # Admin user
        self.admin_user = User(
            full_name="Admin Chief",
            email="admin.chief@agency.gov.in",
            hashed_password=get_password_hash("AdminPass123!"),
            role_id=self.admin_role.id,
            is_active=True,
        )
        self.db.add(self.admin_user)

        # Campaign Manager 1
        self.manager_1 = User(
            full_name="Manager Priya",
            email="priya.manager@agency.gov.in",
            hashed_password=get_password_hash("ManagerPass123!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.db.add(self.manager_1)

        # Campaign Manager 2
        self.manager_2 = User(
            full_name="Manager Rohit",
            email="rohit.manager@agency.gov.in",
            hashed_password=get_password_hash("ManagerPass456!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.db.add(self.manager_2)

        # Communication Team member (restricted from create/clone)
        self.comm_user = User(
            full_name="Comm Operator",
            email="comm.operator@agency.gov.in",
            hashed_password=get_password_hash("CommPass123!"),
            role_id=self.comm_role.id,
            is_active=True,
        )
        self.db.add(self.comm_user)
        self.db.commit()

        # Audience Members with varying location data for {area} testing
        # 1. Full location data (city + state)
        self.aud_chennai = AudienceMember(
            name="Ananya Krishnan",
            email="ananya.krishnan@example.gov.in",
            phone="+919876543210",
            city="Chennai",
            state="Tamil Nadu",
            preferred_language="ta",
            consent_status=True,
        )
        # 2. City missing, state present
        self.aud_state_only = AudienceMember(
            name="Murugan Vel",
            email="murugan.vel@example.gov.in",
            phone="+919876543211",
            city=None,
            state="Tamil Nadu",
            preferred_language="ta",
            consent_status=True,
        )
        # 3. Both city and state missing
        self.aud_no_location = AudienceMember(
            name="Anonymous Citizen",
            email="citizen.anon@example.gov.in",
            phone="+919876543212",
            city=None,
            state=None,
            preferred_language="en",
            consent_status=True,
        )
        self.db.add_all([self.aud_chennai, self.aud_state_only, self.aud_no_location])

        # Target Segment
        self.segment = Segment(
            name="South Region Citizens",
            description="Citizens in Tamil Nadu",
            filter_rules={
                "combinator": "AND",
                "rules": [
                    {"field": "preferred_language", "operator": "equals", "value": "ta"}
                ],
            },
            created_by=self.manager_1.id,
        )
        self.db.add(self.segment)

        # Reusable Template with {area}
        self.template = Template(
            title="Monsoon Health Alert",
            category="Disaster Management",
            body="Hello {name}, heavy rain forecast for {area}. Residents of {city}, {state} stay alert.",
            language="en",
            tags="monsoon, advisory",
            created_by=self.manager_1.id,
        )
        self.db.add(self.template)
        self.db.commit()
        self.db.refresh(self.segment)
        self.db.refresh(self.template)

        # Tokens
        self.admin_token = create_access_token(self.admin_user.id)
        self.manager_1_token = create_access_token(self.manager_1.id)
        self.manager_2_token = create_access_token(self.manager_2.id)
        self.comm_token = create_access_token(self.comm_user.id)

        # Dependency override
        def override_get_db():
            db = self.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.test_engine)
        app.dependency_overrides.clear()

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    # =========================================================================
    # D-01: CAMPAIGN CLONING TESTS
    # =========================================================================

    def test_clone_campaign_success_and_preservation(self):
        """Verify successful campaign clone, ID generation, (Copy) suffix, Draft status, and configuration preservation."""
        # 1. Create a source campaign that is Approved
        source_campaign = Campaign(
            name="Dengue Prevention Initiative 2026",
            campaign_type="Awareness",
            objective="Eliminate stagnant water breeding grounds across sectors.",
            priority="Medium",
            status="Approved",
            channels=["Email", "SMS"],
            template_id=self.template.id,
            start_date=datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc),
            end_date=datetime(2026, 7, 31, 18, 0, tzinfo=timezone.utc),
            created_by=self.manager_1.id,
        )
        source_campaign.segments = [self.segment]
        self.db.add(source_campaign)
        self.db.commit()
        self.db.refresh(source_campaign)

        # Attach an operational message to source to verify it is NOT copied
        msg = Message(
            campaign_id=source_campaign.id,
            audience_member_id=self.aud_chennai.id,
            channel="Email",
            rendered_content="Test message content",
            status="Sent",
            sent_at=datetime.now(timezone.utc),
        )
        self.db.add(msg)
        self.db.commit()

        # 2. Clone the campaign as Manager 2
        resp = self.client.post(
            f"/campaigns/{source_campaign.id}/clone",
            headers=self._headers(self.manager_2_token),
        )
        self.assertEqual(resp.status_code, 201)
        cloned_data = resp.json()

        # Check new unique ID
        self.assertNotEqual(cloned_data["id"], source_campaign.id)
        # Check name with (Copy) suffix
        self.assertEqual(cloned_data["name"], "Dengue Prevention Initiative 2026 (Copy)")
        # Check Draft status (never inherits Approved)
        self.assertEqual(cloned_data["status"], "Draft")
        # Check configuration preservation
        self.assertEqual(cloned_data["campaign_type"], "Awareness")
        self.assertEqual(cloned_data["objective"], source_campaign.objective)
        self.assertEqual(cloned_data["priority"], "Medium")
        self.assertEqual(sorted(cloned_data["channels"]), ["Email", "SMS"])
        self.assertEqual(cloned_data["template_id"], self.template.id)
        # Check creator is the cloning user
        self.assertEqual(cloned_data["created_by"], self.manager_2.id)
        # Check segments preserved
        self.assertEqual(len(cloned_data["segments"]), 1)
        self.assertEqual(cloned_data["segments"][0]["id"], self.segment.id)

        # 3. Verify operational records were NOT copied to clone
        cloned_messages = (
            self.db.query(Message).filter(Message.campaign_id == cloned_data["id"]).all()
        )
        self.assertEqual(len(cloned_messages), 0)

        # 4. Verify source campaign remains completely unchanged
        self.db.refresh(source_campaign)
        self.assertEqual(source_campaign.status, "Approved")
        self.assertEqual(source_campaign.name, "Dengue Prevention Initiative 2026")
        self.assertEqual(len(source_campaign.messages), 1)

    def test_clone_campaign_subsequent_copies_generate_unique_names(self):
        """Verify cloning multiple times generates (Copy 2), (Copy 3) without collision errors."""
        source = Campaign(
            name="Cyclone Preparedness 2026",
            campaign_type="Awareness",
            priority="Medium",
            status="Draft",
            channels=["SMS"],
            created_by=self.manager_1.id,
        )
        self.db.add(source)
        self.db.commit()

        # First clone -> (Copy)
        r1 = self.client.post(f"/campaigns/{source.id}/clone", headers=self._headers(self.manager_1_token))
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r1.json()["name"], "Cyclone Preparedness 2026 (Copy)")

        # Second clone -> (Copy 2)
        r2 = self.client.post(f"/campaigns/{source.id}/clone", headers=self._headers(self.manager_1_token))
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(r2.json()["name"], "Cyclone Preparedness 2026 (Copy 2)")

    def test_clone_campaign_not_found(self):
        """Verify 404 response when cloning a nonexistent campaign."""
        resp = self.client.post("/campaigns/99999/clone", headers=self._headers(self.admin_token))
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())

    def test_clone_campaign_rbac(self):
        """Verify Admin and Campaign Manager can clone; Comm Team gets 403; Unauthenticated gets 401."""
        source = Campaign(
            name="RBAC Source Campaign",
            campaign_type="Educational",
            priority="Low",
            status="Draft",
            channels=["Email"],
            created_by=self.manager_1.id,
        )
        self.db.add(source)
        self.db.commit()

        # Unauthenticated -> 401
        r_unauth = self.client.post(f"/campaigns/{source.id}/clone")
        self.assertEqual(r_unauth.status_code, 401)

        # Comm Team -> 403
        r_comm = self.client.post(f"/campaigns/{source.id}/clone", headers=self._headers(self.comm_token))
        self.assertEqual(r_comm.status_code, 403)

        # Admin -> 201
        r_admin = self.client.post(f"/campaigns/{source.id}/clone", headers=self._headers(self.admin_token))
        self.assertEqual(r_admin.status_code, 201)

    # =========================================================================
    # D-02: {area} PLACEHOLDER SUPPORT TESTS
    # =========================================================================

    def test_template_validation_accepts_area_placeholder(self):
        """Verify {area} placeholder is valid in TemplateCreate and TemplateUpdate payloads."""
        # 1. Create template with {area}
        create_payload = {
            "title": "Flood Warning District Notice",
            "category": "Disaster Management",
            "body": "Urgent alert for {name} in {area}. Water logging reported across {city}.",
            "language": "en",
        }
        resp = self.client.post("/templates", json=create_payload, headers=self._headers(self.admin_token))
        self.assertEqual(resp.status_code, 201)
        tmpl_data = resp.json()
        self.assertIn("{area}", tmpl_data["placeholders"])
        self.assertIn("{name}", tmpl_data["placeholders"])
        self.assertIn("{city}", tmpl_data["placeholders"])

        # 2. Update template with {area} and {state}
        update_payload = {
            "body": "Updated: Stay indoors {name} ({area}, {state}).",
        }
        r_up = self.client.put(f"/templates/{tmpl_data['id']}", json=update_payload, headers=self._headers(self.admin_token))
        self.assertEqual(r_up.status_code, 200)
        self.assertIn("{area}", r_up.json()["placeholders"])
        self.assertIn("{state}", r_up.json()["placeholders"])

    def test_area_placeholder_resolution_with_city_and_state_fallback(self):
        """Verify {area} prefers city, falls back to state, and handles missing location safely."""
        template_text = "Citizen {name}, please report to relief center in {area} ({city}, {state})."

        # Case 1: City is populated -> {area} resolves to city
        rendered_1 = render_personalized_content(template_text, self.aud_chennai)
        self.assertIn("in Chennai", rendered_1)
        self.assertIn("(Chennai, Tamil Nadu)", rendered_1)

        # Case 2: City is None/empty, State is populated -> {area} falls back to state
        rendered_2 = render_personalized_content(template_text, self.aud_state_only)
        self.assertIn("in Tamil Nadu", rendered_2)
        # city becomes empty string, no internal error
        self.assertIn("(, Tamil Nadu)", rendered_2)

        # Case 3: Both City and State are None/empty -> {area} safely becomes empty string
        rendered_3 = render_personalized_content(template_text, self.aud_no_location)
        self.assertIn("in  (, )", rendered_3)
        self.assertNotIn("{area}", rendered_3)
        self.assertNotIn("Error", rendered_3)

    def test_campaign_preview_renders_area_placeholder(self):
        """Verify campaign multi-channel preview endpoint renders {area} placeholder with real recipient data."""
        campaign = Campaign(
            name="Coastal Weather Advisory",
            campaign_type="Emergency Alert",
            priority="High",
            status="Draft",
            channels=["SMS", "Email"],
            template_id=self.template.id,
            created_by=self.admin_user.id,
        )
        campaign.segments = [self.segment]
        self.db.add(campaign)
        self.db.commit()

        # Preview with Chennai recipient
        resp = self.client.get(
            f"/campaigns/{campaign.id}/preview?audience_member_id={self.aud_chennai.id}",
            headers=self._headers(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        preview = resp.json()
        rendered_content = preview["rendered_content"]
        # Template body: "Hello {name}, heavy rain forecast for {area}. Residents of {city}, {state} stay alert."
        self.assertIn("forecast for Chennai", rendered_content)
        self.assertIn("Residents of Chennai, Tamil Nadu", rendered_content)

        # Preview with state-only recipient (city missing)
        r_state = self.client.get(
            f"/campaigns/{campaign.id}/preview?audience_member_id={self.aud_state_only.id}",
            headers=self._headers(self.admin_token),
        )
        self.assertEqual(r_state.status_code, 200)
        p_state = r_state.json()
        # {area} should fall back to "Tamil Nadu"
        self.assertIn("forecast for Tamil Nadu", p_state["rendered_content"])

    # =========================================================================
    # D-03: EMERGENCY ALERT HIGH PRIORITY TESTS
    # =========================================================================

    def test_emergency_alert_creation_enforces_high_priority(self):
        """Verify Emergency Alert campaign creation automatically enforces High priority regardless of input."""
        # 1. No priority supplied -> automatically High
        p1 = {
            "name": "Tsunami Coastal Evacuation Notice",
            "campaign_type": "Emergency Alert",
            "channels": ["SMS", "Voice"],
        }
        r1 = self.client.post("/campaigns", json=p1, headers=self._headers(self.admin_token))
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r1.json()["priority"], "High")

        # 2. 'Low' priority supplied -> automatically elevated to High
        p2 = {
            "name": "Flash Flood Flash Warning",
            "campaign_type": "Emergency Alert",
            "priority": "Low",
            "channels": ["SMS"],
        }
        r2 = self.client.post("/campaigns", json=p2, headers=self._headers(self.admin_token))
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(r2.json()["priority"], "High")

        # 3. 'Medium' priority supplied -> automatically elevated to High
        p3 = {
            "name": "Earthquake Immediate Response Alert",
            "campaign_type": "Emergency Alert",
            "priority": "Medium",
            "channels": ["SMS", "Email"],
        }
        r3 = self.client.post("/campaigns", json=p3, headers=self._headers(self.admin_token))
        self.assertEqual(r3.status_code, 201)
        self.assertEqual(r3.json()["priority"], "High")

    def test_emergency_alert_update_enforces_high_priority(self):
        """Verify campaign update changing type to Emergency Alert elevates priority to High."""
        camp = Campaign(
            name="General Civic Update",
            campaign_type="Awareness",
            priority="Low",
            status="Draft",
            channels=["Email"],
            created_by=self.admin_user.id,
        )
        self.db.add(camp)
        self.db.commit()

        # Update type to Emergency Alert (with priority not specified)
        up_payload = {"campaign_type": "Emergency Alert"}
        resp = self.client.put(f"/campaigns/{camp.id}", json=up_payload, headers=self._headers(self.admin_token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["campaign_type"], "Emergency Alert")
        self.assertEqual(resp.json()["priority"], "High")

    def test_emergency_alert_cannot_lower_priority(self):
        """Verify attempt to lower priority of an Emergency Alert campaign is rejected with HTTP 400."""
        camp = Campaign(
            name="Active Severe Weather Emergency",
            campaign_type="Emergency Alert",
            priority="High",
            status="Draft",
            channels=["SMS"],
            created_by=self.admin_user.id,
        )
        self.db.add(camp)
        self.db.commit()

        # Attempt to lower priority to Low
        r_low = self.client.put(f"/campaigns/{camp.id}", json={"priority": "Low"}, headers=self._headers(self.admin_token))
        self.assertEqual(r_low.status_code, 400)
        self.assertIn("cannot be set to a lower priority", r_low.json()["detail"].lower())

        # Attempt to lower priority to Medium
        r_med = self.client.put(f"/campaigns/{camp.id}", json={"priority": "Medium"}, headers=self._headers(self.admin_token))
        self.assertEqual(r_med.status_code, 400)
        self.assertIn("cannot be set to a lower priority", r_med.json()["detail"].lower())

    def test_switching_away_from_emergency_alert_allows_lowering_priority(self):
        """Verify switching campaign type away from Emergency Alert allows normal priority selection."""
        camp = Campaign(
            name="De-escalated Incident Notice",
            campaign_type="Emergency Alert",
            priority="High",
            status="Draft",
            channels=["SMS"],
            created_by=self.admin_user.id,
        )
        self.db.add(camp)
        self.db.commit()

        # Change type to Awareness and set priority to Low
        up_payload = {"campaign_type": "Awareness", "priority": "Low"}
        resp = self.client.put(f"/campaigns/{camp.id}", json=up_payload, headers=self._headers(self.admin_token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["campaign_type"], "Awareness")
        self.assertEqual(resp.json()["priority"], "Low")

    def test_normal_campaigns_retain_priority_flexibility(self):
        """Verify non-emergency campaign types (Awareness, Educational, etc.) can use Low, Medium, or High."""
        for prio in ["Low", "Medium", "High"]:
            camp_payload = {
                "name": f"Educational Literacy Program {prio}",
                "campaign_type": "Educational",
                "priority": prio,
                "channels": ["Email"],
            }
            resp = self.client.post("/campaigns", json=camp_payload, headers=self._headers(self.admin_token))
            self.assertEqual(resp.status_code, 201)
            self.assertEqual(resp.json()["priority"], prio)


if __name__ == "__main__":
    unittest.main()

