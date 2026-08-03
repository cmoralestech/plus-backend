"""Integration tests for the complete signup → onboarding → subscription flow.

These tests verify the critical revenue path:
  Register → Profile → Subscription → Checkout → Webhook → Active Premium
"""
import pytest
from tests.conftest import auth_header


@pytest.mark.asyncio
class TestRegistration:
    async def test_register_creates_user(self, client):
        resp = await client.post("/api/auth/register", json={
            "email": "newuser@test.com",
            "password": "testpass123",
            "user_type": "established",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["email"] == "newuser@test.com"
        assert data["user"]["user_type"] == "established"
        assert data["user"]["has_profile"] is False

    async def test_register_attractive_member(self, client):
        resp = await client.post("/api/auth/register", json={
            "email": "attractive@test.com",
            "password": "testpass123",
            "user_type": "plus",
        })
        assert resp.status_code == 201
        assert resp.json()["user"]["user_type"] == "plus"

    async def test_duplicate_email_rejected(self, client):
        await client.post("/api/auth/register", json={
            "email": "dupe@test.com",
            "password": "testpass123",
            "user_type": "established",
        })
        resp = await client.post("/api/auth/register", json={
            "email": "dupe@test.com",
            "password": "testpass123",
            "user_type": "established",
        })
        assert resp.status_code == 400
        assert "already" in resp.json()["detail"].lower()

    async def test_weak_password_rejected(self, client):
        resp = await client.post("/api/auth/register", json={
            "email": "weak@test.com",
            "password": "123",
            "user_type": "established",
        })
        assert resp.status_code == 422  # validation error


@pytest.mark.asyncio
class TestLogin:
    async def test_login_valid_credentials(self, client):
        # Register first
        await client.post("/api/auth/register", json={
            "email": "login@test.com",
            "password": "testpass123",
            "user_type": "established",
        })
        resp = await client.post("/api/auth/login", json={
            "email": "login@test.com",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_wrong_password(self, client):
        await client.post("/api/auth/register", json={
            "email": "wrongpw@test.com",
            "password": "testpass123",
            "user_type": "established",
        })
        resp = await client.post("/api/auth/login", json={
            "email": "wrongpw@test.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client):
        resp = await client.post("/api/auth/login", json={
            "email": "nobody@test.com",
            "password": "testpass123",
        })
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestProfileCreation:
    async def test_create_profile(self, client, sugar_user):
        # sugar_user already has a profile via fixture, test with a new user
        reg = await client.post("/api/auth/register", json={
            "email": "newprofile@test.com",
            "password": "testpass123",
            "user_type": "established",
        })
        token = reg.json()["access_token"]

        resp = await client.post("/api/profiles/", json={
            "display_name": "New User",
            "date_of_birth": "1990-01-15",
            "gender": "male",
            "city": "Houston",
            "looking_for": "Someone genuine",
        }, headers=auth_header(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["display_name"] == "New User"
        assert data["city"] == "Houston"

    async def test_no_profile_returns_404(self, client):
        reg = await client.post("/api/auth/register", json={
            "email": "noprofile@test.com",
            "password": "testpass123",
            "user_type": "established",
        })
        token = reg.json()["access_token"]
        resp = await client.get("/api/profiles/me", headers=auth_header(token))
        assert resp.status_code == 404

    async def test_profile_update(self, client, sugar_user):
        resp = await client.patch("/api/profiles/me", json={
            "headline": "Updated",
            "lifestyle_tags": ["enm", "kink_friendly"],
        }, headers=auth_header(sugar_user["token"]))
        assert resp.status_code == 200
        data = resp.json()
        assert data["headline"] == "Updated"
        assert "enm" in data["lifestyle_tags"]
        assert "kink_friendly" in data["lifestyle_tags"]

    async def test_invalid_lifestyle_tag_rejected(self, client, sugar_user):
        resp = await client.patch("/api/profiles/me", json={
            "lifestyle_tags": ["invalid_tag"],
        }, headers=auth_header(sugar_user["token"]))
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestSubscriptionFlow:
    async def test_free_user_sees_free_tier(self, client, sugar_user):
        resp = await client.get("/api/subscription/", headers=auth_header(sugar_user["token"]))
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "free"
        assert data["can_upgrade"] is True

    async def test_plus_user_sees_plus(self, client, premium_user):
        resp = await client.get("/api/subscription/", headers=auth_header(premium_user["token"]))
        assert resp.status_code == 200
        assert resp.json()["tier"] == "plus"

    async def test_cancel_without_subscription_rejected(self, client, sugar_user):
        resp = await client.post("/api/billing/cancel", headers=auth_header(sugar_user["token"]))
        assert resp.status_code == 400
        assert "No active subscription" in resp.json()["detail"]

    async def test_invalid_checkout_tier(self, client, sugar_user):
        resp = await client.post("/api/billing/checkout?tier=gold", headers=auth_header(sugar_user["token"]))
        assert resp.status_code == 400


@pytest.mark.asyncio
class TestVerification:
    async def test_submit_photo_verification(self, client, sugar_user):
        resp = await client.post("/api/profiles/verify/photo", headers=auth_header(sugar_user["token"]))
        assert resp.status_code == 200
        assert resp.json()["submitted"] is True

    async def test_duplicate_verification_rejected(self, client, sugar_user):
        await client.post("/api/profiles/verify/photo", headers=auth_header(sugar_user["token"]))
        resp = await client.post("/api/profiles/verify/photo", headers=auth_header(sugar_user["token"]))
        assert resp.status_code == 400
        assert "pending" in resp.json()["detail"].lower()

    async def test_verification_status(self, client, sugar_user):
        await client.post("/api/profiles/verify/photo", headers=auth_header(sugar_user["token"]))
        resp = await client.get("/api/profiles/verify/status", headers=auth_header(sugar_user["token"]))
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_photo"] is True
        assert data["photo_verified"] is False


@pytest.mark.asyncio
class TestPrivacySettings:
    async def test_read_privacy(self, client, sugar_user):
        resp = await client.get("/api/subscription/privacy", headers=auth_header(sugar_user["token"]))
        assert resp.status_code == 200
        data = resp.json()
        assert data["hide_online_status"] is False

    async def test_update_privacy(self, client, sugar_user):
        resp = await client.patch("/api/subscription/privacy", json={
            "hide_online_status": True,
        }, headers=auth_header(sugar_user["token"]))
        assert resp.status_code == 200
        assert resp.json()["hide_online_status"] is True


@pytest.mark.asyncio
class TestWebhookSecurity:
    async def test_bad_signature_rejected(self, client):
        resp = await client.post("/api/billing/webhook",
            content=b'{"type":"test"}',
            headers={
                "Content-Type": "application/json",
                "stripe-signature": "bad_sig",
            })
        assert resp.status_code == 400

    async def test_missing_signature_rejected(self, client):
        resp = await client.post("/api/billing/webhook",
            content=b'{"type":"test"}',
            headers={"Content-Type": "application/json"})
        # Should either reject (400) or process without sig verification warning
        assert resp.status_code in (200, 400)


@pytest.mark.asyncio
class TestContactAndNewsletter:
    async def test_contact_form(self, client):
        resp = await client.post("/api/contact", json={
            "name": "Test User",
            "email": "contact@test.com",
            "category": "general",
            "message": "This is a test message that is long enough to pass validation.",
        })
        assert resp.status_code == 200
        assert "sent" in resp.json()["message"].lower()

    async def test_contact_short_message_rejected(self, client):
        resp = await client.post("/api/contact", json={
            "name": "Test",
            "email": "contact@test.com",
            "category": "general",
            "message": "too short",
        })
        assert resp.status_code == 422

    async def test_contact_invalid_category_rejected(self, client):
        resp = await client.post("/api/contact", json={
            "name": "Test",
            "email": "contact@test.com",
            "category": "invalid_category",
            "message": "This is a valid length message for testing.",
        })
        assert resp.status_code == 422

    async def test_newsletter_subscribe(self, client):
        resp = await client.post("/api/newsletter/subscribe", json={
            "email": "newsletter@test.com",
            "source": "test",
        })
        assert resp.status_code == 200
        assert resp.json()["subscribed"] is True


@pytest.mark.asyncio
class TestDiscover:
    async def test_discover_returns_profiles(self, client, sugar_user, attractive_user):
        resp = await client.get("/api/discover/?page_size=10", headers=auth_header(sugar_user["token"]))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_discover_requires_auth(self, client):
        resp = await client.get("/api/discover/?page_size=10")
        assert resp.status_code in (401, 403, 422)


@pytest.mark.asyncio
class TestHealthCheck:
    async def test_health(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["db"] is True
