"""Who Liked Me, Favorites, Profile Views."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, UserType
from app.models.profile import Profile
from app.models.match import Like
from app.models.engagement import Favorite, ProfileView
from app.models.subscription import Subscription, SubscriptionTier
from app.routers.profiles import profile_to_response

router = APIRouter(prefix="/api/engagement", tags=["engagement"])


async def _get_tier(user_id: int, db: AsyncSession) -> SubscriptionTier:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalar_one_or_none()
    return sub.tier if sub else SubscriptionTier.FREE


# ─── Who Liked Me ───

@router.get("/likes-received")
async def get_likes_received(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get profiles that liked you. Free users see count + blurred previews, Premium+ see full profiles."""
    if not user.profile:
        return {"count": 0, "profiles": [], "is_premium": False}

    pid = user.profile.id
    tier = await _get_tier(user.id, db)
    is_premium = tier in (SubscriptionTier.PLUS, SubscriptionTier.PLUS_PLUS)
    # Attractive members get this free
    is_attractive = user.user_type == UserType.PLUS
    can_see = is_premium or is_attractive

    # Get profiles who liked me but I haven't liked back (no match yet)
    result = await db.execute(
        select(Like).where(Like.to_profile_id == pid)
    )
    likes = result.scalars().all()

    liker_pids = [l.from_profile_id for l in likes]
    count = len(liker_pids)

    if not can_see or not liker_pids:
        # Return count + blurred previews (just initials and city)
        previews = []
        if liker_pids:
            profiles_result = await db.execute(select(Profile).where(Profile.id.in_(liker_pids)))
            for p in profiles_result.scalars().all():
                previews.append({
                    "id": p.id,
                    "initial": p.display_name[0] if p.display_name else "?",
                    "city": p.city,
                    "age": None,  # Hidden for free users
                    "blurred": True,
                })
        return {"count": count, "profiles": previews, "is_premium": False}

    # Premium: full profiles
    profiles_result = await db.execute(select(Profile).where(Profile.id.in_(liker_pids)))
    profiles = profiles_result.scalars().all()

    user_ids = [p.user_id for p in profiles]
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    full_profiles = []
    for p in profiles:
        u = users_map.get(p.user_id)
        full_profiles.append(profile_to_response(p, u))

    return {"count": count, "profiles": full_profiles, "is_premium": True}


# ─── Likes Sent ───

@router.get("/likes-sent")
async def get_likes_sent(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get profiles that you liked."""
    if not user.profile:
        return []

    pid = user.profile.id
    result = await db.execute(
        select(Like).where(Like.from_profile_id == pid).order_by(Like.created_at.desc())
    )
    likes = result.scalars().all()
    if not likes:
        return []

    liked_pids = [l.to_profile_id for l in likes]
    profiles_result = await db.execute(select(Profile).where(Profile.id.in_(liked_pids)))
    profiles_map = {p.id: p for p in profiles_result.scalars().all()}

    user_ids = [p.user_id for p in profiles_map.values()]
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    return [
        profile_to_response(profiles_map[l.to_profile_id], users_map.get(profiles_map[l.to_profile_id].user_id))
        for l in likes
        if l.to_profile_id in profiles_map
    ]


# ─── Favorites ───

@router.post("/favorites/{profile_id}", status_code=201)
async def add_favorite(
    profile_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")
    if profile_id == user.profile.id:
        raise HTTPException(status_code=400, detail="Cannot favorite yourself")

    existing = await db.execute(
        select(Favorite).where(
            Favorite.from_profile_id == user.profile.id,
            Favorite.to_profile_id == profile_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already favorited")

    fav = Favorite(from_profile_id=user.profile.id, to_profile_id=profile_id)
    db.add(fav)
    await db.commit()
    return {"favorited": True}


@router.delete("/favorites/{profile_id}")
async def remove_favorite(
    profile_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    result = await db.execute(
        select(Favorite).where(
            Favorite.from_profile_id == user.profile.id,
            Favorite.to_profile_id == profile_id,
        )
    )
    fav = result.scalar_one_or_none()
    if not fav:
        raise HTTPException(status_code=404, detail="Not favorited")

    await db.delete(fav)
    await db.commit()
    return {"unfavorited": True}


@router.get("/favorites")
async def get_favorites(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        return []

    result = await db.execute(
        select(Favorite)
        .where(Favorite.from_profile_id == user.profile.id)
        .order_by(Favorite.created_at.desc())
    )
    favs = result.scalars().all()
    if not favs:
        return []

    pids = [f.to_profile_id for f in favs]
    profiles_result = await db.execute(select(Profile).where(Profile.id.in_(pids)))
    profiles_map = {p.id: p for p in profiles_result.scalars().all()}

    user_ids = [p.user_id for p in profiles_map.values()]
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    return [
        profile_to_response(profiles_map[f.to_profile_id], users_map.get(profiles_map[f.to_profile_id].user_id))
        for f in favs
        if f.to_profile_id in profiles_map
    ]


# ─── Profile Views ───

@router.post("/views/{profile_id}", status_code=201)
async def record_view(
    profile_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record that the current user viewed a profile. Debounced: only one view per profile per hour."""
    if not user.profile or profile_id == user.profile.id:
        return {"recorded": False}

    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    existing = await db.execute(
        select(ProfileView).where(
            ProfileView.viewer_profile_id == user.profile.id,
            ProfileView.viewed_profile_id == profile_id,
            ProfileView.created_at > one_hour_ago,
        )
    )
    if existing.scalar_one_or_none():
        return {"recorded": False}

    view = ProfileView(viewer_profile_id=user.profile.id, viewed_profile_id=profile_id)
    db.add(view)
    await db.commit()
    return {"recorded": True}


@router.get("/views")
async def get_my_views(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get who viewed my profile (Premium feature)."""
    if not user.profile:
        return {"count": 0, "weekly_count": 0, "viewers": [], "is_premium": False}

    pid = user.profile.id
    tier = await _get_tier(user.id, db)
    is_premium = tier in (SubscriptionTier.PLUS, SubscriptionTier.PLUS_PLUS)

    # Count total and weekly views
    total_result = await db.execute(
        select(func.count(ProfileView.id)).where(ProfileView.viewed_profile_id == pid)
    )
    total = total_result.scalar()

    week_ago = datetime.utcnow() - timedelta(days=7)
    weekly_result = await db.execute(
        select(func.count(ProfileView.id)).where(
            ProfileView.viewed_profile_id == pid,
            ProfileView.created_at > week_ago,
        )
    )
    weekly = weekly_result.scalar()

    if not is_premium:
        return {"count": total, "weekly_count": weekly, "viewers": [], "is_premium": False}

    # Premium: show who viewed (last 50)
    result = await db.execute(
        select(ProfileView.viewer_profile_id, func.max(ProfileView.created_at).label("last_viewed"))
        .where(ProfileView.viewed_profile_id == pid)
        .group_by(ProfileView.viewer_profile_id)
        .order_by(func.max(ProfileView.created_at).desc())
        .limit(50)
    )
    viewer_rows = result.all()

    if not viewer_rows:
        return {"count": total, "weekly_count": weekly, "viewers": [], "is_premium": True}

    viewer_pids = [r[0] for r in viewer_rows]
    profiles_result = await db.execute(select(Profile).where(Profile.id.in_(viewer_pids)))
    profiles_map = {p.id: p for p in profiles_result.scalars().all()}

    user_ids = [p.user_id for p in profiles_map.values()]
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    viewers = []
    for viewer_pid, last_viewed in viewer_rows:
        p = profiles_map.get(viewer_pid)
        if p:
            resp = profile_to_response(p, users_map.get(p.user_id))
            viewers.append({"profile": resp, "viewed_at": last_viewed.isoformat()})

    return {"count": total, "weekly_count": weekly, "viewers": viewers, "is_premium": True}
