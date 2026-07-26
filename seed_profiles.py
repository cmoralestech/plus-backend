"""Seed high-quality profiles for launch.

Run on the server: python seed_profiles.py
"""
import asyncio
import random
import uuid
import urllib.request
from pathlib import Path
from datetime import date, timedelta

from app.database import async_session, engine
from app.models.user import User, UserType
from app.models.profile import Profile, Photo
from app.services.auth import hash_password
from sqlalchemy import select, text

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ═══ ATTRACTIVE FEMALE PROFILES ═══
ATTRACTIVE_FEMALES = [
    {
        "name": "Valentina", "age": 24, "city": "Miami", "state": "Florida",
        "occupation": "Model", "education": "bachelors", "body_type": "slim",
        "headline": "Art, ambition, and authenticity",
        "bio": "I've always been drawn to people who build things — companies, experiences, lives worth living. I'm a working model who speaks three languages and would rather talk about your passion project over dinner than scroll through small talk. Looking for someone who knows what they want and isn't afraid to go after it.",
        "looking_for": "A genuine connection with someone established and driven. Mentorship is a plus — I'm building my own brand and value perspective from someone who's been there.",
        "offering": "Great conversation, spontaneity, and someone who makes every room better. I'm low-drama, high-energy, and always up for an adventure.",
        "ideal_first_date": "Rooftop dinner with a view, followed by a walk somewhere unexpected.",
        "arrangement_types": ["long_term", "mentorship", "travel_companion"],
        "interests": ["travel", "fine_dining", "fashion", "art", "yoga"],
        "ethnicity": "Hispanic / Latino", "drinking": "socially", "smoking": "never",
        "height_cm": 170, "relationship_status": "single", "availability": "flexible",
        "lifestyle_expectation": "substantial",
    },
    {
        "name": "Sophia", "age": 26, "city": "New York", "state": "New York",
        "occupation": "Interior Designer", "education": "bachelors", "body_type": "athletic",
        "headline": "Designing beautiful spaces — and a beautiful life",
        "bio": "I run a small interior design studio in Manhattan. My clients are interesting, my work is fulfilling, and my weekends are spent at gallery openings or trying every new restaurant in the West Village. What's missing is someone to share it with who matches my ambition.",
        "looking_for": "Someone successful who values aesthetics and experiences as much as I do. I want real chemistry, not a transaction.",
        "offering": "I'm the person who makes your life more colorful. Literally — I have an eye for beauty in everything. Plus I can hold my own at any dinner table.",
        "ideal_first_date": "Private gallery viewing then dinner at a chef's table.",
        "arrangement_types": ["long_term", "dating", "experience_partner"],
        "interests": ["art", "fine_dining", "travel", "photography", "wine"],
        "ethnicity": "White / Caucasian", "drinking": "socially", "smoking": "never",
        "height_cm": 168, "relationship_status": "single", "availability": "weekends",
        "lifestyle_expectation": "high",
    },
    {
        "name": "Aria", "age": 22, "city": "Los Angeles", "state": "California",
        "occupation": "Nursing Student", "education": "some_college", "body_type": "curvy",
        "headline": "Future RN who loves good food and better company",
        "bio": "Halfway through nursing school and loving it, but the student life doesn't fund the lifestyle I want to live. I grew up in a small town and came to LA for a reason — I want to experience everything this city has to offer with someone who can show me the way.",
        "looking_for": "A generous, kind man who enjoys spoiling someone who genuinely appreciates it. I'm not materialistic — I value experiences over things.",
        "offering": "Youth, energy, genuine gratitude, and someone who will actually listen when you talk about your day. I'm nurturing by nature.",
        "ideal_first_date": "Sushi omakase — I want to see how you treat the chef.",
        "arrangement_types": ["sugar_relationship", "dating", "long_term"],
        "interests": ["fine_dining", "fitness", "hiking", "cooking", "nightlife"],
        "ethnicity": "Mixed / Multiracial", "drinking": "socially", "smoking": "never",
        "height_cm": 163, "relationship_status": "single", "availability": "evenings",
        "lifestyle_expectation": "moderate",
    },
    {
        "name": "Jasmine", "age": 28, "city": "Las Vegas", "state": "Nevada",
        "occupation": "Event Coordinator", "education": "bachelors", "body_type": "slim",
        "headline": "I plan unforgettable nights for a living",
        "bio": "I coordinate high-end events on the Strip — product launches, private parties, celebrity dinners. I know every restaurant, every club, every hidden spot in this city. When I'm not working, I'm looking for someone who matches my energy and doesn't need me to slow down.",
        "looking_for": "A confident, successful man who travels frequently and wants a local connection in Vegas — or someone to bring along on the next trip.",
        "offering": "VIP access to the best of Vegas, effortless charm, and the kind of company that makes business dinners actually enjoyable.",
        "ideal_first_date": "Drinks at a speakeasy I know that doesn't have a sign on the door.",
        "arrangement_types": ["travel_companion", "experience_partner", "short_term"],
        "interests": ["nightlife", "travel", "fine_dining", "fashion", "music"],
        "ethnicity": "Black / African American", "drinking": "socially", "smoking": "never",
        "height_cm": 175, "relationship_status": "single", "availability": "flexible",
        "lifestyle_expectation": "substantial",
    },
    {
        "name": "Elena", "age": 25, "city": "Chicago", "state": "Illinois",
        "occupation": "Graduate Student", "education": "masters", "body_type": "athletic",
        "headline": "MBA by day, adventurer by nature",
        "bio": "Getting my MBA at Booth while trying to maintain a social life that doesn't revolve around case studies. I'm intellectually curious, physically active, and looking for someone who challenges me in all the right ways. I've traveled to 30 countries and I'm not stopping.",
        "looking_for": "A mentor figure who's already built what I'm working toward. Someone who can teach me about business over dinner and show me what success actually looks like day-to-day.",
        "offering": "Sharp mind, sharp style, and someone who makes you feel 25 again. I bring ambition, perspective, and I'll never bore you.",
        "ideal_first_date": "Jazz bar in the Gold Coast, then late-night tacos.",
        "arrangement_types": ["mentorship", "long_term", "networking"],
        "interests": ["travel", "fitness", "reading", "wine", "investing"],
        "ethnicity": "Asian", "drinking": "socially", "smoking": "never",
        "height_cm": 165, "relationship_status": "single", "availability": "weekends",
        "lifestyle_expectation": "moderate",
    },
    {
        "name": "Natasha", "age": 27, "city": "San Francisco", "state": "California",
        "occupation": "Yoga Instructor", "education": "bachelors", "body_type": "athletic",
        "headline": "Flexible in every sense of the word",
        "bio": "I teach yoga at a studio in the Marina and do private sessions for tech executives who need to decompress. I'm calm on the surface but passionate underneath. Looking for someone who appreciates both sides.",
        "looking_for": "Someone grounded and generous who wants a genuine connection, not just arm candy. I'm looking for mutual respect and good energy.",
        "offering": "Peace, presence, and someone who keeps you balanced. Plus I'll get you into the best shape of your life.",
        "ideal_first_date": "Hike at Lands End followed by brunch at a farm-to-table spot.",
        "arrangement_types": ["dating", "long_term", "experience_partner"],
        "interests": ["yoga", "hiking", "cooking", "spa", "travel"],
        "ethnicity": "White / Caucasian", "drinking": "socially", "smoking": "never",
        "height_cm": 172, "relationship_status": "single", "availability": "flexible",
        "lifestyle_expectation": "moderate",
    },
    {
        "name": "Camille", "age": 23, "city": "Atlanta", "state": "Georgia",
        "occupation": "Social Media Manager", "education": "bachelors", "body_type": "curvy",
        "headline": "Building brands by day, living my best life always",
        "bio": "I manage social media for a luxury lifestyle brand, which means I know how to present the best version of everything — including myself. But in person, I'm way more down to earth than my feed suggests. Looking for someone real.",
        "looking_for": "An established man who wants genuine companionship, not a performance. Someone who appreciates ambition in a younger woman.",
        "offering": "Loyalty, great taste, and someone who makes you look forward to the weekend. I'm also really good at picking restaurants.",
        "ideal_first_date": "Wine tasting at a boutique vineyard, or cocktails at the best bar in Buckhead.",
        "arrangement_types": ["sugar_relationship", "long_term", "dating"],
        "interests": ["fashion", "fine_dining", "photography", "travel", "nightlife"],
        "ethnicity": "Black / African American", "drinking": "socially", "smoking": "never",
        "height_cm": 167, "relationship_status": "single", "availability": "evenings",
        "lifestyle_expectation": "substantial",
    },
    {
        "name": "Mia", "age": 29, "city": "Dallas", "state": "Texas",
        "occupation": "Real Estate Agent", "education": "bachelors", "body_type": "slim",
        "headline": "I sell dream homes. Now I'm looking for my dream connection.",
        "bio": "Top-producing agent in the Dallas luxury market. I spend my days showing $5M+ properties and my evenings wishing I had someone equally driven to share a glass of wine with. I know this city inside out.",
        "looking_for": "A successful, secure man who doesn't play games. Someone who's as direct about what he wants as I am.",
        "offering": "Confidence, class, and someone who can navigate any social situation. Plus if you need a house, I've got you.",
        "ideal_first_date": "Dinner at the new spot in the Design District that nobody knows about yet.",
        "arrangement_types": ["dating", "long_term", "networking"],
        "interests": ["fine_dining", "investing", "travel", "art", "wine"],
        "ethnicity": "Hispanic / Latino", "drinking": "socially", "smoking": "never",
        "height_cm": 169, "relationship_status": "divorced", "availability": "flexible",
        "lifestyle_expectation": "high",
    },
]

# ═══ SUCCESSFUL MALE PROFILES ═══
SUCCESSFUL_MALES = [
    {
        "name": "James", "age": 42, "city": "New York", "state": "New York",
        "occupation": "Managing Director, Finance", "education": "masters", "body_type": "athletic",
        "headline": "Not your average CEO",
        "bio": "20 years on Wall Street taught me how to build wealth. Now I'm more interested in building experiences. I work hard during the week but I play harder on weekends — whether that's sailing in the Hamptons, trying a new restaurant, or flying somewhere warm on a whim.",
        "looking_for": "An intelligent, driven woman who wants more than a paycheck from this. I want real chemistry, good conversation, and someone who makes me want to leave the office early.",
        "offering": "Wisdom, stability, and access to a world most only read about. Financial support, mentorship, and genuine care for someone who earns it.",
        "ideal_first_date": "The Grill in Midtown — because first impressions matter.",
        "arrangement_types": ["long_term", "mentorship", "travel_companion"],
        "interests": ["fine_dining", "travel", "yachting", "wine", "golf"],
        "income_range": "1m_5m", "ethnicity": "White / Caucasian",
        "drinking": "socially", "smoking": "never",
        "height_cm": 185, "relationship_status": "divorced", "availability": "weekends",
    },
    {
        "name": "Marcus", "age": 38, "city": "Miami", "state": "Florida",
        "occupation": "Tech Entrepreneur", "education": "bachelors", "body_type": "athletic",
        "headline": "Built it from scratch. Now I want to share it.",
        "bio": "Sold my first company at 32. Building my second. Miami is home base but I'm on a plane every other week. I have more money than free time, which is why I'm here — I don't want to waste either on bad dates.",
        "looking_for": "Someone beautiful, ambitious, and honest about what she wants. I respect directness. I don't respect games.",
        "offering": "Financial generosity, travel experiences, and the perspective that comes from building something from nothing. I'm a mentor at heart.",
        "ideal_first_date": "Sunset on the boat, then dinner at Zuma.",
        "arrangement_types": ["sugar_relationship", "travel_companion", "experience_partner"],
        "interests": ["travel", "fitness", "investing", "yachting", "nightlife"],
        "income_range": "5m_10m", "ethnicity": "Black / African American",
        "drinking": "socially", "smoking": "never",
        "height_cm": 188, "relationship_status": "single", "availability": "flexible",
    },
    {
        "name": "William", "age": 52, "city": "Los Angeles", "state": "California",
        "occupation": "Entertainment Attorney", "education": "doctorate", "body_type": "average",
        "headline": "Hollywood adjacent, refreshingly normal",
        "bio": "I represent talent you've heard of, but I'm not interested in the spotlight myself. After a long marriage that ended amicably, I'm rediscovering what it means to date — and I'd rather be honest about the dynamic upfront than pretend it doesn't exist.",
        "looking_for": "A warm, intelligent woman who enjoys the finer things without being defined by them. Someone discreet who understands that not everything needs to be on Instagram.",
        "offering": "Generosity, stability, and interesting dinner company. I can also introduce you to people who can open doors in entertainment, fashion, or media.",
        "ideal_first_date": "Nobu Malibu at sunset. Classic for a reason.",
        "arrangement_types": ["long_term", "mentorship", "dating"],
        "interests": ["fine_dining", "theater", "wine", "golf", "travel"],
        "income_range": "1m_5m", "ethnicity": "White / Caucasian",
        "drinking": "socially", "smoking": "never",
        "height_cm": 180, "relationship_status": "divorced", "availability": "evenings",
    },
    {
        "name": "David", "age": 45, "city": "San Francisco", "state": "California",
        "occupation": "Venture Capitalist", "education": "masters", "body_type": "average",
        "headline": "I invest in potential — in startups and in people",
        "bio": "Partner at a top-tier VC firm. I spend my days evaluating founders and my evenings wishing I had someone to cook dinner for. Yes, I cook. Yes, that surprises people. I'm looking for something real in a city that's forgotten how to date.",
        "looking_for": "An ambitious woman who has her own goals. I want to support your dreams, not replace them. Chemistry and intellectual connection are non-negotiable.",
        "offering": "Financial support, career mentorship, and a genuine relationship with someone who has nothing to prove. I'm generous with my time, money, and network.",
        "ideal_first_date": "I cook for you at my place in Pacific Heights. Bold move, but I'm a great cook.",
        "arrangement_types": ["mentorship", "long_term", "dating"],
        "interests": ["cooking", "investing", "travel", "reading", "hiking"],
        "income_range": "5m_10m", "ethnicity": "Asian",
        "drinking": "socially", "smoking": "never",
        "height_cm": 178, "relationship_status": "divorced", "availability": "flexible",
    },
    {
        "name": "Alexander", "age": 36, "city": "Chicago", "state": "Illinois",
        "occupation": "Hedge Fund Manager", "education": "masters", "body_type": "athletic",
        "headline": "Numbers by day, human connection by night",
        "bio": "I manage a $2B fund and my social life has suffered for it. I'm not looking for sympathy — I'm looking for someone who understands that success comes with trade-offs, and who wants to enjoy the upside with me.",
        "looking_for": "Someone who can keep up intellectually and doesn't need to be entertained 24/7. Independence is attractive. So is knowing what you want.",
        "offering": "A lifestyle most people only dream about. Monthly support, travel, experiences, and the attention of someone who doesn't give it easily.",
        "ideal_first_date": "Alinea. Three-star Michelin. If we can survive 18 courses together, we can do anything.",
        "arrangement_types": ["sugar_relationship", "experience_partner", "short_term"],
        "interests": ["fine_dining", "fitness", "investing", "sports", "travel"],
        "income_range": "over_10m", "ethnicity": "White / Caucasian",
        "drinking": "socially", "smoking": "never",
        "height_cm": 183, "relationship_status": "single", "availability": "weekends",
    },
    {
        "name": "Robert", "age": 48, "city": "Houston", "state": "Texas",
        "occupation": "Oil & Gas Executive", "education": "masters", "body_type": "average",
        "headline": "Old school values, new school generosity",
        "bio": "30 years in energy. I've built a life I'm proud of — beautiful home, good friends, meaningful work. What's missing is someone to share it with. My last relationship ended because she didn't understand the travel. I'm hoping to find someone who sees it as a feature, not a bug.",
        "looking_for": "A kind, genuine woman who appreciates stability and doesn't mind that I'll be in Dubai one week and Denver the next. Loyalty matters more to me than anything.",
        "offering": "Financial security, unwavering support, and someone who will always make sure you're taken care of. I'm traditional in the best ways.",
        "ideal_first_date": "Steak dinner at Pappas Bros. If you can appreciate a perfect ribeye, we'll get along just fine.",
        "arrangement_types": ["long_term", "sugar_relationship", "travel_companion"],
        "interests": ["golf", "travel", "fine_dining", "sports", "investing"],
        "income_range": "1m_5m", "ethnicity": "White / Caucasian",
        "drinking": "socially", "smoking": "never",
        "height_cm": 182, "relationship_status": "divorced", "availability": "travel_ready",
    },
    {
        "name": "Andre", "age": 40, "city": "Atlanta", "state": "Georgia",
        "occupation": "Real Estate Developer", "education": "bachelors", "body_type": "athletic",
        "headline": "Building the skyline, looking for my skyline view",
        "bio": "I develop commercial properties across the Southeast. My portfolio keeps me busy, but I always make time for the right person. Atlanta is my base, but I'm in Miami, Charlotte, or Nashville any given week. Looking for someone genuine.",
        "looking_for": "A beautiful, motivated woman who has her own thing going on. I don't want a dependent — I want a partner in enjoying life.",
        "offering": "Generosity, great experiences, and someone who follows through. I don't make promises I can't keep.",
        "ideal_first_date": "Dinner at Marcel, then drinks at a rooftop with a view of the city I'm building.",
        "arrangement_types": ["dating", "sugar_relationship", "long_term"],
        "interests": ["investing", "fitness", "fine_dining", "travel", "sports"],
        "income_range": "1m_5m", "ethnicity": "Black / African American",
        "drinking": "socially", "smoking": "never",
        "height_cm": 190, "relationship_status": "single", "availability": "flexible",
    },
    {
        "name": "Richard", "age": 55, "city": "Las Vegas", "state": "Nevada",
        "occupation": "Casino & Hospitality Owner", "education": "bachelors", "body_type": "average",
        "headline": "The house always wins — and so do the people I care about",
        "bio": "I own three hospitality businesses in Vegas. I've been in this town for 25 years and I know everyone worth knowing. I'm at the point in my life where money isn't the goal anymore — connection is. But I'm realistic about what I bring to the table and what I'm looking for.",
        "looking_for": "Someone young, vibrant, and honest. I've had enough pretenders. If you want a luxury lifestyle and you're willing to be genuine about it, we'll get along perfectly.",
        "offering": "VIP everything. Travel. Monthly support. And someone who's seen enough of life to treat you with the respect you deserve.",
        "ideal_first_date": "My private table at Delilah, then anywhere the night takes us.",
        "arrangement_types": ["sugar_relationship", "experience_partner", "short_term"],
        "interests": ["nightlife", "fine_dining", "golf", "travel", "wine"],
        "income_range": "over_10m", "ethnicity": "White / Caucasian",
        "drinking": "socially", "smoking": "occasionally",
        "height_cm": 178, "relationship_status": "divorced", "availability": "flexible",
    },
]

# Geocoder for lat/lon
CITY_COORDS = {
    "miami": (25.7617, -80.1918), "new york": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437), "las vegas": (36.1699, -115.1398),
    "chicago": (41.8781, -87.6298), "san francisco": (37.7749, -122.4194),
    "atlanta": (33.7490, -84.3880), "dallas": (32.7767, -96.7970),
    "houston": (29.7604, -95.3698), "seattle": (47.6062, -122.3321),
    "boston": (42.3601, -71.0589), "denver": (39.7392, -104.9903),
}


def random_dob(age: int) -> date:
    today = date.today()
    base = today.replace(year=today.year - age)
    offset = random.randint(-180, 180)
    return base + timedelta(days=offset)


async def download_photo(profile_id: int, index: int) -> str | None:
    """Download a random face from thispersondoesnotexist.com."""
    try:
        filename = f"seed_{profile_id}_{index}_{uuid.uuid4().hex[:8]}.jpg"
        filepath = UPLOAD_DIR / filename
        req = urllib.request.Request("https://thispersondoesnotexist.com", headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        filepath.write_bytes(resp.read())
        return f"/api/photos/file/{filename}"
    except Exception as e:
        print(f"  Photo download failed: {e}")
        return None


async def seed():
    async with async_session() as db:
        # First, mark all existing profiles as seed and deactivate them
        existing = await db.execute(select(Profile).where(Profile.is_seed == True))
        for p in existing.scalars().all():
            p.is_active = False
            p.is_hidden = True
        await db.flush()
        print("Deactivated old seed profiles")

        all_profiles = []

        # Create attractive female profiles
        for data in ATTRACTIVE_FEMALES:
            email = f"seed-{data['name'].lower()}-{random.randint(1000,9999)}@seed.getarranged.io"
            user = User(email=email, password_hash=hash_password("SeedProfile2026!"), user_type=UserType.ATTRACTIVE, is_verified=True)
            db.add(user)
            await db.flush()

            coords = CITY_COORDS.get(data["city"].lower(), (None, None))
            profile = Profile(
                user_id=user.id,
                display_name=data["name"],
                date_of_birth=random_dob(data["age"]),
                gender="female",
                headline=data["headline"],
                bio=data["bio"],
                city=data["city"],
                state=data["state"],
                latitude=coords[0],
                longitude=coords[1],
                occupation=data["occupation"],
                education=data["education"],
                body_type=data["body_type"],
                height_cm=data["height_cm"],
                looking_for=data["looking_for"],
                offering=data["offering"],
                ideal_first_date=data["ideal_first_date"],
                arrangement_types=data["arrangement_types"],
                interests=data["interests"],
                ethnicity=data["ethnicity"],
                drinking=data["drinking"],
                smoking=data["smoking"],
                relationship_status=data["relationship_status"],
                availability=data["availability"],
                lifestyle_expectation=data["lifestyle_expectation"],
                is_seed=True,
                is_photo_verified=True,
            )
            db.add(profile)
            await db.flush()
            all_profiles.append((profile, data["name"]))
            print(f"Created: {data['name']} ({data['city']}) - attractive")

        # Create successful male profiles
        for data in SUCCESSFUL_MALES:
            email = f"seed-{data['name'].lower()}-{random.randint(1000,9999)}@seed.getarranged.io"
            user = User(email=email, password_hash=hash_password("SeedProfile2026!"), user_type=UserType.SUGAR, is_verified=True)
            db.add(user)
            await db.flush()

            coords = CITY_COORDS.get(data["city"].lower(), (None, None))
            profile = Profile(
                user_id=user.id,
                display_name=data["name"],
                date_of_birth=random_dob(data["age"]),
                gender="male",
                headline=data["headline"],
                bio=data["bio"],
                city=data["city"],
                state=data["state"],
                latitude=coords[0],
                longitude=coords[1],
                occupation=data["occupation"],
                education=data["education"],
                body_type=data["body_type"],
                height_cm=data["height_cm"],
                looking_for=data["looking_for"],
                offering=data["offering"],
                ideal_first_date=data["ideal_first_date"],
                arrangement_types=data["arrangement_types"],
                interests=data["interests"],
                income_range=data["income_range"],
                ethnicity=data["ethnicity"],
                drinking=data["drinking"],
                smoking=data["smoking"],
                relationship_status=data["relationship_status"],
                availability=data["availability"],
                is_seed=True,
                is_photo_verified=True,
                is_income_verified=True,
            )
            db.add(profile)
            await db.flush()
            all_profiles.append((profile, data["name"]))
            print(f"Created: {data['name']} ({data['city']}) - successful")

        await db.commit()

        # Download photos (3 per profile)
        import time
        for profile, name in all_profiles:
            for i in range(3):
                url = await download_photo(profile.id, i)
                if url:
                    photo = Photo(
                        profile_id=profile.id,
                        url=url,
                        is_primary=(i == 0),
                        order=i,
                    )
                    db.add(photo)
                    print(f"  {name}: photo {i+1}/3")
                time.sleep(0.3)

        await db.commit()
        print(f"\nDone! Created {len(all_profiles)} profiles with photos.")


if __name__ == "__main__":
    asyncio.run(seed())
