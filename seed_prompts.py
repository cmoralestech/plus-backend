"""Give every seed profile its own prompt answers.

Background: bio, headline and looking_for were individualised earlier and are
200-distinct. ideal_first_date and offering were not — 200 profiles shared six
and seven values respectively, so Rafael and Tomás proposed word-identical first
dates. That was invisible while the fields rendered nowhere. Now that prompts
are shown on a profile and can be liked individually, the repetition is the most
obvious tell in the product.

Two rules held throughout:

- `offering` describes character, time and taste. Never money, allowances or
  anything payable. The whole platform's compliance position is that this is a
  dating service and not an escort service, and a field literally called
  "offering" is the first place a reviewer will look.
- Every answer is specific to that person's work and city. Generic lines are
  what made the original six so obvious.

Usage:
    python seed_prompts.py --batch 1 [--dry-run]
    python seed_prompts.py --all [--dry-run]
"""
import argparse
import asyncio
import sys

from sqlalchemy import select

from app.database import async_session
from app.models.profile import Profile

# id: (ideal_first_date, offering)

BATCH_1 = {
    2: ("Somewhere in Hialeah with plastic chairs and food worth the drive. I order, you argue with me about it.",
        "Sunday lunch for whoever turns up, and a table that always has room at it."),
    3: ("On the water before seven, coffee after. If you hate boats, say so now and we'll walk the Grove instead.",
        "I can fix almost anything you own, and I won't make you feel stupid for not knowing how."),
    4: ("Dinner somewhere quiet enough to actually hear you. I've had enough noise for one lifetime.",
        "Undivided attention when I'm off shift, which I guard carefully because there isn't much of it."),
    5: ("A long walk and worse coffee than we deserve, somewhere neither of us has been.",
        "Patience, a good ear, and the ability to tell when you're in pain before you mention it."),
    6: ("My own kitchen, after close. I cook, you keep me company, nobody takes a photo of the plate.",
        "Three kitchens that will always feed you, and a fairly ruthless sense of what's actually good."),
    7: ("Something visual — a show, a gallery, anywhere I can watch you notice things.",
        "An eye for detail and a habit of making ordinary rooms feel deliberate."),
    8: ("Drinks somewhere with a view I helped finance, so I can be insufferable about the skyline.",
        "Straight answers, a full diary I'll rearrange for the right person, and good taste in rooms."),
    9: ("Low tide at Bear Cut. I'll show you what's living in six inches of water and you'll never unsee it.",
        "Genuine curiosity, and enthusiasm for things most people walk past."),
    10: ("Somewhere with a runway view. Forty years in the air and I still look up.",
         "Stories that are true, patience earned the hard way, and a calm that doesn't rattle."),
    11: ("A small room with a good band and no talking during the set. Talk after.",
         "An ear for what's actually good, and the discipline that comes from a job with no shortcuts."),
    12: ("Somewhere Cuban, somewhere loud, where the argument at the next table is better than the television.",
         "Fierce loyalty, and a working knowledge of how to get things done through a system."),
    13: ("Dawn, before service. I'll have made something you won't get on a menu.",
         "Precision, early mornings, and the best thing you'll eat that week."),
    14: ("A walk through Coral Gables while I point at buildings and explain why they work.",
         "A considered opinion on nearly everything, and the patience to hear yours."),
    15: ("Something physical — paddleboards, a hike, anything better than sitting across a table performing.",
         "Consistency. I show up when I say I will, which is rarer than it should be."),
    16: ("Early dinner. I'm up at five and I'd rather be honest about that than yawn through dessert.",
         "Directness, a good eye, and no tolerance whatsoever for nonsense."),
    17: ("Somewhere new that nobody has posted about yet. I'll have found it first.",
         "Taste I'm confident about, and access to things before they're obvious."),
    18: ("Lunch, not dinner. I've done enough evenings that were really meetings.",
         "Time that is genuinely mine now, and the perspective of having built something and let it go."),
    19: ("Whatever's open at midnight when I get off. That's my evening, and I won't pretend otherwise.",
         "Honesty about who I am, and a complete absence of pretending to be anything else."),
    20: ("A boat that isn't mine, borrowed for an afternoon, with nothing to sell you.",
         "A life that runs on the water, and the good sense to know it's a job and not a personality."),
    21: ("Coffee between shifts. Twenty minutes of something that isn't a textbook.",
         "Ambition I'm not embarrassed about, and the energy to still be interested at the end of a long day."),
    22: ("Dinner and a genuine argument about something that matters. I've missed being disagreed with.",
         "Sixty years of judgement, and the confidence to say what I actually think."),
    23: ("Somewhere with no wifi. I'd like one evening where nobody can reach either of us.",
         "A quiet mind, dry humour, and the ability to fix your laptop without commentary."),
    24: ("Somewhere with air conditioning I didn't install, for once.",
         "A business that runs without me now, and the free time that finally bought."),
    25: ("Somewhere I haven't worked. That narrows it, but it's the only way I'll relax.",
         "The ability to make things happen quickly, and a phone full of people who owe me favours."),
    26: ("Sunday. It's the only day the hospital doesn't own, and I'd give it to the right person.",
         "Calm in genuine chaos, and an unusually clear sense of what actually matters."),
}

BATCH_2 = {
    27: ("Somewhere I can bring the dog. He's a good judge and I'd like his opinion.",
         "Softness that I don't apologise for, and a house that always has animals in it."),
    28: ("Early. I'm on site at six and I'd rather see you fresh than exhausted.",
         "Something built with my own hands to point at, and a very short tolerance for excuses."),
    29: ("Somewhere dark and cool. I stare at screens all day and my eyes need the break.",
         "Steadiness, and the ability to see what's wrong before anyone says it out loud."),
    30: ("A long lunch that runs into the afternoon because neither of us checked the time.",
         "Security, in the boring literal sense, and a good story about most things."),
    31: ("My night off, which is a Tuesday. If you can do Tuesdays we'll get along.",
         "I know everyone worth knowing in this city, and where to go after everything closes."),
    32: ("Somewhere calm. My working life is entirely other people's worst days.",
         "Complete composure, and a very high threshold for what counts as a crisis."),
    33: ("A gallery, then somewhere to sit and be rude about what we saw.",
         "An eye that notices, and the patience to make something until it's right."),
    34: ("Somewhere without a wine list four pages long. I'd rather talk than perform.",
         "Resources, discretion, and no need whatsoever to impress anyone in the room."),
    35: ("Sunrise on the beach, then breakfast. If that's too early we may want different things.",
         "Presence, patience, and a genuinely steady temperament."),
    36: ("Anywhere I don't have to fix the service afterwards. I can't switch it off.",
         "Every restaurant door in this city, and the sense not to make a thing of it."),
    37: ("A Saturday morning, before the day gets away. I'm asleep by nine on a school night.",
         "Kindness that isn't performance, and infinite patience for people learning things slowly."),
    38: ("Somewhere I can't see a single piece of my own work. Harder than it sounds.",
         "A business I built, an eye for what will land, and the ability to close a laptop."),
    39: ("A walk. I spend all day telling people to move more and I should take my own advice.",
         "Good hands, real patience, and interest in how you're actually doing."),
    40: ("Lunch somewhere unhurried. I did thirty years of hurried and I'm finished with it.",
         "A lifetime of children's questions, so nothing you ask will surprise me."),
    41: ("A show, somewhere small. I want to see what you do when the bass is too loud.",
         "A studio at odd hours, and an ear that hears what a room is missing."),
    42: ("Dinner somewhere I'm not billing by the hour, which is most of my life.",
         "A very sharp read on any contract you're handed, and evenings I now protect."),
    43: ("Somewhere with a proper cocktail list. I'd like one problem I can't model.",
         "Rigour, curiosity, and the willingness to change my mind when the evidence does."),
    44: ("My own hotel bar, which is cheating, but the service will be flawless.",
         "Anticipating what you need before you ask. It's the job, and it doesn't switch off."),
    45: ("Whatever city we're both in. I'll be honest, that's the hard part.",
         "A world that's smaller than most people's, and the ability to disappear into it with you."),
    46: ("Dinner on a night I'm not flying, which I'll know about weeks ahead.",
         "Reliability at work, spontaneity outside it, and a genuinely good sense of where to go."),
    47: ("Somewhere I can laugh loudly without anyone minding.",
         "Easy company, and the good sense not to take much of it too seriously."),
    48: ("A drive. Any car you like, I'll bring two and you pick.",
         "Generosity that's genuinely enjoyable to be around, and no interest in being thanked for it."),
    49: ("Somewhere structurally interesting. I know how that sounds. Come anyway.",
         "Precision, dependability, and an explanation for why anything is standing up."),
    50: ("Nothing scheduled. I ran on a calendar for fifteen years and I'm done with it.",
         "Time that's finally mine, and the freedom to spend it on something worthwhile."),
    51: ("Something active, then food. That's my whole personality and I've made peace with it.",
         "Fixing what hurts, and the discipline to keep showing up when it's boring."),
}

BATCH_3 = {
    52: ("Somewhere with people from six countries at the next four tables.",
         "A network that spans continents, and stories from most of them."),
    53: ("Your favourite room in your own home. I'd learn more there than over dinner.",
         "An eye for how a space should feel, and restraint about saying so uninvited."),
    54: ("A steak and a real conversation. I'm too old to pretend I want anything else.",
         "Decades of judgement about people, and the bluntness that comes with it."),
    55: ("Something outdoors, ideally after a run of night shifts, to remind me the sun exists.",
         "Competence under pressure, and warmth that survives a twelve-hour shift."),
    56: ("An opening, then somewhere quiet to say what we actually thought.",
         "A room full of work I chose, and an eye trained over thirty years."),
    57: ("Golden hour, somewhere with good light. Occupational hazard.",
         "Seeing you as you actually are, and the patience to wait for the right moment."),
    58: ("Somewhere where nothing is on a schedule and nothing needs tracking.",
         "A business that moves things across the world, and total calm when it doesn't."),
    59: ("A slow morning. My work is other people's big evenings and I like the opposite.",
         "Making people feel good about themselves, which turns out to be a transferable skill."),
    60: ("Somewhere I can sit with my back to a wall. I know. It's the job.",
         "A very literal sense of safety, and discretion I've never had to be asked for."),
    61: ("A gallery I can't afford, then the cheapest coffee nearby.",
         "Enthusiasm I haven't had knocked out of me yet, and time on a Tuesday afternoon."),
    62: ("Dinner, late, after rounds. It's the only reservation I can keep.",
         "Steadiness, and expertise you'd want in your corner on a bad day."),
    63: ("Dancing, obviously. I'll be kind about your rhythm for the first ten minutes.",
         "Joy that's hard to fake, and the ability to get anyone onto a floor."),
    64: ("Somewhere nobody will ask me about interest rates.",
         "A very clear head about money, and the discretion never to discuss yours."),
    65: ("A wine I choose, that you've never heard of, that you'll like more than you expect.",
         "A palate worth borrowing, and no snobbery about using it."),
    66: ("Somewhere with genuinely good lighting. I look at faces all day; it's a curse.",
         "Attention to detail, and a schedule that ends at five."),
    67: ("The water at first light. I'll bring the coffee and the binoculars.",
         "Conviction about something bigger than either of us, and the sea as a second home."),
    68: ("Somewhere with no press, no photos, and nobody I have to be pleasant to.",
         "Knowing exactly how a thing will be received, and how to keep it out of the room."),
    69: ("A weekday, off-shift. I work a rota, so ordinary evenings are the treat.",
         "Physical courage, emotional steadiness, and no drama at all in a real emergency."),
    70: ("Lunch. Long. I spent thirty years eating standing up.",
         "Perspective, a good address book, and no remaining need to prove anything."),
    71: ("Somewhere I can hear you properly. Professional interest and personal preference.",
         "Real listening, and infinite patience with anyone finding words hard."),
    72: ("A building site at the end of the day, when it's quiet and you can see the shape of it.",
         "Vision for what a place could be, and the money and nerve to find out."),
    73: ("Something with our hands — pottery, cooking, anything but sitting and talking about ourselves.",
         "Adapting to whatever you need, which is the entire job, and patience for slow progress."),
    74: ("A ride out to the Keys. I'll fix your bike first and pretend it was nothing.",
         "A simple life that works, and no interest in complicating it."),
    75: ("Somewhere I can't open a textbook. I need someone to physically stop me.",
         "Ambition, argument, and the ability to construct a case for anything."),
    76: ("Dinner, booked weeks out, that I will genuinely protect from the calendar.",
         "Resources, and the increasingly rare decision to spend time rather than earn it."),
}

BATCH_4 = {
    77: ("Somewhere light. My working days are heavy and I'd like the evening not to be.",
         "Real empathy, and a spine underneath it that most people miss."),
    78: ("Coffee. Twenty minutes, and if it's good we ruin the rest of the day's schedule.",
         "Reading people quickly, and a business that runs whether or not I'm in the room."),
    79: ("After service, wherever's still open. That's when my day starts.",
         "Cooking for you properly, and the honesty of a trade with no shortcuts."),
    80: ("Somewhere near the port. I like watching things arrive.",
         "Steadiness, and a business that has survived every bad year so far."),
    81: ("A house I'm showing, before it sells. Best rooms in the city, briefly.",
         "Knowing this city street by street, and being genuinely useful with it."),
    82: ("A drive somewhere with no destination. I have the cars for it.",
         "Flexibility, generosity, and never making a fuss about either."),
    83: ("Somewhere well-designed enough that I'll stop critiquing it out loud.",
         "Noticing what's broken, and the patience to make it better quietly."),
    84: ("Anywhere at all. Genuinely — my week is so constrained that I've stopped having preferences.",
         "Absolute reliability in a crisis, and complete honesty about how little time I have."),
    85: ("Somewhere I'm not looking at the back of someone's head.",
         "Making people feel looked after, and hearing everything without repeating any of it."),
    86: ("Somewhere cheap and good. I'd rather the money went elsewhere.",
         "Caring about something beyond myself, and the stamina to keep at it."),
    87: ("A walk through a neighbourhood neither of us knows, arguing about the buildings.",
         "Seeing how things fit together, in buildings and otherwise."),
    88: ("Lunch somewhere unhurried, then whatever the afternoon suggests.",
         "Time, patience, and forty years of watching people make the same mistakes."),
    89: ("Something cheap and fun. I'm three years into an apprenticeship and honest about it.",
         "Turning up, learning fast, and no pretence about where I am in life."),
    90: ("Somewhere with good paper stock. I'm joking. Mostly.",
         "A steady business, an eye for craft, and evenings that are actually free."),
    91: ("I'll cook. It's the only thing I'm reliably better at than most people.",
         "Feeding you properly, and finding out what you like without being told."),
    92: ("Somewhere with nothing to do with teeth.",
         "Precision, dependability, and a workshop that makes things fit perfectly."),
    93: ("Up in a small plane at sunrise. If you'd hate that, I'd like to know early.",
         "Calm at altitude, and the ability to teach anything without condescension."),
    94: ("A long dinner and a proper disagreement. I miss cross-examination.",
         "Judgement, argument, and forty years of hearing what people really mean."),
    95: ("A penthouse I'm listing, at sunset, before the buyers see it.",
         "Knowing what a place is worth and what it's actually like to live in."),
    96: ("Something that doesn't involve standing. I'm on my feet nine hours a day.",
         "Skill under pressure, and being fully present the moment I'm out of theatre."),
    97: ("Somewhere I can ask too many questions without being told I'm working.",
         "Genuine curiosity, and the habit of finding out what's actually going on."),
    98: ("Outdoors, obviously. I'd rather be in a garden than a restaurant.",
         "Building things that grow, and the patience that requires."),
    99: ("A film, then an argument about the sound design that you'll regret starting.",
         "Hearing what nobody else does, and long uninterrupted hours to spend on it."),
    100: ("Somewhere I'm not counting vehicles.",
          "A business that runs itself now, and the time that finally freed up."),
    101: ("Somewhere quiet after a day of talking. I'll have used my words up.",
          "Reliability, and a genuinely encyclopaedic memory for the details of your life."),
}

BATCH_5 = {
    102: ("Somewhere with real food after a rotation. I've eaten enough camp catering.",
          "Long stretches away, then complete presence when I'm home. It suits some people."),
    103: ("Breakfast after nights. My evening is your morning, and that's negotiable but honest.",
          "Composure in an actual emergency, and warmth that survives twelve-hour shifts."),
    104: ("Somewhere I can't hear a machine running.",
          "Making things properly, and a business built one contract at a time."),
    105: ("Dinner somewhere with no small talk about dentistry.",
          "A practice I own, evenings that are genuinely mine, and a very steady hand."),
    106: ("Somewhere with clean air and no alarms.",
          "Absolute calm when something goes wrong, which is the whole job."),
    107: ("Coffee between clinics. Short, but I'll be entirely there for it.",
          "Reading people quickly, and the patience to explain anything twice."),
    108: ("Lunch, unhurried. Forty years of shift work bought me that.",
          "A pension, a passport, and no remaining interest in impressing anyone."),
    109: ("My own dining room after close, when the chairs are up and the kitchen's mine.",
          "Feeding people well, and knowing everyone in this business worth knowing."),
    110: ("Dinner late, after rounds, on a night that isn't on call.",
          "Steadiness, and expertise you'd want on your worst day."),
    111: ("Outdoors somewhere with a view worth measuring.",
          "Precision, early starts, and a great deal of time spent thinking alone."),
    112: ("Somewhere nothing is arriving or departing.",
          "A business that moves across state lines, and total calm when it stops."),
    113: ("Somewhere with no queue and nobody asking me about interactions.",
          "Care taken seriously, and complete discretion about everything I know."),
    114: ("A long lunch. I've spent my life on other people's worst days.",
          "Security in the literal sense, and a very clear head about risk."),
    115: ("Cheap, good, and near campus. I'm a student and I'd rather be honest about it.",
          "Curiosity, energy, and a mind that hasn't been worn down yet."),
    116: ("Somewhere I can point at the sky and be boring about it.",
          "Thirty years of solving problems nobody had solved before, and the patience it taught."),
    117: ("Somewhere without wifi. I'd like one evening off-grid.",
          "A quiet mind, dry humour, and total reliability."),
    118: ("My own chair, after hours. Best conversation in Houston happens in it.",
          "Knowing this neighbourhood completely, and being trusted by all of it."),
    119: ("Somewhere I can bring a dog, ideally yours.",
          "Steady hands, real compassion, and the ability to stay calm while everyone else panics."),
    120: ("Drinks somewhere high enough to see what I've financed.",
          "Straight answers, resources, and a diary I'll rearrange for the right person."),
    121: ("A concert, anything live. I'd like to watch you listen.",
          "Patience with beginners, and genuine joy in watching someone get better."),
    122: ("Six in the morning on a site, before the noise starts.",
          "Something built to point at, and no tolerance at all for excuses."),
    123: ("Somewhere I can eat properly. Welding burns more than people think.",
          "A trade that can't be outsourced, and complete honesty about who I am."),
    124: ("Somewhere with no queue of cars.",
          "A business that runs without me, and the free time that bought."),
    125: ("Somewhere light. My days are heavy enough.",
          "Real empathy, and considerably more steel underneath than people expect."),
    126: ("Somewhere calm. My work is entirely other people's fear.",
          "Complete composure, and a very high bar for what counts as a crisis."),
}

BATCH_6 = {
    127: ("Your favourite room in your own house. I'd learn more there than at dinner.",
          "An eye for how a room should feel, and the restraint not to redesign yours."),
    128: ("Somewhere the phone won't ring about a breakdown in Amarillo.",
          "A business built truck by truck, and a very clear sense of what things cost."),
    129: ("Somewhere with actual daylight. I spend my day in a dark room.",
          "Seeing what's wrong before anyone says it, and the discretion never to repeat it."),
    130: ("A long dinner and a genuine argument. I miss being disagreed with.",
          "Forty years of judgement, and the confidence to say what I actually think."),
    131: ("Somewhere I'm not catering. Anywhere. I'll cry with relief.",
          "Feeding a room properly, and knowing exactly how much work goes into looking effortless."),
    132: ("Lunch, unhurried, on a weekday because I finally can.",
          "A working life finished honourably, and the time that came after it."),
    133: ("Somewhere outdoors after a week of fluorescent lighting.",
          "Practical care, and noticing when someone's struggling before they say so."),
    134: ("Somewhere with rocks worth looking at, which I accept is a narrow interest.",
          "Reading what's underneath, and the patience of a job measured in decades."),
    135: ("Somewhere I'm not quoting on a repair.",
          "Fixing what other people write off, and being straight about the price."),
    136: ("Somewhere nobody mentions the word deductible.",
          "Order, discretion, and a very clear head about money that isn't mine."),
    137: ("Somewhere quiet after a shift on the ward. I'll have used my patience up.",
          "Gentleness under real pressure, and a completely unshockable temperament."),
    138: ("Somewhere I'm not under a sink.",
          "A trade that will never disappear, and total reliability about turning up."),
    139: ("Anywhere with a building worth arguing about. I'll have strong views and a pencil.",
          "Ambition, strong opinions, and the willingness to defend both."),
    140: ("Out on the land at dusk. It's the best hour and it's not close.",
          "Space, quiet, and a life that runs on seasons rather than quarters."),
    141: ("Somewhere I haven't produced an event. Getting harder every year.",
          "Making things happen quickly, and a phone full of people who owe me a favour."),
    142: ("Somewhere with no rota to fill.",
          "A company I built from nothing, and a very good read on people."),
    143: ("Somewhere with something well-engineered to look at.",
          "Solving things properly the first time, and explaining how without condescension."),
    144: ("Something active, then a proper meal. That's the whole day, ideally.",
          "Discipline that's genuinely enjoyable to be around, and gyms that keep me free by four."),
    145: ("A walk. I tell people to move more all day and rarely take my own advice.",
          "Getting people back to what they thought they'd lost, and the stubbornness that needs."),
    146: ("Somewhere with no screens. I watch six of them for a living.",
          "Nerve, resources, and the ability to stop thinking about the market at seven."),
    147: ("Somewhere with no children in it. I say that with enormous love.",
          "Endless patience, and a business that matters to two hundred families."),
    148: ("A Saturday morning, unhurried, the way they were always meant to be.",
          "Forty years of children's questions, and total unflappability."),
    149: ("After service, wherever's open. That's when my day begins.",
          "A kitchen of my own, strange hours, and the best meal you'll have that month."),
    150: ("Somewhere nothing needs restarting.",
          "Fixing what's broken calmly, and a business that finally runs itself."),
    151: ("Cheap and quick between rotations. I have about ninety free minutes a week.",
          "Ambition I won't apologise for, and complete honesty about how little time I have."),
}

BATCH_7 = {
    152: ("Outdoors, in the sun, which is professionally on-brand.",
          "Building something that outlasts me, and conviction about why it matters."),
    153: ("Something cheap and good. I'm an apprentice and I'd rather say so.",
          "A trade worth finishing, four years of it left, and complete honesty about that."),
    154: ("Somewhere with nothing on a pallet.",
          "A business built on being reliable for thirty years, and no drama whatsoever."),
    155: ("Somewhere I can talk without a mask on.",
          "Easy company, hearing everything, and repeating none of it."),
    156: ("Lunch, long, on a weekday. I earned it.",
          "A finished career, a full passport, and no need to impress anyone."),
    157: ("Somewhere I'm not looking at hands.",
          "Making people feel good about themselves, and an excellent ear for a story."),
    158: ("A garden, mine or anyone's. It's where I think.",
          "Growing things slowly, and the patience that teaches."),
    159: ("Midnight, when I get off. That's my evening and I won't pretend otherwise.",
          "Honesty about my hours, and cooking for you properly on the one day I'm free."),
    160: ("Somewhere with no radar and no traffic.",
          "Thirty years of staying calm while everything happened at once."),
    161: ("A weekday off-rota. Ordinary evenings are the treat.",
          "Steadiness in a real emergency, and no drama about anything smaller."),
    162: ("Somewhere clean. My working life is not.",
          "A business nobody expects to be lucrative, and the freedom it bought."),
    163: ("Somewhere I'm not mediating anything.",
          "Reading a room instantly, and complete discretion about what I find there."),
    164: ("Somewhere I can't hear a grinder.",
          "Making things exactly right, and a workshop that's mine outright."),
    165: ("Somewhere with no pallets and no clipboards.",
          "Keeping a hundred moving parts straight, and staying calm when they aren't."),
    166: ("Somewhere with nothing living in the walls. Professional preference.",
          "A steady business, an unshockable temperament, and good stories."),
    167: ("Somewhere I can hear you properly. Professional habit and personal preference.",
          "Real listening, and endless patience with anyone finding words hard."),
    168: ("Lunch, unhurried, after thirty years of eating standing up.",
          "Perspective, a good address book, and nothing left to prove."),
    169: ("Something physical, then food. It's my whole personality; I've made peace with it.",
          "Consistency, and showing up when I say I will."),
    170: ("Somewhere with good paper. I know how that sounds.",
          "A craft business, an eye for detail, and evenings that are genuinely free."),
    171: ("Somewhere with the lights already working.",
          "A trade that can't be outsourced, and turning up when I say I will."),
    172: ("Somewhere without a laptop in sight.",
          "Pipelines that run overnight so my evenings don't, and dry humour about it."),
    173: ("Anywhere that lets animals in. I'm better with them than with menus.",
          "Compassion, steady hands, and staying calm while everyone else doesn't."),
    174: ("Somewhere I can sit with my back to a wall. It's the job.",
          "A literal sense of safety, and discretion I've never had to be asked for."),
    175: ("Cheap and good. First graduate job, and I'd rather be honest about the budget.",
          "A degree just finished, a career just starting, and no pretence about either."),
    176: ("Somewhere nobody wants to negotiate.",
          "Reading people fast, and a business that runs whether I'm there or not."),
}

BATCH_8 = {
    177: ("Somewhere I'm not modelling anything.",
          "Rigour about numbers, and the discretion never to discuss yours."),
    178: ("Somewhere already cool, where I'm not quietly judging the ductwork.",
          "A trade that people call in August, and the security that comes with it."),
    179: ("Breakfast after nights. My hours are strange and I'd rather say so now.",
          "Calm at three in the morning, and a very high threshold for panic."),
    180: ("Somewhere with a roof I'm not assessing.",
          "Hard work that shows, and complete straightness about what things cost."),
    181: ("A small room with a good band and no talking during the set.",
          "An ear for what's missing, and long strange hours to spend on it."),
    182: ("Somewhere with nothing to inspect.",
          "Forty years of noticing what other people walked past."),
    183: ("Somewhere nobody asks me about engagement rates.",
          "Knowing how a thing will land, and the sense to keep quiet about it."),
    184: ("Somewhere I'm not checking the stock.",
          "Feeding half this city without anyone knowing my name, and being fine with that."),
    185: ("Somewhere I can get the grease off first, then relax.",
          "Fixing what others write off, and honesty about the bill."),
    186: ("Somewhere with nothing in storage.",
          "A quiet business, no drama, and considerably more time than people assume."),
    187: ("Somewhere I'm not waiting on results.",
          "Patience measured in years, and genuine belief that the work matters."),
    188: ("On dry land, ideally. I get enough of the other thing.",
          "Nerve, long absences, and complete presence when I'm actually here."),
    189: ("Somewhere I'm not looking at the back of a head.",
          "Making people feel like themselves, and hearing everything without repeating it."),
    190: ("Somewhere with no ships to schedule.",
          "Thirty-five years of moving things that had to arrive, and the calm that built."),
    191: ("Somewhere with more than one language happening at once.",
          "Hearing what's actually meant, in any of four languages."),
    192: ("Lunch, long and unhurried. I ran a ward for thirty years.",
          "Organising anything, and infinite patience with people at their worst."),
    193: ("A Saturday morning, before the day disappears. I'm asleep by nine on a school night.",
          "Kindness that isn't performance, and endless patience with slow progress."),
    194: ("Somewhere I'm not counting cases.",
          "A business built route by route, and no interest in pretending it's glamorous."),
    195: ("Something with our hands, rather than sitting and performing at each other.",
          "Adapting to what you need, which is the job, and patience for slow progress."),
    196: ("Somewhere I can't hear a lathe.",
          "Making things to a thousandth of an inch, and applying that to most of life."),
    197: ("Somewhere with good light. Occupational preoccupation.",
          "Noticing detail, and a working week that genuinely ends on Friday."),
    198: ("Somewhere quiet. My work is loud in every sense.",
          "Nerve, long rotations, and complete presence in between them."),
    199: ("Coffee between shifts and lectures. Twenty minutes of something that isn't a textbook.",
          "Ambition I'm not embarrassed about, and energy left at the end of a long day."),
    200: ("Somewhere already clean.",
          "A business built at five in the morning, and no illusions about hard work."),
    201: ("A walk. I tell people to move more all day and should take my own advice.",
          "Rehabilitating what people were told to live with, and the patience that takes."),
}

BATCHES = {
    1: BATCH_1, 2: BATCH_2, 3: BATCH_3, 4: BATCH_4,
    5: BATCH_5, 6: BATCH_6, 7: BATCH_7, 8: BATCH_8,
}


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
        for pid, (ideal_first_date, offering) in content.items():
            p = found.get(pid)
            if not p:
                continue
            # The guard that matters. These ids came from a seed export, but an
            # id is a weak identifier — a deleted seed and a new signup can leave
            # a real member sitting on one. Overwriting a real profile's words
            # would be unrecoverable.
            if not p.is_seed:
                print(f"  SKIPPED {pid}: not a seed profile — refusing to overwrite a real member")
                continue
            p.ideal_first_date = ideal_first_date
            p.offering = offering
            changed += 1

        if dry_run:
            print(f"  batch {batch_no}: would update {changed} profiles (dry run, nothing written)")
            await db.rollback()
        else:
            await db.commit()
            print(f"  batch {batch_no}: updated {changed} profiles")

    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=int, help="Batch number to apply")
    parser.add_argument("--all", action="store_true", help="Apply every batch")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    args = parser.parse_args()

    if args.all:
        for n in sorted(BATCHES):
            await apply_batch(n, args.dry_run)
        return 0

    if args.batch:
        return await apply_batch(args.batch, args.dry_run)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
