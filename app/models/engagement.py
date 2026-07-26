from datetime import datetime

from sqlalchemy import Integer, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("from_profile_id", "to_profile_id", name="uq_favorite"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), index=True)
    to_profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ProfileView(Base):
    __tablename__ = "profile_views"

    id: Mapped[int] = mapped_column(primary_key=True)
    viewer_profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), index=True)
    viewed_profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
