"""Send weekly digest and re-engagement emails.

Run weekly via cron or manually:
  python send_digest.py

Sends two types of emails:
1. Weekly digest — to all active users with stats (new members, likes, views)
2. Re-engagement — to users inactive for 7+ days
"""
import asyncio
import logging
from datetime import datetime, timedelta

from app.database import async_session
from app.models.user import User
from app.models.profile import Profile
from app.services.email import send_weekly_digest, send_reengagement
from app.services.engagement import get_digest_stats
from sqlalchemy import select

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run():
    async with async_session() as db:
        # Get all real users with profiles
        result = await db.execute(
            select(User)
            .join(Profile, Profile.user_id == User.id)
            .where(
                User.is_active == True,
                Profile.is_seed == False,
            )
        )
        users = result.scalars().all()
        logger.info(f"Found {len(users)} real users with profiles")

        now = datetime.utcnow()
        digest_count = 0
        reengage_count = 0

        for user in users:
            if not user.profile:
                continue
            # Skip test accounts
            if user.email.endswith("@test.com") or user.email.endswith("@arranged.demo"):
                continue

            display_name = user.profile.display_name
            last_seen = user.last_seen or user.created_at
            days_inactive = (now - last_seen).days

            if days_inactive >= 14:
                # Re-engagement email for users gone 14+ days
                try:
                    send_reengagement(user.email, display_name, days_inactive)
                    reengage_count += 1
                    logger.info(f"  Re-engagement: {user.email} ({days_inactive} days inactive)")
                except Exception as e:
                    logger.error(f"  Failed re-engagement for {user.email}: {e}")

            elif days_inactive <= 7:
                # Weekly digest for active users (seen in last 7 days)
                try:
                    stats = await get_digest_stats(user.id, db)
                    send_weekly_digest(
                        user.email,
                        display_name,
                        new_members=stats["new_members"],
                        likes_received=stats["likes_received"],
                        profile_views=stats["profile_views"],
                    )
                    digest_count += 1
                    logger.info(f"  Digest: {user.email} (likes={stats['likes_received']}, views={stats['profile_views']})")
                except Exception as e:
                    logger.error(f"  Failed digest for {user.email}: {e}")

        logger.info(f"\nDone! Sent {digest_count} digests + {reengage_count} re-engagement emails")


if __name__ == "__main__":
    asyncio.run(run())
