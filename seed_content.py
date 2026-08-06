"""Replace templated seed-profile copy with distinct content, one batch at a time.

The original seeder reused a small pool: 200 profiles shared 30 bios, 40
headlines and 10 "looking for" lines, so one bio appeared 14 times and one
"looking for" appeared 28 times. Five profiles were called Harry. Scrolling
Discover, the repetition is obvious within about four cards, which is worse
than an empty feed — it reads as a platform padding its numbers.

These are labelled in the UI as example profiles and cannot be liked or
messaged. The point of the rewrite is that a demonstration should look like
the product working, not like a mail merge.

Run per batch so the copy can be reviewed before the next one:

    python seed_content.py --batch 1
    python seed_content.py --batch 1 --dry-run

Idempotent: applying a batch twice writes the same values.
"""
import argparse
import asyncio
import sys

from sqlalchemy import select

from app.database import async_session
from app.models.profile import Profile

# id: (display_name, occupation, headline, bio, looking_for)
BATCH_1 = {
    2: ("Rafael", "Port logistics director",
        "Grew up in Hialeah, still eat lunch there",
        "Thirty years moving freight through Port Miami and I still get a small thrill watching a ship come in. Divorced, two daughters in college, one very opinionated dog. I cook Sunday lunch for whoever shows up.",
        "Someone who tells me the truth even when it's inconvenient."),
    3: ("Tomás", "Marine mechanic",
        "I fix the boats you post photos on",
        "Coconut Grove, born and raised. I work with my hands and I'm better at it than most people are at anything. Weekends I'm usually on the water or asleep. I read more than people expect.",
        "Someone with their own thing going on who still makes time."),
    4: ("Dev", "Cardiologist",
        "Long shifts, short patience for small talk",
        "I moved here from Chicago for the weather and stayed for everything else. Baptist Health most days. I run at 5am not because I'm disciplined but because it's the only hour nobody needs me.",
        "Real conversation. I'd rather one good evening than five polite ones."),
    5: ("Camila", "Physical therapist",
        "Brickell, but I miss Bogotá constantly",
        "I put people back together after surgery, which means I'm patient and slightly bossy. I dance badly and enthusiastically. My friends call me when something breaks, emotionally or otherwise.",
        "Someone kind who's also funny. The order matters."),
    6: ("Marisol", "Owns three restaurants",
        "I feed people for a living and love for a hobby",
        "Twenty-two years in Miami kitchens, the last nine running my own. Widowed four years. My kids are grown and mildly horrified I'm dating. I'm up at four and asleep by nine, which narrows the field.",
        "Someone who's built something too and doesn't need me to explain why I work this hard."),
    7: ("Yaz", "Set designer",
        "I build the rooms you see in commercials",
        "Wynwood studio, too many houseplants. I'm Cuban on my mother's side and it's the loud half. I like early mornings, bad horror films, and being convinced of things I initially disagreed with.",
        "Curiosity. If you have a subject you can't shut up about, I want to hear it."),
    8: ("Warren", "Commercial real estate",
        "Fifty-two and finally comfortable saying what I want",
        "I develop mixed-use in the Design District. Two failed marriages taught me I'm not easy, just honest about it now. I collect records and I'm insufferable about it. Ask me anything.",
        "Someone direct. I've run out of appetite for guessing."),
    9: ("Andrés", "Grad student, marine biology",
        "I count fish for science and it's better than it sounds",
        "Twenty-three, at RSMAS, broke in the specific way that graduate students are. I dive four days a week. I can talk about coral until people leave the room and I've made peace with that.",
        "Someone who finds enthusiasm attractive rather than exhausting."),
    10: ("Peter", "Retired airline captain",
        "Thirty years of takeoffs, now I mostly garden",
        "Flew widebodies out of MIA until 2023. Now I grow mangoes badly and travel for pleasure instead of pay. Two grown sons, one grandchild, plenty of time and finally no schedule.",
        "Company. Someone to eat dinner with who has stories of their own."),
    11: ("Kofi", "Sound engineer",
        "I mix records in a room with no windows",
        "Little Haiti studio. I work nights, which ruins most social lives but suits mine. Ghanaian family, Miami accent. I'm calmer than my job suggests and I hold a grudge about very few things.",
        "Someone patient with odd hours who has their own life during the day."),
    12: ("Lucía", "Immigration attorney",
        "I argue for a living and try not to at home",
        "Twelve years of asylum work. It's heavy and I love it. Divorced, no kids by choice. I need someone who doesn't flinch when I talk about my day, or who knows when to change the subject.",
        "Steadiness. Somebody whose mood I don't have to manage."),
    13: ("Bea", "Pastry chef",
        "Awake at 3am, asleep by 8pm, sorry",
        "I run the bakery program at a hotel on the beach. Brazilian, though I've been here longer than there now. My schedule is antisocial and my croissants are excellent. I think it's a fair trade.",
        "Someone with early mornings of their own, or the patience for mine."),
    14: ("Elias", "Architect",
        "I design buildings I mostly can't afford to live in",
        "Thirty-four, my own small practice, three people and a lot of coffee. I sketch constantly. I'm told I'm quiet until I'm suddenly not. I'd rather walk a neighbourhood than sit in a restaurant.",
        "Someone who likes walking and doesn't need every silence filled."),
    15: ("Junior", "Personal trainer",
        "Yes, I'm the cliché. I'm also good at it.",
        "Twenty-five, South Beach, I train people who are serious and a few who aren't. I read philosophy on the bus, which nobody believes. I'm cheerful in a way that annoys my friends.",
        "Someone who takes something seriously. Doesn't matter what."),
    16: ("Renata", "Dermatologist",
        "Coral Gables, two cats, one ex-husband",
        "Forty-two and I like my life, which I'm told is intimidating. My practice keeps me busy and my friends keep me honest. I want company, not rescuing. I'm a very good cook and a terrible gardener.",
        "Someone secure enough that my life not needing fixing isn't a problem."),
    17: ("Naomi", "Fashion buyer",
        "I fly to Milan and see the inside of showrooms",
        "Twenty-eight, work sends me away a lot, which suits me. I'm from Kingston originally. I want someone who has plans when I'm gone rather than waiting. I'm blunt and I'll ask directly.",
        "Independence. Someone whose week isn't organised around mine."),
    18: ("Diane", "Sold her logistics company",
        "I worked very hard for a long time and then stopped",
        "Fifty-two. Sold the business in 2024 and I'm still learning what to do with a Tuesday. Divorced amicably. I sail, badly. I'd like to be surprised by someone at this stage rather than reassured.",
        "Someone interesting. I have enough comfort and not enough surprise."),
    19: ("Malik", "Line cook",
        "I work in a kitchen you've probably eaten in",
        "Twenty-six, Overtown, working my way up and it's slow. I'm ambitious in the boring way — showing up early. Days off I sleep and cook for my grandmother. I'm shy for about ten minutes.",
        "Someone who works hard too and gets why I'm tired on Sundays."),
    20: ("Julian", "Yacht brokerage",
        "I sell boats. It's less glamorous than it looks.",
        "Forty, divorced, one son who's twelve and funnier than me. Coconut Grove. I'm on the water constantly and genuinely never bored of it. I've stopped pretending to like clubs.",
        "Someone who'd rather be outside than out."),
    21: ("Sof", "Nursing student",
        "Twenty-two and permanently studying",
        "FIU, two years in, working at a coffee place to pay for it. I'm from Doral. I'm loud with my friends and quiet with everyone else until I'm not. I want to be a paediatric nurse.",
        "Someone patient. My schedule is a disaster for another two years."),
    22: ("Elaine", "Retired judge",
        "Thirty years on the bench, now reading for pleasure",
        "Fifty-three and recently retired, which everyone tells me was early. Widowed. I have strong opinions and I enjoy being argued with by someone who's done the reading. I walk five miles a day.",
        "Conversation. Genuinely, that's the whole list."),
    23: ("Priya", "Software engineer",
        "I work remote and forget to go outside",
        "Thirty-two, backend engineer, moved here from Austin for the winters. I'm quieter than most people in this city and I've made peace with that. I bake when stressed, so my colleagues eat well.",
        "Someone who doesn't think staying in is a wasted evening."),
    24: ("Hank", "Owns an HVAC company",
        "Not fancy. Built it from one van.",
        "Fifty-two, thirty-eight employees, started with a van and a loan from my uncle. Divorced a long time ago. I'm straightforward and I don't play games because I genuinely don't know how.",
        "Someone honest. I'd rather hear no than be managed."),
    25: ("Valentina", "Event producer",
        "I run the parties, I don't attend them",
        "Twenty-seven, I produce corporate events and weddings, which means I'm calm in a crisis and useless at relaxing. Venezuelan family, Kendall. My friends are my whole personality and I'm fine with it.",
        "Someone steady. My job is chaos and I don't want it at home."),
    26: ("Grace", "Hospital administrator",
        "I run a department and a household, badly, simultaneously",
        "Forty-five, two teenagers, one very demanding job at Jackson. Divorced three years and only now actually ready. I'm organised at work and a disaster at home. I laugh loudly.",
        "Someone patient with the fact that my kids come first, without resenting it."),
}

BATCHES = {1: BATCH_1}


async def apply_batch(batch_no: int, dry_run: bool) -> int:
    content = BATCHES.get(batch_no)
    if not content:
        print(f"No batch {batch_no}. Available: {sorted(BATCHES)}")
        return 1

    async with async_session() as db:
        rows = (await db.execute(
            select(Profile).where(Profile.id.in_(list(content)))
        )).scalars().all()
        found = {p.id: p for p in rows}

        missing = set(content) - set(found)
        if missing:
            print(f"  warning: no profile for ids {sorted(missing)}")

        changed = 0
        for pid, (name, occupation, headline, bio, looking_for) in content.items():
            p = found.get(pid)
            if not p:
                continue
            if not p.is_seed:
                print(f"  SKIPPED {pid}: not a seed profile — refusing to overwrite a real member")
                continue
            p.display_name = name
            p.occupation = occupation
            p.headline = headline
            p.bio = bio
            p.looking_for = looking_for
            changed += 1
            if dry_run:
                print(f"  [dry-run] {pid}: {name} — {headline}")

        if dry_run:
            print(f"\n{changed} profiles would be updated. Nothing written.")
            await db.rollback()
        else:
            await db.commit()
            print(f"\n{changed} profiles updated.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.exit(asyncio.run(apply_batch(args.batch, args.dry_run)))
