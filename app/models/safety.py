import enum
from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Block(Base):
    __tablename__ = "blocks"
    __table_args__ = (
        UniqueConstraint("blocker_profile_id", "blocked_profile_id", name="uq_block"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    blocker_profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), index=True)
    blocked_profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReportReason(str, enum.Enum):
    FAKE_PROFILE = "fake_profile"
    HARASSMENT = "harassment"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    SCAM = "scam"
    UNDERAGE = "underage"
    HUMAN_TRAFFICKING = "human_trafficking"
    OTHER = "other"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), index=True)
    reported_profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), index=True)
    reason: Mapped[ReportReason] = mapped_column(Enum(ReportReason))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
