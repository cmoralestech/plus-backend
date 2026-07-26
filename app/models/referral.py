import uuid
from datetime import datetime

from sqlalchemy import Integer, String, Float, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def generate_referral_code() -> str:
    return uuid.uuid4().hex[:8]


class ReferralLink(Base):
    """Each user gets a unique referral code."""
    __tablename__ = "referral_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    custom_slug: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)  # e.g. "jessica" -> meetyourplus.com/r/jessica
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Referral(Base):
    """Tracks who referred whom."""
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    referred_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, index=True)
    referral_code: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReferralEarning(Base):
    """Monthly earnings from each referred subscriber."""
    __tablename__ = "referral_earnings"

    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    referred_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    amount: Mapped[float] = mapped_column(Float)
    subscription_tier: Mapped[str] = mapped_column(String(20))
    period: Mapped[str] = mapped_column(String(7))  # "2026-06" format
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
