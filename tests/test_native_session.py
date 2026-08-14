"""A native client can keep a session.

Access tokens last fifteen minutes. The browser survives that with an httpOnly
refresh cookie and an interceptor that re-authenticates on a 401. The mobile app
had neither and stored only the access token, so a member was signed out a
quarter of an hour after signing in — which presents as "my account works on the
web but not on the app", because the account is fine and the session isn't.

Native clients now receive the refresh token in the response body and present it
back. Browsers must keep getting a cookie and nothing else: a refresh token in a
JSON body on the web is readable by any script on the page, which is the whole
reason httpOnly exists.
"""
import pytest

from tests.conftest import auth_header

NATIVE = {"X-Client-Platform": "ios"}


@pytest.mark.asyncio
async def test_a_browser_never_receives_the_refresh_token_in_the_body(client, sugar_user):
    r = await client.post(
        "/api/auth/login",
        json={"email": "testsd@test.com", "password": "testpass123"},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("refresh_token") is None
    # It still arrives, as a cookie the page's scripts cannot read.
    assert "refresh_token" in r.cookies


@pytest.mark.asyncio
async def test_a_native_client_receives_the_refresh_token(client, sugar_user):
    r = await client.post(
        "/api/auth/login",
        json={"email": "testsd@test.com", "password": "testpass123"},
        headers=NATIVE,
    )
    assert r.status_code == 200, r.text
    assert r.json().get("refresh_token"), "native clients have no cookie jar to fall back on"


@pytest.mark.asyncio
async def test_the_returned_token_buys_a_new_access_token(client, sugar_user):
    login = await client.post(
        "/api/auth/login",
        json={"email": "testsd@test.com", "password": "testpass123"},
        headers=NATIVE,
    )
    refresh_token = login.json()["refresh_token"]

    # Cleared so this exercises the body path a native client actually uses,
    # rather than silently falling back to the cookie login left behind.
    client.cookies.clear()

    r = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token}, headers=NATIVE)
    assert r.status_code == 200, r.text

    fresh = r.json()["access_token"]
    assert fresh
    # And it actually authenticates, which is the point.
    me = await client.get("/api/profiles/me", headers=auth_header(fresh))
    assert me.status_code in (200, 404)  # 404 only if the fixture has no profile


@pytest.mark.asyncio
async def test_a_junk_refresh_token_is_refused(client):
    r = await client.post("/api/auth/refresh", json={"refresh_token": "not-a-token"}, headers=NATIVE)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_without_a_token_anywhere_is_refused(client):
    """No cookie and no body — the request cannot be honoured, and saying so
    beats a 500."""
    r = await client.post("/api/auth/refresh", json={})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_an_access_token_is_not_accepted_as_a_refresh_token(client, sugar_user):
    """They are different token types. Letting an access token refresh itself
    would make the fifteen-minute expiry meaningless."""
    login = await client.post(
        "/api/auth/login",
        json={"email": "testsd@test.com", "password": "testpass123"},
        headers=NATIVE,
    )
    access = login.json()["access_token"]

    # The test client kept the refresh cookie from signing in, and the endpoint
    # reads the cookie before the body — so without clearing it this asserts
    # nothing. A real native client has no cookie jar at all.
    client.cookies.clear()

    r = await client.post("/api/auth/refresh", json={"refresh_token": access}, headers=NATIVE)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_creating_a_profile_sends_a_welcome(client, db, monkeypatch):
    """It was written, formatted, and called from nowhere, so nobody who signed
    up ever received one. Sent on profile creation rather than registration
    because it greets them by name."""
    sent = []
    monkeypatch.setattr(
        "app.services.email.send_welcome",
        lambda to, display_name: sent.append((to, display_name)),
    )

    r = await client.post(
        "/api/auth/register",
        json={
            "email": "welcomed@test.com",
            "password": "testpass123",
            "user_type": "established",
            "date_of_birth": "1988-01-01",
        },
    )
    assert r.status_code in (200, 201), r.text
    token = r.json()["access_token"]

    r = await client.post(
        "/api/profiles/",
        headers=auth_header(token),
        json={
            "display_name": "Welcomed",
            "date_of_birth": "1988-01-01",
            "gender": "male",
            "city": "Miami",
        },
    )
    assert r.status_code in (200, 201), r.text
    assert sent == [("welcomed@test.com", "Welcomed")]
