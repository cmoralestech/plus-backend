"""The photo requirement for discovery, and the visibility notice behind it.

The rule is config-gated because switching it on against photoless data empties
discovery entirely. These tests pin both states, so turning the flag on later is
a config change rather than a code change made under pressure.
"""
from datetime import date

import pytest

from app.config import settings
from app.models.profile import Gender, Photo, Profile
from app.models.user import User, UserType
from app.services.auth import hash_password
from tests.conftest import auth_header


@pytest.fixture
def require_photo(monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_PHOTO_FOR_DISCOVERY", True)


async def _candidate(db, email: str, **photo_kwargs):
    """A PLUS member an ESTABLISHED member would see in discovery.

    photo_kwargs, when given, attaches a single photo with those attributes;
    passing nothing leaves the profile photoless.
    """
    user = User(email=email, password_hash=hash_password("testpass123"), user_type=UserType.PLUS)
    db.add(user)
    await db.flush()

    profile = Profile(
        user_id=user.id,
        display_name=email.split("@")[0].title(),
        date_of_birth=date(1996, 4, 2),
        gender=Gender.FEMALE,
        city="Miami",
    )
    db.add(profile)
    await db.flush()

    if photo_kwargs:
        db.add(Photo(profile_id=profile.id, url="/api/photos/file/x.jpg", **photo_kwargs))

    await db.commit()
    return profile


async def _discovered_ids(client, token):
    r = await client.get("/api/discover/", headers=auth_header(token))
    assert r.status_code == 200
    return [p["id"] for p in r.json()]


@pytest.mark.asyncio
async def test_photoless_profile_is_hidden_when_required(client, db, sugar_user, require_photo):
    """The whole point of the rule: no photo, no listing."""
    photoless = await _candidate(db, "nophoto@test.com")
    assert photoless.id not in await _discovered_ids(client, sugar_user["token"])


@pytest.mark.asyncio
async def test_profile_with_photo_still_appears(client, db, sugar_user, require_photo):
    shown = await _candidate(db, "hasphoto@test.com", is_primary=True)
    assert shown.id in await _discovered_ids(client, sugar_user["token"])


@pytest.mark.asyncio
async def test_flagged_photo_does_not_satisfy_the_requirement(client, db, sugar_user, require_photo):
    """A photo held for moderation isn't shown, so it can't count as one."""
    held = await _candidate(db, "flagged@test.com", is_primary=True, is_flagged=True)
    assert held.id not in await _discovered_ids(client, sugar_user["token"])


@pytest.mark.asyncio
async def test_private_photo_does_not_satisfy_the_requirement(client, db, sugar_user, require_photo):
    """Discovery never renders private photos — the card would be blank."""
    private_only = await _candidate(db, "private@test.com", is_primary=True, is_private=True)
    assert private_only.id not in await _discovered_ids(client, sugar_user["token"])


@pytest.mark.asyncio
async def test_photoless_profile_appears_while_the_flag_is_off(client, db, sugar_user):
    """Current production behaviour. If this fails, the flag was switched on
    without checking whether there were photographs to show."""
    assert settings.REQUIRE_PHOTO_FOR_DISCOVERY is False
    photoless = await _candidate(db, "offflag@test.com")
    assert photoless.id in await _discovered_ids(client, sugar_user["token"])


@pytest.mark.asyncio
async def test_visibility_tells_a_photoless_member_what_to_do(client, attractive_user, require_photo):
    r = await client.get("/api/profiles/me/visibility", headers=auth_header(attractive_user["token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["visible"] is False
    assert body["reason"] == "no_photo"
    assert body["action"] == "add_photo"
    assert body["detail"]


@pytest.mark.asyncio
async def test_visibility_reports_visible_once_a_photo_exists(client, db, attractive_user, require_photo):
    db.add(Photo(profile_id=attractive_user["profile"].id, url="/api/photos/file/d.jpg", is_primary=True))
    await db.commit()

    body = (await client.get("/api/profiles/me/visibility", headers=auth_header(attractive_user["token"]))).json()
    assert body["visible"] is True
    assert body["reason"] is None


@pytest.mark.asyncio
async def test_review_outranks_missing_photo_in_the_message(client, db, attractive_user, require_photo):
    """Someone whose photo is in review shouldn't be told to add a photo — they
    already did, and re-uploading won't help."""
    db.add(Photo(profile_id=attractive_user["profile"].id, url="/api/photos/file/e.jpg", is_flagged=True))
    await db.commit()

    body = (await client.get("/api/profiles/me/visibility", headers=auth_header(attractive_user["token"]))).json()
    assert body["reason"] == "photo_in_review"
    assert body["action"] is None


@pytest.mark.asyncio
async def test_all_private_photos_gets_its_own_message(client, db, attractive_user, require_photo):
    """"Add a photo" is wrong advice for someone who has three of them."""
    db.add(Photo(profile_id=attractive_user["profile"].id, url="/api/photos/file/f.jpg", is_private=True))
    await db.commit()

    body = (await client.get("/api/profiles/me/visibility", headers=auth_header(attractive_user["token"]))).json()
    assert body["reason"] == "photos_all_private"
    assert body["action"] == "add_photo"
