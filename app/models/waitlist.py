import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def generate_share_code() -> str:
    """Referral code for a waitlist member.

    Waitlist entries are not Users yet, so they can't use ReferralLink (which is
    keyed on users.id). This is the pre-signup equivalent, letting someone invite
    people into their city's queue before PLUS launches there.
    """
    return uuid.uuid4().hex[:10]


class WaitlistEntry(Base):
    __tablename__ = "waitlist"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Contact
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    instagram: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Location
    city: Mapped[str] = mapped_column(String(100), index=True)
    metro: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Preferences
    worth_joining: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(30), nullable=True)
    interested_in: Mapped[str | None] = mapped_column(String(30), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    desired_age_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    desired_age_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    looking_for: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    what_matters: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    bring_to_table: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    # Attribution
    how_heard: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # This member's own code, for inviting people into their city's queue.
    share_code: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, default=generate_share_code
    )
    # The share_code this member arrived through, if any.
    referred_by_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    utm_source: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    utm_medium: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )
