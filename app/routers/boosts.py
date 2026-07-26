"""Boost endpoints — purchase and manage profile boosts."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, UserType
from app.models.boost import Boost, BoostType
from app.models.subscription import Subscription, SubscriptionTier

router = APIRouter(prefix="/api/boosts", tags=["boosts"])

BOOST_PRICES = {
    "1h": {"hours": 1, "price": 4.99},
    "6h": {"hours": 6, "price": 9.99},
    "24h": {"hours": 24, "price": 19.99},
}


@router.get("/")
async def get_my_boosts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        return {"active_boost": None, "history": []}

    now = datetime.utcnow()

    # Active boost
    active_result = await db.execute(
        select(Boost).where(
            Boost.profile_id == user.profile.id,
            Boost.is_active == True,
            Boost.expires_at > now,
        ).order_by(Boost.expires_at.desc()).limit(1)
    )
    active = active_result.scalar_one_or_none()

    # History
    history_result = await db.execute(
        select(Boost).where(Boost.profile_id == user.profile.id)
        .order_by(Boost.started_at.desc()).limit(10)
    )
    history = history_result.scalars().all()

    return {
        "active_boost": {
            "id": active.id,
            "type": active.type.value,
            "expires_at": active.expires_at.isoformat(),
            "minutes_remaining": max(0, int((active.expires_at - now).total_seconds() / 60)),
        } if active else None,
        "prices": BOOST_PRICES,
        "history": [
            {
                "id": b.id,
                "type": b.type.value,
                "started_at": b.started_at.isoformat() if b.started_at else None,
                "expires_at": b.expires_at.isoformat(),
                "is_active": b.is_active and b.expires_at > now,
            }
            for b in history
        ],
    }


@router.post("/purchase")
async def purchase_boost(
    duration: str = "24h",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Purchase a profile boost. Currently deducts from subscription credit (TODO: integrate with Stripe for one-time purchase)."""
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    if duration not in BOOST_PRICES:
        raise HTTPException(status_code=400, detail=f"Invalid duration. Options: {', '.join(BOOST_PRICES.keys())}")

    # Check for existing active boost
    now = datetime.utcnow()
    existing = await db.execute(
        select(Boost).where(
            Boost.profile_id == user.profile.id,
            Boost.is_active == True,
            Boost.expires_at > now,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You already have an active boost")

    # For now, require Premium+ to purchase boosts
    sub_result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = sub_result.scalar_one_or_none()
    if not sub or sub.tier == SubscriptionTier.FREE:
        raise HTTPException(status_code=403, detail="Upgrade to Premium to purchase boosts")

    hours = BOOST_PRICES[duration]["hours"]
    boost = Boost(
        profile_id=user.profile.id,
        type=BoostType.PAID,
        expires_at=now + timedelta(hours=hours),
    )
    db.add(boost)
    await db.commit()

    return {
        "boosted": True,
        "expires_at": boost.expires_at.isoformat(),
        "hours": hours,
    }


async def grant_new_member_boost(profile_id: int, db: AsyncSession):
    """Grant a free 7-day boost to new attractive members. Called from profile creation."""
    boost = Boost(
        profile_id=profile_id,
        type=BoostType.NEW_MEMBER,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(boost)
