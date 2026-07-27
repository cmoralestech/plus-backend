from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, UserType
from app.models.subscription import (
    Subscription, SubscriptionTier, PrivacySettings,
    TIER_FEATURES, ATTRACTIVE_FREE_FEATURES,
)

router = APIRouter(prefix="/api/subscription", tags=["subscription"])


class SubscriptionResponse(BaseModel):
    tier: SubscriptionTier
    is_active: bool
    features: list[str]
    can_upgrade: bool

    model_config = {"from_attributes": True}


class PrivacySettingsResponse(BaseModel):
    hide_profile: bool
    hide_online_status: bool
    hide_from_search: bool
    blur_photos_for_non_matches: bool
    hide_income: bool
    hide_read_receipts: bool
    hide_last_seen: bool
    private_browsing: bool

    model_config = {"from_attributes": True}


class PrivacySettingsUpdate(BaseModel):
    hide_profile: bool | None = None
    hide_online_status: bool | None = None
    hide_from_search: bool | None = None
    blur_photos_for_non_matches: bool | None = None
    hide_income: bool | None = None
    hide_read_receipts: bool | None = None
    hide_last_seen: bool | None = None
    private_browsing: bool | None = None


# Premium feature names that require a paid subscription
PREMIUM_SETTINGS = {
    "hide_from_search",
    "blur_photos_for_non_matches",
    "hide_income",
    "hide_read_receipts",
    "hide_last_seen",
    "private_browsing",
}


async def _get_or_create_subscription(user_id: int, db: AsyncSession) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalar_one_or_none()
    if not sub:
        sub = Subscription(user_id=user_id, tier=SubscriptionTier.FREE)
        db.add(sub)
        await db.flush()
    return sub


async def _get_or_create_privacy(user_id: int, db: AsyncSession) -> PrivacySettings:
    result = await db.execute(select(PrivacySettings).where(PrivacySettings.user_id == user_id))
    ps = result.scalar_one_or_none()
    if not ps:
        ps = PrivacySettings(user_id=user_id)
        db.add(ps)
        await db.flush()
    return ps


def _get_available_features(tier: SubscriptionTier, user_type: UserType) -> set[str]:
    features = TIER_FEATURES.get(tier, set()).copy()
    # Attractive members get certain features free
    if user_type == UserType.ATTRACTIVE:
        features |= ATTRACTIVE_FREE_FEATURES
    return features


@router.get("/", response_model=SubscriptionResponse)
async def get_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await _get_or_create_subscription(user.id, db)
    await db.commit()
    features = _get_available_features(sub.tier, user.user_type)
    return SubscriptionResponse(
        tier=sub.tier,
        is_active=sub.is_active,
        features=sorted(features),
        can_upgrade=sub.tier != SubscriptionTier.PLUS_PLUS,
    )


@router.get("/privacy", response_model=PrivacySettingsResponse)
async def get_privacy_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ps = await _get_or_create_privacy(user.id, db)
    await db.commit()
    return ps


@router.patch("/privacy", response_model=PrivacySettingsResponse)
async def update_privacy_settings(
    data: PrivacySettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await _get_or_create_subscription(user.id, db)
    ps = await _get_or_create_privacy(user.id, db)
    available = _get_available_features(sub.tier, user.user_type)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        # Check if this is a premium setting being turned ON
        if value and field in PREMIUM_SETTINGS and field not in available:
            raise HTTPException(
                status_code=403,
                detail=f"Upgrade to Premium to use {field.replace('_', ' ')}",
            )
        setattr(ps, field, value)

    await db.commit()
    await db.refresh(ps)
    return ps


@router.get("/tiers")
async def get_tiers():
    """Return available subscription tiers and their features for the pricing page."""
    return {
        "tiers": [
            {
                "id": "free",
                "name": "Free",
                "price_monthly": 0,
                "features": [
                    "Create profile & upload photos",
                    "Browse & discover profiles",
                    "Like & match",
                    "5 messages per day",
                    "Basic privacy controls",
                ],
            },
            {
                "id": "plus",
                "name": "Plus",
                "price_monthly": 49.99,
                "price_annual": 499,
                "features": [
                    "Everything in Free",
                    "Unlimited messaging",
                    "See who liked you",
                    "Verified badge",
                    "Hide from search",
                    "Blur photos for non-matches",
                ],
            },
            {
                "id": "plus_plus",
                "name": "Plus+",
                "price_monthly": 99.99,
                "price_annual": 999,
                "features": [
                    "Everything in Plus",
                    "Priority placement in discover",
                    "Travel mode",
                    "Read receipts",
                    "Profile boost",
                    "Unlimited likes",
                ],
            },
        ],
    }
