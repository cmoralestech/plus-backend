"""Unmatching, and the places an ended match must stop working.

There was no way to leave a conversation short of blocking, which reports
somebody as a problem when you have simply lost interest. Match.is_active
existed and nothing ever set it — or read it.

Half a feature is the danger here: deactivating the match while some route still
honours the conversation would leave the other person able to keep messaging
somebody who thinks they're gone.
"""
import pytest
from sqlalchemy import select

from app.models.match import Like, Match
from tests.conftest import auth_header


async def _matched(client, db, a, b) -> int:
    """Mutual likes between a and b. Returns the conversation id."""
    await client.post(
        "/api/matches/like",
        headers=auth_header(a["token"]),
        json={"profile_id": b["profile"].id},
    )
    r = await client.post(
        "/api/matches/like",
        headers=auth_header(b["token"]),
        json={"profile_id": a["profile"].id},
    )
    assert r.status_code == 201

    convs = (await client.get("/api/messages/conversations", headers=auth_header(a["token"]))).json()
    assert convs, "a mutual like should have produced a conversation"
    return convs[0]["id"]


@pytest.mark.asyncio
async def test_unmatch_deactivates_the_match(client, db, sugar_user, attractive_user):
    await _matched(client, db, sugar_user, attractive_user)

    r = await client.delete(
        f"/api/matches/{attractive_user['profile'].id}",
        headers=auth_header(sugar_user["token"]),
    )
    assert r.status_code == 200

    match = (await db.execute(select(Match))).scalar_one()
    assert match.is_active is False


@pytest.mark.asyncio
async def test_unmatch_removes_both_likes(client, db, sugar_user, attractive_user):
    """Leaving the other like standing means one tap silently re-forms the match,
    which is not what somebody who just walked away expects."""
    await _matched(client, db, sugar_user, attractive_user)

    await client.delete(
        f"/api/matches/{attractive_user['profile'].id}",
        headers=auth_header(sugar_user["token"]),
    )

    assert (await db.execute(select(Like))).scalars().all() == []


@pytest.mark.asyncio
async def test_the_conversation_disappears_for_both(client, db, sugar_user, attractive_user):
    await _matched(client, db, sugar_user, attractive_user)
    await client.delete(
        f"/api/matches/{attractive_user['profile'].id}",
        headers=auth_header(sugar_user["token"]),
    )

    for who in (sugar_user, attractive_user):
        convs = (await client.get("/api/messages/conversations", headers=auth_header(who["token"]))).json()
        assert convs == [], "an ended match must leave neither inbox showing it"


@pytest.mark.asyncio
async def test_the_other_person_cannot_keep_messaging(client, db, sugar_user, attractive_user):
    """The half-a-feature case. They still hold the conversation id."""
    conv_id = await _matched(client, db, sugar_user, attractive_user)
    await client.delete(
        f"/api/matches/{attractive_user['profile'].id}",
        headers=auth_header(sugar_user["token"]),
    )

    r = await client.post(
        f"/api/messages/{conv_id}",
        headers=auth_header(attractive_user["token"]),
        json={"content": "Hello? Are you there?"},
    )
    assert r.status_code == 404

    r = await client.get(f"/api/messages/{conv_id}", headers=auth_header(attractive_user["token"]))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_unmatching_a_stranger_is_refused(client, sugar_user, attractive_user):
    r = await client.delete(
        f"/api/matches/{attractive_user['profile'].id}",
        headers=auth_header(sugar_user["token"]),
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_unmatching_twice_is_refused(client, db, sugar_user, attractive_user):
    await _matched(client, db, sugar_user, attractive_user)
    first = await client.delete(
        f"/api/matches/{attractive_user['profile'].id}",
        headers=auth_header(sugar_user["token"]),
    )
    assert first.status_code == 200

    second = await client.delete(
        f"/api/matches/{attractive_user['profile'].id}",
        headers=auth_header(sugar_user["token"]),
    )
    assert second.status_code == 404
