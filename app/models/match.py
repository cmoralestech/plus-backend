from datetime import datetime

from sqlalchemy import Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (
        UniqueConstraint("from_profile_id", "to_profile_id", name="uq_like"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), index=True)
    to_profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    from_profile: Mapped["Profile"] = relationship(foreign_keys=[from_profile_id], lazy="selectin")
    to_profile: Mapped["Profile"] = relationship(foreign_keys=[to_profile_id], lazy="selectin")


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("profile1_id", "profile2_id", name="uq_match"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile1_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), index=True)
    profile2_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    profile1: Mapped["Profile"] = relationship(foreign_keys=[profile1_id], lazy="selectin")
    profile2: Mapped["Profile"] = relationship(foreign_keys=[profile2_id], lazy="selectin")
    conversation: Mapped["Conversation"] = relationship(back_populates="match", uselist=False, lazy="selectin")
