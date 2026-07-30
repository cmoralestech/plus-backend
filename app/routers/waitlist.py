"""Waitlist: collect interest from users outside launch cities.

The waitlist doubles as a market-demand system. Beyond capturing an email, each
entry records enough about the person to judge whether a city has balanced
marketplace liquidity — not just a large raw count — before PLUS opens there.
"""
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.waitlist import WaitlistEntry, generate_share_code
from app.routers.admin import require_admin

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])

# Signals that a member is likely to qualify as an ESTABLISHED member. Used only
# for aggregate launch planning, never to label an individual.
ESTABLISHED_SIGNALS = {"An established lifestyle", "Generosity", "Connections"}

AGE_BUCKETS = [(18, 24), (25, 29), (30, 34), (35, 44), (45, 54), (55, 200)]


def _age_bucket_label(low: int, high: int) -> str:
    return f"{low}+" if high >= 200 else f"{low}-{high}"


class WaitlistSubmit(BaseModel):
    email: EmailStr
    first_name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=30)
    instagram: str | None = Field(None, max_length=100)
    city: str = Field(..., max_length=100)
    metro: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    zip_code: str | None = Field(None, max_length=20)
    worth_joining: list[str] | None = None
    gender: str | None = Field(None, max_length=30)
    interested_in: str | None = Field(None, max_length=30)
    age: int | None = Field(None, ge=18, le=120)
    desired_age_min: int | None = Field(None, ge=18, le=120)
    desired_age_max: int | None = Field(None, ge=18, le=120)
    looking_for: list[str] | None = None
    what_matters: list[str] | None = None
    bring_to_table: list[str] | None = None
    how_heard: str | None = Field(None, max_length=100)
    referred_by_code: str | None = Field(None, max_length=20)
    utm_source: str | None = Field(None, max_length=100)
    utm_medium: str | None = Field(None, max_length=100)
    utm_campaign: str | None = Field(None, max_length=100)


@router.post("/")
async def join_waitlist(data: WaitlistSubmit, db: AsyncSession = Depends(get_db)):
    """Join the waitlist. Upserts by email, and returns the member's share code."""
    email = data.email.lower().strip()
    payload = data.model_dump(exclude={"email"})

    result = await db.execute(select(WaitlistEntry).where(WaitlistEntry.email == email))
    entry = result.scalar_one_or_none()

    if entry:
        for field, value in payload.items():
            if value is not None:
                setattr(entry, field, value)
        # Entries created before share codes existed won't have one.
        if not entry.share_code:
            entry.share_code = generate_share_code()
        # A member can't be re-attributed to a new referrer on a resubmit.
        entry.referred_by_code = entry.referred_by_code or data.referred_by_code
    else:
        entry = WaitlistEntry(email=email, share_code=generate_share_code(), **payload)
        db.add(entry)

    await db.commit()
    await db.refresh(entry)

    return {
        "message": f"You're on the list for {entry.city}.",
        "city": entry.city,
        "share_code": entry.share_code,
    }


@router.get("/cities")
async def waitlist_cities(db: AsyncSession = Depends(get_db)):
    """Public: cities with waitlist counts, sorted by demand."""
    result = await db.execute(
        select(WaitlistEntry.city, func.count(WaitlistEntry.id).label("count"))
        .group_by(WaitlistEntry.city)
        .order_by(func.count(WaitlistEntry.id).desc())
    )
    return {"cities": [{"city": row.city, "count": row.count} for row in result.all()]}


@router.get("/referrals/{share_code}")
async def referral_progress(share_code: str, db: AsyncSession = Depends(get_db)):
    """Public: how many people a member has pulled into their city's queue.

    Returns counts only — never the identities of the people referred.
    """
    owner = (
        await db.execute(select(WaitlistEntry).where(WaitlistEntry.share_code == share_code))
    ).scalar_one_or_none()
    if not owner:
        raise HTTPException(status_code=404, detail="Unknown referral code")

    referred = (
        await db.execute(
            select(func.count(WaitlistEntry.id)).where(
                WaitlistEntry.referred_by_code == share_code
            )
        )
    ).scalar()

    city_total = (
        await db.execute(
            select(func.count(WaitlistEntry.id)).where(WaitlistEntry.city == owner.city)
        )
    ).scalar()

    return {
        "city": owner.city,
        "referred": referred or 0,
        "city_total": city_total or 0,
    }


@router.get("/stats")
async def waitlist_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin: per-city marketplace composition for launch planning.

    Aggregates are computed with one grouped query per dimension across all
    cities at once, rather than a query per city.
    """
    total = (await db.execute(select(func.count(WaitlistEntry.id)))).scalar() or 0

    city_rows = (
        await db.execute(
            select(WaitlistEntry.city, func.count(WaitlistEntry.id).label("count"))
            .group_by(WaitlistEntry.city)
            .order_by(func.count(WaitlistEntry.id).desc())
        )
    ).all()
    counts = {row.city: row.count for row in city_rows}

    async def scalar_breakdown(column) -> dict[str, dict[str, int]]:
        rows = (
            await db.execute(
                select(WaitlistEntry.city, column, func.count(WaitlistEntry.id))
                .where(column.isnot(None))
                .group_by(WaitlistEntry.city, column)
            )
        ).all()
        out: dict[str, dict[str, int]] = defaultdict(dict)
        for city, value, count in rows:
            out[city][value] = count
        return out

    async def array_breakdown(column) -> dict[str, dict[str, int]]:
        value = func.unnest(column).label("value")
        rows = (
            await db.execute(
                select(WaitlistEntry.city, value, func.count())
                .where(column.isnot(None))
                .group_by(WaitlistEntry.city, value)
            )
        ).all()
        out: dict[str, dict[str, int]] = defaultdict(dict)
        for city, val, count in rows:
            out[city][val] = count
        return out

    gender = await scalar_breakdown(WaitlistEntry.gender)
    interested_in = await scalar_breakdown(WaitlistEntry.interested_in)
    how_heard = await scalar_breakdown(WaitlistEntry.how_heard)
    utm_source = await scalar_breakdown(WaitlistEntry.utm_source)
    looking_for = await array_breakdown(WaitlistEntry.looking_for)
    what_matters = await array_breakdown(WaitlistEntry.what_matters)
    bring_to_table = await array_breakdown(WaitlistEntry.bring_to_table)
    worth_joining = await array_breakdown(WaitlistEntry.worth_joining)

    # Orientation pairing (e.g. "women seeking men") drives liquidity, and a raw
    # gender split alone can't express it.
    pairing_rows = (
        await db.execute(
            select(
                WaitlistEntry.city,
                WaitlistEntry.gender,
                WaitlistEntry.interested_in,
                func.count(WaitlistEntry.id),
            )
            .where(WaitlistEntry.gender.isnot(None), WaitlistEntry.interested_in.isnot(None))
            .group_by(WaitlistEntry.city, WaitlistEntry.gender, WaitlistEntry.interested_in)
        )
    ).all()
    pairings: dict[str, dict[str, int]] = defaultdict(dict)
    for city, g, i, count in pairing_rows:
        pairings[city][f"{g} seeking {i}"] = count

    bucket_expr = case(
        *[
            (WaitlistEntry.age.between(low, high), _age_bucket_label(low, high))
            for low, high in AGE_BUCKETS
        ],
        else_="unknown",
    ).label("bucket")
    age_rows = (
        await db.execute(
            select(WaitlistEntry.city, bucket_expr, func.count(WaitlistEntry.id))
            .where(WaitlistEntry.age.isnot(None))
            .group_by(WaitlistEntry.city, bucket_expr)
        )
    ).all()
    age_ranges: dict[str, dict[str, int]] = defaultdict(dict)
    for city, bucket, count in age_rows:
        age_ranges[city][bucket] = count

    avg_age_rows = (
        await db.execute(
            select(WaitlistEntry.city, func.avg(WaitlistEntry.age))
            .where(WaitlistEntry.age.isnot(None))
            .group_by(WaitlistEntry.city)
        )
    ).all()
    avg_ages = {city: round(float(avg), 1) for city, avg in avg_age_rows if avg is not None}

    # Referrers, resolved to the city they were recruiting for.
    referrer = WaitlistEntry.__table__.alias("referrer")
    referred = WaitlistEntry.__table__.alias("referred")
    referrer_rows = (
        await db.execute(
            select(
                referrer.c.city,
                referrer.c.first_name,
                referrer.c.share_code,
                func.count(referred.c.id).label("referred_count"),
            )
            .select_from(
                referrer.join(referred, referred.c.referred_by_code == referrer.c.share_code)
            )
            .group_by(referrer.c.city, referrer.c.first_name, referrer.c.share_code)
            .order_by(func.count(referred.c.id).desc())
        )
    ).all()
    top_referrers: dict[str, list[dict]] = defaultdict(list)
    for city, first_name, share_code, referred_count in referrer_rows:
        if len(top_referrers[city]) < 10:
            top_referrers[city].append(
                {
                    "first_name": first_name,
                    "share_code": share_code,
                    "referred": referred_count,
                }
            )

    growth_rows = (
        await db.execute(
            select(
                WaitlistEntry.city,
                func.to_char(WaitlistEntry.created_at, "YYYY-MM").label("month"),
                func.count(WaitlistEntry.id),
            ).group_by(WaitlistEntry.city, "month")
        )
    ).all()
    growth: dict[str, dict[str, int]] = defaultdict(dict)
    for city, month, count in growth_rows:
        growth[city][month] = count

    cities = []
    for city, count in counts.items():
        brings = bring_to_table.get(city, {})
        established = sum(v for k, v in brings.items() if k in ESTABLISHED_SIGNALS)
        cities.append(
            {
                "city": city,
                "count": count,
                "potential_established": established,
                "gender": gender.get(city, {}),
                "interested_in": interested_in.get(city, {}),
                "pairings": dict(pairings.get(city, {})),
                "age_ranges": dict(age_ranges.get(city, {})),
                "avg_age": avg_ages.get(city),
                "looking_for": looking_for.get(city, {}),
                "what_matters": what_matters.get(city, {}),
                "bring_to_table": brings,
                "worth_joining": worth_joining.get(city, {}),
                "how_heard": how_heard.get(city, {}),
                "utm_source": utm_source.get(city, {}),
                "top_referrers": top_referrers.get(city, []),
                "growth": dict(sorted(growth.get(city, {}).items())),
            }
        )

    return {"total": total, "cities": cities}
