"""Going somewhere? — destinations members are heading to, and who else is.

Asks "where are you going and who do you want beside you" rather than only
"who do you want to date".
"""
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.destination import Destination, DestinationInterest, InterestLevel
from app.models.profile import Profile
from app.models.safety import Block
from app.models.user import User
from app.routers.profiles import profile_to_response

router = APIRouter(prefix="/api/destinations", tags=["destinations"])


class InterestUpdate(BaseModel):
    level: InterestLevel


def _destination_dict(d: Destination) -> dict:
    return {
        "id": d.id,
        "slug": d.slug,
        "name": d.name,
        "location": d.location,
        "blurb": d.blurb,
        "starts_on": d.starts_on.isoformat() if d.starts_on else None,
        "ends_on": d.ends_on.isoformat() if d.ends_on else None,
    }


@router.get("/")
async def list_destinations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Active destinations, each with interest counts and the caller's own mark."""
    destinations = (
        await db.execute(
            select(Destination)
            .where(Destination.is_active == True)  # noqa: E712
            .order_by(Destination.sort_order, Destination.name)
        )
    ).scalars().all()

    counts_rows = (
        await db.execute(
            select(
                DestinationInterest.destination_id,
                DestinationInterest.level,
                func.count(DestinationInterest.id),
            ).group_by(DestinationInterest.destination_id, DestinationInterest.level)
        )
    ).all()
    counts: dict[int, dict[str, int]] = {}
    for dest_id, level, count in counts_rows:
        bucket = counts.setdefault(dest_id, {"going": 0, "want_to_go": 0})
        bucket[level.value if hasattr(level, "value") else str(level)] = count

    mine: dict[int, str] = {}
    if user.profile:
        rows = (
            await db.execute(
                select(DestinationInterest.destination_id, DestinationInterest.level).where(
                    DestinationInterest.profile_id == user.profile.id
                )
            )
        ).all()
        mine = {d: (l.value if hasattr(l, "value") else str(l)) for d, l in rows}

    return [
        {
            **_destination_dict(d),
            "going_count": counts.get(d.id, {}).get("going", 0),
            "want_count": counts.get(d.id, {}).get("want_to_go", 0),
            "my_level": mine.get(d.id),
        }
        for d in destinations
    ]


async def _get_destination(slug: str, db: AsyncSession) -> Destination:
    dest = (
        await db.execute(select(Destination).where(Destination.slug == slug))
    ).scalar_one_or_none()
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found")
    return dest


@router.put("/{slug}")
async def set_interest(
    slug: str,
    data: InterestUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    dest = await _get_destination(slug, db)
    existing = (
        await db.execute(
            select(DestinationInterest).where(
                and_(
                    DestinationInterest.profile_id == user.profile.id,
                    DestinationInterest.destination_id == dest.id,
                )
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.level = data.level
    else:
        db.add(
            DestinationInterest(
                profile_id=user.profile.id, destination_id=dest.id, level=data.level
            )
        )
    await db.commit()
    return {"slug": slug, "level": data.level.value}


@router.delete("/{slug}")
async def clear_interest(
    slug: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    dest = await _get_destination(slug, db)
    existing = (
        await db.execute(
            select(DestinationInterest).where(
                and_(
                    DestinationInterest.profile_id == user.profile.id,
                    DestinationInterest.destination_id == dest.id,
                )
            )
        )
    ).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.commit()
    return {"slug": slug, "level": None}


@router.get("/{slug}/members")
async def destination_members(
    slug: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Who else is going, or wants to.

    Applies the same cross-type and block rules as Discover, so this can't be
    used to see people who are otherwise hidden from you.
    """
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    dest = await _get_destination(slug, db)

    blocked_rows = (
        await db.execute(
            select(Block.blocked_profile_id).where(Block.blocker_profile_id == user.profile.id)
        )
    ).all()
    blocked_by_rows = (
        await db.execute(
            select(Block.blocker_profile_id).where(Block.blocked_profile_id == user.profile.id)
        )
    ).all()
    excluded = {r[0] for r in blocked_rows} | {r[0] for r in blocked_by_rows}
    excluded.add(user.profile.id)

    rows = (
        await db.execute(
            select(Profile, User, DestinationInterest.level)
            .join(DestinationInterest, DestinationInterest.profile_id == Profile.id)
            .join(User, User.id == Profile.user_id)
            .where(
                DestinationInterest.destination_id == dest.id,
                Profile.is_active == True,  # noqa: E712
                Profile.is_hidden == False,  # noqa: E712
                User.user_type != user.user_type,
            )
            .order_by(DestinationInterest.created_at.desc())
            .limit(60)
        )
    ).all()

    members = [
        {**profile_to_response(profile, u).model_dump(mode="json"),
         "interest_level": level.value if hasattr(level, "value") else str(level)}
        for profile, u, level in rows
        if profile.id not in excluded
    ]

    return {"destination": _destination_dict(dest), "members": members}
