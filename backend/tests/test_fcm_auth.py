"""Automated Unit and Integration Tests for Firebase Cloud Messaging (FCM) HTTP v1 Authentication.

Verifies:
1. Service-account dictionary credential parsing and Google OAuth2 access token generation.
2. Service-account JSON string parsing and credential generation.
3. Individual credential fields (project_id, client_email, private_key) support.
4. FCM OAuth2 scope enforcement (https://www.googleapis.com/auth/firebase.messaging).
5. Token caching in memory and reuse across subsequent dispatches.
6. Token automatic refresh when expired or within 60s safety buffer.
7. Authorization: Bearer <access_token> header injection in FCM HTTP v1 POST requests.
8. Missing project_id handling (MISSING_FCM_PROJECT_ID).
9. Missing credentials handling (INVALID_FCM_CREDENTIALS).
10. Malformed service_account_json handling (INVALID_FCM_CREDENTIALS).
11. Google Auth OAuth2 exception handling (FCM_AUTH_ERROR).
12. FCM HTTP v1 error response mapping (UNREGISTERED -> DEVICE_TOKEN_INVALID).
13. FCM HTTP v1 error response mapping (INVALID_ARGUMENT -> DEVICE_TOKEN_INVALID).
14. FCM HTTP v1 error response mapping (HTTP 401 / UNAUTHENTICATED -> FCM_AUTH_ERROR).
15. FCM HTTP v1 error response mapping (HTTP 429 / QUOTA_EXCEEDED -> RATE_LIMIT_EXCEEDED).
16. FCM HTTP v1 error response mapping (HTTP 503 / UNAVAILABLE -> GATEWAY_TIMEOUT).
17. Bearer token and private key sanitization in error messages.
18. Backward compatibility with static server_key / access_token override.
19. Deterministic Mock mode preservation (success, fail_perm, fail_temp).
20. Admin channel configuration credentials masking and preservation during update.
21. Automatic device token deactivation integration when DEVICE_TOKEN_INVALID is emitted.
"""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import datetime
import json
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.user import User, Role
from app.models.device_token import DeviceToken
from app.models.channel_config import ChannelConfiguration
from app.core.security import get_password_hash, create_access_token
from app.services.channels.push_channel import PushChannel, FCM_OAUTH_SCOPE


class TestFCMAuthentication(unittest.TestCase):
    """Test suite for FCM HTTP v1 Service-Account Authentication and Token Lifecycle."""

    def setUp(self):
        PushChannel.clear_token_cache()
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        # Seed roles
        for r_id, r_name in [(1, "Admin"), (2, "Campaign Manager"), (3, "Communication Team")]:
            self.db.add(Role(id=r_id, name=r_name, description=r_name))
        self.db.commit()

        # Seed admin user
        self.admin = User(
            id=1,
            email="admin@test.gov.in",
            hashed_password=get_password_hash("AdminPass123!"),
            full_name="FCM Admin",
            role_id=1,
            is_active=True,
            organization="Central Ministry",
        )
        self.db.add(self.admin)
        self.db.commit()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.admin_token = create_access_token(self.admin.id)

        self.sample_sa_info = {
            "type": "service_account",
            "project_id": "test-gov-push-project",
            "private_key_id": "pk_12345678",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCfake\n-----END PRIVATE KEY-----\n",
            "client_email": "firebase-adminsdk@test-gov-push-project.iam.gserviceaccount.com",
            "token_uri": "https://oauth2.googleapis.com/token",
        }

    def tearDown(self):
        PushChannel.clear_token_cache()
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_fcm_service_account_info_token_generation_and_scope(self):
        """Verifies OAuth2 access token generation using service_account_info with required FCM scope."""
        channel = PushChannel(
            provider_type="fcm",
            sender_address="test-gov-push-project",
            credentials={"service_account_info": self.sample_sa_info},
        )

        mock_google_creds = MagicMock()
        mock_google_creds.token = "oauth2_bearer_token_xyz_123"
        mock_google_creds.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

        with patch("google.oauth2.service_account.Credentials.from_service_account_info", return_value=mock_google_creds) as mock_from_info:
            token, err_code, err_msg = channel._get_fcm_access_token(channel.credentials, "test-gov-push-project")
            self.assertEqual(token, "oauth2_bearer_token_xyz_123")
            self.assertIsNone(err_code)
            self.assertIsNone(err_msg)

            # Confirm scope passed to Google Credentials
            mock_from_info.assert_called_once()
            call_args = mock_from_info.call_args
            self.assertEqual(call_args[0][0], self.sample_sa_info)
            self.assertEqual(call_args[1]["scopes"], [FCM_OAUTH_SCOPE])

    def test_fcm_service_account_json_token_generation(self):
        """Verifies JSON string parsing and token generation."""
        json_str = json.dumps(self.sample_sa_info)
        channel = PushChannel(
            provider_type="fcm",
            sender_address="test-gov-push-project",
            credentials={"service_account_json": json_str},
        )

        mock_google_creds = MagicMock()
        mock_google_creds.token = "oauth2_bearer_from_json_string"
        mock_google_creds.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

        with patch("google.oauth2.service_account.Credentials.from_service_account_info", return_value=mock_google_creds) as mock_from_info:
            token, err_code, err_msg = channel._get_fcm_access_token(channel.credentials, "test-gov-push-project")
            self.assertEqual(token, "oauth2_bearer_from_json_string")
            self.assertIsNone(err_code)
            mock_from_info.assert_called_once()
            self.assertEqual(mock_from_info.call_args[0][0]["client_email"], self.sample_sa_info["client_email"])

    def test_fcm_individual_fields_token_generation(self):
        """Verifies individual fields (project_id, client_email, private_key) generate credentials."""
        channel = PushChannel(
            provider_type="fcm",
            credentials={
                "project_id": "test-gov-push-project",
                "client_email": self.sample_sa_info["client_email"],
                "private_key": self.sample_sa_info["private_key"],
            },
        )

        mock_google_creds = MagicMock()
        mock_google_creds.token = "oauth2_bearer_from_individual_fields"
        mock_google_creds.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

        with patch("google.oauth2.service_account.Credentials.from_service_account_info", return_value=mock_google_creds) as mock_from_info:
            token, err_code, err_msg = channel._get_fcm_access_token(channel.credentials, "test-gov-push-project")
            self.assertEqual(token, "oauth2_bearer_from_individual_fields")
            self.assertIsNone(err_code)
            mock_from_info.assert_called_once()
            passed_sa = mock_from_info.call_args[0][0]
            self.assertEqual(passed_sa["client_email"], self.sample_sa_info["client_email"])
            self.assertEqual(passed_sa["private_key"], self.sample_sa_info["private_key"])

    def test_fcm_token_caching_and_reuse(self):
        """Verifies token caching: second dispatch does NOT re-refresh credentials."""
        channel = PushChannel(
            provider_type="fcm",
            sender_address="test-gov-push-project",
            credentials={"service_account_info": self.sample_sa_info},
        )

        mock_google_creds = MagicMock()
        mock_google_creds.token = "cached_token_abc"
        mock_google_creds.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=45)

        with patch("google.oauth2.service_account.Credentials.from_service_account_info", return_value=mock_google_creds) as mock_from_info:
            token1, _, _ = channel._get_fcm_access_token(channel.credentials, "test-gov-push-project")
            token2, _, _ = channel._get_fcm_access_token(channel.credentials, "test-gov-push-project")

            self.assertEqual(token1, "cached_token_abc")
            self.assertEqual(token2, "cached_token_abc")
            # Should only have been called ONCE due to in-memory caching
            self.assertEqual(mock_from_info.call_count, 1)

    def test_fcm_token_refresh_when_expired(self):
        """Verifies expired token is automatically refreshed."""
        channel = PushChannel(
            provider_type="fcm",
            sender_address="test-gov-push-project",
            credentials={"service_account_info": self.sample_sa_info},
        )

        cache_key = f"{self.sample_sa_info['client_email']}:test-gov-push-project"
        # Seed cache with an expired token
        past_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=10)
        PushChannel._token_cache[cache_key] = ("expired_token_000", past_time)

        mock_google_creds = MagicMock()
        mock_google_creds.token = "fresh_refreshed_token_111"
        mock_google_creds.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

        with patch("google.oauth2.service_account.Credentials.from_service_account_info", return_value=mock_google_creds) as mock_from_info:
            token, _, _ = channel._get_fcm_access_token(channel.credentials, "test-gov-push-project")
            self.assertEqual(token, "fresh_refreshed_token_111")
            self.assertEqual(mock_from_info.call_count, 1)

    def test_fcm_missing_project_id(self):
        """Verifies error code MISSING_FCM_PROJECT_ID when project_id is missing."""
        channel = PushChannel(
            provider_type="fcm",
            sender_address="",
            credentials={},
        )

        class Msg:
            tracking_id = "trk_1"
            title = "Test"
            rendered_content = "Body"

        class Recipient:
            token = "device_token_abc"

        res = asyncio.run(channel.send(Msg(), Recipient()))
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "MISSING_FCM_PROJECT_ID")

    def test_fcm_missing_credentials(self):
        """Verifies error code INVALID_FCM_CREDENTIALS when credentials are not configured."""
        channel = PushChannel(
            provider_type="fcm",
            sender_address="test-proj",
            credentials={"project_id": "test-proj"},
        )

        class Msg:
            tracking_id = "trk_2"
            title = "Test"
            rendered_content = "Body"

        class Recipient:
            token = "device_token_abc"

        res = asyncio.run(channel.send(Msg(), Recipient()))
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "INVALID_FCM_CREDENTIALS")
        self.assertIn("Missing FCM service-account credentials", res.error_message)

    def test_fcm_malformed_service_account_json(self):
        """Verifies malformed JSON string handling."""
        channel = PushChannel(
            provider_type="fcm",
            sender_address="test-proj",
            credentials={"project_id": "test-proj", "service_account_json": "{not-valid-json:"},
        )

        class Msg:
            tracking_id = "trk_3"
            title = "Test"
            rendered_content = "Body"

        class Recipient:
            token = "device_token_abc"

        res = asyncio.run(channel.send(Msg(), Recipient()))
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "INVALID_FCM_CREDENTIALS")
        self.assertIn("Malformed service_account_json", res.error_message)

    def test_fcm_google_auth_oauth2_exception(self):
        """Verifies FCM_AUTH_ERROR when Google OAuth2 token refresh raises an exception."""
        channel = PushChannel(
            provider_type="fcm",
            sender_address="test-gov-push-project",
            credentials={"service_account_info": self.sample_sa_info},
        )

        class Msg:
            tracking_id = "trk_4"
            title = "Test"
            rendered_content = "Body"

        class Recipient:
            token = "device_token_abc"

        with patch("google.oauth2.service_account.Credentials.from_service_account_info", side_effect=Exception("Invalid JWT signature")):
            res = asyncio.run(channel.send(Msg(), Recipient()))
            self.assertFalse(res.success)
            self.assertEqual(res.error_code, "FCM_AUTH_ERROR")
            self.assertIn("FCM OAuth2 authentication failed", res.error_message)

    def test_fcm_http_v1_successful_dispatch_and_headers(self):
        """Verifies successful dispatch to FCM HTTP v1 endpoint with Bearer auth and payload."""
        channel = PushChannel(
            provider_type="fcm",
            sender_address="test-gov-push-project",
            credentials={"service_account_info": self.sample_sa_info},
        )

        class Msg:
            tracking_id = "trk_success_01"
            title = "Flood Advisory"
            rendered_content = "Water levels rising in sector 4. Move to designated shelters."

        class Recipient:
            token = "client_device_token_xyz"

        mock_google_creds = MagicMock()
        mock_google_creds.token = "valid_fcm_v1_bearer_token"
        mock_google_creds.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = {
            "name": "projects/test-gov-push-project/messages/msg_fcm_uuid_999"
        }

        with patch("google.oauth2.service_account.Credentials.from_service_account_info", return_value=mock_google_creds):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_http_response) as mock_post:
                res = asyncio.run(channel.send(Msg(), Recipient()))

                self.assertTrue(res.success)
                self.assertEqual(res.status, "Sent")
                self.assertEqual(res.provider_name, "push_fcm")
                self.assertEqual(res.provider_message_id, "projects/test-gov-push-project/messages/msg_fcm_uuid_999")

                # Verify HTTP call arguments
                mock_post.assert_called_once()
                target_url = mock_post.call_args[0][0]
                self.assertEqual(target_url, "https://fcm.googleapis.com/v1/projects/test-gov-push-project/messages:send")

                headers = mock_post.call_args[1]["headers"]
                self.assertEqual(headers["Authorization"], "Bearer valid_fcm_v1_bearer_token")
                self.assertEqual(headers["Content-Type"], "application/json")

                payload = mock_post.call_args[1]["json"]
                self.assertEqual(payload["message"]["token"], "client_device_token_xyz")
                self.assertEqual(payload["message"]["notification"]["title"], "Flood Advisory")
                self.assertEqual(payload["message"]["data"]["tracking_id"], "trk_success_01")

    def test_fcm_http_v1_unregistered_token_maps_to_device_token_invalid(self):
        """Verifies UNREGISTERED error code maps to DEVICE_TOKEN_INVALID."""
        channel = PushChannel(
            provider_type="fcm",
            sender_address="test-gov-push-project",
            credentials={"service_account_info": self.sample_sa_info},
        )

        class Msg:
            tracking_id = "trk_unreg"
            title = "Test"
            rendered_content = "Body"

        class Recipient:
            token = "expired_client_token"

        mock_google_creds = MagicMock()
        mock_google_creds.token = "bearer_token"
        mock_google_creds.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

        mock_http_response = MagicMock()
        mock_http_response.status_code = 404
        mock_http_response.headers = {"content-type": "application/json"}
        mock_http_response.json.return_value = {
            "error": {
                "code": 404,
                "message": "Requested entity was not found.",
                "status": "NOT_FOUND",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError",
                        "errorCode": "UNREGISTERED",
                    }
                ],
            }
        }

        with patch("google.oauth2.service_account.Credentials.from_service_account_info", return_value=mock_google_creds):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_http_response):
                res = asyncio.run(channel.send(Msg(), Recipient()))
                self.assertFalse(res.success)
                self.assertEqual(res.error_code, "DEVICE_TOKEN_INVALID")

    def test_fcm_http_v1_auth_error_http_401(self):
        """Verifies HTTP 401 unauthenticated maps to FCM_AUTH_ERROR."""
        channel = PushChannel(
            provider_type="fcm",
            sender_address="test-gov-push-project",
            credentials={"service_account_info": self.sample_sa_info},
        )

        class Msg:
            tracking_id = "trk_401"
            title = "Test"
            rendered_content = "Body"

        class Recipient:
            token = "device_token"

        mock_google_creds = MagicMock()
        mock_google_creds.token = "revoked_token"
        mock_google_creds.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

        mock_http_response = MagicMock()
        mock_http_response.status_code = 401
        mock_http_response.headers = {"content-type": "application/json"}
        mock_http_response.json.return_value = {
            "error": {
                "code": 401,
                "message": "Request had invalid authentication credentials.",
                "status": "UNAUTHENTICATED",
            }
        }

        with patch("google.oauth2.service_account.Credentials.from_service_account_info", return_value=mock_google_creds):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_http_response):
                res = asyncio.run(channel.send(Msg(), Recipient()))
                self.assertFalse(res.success)
                self.assertEqual(res.error_code, "FCM_AUTH_ERROR")

    def test_fcm_http_v1_quota_exceeded_http_429(self):
        """Verifies HTTP 429 maps to RATE_LIMIT_EXCEEDED."""
        channel = PushChannel(
            provider_type="fcm",
            sender_address="test-gov-push-project",
            credentials={"service_account_info": self.sample_sa_info},
        )

        class Msg:
            tracking_id = "trk_429"
            title = "Test"
            rendered_content = "Body"

        class Recipient:
            token = "device_token"

        mock_google_creds = MagicMock()
        mock_google_creds.token = "bearer_token"
        mock_google_creds.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

        mock_http_response = MagicMock()
        mock_http_response.status_code = 429
        mock_http_response.headers = {"content-type": "application/json"}
        mock_http_response.json.return_value = {
            "error": {
                "code": 429,
                "message": "Quota exceeded for project test-gov-push-project",
                "status": "RESOURCE_EXHAUSTED",
            }
        }

        with patch("google.oauth2.service_account.Credentials.from_service_account_info", return_value=mock_google_creds):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_http_response):
                res = asyncio.run(channel.send(Msg(), Recipient()))
                self.assertFalse(res.success)
                self.assertEqual(res.error_code, "RATE_LIMIT_EXCEEDED")

    def test_fcm_http_v1_server_error_http_503(self):
        """Verifies HTTP 503 gateway failure maps to GATEWAY_TIMEOUT."""
        channel = PushChannel(
            provider_type="fcm",
            sender_address="test-gov-push-project",
            credentials={"service_account_info": self.sample_sa_info},
        )

        class Msg:
            tracking_id = "trk_503"
            title = "Test"
            rendered_content = "Body"

        class Recipient:
            token = "device_token"

        mock_google_creds = MagicMock()
        mock_google_creds.token = "bearer_token"
        mock_google_creds.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

        mock_http_response = MagicMock()
        mock_http_response.status_code = 503
        mock_http_response.headers = {"content-type": "application/json"}
        mock_http_response.json.return_value = {
            "error": {
                "code": 503,
                "message": "The service is temporarily unavailable.",
                "status": "UNAVAILABLE",
            }
        }

        with patch("google.oauth2.service_account.Credentials.from_service_account_info", return_value=mock_google_creds):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_http_response):
                res = asyncio.run(channel.send(Msg(), Recipient()))
                self.assertFalse(res.success)
                self.assertEqual(res.error_code, "GATEWAY_TIMEOUT")

    def test_fcm_token_sanitization_no_bearer_leak(self):
        """Verifies error responses redact sensitive bearer tokens if present in error message."""
        channel = PushChannel(
            provider_type="fcm",
            sender_address="test-gov-push-project",
            credentials={"service_account_info": self.sample_sa_info},
        )

        class Msg:
            tracking_id = "trk_leak"
            title = "Test"
            rendered_content = "Body"

        class Recipient:
            token = "device_token"

        secret_token = "secret_bearer_token_should_not_leak"
        mock_google_creds = MagicMock()
        mock_google_creds.token = secret_token
        mock_google_creds.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

        mock_http_response = MagicMock()
        mock_http_response.status_code = 400
        mock_http_response.headers = {"content-type": "application/json"}
        mock_http_response.json.return_value = {
            "error": {
                "code": 400,
                "message": f"Bad Request with token {secret_token}",
                "status": "INVALID_ARGUMENT",
            }
        }

        with patch("google.oauth2.service_account.Credentials.from_service_account_info", return_value=mock_google_creds):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_http_response):
                res = asyncio.run(channel.send(Msg(), Recipient()))
                self.assertNotIn(secret_token, res.error_message)
                self.assertIn("[REDACTED]", res.error_message)

    def test_fcm_static_server_key_backward_compatibility(self):
        """Verifies backward compatibility when static server_key or access_token is directly provided."""
        channel = PushChannel(
            provider_type="fcm",
            sender_address="test-gov-push-project",
            credentials={"project_id": "test-gov-push-project", "server_key": "legacy_static_key_123"},
        )

        token, err_code, err_msg = channel._get_fcm_access_token(channel.credentials, "test-gov-push-project")
        self.assertEqual(token, "legacy_static_key_123")
        self.assertIsNone(err_code)

    def test_push_mock_mode_preservation(self):
        """Verifies mock mode remains deterministic and unaffected."""
        channel = PushChannel(provider_type="mock")

        class Msg:
            tracking_id = "trk_mock"
            title = "Test"
            rendered_content = "Body"

        # Success
        class RecOk:
            token = "token_regular"

        res = asyncio.run(channel.send(Msg(), RecOk()))
        self.assertTrue(res.success)
        self.assertEqual(res.status, "Sent")
        self.assertIn("mock-fcm", res.provider_message_id)

        # Permanent fail
        class RecPerm:
            token = "token_fail_perm"

        res = asyncio.run(channel.send(Msg(), RecPerm()))
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "DEVICE_TOKEN_INVALID")

        # Temporary fail
        class RecTemp:
            token = "token_fail_temp"

        res = asyncio.run(channel.send(Msg(), RecTemp()))
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "GATEWAY_TIMEOUT")

    def test_admin_channel_fcm_credentials_masking_and_updating(self):
        """Verifies administrative configuration endpoint masks FCM credentials and preserves them on update."""
        # 1. Update Push configuration with full service account credentials
        update_payload = {
            "is_enabled": True,
            "provider_type": "fcm",
            "sender_address": "test-gov-push-project",
            "sender_name": "Ministry Push Alerts",
            "credentials": {
                "project_id": "test-gov-push-project",
                "client_email": self.sample_sa_info["client_email"],
                "private_key": self.sample_sa_info["private_key"],
            },
        }

        res = self.client.put(
            "/admin/channels/Push",
            json=update_payload,
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["channel"], "Push")
        self.assertEqual(data["provider_type"], "fcm")
        self.assertTrue(data["has_credentials"])

        # Confirm sensitive private_key is masked
        masked = data["masked_credentials"]
        self.assertIn("private_key", masked)
        self.assertIn("****", masked["private_key"])
        self.assertNotIn(self.sample_sa_info["private_key"], masked["private_key"])

        # 2. Update only sender_name while sending back masked credentials:
        # Confirm real private_key is NOT overwritten with the masked string
        update_name_payload = {
            "sender_name": "Updated Push Header Name",
            "credentials": {
                "project_id": "test-gov-push-project",
                "client_email": masked.get("client_email", self.sample_sa_info["client_email"]),
                "private_key": masked["private_key"],  # Contains ****
            },
        }

        res2 = self.client.put(
            "/admin/channels/Push",
            json=update_name_payload,
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["sender_name"], "Updated Push Header Name")

        # Verify underlying DB record retained full private_key
        db_cfg = self.db.query(ChannelConfiguration).filter_by(channel="Push").first()
        self.assertEqual(db_cfg.credentials["private_key"], self.sample_sa_info["private_key"])

    def test_fcm_device_token_auto_deactivation_integration(self):
        """Verifies that an UNREGISTERED response from FCM HTTP v1 triggers automatic device token deactivation."""
        from app.models.audience import AudienceMember
        from app.models.campaign import Campaign
        from app.models.content_asset import ContentAsset
        from app.services.campaign_sending_service import send_campaign
        from app.schemas.channel_config import CampaignSendRequest

        # Create active DeviceToken and associated AudienceMember
        bad_token_str = "fcm_dead_client_device_token_xyz"
        member = AudienceMember(
            name="Citizen Tester",
            phone="+919876543210",
            email="citizen@example.gov.in",
            preferred_channel="Push",
            consent_status=True,
        )
        self.db.add(member)
        self.db.commit()

        dt = DeviceToken(
            token=bad_token_str,
            device_type="android",
            audience_member_id=member.id,
            is_active=True,
        )
        self.db.add(dt)

        # Configure Push channel with FCM provider
        push_cfg = ChannelConfiguration(
            channel="Push",
            is_enabled=True,
            provider_type="fcm",
            sender_address="test-gov-push-project",
            sender_name="Emergency Alerts",
            credentials={"service_account_info": self.sample_sa_info},
        )
        self.db.add(push_cfg)

        campaign = Campaign(
            id=50,
            name="Urgent Weather Warning",
            campaign_type="Emergency Alert",
            objective="Notify citizens",
            priority="High",
            status="Approved",
            channels=["Push"],
            created_by=self.admin.id,
        )
        self.db.add(campaign)

        root_asset = ContentAsset(
            title="Weather Alert",
            body="Alert body text",
            category="Emergency Alert",
            channel="Push",
            source_language="en",
            review_status="Approved",
            campaign_id=50,
            created_by=self.admin.id,
        )
        self.db.add(root_asset)
        self.db.commit()

        # Mock Google auth and FCM 404 UNREGISTERED response
        mock_google_creds = MagicMock()
        mock_google_creds.token = "bearer_token"
        mock_google_creds.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

        mock_http_response = MagicMock()
        mock_http_response.status_code = 404
        mock_http_response.headers = {"content-type": "application/json"}
        mock_http_response.json.return_value = {
            "error": {
                "code": 404,
                "message": "Requested entity was not found.",
                "status": "NOT_FOUND",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError",
                        "errorCode": "UNREGISTERED",
                    }
                ],
            }
        }

        with patch("google.oauth2.service_account.Credentials.from_service_account_info", return_value=mock_google_creds):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_http_response):
                summary = asyncio.run(
                    send_campaign(
                        db=self.db,
                        campaign_id=50,
                        request=CampaignSendRequest(channels=["Push"], enable_fallback=False),
                        current_user=self.admin,
                    )
                )

        # Confirm send outcome
        self.assertEqual(summary.failed_messages, 1)

        # Verify device token was automatically deactivated in DB
        self.db.refresh(dt)
        self.assertFalse(dt.is_active, "DeviceToken should have been deactivated (is_active=False)")

    def test_fcm_concurrent_token_refresh_safety(self):
        """Verifies that concurrent token requests under lock only invoke Google OAuth refresh once."""
        import concurrent.futures

        channel = PushChannel(
            provider_type="fcm",
            sender_address="test-gov-push-project",
            credentials={"service_account_info": self.sample_sa_info},
        )

        mock_google_creds = MagicMock()
        mock_google_creds.token = "concurrent_safe_token"
        mock_google_creds.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

        with patch("google.oauth2.service_account.Credentials.from_service_account_info", return_value=mock_google_creds) as mock_from_info:
            def fetch_token():
                return channel._get_fcm_access_token(channel.credentials, "test-gov-push-project")

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(fetch_token) for _ in range(10)]
                results = [f.result() for f in futures]

            # All 10 callers should have received the valid token
            for token, err_code, err_msg in results:
                self.assertEqual(token, "concurrent_safe_token")
                self.assertIsNone(err_code)

            # Only ONE call to Google Auth should have occurred
            self.assertEqual(mock_from_info.call_count, 1)


if __name__ == "__main__":
    unittest.main()
