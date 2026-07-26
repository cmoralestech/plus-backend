"""Large seed: 50+ profiles, matches, conversations, messages."""
import asyncio
import random
from datetime import date, datetime, timedelta
from app.database import async_session
from app.models.user import User, UserType
from app.models.profile import (
    Profile, Gender, BodyType, Education,
    IncomeRange, LifestyleExpectation, DrinkingHabit, SmokingHabit,
    RelationshipStatus, Availability,
)
from app.models.match import Like, Match
from app.models.message import Conversation, Message
from app.services.auth import hash_password
import sqlalchemy

PASSWORD = hash_password("password123")

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
    ("London", None, "UK", 51.5074, -0.1278),
    ("Paris", None, "FR", 48.8566, 2.3522),
    ("Dubai", None, "AE", 25.2048, 55.2708),
]

SUGAR_PROFILES = [
    {"name": "James", "age": 41, "occ": "CEO", "edu": Education.MASTERS, "income": IncomeRange.R1M_5M,
     "bio": "Tech entrepreneur who loves traveling, fine dining, and meaningful connections.",
     "headline": "Building the future, one venture at a time",
     "looking": "Someone who appreciates the finer things and wants to share adventures.",
     "offering": "Financial mentorship, luxury travel, fine dining experiences.",
     "arrangement": ["mentorship", "travel_companion", "long_term"], "interests": ["travel", "fine_dining", "wine", "investing"]},
    {"name": "Michael", "age": 47, "occ": "Investment Banker", "edu": Education.MASTERS, "income": IncomeRange.R5M_10M,
     "bio": "Investment banker by day, foodie by night. Wine, sailing, conversation.",
     "headline": "Life is short, live generously",
     "looking": "A captivating woman with substance behind the beauty.",
     "offering": "The best experiences money can buy — travel, events, generosity.",
     "arrangement": ["sugar_relationship", "travel_companion"], "interests": ["yachting", "wine", "fine_dining", "travel"]},
    {"name": "David", "age": 46, "occ": "Real Estate Developer", "edu": Education.BACHELORS, "income": IncomeRange.R500K_1M,
     "bio": "Real estate developer with a passion for architecture and design.",
     "headline": "Building dreams, brick by brick",
     "looking": "An intelligent, driven woman who wants more from life.",
     "offering": "Stability, mentorship, luxury living.",
     "arrangement": ["mentorship", "long_term", "networking"], "interests": ["real_estate", "fine_dining", "travel", "art"]},
    {"name": "Alexander", "age": 43, "occ": "Physician", "edu": Education.DOCTORATE, "income": IncomeRange.R250K_500K,
     "bio": "Physician and medical researcher. Jazz clubs and art galleries.",
     "headline": "Healing the world, one patient at a time",
     "looking": "A curious, cultured woman who loves learning.",
     "offering": "Intellectual stimulation, financial security, worldwide travel.",
     "arrangement": ["mentorship", "long_term"], "interests": ["travel", "reading", "music", "theater"]},
    {"name": "Robert", "age": 51, "occ": "Private Equity Partner", "edu": Education.MASTERS, "income": IncomeRange.OVER_10M,
     "bio": "Private equity partner. Weekdays in the boardroom, weekends on the yacht.",
     "headline": "Making deals and making memories",
     "looking": "A stunning, intelligent woman for charity galas and beach getaways.",
     "offering": "An extraordinary lifestyle — travel, gifts, financial freedom.",
     "arrangement": ["sugar_relationship", "travel_companion", "no_strings"], "interests": ["yachting", "travel", "fine_dining", "fitness"]},
    {"name": "William", "age": 54, "occ": "Angel Investor", "edu": Education.DOCTORATE, "income": IncomeRange.R5M_10M,
     "bio": "Attorney turned angel investor. Comfortable life, want someone to enjoy it with.",
     "headline": "Old money, new adventures",
     "looking": "Genuine warmth and companionship. Experiences over things.",
     "offering": "Wisdom, stability, generosity, access to a different world.",
     "arrangement": ["long_term", "mentorship", "experience_partner"], "interests": ["art", "theater", "wine", "reading"]},
    {"name": "Richard", "age": 42, "occ": "Tech Entrepreneur", "edu": Education.BACHELORS, "income": IncomeRange.R1M_5M,
     "bio": "Serial entrepreneur in fintech. Three exits, zero regrets.",
     "headline": "Life's too short for mediocre anything",
     "looking": "A spontaneous, fun-loving woman. First-class flights on a Tuesday.",
     "offering": "Excitement, generosity, travel, never boring.",
     "arrangement": ["sugar_relationship", "travel_companion", "short_term"], "interests": ["travel", "nightlife", "cars", "fitness"]},
    {"name": "Marcus", "age": 38, "occ": "Hedge Fund Manager", "edu": Education.MASTERS, "income": IncomeRange.R5M_10M,
     "bio": "Numbers by day, Negronis by night. Looking for someone to spoil.",
     "headline": "Work hard, play harder",
     "looking": "Ambition meets beauty. Someone who can keep up.",
     "offering": "Black card lifestyle. No limits, no drama.",
     "arrangement": ["sugar_relationship", "no_strings", "travel_companion"], "interests": ["fitness", "nightlife", "travel", "wine"]},
    {"name": "Jonathan", "age": 49, "occ": "Surgeon", "edu": Education.DOCTORATE, "income": IncomeRange.R500K_1M,
     "bio": "Cardiothoracic surgeon. Steady hands, generous heart.",
     "headline": "Precision in everything I do",
     "looking": "Someone patient and genuine. My schedule is demanding but I make up for it.",
     "offering": "Security, fine dining, weekend getaways, real connection.",
     "arrangement": ["long_term", "dating", "experience_partner"], "interests": ["cooking", "wine", "golf", "travel"]},
    {"name": "Vincent", "age": 44, "occ": "Luxury Real Estate", "edu": Education.BACHELORS, "income": IncomeRange.R1M_5M,
     "bio": "I sell penthouses. I also live in one. Join me for the view.",
     "headline": "The penthouse life",
     "looking": "Class, beauty, intelligence. In that order.",
     "offering": "Penthouse living, VIP access, a man who knows what he wants.",
     "arrangement": ["sugar_relationship", "dating", "no_strings"], "interests": ["real_estate", "nightlife", "cars", "fashion"]},
    {"name": "Andrew", "age": 36, "occ": "Crypto Founder", "edu": Education.BACHELORS, "income": IncomeRange.R1M_5M,
     "bio": "Built a protocol, now building a lifestyle. Decentralized everything except my dating life.",
     "headline": "Web3 money, real world taste",
     "looking": "Someone who doesn't know what a blockchain is. Seriously.",
     "offering": "Adventure, spontaneity, generosity, private flights.",
     "arrangement": ["dating", "travel_companion", "sugar_relationship"], "interests": ["tech", "travel", "fitness", "concerts"]},
    {"name": "Thomas", "age": 52, "occ": "Shipping Magnate", "edu": Education.MASTERS, "income": IncomeRange.OVER_10M,
     "bio": "Third generation shipping. Mediterranean summers, Manhattan winters.",
     "headline": "Old world charm",
     "looking": "Elegance, culture, someone comfortable at a state dinner or a beach bar.",
     "offering": "Yacht, homes in 4 countries, complete financial freedom.",
     "arrangement": ["long_term", "travel_companion", "sugar_relationship"], "interests": ["yachting", "art", "wine", "travel"]},
    {"name": "Daniel", "age": 40, "occ": "Media Executive", "edu": Education.MASTERS, "income": IncomeRange.R500K_1M,
     "bio": "Run a media company. Always at premieres, openings, and after-parties.",
     "headline": "Front row to everything",
     "looking": "My plus-one. Someone who turns heads and holds conversations.",
     "offering": "Red carpet access, dinners that make Instagram jealous.",
     "arrangement": ["dating", "networking", "experience_partner"], "interests": ["movies", "theater", "fashion", "nightlife"]},
]

ATTRACTIVE_PROFILES = [
    {"name": "Sophia", "age": 27, "occ": "Art Curator", "edu": Education.MASTERS, "lifestyle": LifestyleExpectation.SUBSTANTIAL,
     "bio": "Graduate student passionate about art, yoga, and personal growth.",
     "headline": "Art, ambition, and authenticity",
     "looking": "A generous, established gentleman who values culture and deep conversations.",
     "offering": "Engaging company, a creative perspective, genuine warmth.",
     "arrangement": ["mentorship", "long_term", "experience_partner"], "interests": ["art", "yoga", "fine_dining", "travel"]},
    {"name": "Emma", "age": 26, "occ": "Model", "edu": Education.BACHELORS, "lifestyle": LifestyleExpectation.HIGH,
     "bio": "Model and aspiring fashion designer. New cultures, rooftop sunsets.",
     "headline": "Chasing sunsets and dreams",
     "looking": "A successful man who knows how to treat a lady.",
     "offering": "Stunning company, adventure, unforgettable energy.",
     "arrangement": ["sugar_relationship", "travel_companion", "dating"], "interests": ["fashion", "travel", "fitness", "nightlife"]},
    {"name": "Olivia", "age": 29, "occ": "Dental Hygienist", "edu": Education.BACHELORS, "lifestyle": LifestyleExpectation.MODERATE,
     "bio": "Dental hygienist who loves hiking, cooking, and cozy nights in.",
     "headline": "Simple girl with big dreams",
     "looking": "Someone kind and established who values simple pleasures.",
     "offering": "Down-to-earth companionship, great cooking, someone who listens.",
     "arrangement": ["dating", "long_term", "experience_partner"], "interests": ["cooking", "hiking", "yoga", "reading"]},
    {"name": "Isabella", "age": 28, "occ": "Fitness Trainer", "edu": Education.BACHELORS, "lifestyle": LifestyleExpectation.SUBSTANTIAL,
     "bio": "Fitness trainer and wellness coach. Outdoors, great food, better company.",
     "headline": "Strong body, stronger mind",
     "looking": "A confident, generous man who values health and adventure.",
     "offering": "High energy, fitness companionship, spontaneous adventures.",
     "arrangement": ["dating", "travel_companion", "sugar_relationship"], "interests": ["fitness", "hiking", "travel", "cooking"]},
    {"name": "Ava", "age": 26, "occ": "PR Consultant", "edu": Education.BACHELORS, "lifestyle": LifestyleExpectation.HIGH,
     "bio": "PR consultant by day, socialite by night. Every rooftop bar in the city.",
     "headline": "Champagne taste, caviar dreams",
     "looking": "Someone powerful and decisive who takes charge.",
     "offering": "The perfect plus-one. Charming, connected, camera-ready.",
     "arrangement": ["sugar_relationship", "networking", "no_strings"], "interests": ["nightlife", "fashion", "fine_dining", "travel"]},
    {"name": "Mia", "age": 31, "occ": "Pediatric Nurse", "edu": Education.BACHELORS, "lifestyle": LifestyleExpectation.MODERATE,
     "bio": "Pediatric nurse with a huge heart. Saving tiny humans by day.",
     "headline": "Nurse by day, dreamer always",
     "looking": "A kind, generous soul who wants to explore the world. No games.",
     "offering": "Genuine care, loyalty, great conversation.",
     "arrangement": ["dating", "long_term", "travel_companion"], "interests": ["travel", "cooking", "yoga", "movies"]},
    {"name": "Luna", "age": 24, "occ": "Dancer / Choreographer", "edu": Education.SOME_COLLEGE, "lifestyle": LifestyleExpectation.SUBSTANTIAL,
     "bio": "Professional dancer. Passion and grace, on and off the stage.",
     "headline": "Dance like nobody's watching",
     "looking": "A generous gentleman who appreciates art and energy.",
     "offering": "Unforgettable company, spontaneity, every night feels like an event.",
     "arrangement": ["sugar_relationship", "experience_partner", "short_term"], "interests": ["dancing", "fitness", "nightlife", "music"]},
    {"name": "Charlotte", "age": 28, "occ": "MBA Student", "edu": Education.MASTERS, "lifestyle": LifestyleExpectation.SUBSTANTIAL,
     "bio": "MBA student at Wharton. Building my future, enjoying the present.",
     "headline": "Brains, beauty, and a business plan",
     "looking": "A mentor-type who's already where I want to be.",
     "offering": "Sharp mind, great company, someone who gets your business talk.",
     "arrangement": ["mentorship", "networking", "long_term"], "interests": ["investing", "fine_dining", "travel", "reading"]},
    {"name": "Natalie", "age": 29, "occ": "Flight Attendant", "edu": Education.BACHELORS, "lifestyle": LifestyleExpectation.MODERATE,
     "bio": "Flight attendant, 40+ countries. I collect passport stamps and stories.",
     "headline": "Sun-kissed and spontaneous",
     "looking": "Freedom and spontaneity. Bonus if you have a place in Monaco.",
     "offering": "A travel partner who knows the best hidden spots everywhere.",
     "arrangement": ["travel_companion", "dating", "no_strings"], "interests": ["travel", "photography", "hiking", "fine_dining"]},
    {"name": "Valentina", "age": 25, "occ": "Fashion Stylist", "edu": Education.BACHELORS, "lifestyle": LifestyleExpectation.HIGH,
     "bio": "Fashion stylist to the stars. I dress people for a living but I'm best undressed.",
     "headline": "Style is a way of life",
     "looking": "A man with taste — in clothes, cars, and women.",
     "offering": "A wardrobe upgrade and the best arm candy in town.",
     "arrangement": ["sugar_relationship", "experience_partner", "dating"], "interests": ["fashion", "art", "nightlife", "shopping"]},
    {"name": "Aria", "age": 23, "occ": "Interior Design Student", "edu": Education.SOME_COLLEGE, "lifestyle": LifestyleExpectation.MODERATE,
     "bio": "Design student by day, old soul by night. I love a good whiskey and jazz.",
     "headline": "Old soul, young heart",
     "looking": "Someone mature and cultured. Age is just a number.",
     "offering": "Fresh perspective, great taste, genuine interest in your world.",
     "arrangement": ["mentorship", "dating", "long_term"], "interests": ["art", "music", "reading", "cooking"]},
    {"name": "Sienna", "age": 27, "occ": "Pilates Instructor", "edu": Education.BACHELORS, "lifestyle": LifestyleExpectation.SUBSTANTIAL,
     "bio": "Pilates instructor and wellness obsessed. Strong, flexible, and fun.",
     "headline": "Flexible in every way",
     "looking": "A driven man who takes care of his body and his woman.",
     "offering": "Energy, positivity, and someone who makes you feel 10 years younger.",
     "arrangement": ["dating", "sugar_relationship", "travel_companion"], "interests": ["fitness", "yoga", "travel", "spa"]},
    {"name": "Jade", "age": 30, "occ": "Real Estate Agent", "edu": Education.BACHELORS, "lifestyle": LifestyleExpectation.HIGH,
     "bio": "I sell multimillion dollar homes. I know what luxury looks like.",
     "headline": "I know my worth — do you?",
     "looking": "A man who's already successful, not just talking about it.",
     "offering": "Sophistication, hustle, and someone who can hold court at any dinner.",
     "arrangement": ["networking", "sugar_relationship", "long_term"], "interests": ["real_estate", "fine_dining", "travel", "fashion"]},
    {"name": "Camille", "age": 26, "occ": "Sommelier", "edu": Education.BACHELORS, "lifestyle": LifestyleExpectation.MODERATE,
     "bio": "Certified sommelier. I'll pick the wine, you pick the restaurant.",
     "headline": "Life's too short for bad wine",
     "looking": "A generous gentleman who appreciates the finer things — starting with wine.",
     "offering": "Wine education, great taste, and a palate that'll impress your friends.",
     "arrangement": ["dating", "experience_partner", "long_term"], "interests": ["wine", "fine_dining", "travel", "cooking"]},
    {"name": "Zara", "age": 24, "occ": "Influencer", "edu": Education.SOME_COLLEGE, "lifestyle": LifestyleExpectation.HIGH,
     "bio": "500K followers and counting. I make everything look good on camera.",
     "headline": "Main character energy",
     "looking": "Someone who can keep up with my lifestyle and doesn't mind the camera.",
     "offering": "The kind of content that makes your friends jealous.",
     "arrangement": ["sugar_relationship", "travel_companion", "no_strings"], "interests": ["fashion", "travel", "photography", "nightlife"]},
    {"name": "Aurora", "age": 22, "occ": "Pre-Med Student", "edu": Education.SOME_COLLEGE, "lifestyle": LifestyleExpectation.MODERATE,
     "bio": "Pre-med student who needs a break from textbooks. Take me somewhere nice.",
     "headline": "Future doctor, current dreamer",
     "looking": "A successful man who values intelligence and ambition.",
     "offering": "A driven mind, genuine warmth, and someone who'll make you proud.",
     "arrangement": ["mentorship", "dating", "experience_partner"], "interests": ["reading", "yoga", "fine_dining", "travel"]},
    {"name": "Bianca", "age": 28, "occ": "Jewelry Designer", "edu": Education.BACHELORS, "lifestyle": LifestyleExpectation.SUBSTANTIAL,
     "bio": "I design jewelry for a living. I have expensive taste — in every sense.",
     "headline": "Diamonds are a girl's best friend",
     "looking": "A man who understands that quality costs. In life and love.",
     "offering": "Creativity, elegance, and a custom piece just for you.",
     "arrangement": ["sugar_relationship", "long_term", "experience_partner"], "interests": ["art", "fashion", "travel", "fine_dining"]},
    {"name": "Layla", "age": 25, "occ": "Marketing Manager", "edu": Education.BACHELORS, "lifestyle": LifestyleExpectation.MODERATE,
     "bio": "Marketing manager at a luxury brand. I sell dreams, but I also live them.",
     "headline": "Selling dreams, living mine",
     "looking": "Someone ambitious, generous, and not afraid to show it.",
     "offering": "Branding advice, killer instincts, and someone who makes you look good.",
     "arrangement": ["networking", "dating", "sugar_relationship"], "interests": ["fashion", "nightlife", "travel", "concerts"]},
]

BODY_TYPES_M = [BodyType.ATHLETIC, BodyType.AVERAGE, BodyType.ATHLETIC, BodyType.AVERAGE]
BODY_TYPES_F = [BodyType.SLIM, BodyType.ATHLETIC, BodyType.CURVY, BodyType.SLIM, BodyType.ATHLETIC]
STATUSES = [RelationshipStatus.SINGLE, RelationshipStatus.DIVORCED, RelationshipStatus.SINGLE, RelationshipStatus.SINGLE]
AVAILABILITIES = [Availability.FLEXIBLE, Availability.WEEKENDS, Availability.EVENINGS, Availability.TRAVEL_READY, Availability.FLEXIBLE]
FIRST_DATES = [
    "Dinner at a Michelin-starred restaurant",
    "Cocktails at a rooftop bar with a view",
    "A private wine tasting",
    "Sunset sailing",
    "A gallery opening followed by dinner",
    "Coffee that turns into lunch that turns into dinner",
    "Shopping and champagne",
    "A walk through Central Park then dinner in the West Village",
]

CONVO_OPENERS = [
    ("Hi {name}! Your profile caught my eye.", "Thank you! What stood out to you?", "Your {trait}. I'd love to get to know you better.", "I'd like that. Tell me about yourself."),
    ("Love your headline — '{headline}'. Very intriguing.", "Thank you! I put thought into it 😊", "It shows. Would you like to grab dinner sometime?", "I'd love that. What area are you in?"),
    ("{name}, you seem like exactly what I've been looking for.", "That's quite a compliment! What makes you say that?", "Your combination of {trait} and ambition. It's rare.", "I appreciate that. Let's see if the chemistry is real."),
]


async def seed():
    async with async_session() as db:
        # Clear everything
        for table in ["messages", "conversations", "matches", "likes", "blocks", "reports", "photos", "favorites", "profile_views",
                      "profiles", "privacy_settings", "notification_preferences", "subscriptions", "users"]:
            try:
                await db.execute(sqlalchemy.text(f"DELETE FROM {table}"))
            except Exception:
                pass
        await db.commit()

        email_to_profile = {}
        all_sugar_pids = []
        all_attractive_pids = []

        # Create sugar profiles
        for i, p in enumerate(SUGAR_PROFILES):
            city = CITIES[i % len(CITIES)]
            email = f"{p['name'].lower()}@demo.com"
            user = User(email=email, password_hash=PASSWORD, user_type=UserType.SUGAR)
            db.add(user)
            await db.flush()

            dob = date(2026 - p["age"], random.randint(1, 12), random.randint(1, 28))
            profile = Profile(
                user_id=user.id, display_name=p["name"], bio=p["bio"], headline=p["headline"],
                date_of_birth=dob, gender=Gender.MALE, seeking_gender=Gender.FEMALE,
                city=city[0], state=city[1], country=city[2], latitude=city[3], longitude=city[4],
                occupation=p["occ"], education=p["edu"], height_cm=random.randint(175, 193),
                body_type=BODY_TYPES_M[i % len(BODY_TYPES_M)], income_range=p["income"],
                drinking=DrinkingHabit.SOCIALLY, smoking=SmokingHabit.NEVER,
                relationship_status=STATUSES[i % len(STATUSES)], availability=AVAILABILITIES[i % len(AVAILABILITIES)],
                looking_for=p["looking"], offering=p["offering"],
                arrangement_types=p["arrangement"], interests=p["interests"],
                ideal_first_date=FIRST_DATES[i % len(FIRST_DATES)],
                languages="English",
            )
            db.add(profile)
            await db.flush()
            email_to_profile[email] = profile.id
            all_sugar_pids.append(profile.id)

        # Create attractive profiles
        for i, p in enumerate(ATTRACTIVE_PROFILES):
            city = CITIES[i % len(CITIES)]
            email = f"{p['name'].lower()}@demo.com"
            user = User(email=email, password_hash=PASSWORD, user_type=UserType.ATTRACTIVE)
            db.add(user)
            await db.flush()

            dob = date(2026 - p["age"], random.randint(1, 12), random.randint(1, 28))
            profile = Profile(
                user_id=user.id, display_name=p["name"], bio=p["bio"], headline=p["headline"],
                date_of_birth=dob, gender=Gender.FEMALE, seeking_gender=Gender.MALE,
                city=city[0], state=city[1], country=city[2], latitude=city[3], longitude=city[4],
                occupation=p["occ"], education=p["edu"], height_cm=random.randint(160, 175),
                body_type=BODY_TYPES_F[i % len(BODY_TYPES_F)],
                lifestyle_expectation=p["lifestyle"],
                drinking=DrinkingHabit.SOCIALLY, smoking=SmokingHabit.NEVER,
                relationship_status=RelationshipStatus.SINGLE, availability=AVAILABILITIES[i % len(AVAILABILITIES)],
                looking_for=p["looking"], offering=p["offering"],
                arrangement_types=p["arrangement"], interests=p["interests"],
                ideal_first_date=FIRST_DATES[i % len(FIRST_DATES)],
                languages="English",
            )
            db.add(profile)
            await db.flush()
            email_to_profile[email] = profile.id
            all_attractive_pids.append(profile.id)

        await db.commit()

        # Create matches: pair sugar with attractive
        matches_to_create = [
            ("sophia@demo.com", "james@demo.com"),
            ("sophia@demo.com", "william@demo.com"),
            ("emma@demo.com", "robert@demo.com"),
            ("emma@demo.com", "michael@demo.com"),
            ("charlotte@demo.com", "james@demo.com"),
            ("mia@demo.com", "david@demo.com"),
            ("ava@demo.com", "marcus@demo.com"),
            ("isabella@demo.com", "alexander@demo.com"),
            ("luna@demo.com", "richard@demo.com"),
            ("valentina@demo.com", "vincent@demo.com"),
            ("natalie@demo.com", "thomas@demo.com"),
            ("jade@demo.com", "daniel@demo.com"),
            ("sienna@demo.com", "jonathan@demo.com"),
            ("camille@demo.com", "andrew@demo.com"),
        ]

        convos_created = 0
        for a_email, s_email in matches_to_create:
            a_pid = email_to_profile.get(a_email)
            s_pid = email_to_profile.get(s_email)
            if not a_pid or not s_pid:
                continue

            db.add(Like(from_profile_id=a_pid, to_profile_id=s_pid))
            db.add(Like(from_profile_id=s_pid, to_profile_id=a_pid))

            p1, p2 = min(a_pid, s_pid), max(a_pid, s_pid)
            match = Match(profile1_id=p1, profile2_id=p2)
            db.add(match)
            await db.flush()

            conv = Conversation(match_id=match.id)
            db.add(conv)
            await db.flush()

            # Add messages
            opener = random.choice(CONVO_OPENERS)
            base_time = datetime.utcnow() - timedelta(hours=random.randint(2, 48))
            profiles_in_conv = [s_pid, a_pid, s_pid, a_pid]
            for j, (pid, text) in enumerate(zip(profiles_in_conv, opener)):
                # Replace placeholders
                text = text.replace("{name}", a_email.split("@")[0].capitalize() if pid == s_pid else s_email.split("@")[0].capitalize())
                text = text.replace("{headline}", "intriguing")
                text = text.replace("{trait}", "style")
                msg = Message(
                    conversation_id=conv.id, sender_profile_id=pid, content=text,
                    is_read=j < 3,
                )
                db.add(msg)
                base_time += timedelta(minutes=random.randint(5, 60))
            convos_created += 1

        # One-way likes (no match yet)
        for _ in range(30):
            a_pid = random.choice(all_attractive_pids)
            s_pid = random.choice(all_sugar_pids)
            try:
                db.add(Like(from_profile_id=a_pid, to_profile_id=s_pid))
                await db.flush()
            except Exception:
                await db.rollback()

        # Set one person as traveling
        natalie_pid = email_to_profile.get("natalie@demo.com")
        if natalie_pid:
            result = await db.execute(sqlalchemy.select(Profile).where(Profile.id == natalie_pid))
            natalie = result.scalar_one_or_none()
            if natalie:
                natalie.is_traveling = True
                natalie.travel_city = "Paris"
                natalie.travel_latitude = 48.8566
                natalie.travel_longitude = 2.3522

        await db.commit()

    total = len(SUGAR_PROFILES) + len(ATTRACTIVE_PROFILES)
    print(f"Seeded {total} profiles ({len(SUGAR_PROFILES)} sugar, {len(ATTRACTIVE_PROFILES)} attractive)")
    print(f"Created {convos_created} matches with conversations")
    print(f"Created ~30 one-way likes")
    print(f"Password for all: password123")
    print(f"\nTest as: sophia@demo.com (2 matches), emma@demo.com (2 matches)")


if __name__ == "__main__":
    asyncio.run(seed())
