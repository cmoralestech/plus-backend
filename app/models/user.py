import enum
from datetime import date, datetime

from sqlalchemy import String, Boolean, Date, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserType(str, enum.Enum):
    SUGAR = "sugar"
    ATTRACTIVE = "attractive"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    user_type: Mapped[UserType] = mapped_column(Enum(UserType))
    # Collected at registration for the 18+ check. It used to be validated and
    # then discarded, leaving onboarding with no date to send — which failed
    # profile creation for every account.
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    profile: Mapped["Profile"] = relationship(back_populates="user", uselist=False, lazy="selectin")
