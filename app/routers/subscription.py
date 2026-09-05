from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, UserType
from app.config import settings
from app.models.subscription import (
    Subscription, SubscriptionTier, PrivacySettings, features_for,
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


# Privacy settings that require a paid subscription, mapped to the feature name
# that unlocks them.
#
# These used to be a bare set compared directly against the feature list, but
# the names never lined up: the setting is `blur_photos_for_non_matches` while
# the feature is `blur_photos`, and `hide_income`, `hide_last_seen` and
# `private_browsing` are not in the feature map at all. The effect was that a
# paying Plus member was still refused four of the six settings they had paid
# for. An explicit mapping makes the mismatch impossible to reintroduce, and
# `None` marks a setting no tier gates.
PREMIUM_SETTINGS: dict[str, str | None] = {
    "hide_from_search": "hide_from_search",
    "blur_photos_for_non_matches": "blur_photos",
    "hide_read_receipts": "hide_read_receipts",
    # Not sold as part of any tier — included with the rest of privacy.
    "hide_income": None,
    "hide_last_seen": None,
    "private_browsing": None,
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
    return features_for(tier, is_plus_member=user_type == UserType.PLUS)


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
        can_upgrade=not settings.FREE_MODE and sub.tier != SubscriptionTier.PLUS_PLUS,
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
        # Only block a premium setting being turned ON, and only when the tier
        # genuinely lacks the feature behind it. In free mode `available` is
        # everything, so nothing here fires — that is the intended behaviour,
        # not an oversight.
        required = PREMIUM_SETTINGS.get(field)
        if value and required is not None and required not in available:
            raise HTTPException(
                status_code=403,
                detail=f"Upgrade to Plus to use {field.replace('_', ' ')}",
            )
        setattr(ps, field, value)

    await db.commit()
    await db.refresh(ps)
    return ps


@router.get("/tiers")
async def get_tiers():
    """Return available subscription tiers and their features for the pricing page.

    `free_mode` tells the client that the prices below are not currently being
    charged. The tier list is still returned in full so the pricing page can
    show what the plans will be, rather than pretending they do not exist.
    """
    return {
        "free_mode": settings.FREE_MODE,
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
