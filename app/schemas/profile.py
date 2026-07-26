from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.profile import (
    Gender, BodyType, Education, IncomeRange, NetWorthRange,
    LifestyleExpectation, DrinkingHabit, SmokingHabit,
    RelationshipStatus, Availability, SexualOrientation, Pronouns,
    VALID_INTERESTS, VALID_ARRANGEMENT_TYPES, VALID_LIFESTYLE_TAGS,
)
from app.models.user import UserType


class PhotoResponse(BaseModel):
    id: int
    url: str
    is_primary: bool
    is_verified: bool
    is_private: bool
    order: int

    model_config = {"from_attributes": True}


class ProfileCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    bio: str | None = Field(None, max_length=2000)
    headline: str | None = Field(None, max_length=200)
    date_of_birth: date
    gender: Gender
    seeking_gender: Gender | None = None
    sexual_orientation: SexualOrientation | None = None
    pronouns: Pronouns | None = None
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    height_cm: int | None = Field(None, ge=100, le=250)
    body_type: BodyType | None = None
    ethnicity: str | None = None
    education: Education | None = None
    occupation: str | None = None
    languages: str | None = Field(None, max_length=200)
    income_range: IncomeRange | None = None
    net_worth_range: NetWorthRange | None = None
    lifestyle_expectation: LifestyleExpectation | None = None
    looking_for: str | None = Field(None, max_length=1000)
    offering: str | None = Field(None, max_length=1000)
    arrangement_types: list[str] | None = None
    interests: list[str] | None = None
    lifestyle_tags: list[str] | None = None
    relationship_status: RelationshipStatus | None = None
    availability: Availability | None = None
    drinking: DrinkingHabit | None = None
    smoking: SmokingHabit | None = None
    has_children: bool | None = None
    ideal_first_date: str | None = Field(None, max_length=500)

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return v

    @field_validator("arrangement_types")
    @classmethod
    def validate_arrangement_types(cls, v: list[str] | None) -> list[str] | None:
        if v:
            invalid = set(v) - VALID_ARRANGEMENT_TYPES
            if invalid:
                raise ValueError(f"Invalid arrangement types: {invalid}")
            if len(v) > 5:
                raise ValueError("Maximum 5 arrangement types")
        return v

    @field_validator("interests")
    @classmethod
    def validate_interests(cls, v: list[str] | None) -> list[str] | None:
        if v:
            invalid = set(v) - VALID_INTERESTS
            if invalid:
                raise ValueError(f"Invalid interests: {invalid}")
            if len(v) > 10:
                raise ValueError("Maximum 10 interests")
        return v

    @field_validator("lifestyle_tags")
    @classmethod
    def validate_lifestyle_tags(cls, v: list[str] | None) -> list[str] | None:
        if v:
            invalid = set(v) - VALID_LIFESTYLE_TAGS
            if invalid:
                raise ValueError(f"Invalid lifestyle tags: {invalid}")
            if len(v) > 8:
                raise ValueError("Maximum 8 lifestyle tags")
        return v


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    headline: str | None = None
    gender: Gender | None = None
    seeking_gender: Gender | None = None
    sexual_orientation: SexualOrientation | None = None
    pronouns: Pronouns | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    height_cm: int | None = None
    body_type: BodyType | None = None
    ethnicity: str | None = None
    education: Education | None = None
    occupation: str | None = None
    languages: str | None = None
    income_range: IncomeRange | None = None
    net_worth_range: NetWorthRange | None = None
    lifestyle_expectation: LifestyleExpectation | None = None
    looking_for: str | None = None
    offering: str | None = None
    arrangement_types: list[str] | None = None
    interests: list[str] | None = None
    lifestyle_tags: list[str] | None = None
    relationship_status: RelationshipStatus | None = None
    availability: Availability | None = None
    drinking: DrinkingHabit | None = None
    smoking: SmokingHabit | None = None
    has_children: bool | None = None
    ideal_first_date: str | None = None
    is_hidden: bool | None = None


class ProfileResponse(BaseModel):
    id: int
    user_id: int
    user_type: UserType | None = None
    display_name: str
    bio: str | None
    headline: str | None
    date_of_birth: date
    age: int | None = None
    gender: Gender
    seeking_gender: Gender | None
    sexual_orientation: SexualOrientation | None = None
    pronouns: Pronouns | None = None
    city: str | None
    state: str | None
    country: str | None
    height_cm: int | None
    body_type: BodyType | None
    ethnicity: str | None
    education: Education | None
    occupation: str | None
    languages: str | None
    income_range: IncomeRange | None
    net_worth_range: NetWorthRange | None
    lifestyle_expectation: LifestyleExpectation | None
    looking_for: str | None
    offering: str | None
    arrangement_types: list[str] | None
    interests: list[str] | None
    lifestyle_tags: list[str] | None = None
    relationship_status: RelationshipStatus | None
    availability: Availability | None
    drinking: DrinkingHabit | None
    smoking: SmokingHabit | None
    has_children: bool | None
    ideal_first_date: str | None
    is_online: bool = False
    last_active: str | None = None
    is_photo_verified: bool
    is_income_verified: bool = False
    is_traveling: bool = False
    travel_city: str | None = None
    distance_miles: int | None = None
    is_featured: bool = False
    is_new: bool = False
    is_popular: bool = False
    subscription_tier: str | None = None
    photos: list[PhotoResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}
