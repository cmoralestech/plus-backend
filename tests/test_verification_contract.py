"""The keys both clients read off the verification endpoints.

The mobile screen typed four fields — `identity_status`, `financial_status`,
`is_photo_verified`, `is_income_verified` — that `/api/verification/me` has
never returned. Every one came back `undefined`, so both cards rendered "Not
started" for everybody including already-verified members, and both buttons
stayed live and called an endpoint that 503s.

Nothing failed. TypeScript was satisfied because the fields were optional, and
the response is cast rather than validated, so a client can read a field the
server does not send and no test on either side notices.

The same screen then treated a 200 as proof a check had started. Without a
provider configured the start endpoints return 200 and do nothing, so members
were told a review was underway that had never been recorded.

These pin the response shapes the clients actually depend on. A key renamed or
dropped here should fail in this repo rather than silently blank a screen in
someone's hand.
"""
import pytest

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_verification_me_returns_the_keys_clients_read(client, sugar_user):
    r = await client.get("/api/verification/me", headers=auth_header(sugar_user["token"]))
    assert r.status_code == 200, r.text

    body = r.json()
    for key in (
        "identity_verified",
        "financially_verified",
        "is_expired",
        "provider_configured",
        "qualification_result",
        "declared_qualifies",
    ):
        assert key in body, f"{key} is read by a client and is missing from the response"

    # The fields the mobile screen used to read. If any of these ever appears,
    # it means a second vocabulary has grown for the same idea.
    for absent in ("identity_status", "financial_status", "is_photo_verified", "is_income_verified"):
        assert absent not in body, (
            f"{absent} is the name a client once guessed at; either the client is wrong "
            "or this endpoint has grown a duplicate field"
        )


@pytest.mark.asyncio
async def test_manual_verify_status_returns_the_keys_clients_read(client, sugar_user):
    r = await client.get("/api/profiles/verify/status", headers=auth_header(sugar_user["token"]))
    assert r.status_code == 200, r.text

    body = r.json()
    assert set(body) == {"photo_verified", "income_verified", "pending_photo", "pending_income"}


@pytest.mark.asyncio
async def test_manual_photo_request_is_accepted_and_then_pending(client, sugar_user):
    """The path the phone now uses, and the one that actually works."""
    headers = auth_header(sugar_user["token"])

    submitted = await client.post("/api/profiles/verify/photo", headers=headers)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["submitted"] is True

    status = await client.get("/api/profiles/verify/status", headers=headers)
    assert status.json()["pending_photo"] is True

    # A second request while one is outstanding is refused with a reason worth
    # showing, which is what the client surfaces verbatim.
    again = await client.post("/api/profiles/verify/photo", headers=headers)
    assert again.status_code == 400
    assert "pending" in again.json()["detail"].lower()


@pytest.mark.asyncio
async def test_starting_a_provider_check_succeeds_while_doing_nothing(client, sugar_user):
    """Pins why the client hides these behind `provider_configured`.

    This is the trap. With no provider set the call does not fail — it returns
    200 with `status: "unavailable"`, records nothing and schedules no review.
    A client that checks only the status code sees success, which is exactly
    what the mobile screen did: it announced "our team will review this" for a
    request that did not exist.

    So the status code cannot be the signal. `provider_configured` is, and the
    body says so a second time.
    """
    headers = auth_header(sugar_user["token"])

    me = await client.get("/api/verification/me", headers=headers)
    assert me.json()["provider_configured"] is False

    started = await client.post("/api/verification/identity/start", headers=headers)
    assert started.status_code == 200, "a client checking only the status sees this as success"
    assert started.json()["status"] == "unavailable"
    assert started.json()["reference"] is None

    # And nothing moved as a result of that call.
    after = await client.get("/api/verification/me", headers=headers)
    assert after.json()["identity_verified"] is False
