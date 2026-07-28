"""Waitlist: collect interest from users outside launch cities."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.waitlist import WaitlistEntry

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])


class WaitlistSubmit(BaseModel):
    email: EmailStr
    first_name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=30)
    instagram: str | None = Field(None, max_length=100)
    city: str = Field(..., max_length=100)
    state: str | None = Field(None, max_length=100)
    zip_code: str | None = Field(None, max_length=20)
    worth_joining: list[str] | None = None
    gender: str | None = Field(None, max_length=30)
    interested_in: str | None = Field(None, max_length=30)
    age: int | None = None
    desired_age_min: int | None = None
    desired_age_max: int | None = None
    looking_for: list[str] | None = None
    what_matters: list[str] | None = None
    bring_to_table: list[str] | None = None
    how_heard: str | None = Field(None, max_length=100)
    referral_code: str | None = Field(None, max_length=50)


@router.post("/")
async def join_waitlist(data: WaitlistSubmit, db: AsyncSession = Depends(get_db)):
    """Join the waitlist. Upserts by email."""
    email = data.email.lower().strip()

    result = await db.execute(select(WaitlistEntry).where(WaitlistEntry.email == email))
    entry = result.scalar_one_or_none()

    if entry:
        # Update existing entry
        for field, value in data.model_dump(exclude={"email"}).items():
            if value is not None:
                setattr(entry, field, value)
    else:
        entry = WaitlistEntry(email=email, **data.model_dump(exclude={"email"}))
        db.add(entry)

    await db.commit()
    return {"message": f"You're on the list for {data.city}.", "city": data.city}


@router.get("/cities")
async def waitlist_cities(db: AsyncSession = Depends(get_db)):
    """Public: cities with waitlist counts, sorted by demand."""
    result = await db.execute(
        select(WaitlistEntry.city, func.count(WaitlistEntry.id).label("count"))
        .group_by(WaitlistEntry.city)
        .order_by(func.count(WaitlistEntry.id).desc())
    )
    cities = [{"city": row.city, "count": row.count} for row in result.all()]
    return {"cities": cities}


@router.get("/stats")
async def waitlist_stats(db: AsyncSession = Depends(get_db)):
    """Admin: detailed waitlist stats per city for launch planning."""
    # Total count
    total_result = await db.execute(select(func.count(WaitlistEntry.id)))
    total = total_result.scalar()

    # Per-city breakdown
    city_result = await db.execute(
        select(WaitlistEntry.city, func.count(WaitlistEntry.id).label("count"))
        .group_by(WaitlistEntry.city)
        .order_by(func.count(WaitlistEntry.id).desc())
        .limit(50)
    )
    cities = []
    for row in city_result.all():
        city_name = row.city
        # Get gender breakdown for this city
        gender_result = await db.execute(
            select(WaitlistEntry.gender, func.count(WaitlistEntry.id))
            .where(WaitlistEntry.city == city_name, WaitlistEntry.gender.isnot(None))
            .group_by(WaitlistEntry.gender)
        )
        gender_breakdown = {r[0]: r[1] for r in gender_result.all()}

        # Get interested_in breakdown
        interest_result = await db.execute(
            select(WaitlistEntry.interested_in, func.count(WaitlistEntry.id))
            .where(WaitlistEntry.city == city_name, WaitlistEntry.interested_in.isnot(None))
            .group_by(WaitlistEntry.interested_in)
        )
        interest_breakdown = {r[0]: r[1] for r in interest_result.all()}

        # Get looking_for breakdown (unnest array)
        looking_result = await db.execute(
            select(func.unnest(WaitlistEntry.looking_for).label("lf"), func.count())
            .where(WaitlistEntry.city == city_name, WaitlistEntry.looking_for.isnot(None))
            .group_by("lf")
        )
        looking_breakdown = {r[0]: r[1] for r in looking_result.all()}

        # Get how_heard breakdown
        heard_result = await db.execute(
            select(WaitlistEntry.how_heard, func.count(WaitlistEntry.id))
            .where(WaitlistEntry.city == city_name, WaitlistEntry.how_heard.isnot(None))
            .group_by(WaitlistEntry.how_heard)
        )
        heard_breakdown = {r[0]: r[1] for r in heard_result.all()}

        # Average age
        avg_age_result = await db.execute(
            select(func.avg(WaitlistEntry.age))
            .where(WaitlistEntry.city == city_name, WaitlistEntry.age.isnot(None))
        )
        avg_age = avg_age_result.scalar()

        cities.append({
            "city": city_name,
            "count": row.count,
            "gender": gender_breakdown,
            "interested_in": interest_breakdown,
            "looking_for": looking_breakdown,
            "how_heard": heard_breakdown,
            "avg_age": round(avg_age, 1) if avg_age else None,
        })

    return {"total": total, "cities": cities}
