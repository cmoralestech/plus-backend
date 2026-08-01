"""Seed labelled example profiles for the active markets.

100 profiles per launch city, split across both member types so Discover
(which is cross-type) has something to show either side.

Every profile is created with is_seed=True. That flag is what the UI uses to
label them "Example profile · not a real member", and what the API uses to
reject likes and messages aimed at them. A seed without that flag is
indistinguishable from a real member, so it is set unconditionally here.

Photos are generated per profile from thispersondoesnotexist.com — each request
returns a different face, so no image is reused and no real person is depicted.
Stock photo libraries fail on both counts. Roughly 20% are left without a photo,
because a market where every single profile has a perfect headshot doesn't look
like a real one.

Run:  PYTHONPATH=/app python seed_cities.py
"""
import asyncio
import random
import sys
import urllib.request
import uuid
from datetime import date
from pathlib import Path

import sqlalchemy
from sqlalchemy import select

from app.database import async_session
from app.models.profile import (
    Profile,
    Photo,
    VALID_ARRANGEMENT_TYPES,
    Gender,
    BodyType,
    Education,
    IncomeRange,
    LifestyleExpectation,
    RelationshipStatus,
)
from app.models.user import User, UserType
from app.services.auth import hash_password

# Content pools are reused from the existing seeder rather than duplicated.
from seed_500 import (
    MALE_NAMES, FEMALE_NAMES,
    MALE_OCCUPATIONS, FEMALE_OCCUPATIONS,
    MALE_HEADLINES, FEMALE_HEADLINES,
    MALE_BIOS, FEMALE_BIOS,
    LOOKING_FOR, INTEREST_SETS, LIFESTYLE_TAG_SETS,
)

PER_CITY = 100
PHOTO_SHARE = 0.8
SEED_EMAIL_DOMAIN = "example.invalid"  # reserved by RFC 2606; can never be real

CITIES = [
    {"city": "Miami", "state": "Florida", "lat": 25.7617, "lon": -80.1918},
    {"city": "Houston", "state": "Texas", "lat": 29.7604, "lon": -95.3698},
]

# Drawn from the valid set only — sugar_relationship was removed as a
# relationship type, and seeding it would reintroduce invalid data.
ARRANGEMENT_SETS = [
    ["dating", "long_term"],
    ["dating", "something_casual"],
    ["long_term", "travel_companion"],
    ["travel_companion", "experience_partner"],
    ["dating", "experience_partner", "long_term"],
    ["networking", "mentorship", "dating"],
    ["something_casual", "open_relationship"],
]

OFFERING = [
    "A full passport and the flexibility to use it.",
    "Good taste, better questions, and a standing table at my favourite place.",
    "Curiosity, patience, and a genuine interest in what you're building.",
    "Connections worth having and the discretion to go with them.",
    "Energy, warmth, and an unreasonable enthusiasm for a good plan.",
    "A point of view, and the confidence to be wrong about it occasionally.",
    "Ambition that doesn't need an audience.",
]

IDEAL_FIRST_DATE = [
    "Something with a walk in it. Dinner after, if it's going well.",
    "An exhibition neither of us knows anything about, then argue about it over wine.",
    "Coffee at first. I'd rather leave wanting more than sit through a long one.",
    "Somewhere with good food and bad acoustics, so we have to lean in.",
    "A drive out of the city with no fixed plan.",
    "Wherever you already love. I want to see you somewhere familiar.",
]

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)

UPLOAD_DIR = Path("/app/uploads") if Path("/app/uploads").exists() else Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def download_face() -> str | None:
    """One uniquely generated face. Returns a served URL, or None on failure."""
    filename = f"{uuid.uuid4().hex}.jpg"
    try:
        req = urllib.request.Request(
            "https://thispersondoesnotexist.com/random-person.jpeg",
            headers={"User-Agent": UA},
        )
        data = urllib.request.urlopen(req, timeout=20).read()
        if len(data) < 10_000:
            return None
        (UPLOAD_DIR / filename).write_bytes(data)
        return f"/api/photos/file/{filename}"
    except Exception as exc:
        print(f"  photo download failed: {exc}")
        return None


def birth_date(min_age: int, max_age: int) -> date:
    age = random.randint(min_age, max_age)
    today = date.today()
    return date(today.year - age, random.randint(1, 12), random.randint(1, 28))


async def seed() -> None:
    created = 0
    with_photo = 0

    async with async_session() as db:
        existing = (
            await db.execute(
                select(User.id).where(User.email.like(f"%@{SEED_EMAIL_DOMAIN}"))
            )
        ).all()
        if existing:
            print(f"{len(existing)} existing example accounts found — "
                  f"delete them first if you want a clean run.")
            return

        password = hash_password(uuid.uuid4().hex)

        for spec in CITIES:
            for i in range(PER_CITY):
                # Alternate member type so each side has people to discover.
                is_established = i % 2 == 0
                user_type = UserType.SUGAR if is_established else UserType.ATTRACTIVE

                # Established members skew older; both sides stay well over 18.
                if is_established:
                    male = random.random() < 0.8
                    dob = birth_date(34, 58)
                else:
                    male = random.random() < 0.25
                    dob = birth_date(23, 37)

                name = random.choice(MALE_NAMES if male else FEMALE_NAMES)
                user = User(
                    email=f"{name.lower()}.{spec['city'].lower()}.{i}@{SEED_EMAIL_DOMAIN}",
                    password_hash=password,
                    user_type=user_type,
                    is_active=True,
                    is_verified=True,
                )
                db.add(user)
                await db.flush()

                profile = Profile(
                    user_id=user.id,
                    display_name=name,
                    date_of_birth=dob,
                    gender=Gender.MALE if male else Gender.FEMALE,
                    seeking_gender=Gender.FEMALE if male else Gender.MALE,
                    city=spec["city"],
                    state=spec["state"],
                    country="United States",
                    latitude=spec["lat"] + random.uniform(-0.12, 0.12),
                    longitude=spec["lon"] + random.uniform(-0.12, 0.12),
                    occupation=random.choice(MALE_OCCUPATIONS if male else FEMALE_OCCUPATIONS),
                    headline=random.choice(MALE_HEADLINES if male else FEMALE_HEADLINES),
                    bio=random.choice(MALE_BIOS if male else FEMALE_BIOS),
                    looking_for=random.choice(LOOKING_FOR),
                    offering=random.choice(OFFERING),
                    ideal_first_date=random.choice(IDEAL_FIRST_DATE),
                    arrangement_types=random.choice(ARRANGEMENT_SETS),
                    interests=random.choice(INTEREST_SETS),
                    lifestyle_tags=random.choice(LIFESTYLE_TAG_SETS),
                    height_cm=random.randint(168, 193) if male else random.randint(155, 180),
                    body_type=random.choice(list(BodyType)),
                    education=random.choice(list(Education)),
                    relationship_status=RelationshipStatus.SINGLE,
                    income_range=random.choice(list(IncomeRange)) if is_established else None,
                    lifestyle_expectation=(
                        None if is_established else random.choice(list(LifestyleExpectation))
                    ),
                    is_photo_verified=False,
                    is_income_verified=False,
                    is_seed=True,
                )
                db.add(profile)
                await db.flush()

                if random.random() < PHOTO_SHARE:
                    url = download_face()
                    if url:
                        db.add(Photo(profile_id=profile.id, url=url, is_primary=True, order=0))
                        with_photo += 1

                created += 1
                if created % 20 == 0:
                    await db.commit()
                    print(f"  {created} created ({with_photo} with photos)")

        await db.commit()

    invalid = {t for s in ARRANGEMENT_SETS for t in s} - VALID_ARRANGEMENT_TYPES
    if invalid:
        print(f"WARNING: invalid arrangement types seeded: {invalid}")

    print(f"\nDone. {created} example profiles across "
          f"{', '.join(c['city'] for c in CITIES)}.")
    print(f"{with_photo} with a unique generated photo, {created - with_photo} without.")
    print("All flagged is_seed=True — labelled in the UI, and likes/messages are rejected.")


if __name__ == "__main__":
    if "--yes" not in sys.argv:
        print("This writes example profiles to the configured database.")
        print("Re-run with --yes to proceed.")
        sys.exit(1)
    asyncio.run(seed())
