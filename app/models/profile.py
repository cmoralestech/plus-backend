import enum
from datetime import date, datetime

from sqlalchemy import String, Text, Integer, Boolean, Date, DateTime, Enum, ForeignKey, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import StringArray


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
    OTHER = "other"


class BodyType(str, enum.Enum):
    SLIM = "slim"
    ATHLETIC = "athletic"
    AVERAGE = "average"
    CURVY = "curvy"
    FULL_FIGURED = "full_figured"
    OTHER = "other"


class Education(str, enum.Enum):
    HIGH_SCHOOL = "high_school"
    SOME_COLLEGE = "some_college"
    BACHELORS = "bachelors"
    MASTERS = "masters"
    DOCTORATE = "doctorate"
    OTHER = "other"


class IncomeRange(str, enum.Enum):
    UNDER_100K = "under_100k"
    R100K_250K = "100k_250k"
    R250K_500K = "250k_500k"
    R500K_1M = "500k_1m"
    R1M_5M = "1m_5m"
    R5M_10M = "5m_10m"
    OVER_10M = "over_10m"


class NetWorthRange(str, enum.Enum):
    UNDER_1M = "under_1m"
    R1M_5M = "1m_5m"
    R5M_10M = "5m_10m"
    R10M_50M = "10m_50m"
    R50M_100M = "50m_100m"
    OVER_100M = "over_100m"


class LifestyleExpectation(str, enum.Enum):
    NEGOTIABLE = "negotiable"
    MINIMAL = "minimal"
    PRACTICAL = "practical"
    MODERATE = "moderate"
    SUBSTANTIAL = "substantial"
    HIGH = "high"


class RelationshipStatus(str, enum.Enum):
    SINGLE = "single"
    DIVORCED = "divorced"
    SEPARATED = "separated"
    WIDOWED = "widowed"
    MARRIED = "married"
    OPEN = "open_relationship"


class Availability(str, enum.Enum):
    FLEXIBLE = "flexible"
    WEEKDAYS = "weekdays"
    WEEKENDS = "weekends"
    EVENINGS = "evenings"
    TRAVEL_READY = "travel_ready"


class DrinkingHabit(str, enum.Enum):
    NEVER = "never"
    SOCIALLY = "socially"
    REGULARLY = "regularly"


class SmokingHabit(str, enum.Enum):
    NEVER = "never"
    OCCASIONALLY = "occasionally"
    REGULARLY = "regularly"


class SexualOrientation(str, enum.Enum):
    STRAIGHT = "straight"
    GAY = "gay"
    LESBIAN = "lesbian"
    BISEXUAL = "bisexual"
    PANSEXUAL = "pansexual"
    QUEER = "queer"
    ASEXUAL = "asexual"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class Pronouns(str, enum.Enum):
    HE_HIM = "he_him"
    SHE_HER = "she_her"
    THEY_THEM = "they_them"
    HE_THEY = "he_they"
    SHE_THEY = "she_they"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


# Valid tags for interests and arrangement_types (stored as string arrays)
VALID_INTERESTS = {
    "travel", "fine_dining", "fitness", "art", "fashion", "nightlife",
    "music", "cooking", "wine", "yachting", "golf", "theater",
    "photography", "reading", "hiking", "yoga", "dancing", "spa",
    "cars", "tech", "investing", "real_estate", "volunteering",
    "sports", "movies", "concerts", "shopping", "nature",
}

# What a member is open to. "sugar_relationship" was removed: naming it as a
# relationship type is what makes a product read as compensated dating.
# "something_casual" and "open_relationship" were offered in onboarding but
# missing here, so selecting either failed validation and blocked profile save.
VALID_ARRANGEMENT_TYPES = {
    "mentorship", "travel_companion", "long_term", "short_term",
    "no_strings", "friends_with_benefits", "dating", "networking",
    "experience_partner", "something_casual", "open_relationship",
}

VALID_LIFESTYLE_TAGS = {
    "monogamous", "enm", "open_relationship", "polyamorous",
    "kink_friendly", "vanilla", "curious",
    "dom", "sub", "switch",
    "couples_friendly", "group_friendly",
    "voyeur", "exhibitionist",
    "discrete", "420_friendly",
}


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    bio: Mapped[str | None] = mapped_column(Text)
    headline: Mapped[str | None] = mapped_column(String(200))
    date_of_birth: Mapped[date] = mapped_column(Date)
    gender: Mapped[Gender] = mapped_column(Enum(Gender))
    seeking_gender: Mapped[Gender | None] = mapped_column(Enum(Gender), nullable=True)
    sexual_orientation: Mapped[SexualOrientation | None] = mapped_column(Enum(SexualOrientation), nullable=True)
    pronouns: Mapped[Pronouns | None] = mapped_column(Enum(Pronouns), nullable=True)

    # Home location
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Travel mode — temporary location when traveling
    is_traveling: Mapped[bool] = mapped_column(Boolean, default=False)
    travel_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    travel_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    travel_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    travel_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Physical
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body_type: Mapped[BodyType | None] = mapped_column(Enum(BodyType), nullable=True)
    ethnicity: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Background
    education: Mapped[Education | None] = mapped_column(Enum(Education), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    languages: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Financial / lifestyle
    income_range: Mapped[IncomeRange | None] = mapped_column(Enum(IncomeRange), nullable=True)
    net_worth_range: Mapped[NetWorthRange | None] = mapped_column(Enum(NetWorthRange), nullable=True)
    lifestyle_expectation: Mapped[LifestyleExpectation | None] = mapped_column(Enum(LifestyleExpectation), nullable=True)

    # The sugar dating core: what you want and what you bring
    looking_for: Mapped[str | None] = mapped_column(Text, nullable=True)
    offering: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Arrangement preferences (stored as postgres array of strings)
    arrangement_types: Mapped[list[str] | None] = mapped_column(StringArray(50), nullable=True)
    interests: Mapped[list[str] | None] = mapped_column(StringArray(50), nullable=True)
    lifestyle_tags: Mapped[list[str] | None] = mapped_column(StringArray(50), nullable=True)

    # Personal
    relationship_status: Mapped[RelationshipStatus | None] = mapped_column(
        Enum(RelationshipStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=True,
    )
    availability: Mapped[Availability | None] = mapped_column(
        Enum(Availability, values_callable=lambda e: [x.value for x in e]),
        nullable=True,
    )
    drinking: Mapped[DrinkingHabit | None] = mapped_column(Enum(DrinkingHabit), nullable=True)
    smoking: Mapped[SmokingHabit | None] = mapped_column(Enum(SmokingHabit), nullable=True)
    has_children: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ideal_first_date: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Plus onboarding extras
    net_worth: Mapped[str | None] = mapped_column(String(50), nullable=True)
    show_up_traits: Mapped[list[str] | None] = mapped_column(StringArray(50), nullable=True)
    plus_traits: Mapped[list[str] | None] = mapped_column(StringArray(50), nullable=True)
    generosity: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    is_photo_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_income_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="profile")
    photos: Mapped[list["Photo"]] = relationship(back_populates="profile", lazy="selectin", order_by="Photo.order")


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    profile: Mapped["Profile"] = relationship(back_populates="photos")
