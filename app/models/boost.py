import enum
from datetime import datetime

from sqlalchemy import Integer, String, Boolean, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BoostType(str, enum.Enum):
    NEW_MEMBER = "new_member"    # Free 7-day boost for new attractive members
    PAID = "paid"                # Purchased boost (e.g. 24 hours)
    PROMOTIONAL = "promotional"  # Admin-granted


class Boost(Base):
    __tablename__ = "boosts"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), index=True)
    type: Mapped[BoostType] = mapped_column(Enum(BoostType))
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
