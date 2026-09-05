"""Every surface that renders another member honours their privacy settings.

Enforcement was added to discover and the profile detail endpoint first, and
five surfaces were missed — likes received, likes sent, favourites, viewers, the
conversation header and destinations all kept publishing online status and
income for members who had asked to hide both.

The failure mode is why this file exists per-surface rather than once:
profile_to_response treats absent settings as "none recorded" and therefore
fails open, so a call site nobody wired shows more than the member asked and
nothing anywhere reports it. A new endpoint that forgets should fail a test, not
leak until somebody notices.
"""
from datetime import date, datetime

import pytest

from app.models.match import Like
from app.models.profile import Gender, IncomeRange, Profile
from app.models.subscription import PrivacySettings, Subscription, SubscriptionTier
from app.models.user import User, UserType
from app.services.auth import hash_password
from tests.conftest import auth_header

HIDDEN = dict(hide_online_status=True, hide_last_seen=True, hide_income=True)


async def _private_member(db):
    """A PLUS member who has hidden their activity and income, and is online."""
    user = User(
        email="private@test.com",
        password_hash=hash_password("testpass123"),
        user_type=UserType.PLUS,
        last_seen=datetime.utcnow(),
    )
    db.add(user)
    await db.flush()

    profile = Profile(
        user_id=user.id,
        display_name="Private",
        date_of_birth=date(1993, 9, 9),
        gender=Gender.FEMALE,
        seeking_gender=Gender.MALE,
        city="Miami",
        latitude=25.7617,
        longitude=-80.1918,
        income_range=IncomeRange.R250K_500K,
    )
    db.add(profile)
    db.add(PrivacySettings(user_id=user.id, **HIDDEN))
    await db.flush()
    return user, profile


def _assert_respected(entry: dict, where: str):
    assert entry.get("is_online") is not True, f"{where} leaked online status"
    assert entry.get("last_active") in (None, ""), f"{where} leaked last seen"
    assert entry.get("income_range") in (None, ""), f"{where} leaked income"


@pytest.mark.asyncio
async def test_discover_respects_them(client, db, sugar_user):
    sugar_user["profile"].latitude, sugar_user["profile"].longitude = 25.7617, -80.1918
    _, profile = await _private_member(db)
    await db.commit()

    feed = (await client.get("/api/discover/", headers=auth_header(sugar_user["token"]))).json()
    entry = next((p for p in feed if p["id"] == profile.id), None)
    assert entry, "the member should still appear — they hid details, not themselves"
    _assert_respected(entry, "discover")


@pytest.mark.asyncio
async def test_profile_detail_respects_them(client, db, sugar_user):
    _, profile = await _private_member(db)
    await db.commit()

    body = (await client.get(f"/api/profiles/{profile.id}", headers=auth_header(sugar_user["token"]))).json()
    _assert_respected(body, "profile detail")


@pytest.mark.asyncio
async def test_likes_sent_respects_them(client, db, sugar_user):
    _, profile = await _private_member(db)
    db.add(Like(from_profile_id=sugar_user["profile"].id, to_profile_id=profile.id))
    await db.commit()

    sent = (await client.get("/api/engagement/likes-sent", headers=auth_header(sugar_user["token"]))).json()
    entry = next((p for p in sent if p["id"] == profile.id), None)
    assert entry, "the like should be listed"
    _assert_respected(entry, "likes sent")


@pytest.mark.asyncio
async def test_likes_received_respects_them(client, db, sugar_user):
    """The premium branch returns full profiles, so it is the one that can leak."""
    user, profile = await _private_member(db)
    db.add(Like(from_profile_id=profile.id, to_profile_id=sugar_user["profile"].id))
    # The fixture already created one; a second violates the unique constraint.
    sugar_user["sub"].tier = SubscriptionTier.PLUS
    sugar_user["sub"].is_active = True
    await db.commit()

    body = (await client.get("/api/engagement/likes-received", headers=auth_header(sugar_user["token"]))).json()
    if not body.get("is_premium"):
        pytest.skip("subscription fixture did not grant the premium view")
    entry = next((p for p in body["profiles"] if p["id"] == profile.id), None)
    assert entry, "the liker should be listed for a paying member"
    _assert_respected(entry, "likes received")


@pytest.mark.asyncio
async def test_favourites_respect_them(client, db, sugar_user):
    _, profile = await _private_member(db)
    await db.commit()

    r = await client.post(
        f"/api/engagement/favorites/{profile.id}", headers=auth_header(sugar_user["token"])
    )
    assert r.status_code in (200, 201)

    saved = (await client.get("/api/engagement/favorites", headers=auth_header(sugar_user["token"]))).json()
    entry = next((p for p in saved if p["id"] == profile.id), None)
    assert entry, "the saved profile should be listed"
    _assert_respected(entry, "favourites")


@pytest.mark.asyncio
async def test_withheld_photos_are_not_returned_to_a_non_match(client, db, sugar_user):
    """blur_photos_for_non_matches withholds rather than blurs — a blur is
    reversible by anyone determined enough, and the promise was that non-matches
    do not see these."""
    from app.models.profile import Photo

    user, profile = await _private_member(db)
    from sqlalchemy import select as _select

    prefs = (
        await db.execute(_select(PrivacySettings).where(PrivacySettings.user_id == user.id))
    ).scalar_one()
    prefs.blur_photos_for_non_matches = True
    db.add(Photo(profile_id=profile.id, url="/api/photos/file/x.jpg", is_primary=True))
    await db.commit()

    body = (await client.get(f"/api/profiles/{profile.id}", headers=auth_header(sugar_user["token"]))).json()
    assert body["photos"] == [], "a non-match received photos the member withheld"


@pytest.mark.asyncio
async def test_the_matches_list_respects_them(client, db, sugar_user):
    """The last call site that rendered somebody without their settings.

    It is not reachable from either client today, which is exactly why it went
    unnoticed — an endpoint nobody calls still answers anyone holding a token.
    """
    from app.models.match import Match

    _, profile = await _private_member(db)
    db.add(Match(profile1_id=sugar_user["profile"].id, profile2_id=profile.id))
    await db.commit()

    body = (await client.get("/api/matches/", headers=auth_header(sugar_user["token"]))).json()
    entry = next((m["profile"] for m in body if m["profile"]["id"] == profile.id), None)
    assert entry, "the match should be listed"
    _assert_respected(entry, "matches list")


@pytest.mark.asyncio
async def test_a_match_still_sees_photos_withheld_from_non_matches(client, db, sugar_user):
    """The trap in fixing the line above.

    blur_photos_for_non_matches keys off `viewer_is_match`, which defaults to
    False. Passing privacy without also passing viewer_is_match=True would close
    the leak and simultaneously hide someone's photographs from the one person
    who has matched with them.
    """
    from app.models.match import Match
    from app.models.profile import Photo
    from sqlalchemy import select as _select

    user, profile = await _private_member(db)
    prefs = (
        await db.execute(_select(PrivacySettings).where(PrivacySettings.user_id == user.id))
    ).scalar_one()
    prefs.blur_photos_for_non_matches = True
    db.add(Photo(profile_id=profile.id, url="/api/photos/file/match.jpg", is_primary=True))
    db.add(Match(profile1_id=sugar_user["profile"].id, profile2_id=profile.id))
    await db.commit()

    body = (await client.get("/api/matches/", headers=auth_header(sugar_user["token"]))).json()
    entry = next((m["profile"] for m in body if m["profile"]["id"] == profile.id), None)
    assert entry, "the match should be listed"
    assert entry["photos"], "a match was denied photographs they are entitled to see"
