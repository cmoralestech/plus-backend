"""Seed 500 profiles across major cities worldwide.

Photo distribution: 35% visible, 30% private (hidden), 35% no photo.
Gender split: 60% female (attractive), 40% male (sugar).
Reuses Pexels photo IDs with varied crop offsets.

Usage: python seed_500.py
"""
import asyncio
import random
import uuid
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import sqlalchemy
from app.database import async_session
from app.models.user import User, UserType
from app.models.profile import (
    Profile, Photo, Gender, BodyType, Education,
    IncomeRange, LifestyleExpectation, DrinkingHabit, SmokingHabit,
    RelationshipStatus, Availability, SexualOrientation,
)
from app.models.match import Like, Match
from app.models.message import Conversation, Message
from app.services.auth import hash_password

PASSWORD = hash_password("password123")
UPLOAD_DIR = Path("/app/uploads") if Path("/app/uploads").exists() else Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# CITY WEIGHTS: (city, state, country, lat, lon, target_count)
# ---------------------------------------------------------------------------
CITIES = [
    # US Major — 30-40 each
    ("New York", "NY", "US", 40.7128, -74.006, 40),
    ("Los Angeles", "CA", "US", 34.0522, -118.2437, 35),
    ("Miami", "FL", "US", 25.7617, -80.1918, 40),
    ("Houston", "TX", "US", 29.7604, -95.3698, 30),
    ("Chicago", "IL", "US", 41.8781, -87.6298, 30),
    ("San Francisco", "CA", "US", 37.7749, -122.4194, 25),
    ("Dallas", "TX", "US", 32.7767, -96.797, 25),
    ("Atlanta", "GA", "US", 33.749, -84.388, 25),
    ("Las Vegas", "NV", "US", 36.1699, -115.1398, 25),
    ("Austin", "TX", "US", 30.2672, -97.7431, 20),
    # US Secondary — 15-20 each
    ("Boston", "MA", "US", 42.3601, -71.0589, 15),
    ("Seattle", "WA", "US", 47.6062, -122.3321, 15),
    ("Denver", "CO", "US", 39.7392, -104.9903, 15),
    ("Nashville", "TN", "US", 36.1627, -86.7816, 15),
    ("Scottsdale", "AZ", "US", 33.4942, -111.9261, 15),
    ("Washington DC", "DC", "US", 38.9072, -77.0369, 15),
    ("San Diego", "CA", "US", 32.7157, -117.1611, 15),
    # International — 10-15 each
    ("London", "England", "UK", 51.5074, -0.1278, 15),
    ("Dubai", "Dubai", "UAE", 25.2048, 55.2708, 15),
    ("Toronto", "Ontario", "Canada", 43.6532, -79.3832, 12),
    ("Singapore", "", "Singapore", 1.3521, 103.8198, 10),
    ("Sydney", "NSW", "Australia", -33.8688, 151.2093, 10),
    ("Paris", "Île-de-France", "France", 48.8566, 2.3522, 10),
    ("Tokyo", "Tokyo", "Japan", 35.6762, 139.6503, 10),
    ("Mexico City", "CDMX", "Mexico", 19.4326, -99.1332, 10),
    ("São Paulo", "SP", "Brazil", -23.5505, -46.6333, 10),
    ("Mumbai", "Maharashtra", "India", 19.076, 72.8777, 8),
    ("Istanbul", "Istanbul", "Turkey", 41.0082, 28.9784, 8),
]

# ---------------------------------------------------------------------------
# NAMES — enough for 500 profiles
# ---------------------------------------------------------------------------
MALE_NAMES = [
    "Mike", "John", "David", "Chris", "Matt", "Jason", "Ryan", "James",
    "Mark", "Alex", "Dan", "Steve", "Tom", "Nick", "Ben", "Sam",
    "Oliver", "Harry", "George", "Liam", "Omar", "Rashid", "Arjun", "Vikram",
    "Carlos", "Diego", "Rafael", "Marco", "Pierre", "Stefan", "Kenji", "Emre",
    "Robert", "William", "Michael", "Richard", "Joseph", "Thomas", "Brian", "Kevin",
    "Eric", "Greg", "Jeff", "Derek", "Sean", "Jake", "Adam", "Tyler",
    "Josh", "Paul", "Tony", "Andrew", "Scott", "Patrick", "Douglas", "Kenneth",
    "Nathan", "Aaron", "Peter", "Bradley", "Vincent", "Russell", "Martin", "Frank",
    "Raymond", "Howard", "Gerald", "Leonard", "Donald", "Gary", "Warren", "Grant",
    "Ivan", "Hugo", "Felix", "Oscar", "Leon", "Axel", "Sven", "Klaus",
    "Ahmed", "Hassan", "Raj", "Amir", "Yusuf", "Ali", "Ravi", "Sanjay",
    "Luis", "Javier", "Sergio", "Pablo", "Miguel", "Fernando", "Alejandro", "Roberto",
]

FEMALE_NAMES = [
    "Sarah", "Jessica", "Ashley", "Emily", "Lauren", "Amanda", "Nicole", "Samantha",
    "Rachel", "Michelle", "Natalie", "Kate", "Olivia", "Emma", "Grace", "Mia",
    "Hannah", "Chloe", "Gabriella", "Sofia", "Valentina", "Camila", "Carmen", "Elena",
    "Priya", "Jasmine", "Zara", "Amira", "Ananya", "Amelie", "Chiara", "Yuki",
    "Elif", "Sienna", "Naomi", "Luna", "Maya", "Nina", "Bella", "Jade",
    "Lily", "Isabel", "Adriana", "Tara", "Dani", "Leila", "Anya", "Mika",
    "Sasha", "Kira", "Rio", "Noor", "Aisha", "Ingrid", "Stella", "Violet",
    "Ruby", "Aria", "Willow", "Ivy", "Aurora", "Clara", "Elise", "Margot",
    "Thalia", "Bianca", "Lena", "Freya", "Alina", "Diana", "Vera", "Nadia",
    "Rosa", "Marina", "Lucia", "Petra", "Simone", "Celeste", "Vivian", "Irene",
    "Tiffany", "Brittany", "Stephanie", "Christina", "Vanessa", "Maria", "Daniela", "Andrea",
    "Catalina", "Fernanda", "Mariana", "Paola", "Carolina", "Juliana", "Renata", "Larissa",
    "Sakura", "Mei", "Hana", "Rina", "Suki", "Keiko", "Yuna", "Hina",
    "Fatima", "Layla", "Sara", "Huda", "Maryam", "Rania", "Dina", "Lina",
    "Tatiana", "Natasha", "Olga", "Anastasia", "Katya", "Irina", "Svetlana", "Yelena",
]

MALE_OCCUPATIONS = [
    "CEO", "Investment Banker", "Surgeon", "Real Estate Developer", "Hedge Fund Manager",
    "Tech Entrepreneur", "Attorney", "Private Equity", "Venture Capitalist", "Physician",
    "Architect", "Finance Director", "Managing Partner", "Portfolio Manager", "CFO",
    "Founder", "Executive Producer", "Consultant", "Wealth Manager", "Business Owner",
    "Dentist", "Cardiologist", "Orthopedic Surgeon", "Plastic Surgeon", "Radiologist",
    "Software Executive", "VP of Sales", "Commercial Pilot", "Investment Manager", "Stockbroker",
]

FEMALE_OCCUPATIONS = [
    "Model", "Art Curator", "Fashion Stylist", "PR Consultant", "Flight Attendant",
    "Fitness Trainer", "Dental Hygienist", "Nurse", "Interior Designer", "Photographer",
    "Event Planner", "Marketing Manager", "Dancer", "Actress", "Real Estate Agent",
    "MBA Student", "Pre-Med Student", "Influencer", "Pilates Instructor", "Stylist",
    "Graphic Designer", "UX Designer", "Social Media Manager", "Jewelry Designer", "Sommelier",
    "Dietitian", "Yoga Instructor", "Beauty Consultant", "Travel Blogger", "Law Student",
]

MALE_HEADLINES = [
    "Let me take you somewhere nice", "Not here to waste your time",
    "Looking for my plus one", "Work hard, play harder",
    "Serious about life, not about myself", "Yes, that's my real income",
    "Better in person, I promise", "Your parents would love me",
    "I cook, too", "Looking for someone real",
    "Fluent in sarcasm and fine dining", "The boring stuff is handled",
    "My friends say I'm generous", "I still open doors",
    "Life's good, just missing someone to share it", "Ask me about my last trip",
    "6'2 since everyone asks", "Not here for pen pals",
    "Semi-retired and looking for adventure", "I tip 30%",
]

FEMALE_HEADLINES = [
    "Tell me something I haven't heard", "Cute and I know it",
    "Grad school and good vibes", "Looking for more than just dinner",
    "I have my own goals, I want your company", "Adventurous when I feel safe",
    "My friends say I'm a catch", "Not looking for a pen pal",
    "Currently accepting applications", "Brains and beauty, it's a thing",
    "Take me somewhere fun", "Low maintenance, high standards",
    "Your next favorite person", "I actually read your bio",
    "Feed me tacos and tell me I'm pretty", "Sweet-natured travel enthusiast",
    "INTP, bilingual, foodie", "Happy, healthy, and free",
    "We both know why you clicked", "I clean up nice",
]

MALE_BIOS = [
    "Finance guy by day. Foodie by night. I've eaten at 47 Michelin-starred restaurants.",
    "Divorced, two kids. I've got my life together and want to share it.",
    "I run three businesses and still find time for the gym at 5am.",
    "Simple version: I work a lot, I travel a lot, I tip well.",
    "Not going to write a novel. I'm successful, generous, and I know what I want.",
    "40s, fit, financially sorted. Now I want something different — honest and fun.",
    "Sold my company last year. Now I have time and money but nobody to spend either with.",
    "I like good scotch, bad puns, and women who can beat me at an argument.",
    "Real estate in Miami. Looking for a reason to leave the office earlier.",
    "Semi-retired at 52. Need someone flexible who doesn't mind first class.",
    "Tech founder. Awkward at parties but great one-on-one.",
    "Dad bod, dad jokes, dad money. The full package.",
    "I express affection through experiences, not words.",
    "Hoping the people here are more real than the last app.",
    "I take care of the people in my life. Ask anyone who knows me.",
]

FEMALE_BIOS = [
    "Nursing student. I study 60 hours a week and still look this good.",
    "I'm the friend who always picks the restaurant. And yes, it'll be expensive.",
    "Not going to pretend I'm not here for what I'm here for. Honest and fun.",
    "Dance background, business degree, expensive taste.",
    "Just moved here and don't know anyone. Open to meeting someone who can show me around.",
    "25, bilingual, and I've been told I'm a great listener.",
    "Fitness trainer. My body is my business, literally.",
    "Grad student by day, your favorite person by night.",
    "I have a life, goals, and ambition. Also a weakness for rooftop bars.",
    "Short version: I'm cute, I'm smart, and I'm not wasting your time.",
    "Model. Yes, those are real photos. Yes, I'll FaceTime before we meet.",
    "Art history major who can talk about Basquiat or basketball.",
    "First gen everything. Working my way through law school. I know my worth.",
    "Sweet-natured and affectionate. Seeking a generous partner in crime.",
    "Bilingual, well-travelled, voracious reader. I like opera in winter.",
]

LOOKING_FOR = [
    "Someone genuine who actually wants to spend time together.",
    "A real connection with chemistry. That's really it.",
    "Good company, real chemistry, no drama.",
    "Honestly? I'm tired of eating alone at nice restaurants.",
    "Someone who doesn't need me but wants me around anyway.",
    "Chemistry first, everything else second.",
    "Someone who's honest about what she wants.",
    "An established person who treats me like a partner, not a project.",
    "Stability and spontaneity. I want both.",
    "A real gentleman. Old school manners, new school money.",
]

ARRANGEMENT_TYPES = [
    ["mentorship", "travel_companion", "long_term"],
    ["sugar_relationship", "travel_companion", "no_strings"],
    ["long_term", "mentorship", "experience_partner"],
    ["sugar_relationship", "dating", "no_strings"],
    ["dating", "long_term", "experience_partner"],
    ["sugar_relationship", "no_strings", "travel_companion"],
    ["mentorship", "networking", "long_term"],
]

INTEREST_SETS = [
    ["travel", "fine_dining", "wine", "investing", "golf"],
    ["fitness", "travel", "nightlife", "fashion", "dancing"],
    ["art", "yoga", "photography", "reading", "cooking"],
    ["yachting", "wine", "travel", "fine_dining", "theater"],
    ["music", "concerts", "hiking", "cooking", "movies"],
    ["fashion", "travel", "spa", "shopping", "nightlife"],
    ["fitness", "hiking", "yoga", "nature", "cooking"],
]

LIFESTYLE_TAG_SETS = [
    None, None, None, None,  # Most profiles have no lifestyle tags
    ["monogamous"],
    ["enm", "open_relationship"],
    ["kink_friendly"],
    ["curious"],
    ["kink_friendly", "dom"],
    ["kink_friendly", "sub"],
    ["vanilla"],
    ["couples_friendly", "group_friendly"],
]

_P = "https://images.pexels.com/photos/{}/pexels-photo-{}.jpeg?auto=compress&cs=tinysrgb&w=600&h=800&fit=crop&crop=face&facepad={}"

MALE_PHOTO_IDS = [
    3875649, 5465871, 5086768, 6327568, 2736502,
    5234250, 4584532, 2284947, 6599707, 6773945,
    4548543, 7854044, 9390008, 10400839, 6787697,
    5447791, 1567165, 5835056, 1854932, 10725700,
    8308483, 8142856, 988854, 5859629, 9576818,
    9961841, 5163400, 9566261, 7518780, 5014742,
]

FEMALE_PHOTO_IDS = [
    4219911, 4346985, 1871340, 5587991, 8173485,
    3776445, 3228768, 4471253, 6567502, 8136799,
    7917829, 4591882, 6278520, 2555910, 9845608,
    3353573, 4826429, 2219118, 5653182, 2645435,
    3781538, 8727469, 7073245, 15485740, 2226888,
    5712106, 8986318, 2226892, 2851559, 9804803,
    5086620, 6248865, 5083914, 5083572, 5083583,
    5584054, 8373544, 13644913, 12036936, 13755878,
    8640799, 1104758, 5036161, 19574973, 13952577,
    1437224, 6134176, 8570116, 831012, 12994780,
]


def download_photo(photo_id: int, facepad: float = 2.0) -> str | None:
    url = _P.format(photo_id, photo_id, facepad)
    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = UPLOAD_DIR / filename
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=10).read()
        with open(filepath, "wb") as f:
            f.write(data)
        return f"/api/photos/file/{filename}"
    except Exception:
        return None


async def seed():
    SEED_PATTERNS = ['%@demo.com', '%@arranged.demo', '%@seed.com', '%@seed500.com']

    async with async_session() as db:
        # Clean existing seeds
        seed_query = sqlalchemy.select(User.id).where(
            sqlalchemy.or_(*[User.email.like(p) for p in SEED_PATTERNS])
        )
        seed_result = await db.execute(seed_query)
        seed_user_ids = [r[0] for r in seed_result.all()]

        if seed_user_ids:
            id_list = ','.join(str(i) for i in seed_user_ids)
            seed_profile_result = await db.execute(
                sqlalchemy.select(Profile.id).where(Profile.user_id.in_(seed_user_ids))
            )
            seed_profile_ids = [r[0] for r in seed_profile_result.all()]

            # Nuke all junction tables with TRUNCATE CASCADE
            try:
                await db.execute(sqlalchemy.text(
                    "TRUNCATE messages, conversations, matches, likes, blocks, reports, "
                    "favorites, profile_views, boosts, verification_requests CASCADE"
                ))
            except Exception as e:
                await db.rollback()
                print(f"  Warning: TRUNCATE failed, trying DELETE: {e}")
                for table in ["messages", "conversations", "matches", "likes", "blocks",
                               "reports", "favorites", "profile_views", "boosts", "verification_requests"]:
                    try:
                        await db.execute(sqlalchemy.text(f"DELETE FROM {table}"))
                    except Exception:
                        await db.rollback()

            # Delete photos and profiles for seed users
            if seed_profile_ids:
                pid_list = ','.join(str(i) for i in seed_profile_ids)
                try:
                    await db.execute(sqlalchemy.text(f"DELETE FROM photos WHERE profile_id IN ({pid_list})"))
                    await db.execute(sqlalchemy.text(f"DELETE FROM profiles WHERE id IN ({pid_list})"))
                except Exception:
                    await db.rollback()

            for table in ["privacy_settings", "notification_preferences", "subscriptions",
                          "referral_links", "referral_earnings", "referrals"]:
                try:
                    await db.execute(sqlalchemy.text(f"DELETE FROM {table} WHERE user_id IN ({id_list})"))
                except Exception:
                    await db.rollback()

            try:
                await db.execute(sqlalchemy.text(f"DELETE FROM users WHERE id IN ({id_list})"))
            except Exception:
                await db.rollback()

            print(f"Cleaned {len(seed_user_ids)} existing seed accounts")

        await db.commit()

        all_sugar_pids = []
        all_attractive_pids = []
        profile_count = 0
        photo_downloaded = 0
        photo_private = 0
        photo_none = 0

        for city_name, state, country, lat, lon, target in CITIES:
            # 40% male (sugar), 60% female (attractive)
            male_count = int(target * 0.4)
            female_count = target - male_count

            print(f"\n{city_name}: {male_count} SD + {female_count} SB = {target}")

            # Create male profiles
            for i in range(male_count):
                name = random.choice(MALE_NAMES)
                email = f"{name.lower()}{profile_count}@seed500.com"
                user = User(email=email, password_hash=PASSWORD, user_type=UserType.SUGAR)
                db.add(user)
                await db.flush()

                dob = date(2026 - random.randint(35, 58), random.randint(1, 12), random.randint(1, 28))
                profile = Profile(
                    user_id=user.id, display_name=name,
                    bio=random.choice(MALE_BIOS),
                    headline=random.choice(MALE_HEADLINES),
                    date_of_birth=dob, gender=Gender.MALE,
                    city=city_name, state=state, country=country,
                    latitude=lat + random.uniform(-0.08, 0.08),
                    longitude=lon + random.uniform(-0.08, 0.08),
                    occupation=random.choice(MALE_OCCUPATIONS),
                    education=random.choice([Education.BACHELORS, Education.MASTERS, Education.DOCTORATE]),
                    height_cm=random.randint(175, 193),
                    body_type=random.choice([BodyType.ATHLETIC, BodyType.AVERAGE]),
                    income_range=random.choice([IncomeRange.R250K_500K, IncomeRange.R500K_1M, IncomeRange.R1M_5M, IncomeRange.R5M_10M]),
                    drinking=random.choice(list(DrinkingHabit)),
                    smoking=random.choice([SmokingHabit.NEVER, SmokingHabit.NEVER, SmokingHabit.OCCASIONALLY]),
                    relationship_status=random.choice([RelationshipStatus.SINGLE, RelationshipStatus.DIVORCED]),
                    looking_for=random.choice(LOOKING_FOR),
                    arrangement_types=random.choice(ARRANGEMENT_TYPES),
                    interests=random.choice(INTEREST_SETS),
                    lifestyle_tags=random.choice(LIFESTYLE_TAG_SETS),
                    languages="English",
                    is_seed=True,
                    is_income_verified=random.random() > 0.2,
                    is_photo_verified=random.random() > 0.3,
                )
                db.add(profile)
                await db.flush()

                # Photo: 35% visible, 30% private, 35% none
                roll = random.random()
                if roll < 0.35:
                    photo_none += 1
                elif roll < 0.65:
                    # Private photo — download but mark private
                    pid = random.choice(MALE_PHOTO_IDS)
                    facepad = random.uniform(1.5, 3.0)
                    url = download_photo(pid, facepad)
                    if url:
                        db.add(Photo(profile_id=profile.id, url=url, is_primary=True, is_private=True, order=0))
                        photo_private += 1
                    else:
                        photo_none += 1
                else:
                    # Visible photo
                    pid = random.choice(MALE_PHOTO_IDS)
                    facepad = random.uniform(1.5, 3.0)
                    url = download_photo(pid, facepad)
                    if url:
                        db.add(Photo(profile_id=profile.id, url=url, is_primary=True, order=0))
                        photo_downloaded += 1
                    else:
                        photo_none += 1

                all_sugar_pids.append(profile.id)
                profile_count += 1

            # Create female profiles
            for i in range(female_count):
                name = random.choice(FEMALE_NAMES)
                email = f"{name.lower()}{profile_count}@seed500.com"
                user = User(email=email, password_hash=PASSWORD, user_type=UserType.ATTRACTIVE)
                db.add(user)
                await db.flush()

                dob = date(2026 - random.randint(21, 32), random.randint(1, 12), random.randint(1, 28))
                profile = Profile(
                    user_id=user.id, display_name=name,
                    bio=random.choice(FEMALE_BIOS),
                    headline=random.choice(FEMALE_HEADLINES),
                    date_of_birth=dob, gender=Gender.FEMALE,
                    city=city_name, state=state, country=country,
                    latitude=lat + random.uniform(-0.08, 0.08),
                    longitude=lon + random.uniform(-0.08, 0.08),
                    occupation=random.choice(FEMALE_OCCUPATIONS),
                    education=random.choice([Education.SOME_COLLEGE, Education.BACHELORS, Education.MASTERS]),
                    height_cm=random.randint(160, 178),
                    body_type=random.choice([BodyType.SLIM, BodyType.ATHLETIC, BodyType.CURVY]),
                    lifestyle_expectation=random.choice(list(LifestyleExpectation)),
                    drinking=random.choice(list(DrinkingHabit)),
                    smoking=random.choice([SmokingHabit.NEVER, SmokingHabit.NEVER, SmokingHabit.OCCASIONALLY]),
                    relationship_status=random.choice([RelationshipStatus.SINGLE, RelationshipStatus.SINGLE, RelationshipStatus.DIVORCED]),
                    looking_for=random.choice(LOOKING_FOR),
                    arrangement_types=random.choice(ARRANGEMENT_TYPES),
                    interests=random.choice(INTEREST_SETS),
                    lifestyle_tags=random.choice(LIFESTYLE_TAG_SETS),
                    languages="English",
                    is_seed=True,
                    is_photo_verified=random.random() > 0.3,
                )
                db.add(profile)
                await db.flush()

                roll = random.random()
                if roll < 0.35:
                    photo_none += 1
                elif roll < 0.65:
                    pid = random.choice(FEMALE_PHOTO_IDS)
                    facepad = random.uniform(1.5, 3.0)
                    url = download_photo(pid, facepad)
                    if url:
                        db.add(Photo(profile_id=profile.id, url=url, is_primary=True, is_private=True, order=0))
                        photo_private += 1
                    else:
                        photo_none += 1
                else:
                    pid = random.choice(FEMALE_PHOTO_IDS)
                    facepad = random.uniform(1.5, 3.0)
                    url = download_photo(pid, facepad)
                    if url:
                        db.add(Photo(profile_id=profile.id, url=url, is_primary=True, order=0))
                        photo_downloaded += 1
                    else:
                        photo_none += 1

                all_attractive_pids.append(profile.id)
                profile_count += 1

            # Commit per city to avoid huge transactions
            await db.commit()
            print(f"  Created {profile_count} total so far")

        # Create matches with conversations
        print(f"\nCreating matches...")
        match_count = min(40, len(all_sugar_pids), len(all_attractive_pids))
        shuffled_sugar = random.sample(all_sugar_pids, match_count)
        shuffled_attractive = random.sample(all_attractive_pids, match_count)

        for s_pid, a_pid in zip(shuffled_sugar, shuffled_attractive):
            db.add(Like(from_profile_id=s_pid, to_profile_id=a_pid))
            db.add(Like(from_profile_id=a_pid, to_profile_id=s_pid))
            p1, p2 = min(s_pid, a_pid), max(s_pid, a_pid)
            match = Match(profile1_id=p1, profile2_id=p2)
            db.add(match)
            await db.flush()
            conv = Conversation(match_id=match.id, profile1_id=p1, profile2_id=p2)
            db.add(conv)

        # Extra likes for realism
        for _ in range(200):
            a = random.choice(all_attractive_pids)
            s = random.choice(all_sugar_pids)
            try:
                db.add(Like(from_profile_id=a, to_profile_id=s))
                await db.flush()
            except Exception:
                await db.rollback()

        await db.commit()

        print(f"\n{'='*50}")
        print(f"DONE!")
        print(f"Total profiles: {profile_count}")
        print(f"  Sugar daddies: {len(all_sugar_pids)}")
        print(f"  Attractive: {len(all_attractive_pids)}")
        print(f"Photos: {photo_downloaded} visible, {photo_private} private, {photo_none} none")
        print(f"Matches: {match_count}")
        print(f"Extra likes: 200")
        print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(seed())
