"""Full seed: 20+ profiles, matches, conversations, messages, likes."""
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

PASSWORD = hash_password("password123")

PROFILES = [
    # === SUGAR (wealthy) members ===
    {
        "email": "james@demo.com", "user_type": UserType.SUGAR,
        "profile": {
            "display_name": "James", "headline": "Building the future, one venture at a time",
            "bio": "Tech entrepreneur who loves traveling, fine dining, and meaningful connections. Looking for someone to share adventures with.",
            "date_of_birth": date(1985, 3, 15), "gender": Gender.MALE, "seeking_gender": Gender.FEMALE,
            "city": "New York", "state": "NY", "country": "US", "latitude": 40.7128, "longitude": -74.006,
            "occupation": "CEO", "education": Education.MASTERS, "height_cm": 183,
            "body_type": BodyType.ATHLETIC, "income_range": IncomeRange.R1M_5M,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
            "relationship_status": RelationshipStatus.DIVORCED, "availability": Availability.FLEXIBLE,
            "looking_for": "Someone who appreciates the finer things and wants to share adventures. Intelligence and ambition are a must.",
            "offering": "Financial mentorship, luxury travel, fine dining experiences, and genuine connections with no drama.",
            "arrangement_types": ["mentorship", "travel_companion", "long_term", "sugar_relationship"],
            "interests": ["travel", "fine_dining", "wine", "investing", "golf", "theater"],
            "ideal_first_date": "Dinner at a Michelin-starred restaurant followed by drinks at a jazz bar",
            "languages": "English, French",
        },
    },
    {
        "email": "michael@demo.com", "user_type": UserType.SUGAR,
        "profile": {
            "display_name": "Michael", "headline": "Life is short, live generously",
            "bio": "Investment banker by day, foodie by night. I enjoy wine, sailing, and stimulating conversation.",
            "date_of_birth": date(1978, 11, 3), "gender": Gender.MALE, "seeking_gender": Gender.FEMALE,
            "city": "Los Angeles", "state": "CA", "country": "US", "latitude": 34.0522, "longitude": -118.2437,
            "occupation": "Investment Banker", "education": Education.MASTERS, "height_cm": 178,
            "body_type": BodyType.AVERAGE, "income_range": IncomeRange.R5M_10M,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
            "relationship_status": RelationshipStatus.DIVORCED, "availability": Availability.EVENINGS,
            "looking_for": "A captivating woman who enjoys the lifestyle but has substance behind the beauty.",
            "offering": "The best experiences money can buy — private travel, exclusive events, generous allowance.",
            "arrangement_types": ["sugar_relationship", "travel_companion", "no_strings"],
            "interests": ["yachting", "wine", "fine_dining", "travel", "nightlife", "investing"],
            "ideal_first_date": "Sunset sailing followed by seafood at a waterfront restaurant",
            "languages": "English",
        },
    },
    {
        "email": "david@demo.com", "user_type": UserType.SUGAR,
        "profile": {
            "display_name": "David", "headline": "Building dreams, brick by brick",
            "bio": "Real estate developer with a passion for architecture and design. I believe in living well and treating others with generosity.",
            "date_of_birth": date(1980, 5, 20), "gender": Gender.MALE, "seeking_gender": Gender.FEMALE,
            "city": "Chicago", "state": "IL", "country": "US", "latitude": 41.8781, "longitude": -87.6298,
            "occupation": "Real Estate Developer", "education": Education.BACHELORS, "height_cm": 188,
            "body_type": BodyType.ATHLETIC, "income_range": IncomeRange.R500K_1M,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
            "relationship_status": RelationshipStatus.SINGLE, "availability": Availability.WEEKENDS,
            "looking_for": "An intelligent, driven woman who wants more from life. I value ambition as much as beauty.",
            "offering": "Stability, mentorship, luxury living, and a partner who genuinely cares about your growth.",
            "arrangement_types": ["mentorship", "long_term", "networking"],
            "interests": ["real_estate", "fine_dining", "travel", "art", "golf", "sports"],
            "ideal_first_date": "Brunch at my favorite spot downtown, no pretenses, just good food and real conversation",
            "languages": "English, Spanish",
        },
    },
    {
        "email": "alex@demo.com", "user_type": UserType.SUGAR,
        "profile": {
            "display_name": "Alexander", "headline": "Healing the world, one patient at a time",
            "bio": "Physician and medical researcher. When I'm not at the hospital, you'll find me at jazz clubs or art galleries.",
            "date_of_birth": date(1982, 12, 1), "gender": Gender.MALE, "seeking_gender": Gender.FEMALE,
            "city": "San Francisco", "state": "CA", "country": "US", "latitude": 37.7749, "longitude": -122.4194,
            "occupation": "Physician", "education": Education.DOCTORATE, "height_cm": 180,
            "body_type": BodyType.AVERAGE, "income_range": IncomeRange.R250K_500K,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
            "relationship_status": RelationshipStatus.SINGLE, "availability": Availability.WEEKENDS,
            "looking_for": "A curious, cultured woman who loves learning and exploring as much as I do.",
            "offering": "Intellectual stimulation, financial security, worldwide travel, and genuine care.",
            "arrangement_types": ["mentorship", "long_term", "experience_partner"],
            "interests": ["travel", "reading", "music", "theater", "wine", "hiking"],
            "ideal_first_date": "A jazz performance followed by late-night conversation over whiskey",
            "languages": "English, German",
        },
    },
    {
        "email": "robert@demo.com", "user_type": UserType.SUGAR,
        "profile": {
            "display_name": "Robert", "headline": "Making deals and making memories",
            "bio": "Private equity partner who works hard and plays harder. Weekdays in the boardroom, weekends on the yacht.",
            "date_of_birth": date(1975, 8, 12), "gender": Gender.MALE, "seeking_gender": Gender.FEMALE,
            "city": "Miami", "state": "FL", "country": "US", "latitude": 25.7617, "longitude": -80.1918,
            "occupation": "Private Equity Partner", "education": Education.MASTERS, "height_cm": 185,
            "body_type": BodyType.ATHLETIC, "income_range": IncomeRange.OVER_10M,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
            "relationship_status": RelationshipStatus.DIVORCED, "availability": Availability.FLEXIBLE,
            "looking_for": "A stunning, intelligent woman who can hold her own at a charity gala and on a beach in St. Barts.",
            "offering": "An extraordinary lifestyle — travel, gifts, financial freedom, and someone who treats you like royalty.",
            "arrangement_types": ["sugar_relationship", "travel_companion", "no_strings"],
            "interests": ["yachting", "travel", "fine_dining", "nightlife", "fitness", "cars"],
            "ideal_first_date": "Private dinner on my yacht in Biscayne Bay",
            "languages": "English, Portuguese",
        },
    },
    {
        "email": "william@demo.com", "user_type": UserType.SUGAR,
        "profile": {
            "display_name": "William", "headline": "Old money, new adventures",
            "bio": "Attorney turned angel investor. I've built a comfortable life and now I want someone to enjoy it with.",
            "date_of_birth": date(1972, 4, 25), "gender": Gender.MALE, "seeking_gender": Gender.FEMALE,
            "city": "New York", "state": "NY", "country": "US", "latitude": 40.7580, "longitude": -73.9855,
            "occupation": "Angel Investor", "education": Education.DOCTORATE, "height_cm": 175,
            "body_type": BodyType.AVERAGE, "income_range": IncomeRange.R5M_10M,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
            "relationship_status": RelationshipStatus.WIDOWED, "availability": Availability.FLEXIBLE,
            "looking_for": "Genuine warmth and companionship. Someone who values experiences over things.",
            "offering": "Wisdom, stability, generosity, and access to a world most people only read about.",
            "arrangement_types": ["long_term", "mentorship", "experience_partner"],
            "interests": ["art", "theater", "wine", "reading", "travel", "volunteering"],
            "ideal_first_date": "A private tour of a gallery opening, followed by a quiet dinner",
            "languages": "English, Italian",
        },
    },
    {
        "email": "richard@demo.com", "user_type": UserType.SUGAR,
        "profile": {
            "display_name": "Richard", "headline": "Life's too short for mediocre anything",
            "bio": "Serial entrepreneur in fintech. Three exits, zero regrets. Looking for my next great adventure — in business and in life.",
            "date_of_birth": date(1983, 7, 9), "gender": Gender.MALE, "seeking_gender": Gender.FEMALE,
            "city": "Las Vegas", "state": "NV", "country": "US", "latitude": 36.1699, "longitude": -115.1398,
            "occupation": "Tech Entrepreneur", "education": Education.BACHELORS, "height_cm": 180,
            "body_type": BodyType.ATHLETIC, "income_range": IncomeRange.R1M_5M,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.OCCASIONALLY,
            "relationship_status": RelationshipStatus.SINGLE, "availability": Availability.TRAVEL_READY,
            "looking_for": "A spontaneous, fun-loving woman who's not afraid of first-class flights on a Tuesday.",
            "offering": "Excitement, generosity, travel, and a lifestyle that never gets boring.",
            "arrangement_types": ["sugar_relationship", "travel_companion", "short_term", "no_strings"],
            "interests": ["travel", "nightlife", "cars", "fitness", "tech", "concerts"],
            "ideal_first_date": "VIP table at a show, then late-night tacos on the strip",
            "languages": "English",
        },
    },

    # === ATTRACTIVE members ===
    {
        "email": "sophia@demo.com", "user_type": UserType.ATTRACTIVE,
        "profile": {
            "display_name": "Sophia", "headline": "Art, ambition, and authenticity",
            "bio": "Graduate student passionate about art, yoga, and personal growth. I appreciate genuine connections and the finer things in life.",
            "date_of_birth": date(1998, 7, 22), "gender": Gender.FEMALE, "seeking_gender": Gender.MALE,
            "city": "New York", "state": "NY", "country": "US", "latitude": 40.7128, "longitude": -74.006,
            "occupation": "Art Curator", "education": Education.MASTERS, "height_cm": 168,
            "body_type": BodyType.SLIM, "lifestyle_expectation": LifestyleExpectation.SUBSTANTIAL,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
            "relationship_status": RelationshipStatus.SINGLE, "availability": Availability.WEEKENDS,
            "looking_for": "A generous, established gentleman who values culture, art, and deep conversations.",
            "offering": "Engaging company, a creative perspective, and genuine warmth. I make every moment memorable.",
            "arrangement_types": ["mentorship", "long_term", "experience_partner"],
            "interests": ["art", "yoga", "fine_dining", "travel", "photography", "reading"],
            "ideal_first_date": "A gallery opening followed by a quiet dinner where we can actually talk",
            "languages": "English, Greek",
        },
    },
    {
        "email": "emma@demo.com", "user_type": UserType.ATTRACTIVE,
        "profile": {
            "display_name": "Emma", "headline": "Chasing sunsets and dreams",
            "bio": "Model and aspiring fashion designer. I love exploring new cultures, rooftop sunsets, and deep late-night talks.",
            "date_of_birth": date(2000, 1, 14), "gender": Gender.FEMALE, "seeking_gender": Gender.MALE,
            "city": "Miami", "state": "FL", "country": "US", "latitude": 25.7617, "longitude": -80.1918,
            "occupation": "Model", "education": Education.BACHELORS, "height_cm": 173,
            "body_type": BodyType.SLIM, "lifestyle_expectation": LifestyleExpectation.HIGH,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
            "relationship_status": RelationshipStatus.SINGLE, "availability": Availability.FLEXIBLE,
            "looking_for": "A successful man who knows how to treat a lady. Generosity and confidence are everything.",
            "offering": "Stunning company, adventure, and the kind of energy that makes you forget about work.",
            "arrangement_types": ["sugar_relationship", "travel_companion", "dating"],
            "interests": ["fashion", "travel", "fitness", "nightlife", "dancing", "spa"],
            "ideal_first_date": "Shopping on Rodeo Drive followed by cocktails at a rooftop bar",
            "languages": "English, Spanish",
        },
    },
    {
        "email": "olivia@demo.com", "user_type": UserType.ATTRACTIVE,
        "profile": {
            "display_name": "Olivia", "headline": "Simple girl with big dreams",
            "bio": "Dental hygienist who loves hiking, cooking, and cozy nights in. Looking for someone ambitious and kind.",
            "date_of_birth": date(1996, 9, 8), "gender": Gender.FEMALE, "seeking_gender": Gender.MALE,
            "city": "New York", "state": "NY", "country": "US", "latitude": 40.73, "longitude": -73.99,
            "occupation": "Dental Hygienist", "education": Education.BACHELORS, "height_cm": 165,
            "body_type": BodyType.CURVY, "lifestyle_expectation": LifestyleExpectation.MODERATE,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
            "relationship_status": RelationshipStatus.SINGLE, "availability": Availability.FLEXIBLE,
            "looking_for": "Someone kind and established who values simple pleasures alongside the exciting ones.",
            "offering": "Down-to-earth companionship, great cooking, and someone who actually listens.",
            "arrangement_types": ["dating", "long_term", "experience_partner"],
            "interests": ["cooking", "hiking", "yoga", "reading", "movies", "nature"],
            "ideal_first_date": "A farmers market followed by cooking dinner together",
            "languages": "English",
        },
    },
    {
        "email": "isabella@demo.com", "user_type": UserType.ATTRACTIVE,
        "profile": {
            "display_name": "Isabella", "headline": "Strong body, stronger mind",
            "bio": "Fitness trainer and wellness coach. I live for the outdoors, great food, and even better company.",
            "date_of_birth": date(1997, 4, 18), "gender": Gender.FEMALE, "seeking_gender": Gender.MALE,
            "city": "Los Angeles", "state": "CA", "country": "US", "latitude": 34.05, "longitude": -118.25,
            "occupation": "Fitness Trainer", "education": Education.BACHELORS, "height_cm": 170,
            "body_type": BodyType.ATHLETIC, "lifestyle_expectation": LifestyleExpectation.SUBSTANTIAL,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
            "relationship_status": RelationshipStatus.SINGLE, "availability": Availability.FLEXIBLE,
            "looking_for": "A confident, generous man who values health and adventure.",
            "offering": "High energy, amazing fitness companionship, spontaneous adventures, and loyalty.",
            "arrangement_types": ["dating", "travel_companion", "sugar_relationship"],
            "interests": ["fitness", "hiking", "travel", "cooking", "dancing", "concerts"],
            "ideal_first_date": "A sunrise hike followed by brunch — if you can keep up",
            "languages": "English, Italian",
        },
    },
    {
        "email": "ava@demo.com", "user_type": UserType.ATTRACTIVE,
        "profile": {
            "display_name": "Ava", "headline": "Champagne taste, caviar dreams",
            "bio": "PR consultant by day, socialite by night. I know every rooftop bar in the city and I'll show you the best ones.",
            "date_of_birth": date(1999, 6, 30), "gender": Gender.FEMALE, "seeking_gender": Gender.MALE,
            "city": "New York", "state": "NY", "country": "US", "latitude": 40.75, "longitude": -73.98,
            "occupation": "PR Consultant", "education": Education.BACHELORS, "height_cm": 170,
            "body_type": BodyType.SLIM, "lifestyle_expectation": LifestyleExpectation.HIGH,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
            "relationship_status": RelationshipStatus.SINGLE, "availability": Availability.EVENINGS,
            "looking_for": "Someone powerful and decisive. I want a man who takes charge and knows what he wants.",
            "offering": "The perfect plus-one. Charming, well-connected, and always camera-ready.",
            "arrangement_types": ["sugar_relationship", "networking", "no_strings"],
            "interests": ["nightlife", "fashion", "fine_dining", "travel", "art", "shopping"],
            "ideal_first_date": "Cocktails at a members-only club, people-watching and plotting world domination",
            "languages": "English, French",
        },
    },
    {
        "email": "mia@demo.com", "user_type": UserType.ATTRACTIVE,
        "profile": {
            "display_name": "Mia", "headline": "Nurse by day, dreamer always",
            "bio": "Pediatric nurse with a huge heart. I spend my days saving tiny humans and my nights dreaming of travel.",
            "date_of_birth": date(1995, 2, 14), "gender": Gender.FEMALE, "seeking_gender": Gender.MALE,
            "city": "Chicago", "state": "IL", "country": "US", "latitude": 41.88, "longitude": -87.63,
            "occupation": "Pediatric Nurse", "education": Education.BACHELORS, "height_cm": 163,
            "body_type": BodyType.AVERAGE, "lifestyle_expectation": LifestyleExpectation.MODERATE,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
            "relationship_status": RelationshipStatus.SINGLE, "availability": Availability.WEEKENDS,
            "looking_for": "A kind, generous soul who wants to explore the world together. No games.",
            "offering": "Genuine care, loyalty, great conversation, and someone who'll always have your back.",
            "arrangement_types": ["dating", "long_term", "travel_companion"],
            "interests": ["travel", "cooking", "yoga", "movies", "music", "volunteering"],
            "ideal_first_date": "Deep dish pizza and a walk along the lakefront at sunset",
            "languages": "English",
        },
    },
    {
        "email": "luna@demo.com", "user_type": UserType.ATTRACTIVE,
        "profile": {
            "display_name": "Luna", "headline": "Dance like nobody's watching",
            "bio": "Professional dancer and choreographer. I bring passion and grace to everything I do — on and off the stage.",
            "date_of_birth": date(2001, 11, 5), "gender": Gender.FEMALE, "seeking_gender": Gender.MALE,
            "city": "Las Vegas", "state": "NV", "country": "US", "latitude": 36.17, "longitude": -115.14,
            "occupation": "Dancer / Choreographer", "education": Education.SOME_COLLEGE, "height_cm": 168,
            "body_type": BodyType.ATHLETIC, "lifestyle_expectation": LifestyleExpectation.SUBSTANTIAL,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
            "relationship_status": RelationshipStatus.SINGLE, "availability": Availability.EVENINGS,
            "looking_for": "A generous gentleman who appreciates art and can keep up with my energy.",
            "offering": "Unforgettable company, spontaneity, and someone who makes every night feel like an event.",
            "arrangement_types": ["sugar_relationship", "experience_partner", "short_term"],
            "interests": ["dancing", "fitness", "nightlife", "music", "travel", "spa"],
            "ideal_first_date": "A show on the strip, then dancing until 3am",
            "languages": "English, Korean",
        },
    },
    {
        "email": "charlotte@demo.com", "user_type": UserType.ATTRACTIVE,
        "profile": {
            "display_name": "Charlotte", "headline": "Brains, beauty, and a business plan",
            "bio": "MBA student at Wharton. I'm building my future but I also know how to enjoy the present. Ambitious and unapologetic.",
            "date_of_birth": date(1997, 3, 21), "gender": Gender.FEMALE, "seeking_gender": Gender.MALE,
            "city": "New York", "state": "NY", "country": "US", "latitude": 40.71, "longitude": -74.01,
            "occupation": "MBA Student", "education": Education.MASTERS, "height_cm": 172,
            "body_type": BodyType.SLIM, "lifestyle_expectation": LifestyleExpectation.SUBSTANTIAL,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
            "relationship_status": RelationshipStatus.SINGLE, "availability": Availability.WEEKENDS,
            "looking_for": "A mentor-type who's already where I want to be. I learn fast and give back more.",
            "offering": "Sharp mind, great company, someone who actually understands your business over dinner.",
            "arrangement_types": ["mentorship", "networking", "long_term", "experience_partner"],
            "interests": ["investing", "fine_dining", "travel", "reading", "fitness", "art"],
            "ideal_first_date": "Coffee that turns into lunch that turns into 'wait, it's 6pm already?'",
            "languages": "English, Mandarin",
        },
    },
    {
        "email": "natalie@demo.com", "user_type": UserType.ATTRACTIVE,
        "profile": {
            "display_name": "Natalie", "headline": "Sun-kissed and spontaneous",
            "bio": "Flight attendant who's been to 40+ countries. I collect passport stamps and good stories. Home is wherever I land.",
            "date_of_birth": date(1996, 8, 17), "gender": Gender.FEMALE, "seeking_gender": Gender.MALE,
            "city": "Miami", "state": "FL", "country": "US", "latitude": 25.76, "longitude": -80.19,
            "occupation": "Flight Attendant", "education": Education.BACHELORS, "height_cm": 167,
            "body_type": BodyType.ATHLETIC, "lifestyle_expectation": LifestyleExpectation.MODERATE,
            "drinking": DrinkingHabit.SOCIALLY, "smoking": SmokingHabit.NEVER,
            "relationship_status": RelationshipStatus.SINGLE, "availability": Availability.TRAVEL_READY,
            "looking_for": "Someone who values freedom and spontaneity. Bonus if you have a place in Monaco.",
            "offering": "A travel partner who actually knows the best hidden spots in every city.",
            "arrangement_types": ["travel_companion", "dating", "no_strings"],
            "interests": ["travel", "photography", "hiking", "fine_dining", "yoga", "concerts"],
            "ideal_first_date": "Meeting at the airport — I'll pick the destination, you buy the tickets",
            "languages": "English, French, Portuguese",
            "is_traveling": True, "travel_city": "Paris", "travel_latitude": 48.8566, "travel_longitude": 2.3522,
        },
    },
]


# Conversations to create between matched users
# (sophia matches with james, william, david; emma matches with robert, michael)
MATCHES_AND_MESSAGES = [
    {
        "user1_email": "sophia@demo.com",
        "user2_email": "james@demo.com",
        "messages": [
            ("james@demo.com", "Hi Sophia! I loved your headline — art, ambition, and authenticity. That's rare."),
            ("sophia@demo.com", "Thank you James! I see you're in tech — I've always been fascinated by how tech and art intersect."),
            ("james@demo.com", "You'd love the immersive exhibit at the Shed right now. Would you want to check it out this weekend?"),
            ("sophia@demo.com", "I've been wanting to go! Saturday afternoon works for me?"),
            ("james@demo.com", "Perfect. I'll get us VIP access. Dinner after at Eleven Madison Park?"),
            ("sophia@demo.com", "You really know how to plan a date 😊 I'm in!"),
        ],
    },
    {
        "user1_email": "sophia@demo.com",
        "user2_email": "william@demo.com",
        "messages": [
            ("william@demo.com", "Sophia, your profile caught my eye. A fellow art lover in the city is always welcome."),
            ("sophia@demo.com", "William! An angel investor who loves art — that's an interesting combination. What's your favorite gallery?"),
            ("william@demo.com", "The Frick. Intimate, timeless, no crowds. I have a membership — happy to take a guest."),
            ("sophia@demo.com", "That sounds lovely. I'd really enjoy that."),
        ],
    },
    {
        "user1_email": "emma@demo.com",
        "user2_email": "robert@demo.com",
        "messages": [
            ("robert@demo.com", "Emma! A model in Miami — we're practically neighbors. I'm on the water most weekends."),
            ("emma@demo.com", "Robert! I've always wanted to go sailing in the Bay. Is that an invitation? 😏"),
            ("robert@demo.com", "Consider it a standing one. This Saturday? I'll have champagne and the sunset ready."),
            ("emma@demo.com", "You had me at champagne. What should I wear?"),
            ("robert@demo.com", "Something you won't mind getting a little salt spray on 😉"),
        ],
    },
    {
        "user1_email": "emma@demo.com",
        "user2_email": "michael@demo.com",
        "messages": [
            ("michael@demo.com", "Hi Emma, your energy is infectious even through a screen. What brings you to the app?"),
            ("emma@demo.com", "Thanks Michael! I'm looking for someone who matches my ambition. Your profile gives main character energy."),
            ("michael@demo.com", "Ha! I like that. I'm in Miami next month for Art Basel — would love to show you around."),
        ],
    },
    {
        "user1_email": "charlotte@demo.com",
        "user2_email": "james@demo.com",
        "messages": [
            ("james@demo.com", "Charlotte — a Wharton MBA who's also into investing? We need to talk shop over dinner."),
            ("charlotte@demo.com", "Finally someone who won't glaze over when I talk about cap tables 😄 Where are you thinking?"),
            ("james@demo.com", "Le Bernardin. Thursday at 8?"),
            ("charlotte@demo.com", "Done. I'll bring my pitch deck. Kidding. Mostly."),
        ],
    },
    {
        "user1_email": "mia@demo.com",
        "user2_email": "david@demo.com",
        "messages": [
            ("david@demo.com", "Mia, a pediatric nurse! That takes a special kind of person. I really respect that."),
            ("mia@demo.com", "Aw thank you David! It's not glamorous but I love it. Your profile is really genuine — refreshing."),
            ("david@demo.com", "I try to keep it real. How about that deep dish and lakefront walk you mentioned?"),
        ],
    },
]

# Additional one-way likes (no match yet)
EXTRA_LIKES = [
    ("ava@demo.com", "james@demo.com"),
    ("ava@demo.com", "william@demo.com"),
    ("luna@demo.com", "richard@demo.com"),
    ("natalie@demo.com", "robert@demo.com"),
    ("olivia@demo.com", "david@demo.com"),
    ("isabella@demo.com", "alex@demo.com"),
    ("charlotte@demo.com", "michael@demo.com"),
    ("mia@demo.com", "james@demo.com"),
]


async def seed():
    async with async_session() as db:
        # Check if data already exists
        existing = await db.execute(
            __import__("sqlalchemy").select(User).limit(1)
        )
        if existing.scalar_one_or_none():
            print("Database already has data. Clearing and re-seeding...")
            # Clear all tables in order
            for table in ["messages", "conversations", "matches", "likes", "blocks", "reports", "photos", "profiles", "privacy_settings", "notification_preferences", "subscriptions", "users"]:
                try:
                    await db.execute(__import__("sqlalchemy").text(f"DELETE FROM {table}"))
                except Exception:
                    pass
            await db.commit()

        # Create users + profiles
        email_to_profile: dict[str, int] = {}
        for item in PROFILES:
            user = User(
                email=item["email"],
                password_hash=PASSWORD,
                user_type=item["user_type"],
            )
            db.add(user)
            await db.flush()

            profile_data = {k: v for k, v in item["profile"].items()}
            profile = Profile(user_id=user.id, **profile_data)
            db.add(profile)
            await db.flush()
            email_to_profile[item["email"]] = profile.id

        await db.commit()

        # Create matches and conversations
        for match_data in MATCHES_AND_MESSAGES:
            p1_id = email_to_profile[match_data["user1_email"]]
            p2_id = email_to_profile[match_data["user2_email"]]
            low, high = min(p1_id, p2_id), max(p1_id, p2_id)

            # Create mutual likes
            db.add(Like(from_profile_id=p1_id, to_profile_id=p2_id))
            db.add(Like(from_profile_id=p2_id, to_profile_id=p1_id))

            # Create match
            match = Match(profile1_id=low, profile2_id=high)
            db.add(match)
            await db.flush()

            # Create conversation
            conv = Conversation(match_id=match.id)
            db.add(conv)
            await db.flush()

            # Create messages with realistic timestamps
            base_time = datetime.utcnow() - timedelta(hours=len(match_data["messages"]) * 3)
            for i, (sender_email, content) in enumerate(match_data["messages"]):
                sender_pid = email_to_profile[sender_email]
                msg = Message(
                    conversation_id=conv.id,
                    sender_profile_id=sender_pid,
                    content=content,
                    is_read=i < len(match_data["messages"]) - 1,  # Last message unread
                )
                db.add(msg)
                base_time += timedelta(minutes=random.randint(5, 45))

        # Create extra one-way likes
        for liker_email, liked_email in EXTRA_LIKES:
            liker_pid = email_to_profile[liker_email]
            liked_pid = email_to_profile[liked_email]
            db.add(Like(from_profile_id=liker_pid, to_profile_id=liked_pid))

        await db.commit()

    print(f"Seeded {len(PROFILES)} profiles, {len(MATCHES_AND_MESSAGES)} conversations with messages, {len(EXTRA_LIKES)} one-way likes")
    print("Password for all accounts: password123")
    print("\nKey accounts to test:")
    print("  sophia@demo.com  — 2 matches with conversations")
    print("  emma@demo.com    — 2 matches with conversations")
    print("  james@demo.com   — 2 matches (sophia + charlotte)")
    print("  robert@demo.com  — 1 match (emma)")
    print("  natalie@demo.com — traveling in Paris")


if __name__ == "__main__":
    asyncio.run(seed())
