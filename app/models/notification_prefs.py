from datetime import datetime

from sqlalchemy import Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NotificationPreferences(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, index=True)

    # Match & activity
    new_match: Mapped[bool] = mapped_column(Boolean, default=True)
    new_message: Mapped[bool] = mapped_column(Boolean, default=True)
    new_like: Mapped[bool] = mapped_column(Boolean, default=True)
    profile_view: Mapped[bool] = mapped_column(Boolean, default=True)

    # Email
    email_matches: Mapped[bool] = mapped_column(Boolean, default=True)
    email_messages: Mapped[bool] = mapped_column(Boolean, default=False)
    email_promotions: Mapped[bool] = mapped_column(Boolean, default=False)
    email_tips: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
