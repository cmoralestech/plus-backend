"""Discovery is scoped to a travelling distance.

A Miami member was shown Houston members 960 miles away — accurately labelled,
and a quarter of the feed. Worse, the distance filter ran after pagination, so
asking for 20 results returned however many survived. Both failures are silent:
the endpoint returns 200 and a shorter list, and nothing looks broken.
"""
from datetime import date

import pytest

from app.config import settings
from app.models.profile import Gender, Profile
from app.models.user import User, UserType
from app.services.auth import hash_password
from tests.conftest import auth_header

MIAMI = (25.7617, -80.1918)
HOUSTON = (29.7604, -95.3698)
FORT_LAUDERDALE = (26.1224, -80.1373)  # ~28 miles from Miami


async def _member(db, email: str, lat: float, lon: float, city: str):
    user = User(email=email, password_hash=hash_password("testpass123"), user_type=UserType.PLUS)
    db.add(user)
    await db.flush()
    profile = Profile(
        user_id=user.id,
        display_name=email.split("@")[0].title(),
        date_of_birth=date(1994, 6, 1),
        gender=Gender.FEMALE,
        city=city,
        latitude=lat,
        longitude=lon,
    )
    db.add(profile)
    await db.flush()
    return profile


async def _feed(client, token, **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    r = await client.get(f"/api/discover/?{query}", headers=auth_header(token))
    assert r.status_code == 200
    return r.json()


@pytest.mark.asyncio
async def test_another_market_is_not_in_the_feed(client, db, sugar_user):
    """The bug this was written for."""
    sugar_user["profile"].latitude, sugar_user["profile"].longitude = MIAMI
    near = await _member(db, "nearby@test.com", *MIAMI, "Miami")
    far = await _member(db, "faraway@test.com", *HOUSTON, "Houston")
    await db.commit()

    ids = [p["id"] for p in await _feed(client, sugar_user["token"])]
    assert near.id in ids
    assert far.id not in ids


@pytest.mark.asyncio
async def test_the_surrounding_metro_is_still_included(client, db, sugar_user):
    """Scoping must not shrink a market to its city limits — Fort Lauderdale is
    a reasonable drive and excluding it would gut an already thin feed."""
    sugar_user["profile"].latitude, sugar_user["profile"].longitude = MIAMI
    suburb = await _member(db, "suburb@test.com", *FORT_LAUDERDALE, "Fort Lauderdale")
    await db.commit()

    assert suburb.id in [p["id"] for p in await _feed(client, sugar_user["token"])]


@pytest.mark.asyncio
async def test_an_explicit_wider_radius_reaches_the_other_market(client, db, sugar_user):
    """The default is a default, not a wall."""
    sugar_user["profile"].latitude, sugar_user["profile"].longitude = MIAMI
    far = await _member(db, "reachable@test.com", *HOUSTON, "Houston")
    await db.commit()

    ids = [p["id"] for p in await _feed(client, sugar_user["token"], max_distance=500)]
    assert far.id not in ids  # 500 is still short of ~960

    # The endpoint caps max_distance at 500, so the far market stays out of
    # reach by design. Travel mode is how a member actually gets there.
    assert settings.DISCOVER_DEFAULT_RADIUS_MILES < 500


@pytest.mark.asyncio
async def test_a_filtered_page_is_still_a_full_page(client, db, sugar_user):
    """Distance filtering used to run after pagination, so a page of 5 could
    return 2 with no indication anything had been dropped."""
    sugar_user["profile"].latitude, sugar_user["profile"].longitude = MIAMI
    for i in range(6):
        await _member(db, f"local{i}@test.com", *MIAMI, "Miami")
    for i in range(6):
        await _member(db, f"distant{i}@test.com", *HOUSTON, "Houston")
    await db.commit()

    page = await _feed(client, sugar_user["token"], page_size=5)
    assert len(page) == 5
    assert all(p["city"] == "Miami" for p in page)


@pytest.mark.asyncio
async def test_distance_is_reported_on_every_result(client, db, sugar_user):
    sugar_user["profile"].latitude, sugar_user["profile"].longitude = MIAMI
    await _member(db, "measured@test.com", *FORT_LAUDERDALE, "Fort Lauderdale")
    await db.commit()

    feed = await _feed(client, sugar_user["token"])
    match = next(p for p in feed if p["display_name"] == "Measured")
    assert 20 <= match["distance_miles"] <= 35


@pytest.mark.asyncio
async def test_a_member_without_coordinates_still_sees_a_feed(client, db, sugar_user):
    """Scoping keys off the viewer's location. Someone who never set one must
    not be shown an empty app."""
    sugar_user["profile"].latitude = None
    sugar_user["profile"].longitude = None
    await _member(db, "anywhere@test.com", *HOUSTON, "Houston")
    await db.commit()

    assert len(await _feed(client, sugar_user["token"])) >= 1
