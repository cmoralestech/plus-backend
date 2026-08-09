"""Push actually fires on the events that matter.

send_push was written, tested and wired to nothing — it had zero callers, so the
whole subsystem would have stayed silent on the day credentials arrived, and
looked like a credentials problem rather than a missing call. These tests exist
to keep that from happening again: they assert the call, not the delivery.

Delivery itself is Expo's business and is stubbed here.
"""
import pytest
from sqlalchemy import select

from app.models.device import DeviceToken
from tests.conftest import auth_header


@pytest.fixture
def sent(monkeypatch):
    """Capture pushes instead of sending them."""
    captured = []

    async def fake_send(db, user_id, title, body, data=None):
        captured.append({"user_id": user_id, "title": title, "body": body, "data": data or {}})
        return 1

    # Patched where each caller resolves the name, not where it's defined.
    # matches imports it directly; messages goes through the shared messaging
    # service, which is where its copy of the name lives.
    monkeypatch.setattr("app.routers.matches.send_push", fake_send)
    monkeypatch.setattr("app.services.messaging.send_push", fake_send)
    return captured


@pytest.mark.asyncio
async def test_a_like_notifies_the_recipient(client, sugar_user, attractive_user, sent):
    await client.post(
        "/api/matches/like",
        headers=auth_header(sugar_user["token"]),
        json={"profile_id": attractive_user["profile"].id},
    )
    likes = [p for p in sent if p["data"].get("type") == "like"]
    assert len(likes) == 1
    assert likes[0]["user_id"] == attractive_user["user"].id


@pytest.mark.asyncio
async def test_a_like_without_a_note_does_not_reveal_who_sent_it(
    client, sugar_user, attractive_user, sent
):
    """Who liked you is what the paid tier reveals. A notification must not give
    that away for free."""
    await client.post(
        "/api/matches/like",
        headers=auth_header(sugar_user["token"]),
        json={"profile_id": attractive_user["profile"].id},
    )
    body = next(p for p in sent if p["data"].get("type") == "like")["body"]
    assert sugar_user["profile"].display_name not in body


@pytest.mark.asyncio
async def test_a_note_leads_the_notification(client, sugar_user, attractive_user, sent):
    await client.post(
        "/api/matches/like",
        headers=auth_header(sugar_user["token"]),
        json={"profile_id": attractive_user["profile"].id, "comment": "Which market, though?"},
    )
    body = next(p for p in sent if p["data"].get("type") == "like")["body"]
    assert "Which market, though?" in body


@pytest.mark.asyncio
async def test_a_mutual_like_notifies_the_match(client, sugar_user, attractive_user, sent):
    await client.post(
        "/api/matches/like",
        headers=auth_header(attractive_user["token"]),
        json={"profile_id": sugar_user["profile"].id},
    )
    sent.clear()
    await client.post(
        "/api/matches/like",
        headers=auth_header(sugar_user["token"]),
        json={"profile_id": attractive_user["profile"].id},
    )

    matches = [p for p in sent if p["data"].get("type") == "match"]
    assert len(matches) == 1
    assert matches[0]["user_id"] == attractive_user["user"].id
    assert sugar_user["profile"].display_name in matches[0]["body"]


@pytest.mark.asyncio
async def test_registering_a_device_twice_moves_it_to_the_new_owner(
    client, db, sugar_user, attractive_user
):
    """A phone that changes hands must stop delivering the previous owner's
    matches to whoever is holding it now."""
    token = "ExponentPushToken[shared-device-xxxxxxxx]"
    for who in (sugar_user, attractive_user):
        r = await client.post(
            "/api/devices/register",
            headers=auth_header(who["token"]),
            json={"token": token, "platform": "ios"},
        )
        assert r.status_code == 200

    rows = (await db.execute(select(DeviceToken).where(DeviceToken.token == token))).scalars().all()
    assert len(rows) == 1
    assert rows[0].user_id == attractive_user["user"].id


@pytest.mark.asyncio
async def test_unregister_cannot_silence_someone_else(client, db, sugar_user, attractive_user):
    token = "ExponentPushToken[victim-device-yyyyyyy]"
    await client.post(
        "/api/devices/register",
        headers=auth_header(sugar_user["token"]),
        json={"token": token, "platform": "ios"},
    )

    r = await client.post(
        "/api/devices/unregister",
        headers=auth_header(attractive_user["token"]),
        json={"token": token, "platform": "ios"},
    )
    assert r.status_code == 200  # Reported the same either way, deliberately.

    row = (await db.execute(select(DeviceToken).where(DeviceToken.token == token))).scalar_one()
    assert row.is_active is True
