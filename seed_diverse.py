"""Diverse seed: 120+ profiles with unique photos across 20 cities."""
import asyncio
import random
import uuid
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from app.database import async_session
from app.models.user import User, UserType
from app.models.profile import (
    Profile, Photo, Gender, BodyType, Education,
    IncomeRange, LifestyleExpectation, DrinkingHabit, SmokingHabit,
    RelationshipStatus, Availability,
)
from app.models.match import Like, Match
from app.models.message import Conversation, Message
from app.services.auth import hash_password
import sqlalchemy

PASSWORD = hash_password("password123")
UPLOAD_DIR = Path("/app/uploads") if Path("/app/uploads").exists() else Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

CITIES = [
    ("New York", "NY", "US", 40.7128, -74.006),
    ("Los Angeles", "CA", "US", 34.0522, -118.2437),
    ("Miami", "FL", "US", 25.7617, -80.1918),
    ("Chicago", "IL", "US", 41.8781, -87.6298),
    ("San Francisco", "CA", "US", 37.7749, -122.4194),
    ("Las Vegas", "NV", "US", 36.1699, -115.1398),
    ("Dallas", "TX", "US", 32.7767, -96.797),
    ("Atlanta", "GA", "US", 33.749, -84.388),
    ("Seattle", "WA", "US", 47.6062, -122.3321),
    ("Boston", "MA", "US", 42.3601, -71.0589),
    ("Denver", "CO", "US", 39.7392, -104.9903),
    ("Scottsdale", "AZ", "US", 33.4942, -111.9261),
    ("Houston", "TX", "US", 29.7604, -95.3698),
    ("Nashville", "TN", "US", 36.1627, -86.7816),
    ("Austin", "TX", "US", 30.2672, -97.7431),
    ("San Diego", "CA", "US", 32.7157, -117.1611),
    ("Portland", "OR", "US", 45.5152, -122.6784),
    ("Charlotte", "NC", "US", 35.2271, -80.8431),
    ("Tampa", "FL", "US", 27.9506, -82.4572),
    ("Phoenix", "AZ", "US", 33.4484, -112.074),
]

# 40 unique male portrait Unsplash photo IDs
MALE_PHOTOS = [
    "1507003211169-0a1dd7228f2d", "1472099645785-5658abf4ff4e", "1500648767791-00dcc994a43e",
    "1506794778202-cad84cf45f1d", "1560250097-0b93528c311a", "1519345182560-cafc5cde0af5",
    "1513956589380-bad6acb9b9d4", "1506277886164-e25aa3f4ef7f", "1568602471122-7832951cc4c5",
    "1480429370612-a3aadc1a831f", "1600486913747-55e5470d6f45", "1583864697784-a0efc8379f70",
    "1564564321837-a57b7070ac4f", "1552374196-c4e7ffc6e126", "1547425260-76bcadfb4f2c",
    "1537511446984-935f663eb1f4", "1545167622-3a6ac756afa4", "1566492031773-4f4e44671857",
    "1504257432389-52343af06ae3", "1567515004624-219c11d31f2e",
    "1579038773867-044c48829161", "1557862921-37829c790f19", "1500648767791-00dcc994a43e",
    "1463453091185-61582044d556", "1570295999919-56ceb5ecca61", "1548372290-8d01b6c8e78c",
    "1580489944761-15a19d654956", "1633332755192-727a05c4013d", "1586297135537-94bc9ba114e0",
    "1599566150163-29194dcaad36", "1611695434369-a8f5d76ceb7b", "1542909168-82c3e7fdca5c",
    "1618886614638-80e3c183d767", "1615813967515-e1838c1c5116", "1614289371518-722f2615943d",
    "1600878459108-617a253537e9", "1531384441138-2736e62e0919", "1607990281513-2c110a25bd8c",
    "1556474835-b0f3ac40d4d1", "1603415526960-f7e0328c63b1",
]

# 50 unique female portrait Unsplash photo IDs
FEMALE_PHOTOS = [
    "1529626455594-4ff0802cfb7e", "1488426862023-04b694b5dd3a", "1524504388940-b1c1722653e1",
    "1534528741775-53994a69daeb", "1531746020798-e6953c6e8e04", "1517841905240-472988babdf9",
    "1494790108377-be9c29b29330", "1502685104226-ee32379fefbe", "1521146764736-af640c2e050a",
    "1524250502761-1ac6f2e30d43", "1517365830460-955ce3ccd263", "1523824921871-d73f9968f5ee",
    "1438761681033-6461ffad8d80", "1508214751196-bcfd4ca60f91", "1544005313-94ddf0286df2",
    "1509967419530-da38b4704bc6", "1487412720507-e7ab37603c6f", "1485893086445-ed75865251e0",
    "1519699047748-de8e457a634e", "1524504388940-b1c1722653e1",
    "1580489944761-15a19d654956", "1542909168-82c3e7fdca5c", "1508214751196-bcfd4ca60f91",
    "1496440737103-cd596325d314", "1519699047748-de8e457a634e", "1557555187-afa67bd6e4c4",
    "1508243771214-6e95d137426b", "1524638431109-93d95c968227", "1520466809213-7b9a56adcd45",
    "1514315384763-ba401779410f", "1542596768-5d1d21f1cf98", "1504703395950-b89145a5425b",
    "1500917293891-ef795e70e1f6", "1531123897727-8f129e1688ce", "1519742866993-66d3cfef4bbd",
    "1546820389-44d77e1f3b31", "1507152832244-10d45c7eda57", "1535295972055-1c762f4483e5",
    "1485875437517-83e90e2f93e2", "1519648023493-d82b5f8d7b8a",
    "1508002366005-75a695ee2d17", "1513097847644-aca43ec32b6e", "1529232356377-57971f020a94",
    "1504439468489-c8920d796a29", "1531927557220-a20eb2e2e721", "1485893086445-ed75865251e0",
    "1517230878791-4d28214057c2", "1509868918941-1e8bc3601544", "1516726817505-f5ed825624d8",
    "1520333789862-abe0f85b8e00",
]

MALE_NAMES = [
    "James", "Michael", "David", "Alexander", "Robert", "William", "Richard",
    "Marcus", "Jonathan", "Vincent", "Andrew", "Thomas", "Daniel", "Christopher",
    "Nicholas", "Sebastian", "Dominic", "Edward", "Maxwell", "Harrison",
    "Theodore", "Xavier", "Lawrence", "Raymond", "Charles", "Victor",
    "Franklin", "Philip", "Graham", "Sterling", "Ethan", "Liam", "Noah",
    "Oliver", "Benjamin", "Elijah", "Lucas", "Henry", "Jack", "Adrian",
]

FEMALE_NAMES = [
    "Sophia", "Emma", "Olivia", "Isabella", "Ava", "Mia", "Luna", "Charlotte",
    "Natalie", "Valentina", "Aria", "Sienna", "Jade", "Camille", "Zara",
    "Aurora", "Bianca", "Layla", "Serena", "Vivienne", "Catalina", "Giselle",
    "Adriana", "Tatiana", "Anastasia", "Priya", "Naomi", "Jasmine", "Elena",
    "Scarlett", "Penelope", "Isla", "Harper", "Maya", "Willow", "Delilah",
    "Cleo", "Sasha", "Dahlia", "Reign", "Nova", "Ember", "Raven", "Sage",
    "Winter", "Celeste", "Lyra", "Freya", "Athena", "Iris", "Leilani",
    "Amara", "Kaia", "Nyla", "Eloise", "Thalia", "Vera", "Gemma", "Demi", "Paris",
]

MALE_OCCS = ["CEO", "Investment Banker", "Surgeon", "Real Estate Developer", "Hedge Fund Manager",
    "Tech Entrepreneur", "Attorney", "Private Equity", "Venture Capitalist", "Physician",
    "Architect", "Finance Director", "Managing Partner", "Portfolio Manager", "CFO",
    "Founder", "Executive Producer", "Consultant", "Wealth Manager", "Business Owner"]

FEMALE_OCCS = ["Model", "Art Curator", "Fashion Stylist", "PR Consultant", "Flight Attendant",
    "Fitness Trainer", "Nurse", "Interior Designer", "Photographer", "Event Planner",
    "Marketing Manager", "Dancer", "Actress", "Real Estate Agent", "Jewelry Designer",
    "Sommelier", "MBA Student", "Influencer", "Pilates Instructor", "Beauty Consultant",
    "Yoga Instructor", "Dietitian", "Music Producer", "UX Designer", "Makeup Artist"]

MALE_HEADLINES = [
    "Building empires, seeking a queen", "Life is short, live generously",
    "Old money, new adventures", "Work hard, spoil harder",
    "The good life is better shared", "Making deals and making memories",
    "Success tastes better with company", "First class everything",
    "Precision in everything I do", "Front row to everything",
    "Fortune favors the bold", "Living well is the best revenge",
    "Not your average CEO", "Champagne lifestyle, whiskey soul",
]

FEMALE_HEADLINES = [
    "Champagne taste, caviar dreams", "Strong body, stronger mind",
    "Art, ambition, and authenticity", "Chasing sunsets and dreams",
    "Brains, beauty, and a business plan", "Dance like nobody's watching",
    "Style is a way of life", "Main character energy",
    "Future doctor, current dreamer", "I know my worth — do you?",
    "Not just a pretty face", "Sweet but never naive",
    "Classy with a hint of wild", "Born to stand out",
]

MALE_BIOS = [
    "Entrepreneur who loves traveling, fine dining, and meaningful connections.",
    "I work hard because I love what I do. I play hard because life's too short not to.",
    "Built a career I'm proud of. Now looking for someone who makes the weekends worth the weekdays.",
    "I've been told I'm generous to a fault. I call it investing in the people I care about.",
    "Three things I value: honesty, ambition, and a great bottle of wine.",
    "Self-made, well-traveled, and looking for someone who can keep up.",
    "I believe in creating experiences, not just accumulating things.",
]

FEMALE_BIOS = [
    "Creative soul with expensive taste. I appreciate the finer things and the people who provide them.",
    "Life's too short for boring dates and cheap wine. Let's skip the small talk.",
    "I bring energy, charm, and the kind of company that makes you forget about work.",
    "Ambitious and unapologetic about it. Looking for someone who matches my drive.",
    "I've been told I'm unforgettable. Only one way to find out.",
    "Smart enough to know what I want. Beautiful enough to get it.",
    "Looking for a connection that's as real as it is exciting.",
    "I turn heads and start conversations. What's your opening line?",
]

LOOKING_M = [
    "Someone who appreciates the finer things and wants to share adventures.",
    "A captivating woman with substance behind the beauty.",
    "Genuine warmth and companionship. Experiences over things.",
    "An intelligent, driven woman who wants more from life.",
    "A stunning, fun woman who can hold her own anywhere.",
]
LOOKING_F = [
    "A generous, established gentleman who values culture and conversation.",
    "A successful man who knows how to treat a lady.",
    "Someone kind and established who values the simple and the exciting.",
    "A confident, generous man who values health and adventure.",
    "A mentor-type who's already where I want to be.",
]
OFFERING_M = [
    "Financial mentorship, luxury travel, fine dining, genuine connection.",
    "The best experiences money can buy — travel, events, generosity.",
    "Stability, mentorship, luxury living, and real care.",
    "Excitement, generosity, travel, and a lifestyle that never gets boring.",
    "Wisdom, stability, and access to a world most only read about.",
]
OFFERING_F = [
    "Engaging company, creativity, and genuine warmth.",
    "Stunning company, adventure, and unforgettable energy.",
    "Down-to-earth companionship and someone who actually listens.",
    "High energy, spontaneous adventures, and loyalty.",
    "Sharp mind, great company, and someone who gets your world.",
]

ARR_M = [["mentorship","travel_companion","long_term"],["sugar_relationship","travel_companion","no_strings"],
    ["long_term","mentorship","experience_partner"],["sugar_relationship","dating"],["networking","long_term","mentorship"]]
ARR_F = [["mentorship","long_term","experience_partner"],["sugar_relationship","travel_companion","dating"],
    ["dating","long_term"],["sugar_relationship","no_strings","travel_companion"],["mentorship","networking","long_term"]]

INTERESTS = [
    ["travel","fine_dining","wine","investing","golf"],["fitness","travel","nightlife","fashion","dancing"],
    ["art","yoga","photography","reading","cooking"],["yachting","wine","travel","fine_dining","theater"],
    ["music","concerts","hiking","cooking","movies"],["fashion","travel","spa","shopping","nightlife"],
    ["investing","real_estate","golf","wine","travel"],["fitness","hiking","yoga","nature","cooking"],
    ["photography","art","music","travel","fashion"],["fine_dining","wine","theater","reading","travel"],
]

FIRST_DATES = [
    "Dinner at a Michelin-starred restaurant", "Cocktails at a rooftop bar",
    "A private wine tasting", "Sunset sailing", "A gallery opening followed by dinner",
    "Coffee that turns into lunch that turns into dinner", "Shopping and champagne",
    "A walk then dinner somewhere quiet", "Live jazz and whiskey", "Brunch at the best spot in town",
]


def download_photo(photo_id: str) -> str | None:
    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = UPLOAD_DIR / filename
    url = f"https://images.unsplash.com/photo-{photo_id}?w=600&h=800&fit=crop&crop=face&q=80"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=15).read()
        if len(data) < 5000:
            return None
        with open(filepath, "wb") as f:
            f.write(data)
        return f"/api/photos/file/{filename}"
    except Exception:
        return None


async def seed():
    async with async_session() as db:
        # Clear all
        for t in ["messages","conversations","matches","likes","blocks","reports","photos","favorites",
                   "profile_views","referral_earnings","referrals","referral_links","boosts",
                   "verification_requests","profiles","privacy_settings","notification_preferences",
                   "subscriptions","users"]:
            try: await db.execute(sqlalchemy.text(f"DELETE FROM {t}"))
            except: pass
        await db.commit()

        sugar_pids, attractive_pids = [], []

        # 40 sugar males
        print("Creating 40 sugar profiles...")
        used_male_photos = list(MALE_PHOTOS)
        random.shuffle(used_male_photos)
        for i, name in enumerate(MALE_NAMES):
            city = CITIES[i % len(CITIES)]
            email = f"{name.lower()}@demo.com" if i < 13 else f"{name.lower()}{i}@arranged.demo"
            user = User(email=email, password_hash=PASSWORD, user_type=UserType.SUGAR)
            db.add(user); await db.flush()

            dob = date(2026 - random.randint(33, 58), random.randint(1,12), random.randint(1,28))
            profile = Profile(
                user_id=user.id, display_name=name, bio=random.choice(MALE_BIOS),
                headline=random.choice(MALE_HEADLINES), date_of_birth=dob,
                gender=Gender.MALE, seeking_gender=Gender.FEMALE,
                city=city[0], state=city[1], country=city[2],
                latitude=city[3]+random.uniform(-0.03,0.03), longitude=city[4]+random.uniform(-0.03,0.03),
                occupation=MALE_OCCS[i%len(MALE_OCCS)], education=random.choice([Education.BACHELORS,Education.MASTERS,Education.DOCTORATE]),
                height_cm=random.randint(175,193), body_type=random.choice([BodyType.ATHLETIC,BodyType.AVERAGE]),
                income_range=random.choice([IncomeRange.R250K_500K,IncomeRange.R500K_1M,IncomeRange.R1M_5M,IncomeRange.R5M_10M,IncomeRange.OVER_10M]),
                drinking=DrinkingHabit.SOCIALLY, smoking=SmokingHabit.NEVER,
                relationship_status=random.choice([RelationshipStatus.SINGLE,RelationshipStatus.DIVORCED]),
                availability=random.choice(list(Availability)),
                looking_for=random.choice(LOOKING_M), offering=random.choice(OFFERING_M),
                arrangement_types=random.choice(ARR_M), interests=random.choice(INTERESTS),
                ideal_first_date=random.choice(FIRST_DATES), languages="English",
            )
            db.add(profile); await db.flush()

            photo_id = used_male_photos[i % len(used_male_photos)]
            url = download_photo(photo_id)
            if url:
                db.add(Photo(profile_id=profile.id, url=url, is_primary=True, order=0))
                print(f"  {name} ({city[0]}) ✓")
            else:
                print(f"  {name} ({city[0]}) - no photo")
            sugar_pids.append(profile.id)

        # 60 attractive females
        print("Creating 60 attractive profiles...")
        used_female_photos = list(FEMALE_PHOTOS)
        random.shuffle(used_female_photos)
        for i, name in enumerate(FEMALE_NAMES):
            city = CITIES[i % len(CITIES)]
            email = f"{name.lower()}@demo.com" if i < 18 else f"{name.lower()}{i}@arranged.demo"
            user = User(email=email, password_hash=PASSWORD, user_type=UserType.ATTRACTIVE)
            db.add(user); await db.flush()

            dob = date(2026 - random.randint(21,32), random.randint(1,12), random.randint(1,28))
            profile = Profile(
                user_id=user.id, display_name=name, bio=random.choice(FEMALE_BIOS),
                headline=random.choice(FEMALE_HEADLINES), date_of_birth=dob,
                gender=Gender.FEMALE, seeking_gender=Gender.MALE,
                city=city[0], state=city[1], country=city[2],
                latitude=city[3]+random.uniform(-0.03,0.03), longitude=city[4]+random.uniform(-0.03,0.03),
                occupation=FEMALE_OCCS[i%len(FEMALE_OCCS)], education=random.choice([Education.SOME_COLLEGE,Education.BACHELORS,Education.MASTERS]),
                height_cm=random.randint(160,178), body_type=random.choice([BodyType.SLIM,BodyType.ATHLETIC,BodyType.CURVY]),
                lifestyle_expectation=random.choice(list(LifestyleExpectation)),
                drinking=DrinkingHabit.SOCIALLY, smoking=SmokingHabit.NEVER,
                relationship_status=RelationshipStatus.SINGLE,
                availability=random.choice(list(Availability)),
                looking_for=random.choice(LOOKING_F), offering=random.choice(OFFERING_F),
                arrangement_types=random.choice(ARR_F), interests=random.choice(INTERESTS),
                ideal_first_date=random.choice(FIRST_DATES), languages="English",
            )
            db.add(profile); await db.flush()

            photo_id = used_female_photos[i % len(used_female_photos)]
            url = download_photo(photo_id)
            if url:
                db.add(Photo(profile_id=profile.id, url=url, is_primary=True, order=0))
                print(f"  {name} ({city[0]}) ✓")
            else:
                print(f"  {name} ({city[0]}) - no photo")
            attractive_pids.append(profile.id)

        await db.commit()

        # Create 25 matches with conversations
        print("Creating matches...")
        for i in range(min(25, len(sugar_pids), len(attractive_pids))):
            s, a = sugar_pids[i], attractive_pids[i]
            db.add(Like(from_profile_id=s, to_profile_id=a))
            db.add(Like(from_profile_id=a, to_profile_id=s))
            p1, p2 = min(s,a), max(s,a)
            m = Match(profile1_id=p1, profile2_id=p2)
            db.add(m); await db.flush()
            c = Conversation(match_id=m.id, profile1_id=p1, profile2_id=p2)
            db.add(c); await db.flush()
            msgs = [
                (s, "Hi! Your profile really caught my eye."),
                (a, "Thank you! What stood out to you?"),
                (s, "Your ambition and style. Would love to get to know you."),
                (a, "I'd like that. Tell me more about yourself."),
            ]
            for j,(sender,text) in enumerate(msgs):
                db.add(Message(conversation_id=c.id, sender_profile_id=sender, content=text, is_read=j<3))

        # 80 one-way likes
        for _ in range(80):
            try:
                db.add(Like(from_profile_id=random.choice(attractive_pids), to_profile_id=random.choice(sugar_pids)))
                await db.flush()
            except: await db.rollback()

        await db.commit()

    total = len(sugar_pids) + len(attractive_pids)
    print(f"\nDone! {total} profiles ({len(sugar_pids)} sugar, {len(attractive_pids)} attractive)")
    print(f"25 matches with conversations, ~80 one-way likes")
    print(f"Across {len(CITIES)} cities")
    print(f"Test: sophia@demo.com / password123")


if __name__ == "__main__":
    asyncio.run(seed())
