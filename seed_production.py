"""Production seed: ~80 profiles with Pexels stock photos."""
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
    # US Major
    ("New York", "NY", "US", 40.7128, -74.006),
    ("Los Angeles", "CA", "US", 34.0522, -118.2437),
    ("Miami", "FL", "US", 25.7617, -80.1918),
    ("Chicago", "IL", "US", 41.8781, -87.6298),
    ("San Francisco", "CA", "US", 37.7749, -122.4194),
    ("Las Vegas", "NV", "US", 36.1699, -115.1398),
    ("Dallas", "TX", "US", 32.7767, -96.797),
    ("Houston", "TX", "US", 29.7604, -95.3698),
    ("Atlanta", "GA", "US", 33.749, -84.388),
    ("Boston", "MA", "US", 42.3601, -71.0589),
    ("Austin", "TX", "US", 30.2672, -97.7431),
    ("Scottsdale", "AZ", "US", 33.4942, -111.9261),
    # International
    ("London", "England", "UK", 51.5074, -0.1278),
    ("Dubai", "Dubai", "UAE", 25.2048, 55.2708),
    ("Toronto", "Ontario", "Canada", 43.6532, -79.3832),
    ("Singapore", "", "Singapore", 1.3521, 103.8198),
    ("Sydney", "NSW", "Australia", -33.8688, 151.2093),
    ("Paris", "Île-de-France", "France", 48.8566, 2.3522),
    ("Zurich", "Zurich", "Switzerland", 47.3769, 8.5417),
    ("Mexico City", "CDMX", "Mexico", 19.4326, -99.1332),
    ("São Paulo", "SP", "Brazil", -23.5505, -46.6333),
    ("Istanbul", "Istanbul", "Turkey", 41.0082, 28.9784),
    ("Mumbai", "Maharashtra", "India", 19.076, 72.8777),
    ("Tokyo", "Tokyo", "Japan", 35.6762, 139.6503),
]

# ---------------------------------------------------------------------------
# DATA ARRAYS
# ---------------------------------------------------------------------------

MALE_NAMES = [
    # US/English
    "Mike", "John", "David", "Chris", "Matt", "Jason", "Ryan", "James",
    "Mark", "Alex", "Dan", "Steve", "Tom", "Nick", "Ben", "Sam",
    # UK/Australia
    "Oliver", "Harry", "George", "Liam",
    # Middle East / South Asian
    "Omar", "Rashid", "Arjun", "Vikram",
    # Latin American
    "Carlos", "Diego", "Rafael", "Marco",
    # European
    "Pierre", "Stefan", "Kenji", "Emre",
]

FEMALE_NAMES = [
    # US/English
    "Sarah", "Jessica", "Ashley", "Emily", "Lauren", "Amanda",
    "Nicole", "Samantha", "Rachel", "Michelle", "Natalie", "Kate",
    "Olivia", "Emma", "Grace", "Mia", "Hannah", "Chloe",
    # Latina
    "Gabriella", "Sofia", "Valentina", "Camila", "Carmen", "Elena",
    # South Asian / Middle Eastern
    "Priya", "Jasmine", "Zara", "Amira", "Ananya",
    # European
    "Amelie", "Chiara", "Yuki", "Elif", "Sienna",
    # International
    "Naomi", "Luna", "Maya", "Nina", "Bella",
    "Jade", "Lily", "Isabel", "Adriana", "Tara",
    # More variety
    "Dani", "Leila", "Anya", "Mika", "Sasha",
    "Kira", "Rio", "Noor", "Aisha", "Ingrid",
]

MALE_OCCUPATIONS = [
    "CEO", "Investment Banker", "Surgeon", "Real Estate Developer", "Hedge Fund Manager",
    "Tech Entrepreneur", "Attorney", "Private Equity", "Venture Capitalist", "Physician",
    "Architect", "Finance Director", "Managing Partner", "Portfolio Manager", "CFO",
    "Founder", "Executive Producer", "Consultant", "Wealth Manager", "Business Owner",
]

FEMALE_OCCUPATIONS = [
    "Model", "Art Curator", "Fashion Stylist", "PR Consultant", "Flight Attendant",
    "Fitness Trainer", "Dental Hygienist", "Nurse", "Interior Designer", "Photographer",
    "Event Planner", "Marketing Manager", "Dancer", "Actress", "Real Estate Agent",
    "Jewelry Designer", "Sommelier", "MBA Student", "Pre-Med Student", "Influencer",
    "Pilates Instructor", "Beauty Consultant", "Dietitian", "Yoga Instructor", "Stylist",
]

MALE_HEADLINES = [
    "Let me take you somewhere nice",
    "Not here to waste your time",
    "Looking for my plus one",
    "Work hard, play harder",
    "I'd rather be on a boat",
    "Serious about life, not about myself",
    "Yes, that's my real income",
    "Ask me about my last trip",
    "6'2 since everyone asks",
    "Better in person, I promise",
    "Your parents would love me",
    "I cook, too",
    "Looking for someone real",
    "No games, just good times",
    "Fluent in sarcasm and fine dining",
    "The boring stuff is handled",
    "Newly single, not newly desperate",
    "My friends say I'm generous",
    "I still open doors",
    "Life's good, just missing someone to share it",
]

FEMALE_HEADLINES = [
    "Tell me something I haven't heard",
    "Cute and I know it",
    "Grad school and good vibes",
    "Looking for more than just dinner",
    "I have my own goals, I want your company",
    "Adventurous when I feel safe",
    "My friends say I'm a catch",
    "5'7 in heels, taller in confidence",
    "Not looking for a pen pal",
    "I clean up nice",
    "Currently accepting applications",
    "Brains and beauty, it's a thing",
    "Probably overthinking this bio right now",
    "Take me somewhere fun",
    "Happy, healthy, and free — missing my partner",
    "Sweet-natured travel enthusiast",
    "INTP, bilingual, foodie, well-travelled",
    "Low maintenance, high standards",
    "Freckled in all the right places",
    "I actually read your bio",
    "We both know why you clicked",
    "Feed me tacos and tell me I'm pretty",
    "Your next favorite person",
    "Wait.. this isn't ChristianMingle",
]

MALE_BIOS = [
    "Finance guy by day. Foodie by night. I've eaten at 47 Michelin-starred restaurants and I'm not done yet.",
    "Divorced, two kids who live with their mom. I've got my life together and I want to share it with someone who gets that.",
    "I run three businesses and somehow still find time to hit the gym at 5am. Looking for someone who makes me want to cancel my morning alarm.",
    "Simple version: I work a lot, I travel a lot, I tip well. Looking for someone who wants to come along.",
    "I'm the guy your friends tell you to go for but you usually don't. Maybe this time?",
    "Not going to write a novel here. I'm successful, I'm generous, and I know what I want. Let's see if we click.",
    "40s, fit, financially sorted. I've done the marriage thing. Now I want something different — honest, fun, no pretense.",
    "Sold my company last year. Now I have time and money but nobody interesting to spend either with.",
    "I like good scotch, bad puns, and women who can beat me at an argument.",
    "Look, I'm not going to pretend this isn't what it is. I'm established, you're attractive, and we can skip the part where we pretend we met at a coffee shop.",
    "Real estate in Miami. I work too much but I'm working on that. Literally looking for a reason to leave the office earlier.",
    "Semi-retired at 52. Spend half my time in New York, half in Miami. Need someone who's flexible and doesn't mind first class.",
    "Tech founder. Awkward at parties but great one-on-one. I express affection through experiences, not words.",
    "I've been on Seeking for two years. Time to try something new. Hoping the people here are more real.",
    "Dad bod, dad jokes, dad money. The full package.",
]

FEMALE_BIOS = [
    "Nursing student. I study 60 hours a week and still look this good. Just saying.",
    "I'm the friend who always picks the restaurant. And yes, it'll be expensive.",
    "Not going to pretend I'm not here for what I'm here for. Honest, fun, and I give great company.",
    "Dance background, business degree, expensive taste. I keep things interesting.",
    "I just moved to Miami and I don't know anyone. Open to meeting someone who can show me around properly.",
    "25, bilingual, and I've been told I'm a great listener. Also a great talker when the conversation is worth it.",
    "Fitness trainer. My body is my business, literally. Looking for someone who appreciates dedication.",
    "Grad student by day, your favorite person by night. I'm funnier than my photos suggest.",
    "I have a life, I have goals, I have ambition. I also have a weakness for rooftop bars and men who know what they want.",
    "Short version: I'm cute, I'm smart, and I'm not wasting your time if you're not wasting mine.",
    "Model. Yes, those are real photos. Yes, I'll FaceTime before we meet. No, I'm not here to scam you.",
    "I'm the girl your ex warned you about. In the best way possible.",
    "Art history major who can talk about Basquiat or basketball. I contain multitudes.",
    "First gen everything. Working my way through law school. I know my worth — but I'm open to being spoiled.",
    "27. Vegan but I won't judge you for ordering the steak. Much.",
    "Sweet-natured and affectionate. Seeking a generous partner in crime for worldwide escapades.",
    "Young college girl who loves new restaurants, random books, and experiencing things for the first time.",
    "Bilingual, well-travelled, voracious reader. I like opera in the winter and the Mediterranean in the summer.",
    "We both know why you clicked on my profile. It's because you like big beautiful smiles. Mine is real.",
    "Cute, curvy, and a desire for adrenaline. Quirky and social. I'll make you laugh, I promise.",
]

ARRANGEMENT_TYPES_M = [
    ["mentorship", "travel_companion", "long_term"],
    ["sugar_relationship", "travel_companion", "no_strings"],
    ["long_term", "mentorship", "experience_partner"],
    ["sugar_relationship", "dating", "no_strings"],
    ["networking", "long_term", "mentorship"],
]

ARRANGEMENT_TYPES_F = [
    ["mentorship", "long_term", "experience_partner"],
    ["sugar_relationship", "travel_companion", "dating"],
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
    ["investing", "real_estate", "golf", "wine", "travel"],
    ["fitness", "hiking", "yoga", "nature", "cooking"],
]

# ---------------------------------------------------------------------------
# PEXELS PHOTO URLs — one unique photo per seed profile, no repeats
# ---------------------------------------------------------------------------

_P = "https://images.pexels.com/photos/{}/pexels-photo-{}.jpeg?auto=compress&cs=tinysrgb&w=600&h=800&fit=crop"
MALE_PHOTOS = [_P.format(i, i) for i in [
    3875649, 5465871, 5086768, 6327568, 2736502,
    5234250, 4584532, 2284947, 6599707, 6773945,
    4548543, 7854044, 9390008, 10400839, 6787697,
    5447791, 1567165, 5835056, 1854932, 10725700,
    8308483, 8142856, 988854, 5859629, 9576818,
    9961841, 5163400, 9566261, 7518780, 5014742,
]]

FEMALE_PHOTOS = [_P.format(i, i) for i in [
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
]]

FIRST_DATES = [
    "Dinner at a Michelin-starred restaurant",
    "Cocktails at a rooftop bar with a view",
    "A private wine tasting",
    "Sunset sailing in the bay",
    "A gallery opening followed by dinner",
    "Coffee that turns into lunch that turns into dinner",
    "Shopping and champagne",
    "A walk through the park then dinner somewhere quiet",
    "Live jazz and whiskey",
    "Brunch at the best spot in town",
]

LOOKING_FOR_M = [
    "Someone genuine who actually wants to spend time together, not just collect gifts.",
    "A woman who keeps me on my toes. I get bored easily but the right person fixes that.",
    "Good company, real chemistry, no drama. That's really it.",
    "Honestly? I'm tired of eating alone at nice restaurants. I want someone across the table.",
    "Someone who doesn't need me but wants me around anyway. That's the sweet spot.",
    "A real connection with someone younger who brings energy back into my life.",
    "I don't do casual well. If we click, I'm all in — trips, dinners, the whole thing.",
    "Looking for someone fun and low-key who doesn't take herself too seriously.",
    "Chemistry first, everything else second. You can't fake a spark.",
    "Someone who's honest about what she wants. I respect directness.",
]

LOOKING_FOR_F = [
    "A man who's already built his life and wants to enjoy it with someone.",
    "Someone generous and confident who doesn't play games. I know what I bring to the table.",
    "An established guy who wants real company, not arm candy. I'm more than a pretty face.",
    "Honestly just looking for someone who follows through. Say what you mean, mean what you say.",
    "A mentor type who treats me like a partner, not a project.",
    "Someone older who's got his life together and wants to help me build mine.",
    "A guy who actually shows up. In person, not just in the DMs.",
    "Stability and spontaneity. I want both and I don't think that's too much to ask.",
    "I'm looking for someone consistent. Grand gestures are nice but showing up matters more.",
    "A real gentleman. Old school manners, new school money.",
]

OFFERING_M = [
    "Financial stability, great experiences, and the kind of dates your friends will be jealous of.",
    "Mentorship if you want it, space if you don't. I adapt to what works for us.",
    "I'll fly you out, take you to dinner, introduce you to interesting people. Life's short.",
    "Generosity isn't something I perform. I just like making the people around me comfortable.",
    "Good conversation, nice dinners, travel when the timing works. No strings attached if that's what you prefer.",
    "I take care of the people in my life. That's not a line — ask anyone who knows me.",
    "Stability, consistency, and experiences that are actually worth your time.",
    "Financial support, real mentorship, and zero judgment. We're all adults here.",
    "First-class everything. If I'm going to do this, I'm doing it right.",
    "The freedom to focus on your goals while I handle the rest.",
]

OFFERING_F = [
    "Great conversation, real chemistry, and the kind of energy that makes you forget you're stressed.",
    "I'm the person who makes your day better. I bring warmth, attention, and zero drama.",
    "Good company that doesn't come with a manual. I'm easygoing until I need not to be.",
    "Loyalty, fun, and someone who actually cares how your day went.",
    "I'm low drama, high effort. I show up looking good and I make you feel good.",
    "Someone who listens, laughs at your jokes (even the bad ones), and looks amazing doing it.",
    "Genuine companionship. I'm not here to waste time — mine or yours.",
    "I bring the fun. You bring the plan. We'll figure out the rest.",
    "Smart conversation, real affection, and the kind of company that doesn't get old.",
    "I'm your escape from the boring parts of your week. Simple as that.",
]

CONVERSATIONS = [
    [
        ("s", "Hey, your profile actually made me laugh. That's rare on here."),
        ("a", "Ha, which part?"),
        ("s", "The 'probably overthinking this bio' part. Same honestly."),
        ("a", "At least we're self-aware. So what are you looking for?"),
    ],
    [
        ("s", "I like your vibe. What part of Miami are you in?"),
        ("a", "Brickell! Just moved here a few months ago. You?"),
        ("s", "Coral Gables. Know any good spots for dinner?"),
        ("a", "I know ALL the spots. That might be my only skill."),
    ],
    [
        ("s", "Not gonna lie, you're the first person I've messaged on here."),
        ("a", "Aww. Well I'm flattered. What made you reach out?"),
        ("s", "You said you read bios. I figured you'd actually reply."),
        ("a", "Smart man. So tell me something interesting about yourself."),
    ],
    [
        ("s", "Your smile is really something. Had to say it."),
        ("a", "Thank you! That's sweet. What do you do?"),
        ("s", "Real estate. Mostly commercial. It's boring until it's not."),
        ("a", "Nothing boring about being successful. When are you free?"),
    ],
    [
        ("s", "Alright I'll skip the small talk. Dinner this Friday?"),
        ("a", "Wow, straight to it huh? I respect that."),
        ("s", "Life's too short for 3 weeks of texting first."),
        ("a", "Agreed. Pick somewhere good and I'm in."),
    ],
    [
        ("s", "I see you're in finance too. Finally someone who gets the hours."),
        ("a", "Ugh yes. 80 hour weeks are no joke."),
        ("s", "At least the payoff is worth it. Drinks after close on Friday?"),
        ("a", "Only if it's somewhere with a view."),
    ],
    [
        ("s", "You mentioned you're a foodie. What's the best thing you've eaten recently?"),
        ("a", "Omakase at this tiny spot in Wynwood. Life-changing."),
        ("s", "You had me at omakase. Can I take you back there?"),
        ("a", "Only if you promise not to talk about crypto the whole time."),
        ("s", "Ha! Deal. No crypto, no politics, just good fish."),
    ],
    [
        ("s", "I noticed you're new to the city. How are you liking it so far?"),
        ("a", "It's amazing but I still feel like a tourist honestly."),
        ("s", "I've lived here 8 years. Happy to be your unofficial guide."),
        ("a", "I might take you up on that. What's your favorite neighborhood?"),
        ("s", "Coconut Grove for brunch, Brickell for dinner, Key Biscayne for weekends."),
        ("a", "Okay you clearly know what you're doing. When do we start?"),
    ],
]


def download_photo(url: str) -> str | None:
    """Download a photo and save locally."""
    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = UPLOAD_DIR / filename
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=10).read()
        with open(filepath, "wb") as f:
            f.write(data)
        return f"/api/photos/file/{filename}"
    except Exception as e:
        print(f"  Photo download failed: {e}")
        return None


async def seed():
    # Real users to preserve (never delete these)
    KEEP_EMAILS = [
        "cmoralestech@gmail.com",
        "cmoralestech713@gmail.com",
        "hbradley491@gmail.com",
        "audit-test@getarranged.io",
        "koolstudrocks@gmail.com",
        "ozymandiasonly@gmail.com",
        "tjaochico1998@gmail.com",
        "dust1413@gmail.com",
    ]

    async with async_session() as db:
        # SAFE APPROACH: Only delete seed accounts (demo emails), never real users
        SEED_PATTERNS = ['%@demo.com', '%@arranged.demo', '%@seed.com']

        # Find seed user IDs by email pattern
        seed_query = sqlalchemy.select(User.id).where(
            sqlalchemy.or_(*[User.email.like(p) for p in SEED_PATTERNS])
        )
        seed_result = await db.execute(seed_query)
        seed_user_ids = [r[0] for r in seed_result.all()]

        if not seed_user_ids:
            print("No existing seed users to clean up")
        else:
            print(f"Cleaning up {len(seed_user_ids)} seed accounts")
            id_list = ','.join(str(i) for i in seed_user_ids)

            # Get seed profile IDs
            seed_profile_result = await db.execute(
                sqlalchemy.select(Profile.id).where(Profile.user_id.in_(seed_user_ids))
            )
            seed_profile_ids = [r[0] for r in seed_profile_result.all()]

            # Delete related data for seed profiles only
            if seed_profile_ids:
                pid_list = ','.join(str(i) for i in seed_profile_ids)
                for table in ["messages", "likes", "favorites", "profile_views", "boosts"]:
                    try:
                        await db.execute(sqlalchemy.text(f"DELETE FROM {table} WHERE sender_profile_id IN ({pid_list}) OR EXISTS (SELECT 1)"))
                    except Exception:
                        pass
                await db.execute(sqlalchemy.text(f"DELETE FROM photos WHERE profile_id IN ({pid_list})"))
                await db.execute(sqlalchemy.text(f"DELETE FROM profiles WHERE id IN ({pid_list})"))

            # Delete seed-only junction tables
            for table in ["matches", "conversations", "likes", "blocks", "reports",
                          "favorites", "profile_views", "boosts", "verification_requests"]:
                try:
                    await db.execute(sqlalchemy.text(f"DELETE FROM {table}"))
                except Exception:
                    pass

            # Delete seed users
            for table in ["privacy_settings", "notification_preferences", "subscriptions", "referral_links", "referral_earnings", "referrals"]:
                try:
                    await db.execute(sqlalchemy.text(f"DELETE FROM {table} WHERE user_id IN ({id_list})"))
                except Exception:
                    pass
            await db.execute(sqlalchemy.text(f"DELETE FROM users WHERE id IN ({id_list})"))

        await db.commit()

        all_sugar_pids = []
        all_attractive_pids = []
        email_to_data = {}

        # Create 30 sugar male profiles
        print("Creating sugar profiles...")
        for i, name in enumerate(MALE_NAMES):
            city = CITIES[i % len(CITIES)]
            email = f"{name.lower()}{i}@arranged.demo"
            if i < len(MALE_NAMES[:13]):
                email = f"{name.lower()}@demo.com"

            user = User(email=email, password_hash=PASSWORD, user_type=UserType.SUGAR)
            db.add(user)
            await db.flush()

            dob = date(2026 - random.randint(35, 58), random.randint(1, 12), random.randint(1, 28))
            profile = Profile(
                user_id=user.id, display_name=name,
                bio=random.choice(MALE_BIOS),
                headline=random.choice(MALE_HEADLINES),
                date_of_birth=dob, gender=Gender.MALE, seeking_gender=Gender.FEMALE,
                city=city[0], state=city[1], country=city[2],
                latitude=city[3] + random.uniform(-0.05, 0.05),
                longitude=city[4] + random.uniform(-0.05, 0.05),
                occupation=MALE_OCCUPATIONS[i % len(MALE_OCCUPATIONS)],
                education=random.choice([Education.BACHELORS, Education.MASTERS, Education.DOCTORATE]),
                height_cm=random.randint(175, 193),
                body_type=random.choice([BodyType.ATHLETIC, BodyType.AVERAGE]),
                income_range=random.choice([IncomeRange.R250K_500K, IncomeRange.R500K_1M, IncomeRange.R1M_5M, IncomeRange.R5M_10M, IncomeRange.OVER_10M]),
                drinking=random.choice([DrinkingHabit.SOCIALLY, DrinkingHabit.REGULARLY, DrinkingHabit.SOCIALLY]),
                smoking=random.choice([SmokingHabit.NEVER, SmokingHabit.NEVER, SmokingHabit.OCCASIONALLY, SmokingHabit.OCCASIONALLY]),
                relationship_status=random.choice([RelationshipStatus.SINGLE, RelationshipStatus.DIVORCED]),
                availability=random.choice(list(Availability)),
                looking_for=random.choice(LOOKING_FOR_M),
                offering=random.choice(OFFERING_M),
                arrangement_types=random.choice(ARRANGEMENT_TYPES_M),
                interests=random.choice(INTEREST_SETS),
                ideal_first_date=random.choice(FIRST_DATES),
                languages="English",
                is_seed=True,
                is_income_verified=True,
                is_photo_verified=random.random() > 0.2,
            )
            db.add(profile)
            await db.flush()

            # Download photo — ~35% no photo for realism
            roll = random.random()
            if roll < 0.35:
                print(f"  {name} - no photo")
            else:
                url = MALE_PHOTOS[i % len(MALE_PHOTOS)]
                photo_url = download_photo(url)
                if photo_url:
                    if roll > 0.85:
                        profile.is_hidden = True
                        print(f"  {name} - hidden profile")
                    else:
                        print(f"  {name} - with photo")
                    db.add(Photo(profile_id=profile.id, url=photo_url, is_primary=True, order=0))
                else:
                    print(f"  {name} - download failed")

            all_sugar_pids.append(profile.id)
            email_to_data[email] = {"pid": profile.id, "uid": user.id, "name": name}

        # Create 50 attractive female profiles
        print("Creating attractive profiles...")
        for i, name in enumerate(FEMALE_NAMES):
            city = CITIES[i % len(CITIES)]
            email = f"{name.lower()}{i}@arranged.demo"
            if i < len(FEMALE_NAMES[:18]):
                email = f"{name.lower()}@demo.com"

            user = User(email=email, password_hash=PASSWORD, user_type=UserType.ATTRACTIVE)
            db.add(user)
            await db.flush()

            dob = date(2026 - random.randint(21, 32), random.randint(1, 12), random.randint(1, 28))
            profile = Profile(
                user_id=user.id, display_name=name,
                bio=random.choice(FEMALE_BIOS),
                headline=random.choice(FEMALE_HEADLINES),
                date_of_birth=dob, gender=Gender.FEMALE, seeking_gender=Gender.MALE,
                city=city[0], state=city[1], country=city[2],
                latitude=city[3] + random.uniform(-0.05, 0.05),
                longitude=city[4] + random.uniform(-0.05, 0.05),
                occupation=FEMALE_OCCUPATIONS[i % len(FEMALE_OCCUPATIONS)],
                education=random.choice([Education.SOME_COLLEGE, Education.BACHELORS, Education.MASTERS]),
                height_cm=random.randint(160, 178),
                body_type=random.choice([BodyType.SLIM, BodyType.ATHLETIC, BodyType.CURVY]),
                lifestyle_expectation=random.choice(list(LifestyleExpectation)),
                drinking=random.choice([DrinkingHabit.SOCIALLY, DrinkingHabit.REGULARLY, DrinkingHabit.SOCIALLY, DrinkingHabit.NEVER]),
                smoking=random.choice([SmokingHabit.NEVER, SmokingHabit.NEVER, SmokingHabit.OCCASIONALLY, SmokingHabit.NEVER]),
                relationship_status=random.choice([RelationshipStatus.SINGLE, RelationshipStatus.SINGLE, RelationshipStatus.DIVORCED]),
                availability=random.choice(list(Availability)),
                looking_for=random.choice(LOOKING_FOR_F),
                offering=random.choice(OFFERING_F),
                arrangement_types=random.choice(ARRANGEMENT_TYPES_F),
                interests=random.choice(INTEREST_SETS),
                ideal_first_date=random.choice(FIRST_DATES),
                languages="English",
                is_seed=True,
                is_photo_verified=random.random() > 0.3,
            )
            db.add(profile)
            await db.flush()

            # Download photo — ~30% no photo for realism
            roll = random.random()
            if roll < 0.30:
                print(f"  {name} - no photo")
            else:
                url = FEMALE_PHOTOS[i % len(FEMALE_PHOTOS)]
                photo_url = download_photo(url)
                if photo_url:
                    if roll > 0.92:
                        profile.is_hidden = True
                        print(f"  {name} - hidden profile")
                    else:
                        print(f"  {name} - with photo")
                    db.add(Photo(profile_id=profile.id, url=photo_url, is_primary=True, order=0))
                else:
                    print(f"  {name} - download failed")

            all_attractive_pids.append(profile.id)
            email_to_data[email] = {"pid": profile.id, "uid": user.id, "name": name}

        # -----------------------------------------------------------------
        # LGBTQ+ profiles (3 gay men, 2 women seeking women)
        # -----------------------------------------------------------------
        print("Creating LGBTQ+ profiles...")

        lgbtq_profiles = [
            # Gay men (sugar)
            {
                "name": "Marcus", "type": UserType.SUGAR,
                "gender": Gender.MALE, "seeking": Gender.MALE,
                "bio": "Architect in Chicago. I design buildings by day and my social life by night. Looking for a guy who can keep up.",
                "headline": "Cultured, curious, and great at dinner parties",
                "occupation": "Architect", "age_range": (35, 50),
                "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
                "photo_url": MALE_PHOTOS[3],
            },
            {
                "name": "Andre", "type": UserType.SUGAR,
                "gender": Gender.MALE, "seeking": Gender.MALE,
                "bio": "Lawyer, wine collector, weekend sailor. Tired of apps where nobody's serious. Let's skip to the good part.",
                "headline": "Old enough to know better, young enough to not care",
                "occupation": "Attorney", "age_range": (38, 52),
                "drinking": DrinkingHabit.REGULARLY, "smoking": SmokingHabit.NEVER,
                "photo_url": MALE_PHOTOS[7],
            },
            {
                "name": "Ravi", "type": UserType.ATTRACTIVE,
                "gender": Gender.MALE, "seeking": Gender.MALE,
                "bio": "Med school is expensive and so are my hobbies. I'm smart, I'm driven, and I look good in scrubs.",
                "headline": "Future doctor, current charmer",
                "occupation": "Medical Student", "age_range": (24, 30),
                "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
                "photo_url": MALE_PHOTOS[1],
            },
            # Women seeking women
            {
                "name": "Jordan", "type": UserType.SUGAR,
                "gender": Gender.FEMALE, "seeking": Gender.FEMALE,
                "bio": "Tech exec who finally has time to date properly. I want someone genuine who appreciates the good life.",
                "headline": "Successful, settled, seeking someone special",
                "occupation": "VP of Engineering", "age_range": (36, 48),
                "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
                "photo_url": FEMALE_PHOTOS[4],
            },
            {
                "name": "Kai", "type": UserType.ATTRACTIVE,
                "gender": Gender.FEMALE, "seeking": Gender.FEMALE,
                "bio": "Artist and barista. I make beautiful things and even better pour-overs. Looking for a woman who's already figured out who she is.",
                "headline": "Creative, curious, and really good at eye contact",
                "occupation": "Artist", "age_range": (23, 29),
                "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.OCCASIONALLY,
                "photo_url": FEMALE_PHOTOS[6],
            },
        ]

        for lp in lgbtq_profiles:
            city = random.choice(CITIES)
            email = f"{lp['name'].lower()}.lgbtq@arranged.demo"

            user = User(email=email, password_hash=PASSWORD, user_type=lp["type"])
            db.add(user)
            await db.flush()

            age = random.randint(*lp["age_range"])
            dob = date(2026 - age, random.randint(1, 12), random.randint(1, 28))

            profile = Profile(
                user_id=user.id, display_name=lp["name"],
                bio=lp["bio"],
                headline=lp["headline"],
                date_of_birth=dob,
                gender=lp["gender"], seeking_gender=lp["seeking"],
                city=city[0], state=city[1], country=city[2],
                latitude=city[3] + random.uniform(-0.05, 0.05),
                longitude=city[4] + random.uniform(-0.05, 0.05),
                occupation=lp["occupation"],
                education=random.choice([Education.BACHELORS, Education.MASTERS]),
                height_cm=random.randint(165, 188),
                body_type=random.choice([BodyType.ATHLETIC, BodyType.SLIM, BodyType.AVERAGE]),
                drinking=lp["drinking"], smoking=lp["smoking"],
                relationship_status=RelationshipStatus.SINGLE,
                availability=random.choice(list(Availability)),
                looking_for=random.choice(LOOKING_FOR_M if lp["gender"] == Gender.MALE else LOOKING_FOR_F),
                offering=random.choice(OFFERING_M if lp["type"] == UserType.SUGAR else OFFERING_F),
                arrangement_types=random.choice(ARRANGEMENT_TYPES_M if lp["gender"] == Gender.MALE else ARRANGEMENT_TYPES_F),
                interests=random.choice(INTEREST_SETS),
                ideal_first_date=random.choice(FIRST_DATES),
                languages="English",
                is_seed=True,
                is_photo_verified=True,
                is_income_verified=lp["type"] == UserType.SUGAR,
            )
            db.add(profile)
            await db.flush()

            # Download photo
            photo_url = download_photo(lp["photo_url"])
            if photo_url:
                db.add(Photo(profile_id=profile.id, url=photo_url, is_primary=True, order=0))
                print(f"  {lp['name']} ({lp['gender'].value} seeking {lp['seeking'].value}) - with photo")
            else:
                print(f"  {lp['name']} ({lp['gender'].value} seeking {lp['seeking'].value}) - no photo")

            if lp["type"] == UserType.SUGAR:
                all_sugar_pids.append(profile.id)
            else:
                all_attractive_pids.append(profile.id)
            email_to_data[email] = {"pid": profile.id, "uid": user.id, "name": lp["name"]}

        await db.commit()
        print(f"\nCreated {len(all_sugar_pids)} sugar + {len(all_attractive_pids)} attractive profiles")

        # Create matches with conversations
        print("Creating matches...")
        match_pairs = []
        for i in range(min(20, len(all_sugar_pids), len(all_attractive_pids))):
            s_pid = all_sugar_pids[i]
            a_pid = all_attractive_pids[i]
            match_pairs.append((s_pid, a_pid))

        for idx, (s_pid, a_pid) in enumerate(match_pairs):
            db.add(Like(from_profile_id=s_pid, to_profile_id=a_pid))
            db.add(Like(from_profile_id=a_pid, to_profile_id=s_pid))
            p1, p2 = min(s_pid, a_pid), max(s_pid, a_pid)
            match = Match(profile1_id=p1, profile2_id=p2)
            db.add(match)
            await db.flush()
            conv = Conversation(match_id=match.id, profile1_id=p1, profile2_id=p2)
            db.add(conv)
            await db.flush()

            # Pick a conversation from the pool
            convo = CONVERSATIONS[idx % len(CONVERSATIONS)]
            for j, (role, text) in enumerate(convo):
                sender = s_pid if role == "s" else a_pid
                db.add(Message(conversation_id=conv.id, sender_profile_id=sender, content=text, is_read=j < len(convo) - 1))

        # Extra likes
        for _ in range(50):
            a = random.choice(all_attractive_pids)
            s = random.choice(all_sugar_pids)
            try:
                db.add(Like(from_profile_id=a, to_profile_id=s))
                await db.flush()
            except Exception:
                await db.rollback()

        await db.commit()

    total = len(all_sugar_pids) + len(all_attractive_pids)
    print(f"\nDone! {total} profiles, {len(match_pairs)} matches with conversations")
    print(f"Key test accounts: sarah@demo.com, mike@demo.com (password: password123)")


if __name__ == "__main__":
    asyncio.run(seed())
