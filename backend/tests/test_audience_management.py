"""Automated test suite for Task 4: Audience Database Management & Bulk Import."""

import io
import unittest
import openpyxl
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.seed import seed_default_roles
from app.models.user import User
from app.models.audience import AudienceMember
from app.core.security import get_password_hash, create_access_token


class TestAudienceManagement(unittest.TestCase):
    """Test suite for Audience CRUD, filtering, RBAC, and CSV/Excel bulk import."""

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

        # 1. Admin User
        self.admin_user = User(
            full_name="Admin Director",
            email="admin.director@agency.gov.in",
            hashed_password=get_password_hash("AdminPass123!"),
            role_id=self.admin_role.id,
            is_active=True,
        )
        self.db.add(self.admin_user)

        # 2. Campaign Manager User
        self.manager_user = User(
            full_name="Campaign Lead",
            email="campaign.lead@agency.gov.in",
            hashed_password=get_password_hash("ManagerPass123!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.db.add(self.manager_user)

        # 3. Communication Team User
        self.comm_user = User(
            full_name="Comm Specialist",
            email="comm.specialist@agency.gov.in",
            hashed_password=get_password_hash("CommPass123!"),
            role_id=self.comm_role.id,
            is_active=True,
        )
        self.db.add(self.comm_user)

        self.db.commit()
        self.db.refresh(self.admin_user)
        self.db.refresh(self.manager_user)
        self.db.refresh(self.comm_user)

        # Tokens
        self.admin_token = create_access_token(self.admin_user.id)
        self.manager_token = create_access_token(self.manager_user.id)
        self.comm_token = create_access_token(self.comm_user.id)

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.manager_headers = {"Authorization": f"Bearer {self.manager_token}"}
        self.comm_headers = {"Authorization": f"Bearer {self.comm_token}"}

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.test_engine)

    def test_manager_crud_lifecycle(self):
        """Campaign Manager can create, view, list, update, and delete audience members."""
        # 1. Create
        payload = {
            "name": "Dr. Anita Desai",
            "email": "anita.desai@hospital.org",
            "phone": "+91 98765 43210",
            "age": 42,
            "gender": "Female",
            "city": "Mumbai",
            "state": "Maharashtra",
            "preferred_language": "mr",
            "occupation": "Chief Medical Officer",
            "organization_department": "Public Health",
            "preferred_channel": "Email",
            "consent_status": True,
        }
        res_create = self.client.post("/audience", json=payload, headers=self.manager_headers)
        self.assertEqual(res_create.status_code, 201)
        data_create = res_create.json()
        member_id = data_create["id"]
        self.assertEqual(data_create["name"], "Dr. Anita Desai")
        self.assertEqual(data_create["phone"], "+919876543210")  # normalized
        self.assertEqual(data_create["preferred_language"], "mr")
        self.assertIs(data_create["consent_status"], True)

        # 1b. Create with default consent_status (omitted) -> must default to None (unknown)
        res_default_consent = self.client.post(
            "/audience",
            json={"name": "Consent Omitted", "email": "omitted@hospital.org"},
            headers=self.manager_headers,
        )
        self.assertEqual(res_default_consent.status_code, 201)
        self.assertIsNone(res_default_consent.json()["consent_status"])

        # 2. Retrieve
        res_get = self.client.get(f"/audience/{member_id}", headers=self.manager_headers)
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["email"], "anita.desai@hospital.org")

        # 3. Update (omitting consent_status must not alter existing True)
        update_payload = {
            "city": "Pune",
            "occupation": "Director of Healthcare",
        }
        res_update = self.client.put(f"/audience/{member_id}", json=update_payload, headers=self.manager_headers)
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(res_update.json()["city"], "Pune")
        self.assertEqual(res_update.json()["occupation"], "Director of Healthcare")
        self.assertIs(res_update.json()["consent_status"], True)  # Preserved unchanged!

        # 4. Delete
        res_delete = self.client.delete(f"/audience/{member_id}", headers=self.manager_headers)
        self.assertEqual(res_delete.status_code, 204)

        # 5. Verify Not Found
        res_get_after = self.client.get(f"/audience/{member_id}", headers=self.manager_headers)
        self.assertEqual(res_get_after.status_code, 404)

    def test_communication_team_read_only_access(self):
        """Communication Team can read audience but is prohibited (403) from mutations and import."""
        # Seed a record via Admin
        seed_member = AudienceMember(
            name="Ramesh Patel",
            email="ramesh.patel@gujarat.gov.in",
            phone="+919123456789",
            preferred_language="gu",
            preferred_channel="Email",
            consent_status=True,
        )
        self.db.add(seed_member)
        self.db.commit()
        self.db.refresh(seed_member)

        # Read allowed
        res_list = self.client.get("/audience", headers=self.comm_headers)
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(len(res_list.json()["items"]), 1)

        res_get = self.client.get(f"/audience/{seed_member.id}", headers=self.comm_headers)
        self.assertEqual(res_get.status_code, 200)

        # Create forbidden (403)
        res_create = self.client.post(
            "/audience",
            json={"name": "Forbidden Member", "email": "forbidden@test.com"},
            headers=self.comm_headers,
        )
        self.assertEqual(res_create.status_code, 403)

        # Update forbidden (403)
        res_update = self.client.put(
            f"/audience/{seed_member.id}",
            json={"city": "Ahmedabad"},
            headers=self.comm_headers,
        )
        self.assertEqual(res_update.status_code, 403)

        # Delete forbidden (403)
        res_del = self.client.delete(f"/audience/{seed_member.id}", headers=self.comm_headers)
        self.assertEqual(res_del.status_code, 403)

        # Bulk Import forbidden (403)
        res_imp = self.client.post(
            "/audience/import",
            files={"file": ("test.csv", b"name,email\nTest,test@test.com", "text/csv")},
            headers=self.comm_headers,
        )
        self.assertEqual(res_imp.status_code, 403)

    def test_unauthenticated_requests_denied(self):
        """Unauthenticated requests return 401 Unauthorized."""
        res = self.client.get("/audience")
        self.assertEqual(res.status_code, 401)

        res = self.client.post("/audience", json={"name": "Anon", "email": "anon@test.com"})
        self.assertEqual(res.status_code, 401)

    def test_duplicate_contact_rejection(self):
        """Reject duplicate email and phone registrations with HTTP 409 Conflict."""
        # Create initial record
        self.client.post(
            "/audience",
            json={"name": "Member A", "email": "unique@agency.gov.in", "phone": "+919999900001"},
            headers=self.admin_headers,
        )

        # Duplicate email
        res_dup_email = self.client.post(
            "/audience",
            json={"name": "Member B", "email": "unique@agency.gov.in"},
            headers=self.admin_headers,
        )
        self.assertEqual(res_dup_email.status_code, 409)
        self.assertIn("already registered", res_dup_email.json()["detail"])

        # Duplicate phone
        res_dup_phone = self.client.post(
            "/audience",
            json={"name": "Member C", "phone": "+91 99999-00001"},
            headers=self.admin_headers,
        )
        self.assertEqual(res_dup_phone.status_code, 409)
        self.assertIn("already registered", res_dup_phone.json()["detail"])

    def test_validation_rules_and_channel_constraints(self):
        """Enforce contact handle presence, channel constraints, and age boundaries."""
        # 1. Neither email nor phone provided
        res_no_contact = self.client.post(
            "/audience",
            json={"name": "No Contact Info"},
            headers=self.admin_headers,
        )
        self.assertEqual(res_no_contact.status_code, 422)

        # 2. Channel is Email but no email given
        res_email_mismatch = self.client.post(
            "/audience",
            json={"name": "User", "phone": "+919876543210", "preferred_channel": "Email"},
            headers=self.admin_headers,
        )
        self.assertEqual(res_email_mismatch.status_code, 422)

        # 3. Channel is SMS but no phone given
        res_sms_mismatch = self.client.post(
            "/audience",
            json={"name": "User", "email": "user@test.gov.in", "preferred_channel": "SMS"},
            headers=self.admin_headers,
        )
        self.assertEqual(res_sms_mismatch.status_code, 422)

        # 4. Invalid age bounds
        res_bad_age = self.client.post(
            "/audience",
            json={"name": "User", "email": "user@test.gov.in", "age": 150},
            headers=self.admin_headers,
        )
        self.assertEqual(res_bad_age.status_code, 422)

        # 5. Invalid phone number digit length (too short < 7 digits)
        res_short_phone = self.client.post(
            "/audience",
            json={"name": "Short Phone", "phone": "12345", "preferred_channel": "SMS"},
            headers=self.admin_headers,
        )
        self.assertEqual(res_short_phone.status_code, 422)

        # 6. Invalid phone number digit length (too long > 15 digits)
        res_long_phone = self.client.post(
            "/audience",
            json={"name": "Long Phone", "phone": "+91 1234567890123456", "preferred_channel": "SMS"},
            headers=self.admin_headers,
        )
        self.assertEqual(res_long_phone.status_code, 422)

    def test_search_filter_and_pagination(self):
        """Verify search across fields, targeted filters, and pagination math."""
        # Seed batch of 12 records with varied consent (True, False, None)
        languages = ["hi", "ta", "te", "en"]
        channels = ["Email", "SMS", "WhatsApp"]
        cities = ["Chennai", "Bengaluru", "Hyderabad", "Delhi"]

        for i in range(1, 13):
            # i % 3 == 0 -> None, i % 3 == 1 -> True, i % 3 == 2 -> False
            c_status = True if (i % 3 == 1) else (False if (i % 3 == 2) else None)
            member = AudienceMember(
                name=f"Citizen {i:02d}",
                email=f"citizen{i:02d}@public.gov.in",
                phone=f"+9198000000{i:02d}",
                age=20 + i,
                city=cities[i % len(cities)],
                state="State",
                preferred_language=languages[i % len(languages)],
                preferred_channel=channels[i % len(channels)],
                consent_status=c_status,
            )
            self.db.add(member)
        self.db.commit()

        # Page 1 (size 5)
        res_p1 = self.client.get("/audience?page=1&page_size=5", headers=self.admin_headers)
        self.assertEqual(res_p1.status_code, 200)
        data_p1 = res_p1.json()
        self.assertEqual(data_p1["total"], 12)
        self.assertEqual(len(data_p1["items"]), 5)
        self.assertEqual(data_p1["total_pages"], 3)

        # Search term
        res_search = self.client.get("/audience?search=Citizen 05", headers=self.admin_headers)
        self.assertEqual(res_search.status_code, 200)
        self.assertEqual(res_search.json()["total"], 1)
        self.assertEqual(res_search.json()["items"][0]["name"], "Citizen 05")

        # Filter by language
        res_filter_lang = self.client.get("/audience?preferred_language=ta", headers=self.admin_headers)
        self.assertEqual(res_filter_lang.status_code, 200)
        for item in res_filter_lang.json()["items"]:
            self.assertEqual(item["preferred_language"], "ta")

        # Filter by consent true
        res_filter_consent_true = self.client.get("/audience?consent_status=true", headers=self.admin_headers)
        self.assertEqual(res_filter_consent_true.status_code, 200)
        for item in res_filter_consent_true.json()["items"]:
            self.assertTrue(item["consent_status"])

        # Filter by consent false
        res_filter_consent_false = self.client.get("/audience?consent_status=false", headers=self.admin_headers)
        self.assertEqual(res_filter_consent_false.status_code, 200)
        for item in res_filter_consent_false.json()["items"]:
            self.assertFalse(item["consent_status"])

        # Filter by unconfirmed / null consent
        res_filter_consent_null = self.client.get("/audience?consent_status=unconfirmed", headers=self.admin_headers)
        self.assertEqual(res_filter_consent_null.status_code, 200)
        self.assertEqual(res_filter_consent_null.json()["total"], 4)
        for item in res_filter_consent_null.json()["items"]:
            self.assertIsNone(item["consent_status"])

    def test_audience_stats_aggregation(self):
        """Verify GET /audience/stats aggregates totals, consent, and distributions."""
        m1 = AudienceMember(name="M1", email="m1@a.com", preferred_language="hi", preferred_channel="Email", gender="Female", consent_status=True)
        m2 = AudienceMember(name="M2", email="m2@a.com", preferred_language="hi", preferred_channel="SMS", phone="+9190001", gender="Female", consent_status=False)
        m3 = AudienceMember(name="M3", email="m3@a.com", preferred_language="ta", preferred_channel="WhatsApp", phone="+9190002", gender="Male", consent_status=True)
        self.db.add_all([m1, m2, m3])
        self.db.commit()

        res_stats = self.client.get("/audience/stats", headers=self.admin_headers)
        self.assertEqual(res_stats.status_code, 200)
        stats = res_stats.json()
        self.assertEqual(stats["total_members"], 3)
        self.assertEqual(stats["active_consent_count"], 2)
        self.assertEqual(stats["language_distribution"]["hi"], 2)
        self.assertEqual(stats["language_distribution"]["ta"], 1)
        self.assertEqual(stats["channel_distribution"]["Email"], 1)

    def test_csv_bulk_import_with_mixed_valid_and_invalid_rows(self):
        """CSV bulk import validates rows independently, records duplicates and errors, and preserves null consent."""
        # Pre-seed one user in database to test DB collision
        self.db.add(AudienceMember(name="Existing Person", email="existing@test.com", preferred_channel="Email"))
        self.db.commit()

        csv_content = """name,email,phone,age,city,state,preferred_language,preferred_channel,consent
Suresh Kumar,suresh@test.com,+91 98765 11111,35,Bengaluru,Karnataka,kn,Email,yes
No Consent Person,noconsent@test.com,+91 98765 77777,32,Pune,Maharashtra,mr,Email,
Invalid Row No Contact,,,30,Delhi,Delhi,hi,Email,true
Bad Age Person,badage@test.com,+91 98765 22222,999,Chennai,Tamil Nadu,ta,Email,true
Existing Person,existing@test.com,+91 98765 33333,40,Mumbai,Maharashtra,en,Email,true
Duplicate Suresh,suresh@test.com,+91 98765 44444,36,Bengaluru,Karnataka,kn,Email,true
Meena Sharma,meena@test.com,+91 98765 55555,28,Jaipur,Rajasthan,hi,WhatsApp,no
Ambiguous Consent Person,ambiguous@test.com,+91 98765 88888,25,Kolkata,West Bengal,bn,Email,maybe
"""
        res_import = self.client.post(
            "/audience/import",
            files={"file": ("test_audience.csv", csv_content.encode("utf-8"), "text/csv")},
            headers=self.manager_headers,
        )
        self.assertEqual(res_import.status_code, 200)
        summary = res_import.json()

        self.assertEqual(summary["total_rows"], 8)
        self.assertEqual(summary["successful_imports"], 3)  # Suresh Kumar, No Consent Person, Meena Sharma
        self.assertEqual(summary["duplicate_count"], 2)     # Existing Person (in DB) & Duplicate Suresh (in file)
        self.assertEqual(summary["rejected_count"], 3)      # No contact, Bad age (999), Ambiguous consent ("maybe")
        self.assertEqual(summary["unspecified_consent_count"], 1)  # No Consent Person has null consent
        self.assertEqual(len(summary["errors"]), 5)

        # Confirm valid members exist in DB with expected tri-state consent values
        suresh_db = self.db.execute(select(AudienceMember).where(AudienceMember.email == "suresh@test.com")).scalar_one_or_none()
        self.assertIsNotNone(suresh_db)
        self.assertEqual(suresh_db.city, "Bengaluru")
        self.assertIs(suresh_db.consent_status, True)

        meena_db = self.db.execute(select(AudienceMember).where(AudienceMember.email == "meena@test.com")).scalar_one_or_none()
        self.assertIsNotNone(meena_db)
        self.assertEqual(meena_db.preferred_channel, "WhatsApp")
        self.assertIs(meena_db.consent_status, False)

        noconsent_db = self.db.execute(select(AudienceMember).where(AudienceMember.email == "noconsent@test.com")).scalar_one_or_none()
        self.assertIsNotNone(noconsent_db)
        self.assertEqual(noconsent_db.city, "Pune")
        self.assertIsNone(noconsent_db.consent_status)  # Critical DPDP check: missing consent is NOT coerced to True!

        # Ambiguous consent person must NOT be in DB
        ambiguous_db = self.db.execute(select(AudienceMember).where(AudienceMember.email == "ambiguous@test.com")).scalar_one_or_none()
        self.assertIsNone(ambiguous_db)

    def test_excel_bulk_import_success(self):
        """Excel (.xlsx) bulk import parses workbook, validates rows, and commits data."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Audience"

        # Headers
        ws.append(["Full Name", "Email Address", "Mobile Number", "Age", "City", "State", "Language", "Channel", "Consent"])
        # Rows
        ws.append(["Pooja Verma", "pooja.verma@delhi.gov.in", "+91 98111 22233", 31, "New Delhi", "Delhi", "hi", "Email", "True"])
        ws.append(["Karthik Raj", "karthik.raj@tn.gov.in", "+91 98444 55566", 29, "Madurai", "Tamil Nadu", "ta", "SMS", "True"])

        excel_stream = io.BytesIO()
        wb.save(excel_stream)
        excel_bytes = excel_stream.getvalue()

        res_excel = self.client.post(
            "/audience/import",
            files={"file": ("public_audience.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=self.manager_headers,
        )
        self.assertEqual(res_excel.status_code, 200)
        summary = res_excel.json()
        self.assertEqual(summary["total_rows"], 2)
        self.assertEqual(summary["successful_imports"], 2)
        self.assertEqual(summary["rejected_count"], 0)
        self.assertEqual(summary["duplicate_count"], 0)

        # Verify Karthik in DB
        karthik = self.db.execute(select(AudienceMember).where(AudienceMember.email == "karthik.raj@tn.gov.in")).scalar_one_or_none()
        self.assertIsNotNone(karthik)
        self.assertEqual(karthik.phone, "+919844455566")

    def test_import_unsupported_format_and_empty_file(self):
        """Bulk import rejects legacy .xls, unsupported formats, and 0-byte files with appropriate error codes."""
        # Legacy Excel format (.xls) explicitly rejected with guidance
        res_legacy_xls = self.client.post(
            "/audience/import",
            files={"file": ("legacy_contacts.xls", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "application/vnd.ms-excel")},
            headers=self.admin_headers,
        )
        self.assertEqual(res_legacy_xls.status_code, 400)
        self.assertIn("Legacy Excel format (.xls) is not supported", res_legacy_xls.json()["detail"])
        self.assertIn("xlsx", res_legacy_xls.json()["detail"])

        # Unsupported format (.pdf)
        res_bad_format = self.client.post(
            "/audience/import",
            files={"file": ("records.pdf", b"%PDF-1.4...", "application/pdf")},
            headers=self.admin_headers,
        )
        self.assertEqual(res_bad_format.status_code, 400)
        self.assertIn("Unsupported file format", res_bad_format.json()["detail"])

        # Empty file
        res_empty = self.client.post(
            "/audience/import",
            files={"file": ("empty.csv", b"", "text/csv")},
            headers=self.admin_headers,
        )
        self.assertEqual(res_empty.status_code, 400)
        self.assertIn("Uploaded file is empty", res_empty.json()["detail"])

        # Corrupted / invalid .xlsx file
        res_corrupt_xlsx = self.client.post(
            "/audience/import",
            files={"file": ("corrupt.xlsx", b"PK\x03\x04not-a-valid-zip-data", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=self.admin_headers,
        )
        self.assertEqual(res_corrupt_xlsx.status_code, 400)
        self.assertIn("Unable to parse Excel file", res_corrupt_xlsx.json()["detail"])

        # Oversized file (>10 MB)
        oversized_bytes = b"0" * (10 * 1024 * 1024 + 100)
        res_oversized = self.client.post(
            "/audience/import",
            files={"file": ("huge.csv", oversized_bytes, "text/csv")},
            headers=self.admin_headers,
        )
        self.assertEqual(res_oversized.status_code, 413)


if __name__ == "__main__":
    unittest.main()

