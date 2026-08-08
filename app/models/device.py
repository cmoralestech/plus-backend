"""Registered push targets.

One row per device per member. Tokens are rotated by the OS and reissued on
reinstall, so the token itself is the identity — a member can hold several, and
the same token can move between members when a device is handed on or shared.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Expo push token ("ExponentPushToken[...]"). Unique because re-registering
    # the same device must update the owner rather than accumulate rows — that
    # is how a device that changed hands stops receiving the old member's
    # notifications.
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(20), default="ios")
    device_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Cleared when Expo reports the token as unregistered, rather than deleting
    # the row, so a reinstall on the same device reactivates the same record.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="device_tokens")  # noqa: F821
