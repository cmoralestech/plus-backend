from datetime import datetime
from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


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
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
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
    referral_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
