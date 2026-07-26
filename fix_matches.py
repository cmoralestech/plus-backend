"""Fix: create matches and conversations for seed data."""
import asyncio
from datetime import datetime, timedelta
from app.database import async_session
from app.models.match import Like, Match
from app.models.message import Conversation, Message
from app.models.profile import Profile
import sqlalchemy


async def main():
    async with async_session() as db:
        r = await db.execute(sqlalchemy.select(Profile))
        profiles = {p.display_name: p.id for p in r.scalars().all()}

        # Clear existing matches/convos/messages
        await db.execute(sqlalchemy.text("DELETE FROM messages"))
        await db.execute(sqlalchemy.text("DELETE FROM conversations"))
        await db.execute(sqlalchemy.text("DELETE FROM matches"))
        await db.execute(sqlalchemy.text("DELETE FROM likes"))
        await db.commit()

        pairs = [
            ("Sophia", "James"),
            ("Sophia", "William"),
            ("Emma", "Robert"),
            ("Emma", "Michael"),
            ("Charlotte", "James"),
            ("Mia", "David"),
            ("Ava", "Marcus"),
            ("Isabella", "Alexander"),
            ("Luna", "Richard"),
            ("Valentina", "Vincent"),
            ("Natalie", "Thomas"),
            ("Jade", "Daniel"),
        ]

        created = 0
        for a_name, s_name in pairs:
            a_pid = profiles.get(a_name)
            s_pid = profiles.get(s_name)
            if not a_pid or not s_pid:
                print(f"  SKIP {a_name}-{s_name}: profile not found")
                continue

            # Likes
            db.add(Like(from_profile_id=a_pid, to_profile_id=s_pid))
            db.add(Like(from_profile_id=s_pid, to_profile_id=a_pid))

            # Match
            p1, p2 = min(a_pid, s_pid), max(a_pid, s_pid)
            match = Match(profile1_id=p1, profile2_id=p2)
            db.add(match)
            await db.flush()

            # Conversation
            conv = Conversation(match_id=match.id)
            db.add(conv)
            await db.flush()

            # Messages
            msgs = [
                (s_pid, f"Hi {a_name}! Your profile really caught my eye."),
                (a_pid, f"Thank you {s_name}! What stood out to you?"),
                (s_pid, "Your style and ambition. I would love to get to know you better."),
                (a_pid, "That means a lot. Tell me more about yourself."),
            ]
            for j, (sender, text) in enumerate(msgs):
                db.add(Message(
                    conversation_id=conv.id,
                    sender_profile_id=sender,
                    content=text,
                    is_read=j < 3,
                ))

            created += 1
            print(f"  Created: {a_name} <-> {s_name}")

        # Extra one-way likes
        import random
        all_pids = list(profiles.values())
        for _ in range(25):
            a = random.choice(all_pids)
            b = random.choice(all_pids)
            if a != b:
                try:
                    db.add(Like(from_profile_id=a, to_profile_id=b))
                    await db.flush()
                except Exception:
                    await db.rollback()

        await db.commit()
        print(f"\nDone: {created} matches with conversations created")


if __name__ == "__main__":
    asyncio.run(main())
