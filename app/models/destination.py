"""Places and events members are heading to.

The question the product asks isn't only "who do you want to date" but "where
are you going, and who do you want beside you". A member marks a destination
as somewhere they're going or somewhere they'd like to go, and can then see
who else has done the same.

Interest is deliberately two-tier: "going" is a commitment with a date behind
it, "want to go" is an aspiration. Collapsing them would make the feature
read as logistics rather than intent.
"""
import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InterestLevel(str, enum.Enum):
    GOING = "going"
    WANT_TO_GO = "want_to_go"


class Destination(Base):
    """A curated place or event. Not user-created — an open text field would
    turn this into a tagging system and lose the shared-context that makes
    matching on it useful."""

    __tablename__ = "destinations"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    blurb: Mapped[str | None] = mapped_column(String(240), nullable=True)
    # Null for places that are a standing idea rather than a dated event.
    starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DestinationInterest(Base):
    __tablename__ = "destination_interests"
    __table_args__ = (
        UniqueConstraint("profile_id", "destination_id", name="uq_destination_interest"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    destination_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("destinations.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[InterestLevel] = mapped_column(
        SQLEnum(InterestLevel, name="interest_level"), default=InterestLevel.WANT_TO_GO
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    destination: Mapped["Destination"] = relationship(lazy="selectin")
