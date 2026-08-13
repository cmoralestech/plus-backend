"""Privacy switches do what they say.

Seven of the nine were settable from the settings page and read by nothing. A
member could turn on "hide my profile" and stay in every feed, or "private
browsing" and still appear in the other person's list of viewers. On a platform
whose whole proposition is discretion, a switch that quietly does nothing is
worse than not offering it — it is trusted.

These tests exist because that failure is invisible: the setting saves, the UI
shows it on, and nothing anywhere reports that it isn't honoured.
"""
from datetime import date, datetime

import pytest
from sqlalchemy import select

from app.models.engagement import ProfileView
from app.models.profile import Gender, Profile
from app.models.subscription import PrivacySettings
from app.models.user import User, UserType
from app.services.auth import hash_password
from tests.conftest import auth_header


async def _candidate(db, email="hidden@test.com", **prefs):
    user = User(email=email, password_hash=hash_password("testpass123"), user_type=UserType.PLUS)
    db.add(user)
    await db.flush()

    profile = Profile(
        user_id=user.id,
        display_name="Hidden",
        date_of_birth=date(1994, 2, 2),
        gender=Gender.FEMALE,
        seeking_gender=Gender.MALE,
        city="Miami",
        latitude=25.7617,
        longitude=-80.1918,
    )
    db.add(profile)
    if prefs:
        db.add(PrivacySettings(user_id=user.id, **prefs))
    await db.flush()
    return user, profile


@pytest.mark.asyncio
async def test_hide_profile_removes_you_from_discovery(client, db, sugar_user):
    sugar_user["profile"].latitude, sugar_user["profile"].longitude = 25.7617, -80.1918
    _, hidden = await _candidate(db, hide_profile=True)
    _, shown = await _candidate(db, email="visible@test.com")
    await db.commit()

    ids = [p["id"] for p in (await client.get("/api/discover/", headers=auth_header(sugar_user["token"]))).json()]
    assert shown.id in ids
    assert hidden.id not in ids, "a member who asked to be hidden was still in the feed"


@pytest.mark.asyncio
async def test_hide_from_search_removes_you_too(client, db, sugar_user):
    sugar_user["profile"].latitude, sugar_user["profile"].longitude = 25.7617, -80.1918
    _, hidden = await _candidate(db, hide_from_search=True)
    await db.commit()

    ids = [p["id"] for p in (await client.get("/api/discover/?city=Miami", headers=auth_header(sugar_user["token"]))).json()]
    assert hidden.id not in ids


@pytest.mark.asyncio
async def test_hide_online_status_is_honoured_on_a_profile(client, db, sugar_user):
    user, profile = await _candidate(db, hide_online_status=True, hide_last_seen=True)
    user.last_seen = datetime.utcnow()  # unmistakably online
    await db.commit()

    body = (await client.get(f"/api/profiles/{profile.id}", headers=auth_header(sugar_user["token"]))).json()
    assert body["is_online"] is False
    assert body["last_active"] is None


@pytest.mark.asyncio
async def test_online_status_still_shows_when_not_hidden(client, db, sugar_user):
    """The switch has to change something, so the default must be the opposite."""
    user, profile = await _candidate(db, email="open@test.com")
    user.last_seen = datetime.utcnow()
    await db.commit()

    body = (await client.get(f"/api/profiles/{profile.id}", headers=auth_header(sugar_user["token"]))).json()
    assert body["is_online"] is True


@pytest.mark.asyncio
async def test_private_browsing_records_no_view(client, db, sugar_user, attractive_user):
    db.add(PrivacySettings(user_id=sugar_user["user"].id, private_browsing=True))
    await db.commit()

    r = await client.post(
        f"/api/engagement/views/{attractive_user['profile'].id}",
        headers=auth_header(sugar_user["token"]),
    )
    assert r.status_code in (200, 201)
    assert r.json()["recorded"] is False

    views = (await db.execute(select(ProfileView))).scalars().all()
    assert views == [], "private browsing still left a trace"


@pytest.mark.asyncio
async def test_a_normal_visit_is_still_recorded(client, db, sugar_user, attractive_user):
    r = await client.post(
        f"/api/engagement/views/{attractive_user['profile'].id}",
        headers=auth_header(sugar_user["token"]),
    )
    assert r.json()["recorded"] is True
