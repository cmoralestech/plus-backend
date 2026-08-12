"""Real members outrank example profiles.

Found by walking the signup path against production: a brand new member's first
page of Discover was twenty example profiles and nothing else, with every real,
likeable person on page two. Example profiles refuse likes — so the entire first
screen was people who could not be interacted with, and most members would never
scroll past it.

Seeds exist to stop the app looking empty while the first two cities fill. The
moment one outranks a real person it is doing the opposite of its job.
"""
from datetime import date

import pytest

from app.models.profile import Gender, Profile
from app.models.user import User, UserType
from app.services.auth import hash_password
from tests.conftest import auth_header


async def _plus_member(db, email: str, *, seed: bool, bio: str | None = None):
    """A PLUS member an ESTABLISHED member would see."""
    user = User(email=email, password_hash=hash_password("testpass123"), user_type=UserType.PLUS)
    db.add(user)
    await db.flush()

    profile = Profile(
        user_id=user.id,
        display_name=email.split("@")[0].title(),
        date_of_birth=date(1995, 3, 3),
        gender=Gender.FEMALE,
        seeking_gender=Gender.MALE,
        city="Miami",
        latitude=25.7617,
        longitude=-80.1918,
        is_seed=seed,
        # Seeds are the fuller profiles, which is exactly why they were winning
        # on score.
        bio=bio,
    )
    db.add(profile)
    await db.flush()
    return profile


@pytest.mark.asyncio
async def test_a_real_member_outranks_a_seed(client, db, sugar_user):
    sugar_user["profile"].latitude, sugar_user["profile"].longitude = 25.7617, -80.1918

    for i in range(8):
        await _plus_member(db, f"seed{i}@test.com", seed=True, bio="A complete and appealing profile.")
    real = await _plus_member(db, "real@test.com", seed=False)
    await db.commit()

    feed = (await client.get("/api/discover/", headers=auth_header(sugar_user["token"]))).json()
    assert feed, "the feed should not be empty"
    assert feed[0]["id"] == real.id, "a real member must come before any example profile"


@pytest.mark.asyncio
async def test_every_real_member_precedes_every_seed(client, db, sugar_user):
    """The production failure was one of ordering across a page boundary, so the
    guarantee has to hold for the whole list, not just the first slot."""
    sugar_user["profile"].latitude, sugar_user["profile"].longitude = 25.7617, -80.1918

    for i in range(6):
        await _plus_member(db, f"s{i}@test.com", seed=True, bio="Filled in nicely.")
    for i in range(3):
        await _plus_member(db, f"r{i}@test.com", seed=False)
    await db.commit()

    feed = (await client.get("/api/discover/?page_size=20", headers=auth_header(sugar_user["token"]))).json()
    flags = [p["is_seed"] for p in feed]

    assert True not in flags[: flags.count(False)], "a seed appeared above a real member"


@pytest.mark.asyncio
async def test_seeds_still_appear(client, db, sugar_user):
    """They are the reason the app doesn't look abandoned. Demoting them must
    not remove them."""
    sugar_user["profile"].latitude, sugar_user["profile"].longitude = 25.7617, -80.1918
    await _plus_member(db, "onlyseed@test.com", seed=True)
    await db.commit()

    feed = (await client.get("/api/discover/", headers=auth_header(sugar_user["token"]))).json()
    assert any(p["is_seed"] for p in feed)
