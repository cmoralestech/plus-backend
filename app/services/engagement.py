"""Engagement automation — auto-likes, digest emails, re-engagement.

These systems keep early users engaged when the platform has low activity.
"""
import logging
import random
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserType
from app.models.profile import Profile
from app.models.match import Like
from app.services.email import send_someone_liked_you

logger = logging.getLogger(__name__)


async def auto_like_new_profile(profile_id: int, user_id: int, db: AsyncSession):
    """When a real user creates a profile, have 3-5 seed profiles like them.

    This creates immediate engagement — the user gets "Someone liked you"
    notifications within the first hour, driving them back to the app.
    """
    # Get the new user's profile to determine gender/type
    profile_result = await db.execute(select(Profile).where(Profile.id == profile_id))
    new_profile = profile_result.scalar_one_or_none()
    if not new_profile:
        return

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        return

    # Find seed profiles of the opposite type to like this profile
    # Sugar daddies get liked by attractive seeds, attractive members get liked by sugar seeds
    if user.user_type == UserType.SUGAR:
        target_type = UserType.ATTRACTIVE
    else:
        target_type = UserType.SUGAR

    seed_query = (
        select(Profile)
        .join(User, User.id == Profile.user_id)
        .where(
            Profile.is_seed == True,
            User.user_type == target_type,
            Profile.is_active == True,
            Profile.is_hidden == False,
        )
    )
    result = await db.execute(seed_query)
    seed_profiles = result.scalars().all()

    if not seed_profiles:
        logger.warning(f"[ENGAGEMENT] No seed profiles found for auto-like (target_type={target_type.value})")
        return

    # Pick 3-5 random seed profiles
    num_likes = min(random.randint(3, 5), len(seed_profiles))
    likers = random.sample(list(seed_profiles), num_likes)

    liked_count = 0
    for seed_profile in likers:
        # Check if like already exists
        existing = await db.execute(
            select(Like).where(
                Like.from_profile_id == seed_profile.id,
                Like.to_profile_id == profile_id,
            )
        )
        if existing.scalar_one_or_none():
            continue

        like = Like(from_profile_id=seed_profile.id, to_profile_id=profile_id)
        db.add(like)
        liked_count += 1

    if liked_count > 0:
        await db.commit()
        logger.info(f"[ENGAGEMENT] Auto-liked profile {profile_id} from {liked_count} seed profiles")

        # Send "someone liked you" email for the first like only
        first_liker = likers[0]
        try:
            send_someone_liked_you(
                to=user.email,
                liker_name=first_liker.display_name,
                liker_city=first_liker.city or "",
            )
        except Exception as e:
            logger.error(f"[ENGAGEMENT] Failed to send like email: {e}")


async def get_digest_stats(user_id: int, db: AsyncSession) -> dict:
    """Get weekly stats for a user's digest email."""
    week_ago = datetime.utcnow() - timedelta(days=7)

    # New members this week
    new_members = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    )).scalar() or 0

    # Get user's profile
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.profile:
        return {"new_members": new_members, "likes_received": 0, "profile_views": 0}

    # Likes received this week
    likes = (await db.execute(
        select(func.count(Like.id)).where(
            Like.to_profile_id == user.profile.id,
            Like.created_at >= week_ago,
        )
    )).scalar() or 0

    # Profile views (if table exists)
    views = 0
    try:
        from app.models.engagement import ProfileView
        views = (await db.execute(
            select(func.count(ProfileView.id)).where(
                ProfileView.viewed_profile_id == user.profile.id,
                ProfileView.created_at >= week_ago,
            )
        )).scalar() or 0
    except Exception:
        pass

    return {"new_members": new_members, "likes_received": likes, "profile_views": views}
