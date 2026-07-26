"""Seed database with demo profiles."""
import asyncio
from datetime import date
from app.database import async_session
from app.models.user import User, UserType
from app.models.profile import (
    Profile, Gender, BodyType, Education,
    IncomeRange, LifestyleExpectation, DrinkingHabit, SmokingHabit,
)
from app.services.auth import hash_password

DEMO_PROFILES = [
    {
        "email": "james@demo.com",
        "user_type": UserType.SUGAR,
        "profile": {
            "display_name": "James",
            "bio": "Tech entrepreneur who loves traveling, fine dining, and meaningful connections. Looking for someone to share adventures with.",
            "headline": "Building the future, one venture at a time",
            "date_of_birth": date(1985, 3, 15),
            "gender": Gender.MALE,
            "seeking_gender": Gender.FEMALE,
            "city": "New York",
            "state": "NY",
            "country": "US",
            "occupation": "CEO",
            "education": Education.MASTERS,
            "height_cm": 183,
            "body_type": BodyType.ATHLETIC,
            "income_range": IncomeRange.R1M_5M,
            "drinking": DrinkingHabit.SOCIALLY,
            "smoking": SmokingHabit.NEVER,
        },
    },
    {
        "email": "sophia@demo.com",
        "user_type": UserType.ATTRACTIVE,
        "profile": {
            "display_name": "Sophia",
            "bio": "Graduate student passionate about art, yoga, and personal growth. I appreciate genuine connections and the finer things in life.",
            "headline": "Art, ambition, and authenticity",
            "date_of_birth": date(1998, 7, 22),
            "gender": Gender.FEMALE,
            "seeking_gender": Gender.MALE,
            "city": "New York",
            "state": "NY",
            "country": "US",
            "occupation": "Art Curator",
            "education": Education.MASTERS,
            "height_cm": 168,
            "body_type": BodyType.SLIM,
            "lifestyle_expectation": LifestyleExpectation.SUBSTANTIAL,
            "drinking": DrinkingHabit.SOCIALLY,
            "smoking": SmokingHabit.NEVER,
        },
    },
    {
        "email": "michael@demo.com",
        "user_type": UserType.SUGAR,
        "profile": {
            "display_name": "Michael",
            "bio": "Investment banker by day, foodie by night. I enjoy wine, sailing, and stimulating conversation.",
            "headline": "Life is short, live generously",
            "date_of_birth": date(1978, 11, 3),
            "gender": Gender.MALE,
            "seeking_gender": Gender.FEMALE,
            "city": "Los Angeles",
            "state": "CA",
            "country": "US",
            "occupation": "Investment Banker",
            "education": Education.MASTERS,
            "height_cm": 178,
            "body_type": BodyType.AVERAGE,
            "income_range": IncomeRange.R5M_10M,
            "drinking": DrinkingHabit.SOCIALLY,
            "smoking": SmokingHabit.NEVER,
        },
    },
    {
        "email": "emma@demo.com",
        "user_type": UserType.ATTRACTIVE,
        "profile": {
            "display_name": "Emma",
            "bio": "Model and aspiring fashion designer. I love exploring new cultures, rooftop sunsets, and deep late-night talks.",
            "headline": "Chasing sunsets and dreams",
            "date_of_birth": date(2000, 1, 14),
            "gender": Gender.FEMALE,
            "seeking_gender": Gender.MALE,
            "city": "Miami",
            "state": "FL",
            "country": "US",
            "occupation": "Model",
            "education": Education.BACHELORS,
            "height_cm": 173,
            "body_type": BodyType.SLIM,
            "lifestyle_expectation": LifestyleExpectation.HIGH,
            "drinking": DrinkingHabit.SOCIALLY,
            "smoking": SmokingHabit.NEVER,
        },
    },
    {
        "email": "david@demo.com",
        "user_type": UserType.SUGAR,
        "profile": {
            "display_name": "David",
            "bio": "Real estate developer with a passion for architecture and design. I believe in living well and treating others with generosity.",
            "headline": "Building dreams, brick by brick",
            "date_of_birth": date(1980, 5, 20),
            "gender": Gender.MALE,
            "seeking_gender": Gender.FEMALE,
            "city": "Chicago",
            "state": "IL",
            "country": "US",
            "occupation": "Real Estate Developer",
            "education": Education.BACHELORS,
            "height_cm": 188,
            "body_type": BodyType.ATHLETIC,
            "income_range": IncomeRange.R500K_1M,
            "drinking": DrinkingHabit.SOCIALLY,
            "smoking": SmokingHabit.NEVER,
        },
    },
    {
        "email": "olivia@demo.com",
        "user_type": UserType.ATTRACTIVE,
        "profile": {
            "display_name": "Olivia",
            "bio": "Dental hygienist who loves hiking, cooking, and cozy nights in. Looking for someone ambitious and kind.",
            "headline": "Simple girl with big dreams",
            "date_of_birth": date(1996, 9, 8),
            "gender": Gender.FEMALE,
            "seeking_gender": Gender.MALE,
            "city": "New York",
            "state": "NY",
            "country": "US",
            "occupation": "Dental Hygienist",
            "education": Education.BACHELORS,
            "height_cm": 165,
            "body_type": BodyType.CURVY,
            "lifestyle_expectation": LifestyleExpectation.MODERATE,
            "drinking": DrinkingHabit.SOCIALLY,
            "smoking": SmokingHabit.NEVER,
        },
    },
    {
        "email": "alex@demo.com",
        "user_type": UserType.SUGAR,
        "profile": {
            "display_name": "Alexander",
            "bio": "Physician and medical researcher. When I'm not at the hospital, you'll find me at jazz clubs or art galleries.",
            "headline": "Healing the world, one patient at a time",
            "date_of_birth": date(1982, 12, 1),
            "gender": Gender.MALE,
            "seeking_gender": Gender.FEMALE,
            "city": "San Francisco",
            "state": "CA",
            "country": "US",
            "occupation": "Physician",
            "education": Education.DOCTORATE,
            "height_cm": 180,
            "body_type": BodyType.AVERAGE,
            "income_range": IncomeRange.R250K_500K,
            "drinking": DrinkingHabit.SOCIALLY,
            "smoking": SmokingHabit.NEVER,
        },
    },
    {
        "email": "isabella@demo.com",
        "user_type": UserType.ATTRACTIVE,
        "profile": {
            "display_name": "Isabella",
            "bio": "Fitness trainer and wellness coach. I live for the outdoors, great food, and even better company. Life's too short for boring dates.",
            "headline": "Strong body, stronger mind",
            "date_of_birth": date(1997, 4, 18),
            "gender": Gender.FEMALE,
            "seeking_gender": Gender.MALE,
            "city": "Los Angeles",
            "state": "CA",
            "country": "US",
            "occupation": "Fitness Trainer",
            "education": Education.BACHELORS,
            "height_cm": 170,
            "body_type": BodyType.ATHLETIC,
            "lifestyle_expectation": LifestyleExpectation.SUBSTANTIAL,
            "drinking": DrinkingHabit.SOCIALLY,
            "smoking": SmokingHabit.NEVER,
        },
    },
]


async def seed():
    async with async_session() as db:
        for item in DEMO_PROFILES:
            user = User(
                email=item["email"],
                password_hash=hash_password("password123"),
                user_type=item["user_type"],
            )
            db.add(user)
            await db.flush()

            profile = Profile(user_id=user.id, **item["profile"])
            db.add(profile)

        await db.commit()
    print(f"Seeded {len(DEMO_PROFILES)} demo profiles. Password for all: password123")


if __name__ == "__main__":
    asyncio.run(seed())
