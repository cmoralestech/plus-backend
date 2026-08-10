"""Referral/affiliate system — revenue share model."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionTier
from app.models.referral import ReferralLink, Referral, ReferralEarning, generate_referral_code
from app.config import settings

router = APIRouter(prefix="/api/referrals", tags=["referrals"])

# Legacy flat rate (used as default)
EARNINGS_PER_TIER = {
    SubscriptionTier.PLUS: 5.00,
    SubscriptionTier.PLUS_PLUS: 10.00,
}


class CustomSlugRequest(BaseModel):
    slug: str = Field(..., min_length=3, max_length=30, pattern="^[a-z0-9-]+$")


@router.get("/my-link")
async def get_my_referral_link(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get or create your referral link."""
    result = await db.execute(select(ReferralLink).where(ReferralLink.user_id == user.id))
    link = result.scalar_one_or_none()

    if not link:
        code = generate_referral_code()
        link = ReferralLink(user_id=user.id, code=code)
        db.add(link)
        await db.commit()
        await db.refresh(link)

    base_url = settings.FRONTEND_URL
    return {
        "code": link.code,
        "custom_slug": link.custom_slug,
        "url": f"{base_url}/r/{link.custom_slug or link.code}",
        "clicks": link.clicks,
    }


@router.post("/custom-slug")
async def set_custom_slug(
    data: CustomSlugRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set a custom slug for your referral link (e.g. meetyourplus.com/r/jessica)."""
    # Check if slug is taken
    existing = await db.execute(
        select(ReferralLink).where(ReferralLink.custom_slug == data.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="This slug is already taken")

    result = await db.execute(select(ReferralLink).where(ReferralLink.user_id == user.id))
    link = result.scalar_one_or_none()
    if not link:
        link = ReferralLink(user_id=user.id, code=generate_referral_code(), custom_slug=data.slug)
        db.add(link)
    else:
        link.custom_slug = data.slug

    await db.commit()
    base_url = settings.FRONTEND_URL
    return {
        "custom_slug": data.slug,
        "url": f"{base_url}/r/{data.slug}",
    }


@router.get("/track/{code}")
async def track_click(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """Track a referral link click. Called when someone visits /r/{code}."""
    result = await db.execute(
        select(ReferralLink).where(
            (ReferralLink.code == code) | (ReferralLink.custom_slug == code)
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        return {"valid": False}

    link.clicks += 1
    await db.commit()
    return {"valid": True, "referrer_user_id": link.user_id}


@router.post("/register-referral")
async def register_referral(
    code: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Called after a referred user registers. Links the referral."""
    # Check if already referred
    existing = await db.execute(
        select(Referral).where(Referral.referred_user_id == user.id)
    )
    if existing.scalar_one_or_none():
        return {"already_referred": True}

    # Find the referrer
    link_result = await db.execute(
        select(ReferralLink).where(
            (ReferralLink.code == code) | (ReferralLink.custom_slug == code)
        )
    )
    link = link_result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Invalid referral code")

    if link.user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot refer yourself")

    referral = Referral(
        referrer_user_id=link.user_id,
        referred_user_id=user.id,
        referral_code=link.code,
    )
    db.add(referral)
    await db.commit()
    return {"referred": True}


@router.get("/dashboard")
async def get_referral_dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Affiliate dashboard — see your referrals, earnings, and stats."""
    # Get referral link
    link_result = await db.execute(select(ReferralLink).where(ReferralLink.user_id == user.id))
    link = link_result.scalar_one_or_none()

    # Count referrals
    referrals_result = await db.execute(
        select(func.count(Referral.id)).where(Referral.referrer_user_id == user.id)
    )
    total_referrals = referrals_result.scalar() or 0

    # Count active paying referrals
    referral_ids_result = await db.execute(
        select(Referral.referred_user_id).where(Referral.referrer_user_id == user.id)
    )
    referred_user_ids = [r[0] for r in referral_ids_result.all()]

    # Kept as a count of referrals who went on to subscribe. It is a measure of
    # whether referring works, not a basis for payment: the commission tiers
    # this endpoint used to advertise were removed because nothing ever paid
    # them — no code has ever written a ReferralEarning row, so the balance on
    # that page was always going to be zero.
    active_paying = 0
    if referred_user_ids:
        subs_result = await db.execute(
            select(Subscription).where(
                Subscription.user_id.in_(referred_user_ids),
                Subscription.is_active == True,
                Subscription.tier != SubscriptionTier.FREE,
            )
        )
        paying_subs = list(subs_result.scalars().all())
        active_paying = len(paying_subs)

    base_url = settings.FRONTEND_URL

    return {
        "referral_link": f"{base_url}/r/{link.custom_slug or link.code}" if link else None,
        "code": link.code if link else None,
        "custom_slug": link.custom_slug if link else None,
        "clicks": link.clicks if link else 0,
        "total_referrals": total_referrals,
        "active_paying_referrals": active_paying,
    }
