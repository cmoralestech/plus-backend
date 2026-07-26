import enum
from datetime import datetime

from sqlalchemy import String, Integer, Boolean, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"       # Hide from search, blur photos, see who liked you
    DIAMOND = "diamond"       # All premium + priority in discover, unlimited likes, read receipts hidden


# What each tier unlocks
TIER_FEATURES = {
    SubscriptionTier.FREE: {
        "hide_from_search",      # Not available
        "blur_photos",           # Not available
        "see_who_liked",         # Not available
        "hide_read_receipts",    # Not available
        "priority_discover",     # Not available
        "unlimited_likes",      # Not available
    },
    SubscriptionTier.PREMIUM: {
        "hide_from_search",
        "blur_photos",
        "see_who_liked",
    },
    SubscriptionTier.DIAMOND: {
        "hide_from_search",
        "blur_photos",
        "see_who_liked",
        "hide_read_receipts",
        "priority_discover",
        "unlimited_likes",
    },
}

# Override: attractive members always get these free
ATTRACTIVE_FREE_FEATURES = {
    "see_who_liked",
}


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, index=True)
    tier: Mapped[SubscriptionTier] = mapped_column(Enum(SubscriptionTier), default=SubscriptionTier.FREE)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PrivacySettings(Base):
    __tablename__ = "privacy_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, index=True)

    # Free settings (everyone gets these)
    hide_profile: Mapped[bool] = mapped_column(Boolean, default=False)
    hide_online_status: Mapped[bool] = mapped_column(Boolean, default=False)

    # Premium settings (requires subscription)
    hide_from_search: Mapped[bool] = mapped_column(Boolean, default=False)
    blur_photos_for_non_matches: Mapped[bool] = mapped_column(Boolean, default=False)
    hide_income: Mapped[bool] = mapped_column(Boolean, default=False)
    hide_read_receipts: Mapped[bool] = mapped_column(Boolean, default=False)
    hide_last_seen: Mapped[bool] = mapped_column(Boolean, default=False)
    private_browsing: Mapped[bool] = mapped_column(Boolean, default=False)  # Don't show in "viewed your profile"

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
