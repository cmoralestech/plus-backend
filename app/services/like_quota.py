"""How many people you may like in a day.

Likes were unlimited, on the reasoning — written in `matches.py` — that they
double as saves. They don't need to: `engagement.favorites` is a separate
bookmark with its own tab, so nothing is lost by making a like cost something.

The point of the cap is what it does to the *recipient*. An inbox of unlimited
likes is a spam folder, and a like from someone who sent two hundred that week
carries no information. Ten a day means each one was chosen over nine others,
which is the only thing that makes receiving one worth anything.

**Replying is free.** If the person already liked you, liking them back does not
count. That is deliberate and load-bearing: the whole mechanic is that everyone
you like can answer you, and a recipient who had spent their ten by lunchtime
would be unable to. Reciprocity is judged from the data — their like exists and
predates yours — rather than from which screen made the call, so a client
cannot spend a free like by asking nicely.

The window rolls rather than resetting at midnight. A fixed reset needs a
timezone to be fair, and UTC midnight lands at seven in the evening in both
cities Plus currently serves — quota appearing mid-date-night is worse than
quota trickling back.
"""
from datetime import datetime, timedelta

from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Like
from app.models.subscription import Subscription, SubscriptionTier

WINDOW = timedelta(hours=24)

# Tunable, and expected to be tuned — these are a starting position, not a
# finding. No tier is unlimited on purpose: an unlimited tier would put the
# people with the loudest inboxes back where they started.
DAILY_LIMITS: dict[SubscriptionTier, int] = {
    SubscriptionTier.FREE: 10,
    SubscriptionTier.PLUS: 30,
    SubscriptionTier.PLUS_PLUS: 50,
}


def limit_for(tier: SubscriptionTier | None) -> int:
    return DAILY_LIMITS.get(tier or SubscriptionTier.FREE, DAILY_LIMITS[SubscriptionTier.FREE])


async def tier_for(db: AsyncSession, user_id: int) -> SubscriptionTier:
    sub = (
        await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    ).scalar_one_or_none()
    if sub and sub.is_active:
        return sub.tier
    return SubscriptionTier.FREE


async def used_in_window(db: AsyncSession, profile_id: int, now: datetime | None = None) -> int:
    """Likes this profile has spent in the last 24 hours.

    A like is an answer, and therefore free, when one from them to me already
    existed when I sent it. Comparing timestamps rather than storing a flag
    keeps this derivable from what is already recorded — no column to backfill,
    and no way for an older row to disagree with the rule.
    """
    now = now or datetime.utcnow()
    since = now - WINDOW

    mine = Like.__table__.alias("mine")
    theirs = Like.__table__.alias("theirs")

    # `<=`, not `<`. created_at is second-resolution and defaults to the
    # transaction clock, so two likes moments apart can carry the same stamp —
    # a mutual like inside one second is not rare. The tie has to break
    # somewhere, and it breaks toward free: the cost of getting it wrong the
    # other way is a member who cannot answer somebody, which is the one thing
    # this mechanic must never do.
    answered = exists(
        select(theirs.c.id).where(
            and_(
                theirs.c.from_profile_id == mine.c.to_profile_id,
                theirs.c.to_profile_id == mine.c.from_profile_id,
                theirs.c.created_at <= mine.c.created_at,
            )
        )
    )

    count = await db.execute(
        select(func.count())
        .select_from(mine)
        .where(
            and_(
                mine.c.from_profile_id == profile_id,
                mine.c.created_at >= since,
                ~answered,
            )
        )
    )
    return count.scalar() or 0


async def is_reciprocal(db: AsyncSession, profile_id: int, target_profile_id: int) -> bool:
    """Has the target already liked this member? Then answering them is free."""
    found = await db.execute(
        select(Like.id).where(
            and_(
                Like.from_profile_id == target_profile_id,
                Like.to_profile_id == profile_id,
            )
        )
    )
    return found.scalar_one_or_none() is not None


async def next_free_at(db: AsyncSession, profile_id: int, now: datetime | None = None):
    """When the oldest spent like ages out, freeing a slot. None if none spent."""
    now = now or datetime.utcnow()
    since = now - WINDOW

    oldest = await db.execute(
        select(func.min(Like.created_at)).where(
            and_(Like.from_profile_id == profile_id, Like.created_at >= since)
        )
    )
    stamp = oldest.scalar()
    return (stamp + WINDOW) if stamp else None


async def quota(db: AsyncSession, profile_id: int, user_id: int, now: datetime | None = None) -> dict:
    """Everything a client needs to show the state without a second call."""
    tier = await tier_for(db, user_id)
    limit = limit_for(tier)
    used = await used_in_window(db, profile_id, now=now)
    remaining = max(0, limit - used)

    return {
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "tier": tier.value,
        # Only meaningful once they've run out; null while they still have some.
        "resets_at": (await next_free_at(db, profile_id, now=now)) if remaining == 0 else None,
        # Stated rather than implied, so a client can explain the rule to the
        # member instead of guessing at why a like was free.
        "replies_are_free": True,
    }
