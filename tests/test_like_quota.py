"""Ten likes a day, and answering one never costs.

The cap exists for the recipient, not the sender: a like from somebody who sent
two hundred that week says nothing. The free-reply rule is what stops the cap
eating its own mechanic — if answering cost a like, a member who spent theirs by
lunchtime could not reply to whoever liked them that evening, and the promise
that everyone you like can reach you would be false.
"""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.match import Like
from app.models.profile import Gender, Profile
from app.models.subscription import Subscription, SubscriptionTier
from app.models.user import User, UserType
from app.services import like_quota
from app.services.auth import hash_password
from tests.conftest import auth_header


async def _member(db, email: str, user_type: UserType, name: str) -> Profile:
    user = User(email=email, password_hash=hash_password("testpass123"), user_type=user_type)
    db.add(user)
    await db.flush()
    profile = Profile(
        user_id=user.id,
        display_name=name,
        date_of_birth=date(1990, 1, 1),
        gender=Gender.FEMALE if user_type is UserType.PLUS else Gender.MALE,
        city="Miami",
    )
    db.add(profile)
    await db.flush()
    return profile


async def _targets(db, n: int) -> list[Profile]:
    return [await _member(db, f"target{i}@test.com", UserType.PLUS, f"Target {i}") for i in range(n)]


@pytest.mark.asyncio
async def test_a_free_member_gets_ten(client, db, sugar_user):
    assert like_quota.limit_for(SubscriptionTier.FREE) == 10

    r = await client.get("/api/matches/quota", headers=auth_header(sugar_user["token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 10
    assert body["used"] == 0
    assert body["remaining"] == 10
    assert body["replies_are_free"] is True


@pytest.mark.asyncio
async def test_paid_tiers_get_more(db):
    assert like_quota.limit_for(SubscriptionTier.PLUS) > like_quota.limit_for(SubscriptionTier.FREE)
    assert like_quota.limit_for(SubscriptionTier.PLUS_PLUS) >= like_quota.limit_for(SubscriptionTier.PLUS)
    # No tier is unlimited. An unlimited tier puts the loudest inboxes back
    # exactly where the cap was meant to take them from.
    for tier, cap in like_quota.DAILY_LIMITS.items():
        assert cap < 1000, f"{tier} is effectively unlimited"


@pytest.mark.asyncio
async def test_spending_the_last_like_closes_the_feed(client, db, sugar_user):
    """The eleventh initiated like is refused."""
    me = sugar_user["profile"]
    targets = await _targets(db, 11)
    await db.commit()

    for t in targets[:10]:
        r = await client.post(
            "/api/matches/like",
            headers=auth_header(sugar_user["token"]),
            json={"profile_id": t.id},
        )
        assert r.status_code == 201, r.text

    left = (await client.get("/api/matches/quota", headers=auth_header(sugar_user["token"]))).json()
    assert left["remaining"] == 0
    assert left["resets_at"] is not None, "somebody at zero should be told when it comes back"

    refused = await client.post(
        "/api/matches/like",
        headers=auth_header(sugar_user["token"]),
        json={"profile_id": targets[10].id},
    )
    assert refused.status_code == 429
    assert "10" in refused.json()["detail"]


@pytest.mark.asyncio
async def test_answering_someone_is_free_even_at_the_cap(client, db, sugar_user):
    """The rule the whole mechanic rests on."""
    me = sugar_user["profile"]
    targets = await _targets(db, 10)
    admirer = await _member(db, "admirer@test.com", UserType.PLUS, "Admirer")

    # They liked first, so answering them is a reply rather than an approach.
    db.add(Like(from_profile_id=admirer.id, to_profile_id=me.id))
    await db.commit()

    for t in targets:
        r = await client.post(
            "/api/matches/like",
            headers=auth_header(sugar_user["token"]),
            json={"profile_id": t.id},
        )
        assert r.status_code == 201, r.text

    spent = (await client.get("/api/matches/quota", headers=auth_header(sugar_user["token"]))).json()
    assert spent["remaining"] == 0

    replied = await client.post(
        "/api/matches/like",
        headers=auth_header(sugar_user["token"]),
        json={"profile_id": admirer.id},
    )
    assert replied.status_code == 201, "a reply was refused, so somebody could not answer a like"


@pytest.mark.asyncio
async def test_a_reply_does_not_consume_quota(client, db, sugar_user):
    me = sugar_user["profile"]
    admirer = await _member(db, "admirer2@test.com", UserType.PLUS, "Admirer Two")
    db.add(Like(from_profile_id=admirer.id, to_profile_id=me.id))
    await db.commit()

    await client.post(
        "/api/matches/like",
        headers=auth_header(sugar_user["token"]),
        json={"profile_id": admirer.id},
    )

    after = (await client.get("/api/matches/quota", headers=auth_header(sugar_user["token"]))).json()
    assert after["used"] == 0, "answering somebody should not have cost a like"
    assert after["remaining"] == 10


@pytest.mark.asyncio
async def test_likes_older_than_the_window_free_up(db, sugar_user):
    """Rolling, not a midnight reset — see the module docstring for why."""
    me = sugar_user["profile"]
    targets = await _targets(db, 3)
    await db.flush()

    stale = datetime.utcnow() - timedelta(hours=25)
    for t in targets:
        db.add(Like(from_profile_id=me.id, to_profile_id=t.id, created_at=stale))
    await db.commit()

    used = await like_quota.used_in_window(db, me.id)
    assert used == 0, "likes from more than a day ago should no longer be held against them"


@pytest.mark.asyncio
async def test_a_like_inside_the_window_still_counts(db, sugar_user):
    me = sugar_user["profile"]
    targets = await _targets(db, 2)
    await db.flush()

    recent = datetime.utcnow() - timedelta(hours=3)
    for t in targets:
        db.add(Like(from_profile_id=me.id, to_profile_id=t.id, created_at=recent))
    await db.commit()

    assert await like_quota.used_in_window(db, me.id) == 2


@pytest.mark.asyncio
async def test_reciprocity_is_judged_by_who_liked_first(db, sugar_user):
    """Not by which screen called the endpoint.

    If I liked them first and they answered, my like was an approach and still
    costs. Otherwise a client could spend free likes by calling from the right
    place.
    """
    me = sugar_user["profile"]
    other = await _member(db, "other@test.com", UserType.PLUS, "Other")
    await db.flush()

    now = datetime.utcnow()
    db.add(Like(from_profile_id=me.id, to_profile_id=other.id, created_at=now - timedelta(hours=2)))
    db.add(Like(from_profile_id=other.id, to_profile_id=me.id, created_at=now - timedelta(hours=1)))
    await db.commit()

    assert await like_quota.used_in_window(db, me.id) == 1, (
        "their later reply should not retroactively make my approach free"
    )
