"""Integration tests against the live API.

These tests hit the production API to verify the full stack works.
Run with: pytest tests/test_integration.py -v

Tests create ephemeral accounts with test emails that can be cleaned up.
Rate-limited to 5 registrations/hour per IP.
"""
import pytest
import httpx
import time

BASE = "https://sugardads-api.fly.dev"
TEST_PREFIX = f"inttest-{int(time.time())}"


@pytest.fixture(scope="module")
def api():
    return httpx.Client(base_url=BASE, timeout=15)


@pytest.fixture(scope="module")
def sugar_account(api):
    """Register a sugar daddy and return token."""
    resp = api.post("/api/auth/register", json={
        "email": f"{TEST_PREFIX}-sd@test.com",
        "password": "testpass123",
        "user_type": "sugar",
    })
    if resp.status_code == 429:
        pytest.skip("Rate limited — try again later")
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    data = resp.json()
    token = data["access_token"]

    # Create profile
    api.post("/api/profiles/", json={
        "display_name": "IntTest SD",
        "date_of_birth": "1988-05-15",
        "gender": "male",
        "city": "Miami",
        "looking_for": "Integration test",
    }, headers={"Authorization": f"Bearer {token}"})

    return {"token": token, "user_id": data["user"]["id"]}


@pytest.fixture(scope="module")
def attractive_account(api):
    """Register an attractive member and return token."""
    resp = api.post("/api/auth/register", json={
        "email": f"{TEST_PREFIX}-sb@test.com",
        "password": "testpass123",
        "user_type": "attractive",
    })
    if resp.status_code == 429:
        pytest.skip("Rate limited")
    assert resp.status_code == 201
    data = resp.json()
    token = data["access_token"]

    api.post("/api/profiles/", json={
        "display_name": "IntTest SB",
        "date_of_birth": "1998-07-20",
        "gender": "female",
        "city": "Miami",
        "looking_for": "Integration test",
    }, headers={"Authorization": f"Bearer {token}"})

    return {"token": token, "user_id": data["user"]["id"]}


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ─── Health ───

class TestHealth:
    def test_api_healthy(self, api):
        resp = api.get("/api/health")
        assert resp.status_code == 200
        d = resp.json()
        assert d["status"] == "ok"
        assert d["db"] is True


# ─── Auth ───

class TestAuth:
    def test_login_works(self, api, sugar_account):
        resp = api.post("/api/auth/login", json={
            "email": f"{TEST_PREFIX}-sd@test.com",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_wrong_password_rejected(self, api):
        resp = api.post("/api/auth/login", json={
            "email": f"{TEST_PREFIX}-sd@test.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_nonexistent_user_rejected(self, api):
        resp = api.post("/api/auth/login", json={
            "email": "nobody-ever@nonexistent.com",
            "password": "testpass123",
        })
        assert resp.status_code == 401


# ─── Profile ───

class TestProfile:
    def test_get_profile(self, api, sugar_account):
        resp = api.get("/api/profiles/me", headers=auth(sugar_account["token"]))
        assert resp.status_code == 200
        d = resp.json()
        assert d["display_name"] == "IntTest SD"
        assert d["city"] == "Miami"

    def test_update_profile(self, api, sugar_account):
        resp = api.patch("/api/profiles/me", json={
            "headline": "Integration test headline",
            "lifestyle_tags": ["enm", "kink_friendly"],
        }, headers=auth(sugar_account["token"]))
        assert resp.status_code == 200
        d = resp.json()
        assert d["headline"] == "Integration test headline"
        assert "enm" in d["lifestyle_tags"]

    def test_unauthenticated_rejected(self, api):
        resp = api.get("/api/profiles/me")
        assert resp.status_code in (401, 403, 422)


# ─── Subscription ───

class TestSubscription:
    def test_free_tier(self, api, sugar_account):
        resp = api.get("/api/subscription/", headers=auth(sugar_account["token"]))
        assert resp.status_code == 200
        d = resp.json()
        assert d["tier"] == "free"
        assert d["can_upgrade"] is True

    def test_attractive_also_free(self, api, attractive_account):
        resp = api.get("/api/subscription/", headers=auth(attractive_account["token"]))
        assert resp.status_code == 200
        assert resp.json()["tier"] == "free"


# ─── Billing ───

class TestBilling:
    def test_checkout_premium(self, api, sugar_account):
        resp = api.post("/api/billing/checkout?tier=premium", headers=auth(sugar_account["token"]))
        assert resp.status_code == 200
        url = resp.json().get("checkout_url", "")
        assert "stripe.com" in url, f"Expected Stripe URL, got: {url}"

    def test_checkout_diamond(self, api, sugar_account):
        resp = api.post("/api/billing/checkout?tier=diamond", headers=auth(sugar_account["token"]))
        assert resp.status_code == 200
        assert "stripe.com" in resp.json().get("checkout_url", "")

    def test_checkout_invalid_tier(self, api, sugar_account):
        resp = api.post("/api/billing/checkout?tier=gold", headers=auth(sugar_account["token"]))
        assert resp.status_code == 400

    def test_cancel_no_subscription(self, api, sugar_account):
        resp = api.post("/api/billing/cancel", headers=auth(sugar_account["token"]))
        assert resp.status_code == 400
        assert "No active subscription" in resp.json()["detail"]

    def test_webhook_rejects_bad_signature(self, api):
        resp = api.post("/api/billing/webhook",
            content=b'{"type":"test"}',
            headers={
                "Content-Type": "application/json",
                "stripe-signature": "bad_sig_here",
            })
        assert resp.status_code == 400


# ─── Verification ───

class TestVerification:
    def test_submit_photo_verification(self, api, sugar_account):
        resp = api.post("/api/profiles/verify/photo", headers=auth(sugar_account["token"]))
        assert resp.status_code == 200
        assert resp.json()["submitted"] is True

    def test_duplicate_rejected(self, api, sugar_account):
        resp = api.post("/api/profiles/verify/photo", headers=auth(sugar_account["token"]))
        assert resp.status_code == 400
        assert "pending" in resp.json()["detail"].lower()

    def test_status_shows_pending(self, api, sugar_account):
        resp = api.get("/api/profiles/verify/status", headers=auth(sugar_account["token"]))
        assert resp.status_code == 200
        d = resp.json()
        assert d["pending_photo"] is True
        assert d["photo_verified"] is False


# ─── Privacy ───

class TestPrivacy:
    def test_read_privacy(self, api, sugar_account):
        resp = api.get("/api/subscription/privacy", headers=auth(sugar_account["token"]))
        assert resp.status_code == 200
        assert "hide_online_status" in resp.json()

    def test_update_privacy(self, api, sugar_account):
        resp = api.patch("/api/subscription/privacy", json={
            "hide_online_status": True,
        }, headers=auth(sugar_account["token"]))
        assert resp.status_code == 200
        assert resp.json()["hide_online_status"] is True


# ─── Discover ───

class TestDiscover:
    def test_returns_profiles(self, api, sugar_account):
        resp = api.get("/api/discover/?page_size=5", headers=auth(sugar_account["token"]))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_requires_auth(self, api):
        resp = api.get("/api/discover/?page_size=5")
        assert resp.status_code in (401, 403, 422)


# ─── Contact & Newsletter ───

class TestContact:
    def test_contact_form(self, api):
        resp = api.post("/api/contact", json={
            "name": "IntTest",
            "email": "inttest@test.com",
            "category": "general",
            "message": "Automated integration test message for validation.",
        })
        assert resp.status_code == 200

    def test_short_message_rejected(self, api):
        resp = api.post("/api/contact", json={
            "name": "T",
            "email": "t@test.com",
            "category": "general",
            "message": "short",
        })
        assert resp.status_code == 422

    def test_newsletter(self, api):
        resp = api.post("/api/newsletter/subscribe", json={
            "email": f"{TEST_PREFIX}-news@test.com",
            "source": "inttest",
        })
        assert resp.status_code == 200
        assert resp.json()["subscribed"] is True
